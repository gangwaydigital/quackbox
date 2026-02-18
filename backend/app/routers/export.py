"""Export endpoints — CSV, HTML, EML, and attachment downloads."""
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse, Response
import io
import html as html_mod
from app.services.export import export_emails_csv, export_contacts_csv, export_threads_csv
from app.services.attachment_extractor import (
    extract_attachment, list_extractable_attachments, export_eml,
)
from app.database import get_db

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
