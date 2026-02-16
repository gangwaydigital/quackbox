"""Attachment index endpoints."""
import json
from fastapi import APIRouter, Query
from app.database import get_db

router = APIRouter(prefix="/api/attachments", tags=["attachments"])

@router.get("")
async def list_attachments(
    search: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort_by: str = Query("date"),
):
    """List all attachments across the archive."""
    with get_db() as conn:
        # Get all emails with attachments
        rows = conn.execute("""
            SELECT id, subject, sender_name, sender_email, date_sent,
                   mbox_source, attachment_names
            FROM emails
            WHERE has_attachments = 1 AND attachment_names IS NOT NULL
            ORDER BY date_timestamp DESC
        """).fetchall()

        # Flatten to individual attachments
        attachments = []
        for row in rows:
            try:
                names = json.loads(row["attachment_names"]) if row["attachment_names"] else []
            except (json.JSONDecodeError, TypeError):
                continue
            for name in names:
                if not name: continue
                attachments.append({
                    "filename": name,
                    "extension": name.rsplit('.', 1)[-1].lower() if '.' in name else '',
                    "email_id": row["id"],
                    "subject": row["subject"],
                    "sender_name": row["sender_name"],
                    "sender_email": row["sender_email"],
                    "date_sent": row["date_sent"],
                    "mbox_source": row["mbox_source"],
                })

        # Filter by search
        if search:
            search_lower = search.lower()
            attachments = [a for a in attachments if search_lower in a["filename"].lower()
                          or search_lower in (a.get("subject") or "").lower()]

        # Sort
        if sort_by == "name":
            attachments.sort(key=lambda a: a["filename"].lower())
        elif sort_by == "type":
            attachments.sort(key=lambda a: a["extension"])
        # default: date (already sorted)

        total = len(attachments)
        offset = (page - 1) * page_size
        page_items = attachments[offset:offset + page_size]

        # Extension stats
        ext_counts = {}
        for a in attachments:
            ext = a["extension"] or "other"
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
        top_extensions = sorted(ext_counts.items(), key=lambda x: -x[1])[:15]

        return {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
            "top_extensions": [{"ext": e, "count": c} for e, c in top_extensions],
        }

@router.get("/stats")
async def attachment_stats():
    """Get attachment statistics."""
    with get_db() as conn:
        total_with = conn.execute("SELECT COUNT(*) FROM emails WHERE has_attachments = 1").fetchone()[0]
        rows = conn.execute("""
            SELECT attachment_names FROM emails
            WHERE has_attachments = 1 AND attachment_names IS NOT NULL
        """).fetchall()

        total_files = 0
        ext_counts = {}
        for row in rows:
            try:
                names = json.loads(row["attachment_names"]) if row["attachment_names"] else []
            except (json.JSONDecodeError, TypeError):
                continue
            for name in names:
                if not name: continue
                total_files += 1
                ext = name.rsplit('.', 1)[-1].lower() if '.' in name else 'other'
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

        return {
            "emails_with_attachments": total_with,
            "total_files": total_files,
            "top_extensions": sorted(ext_counts.items(), key=lambda x: -x[1])[:20],
        }
