"""
Mbox ingestion endpoints.
Handles importing email files into the database.
Supports incremental ingestion (default) and forced full re-scan.
"""
import asyncio
import time
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException, Query
from app.config import DATA_DIR
from app.models import IngestRequest, IngestResponse
from app.services.indexer import ingest_mbox, ingest_all, get_source_status
from app.services.emlx_parser import find_emlx_files
from app.logging_config import get_logger

log = get_logger("ingest")
router = APIRouter(prefix="/api/ingest", tags=["ingest"])
_executor = ThreadPoolExecutor(max_workers=1)

router = APIRouter(prefix="/api/ingest", tags=["ingest"])
_executor = ThreadPoolExecutor(max_workers=1)
_ingest_status = {
    "running": False, "phase": "", "progress": "",
    "current_source": "", "files_done": 0, "files_total": 0,
    "emails_imported": 0, "emails_skipped": 0,
    "started_at": None, "finished_at": None,
    "elapsed_seconds": 0, "results": None, "error": None,
    "sources_progress": [], "incremental": True,
}


@router.get("/scan")
async def scan_data_dir():
    """Scan the /data directory for importable email files."""
    found = {
        "emlx_mailboxes": [], "mbox_files": [], "total_files": 0,
        "data_dir": str(DATA_DIR), "exists": DATA_DIR.exists()
    }
    if not DATA_DIR.exists():
        return found
    mailboxes = find_emlx_files(DATA_DIR)
    if mailboxes:
        for name, files in sorted(mailboxes.items()):
            found["emlx_mailboxes"].append({"name": name, "message_count": len(files)})
            found["total_files"] += len(files)
    mbox_files = set()
    for f in DATA_DIR.rglob("mbox"):
        if f.is_file() and f.stat().st_size > 0:
            mbox_files.add(str(f))
    for f in DATA_DIR.glob("*.mbox"):
        if f.is_file() and f.stat().st_size > 0:
            mbox_files.add(str(f))
    for fp in sorted(mbox_files):
        p = Path(fp)
        size_mb = round(p.stat().st_size / 1_048_576, 1)
        name = p.parent.name if p.name == "mbox" else p.name
        found["mbox_files"].append({"name": name, "path": str(p.relative_to(DATA_DIR)), "size_mb": size_mb})
        found["total_files"] += 1
    return found


@router.get("/check")
async def check_for_new():
    """
    Fast check: compare on-disk sources against the ingest tracking tables.
    Returns per-source status (new / unchanged / updated / missing) and
    estimated new email counts without doing any actual parsing.
    """
    sources = get_source_status(DATA_DIR)
    has_updates = any(s["status"] in ("new", "updated") for s in sources)
    total_new = sum(
        s["new_count"] for s in sources
        if s["new_count"] is not None and s["status"] in ("new", "updated")
    )
    return {
        "sources": sources,
        "has_updates": has_updates,
        "total_new_estimated": total_new,
    }


