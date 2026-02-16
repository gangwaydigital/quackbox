"""
Email endpoints.

Search, filter, sort, and retrieve emails.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models import (
    SearchRequest,
    SearchResponse,
    PaginatedResponse,
    EmailDetail,
)
from app.services.search import (
    full_text_search,
    filter_emails,
    get_email_detail,
    get_senders,
    get_mbox_sources,
)

router = APIRouter(prefix="/api/emails", tags=["emails"])


@router.get("", response_model=PaginatedResponse)
async def list_emails(
    sender_email: Optional[str] = Query(None),
    sender_name: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    subject_contains: Optional[str] = Query(None),
    mbox_source: Optional[str] = Query(None),
    topic_id: Optional[int] = Query(None),
    has_attachments: Optional[bool] = Query(None),
    sort_by: str = Query("date_timestamp"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """
    List emails with optional filtering and sorting.

    Supports filtering by sender, date range, subject, mbox source,
    topic, and attachment status. Results are paginated.
    """
    return filter_emails(
        sender_email=sender_email,
        sender_name=sender_name,
        date_from=date_from,
        date_to=date_to,
        subject_contains=subject_contains,
        mbox_source=mbox_source,
        topic_id=topic_id,
        has_attachments=has_attachments,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.post("/search", response_model=SearchResponse)
async def search_emails(request: SearchRequest):
    """
    Full-text search across email subjects, senders, and bodies.

    Uses SQLite FTS5 with BM25 ranking for relevance scoring.
    """
    return full_text_search(
        query=request.query,
        page=request.page,
        page_size=request.page_size,
    )


@router.get("/search")
async def search_emails_get(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """GET version of search for easy browser testing."""
    return full_text_search(query=q, page=page, page_size=page_size)


@router.get("/senders")
async def list_senders(limit: int = Query(100, ge=1, le=1000)):
    """Get unique senders ranked by email count."""
    return {"senders": get_senders(limit=limit)}


@router.get("/sources")
async def list_sources():
    """Get list of ingested mbox files with stats."""
    return {"sources": get_mbox_sources()}


@router.get("/{email_id}")
async def get_email(email_id: int):
    """Get full details for a single email."""
    email = get_email_detail(email_id)
    if not email:
        raise HTTPException(404, f"Email {email_id} not found")
    return email
