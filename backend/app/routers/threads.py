"""Thread endpoints."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException, Query
from app.services.threads import rebuild_threads, get_threads, get_thread_detail, get_thread_participants
from app.services.summarizer import summarize_thread, summarize_email

router = APIRouter(prefix="/api/threads", tags=["threads"])
_executor = ThreadPoolExecutor(max_workers=1)
_task_status = {"running": False, "progress": "", "result": None, "error": None}

def _rebuild_sync():
    global _task_status
    try:
        _task_status = {"running": True, "progress": "Rebuilding threads...", "result": None, "error": None}
        result = rebuild_threads()
        _task_status = {"running": False, "progress": "Done", "result": result, "error": None}
    except Exception as e:
        _task_status = {"running": False, "progress": "", "result": None, "error": str(e)}

@router.post("/rebuild")
async def rebuild():
    if _task_status["running"]: return {"message": "Already running", **_task_status}
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _rebuild_sync)
    return {"message": "Thread rebuild started. Check /api/threads/status for progress."}

@router.get("/status")
async def thread_status():
    return _task_status

@router.get("")
async def list_threads(min_messages: int = Query(2, ge=1), sort_by: str = Query("last_date"),
    sort_order: str = Query("desc"), page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    return get_threads(min_messages=min_messages, sort_by=sort_by, sort_order=sort_order, page=page, page_size=page_size)

@router.get("/{thread_id}")
async def thread_detail(thread_id: int):
    detail = get_thread_detail(thread_id)
    if not detail: raise HTTPException(404, f"Thread {thread_id} not found")
    return detail

@router.get("/{thread_id}/participants")
async def thread_participants(thread_id: int):
    return {"participants": get_thread_participants(thread_id)}

@router.post("/{thread_id}/summarize")
async def thread_summarize(thread_id: int, model: str = Query(None)):
    """Generate an AI summary of the thread. Requires Ollama."""
    result = summarize_thread(thread_id, model=model)
    if result.get("error"):
        raise HTTPException(502, result["error"])
    return result

@router.post("/email/{email_id}/summarize")
async def email_summarize(email_id: int, model: str = Query(None)):
    """Generate an AI summary of a single email. Requires Ollama."""
    result = summarize_email(email_id, model=model)
    if result.get("error"):
        raise HTTPException(502, result["error"])
    return result
