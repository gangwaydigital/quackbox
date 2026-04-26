"""Export endpoints — CSV, HTML, EML, and attachment downloads."""
import io
import json
import re
import zipfile
import html as html_mod
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse, Response

from app.services.export import export_emails_csv, export_contacts_csv, export_threads_csv
from app.services.attachment_extractor import (
    extract_attachment, list_extractable_attachments, export_eml,
)
from app.database import get_db
from app.logging_config import get_logger
from app.utils.email_utils import _is_noise_attachment

log = get_logger("export")

# Hard caps so a single zip request can't OOM the backend
ZIP_MAX_FILES = 2000
ZIP_DEFAULT_FILES = 500
# Filename sanitization — keep alnum, dot, dash, underscore, space; replace
# anything else (including path separators) with underscore
_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._\- ]")

router = APIRouter(prefix="/api/export", tags=["export"])

def _csv_response(content: str, filename: str):
    return StreamingResponse(io.StringIO(content), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"})

@router.get("/emails")
async def export_emails(sender_email: str = Query(None), date_from: str = Query(None),
    date_to: str = Query(None), mbox_source: str = Query(None),
    subject_contains: str = Query(None), limit: int = Query(10000)):
    csv_data = export_emails_csv(sender_email=sender_email, date_from=date_from,
        date_to=date_to, mbox_source=mbox_source, subject_contains=subject_contains, limit=limit)
    return _csv_response(csv_data, "mbox-emails-export.csv")

@router.get("/contacts")
async def export_contacts_endpoint(limit: int = Query(5000)):
    return _csv_response(export_contacts_csv(limit), "mbox-contacts-export.csv")

@router.get("/threads")
async def export_threads_endpoint(min_messages: int = Query(2), limit: int = Query(5000)):
    return _csv_response(export_threads_csv(min_messages, limit), "mbox-threads-export.csv")

@router.get("/thread/{thread_id}/html")
async def export_thread_html(thread_id: int):
    """Export a thread as printable HTML."""
    with get_db() as conn:
        thread = conn.execute("SELECT * FROM threads WHERE id = ?", (thread_id,)).fetchone()
        if not thread:
            raise HTTPException(404, "Thread not found")
        emails = conn.execute("""
            SELECT subject, sender_name, sender_email, date_sent, body_text
            FROM emails WHERE thread_group_id = ?
            ORDER BY date_timestamp ASC
        """, (thread_id,)).fetchall()

    subject = html_mod.escape(thread["subject_normalized"] or "(no subject)")
    msg_count = len(emails)
    first_date = emails[0]["date_sent"] if emails else ""
    last_date = emails[-1]["date_sent"] if emails else ""

    messages_html = ""
    for e in emails:
        sender = html_mod.escape(e["sender_name"] or e["sender_email"] or "Unknown")
        date = html_mod.escape(e["date_sent"] or "")
        body = html_mod.escape(e["body_text"] or "(no body)")
        messages_html += f"""
        <div class="message">
            <div class="msg-header">
                <strong>{sender}</strong>
                <span class="date">{date}</span>
            </div>
            <div class="msg-body"><pre>{body}</pre></div>
        </div>"""

    page_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{subject}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 800px; margin: 0 auto; padding: 40px 20px; color: #1a1a1a; }}
  h1 {{ font-size: 20px; margin-bottom: 4px; }}
  .meta {{ color: #666; font-size: 13px; margin-bottom: 30px; }}
  .message {{ border: 1px solid #e5e5e5; border-radius: 8px; margin-bottom: 16px; overflow: hidden; }}
  .msg-header {{ background: #f8f9fa; padding: 10px 16px; border-bottom: 1px solid #e5e5e5; display: flex; justify-content: space-between; align-items: center; }}
  .msg-header strong {{ font-size: 14px; }}
  .date {{ font-size: 12px; color: #888; }}
  .msg-body {{ padding: 16px; }}
  .msg-body pre {{ white-space: pre-wrap; word-wrap: break-word; font-family: inherit; font-size: 13px; margin: 0; line-height: 1.6; }}
  @media print {{ body {{ padding: 0; }} .message {{ break-inside: avoid; }} }}
  .footer {{ text-align: center; color: #aaa; font-size: 11px; margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; }}
</style></head><body>
<h1>{subject}</h1>
<div class="meta">{msg_count} messages · {first_date[:10] if first_date else ''} → {last_date[:10] if last_date else ''}</div>
{messages_html}
<div class="footer">Exported from QuackBox</div>
</body></html>"""
    return HTMLResponse(content=page_html)


@router.get("/email/{email_id}/eml")
async def export_email_eml(email_id: int):
    """Export a single email as a downloadable .eml file."""
    result = export_eml(email_id)
    if result is None:
        raise HTTPException(
            404,
            "Email not found or original source file is unavailable. "
            "The mbox/emlx file must be accessible in the data directory."
        )
    return Response(
        content=result["data"],
        media_type="message/rfc822",
        headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'},
    )


@router.get("/email/{email_id}/attachments")
async def list_email_attachments(email_id: int):
    """List all extractable attachments for an email with sizes."""
    attachments = list_extractable_attachments(email_id)
    return {"email_id": email_id, "attachments": attachments}


@router.get("/email/{email_id}/attachment/{filename:path}")
async def download_attachment(email_id: int, filename: str):
    """Download a specific attachment from an email."""
    result = extract_attachment(email_id, filename)
    if result is None:
        raise HTTPException(
            404,
            f"Attachment '{filename}' not found. "
            "The original mbox/emlx source file must be accessible."
        )
    return Response(
        content=result["data"],
        media_type=result["content_type"],
        headers={
            "Content-Disposition": f'attachment; filename="{result["filename"]}"',
            "Content-Length": str(len(result["data"])),
        },
    )


# ── Bulk attachment archive ────────────────────────────────────────────────


def _safe_zip_name(date_iso: Optional[str], email_id: int, filename: str) -> str:
    """
    Build a collision-free, path-safe entry name for the zip:
      2024-01/<date>__<id>__<filename>

    Grouping into year-month folders keeps a few hundred attachments
    browsable. Including the email_id disambiguates same-named files
    across different messages.
    """
    folder = (date_iso or "")[:7] or "unknown"
    base = _FILENAME_SAFE.sub("_", filename or "")
    # Collapse path-traversal-ish dot runs and leading dots so the output
    # can't be interpreted as a parent reference by a careless extractor.
    base = re.sub(r"\.{2,}", ".", base).lstrip(".")
    base = base or "attachment"
    return f"{folder}/{(date_iso or '')[:10]}__{email_id}__{base}"


def _select_attachments_for_zip(
    *, search: Optional[str], sender_email: Optional[str],
    mbox_source: Optional[str], limit: int,
) -> list[dict]:
    """Build the candidate list of (email_id, filename, date_sent) tuples
    that match the same filters the Attachments page shows. Hides smime
    noise via the same DB-level filter as the listing endpoint."""
    where = [
        "e.has_attachments = 1",
        "e.attachment_names IS NOT NULL",
        "json_valid(e.attachment_names)",
        "j.value IS NOT NULL",
        "j.value != ''",
        "LOWER(j.value) NOT IN ('smime.p7s', 'smime.p7m')",
    ]
    params: dict = {}
    if search:
        where.append("(LOWER(j.value) LIKE :pat OR LOWER(COALESCE(e.subject,'')) LIKE :pat)")
        params["pat"] = f"%{search.lower()}%"
    if sender_email:
        where.append("e.sender_email = :sender")
        params["sender"] = sender_email
    if mbox_source:
        where.append("e.mbox_source = :mbox")
        params["mbox"] = mbox_source

    sql = f"""
        SELECT e.id AS email_id, e.date_sent, e.subject, j.value AS filename
        FROM emails e, json_each(e.attachment_names) j
        WHERE {' AND '.join(where)}
        ORDER BY e.date_timestamp DESC
        LIMIT :lim
    """
    with get_db() as conn:
        rows = conn.execute(sql, {**params, "lim": limit}).fetchall()
    return [dict(r) for r in rows]


@router.get("/attachments.zip")
async def export_attachments_zip(
    search: Optional[str] = Query(None, description="Filename / subject substring filter"),
    sender_email: Optional[str] = Query(None),
    mbox_source: Optional[str] = Query(None),
    limit: int = Query(ZIP_DEFAULT_FILES, ge=1, le=ZIP_MAX_FILES,
                       description=f"Max files to include (default {ZIP_DEFAULT_FILES}, hard cap {ZIP_MAX_FILES})"),
):
    """
    Stream a zip of attachments matching the given filters.

    Filters mirror the Attachments page: search text, sender, mailbox.
    smime.p7s noise is excluded automatically. Files are grouped into
    YYYY-MM folders inside the zip, and each entry is prefixed with
    the source email id + date so same-named attachments across
    different messages don't collide.

    The zip is built in memory; capped at `limit` files (max 2000) so
    a single request can't blow up the backend. For larger archives,
    narrow the filters or download per-email.
    """
    candidates = _select_attachments_for_zip(
        search=search, sender_email=sender_email,
        mbox_source=mbox_source, limit=limit,
    )
    if not candidates:
        raise HTTPException(404, "No attachments match those filters.")

    buf = io.BytesIO()
    included = 0
    skipped = 0
    seen_names: set[str] = set()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for cand in candidates:
            email_id = cand["email_id"]
            filename = cand["filename"]
            if _is_noise_attachment(filename):  # belt-and-suspenders
                skipped += 1
                continue
            extracted = extract_attachment(email_id, filename)
            if not extracted:
                skipped += 1
                log.debug("Could not extract %s from email %d", filename, email_id)
                continue
            entry_name = _safe_zip_name(cand.get("date_sent"), email_id, extracted["filename"])
            # In the unlikely case of a collision (same date+id+name), tack a counter
            base_entry = entry_name
            counter = 1
            while entry_name in seen_names:
                counter += 1
                entry_name = f"{base_entry}.{counter}"
            seen_names.add(entry_name)
            zf.writestr(entry_name, extracted["data"])
            included += 1

    if included == 0:
        raise HTTPException(404, "No attachments could be extracted (source files missing?).")

    log.info(
        "📦 attachments.zip: %d included, %d skipped, %d candidates considered",
        included, skipped, len(candidates),
    )

    buf.seek(0)
    body = buf.getvalue()
    parts = []
    if search: parts.append(re.sub(r"[^A-Za-z0-9_-]", "_", search)[:30])
    if sender_email: parts.append(sender_email.split("@")[0])
    if mbox_source: parts.append(re.sub(r"[^A-Za-z0-9_-]", "_", mbox_source)[:30])
    suffix = "-".join(parts) if parts else "all"
    download_name = f"quackbox-attachments-{suffix}-{included}.zip"

    return Response(
        content=body,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{download_name}"',
            "Content-Length": str(len(body)),
            "X-Quackbox-Included": str(included),
            "X-Quackbox-Skipped": str(skipped),
        },
    )
