"""Attachment index endpoints."""
import json
from fastapi import APIRouter, Query
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

        total_with = conn.execute(
            "SELECT COUNT(*) FROM emails WHERE has_attachments = 1"
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
