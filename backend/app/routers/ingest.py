"""
Mbox ingestion endpoints.
Handles importing email files into the database.
Supports incremental ingestion (default) and forced full re-scan.
"""
import asyncio
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException, Query
from app.config import DATA_DIR
from app.models import IngestRequest, IngestResponse
from app.services.indexer import ingest_mbox, ingest_all, get_source_status
from app.services.emlx_parser import find_emlx_files
from app.services.ingest_runner import INGEST_STATUS, run_ingest, is_ingest_running
from app.services import watcher
from app.logging_config import get_logger

log = get_logger("ingest")
router = APIRouter(prefix="/api/ingest", tags=["ingest"])
_executor = ThreadPoolExecutor(max_workers=1)


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


@router.post("/start")
async def start_ingest(force: bool = Query(False, description="Force full re-scan, ignoring incremental tracking")):
    """
    Start async ingestion of all data in /data directory.

    force=false (default): incremental mode — skip unchanged sources,
    seek to last offset in grown mbox files, only process new .emlx files.

    force=true: full re-scan of everything. Use after manual data changes
    or if incremental tracking gets out of sync.
    """
    if is_ingest_running():
        return {"message": "Ingestion already running", **INGEST_STATUS}
    incremental = not force
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, run_ingest, incremental, "manual")
    return {"message": f"Ingestion started (mode={'incremental' if incremental else 'full'})."}


@router.get("/progress")
async def ingest_progress():
    """Get current ingestion progress."""
    return INGEST_STATUS


@router.get("/watcher")
async def watcher_status():
    """Status of the background watcher loop (if enabled)."""
    return watcher.status()


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
