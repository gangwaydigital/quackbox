"""Calendar event endpoints — list, stats, and trigger indexing."""
import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Query

from app.services.calendar_extractor import (
    list_events,
    get_event_stats,
    index_all_calendar_events,
)

router = APIRouter(prefix="/api/calendar-events", tags=["calendar"])

_executor = ThreadPoolExecutor(max_workers=1)
_index_status = {"running": False, "result": None, "error": None}


def _run_index_sync():
    global _index_status
    try:
        _index_status = {"running": True, "result": None, "error": None}
        result = index_all_calendar_events()
        _index_status = {"running": False, "result": result, "error": None}
    except Exception as e:
        _index_status = {"running": False, "result": None, "error": str(e)}


@router.get("")
async def get_events(
    upcoming: bool = Query(False, description="Only events that haven't started yet"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str = Query(None),
):
    return list_events(upcoming_only=upcoming, page=page, page_size=page_size, search=search)


@router.get("/stats")
async def stats():
    return get_event_stats()


@router.post("/index")
async def trigger_indexing():
    """Scan every email with a stored raw_message for calendar events."""
    if _index_status["running"]:
        return {"message": "Indexing already running", **_index_status}
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _run_index_sync)
    return {"message": "Calendar indexing started in background. Check /api/calendar-events/status."}


@router.get("/status")
async def index_status():
    return _index_status
