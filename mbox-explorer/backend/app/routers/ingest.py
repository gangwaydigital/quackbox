"""
Mbox ingestion endpoints.

Handles importing .mbox files into the database.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import DATA_DIR
from app.models import IngestRequest, IngestResponse
from app.services.indexer import ingest_mbox, ingest_all

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse)
async def ingest_mbox_file(request: IngestRequest):
    """
    Ingest a single .mbox file.

    The mbox_path should be relative to the data/ directory.
    """
    mbox_path = DATA_DIR / request.mbox_path

    if not mbox_path.exists():
        raise HTTPException(404, f"File not found: {request.mbox_path}")
    if not mbox_path.is_file():
        raise HTTPException(400, f"Not a file: {request.mbox_path}")

    result = ingest_mbox(mbox_path)
    return IngestResponse(**result)


@router.post("/all")
async def ingest_all_mbox_files():
    """Ingest all .mbox files found in the data/ directory."""
    results = ingest_all(DATA_DIR)
    if not results:
        raise HTTPException(404, f"No email data found in {DATA_DIR}. Looking for .emlx files and mbox files.")
    return {"results": results}


@router.get("/sources")
async def list_mbox_sources():
    """List available .mbox files in the data directory."""
    mbox_files = list(DATA_DIR.glob("*.mbox"))
    return {
        "available": [f.name for f in sorted(mbox_files)],
        "data_dir": str(DATA_DIR),
    }
