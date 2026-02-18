"""Duplicate detection and deduplication endpoints."""
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.services.deduplication import (
    scan_duplicates, get_duplicate_groups, delete_duplicates, dismiss_group
)

router = APIRouter(prefix="/api/duplicates", tags=["duplicates"])


@router.post("/scan")
async def scan():
    """Scan the archive for duplicate emails. Returns summary."""
    result = scan_duplicates()
    return result


@router.get("")
async def list_groups(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List detected duplicate groups with canonical + duplicate emails."""
    return get_duplicate_groups(page=page, page_size=page_size)


class DeleteRequest(BaseModel):
    group_ids: Optional[List[int]] = None
    delete_all: bool = False


@router.post("/delete")
async def delete(req: DeleteRequest):
    """Delete duplicate emails, keeping the canonical version in each group."""
    if not req.delete_all and not req.group_ids:
        raise HTTPException(400, "Provide group_ids or set delete_all=true")
    return delete_duplicates(group_ids=req.group_ids, delete_all=req.delete_all)


@router.delete("/{group_id}")
async def dismiss(group_id: int):
    """Dismiss a duplicate group (mark as not duplicates, keep all emails)."""
    return dismiss_group(group_id)
