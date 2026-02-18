"""
Contact profiles service.

Auto-generates CRM-style profiles for every sender:
communication patterns, topics, response times, relationship scores.
"""
import math
import time
from app.database import get_db


def get_contact_profile(email_addr: str) -> dict:
    """Build a full profile for a single contact."""
    with get_db() as conn:
        # Basic info
        basic = conn.execute("""
            SELECT sender_email, sender_name,
                   COUNT(*) as total_emails,
                   MIN(date_sent) as first_seen,
                   MAX(date_sent) as last_seen,
                   SUM(CASE WHEN has_attachments = 1 THEN 1 ELSE 0 END) as with_attachments
            FROM emails
            WHERE sender_email = ?
            GROUP BY sender_email
        """, (email_addr,)).fetchone()

        if not basic:
            return None

        profile = dict(basic)

        # Monthly volume (sparkline)
        monthly = conn.execute("""
            SELECT strftime('%Y-%m', date_sent) as month, COUNT(*) as count
            FROM emails WHERE sender_email = ? AND date_sent IS NOT NULL
            GROUP BY month ORDER BY month ASC
        """, (email_addr,)).fetchall()
        profile["monthly_volume"] = [{"month": r["month"], "count": r["count"]} for r in monthly]

        # Activity by hour and day
        hourly = conn.execute("""
            SELECT CAST(strftime('%H', date_sent) AS INTEGER) as hour, COUNT(*) as count
            FROM emails WHERE sender_email = ? AND date_sent IS NOT NULL
            GROUP BY hour ORDER BY count DESC
        """, (email_addr,)).fetchall()
        profile["peak_hours"] = [{"hour": r["hour"], "count": r["count"]} for r in hourly[:3]]

        daily = conn.execute("""
            SELECT CAST(strftime('%w', date_sent) AS INTEGER) as day, COUNT(*) as count
            FROM emails WHERE sender_email = ? AND date_sent IS NOT NULL
            GROUP BY day ORDER BY count DESC
        """, (email_addr,)).fetchall()
        days_map = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
        profile["peak_days"] = [{"day": days_map[r["day"]], "count": r["count"]} for r in daily[:3]]

        # Mailboxes (shows if they email you, or you email them, etc.)
        mailboxes = conn.execute("""
            SELECT mbox_source, COUNT(*) as count
            FROM emails WHERE sender_email = ?
            GROUP BY mbox_source ORDER BY count DESC
        """, (email_addr,)).fetchall()
        profile["mailboxes"] = [{"name": r["mbox_source"], "count": r["count"]} for r in mailboxes]

        # Thread participation
        thread_info = conn.execute("""
            SELECT COUNT(DISTINCT thread_group_id) as thread_count
            FROM emails
            WHERE sender_email = ? AND thread_group_id IS NOT NULL
        """, (email_addr,)).fetchone()
        profile["thread_count"] = thread_info["thread_count"] if thread_info else 0

        # Top subjects (most common subject lines)
        subjects = conn.execute("""
            SELECT subject, COUNT(*) as count
            FROM emails WHERE sender_email = ? AND subject IS NOT NULL AND subject != ''
            GROUP BY subject ORDER BY count DESC LIMIT 10
        """, (email_addr,)).fetchall()
        profile["top_subjects"] = [{"subject": r["subject"], "count": r["count"]} for r in subjects]

        # Recent emails
        recent = conn.execute("""
            SELECT id, subject, date_sent, mbox_source
            FROM emails WHERE sender_email = ?
            ORDER BY date_timestamp DESC LIMIT 5
        """, (email_addr,)).fetchall()
        profile["recent_emails"] = [dict(r) for r in recent]

        # Names used (sometimes same email has different display names)
        names = conn.execute("""
            SELECT DISTINCT sender_name FROM emails
            WHERE sender_email = ? AND sender_name IS NOT NULL AND sender_name != ''
        """, (email_addr,)).fetchall()
        profile["known_names"] = [r["sender_name"] for r in names]

        # Relationship score (composite)
        profile["relationship_score"] = _compute_relationship_score(profile)

        return profile


def _compute_relationship_score(profile: dict) -> dict:
    """
    Compute a relationship strength score (0-100).
    Based on: volume, recency, frequency, thread depth.
    """
    total = profile.get("total_emails", 0)
    thread_count = profile.get("thread_count", 0)

    # Volume score (log scale, max around 1000 emails)
    volume_score = min(30, math.log1p(total) / math.log1p(1000) * 30)

    # Recency score
    recency_score = 0
    if profile.get("last_seen"):
        try:
            from datetime import datetime
            last = datetime.fromisoformat(profile["last_seen"].replace('Z', '+00:00'))
            now = datetime.now(last.tzinfo) if last.tzinfo else datetime.now()
            days_ago = (now - last).days
            if days_ago < 7: recency_score = 25
            elif days_ago < 30: recency_score = 20
            elif days_ago < 90: recency_score = 15
            elif days_ago < 365: recency_score = 8
            else: recency_score = 3
        except Exception:
            recency_score = 5

    # Frequency score (emails per month)
    months = len(profile.get("monthly_volume", []))
    if months > 0:
        avg_per_month = total / max(months, 1)
        freq_score = min(25, avg_per_month * 5)
    else:
        freq_score = 0

    # Thread engagement score
    thread_score = min(20, thread_count * 2)

    total_score = round(volume_score + recency_score + freq_score + thread_score)

    label = "acquaintance"
    if total_score >= 70: label = "close contact"
    elif total_score >= 50: label = "regular contact"
    elif total_score >= 30: label = "occasional contact"

    return {
        "score": min(100, total_score),
        "label": label,
        "breakdown": {
            "volume": round(volume_score),
            "recency": round(recency_score),
            "frequency": round(freq_score),
            "engagement": round(thread_score),
        }
    }


def list_contacts(
    sort_by: str = "total",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 50,
    search: str = None,
) -> dict:
    """List all contacts with basic stats."""
    conditions = ["sender_email != '' AND sender_email IS NOT NULL"]
    params = []

    if search:
        conditions.append("(sender_email LIKE ? OR sender_name LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = " AND ".join(conditions)

    allowed_sorts = {"total": "total_emails", "name": "display_name", "last": "last_seen", "first": "first_seen"}
    sort_col = allowed_sorts.get(sort_by, "total_emails")
    sort_dir = "ASC" if sort_order == "asc" else "DESC"
    offset = (page - 1) * page_size

    with get_db() as conn:
        total = conn.execute(f"""
            SELECT COUNT(DISTINCT sender_email) FROM emails WHERE {where}
        """, params).fetchone()[0]

        rows = conn.execute(f"""
            SELECT sender_email,
                   MAX(sender_name) as display_name,
                   COUNT(*) as total_emails,
                   MIN(date_sent) as first_seen,
                   MAX(date_sent) as last_seen,
                   COUNT(DISTINCT thread_group_id) as thread_count,
                   COUNT(DISTINCT mbox_source) as mailbox_count
            FROM emails
            WHERE {where}
            GROUP BY sender_email
            ORDER BY {sort_col} {sort_dir}
            LIMIT ? OFFSET ?
        """, params + [page_size, offset]).fetchall()

        items = [dict(r) for r in rows]

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }
