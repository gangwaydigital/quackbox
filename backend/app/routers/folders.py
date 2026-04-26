"""User-registered ingest folders + host filesystem browser."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from app.services import folders as folders_svc
from app.services.attachment_extractor import _invalidate_mbox_cache

router = APIRouter(prefix="/api/folders", tags=["folders"])


class AddFolderRequest(BaseModel):
    host_path: str
    label: Optional[str] = None


@router.get("/browse")
async def browse(path: Optional[str] = Query(None, description="Host path to list. Omit for the top-level roots.")):
    """Directory browser for the in-app folder picker. Refuses any path
    outside the configured /host mount roots."""
    result = folders_svc.browse(path)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("")
async def list_folders():
    """List every folder the user has registered for ingestion."""
    return {"folders": folders_svc.list_folders(), "roots": folders_svc.HOST_ROOTS}


@router.post("")
async def add_folder(req: AddFolderRequest):
    """Register a host path so it gets included in every future ingest."""
    result = folders_svc.add_folder(req.host_path, req.label)
    if result.get("error"):
        raise HTTPException(result.get("status", 400), result["error"])
    _invalidate_mbox_cache()
    return result


@router.delete("/{folder_id}")
async def remove_folder(folder_id: int):
    """Stop scanning a registered folder. Already-imported emails stay."""
    result = folders_svc.delete_folder(folder_id)
    if result.get("error"):
        raise HTTPException(result.get("status", 400), result["error"])
    _invalidate_mbox_cache()
    return result