def _run_ingest(incremental: bool = True):
    """Background ingest worker."""
    global _ingest_status
    start_time = time.time()
    try:
        _ingest_status.update({
            "running": True, "phase": "scanning",
            "progress": "Scanning data directory...",
            "started_at": start_time, "error": None, "results": None,
            "files_done": 0, "emails_imported": 0, "emails_skipped": 0,
            "current_source": "", "sources_progress": [], "elapsed_seconds": 0,
            "incremental": incremental,
        })

        mailboxes = find_emlx_files(DATA_DIR)
        mbox_files = set()
        for f in DATA_DIR.rglob("mbox"):
            if f.is_file() and f.stat().st_size > 0:
                mbox_files.add(str(f))
        for f in DATA_DIR.glob("*.mbox"):
            if f.is_file() and f.stat().st_size > 0:
                mbox_files.add(str(f))

        total_sources = len(mailboxes or {}) + len(mbox_files)
        _ingest_status["files_total"] = total_sources
        _ingest_status["phase"] = "importing"

        results = []

        if mailboxes:
            from app.services.indexer import ingest_emlx_mailbox
            for mailbox_name in sorted(mailboxes.keys()):
                _ingest_status["current_source"] = mailbox_name
                _ingest_status["progress"] = f"Importing {mailbox_name}..."
                _ingest_status["elapsed_seconds"] = round(time.time() - start_time)

                result = ingest_emlx_mailbox(mailbox_name, mailboxes[mailbox_name],
                                             incremental=incremental)
                results.append(result)
                _ingest_status["files_done"] += 1
                _ingest_status["emails_imported"] += result.get("imported", 0)
                _ingest_status["emails_skipped"] += result.get("skipped", 0)
                _ingest_status["sources_progress"].append({
                    "name": mailbox_name,
                    "imported": result.get("imported", 0),
                    "skipped": result.get("skipped", 0),
                    "mode": result.get("mode", ""),
                })

        if mbox_files:
            for mbox_path_str in sorted(mbox_files):
                mbox_path = Path(mbox_path_str)
                name = mbox_path.parent.name if mbox_path.name == "mbox" else mbox_path.name
                _ingest_status["current_source"] = name
                _ingest_status["progress"] = f"Importing {name}..."
                _ingest_status["elapsed_seconds"] = round(time.time() - start_time)

                result = ingest_mbox(mbox_path, incremental=incremental)
                results.append(result)
                _ingest_status["files_done"] += 1
                _ingest_status["emails_imported"] += result.get("imported", 0)
                _ingest_status["emails_skipped"] += result.get("skipped", 0)
                _ingest_status["sources_progress"].append({
                    "name": name,
                    "imported": result.get("imported", 0),
                    "skipped": result.get("skipped", 0),
                    "mode": result.get("mode", ""),
                })

        total_imported = _ingest_status["emails_imported"]
        elapsed = round(time.time() - start_time)
        mode_label = "incremental" if incremental else "full"
        _ingest_status.update({
            "running": False, "phase": "done",
            "progress": f"Complete! {total_imported:,} new emails ({mode_label}) in {elapsed}s.",
            "finished_at": time.time(), "results": results,
            "elapsed_seconds": elapsed, "current_source": "",
        })

        if total_imported > 0:
            try:
                from app.services.analytics import warm_cache
                warm_cache()
            except Exception as e:
                log.warning("Cache warming failed (non-fatal): %s", e)
            try:
                from app.services.attachment_indexer import index_all_attachments
                index_all_attachments()
            except Exception as e:
                log.warning("Attachment indexing failed (non-fatal): %s", e)

    except Exception as e:
        _ingest_status.update({
            "running": False, "phase": "error",
            "progress": f"Error: {str(e)}",
            "error": str(e), "finished_at": time.time(),
            "elapsed_seconds": round(time.time() - start_time),
        })


@router.post("/start")
async def start_ingest(force: bool = Query(False, description="Force full re-scan, ignoring incremental tracking")):
    """
    Start async ingestion of all data in /data directory.
    
    force=false (default): incremental mode — skip unchanged sources,
    seek to last offset in grown mbox files, only process new .emlx files.
    
    force=true: full re-scan of everything. Use after manual data changes
    or if incremental tracking gets out of sync.
    """
    if _ingest_status["running"]:
        return {"message": "Ingestion already running", **_ingest_status}
    incremental = not force
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _run_ingest, incremental)
    return {"message": f"Ingestion started (mode={'incremental' if incremental else 'full'})."}


@router.get("/progress")
async def ingest_progress():
    """Get current ingestion progress."""
    return _ingest_status


@router.post("", response_model=IngestResponse)
async def ingest_mbox_file(request: IngestRequest):
    mbox_path = DATA_DIR / request.mbox_path
    if not mbox_path.exists():
        raise HTTPException(404, f"File not found: {request.mbox_path}")
    if not mbox_path.is_file():
        raise HTTPException(400, f"Not a file: {request.mbox_path}")
    result = ingest_mbox(mbox_path)
    return IngestResponse(**result)


@router.post("/all")
async def ingest_all_mbox_files():
    results = ingest_all(DATA_DIR)
    if not results:
        raise HTTPException(404, f"No email data found in {DATA_DIR}.")
    return {"results": results}


@router.get("/sources")
async def list_mbox_sources():
    mbox_files = list(DATA_DIR.glob("*.mbox"))
    return {"available": [f.name for f in sorted(mbox_files)], "data_dir": str(DATA_DIR)}
