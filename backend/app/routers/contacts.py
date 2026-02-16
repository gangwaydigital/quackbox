"""Contact profile + merge endpoints."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List
from app.services.contacts import get_contact_profile, list_contacts
from app.services.contact_merge import find_merge_candidates, merge_contacts
from app.services.sentiment import analyze_archive_sentiment, score_text

router = APIRouter(prefix="/api/contacts", tags=["contacts"])

@router.get("")
async def contacts_list(sort_by: str = Query("total"), sort_order: str = Query("desc"),
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), search: str = Query(None)):
    return list_contacts(sort_by=sort_by, sort_order=sort_order, page=page, page_size=page_size, search=search)

@router.get("/merge-candidates")
async def merge_candidates():
    """Find contacts that may be the same person."""
    return {"candidates": find_merge_candidates()}

class MergeRequest(BaseModel):
    primary_email: str
    secondary_emails: List[str]

@router.post("/merge")
async def merge(req: MergeRequest):
    """Merge duplicate contacts. WARNING: This modifies the database."""
    result = merge_contacts(req.primary_email, req.secondary_emails)
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return result

@router.get("/sentiment")
async def sentiment_analysis():
    """Analyze sentiment across the entire archive."""
    return analyze_archive_sentiment()

@router.get("/{email_addr:path}")
async def contact_profile(email_addr: str):
    profile = get_contact_profile(email_addr)
    if not profile:
        raise HTTPException(404, f"Contact {email_addr} not found")
    return profile
