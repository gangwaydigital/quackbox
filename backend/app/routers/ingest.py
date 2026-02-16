"""
Mbox ingestion endpoints.
Handles importing email files into the database.
Includes scanning for available data and async ingestion with progress.
"""
import os
import asyncio
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException
from app.config import DATA_DIR
from app.models import IngestRequest, IngestResponse
from app.services.indexer import ingest_mbox, ingest_all
from app.services.emlx_parser import find_emlx_files

router = APIRouter(prefix="/api/ingest", tags=["ingest"])
_executor = ThreadPoolExecutor(max_workers=1)
_ingest_status = {
    "running": False, "phase": "", "progress": "",
    "current_source": "", "files_done": 0, "files_total": 0,
    "emails_imported": 0, "emails_skipped": 0,
    "started_at": None, "finished_at": None,
    "elapsed_seconds": 0, "results": None, "error": None,
    "sources_progress": [],
}


@router.get("/scan")
async def scan_data_dir():
    """Scan the /data directory for importable email files."""
    found = {"emlx_mailboxes": [], "mbox_files": [], "total_files": 0, "data_dir": str(DATA_DIR), "exists": DATA_DIR.exists()}
    if not DATA_DIR.exists():
        return found

    mailboxes = find_emlx_files(DATA_DIR)
    if mailboxes:
        for name, files in sorted(mailboxes.items()):
            found["emlx_mailboxes"].append({"name": name, "message_count": len(files)})
            found["total_files"] += len(files)

    mbox_files = set()
    for mbox_file in DATA_DIR.rglob("mbox"):
        if mbox_file.is_file() and mbox_file.stat().st_size > 0:
            mbox_files.add(str(mbox_file))
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


def _run_ingest():
    """Background ingest worker with detailed progress updates."""
    global _ingest_status
    start_time = time.time()
    try:
        _ingest_status.update({
            "running": True, "phase": "scanning",
            "progress": "Scanning data directory...",
            "started_at": start_time, "error": None, "results": None,
            "files_done": 0, "emails_imported": 0, "emails_skipped": 0,
            "current_source": "", "sources_progress": [], "elapsed_seconds": 0,
        })

        # Count sources first
        from app.services.emlx_parser import find_emlx_files
        mailboxes = find_emlx_files(DATA_DIR)
        mbox_files = set()
        for mbox_file in DATA_DIR.rglob("mbox"):
            if mbox_file.is_file() and mbox_file.stat().st_size > 0:
                mbox_files.add(str(mbox_file))
        for f in DATA_DIR.glob("*.mbox"):
            if f.is_file() and f.stat().st_size > 0:
                mbox_files.add(str(f))

        total_sources = len(mailboxes or {}) + len(mbox_files)
        _ingest_status["files_total"] = total_sources
        _ingest_status["phase"] = "importing"

        results = []

        # Ingest emlx mailboxes one at a time with progress
        if mailboxes:
            from app.services.indexer import ingest_emlx_mailbox
            for mailbox_name in sorted(mailboxes.keys()):
                _ingest_status["current_source"] = mailbox_name
                _ingest_status["progress"] = f"Importing {mailbox_name}..."
                _ingest_status["elapsed_seconds"] = round(time.time() - start_time)

                emlx_files = mailboxes[mailbox_name]
                result = ingest_emlx_mailbox(mailbox_name, emlx_files)
                results.append(result)

                _ingest_status["files_done"] += 1
                _ingest_status["emails_imported"] += result.get("imported", 0)
                _ingest_status["emails_skipped"] += result.get("skipped", 0)
                _ingest_status["sources_progress"].append({
                    "name": mailbox_name,
                    "imported": result.get("imported", 0),
                    "skipped": result.get("skipped", 0),
                })

        # Ingest mbox files
        if mbox_files:
            for mbox_path_str in sorted(mbox_files):
                mbox_path = Path(mbox_path_str)
                name = mbox_path.parent.name if mbox_path.name == "mbox" else mbox_path.name
                _ingest_status["current_source"] = name
                _ingest_status["progress"] = f"Importing {name}..."
                _ingest_status["elapsed_seconds"] = round(time.time() - start_time)

                result = ingest_mbox(mbox_path)
                results.append(result)

                _ingest_status["files_done"] += 1
                _ingest_status["emails_imported"] += result.get("imported", 0)
                _ingest_status["emails_skipped"] += result.get("skipped", 0)
                _ingest_status["sources_progress"].append({
                    "name": name,
                    "imported": result.get("imported", 0),
                    "skipped": result.get("skipped", 0),
                })

        total_imported = _ingest_status["emails_imported"]
        elapsed = round(time.time() - start_time)
        _ingest_status.update({
            "running": False, "phase": "done",
            "progress": f"Complete! {total_imported:,} emails from {len(results)} source(s) in {elapsed}s.",
            "finished_at": time.time(), "results": results,
            "elapsed_seconds": elapsed, "current_source": "",
        })
    except Exception as e:
        _ingest_status.update({
            "running": False, "phase": "error",
            "progress": f"Error: {str(e)}",
            "error": str(e), "finished_at": time.time(),
            "elapsed_seconds": round(time.time() - start_time),
        })


@router.post("/start")
async def start_ingest():
    """Start async ingestion of all data in /data directory."""
    if _ingest_status["running"]:
        return {"message": "Ingestion already running", **_ingest_status}
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _run_ingest)
    return {"message": "Ingestion started."}


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
