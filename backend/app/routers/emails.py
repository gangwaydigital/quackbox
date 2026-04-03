"""Email endpoints — search, filter, similar, semantic."""
from typing import Optional
import logging
from fastapi import APIRouter, HTTPException, Query
from app.models import PaginatedResponse, SearchResponse, SearchRequest
from app.services.search import full_text_search, filter_emails, get_email_detail, get_senders, get_mbox_sources, instant_search
from app.services.semantic_search import semantic_search, find_similar, hybrid_search, has_embeddings
from app.utils.text_cleanup import clean_body_text
from app.logging_config import get_logger

log = get_logger("emails")
router = APIRouter(prefix="/api/emails", tags=["emails"])

@router.get("", response_model=PaginatedResponse)
async def list_emails(
    sender_email: Optional[str] = Query(None), sender_name: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None), date_to: Optional[str] = Query(None),
    subject_contains: Optional[str] = Query(None), mbox_source: Optional[str] = Query(None),
    topic_id: Optional[int] = Query(None), has_attachments: Optional[bool] = Query(None),
    sort_by: str = Query("date_timestamp"), sort_order: str = Query("desc"),
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
):
    return filter_emails(sender_email=sender_email, sender_name=sender_name,
        date_from=date_from, date_to=date_to, subject_contains=subject_contains,
        mbox_source=mbox_source, topic_id=topic_id, has_attachments=has_attachments,
        sort_by=sort_by, sort_order=sort_order, page=page, page_size=page_size)

@router.get("/instant")
async def instant_search_endpoint(q: str = Query(..., min_length=1), limit: int = Query(8, ge=1, le=20)):
    """Lightweight instant search for typeahead — no COUNT, small payload."""
    return {"results": instant_search(q, limit=limit)}

@router.post("/search", response_model=SearchResponse)
async def search_emails(request: SearchRequest):
    return full_text_search(query=request.query, page=request.page, page_size=request.page_size)

@router.get("/search")
async def search_emails_get(q: str = Query(..., min_length=1), page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    return full_text_search(query=q, page=page, page_size=page_size)

@router.get("/semantic-search")
async def semantic_search_endpoint(q: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=100)):
    if not has_embeddings():
        return {"results": [], "message": "No embeddings found. Run topic clustering first."}
    return {"results": semantic_search(q, limit=limit), "total": limit, "query": q}

@router.get("/hybrid-search")
async def hybrid_search_endpoint(q: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=100)):
    results = hybrid_search(q, limit=limit)
    return {"results": results, "total": len(results), "query": q}

@router.get("/senders")
async def list_senders(limit: int = Query(100, ge=1, le=1000)):
    return {"senders": get_senders(limit=limit)}

@router.get("/sources")
async def list_sources():
    return {"sources": get_mbox_sources()}


@router.get("/advanced-search")
async def advanced_search(
    q: str = Query(None), sender: str = Query(None),
    date_from: str = Query(None), date_to: str = Query(None),
    mbox_source: str = Query(None), has_attachments: bool = Query(None),
    tag_id: int = Query(None), bookmarked: bool = Query(None),
    sort_by: str = Query("date_timestamp"), sort_order: str = Query("desc"),
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
):
    """
    Advanced search: FTS5 for keywords + SQL filters for structured criteria.
    Much faster than the old LIKE-based approach on large archives.
    """
    from app.database import get_db
    from app.services.search import _sanitize_fts_query, BM25_WEIGHTS

    with get_db() as conn:
        conditions = []
        params = []
        use_fts = bool(q and q.strip())

        # FTS5 keyword search — replaces the old LIKE chain
        if use_fts:
            safe_query = _sanitize_fts_query(q)
            fts_join = f"""
                JOIN emails_fts ON emails_fts.rowid = e.id
                    AND emails_fts MATCH ?
            """
            params.append(safe_query)
        else:
            fts_join = ""

        # Structured filters
        if sender:
            conditions.append("(e.sender_email LIKE ? OR e.sender_name LIKE ?)")
            params.extend([f"%{sender}%", f"%{sender}%"])
        if date_from:
            conditions.append("e.date_sent >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("e.date_sent <= ?")
            params.append(date_to + "T23:59:59" if len(date_to) == 10 else date_to)
        if mbox_source:
            conditions.append("e.mbox_source = ?")
            params.append(mbox_source)
        if has_attachments is not None:
            conditions.append("e.has_attachments = ?")
            params.append(1 if has_attachments else 0)
        if bookmarked:
            conditions.append("e.id IN (SELECT email_id FROM bookmarks)")
        if tag_id:
            conditions.append("e.id IN (SELECT email_id FROM email_tags WHERE tag_id = ?)")
            params.append(tag_id)

        where = " AND ".join(conditions) if conditions else "1=1"
        valid_sorts = {"date_timestamp", "subject", "sender_name"}
        sb = sort_by if sort_by in valid_sorts else "date_timestamp"
        so = "ASC" if sort_order.lower() == "asc" else "DESC"

        # Use BM25 rank for ordering when doing FTS, otherwise user-specified sort
        order = f"bm25(emails_fts, {BM25_WEIGHTS})" if use_fts and sb == "date_timestamp" else f"e.{sb} {so}"
        if use_fts and sb != "date_timestamp":
            order = f"e.{sb} {so}"

        try:
            total = conn.execute(
                f"SELECT COUNT(*) FROM emails e {fts_join} WHERE {where}", params
            ).fetchone()[0]

            # Build SELECT with optional FTS5 highlights
            if use_fts:
                select_cols = """e.id, e.subject, e.sender_name, e.sender_email, e.date_sent,
                    e.mbox_source, e.has_attachments, e.thread_group_id,
                    snippet(emails_fts, 0, '<mark>', '</mark>', '…', 12) as highlight_subject,
                    snippet(emails_fts, 3, '<mark>', '</mark>', '…', 20) as highlight_body"""
            else:
                select_cols = """e.id, e.subject, e.sender_name, e.sender_email, e.date_sent,
                    e.mbox_source, e.has_attachments, e.thread_group_id"""

            rows = conn.execute(f"""
                SELECT {select_cols}
                FROM emails e {fts_join}
                WHERE {where}
                ORDER BY {order}
                LIMIT ? OFFSET ?
            """, params + [page_size, (page - 1) * page_size]).fetchall()
        except Exception as exc:
            log.warning("Advanced search error: %s", exc)
            return {"items": [], "total": 0, "page": page, "total_pages": 1}

        items = []
        for r in rows:
            item = dict(r)
            item["has_attachments"] = bool(item.get("has_attachments"))
            items.append(item)

        return {
            "items": items,
            "total": total, "page": page,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }

@router.get("/{email_id}")
async def get_email(email_id: int, clean: bool = Query(False)):
    """Get full email. Set clean=true to strip reply quotes."""
    email = get_email_detail(email_id)
    if not email: raise HTTPException(404, f"Email {email_id} not found")
    if clean and email.get("body_text"):
        email["body_text"] = clean_body_text(email["body_text"])
    return email

@router.get("/{email_id}/similar")
async def similar_emails(email_id: int, limit: int = Query(10, ge=1, le=50)):
    if not has_embeddings():
        return {"results": [], "message": "No embeddings found."}
    return {"results": find_similar(email_id, limit=limit), "email_id": email_id}
