"""Analytics endpoints for the dashboard."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Query
from app.services.analytics import (
    email_volume_by_month, top_contacts, activity_heatmap,
    yearly_summary, mailbox_breakdown, thread_stats,
    response_time_stats, communication_network,
    dashboard_batch, warm_cache, _cached_or_compute
)
from app.database import get_db, get_stats
from app.services.timeline import get_timeline_milestones, get_notification_counts

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
_executor = ThreadPoolExecutor(max_workers=1)


@router.get("/dashboard")
async def dashboard():
    """
    Single endpoint that returns all dashboard data.
    Uses cache where fresh, computes and caches the rest.
    Replaces 6 separate API calls with 1.
    """
    data = dashboard_batch()
    data["stats"] = get_stats()
    data["badges"] = get_notification_counts()
    return data

@router.get("/volume")
async def volume():
    return _cached_or_compute("volume_by_month", email_volume_by_month)

@router.get("/contacts")
async def contacts(limit: int = 20):
    return _cached_or_compute("top_contacts", lambda: top_contacts(limit))

@router.get("/heatmap")
async def heatmap():
    return _cached_or_compute("activity_heatmap", activity_heatmap)

@router.get("/yearly")
async def yearly():
    return _cached_or_compute("yearly_summary", yearly_summary)

@router.get("/mailboxes")
async def mailboxes():
    return _cached_or_compute("mailbox_breakdown", mailbox_breakdown)

@router.get("/mailbox/{mailbox_name:path}")
async def mailbox_detail(mailbox_name: str):
    with get_db() as conn:
        basic = conn.execute("""
            SELECT COUNT(*) as total, MIN(date_sent) as first, MAX(date_sent) as last,
                   COUNT(DISTINCT sender_email) as senders,
                   SUM(CASE WHEN has_attachments = 1 THEN 1 ELSE 0 END) as attachments,
                   COUNT(DISTINCT thread_group_id) as threads
            FROM emails WHERE mbox_source = ?
        """, (mailbox_name,)).fetchone()
        if not basic or basic["total"] == 0:
            return {"error": f"Mailbox '{mailbox_name}' not found"}
        monthly = conn.execute("""
            SELECT strftime('%Y-%m', date_sent) as month, COUNT(*) as count
            FROM emails WHERE mbox_source = ? AND date_sent IS NOT NULL
            GROUP BY month ORDER BY month ASC
        """, (mailbox_name,)).fetchall()
        top_senders = conn.execute("""
            SELECT sender_email, sender_name, COUNT(*) as count
            FROM emails WHERE mbox_source = ? AND sender_email != ''
            GROUP BY sender_email ORDER BY count DESC LIMIT 15
        """, (mailbox_name,)).fetchall()
        yearly_data = conn.execute("""
            SELECT strftime('%Y', date_sent) as year, COUNT(*) as count
            FROM emails WHERE mbox_source = ? AND date_sent IS NOT NULL
            GROUP BY year ORDER BY year ASC
        """, (mailbox_name,)).fetchall()
        return {
            "name": mailbox_name, "total_emails": basic["total"],
            "first_date": basic["first"], "last_date": basic["last"],
            "unique_senders": basic["senders"], "attachments": basic["attachments"],
            "threads": basic["threads"],
            "monthly_volume": [dict(r) for r in monthly],
            "top_senders": [dict(r) for r in top_senders],
            "yearly": [dict(r) for r in yearly_data],
        }

@router.get("/threads")
async def threads():
    return _cached_or_compute("thread_stats", thread_stats)

@router.get("/response-times")
async def response_times():
    return {"data": response_time_stats(), "computed_at": "live"}

@router.get("/network")
async def network(min_shared: int = Query(1, ge=1), limit: int = Query(80, ge=10, le=200)):
    return communication_network(min_shared_threads=min_shared, limit_contacts=limit)

@router.get("/calendar")
async def calendar_data(year: int = Query(...), month: int = Query(...)):
    """Get email counts per day for a given month."""
    with get_db() as conn:
        # Use range comparison instead of strftime() to leverage date index
        start = f"{year:04d}-{month:02d}-01"
        if month == 12:
            end = f"{year + 1:04d}-01-01"
        else:
            end = f"{year:04d}-{month + 1:02d}-01"
        rows = conn.execute("""
            SELECT strftime('%Y-%m-%d', date_sent) as day, COUNT(*) as count,
                   COUNT(DISTINCT sender_email) as senders
            FROM emails
            WHERE date_sent >= ? AND date_sent < ? AND date_sent IS NOT NULL
            GROUP BY day ORDER BY day ASC
        """, (start, end)).fetchall()
        return {"year": year, "month": month, "days": [dict(r) for r in rows]}

@router.get("/calendar/day")
async def calendar_day_detail(date: str = Query(...)):
    """Get emails for a specific day."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, subject, sender_name, sender_email, date_sent,
                   mbox_source, has_attachments, thread_group_id
            FROM emails
            WHERE date_sent >= ? AND date_sent < date(?, '+1 day')
            ORDER BY date_timestamp ASC
        """, (date, date)).fetchall()
        return {"date": date, "emails": [dict(r) for r in rows], "total": len(rows)}

@router.get("/timeline")
async def timeline():
    return {"milestones": get_timeline_milestones()}

@router.get("/badges")
async def badges():
    return get_notification_counts()

@router.post("/compute")
async def compute():
    """Recompute and cache all analytics."""
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, warm_cache)
    return {"message": "Analytics computation started in background."}
