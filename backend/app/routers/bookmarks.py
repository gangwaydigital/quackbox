"""Bookmarks and tags endpoints."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from app.database import get_db

router = APIRouter(prefix="/api/bookmarks", tags=["bookmarks"])

# --- Bookmarks ---

class BookmarkRequest(BaseModel):
    email_id: int
    note: Optional[str] = None

@router.get("")
async def list_bookmarks(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1)):
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0]
        rows = conn.execute("""
            SELECT b.email_id, b.note, b.created_at,
                   e.subject, e.sender_name, e.sender_email, e.date_sent, e.mbox_source
            FROM bookmarks b JOIN emails e ON b.email_id = e.id
            ORDER BY b.created_at DESC
            LIMIT ? OFFSET ?
        """, (page_size, (page - 1) * page_size)).fetchall()
        return {"items": [dict(r) for r in rows], "total": total, "page": page}

@router.post("")
async def add_bookmark(req: BookmarkRequest):
    with get_db() as conn:
        try:
            conn.execute("INSERT INTO bookmarks (email_id, note) VALUES (?, ?)", (req.email_id, req.note))
            return {"status": "bookmarked", "email_id": req.email_id}
        except Exception:
            return {"status": "already_bookmarked", "email_id": req.email_id}

@router.delete("/{email_id}")
async def remove_bookmark(email_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM bookmarks WHERE email_id = ?", (email_id,))
        return {"status": "removed", "email_id": email_id}

@router.get("/check/{email_id}")
async def check_bookmark(email_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT 1 FROM bookmarks WHERE email_id = ?", (email_id,)).fetchone()
        return {"bookmarked": row is not None}

# --- Tags ---

class TagCreate(BaseModel):
    name: str
    color: str = '#3b82f6'

class TagEmails(BaseModel):
    email_ids: List[int]

@router.get("/tags")
async def list_tags():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT t.*, COUNT(et.email_id) as email_count
            FROM tags t LEFT JOIN email_tags et ON t.id = et.tag_id
            GROUP BY t.id ORDER BY t.name ASC
        """).fetchall()
        return {"tags": [dict(r) for r in rows]}

@router.post("/tags")
async def create_tag(req: TagCreate):
    with get_db() as conn:
        try:
            cur = conn.execute("INSERT INTO tags (name, color) VALUES (?, ?)", (req.name.strip(), req.color))
            return {"id": cur.lastrowid, "name": req.name.strip(), "color": req.color}
        except Exception:
            raise HTTPException(409, f"Tag '{req.name}' already exists")

@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM email_tags WHERE tag_id = ?", (tag_id,))
        conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        return {"status": "deleted"}

@router.post("/tags/{tag_id}/emails")
async def tag_emails(tag_id: int, req: TagEmails):
    with get_db() as conn:
        added = 0
        for eid in req.email_ids:
            try:
                conn.execute("INSERT INTO email_tags (email_id, tag_id) VALUES (?, ?)", (eid, tag_id))
                added += 1
            except Exception:
                pass
        return {"added": added, "tag_id": tag_id}

@router.delete("/tags/{tag_id}/emails")
async def untag_emails(tag_id: int, req: TagEmails):
    with get_db() as conn:
        for eid in req.email_ids:
            conn.execute("DELETE FROM email_tags WHERE email_id = ? AND tag_id = ?", (eid, tag_id))
        return {"removed": len(req.email_ids), "tag_id": tag_id}

@router.get("/tags/{tag_id}/emails")
async def get_tag_emails(tag_id: int, page: int = Query(1), page_size: int = Query(50)):
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM email_tags WHERE tag_id = ?", (tag_id,)).fetchone()[0]
        rows = conn.execute("""
            SELECT e.id, e.subject, e.sender_name, e.sender_email, e.date_sent, e.mbox_source
            FROM email_tags et JOIN emails e ON et.email_id = e.id
            WHERE et.tag_id = ? ORDER BY e.date_timestamp DESC
            LIMIT ? OFFSET ?
        """, (tag_id, page_size, (page - 1) * page_size)).fetchall()
        return {"items": [dict(r) for r in rows], "total": total, "page": page}

@router.get("/email/{email_id}/tags")
async def get_email_tags(email_id: int):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT t.* FROM tags t JOIN email_tags et ON t.id = et.tag_id
            WHERE et.email_id = ? ORDER BY t.name
        """, (email_id,)).fetchall()
        return {"tags": [dict(r) for r in rows]}
