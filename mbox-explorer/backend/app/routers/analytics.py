"""Analytics endpoints for the dashboard."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter

from app.services.analytics import (
    email_volume_by_month,
    top_contacts,
    activity_heatmap,
    yearly_summary,
    mailbox_breakdown,
    thread_stats,
    response_time_stats,
    compute_all_analytics,
    get_cached,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

_executor = ThreadPoolExecutor(max_workers=1)


@router.get("/volume")
async def volume():
    """Email volume by month."""
    cached = get_cached("volume_by_month")
    if cached:
        return cached
    return {"data": email_volume_by_month(), "computed_at": "live"}


@router.get("/contacts")
async def contacts(limit: int = 20):
    """Top contacts with sparkline data."""
    cached = get_cached("top_contacts")
    if cached:
        return cached
    return {"data": top_contacts(limit), "computed_at": "live"}


@router.get("/heatmap")
async def heatmap():
    """Activity heatmap (day x hour)."""
    cached = get_cached("activity_heatmap")
    if cached:
        return cached
    return {"data": activity_heatmap(), "computed_at": "live"}


@router.get("/yearly")
async def yearly():
    """Year-by-year summary."""
    cached = get_cached("yearly_summary")
    if cached:
        return cached
    return {"data": yearly_summary(), "computed_at": "live"}


@router.get("/mailboxes")
async def mailboxes():
    """Email counts per mailbox."""
    cached = get_cached("mailbox_breakdown")
    if cached:
        return cached
    return {"data": mailbox_breakdown(), "computed_at": "live"}


@router.get("/threads")
async def threads():
    """Thread statistics."""
    cached = get_cached("thread_stats")
    if cached:
        return cached
    return {"data": thread_stats(), "computed_at": "live"}


@router.get("/response-times")
async def response_times():
    """Response time analysis."""
    return {"data": response_time_stats(), "computed_at": "live"}


@router.post("/compute")
async def compute():
    """Pre-compute and cache all analytics (runs in background)."""
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, compute_all_analytics)
    return {"message": "Analytics computation started in background."}
