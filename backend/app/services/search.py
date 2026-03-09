"""
Search and filter service.

Features:
- FTS5 full-text search with BM25 column weighting
- FTS5 snippet() for real highlighted context
- Prefix search (typing "projec" finds "project")
- Phrase search support ("exact phrase")
- Instant search endpoint (lightweight, no COUNT)
"""

import json
import re
from typing import Optional

from app.database import get_db
from app.utils.email_utils import make_snippet


# BM25 column weights: subject=10, sender_name=5, sender_email=3, body_text=1
BM25_WEIGHTS = "10.0, 5.0, 3.0, 1.0"


def full_text_search(
    query: str,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """
    Full-text search with BM25 ranking and FTS5 snippet highlights.
    """
    offset = (page - 1) * page_size

    with get_db() as conn:
        safe_query = _sanitize_fts_query(query)

        # Count total matches
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM emails_fts WHERE emails_fts MATCH ?",
                (safe_query,)
            ).fetchone()[0]
        except Exception:
            return {"results": [], "total": 0, "query": query, "page": page, "page_size": page_size}

        # Get ranked results with FTS5 snippet highlights
        try:
            rows = conn.execute(f"""
                SELECT
                    e.*,
                    bm25(emails_fts, {BM25_WEIGHTS}) as rank,
                    snippet(emails_fts, 0, '<mark>', '</mark>', '…', 12) as subj_hl,
                    snippet(emails_fts, 3, '<mark>', '</mark>', '…', 24) as body_hl
                FROM emails_fts
                JOIN emails e ON e.id = emails_fts.rowid
                WHERE emails_fts MATCH ?
                ORDER BY bm25(emails_fts, {BM25_WEIGHTS})
                LIMIT ? OFFSET ?
            """, (safe_query, page_size, offset)).fetchall()
        except Exception as exc:
            print(f"  ⚠ FTS5 search error: {exc}")
            return {"results": [], "total": 0, "query": query, "page": page, "page_size": page_size}

        results = []
        for row in rows:
            email_data = _row_to_summary(row)
            email_data["highlight_subject"] = row["subj_hl"] or None
            email_data["highlight_body"] = row["body_hl"] or None
            results.append({
                "email": email_data,
                "rank": abs(row["rank"]),
            })

        return {
            "results": results,
            "total": total,
            "query": query,
            "page": page,
            "page_size": page_size,
        }


def instant_search(query: str, limit: int = 8) -> list[dict]:
    """
    Lightweight instant search for typeahead preview.
    No COUNT query, small result set, fast.
    """
    with get_db() as conn:
        safe_query = _sanitize_fts_query(query)
        try:
            rows = conn.execute(f"""
                SELECT
                    e.id, e.subject, e.sender_name, e.sender_email,
                    e.date_sent, e.has_attachments, e.thread_group_id,
                    bm25(emails_fts, {BM25_WEIGHTS}) as rank,
                    snippet(emails_fts, 3, '<mark>', '</mark>', '…', 10) as body_hl
                FROM emails_fts
                JOIN emails e ON e.id = emails_fts.rowid
                WHERE emails_fts MATCH ?
                ORDER BY bm25(emails_fts, {BM25_WEIGHTS})
                LIMIT ?
            """, (safe_query, limit)).fetchall()
        except Exception:
            return []

        return [{
            "id": r["id"],
            "subject": r["subject"],
            "sender_name": r["sender_name"],
            "sender_email": r["sender_email"],
            "date_sent": r["date_sent"],
            "has_attachments": bool(r["has_attachments"]),
            "thread_group_id": r["thread_group_id"],
            "body_highlight": r["body_hl"],
        } for r in rows]


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
    """Filter and sort emails with pagination."""
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
        params.append(date_to + "T23:59:59" if len(date_to) == 10 else date_to)

    if subject_contains:
        conditions.append("e.subject LIKE ?")
        params.append(f"%{subject_contains}%")

    if mbox_source:
        conditions.append("e.mbox_source = ?")
        params.append(mbox_source)

    if has_attachments is not None:
        conditions.append("e.has_attachments = ?")
        params.append(int(has_attachments))

    join_clause = ""
    if topic_id is not None:
        join_clause = "JOIN email_topics et ON et.email_id = e.id"
        conditions.append("et.topic_id = ?")
        params.append(topic_id)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    allowed_sorts = {"date_timestamp", "sender_email", "subject"}
    if sort_by not in allowed_sorts:
        sort_by = "date_timestamp"
    sort_dir = "ASC" if sort_order.lower() == "asc" else "DESC"

    offset = (page - 1) * page_size

    with get_db() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM emails e {join_clause} WHERE {where_clause}",
            params
        ).fetchone()[0]

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

        return _json_safe(data)


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


# ── Internal helpers ─────────────────────────────────────────

def _row_to_summary(row) -> dict:
    """Convert a database row to an email summary dict."""
    data = {
        "id": row["id"],
        "message_id": _safe_text(row["message_id"]),
        "subject": _safe_text(row["subject"]),
        "sender_name": _safe_text(row["sender_name"]),
        "sender_email": _safe_text(row["sender_email"]),
        "date_sent": _safe_text(row["date_sent"]),
        "has_attachments": bool(row["has_attachments"]),
        "snippet": _safe_text(make_snippet(row["body_text"] or "")),
    }
    try:
        data["thread_group_id"] = row["thread_group_id"]
    except (IndexError, KeyError):
        pass
    return data


def _safe_text(value: Optional[str]) -> Optional[str]:
    """Normalize invalid Unicode/control chars so API JSON stays decodable."""
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    cleaned = value.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    # Keep common whitespace controls only.
    cleaned = "".join(ch for ch in cleaned if ch >= " " or ch in "\n\r\t")
    return cleaned


def _json_safe(value):
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    return value


def _sanitize_fts_query(query: str) -> str:
    """
    Sanitize user input for FTS5 query syntax.

    Supports:
    - Phrase search: "exact phrase" passes through
    - Prefix search: last term gets * appended for typeahead
    - Multi-word: implicit AND between terms
    - Special chars: stripped to prevent FTS5 syntax errors
    """
    query = query.strip()
    if not query:
        return '""'

    # Preserve user-quoted phrases
    phrases = []
    def _save_phrase(m):
        phrases.append(m.group(0))
        return f"__PHRASE{len(phrases) - 1}__"

    processed = re.sub(r'"[^"]*"', _save_phrase, query)

    # Clean remaining terms: strip FTS5 operators and special chars
    remaining = re.sub(r'[^\w\s]', ' ', processed)
    words = remaining.split()

    parts = []
    for w in words:
        # Restore saved phrases
        m = re.match(r'__PHRASE(\d+)__', w)
        if m:
            parts.append(phrases[int(m.group(1))])
        elif w.upper() in ('AND', 'OR', 'NOT', 'NEAR'):
            # Pass through FTS5 boolean operators
            parts.append(w.upper())
        elif len(w) >= 2:
            parts.append(f'"{w}"')

    if not parts:
        return '""'

    result = " ".join(parts)

    # Add prefix matching to the last non-phrase, non-operator term
    # This enables typeahead: "projec" matches "project"
    if not query.endswith('"') and parts:
        last = parts[-1]
        if last.startswith('"') and last.endswith('"') and last.upper() not in ('AND', 'OR', 'NOT', 'NEAR'):
            inner = last[1:-1]
            if len(inner) >= 2:
                parts[-1] = f'"{inner}"*'
                result = " ".join(parts)

    return result
