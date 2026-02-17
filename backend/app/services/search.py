"""
Search and filter service.

Handles full-text search via FTS5 and structured
filtering/sorting of emails.
"""

import json
from typing import Optional

from app.database import get_db
from app.utils.email_utils import make_snippet


def full_text_search(
    query: str,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """
    Full-text search across email subjects, senders, and bodies.

    Uses SQLite FTS5 with BM25 ranking.

    Returns:
        dict with results, total count, and pagination info
    """
    offset = (page - 1) * page_size

    with get_db() as conn:
        # Escape FTS5 special characters in user query
        safe_query = _sanitize_fts_query(query)

        # Count total matches
        total = conn.execute(
            "SELECT COUNT(*) FROM emails_fts WHERE emails_fts MATCH ?",
            (safe_query,)
        ).fetchone()[0]

        # Get ranked results
        rows = conn.execute("""
            SELECT
                e.*,
                rank
            FROM emails_fts
            JOIN emails e ON e.id = emails_fts.rowid
            WHERE emails_fts MATCH ?
            ORDER BY rank
            LIMIT ? OFFSET ?
        """, (safe_query, page_size, offset)).fetchall()

        results = []
        for row in rows:
            email_data = _row_to_summary(row)
            results.append({
                "email": email_data,
                "rank": abs(row["rank"]),
                "highlights": _get_highlights(row, query),
            })

        return {
            "results": results,
            "total": total,
            "query": query,
            "page": page,
            "page_size": page_size,
        }


def filter_emails(
    sender_email: Optional[str] = None,
    sender_name: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    subject_contains: Optional[str] = None,
    mbox_source: Optional[str] = None,
    topic_id: Optional[int] = None,
    has_attachments: Optional[bool] = None,
    sort_by: str = "date_timestamp",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """
    Filter and sort emails with pagination.

    Returns:
        dict with items, total count, and pagination info
    """
    conditions = []
    params = []

    if sender_email:
        conditions.append("e.sender_email LIKE ?")
        params.append(f"%{sender_email}%")

    if sender_name:
        conditions.append("e.sender_name LIKE ?")
        params.append(f"%{sender_name}%")

    if date_from:
        conditions.append("e.date_sent >= ?")
        params.append(date_from)

    if date_to:
        conditions.append("e.date_sent <= ?")
        params.append(date_to)

    if subject_contains:
        conditions.append("e.subject LIKE ?")
        params.append(f"%{subject_contains}%")

    if mbox_source:
        conditions.append("e.mbox_source = ?")
        params.append(mbox_source)

    if has_attachments is not None:
        conditions.append("e.has_attachments = ?")
        params.append(int(has_attachments))

    # Topic filter via join
    join_clause = ""
    if topic_id is not None:
        join_clause = "JOIN email_topics et ON et.email_id = e.id"
        conditions.append("et.topic_id = ?")
        params.append(topic_id)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Validate sort column
    allowed_sorts = {"date_timestamp", "sender_email", "subject"}
    if sort_by not in allowed_sorts:
        sort_by = "date_timestamp"
    sort_dir = "ASC" if sort_order.lower() == "asc" else "DESC"

    offset = (page - 1) * page_size

    with get_db() as conn:
        # Count
        total = conn.execute(
            f"SELECT COUNT(*) FROM emails e {join_clause} WHERE {where_clause}",
            params
        ).fetchone()[0]

        # Fetch page
        rows = conn.execute(f"""
            SELECT e.* FROM emails e
            {join_clause}
            WHERE {where_clause}
            ORDER BY e.{sort_by} {sort_dir}
            LIMIT ? OFFSET ?
        """, params + [page_size, offset]).fetchall()

        items = [_row_to_summary(row) for row in rows]

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }


def get_email_detail(email_id: int) -> Optional[dict]:
    """Get full email details by ID."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
        if not row:
            return None

        data = dict(row)
        data["recipients"] = json.loads(data.get("recipients") or "[]")
        data["attachment_names"] = json.loads(data.get("attachment_names") or "[]")

        # Get associated topics
        topics = conn.execute("""
            SELECT t.id, t.label, t.description, t.keywords, t.email_count, et.confidence
            FROM topics t
            JOIN email_topics et ON et.topic_id = t.id
            WHERE et.email_id = ?
            ORDER BY et.confidence DESC
        """, (email_id,)).fetchall()

        data["topics"] = [
            {
                "id": t["id"],
                "label": t["label"],
                "description": t["description"],
                "keywords": json.loads(t["keywords"] or "[]"),
                "email_count": t["email_count"],
            }
            for t in topics
        ]

        return data


def get_senders(limit: int = 100) -> list[dict]:
    """Get list of unique senders with email counts."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT sender_email, sender_name, COUNT(*) as email_count
            FROM emails
            WHERE sender_email != ''
            GROUP BY sender_email
            ORDER BY email_count DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [dict(row) for row in rows]


def get_mbox_sources() -> list[dict]:
    """Get list of ingested mbox files with counts."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT mbox_source, COUNT(*) as email_count,
                   MIN(date_sent) as earliest, MAX(date_sent) as latest
            FROM emails
            GROUP BY mbox_source
            ORDER BY mbox_source
        """).fetchall()

        return [dict(row) for row in rows]


# -- Internal helpers --

def _row_to_summary(row) -> dict:
    """Convert a database row to an email summary dict."""
    data = {
        "id": row["id"],
        "message_id": row["message_id"],
        "subject": row["subject"],
        "sender_name": row["sender_name"],
        "sender_email": row["sender_email"],
        "date_sent": row["date_sent"],
        "has_attachments": bool(row["has_attachments"]),
        "snippet": make_snippet(row["body_text"] or ""),
    }
    # Include thread_group_id if available (may not exist in all queries)
    try:
        data["thread_group_id"] = row["thread_group_id"]
    except (IndexError, KeyError):
        pass
    return data


def _sanitize_fts_query(query: str) -> str:
    """
    Sanitize user input for FTS5 query syntax.

    Wraps each word in quotes to prevent FTS5 syntax errors
    from special characters.
    """
    words = query.strip().split()
    if not words:
        return '""'
    # Quote each term and join with implicit AND
    return " ".join(f'"{w}"' for w in words)


def _get_highlights(row, query: str) -> dict:
    """
    Generate simple highlight snippets showing where query matched.

    TODO: Use FTS5 highlight() function for more accurate highlights.
    """
    highlights = {}
    query_lower = query.lower()

    for field in ("subject", "sender_name", "body_text"):
        value = row[field] or ""
        if query_lower in value.lower():
            # Find the match position and extract context
            idx = value.lower().index(query_lower)
            start = max(0, idx - 50)
            end = min(len(value), idx + len(query) + 50)
            snippet = value[start:end]
            if start > 0:
                snippet = "…" + snippet
            if end < len(value):
                snippet = snippet + "…"
            highlights[field] = snippet

    return highlights
