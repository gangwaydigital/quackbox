"""Attachment index endpoints."""
import json
import mimetypes
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import Response
from app.database import get_db
from app.logging_config import get_logger

router = APIRouter(prefix="/api/attachments", tags=["attachments"])
log = get_logger("attachments")


def _file_ext(name):
    """Return the lowercase extension of a filename, or empty string."""
    if not name or "." not in name:
        return ""
    return name.rsplit(".", 1)[-1].lower()


_SORT_COLUMNS = {
    "date": "date_timestamp DESC, email_id DESC",
    "name": "LOWER(filename) ASC",
    "type": "file_ext(filename) ASC, LOWER(filename) ASC",
}


@router.get("")
async def list_attachments(
    search: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort_by: str = Query("date"),
):
    """List all attachments across the archive."""
    with get_db() as conn:
        conn.create_function("file_ext", 1, _file_ext, deterministic=True)

        order_by = _SORT_COLUMNS.get(sort_by, _SORT_COLUMNS["date"])
        params = {}
        where = """
            e.has_attachments = 1
            AND e.attachment_names IS NOT NULL
            AND json_valid(e.attachment_names)
            AND j.value IS NOT NULL AND j.value != ''
            AND LOWER(j.value) NOT IN ('smime.p7s', 'smime.p7m')
        """
        if search:
            where += " AND (LOWER(j.value) LIKE :pat OR LOWER(COALESCE(e.subject,'')) LIKE :pat)"
            params["pat"] = f"%{search.lower()}%"

        base_from = f"FROM emails e, json_each(e.attachment_names) j WHERE {where}"

        # Total count
        total = conn.execute(f"SELECT COUNT(*) {base_from}", params).fetchone()[0]

        # Page items
        offset = (page - 1) * page_size
        rows = conn.execute(
            f"""
            SELECT e.id AS email_id, e.subject, e.sender_name, e.sender_email,
                   e.date_sent, e.date_timestamp, e.mbox_source,
                   j.value AS filename, file_ext(j.value) AS extension
            {base_from}
            ORDER BY {order_by}
            LIMIT :ps OFFSET :off
            """,
            {**params, "ps": page_size, "off": offset},
        ).fetchall()

        page_items = [
            {
                "filename": r["filename"],
                "extension": r["extension"],
                "email_id": r["email_id"],
                "subject": r["subject"],
                "sender_name": r["sender_name"],
                "sender_email": r["sender_email"],
                "date_sent": r["date_sent"],
                "mbox_source": r["mbox_source"],
            }
            for r in rows
        ]

        # Top extensions across the full filtered set (not just this page)
        ext_rows = conn.execute(
            f"""
            SELECT COALESCE(NULLIF(file_ext(j.value), ''), 'other') AS ext, COUNT(*) AS c
            {base_from}
            GROUP BY ext
            ORDER BY c DESC
            LIMIT 15
            """,
            params,
        ).fetchall()
        top_extensions = [{"ext": r["ext"], "count": r["c"]} for r in ext_rows]

        return {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
            "top_extensions": top_extensions,
        }


@router.get("/stats")
async def attachment_stats():
    """Get attachment statistics."""
    with get_db() as conn:
        conn.create_function("file_ext", 1, _file_ext, deterministic=True)

        # Count emails with at least one *real* attachment (not smime.p7s noise)
        total_with = conn.execute(
            """
            SELECT COUNT(DISTINCT e.id)
            FROM emails e, json_each(e.attachment_names) j
            WHERE e.has_attachments = 1
              AND e.attachment_names IS NOT NULL
              AND json_valid(e.attachment_names)
              AND j.value IS NOT NULL AND j.value != ''
              AND LOWER(j.value) NOT IN ('smime.p7s', 'smime.p7m')
            """
        ).fetchone()[0]

        # Skip rows whose JSON failed to parse, but warn so they don't disappear silently
        invalid = conn.execute(
            """
            SELECT id FROM emails
            WHERE has_attachments = 1
              AND attachment_names IS NOT NULL
              AND NOT json_valid(attachment_names)
            LIMIT 5
            """
        ).fetchall()
        if invalid:
            log.warning(
                "Skipping %d email row(s) with invalid attachment_names JSON (sample ids: %s)",
                len(invalid), [r["id"] for r in invalid],
            )

        ext_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(file_ext(j.value), ''), 'other') AS ext, COUNT(*) AS c
            FROM emails e, json_each(e.attachment_names) j
            WHERE e.has_attachments = 1
              AND e.attachment_names IS NOT NULL
              AND json_valid(e.attachment_names)
              AND j.value IS NOT NULL AND j.value != ''
              AND LOWER(j.value) NOT IN ('smime.p7s', 'smime.p7m')
            GROUP BY ext
            ORDER BY c DESC
            LIMIT 20
            """
        ).fetchall()

        total_files = sum(r["c"] for r in ext_rows)

        return {
            "emails_with_attachments": total_with,
            "total_files": total_files,
            "top_extensions": [(r["ext"], r["c"]) for r in ext_rows],
        }


# ── Attachment text preview & full-text search ───────────────────────────

@router.get("/{email_id}/{filename}/preview")
async def preview_attachment(email_id: int, filename: str):
    """
    Return extracted text content for a PDF or DOCX attachment.

    Triggers extraction on first call if not yet indexed.
    """
    from app.services.attachment_indexer import get_attachment_preview, index_attachment

    preview = get_attachment_preview(email_id, filename)
    if preview is None:
        # Index on demand
        result = index_attachment(email_id, filename)
        preview = get_attachment_preview(email_id, filename)
        if preview is None:
            from fastapi import HTTPException
            raise HTTPException(404, f"Could not extract text from {filename}")

    return preview


@router.get("/search/content")
async def search_attachment_content(
    q: str = Query(..., min_length=2),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Full-text search across indexed PDF/DOCX attachment content."""
    from app.services.attachment_indexer import search_attachment_content as sac
    return sac(query=q, page=page, page_size=page_size)


