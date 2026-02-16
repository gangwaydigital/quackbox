"""Analytics endpoints for the dashboard."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Query
from app.services.analytics import (
    email_volume_by_month, top_contacts, activity_heatmap,
    yearly_summary, mailbox_breakdown, thread_stats,
    response_time_stats, compute_all_analytics, get_cached,
    communication_network
)
from app.database import get_db
from app.services.timeline import get_timeline_milestones, get_notification_counts

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
_executor = ThreadPoolExecutor(max_workers=1)

@router.get("/volume")
async def volume():
    cached = get_cached("volume_by_month")
    if cached: return cached
    return {"data": email_volume_by_month(), "computed_at": "live"}

@router.get("/contacts")
async def contacts(limit: int = 20):
    cached = get_cached("top_contacts")
    if cached: return cached
    return {"data": top_contacts(limit), "computed_at": "live"}

@router.get("/heatmap")
async def heatmap():
    cached = get_cached("activity_heatmap")
    if cached: return cached
    return {"data": activity_heatmap(), "computed_at": "live"}

@router.get("/yearly")
async def yearly():
    cached = get_cached("yearly_summary")
    if cached: return cached
    return {"data": yearly_summary(), "computed_at": "live"}

@router.get("/mailboxes")
async def mailboxes():
    cached = get_cached("mailbox_breakdown")
    if cached: return cached
    return {"data": mailbox_breakdown(), "computed_at": "live"}

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
    cached = get_cached("thread_stats")
    if cached: return cached
    return {"data": thread_stats(), "computed_at": "live"}

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
        rows = conn.execute("""
            SELECT strftime('%Y-%m-%d', date_sent) as day, COUNT(*) as count,
                   COUNT(DISTINCT sender_email) as senders
            FROM emails
            WHERE strftime('%Y', date_sent) = ? AND strftime('%m', date_sent) = ?
              AND date_sent IS NOT NULL
            GROUP BY day ORDER BY day ASC
        """, (str(year), f"{month:02d}")).fetchall()
        return {"year": year, "month": month, "days": [dict(r) for r in rows]}

@router.get("/calendar/day")
async def calendar_day_detail(date: str = Query(...)):
    """Get emails for a specific day."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, subject, sender_name, sender_email, date_sent,
                   mbox_source, has_attachments, thread_group_id
            FROM emails
            WHERE strftime('%Y-%m-%d', date_sent) = ?
            ORDER BY date_timestamp ASC
        """, (date,)).fetchall()
        return {"date": date, "emails": [dict(r) for r in rows], "total": len(rows)}

@router.get("/timeline")
async def timeline():
    return {"milestones": get_timeline_milestones()}

@router.get("/badges")
async def badges():
    return get_notification_counts()

@router.post("/compute")
async def compute():
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, compute_all_analytics)
    return {"message": "Analytics computation started in background."}
