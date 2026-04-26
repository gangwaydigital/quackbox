"""
Background watcher — periodically checks DATA_DIR for new email content
and triggers an incremental ingest when something is found.

The watcher runs as a single asyncio task started by the FastAPI lifespan
context. It does not block the request loop: each tick wakes briefly,
calls the cheap `get_source_status()` to see if any source is "new" or
"updated", and only then dispatches `run_ingest()` on a thread executor.

Disabled by default. Enable via WATCH_INTERVAL_MINUTES > 0.
"""
from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from app.config import DATA_DIR, WATCH_INTERVAL_MINUTES, WATCH_ON_STARTUP
from app.logging_config import get_logger
from app.services.indexer import get_source_status
from app.services.ingest_runner import is_ingest_running, run_ingest
from app.services.folders import all_data_paths

log = get_logger("watcher")

_task: Optional[asyncio.Task] = None
_stop_event: Optional[asyncio.Event] = None
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="watcher-ingest")

_state = {
    "enabled": False,
    "interval_seconds": 0,
    "started_at": None,
    "last_check_at": None,
    "last_run_at": None,
    "checks": 0,
    "runs": 0,
    "last_status_summary": None,  # one-line summary of last check
}


def status() -> dict:
    """Snapshot of the watcher state for the /api/ingest/watcher endpoint."""
    return dict(_state)


def _has_pending_work() -> bool:
    """Return True if any source on disk is new or updated since last ingest.
    Checks every registered folder + the legacy DATA_DIR."""
    try:
        for path in all_data_paths():
            sources = get_source_status(path)
            if any(s.get("status") in ("new", "updated") for s in sources):
                return True
    except Exception as e:
        log.warning("Watcher: get_source_status failed: %s", e)
        return False
    return False


async def _watch_loop(interval_seconds: int) -> None:
    """The main ticker. Cancellable via _stop_event."""
    log.info("🔭 Watcher loop running every %ds", interval_seconds)
    assert _stop_event is not None
    loop = asyncio.get_running_loop()
    while not _stop_event.is_set():
        try:
            _state["checks"] += 1
            _state["last_check_at"] = time.time()

            if is_ingest_running():
                _state["last_status_summary"] = "Skipped: ingest already running"
            elif _has_pending_work():
                log.info("🔭 Watcher: pending work detected, dispatching incremental ingest")
                _state["last_status_summary"] = "Triggered incremental ingest"
                _state["last_run_at"] = time.time()
                _state["runs"] += 1
                # Run in a worker thread so we don't block the asyncio loop
                await loop.run_in_executor(_executor, run_ingest, True, "watcher")
            else:
                _state["last_status_summary"] = "No new content"
        except Exception as e:
            log.exception("Watcher tick failed")
            _state["last_status_summary"] = f"Error: {e}"

        # Wait for the next tick or for a shutdown request, whichever comes first
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass

    log.info("🔭 Watcher loop stopped")


def start(interval_minutes: int = WATCH_INTERVAL_MINUTES,
          run_on_startup: bool = WATCH_ON_STARTUP) -> None:
    """Start the watcher task. No-op if interval_minutes <= 0 or already running."""
    global _task, _stop_event
    if interval_minutes <= 0:
        log.info("🔭 Watcher disabled (WATCH_INTERVAL_MINUTES=%s)", interval_minutes)
        _state["enabled"] = False
        return
    if _task is not None and not _task.done():
        log.warning("Watcher already running")
        return

    interval_seconds = max(60, int(interval_minutes * 60))
    _stop_event = asyncio.Event()
    _state.update({
        "enabled": True,
        "interval_seconds": interval_seconds,
        "started_at": time.time(),
        "last_check_at": None,
        "last_run_at": None,
        "checks": 0,
        "runs": 0,
        "last_status_summary": "Awaiting first tick",
    })
    _task = asyncio.create_task(_watch_loop(interval_seconds), name="watcher")

    if run_on_startup:
        # Fire-and-forget an immediate run so we don't have to wait for the first tick
        loop = asyncio.get_running_loop()
        loop.create_task(_run_once_now())


async def _run_once_now() -> None:
    """Trigger an immediate ingest if there's pending work."""
    try:
        if is_ingest_running():
            return
        if _has_pending_work():
            log.info("🔭 Watcher: startup scan found pending work")
            _state["last_run_at"] = time.time()
            _state["runs"] += 1
            _state["last_status_summary"] = "Startup scan triggered ingest"
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(_executor, run_ingest, True, "watcher-startup")
        else:
            _state["last_status_summary"] = "Startup scan: nothing new"
    except Exception:
        log.exception("Watcher startup scan failed")


def trigger_scan_now() -> dict:
    """
    Run an immediate scan + ingest pass synchronously on a worker thread.
    Returns a status dict describing what happened (queued / nothing-to-do /
    already-running / disabled).

    Called by the manual /api/ingest/watcher/scan endpoint so users can force
    a scan without waiting for the next tick.
    """
    if is_ingest_running():
        return {"queued": False, "reason": "ingest_already_running"}
    if not _has_pending_work():
        _state["last_check_at"] = time.time()
        _state["checks"] += 1
        _state["last_status_summary"] = "Manual scan: nothing new"
        return {"queued": False, "reason": "no_new_content"}
    log.info("🔭 Watcher: manual scan triggered, dispatching incremental ingest")
    _state["last_run_at"] = time.time()
    _state["runs"] += 1
    _state["last_status_summary"] = "Manual scan triggered ingest"
    # Fire and forget — the executor runs the ingest, the user polls
    # /api/ingest/progress for results.
    _executor.submit(run_ingest, True, "watcher-manual")
    return {"queued": True, "reason": "ingest_started"}


async def stop() -> None:
    """Cancel the watcher task. Safe to call even if never started."""
    global _task, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    if _task is not None:
        try:
            await asyncio.wait_for(_task, timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            _task.cancel()
        finally:
            _task = None
            _stop_event = None
    _state["enabled"] = False
