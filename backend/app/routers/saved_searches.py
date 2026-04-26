"""Saved searches (smart folders) endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.services.search import _sanitize_fts_query, BM25_WEIGHTS

router = APIRouter(prefix="/api/saved-searches", tags=["saved_searches"])


def _count_matches_for_search(conn, s: dict) -> Optional[int]:
    """
    Count how many emails match a saved-search row right now.

    Mirrors the query/filter logic of GET /api/emails/advanced-search
    so the sidebar's "12 emails" badge always agrees with what the user
    sees when they click through. Returns None if the count fails
    (e.g. malformed FTS query).
    """
    conditions: list[str] = []
    params: list = []
    use_fts = bool(s.get("query") and str(s["query"]).strip())

    if use_fts:
        params.append(_sanitize_fts_query(s["query"]))
        fts_join = "JOIN emails_fts ON emails_fts.rowid = e.id AND emails_fts MATCH ?"
    else:
        fts_join = ""

    if s.get("sender"):
        conditions.append("(e.sender_email LIKE ? OR e.sender_name LIKE ?)")
        params.extend([f"%{s['sender']}%", f"%{s['sender']}%"])
    if s.get("date_from"):
        conditions.append("e.date_sent >= ?")
        params.append(s["date_from"])
    if s.get("date_to"):
        date_to = s["date_to"]
        conditions.append("e.date_sent <= ?")
        params.append(date_to + "T23:59:59" if len(date_to) == 10 else date_to)
    if s.get("mbox_source"):
        conditions.append("e.mbox_source = ?")
        params.append(s["mbox_source"])
    if s.get("has_attachments"):
        conditions.append("e.has_attachments = 1")

    where = " AND ".join(conditions) if conditions else "1=1"
    try:
        return conn.execute(
            f"SELECT COUNT(*) FROM emails e {fts_join} WHERE {where}", params,
        ).fetchone()[0]
    except Exception:
        return None


class SavedSearchCreate(BaseModel):
    name: str
    query: Optional[str] = None
    sender: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    has_attachments: bool = False
    mbox_source: Optional[str] = None
    color: str = "#3b82f6"


class SavedSearchUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None


@router.get("")
async def list_saved_searches(with_counts: bool = True):
    """
    List all saved searches. Returns a `count` field for each (number of
    emails currently matching the search) when with_counts=true, so the
    sidebar can show live badges. Disable with `?with_counts=false` if
    callers want the cheaper read.
    """
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, name, query, sender, date_from, date_to,
                   has_attachments, mbox_source, color,
                   run_count, last_run_at, created_at
            FROM saved_searches
            ORDER BY run_count DESC, created_at DESC
        """).fetchall()
        items = [dict(r) for r in rows]
        if with_counts:
            for s in items:
                s["count"] = _count_matches_for_search(conn, s)
    return {"searches": items}


@router.post("")
async def create_saved_search(body: SavedSearchCreate):
    if not body.name.strip():
        raise HTTPException(400, "Name is required")
    with get_db() as conn:
        cur = conn.execute("""
            INSERT INTO saved_searches
                (name, query, sender, date_from, date_to,
                 has_attachments, mbox_source, color)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (body.name.strip(), body.query or None, body.sender or None,
              body.date_from or None, body.date_to or None,
              1 if body.has_attachments else 0,
              body.mbox_source or None, body.color))
        new_id = cur.lastrowid
        row = conn.execute(
            "SELECT * FROM saved_searches WHERE id = ?", (new_id,)
        ).fetchone()
    return dict(row)


@router.post("/{search_id}/run")
async def record_run(search_id: int):
    """Increment run_count and update last_run_at when a saved search is executed."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM saved_searches WHERE id = ?", (search_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Saved search not found")
        conn.execute("""
            UPDATE saved_searches
            SET run_count = run_count + 1, last_run_at = datetime('now')
            WHERE id = ?
        """, (search_id,))
    return {"ok": True}


@router.patch("/{search_id}")
async def update_saved_search(search_id: int, body: SavedSearchUpdate):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM saved_searches WHERE id = ?", (search_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Saved search not found")
        if body.name is not None:
            conn.execute(
                "UPDATE saved_searches SET name = ? WHERE id = ?",
                (body.name.strip(), search_id)
            )
        if body.color is not None:
            conn.execute(
                "UPDATE saved_searches SET color = ? WHERE id = ?",
                (body.color, search_id)
            )
        row = conn.execute(
            "SELECT * FROM saved_searches WHERE id = ?", (search_id,)
        ).fetchone()
    return dict(row)


@router.delete("/{search_id}")
async def delete_saved_search(search_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM saved_searches WHERE id = ?", (search_id,))
    return {"deleted": search_id}