@router.post("/index")
async def trigger_indexing():
    """Trigger background indexing of all PDF/DOCX attachments."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from app.services.attachment_indexer import index_all_attachments
    executor = ThreadPoolExecutor(max_workers=1)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(executor, index_all_attachments)
    return {"message": "Attachment indexing started in background"}


# ── Disk-scanned attachments (Apple Mail Attachments/ trees) ───────────────


@router.get("/disk")
async def list_disk_attachments(
    search: str = Query(None),
    mailbox: str = Query(None, description="Filter by mailbox_hint"),
    extension: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List attachments discovered by walking */Attachments/ on disk —
    independent of whether we could link them to a specific email row."""
    conditions: list[str] = []
    params: dict = {}
    if search:
        conditions.append("LOWER(filename) LIKE :pat")
        params["pat"] = f"%{search.lower()}%"
    if mailbox:
        conditions.append("mailbox_hint = :mbx")
        params["mbx"] = mailbox
    if extension:
        conditions.append("extension = :ext")
        params["ext"] = extension.lower().lstrip(".")
    where = " AND ".join(conditions) if conditions else "1=1"
    offset = (page - 1) * page_size

    with get_db() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM disk_attachments WHERE {where}", params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT id, file_path, filename, extension, size, mailbox_hint, file_mtime
            FROM disk_attachments
            WHERE {where}
            ORDER BY file_mtime DESC, id DESC
            LIMIT :ps OFFSET :off
            """,
            {**params, "ps": page_size, "off": offset},
        ).fetchall()
        # Top extensions in the filtered set
        ext_rows = conn.execute(
            f"""
            SELECT COALESCE(NULLIF(extension, ''), 'other') AS ext, COUNT(*) AS c
            FROM disk_attachments
            WHERE {where}
            GROUP BY ext
            ORDER BY c DESC
            LIMIT 15
            """,
            params,
        ).fetchall()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "top_extensions": [{"ext": r["ext"], "count": r["c"]} for r in ext_rows],
    }


@router.get("/disk/stats")
async def disk_attachments_stats():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM disk_attachments").fetchone()[0]
        mailboxes = conn.execute("""
            SELECT mailbox_hint, COUNT(*) AS c
            FROM disk_attachments
            WHERE mailbox_hint IS NOT NULL
            GROUP BY mailbox_hint
            ORDER BY c DESC
            LIMIT 20
        """).fetchall()
        ext_rows = conn.execute("""
            SELECT COALESCE(NULLIF(extension, ''), 'other') AS ext, COUNT(*) AS c
            FROM disk_attachments
            GROUP BY ext
            ORDER BY c DESC
            LIMIT 20
        """).fetchall()
    return {
        "total_files": total,
        "top_mailboxes": [{"name": r["mailbox_hint"], "count": r["c"]} for r in mailboxes],
        "top_extensions": [{"ext": r["ext"], "count": r["c"]} for r in ext_rows],
    }


@router.get("/disk/{att_id}/download")
async def download_disk_attachment(att_id: int):
    """Serve the file at the stored file_path. Security: the path must
    fall inside one of the configured browse roots — we don't let an
    arbitrary path leak via a bogus database row."""
    from app.services.folders import HOST_ROOTS

    with get_db() as conn:
        row = conn.execute(
            "SELECT file_path, filename FROM disk_attachments WHERE id = ?",
            (att_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Disk attachment not found.")

    p = Path(row["file_path"]).resolve()
    # The data dir is /app/data inside the container, OR a path under /host.
    safe_roots = ["/app/data"] + list(HOST_ROOTS)
    if not any(str(p).startswith(root) for root in safe_roots):
        raise HTTPException(403, "Attachment path is outside permitted roots.")
    if not p.is_file():
        raise HTTPException(
            404,
            "File no longer exists on disk — drive unmounted or file moved.",
        )

    try:
        data = p.read_bytes()
    except OSError as e:
        raise HTTPException(500, f"Could not read file: {e}")

    ct, _ = mimetypes.guess_type(p.name)
    return Response(
        content=data,
        media_type=ct or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{row["filename"]}"',
            "Content-Length": str(len(data)),
        },
    )
