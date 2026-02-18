"""
Semantic search service.

Uses Ollama embeddings for cosine similarity search,
hybrid search (FTS5 + semantic), and find-similar.
"""
import numpy as np
import requests
from typing import Optional
from app.config import EMBED_API_URL, EMBED_MODEL, EMBED_API_TYPE, EMBED_API_KEY
from app.database import get_db
from app.logging_config import get_logger

log = get_logger("semantic")


def _generate_query_embedding(text: str) -> Optional[np.ndarray]:
    """Generate an embedding for a query string. Supports Ollama and OpenAI API formats."""
    try:
        headers = {"Content-Type": "application/json"}
        if EMBED_API_TYPE == "openai":
            if EMBED_API_KEY:
                headers["Authorization"] = f"Bearer {EMBED_API_KEY}"
            resp = requests.post(
                f"{EMBED_API_URL}/v1/embeddings",
                headers=headers,
                json={"model": EMBED_MODEL, "input": text},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                emb = data.get("data", [])
                if emb:
                    return np.array(emb[0]["embedding"], dtype=np.float32)
        else:
            resp = requests.post(
                f"{EMBED_API_URL}/api/embed",
                json={"model": EMBED_MODEL, "input": text},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                emb = data.get("embeddings", [])
                if emb:
                    return np.array(emb[0], dtype=np.float32)
                emb = data.get("embedding")
                if emb:
                    return np.array(emb, dtype=np.float32)
    except Exception as e:
        log.warning("Query embedding error: %s", e)
    return None


def _load_all_embeddings(conn):
    """Load all embeddings from DB into a matrix + ID list."""
    rows = conn.execute("SELECT email_id, embedding FROM embeddings").fetchall()
    if not rows:
        return None, []
    ids = []
    vecs = []
    for row in rows:
        ids.append(row["email_id"])
        vecs.append(np.frombuffer(row["embedding"], dtype=np.float32))
    return np.vstack(vecs), ids


def _cosine_similarity(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between query and all rows in matrix."""
    # Normalize
    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10
    matrix_norm = matrix / norms
    return matrix_norm @ query_norm


def semantic_search(query: str, limit: int = 20) -> list[dict]:
    """
    Search emails by semantic similarity to the query.
    Embeds the query, then finds nearest neighbors.
    Uses batch email lookup instead of N individual queries.
    """
    query_vec = _generate_query_embedding(query)
    if query_vec is None:
        return []

    with get_db() as conn:
        matrix, ids = _load_all_embeddings(conn)
        if matrix is None:
            return []

        scores = _cosine_similarity(query_vec, matrix)
        top_indices = np.argsort(scores)[::-1][:limit * 2]  # over-fetch to filter low scores

        # Filter to meaningful scores and collect IDs
        candidates = [(ids[idx], float(scores[idx])) for idx in top_indices if scores[idx] >= 0.1]
        candidates = candidates[:limit]

        if not candidates:
            return []

        # Batch lookup all emails in ONE query
        email_ids = [c[0] for c in candidates]
        score_map = {c[0]: c[1] for c in candidates}
        placeholders = ",".join("?" * len(email_ids))
        rows = conn.execute(f"""
            SELECT id, subject, sender_name, sender_email, date_sent,
                   body_text, mbox_source, thread_group_id
            FROM emails WHERE id IN ({placeholders})
        """, email_ids).fetchall()

        # Build lookup and return in score order
        row_map = {r["id"]: r for r in rows}
        results = []
        for eid, score in candidates:
            row = row_map.get(eid)
            if row:
                results.append({
                    "id": row["id"],
                    "subject": row["subject"],
                    "sender_name": row["sender_name"],
                    "sender_email": row["sender_email"],
                    "date_sent": row["date_sent"],
                    "snippet": (row["body_text"] or "")[:200],
                    "mbox_source": row["mbox_source"],
                    "thread_group_id": row["thread_group_id"],
                    "similarity": round(score, 4),
                })
        return results


def find_similar(email_id: int, limit: int = 10) -> list[dict]:
    """Find emails similar to a given email by comparing embeddings."""
    with get_db() as conn:
        row = conn.execute("SELECT embedding FROM embeddings WHERE email_id = ?", (email_id,)).fetchone()
        if not row:
            return []
        query_vec = np.frombuffer(row["embedding"], dtype=np.float32)

        matrix, ids = _load_all_embeddings(conn)
        if matrix is None:
            return []

        scores = _cosine_similarity(query_vec, matrix)

        # Exclude the source email itself
        try:
            self_idx = ids.index(email_id)
            scores[self_idx] = -1
        except ValueError:
            pass

        top_indices = np.argsort(scores)[::-1][:limit * 2]
        candidates = [(ids[idx], float(scores[idx])) for idx in top_indices if scores[idx] >= 0.1]
        candidates = candidates[:limit]

        if not candidates:
            return []

        # Batch lookup
        email_ids = [c[0] for c in candidates]
        score_map = {c[0]: c[1] for c in candidates}
        placeholders = ",".join("?" * len(email_ids))
        rows = conn.execute(f"""
            SELECT id, subject, sender_name, sender_email, date_sent,
                   body_text, mbox_source, thread_group_id
            FROM emails WHERE id IN ({placeholders})
        """, email_ids).fetchall()

        row_map = {r["id"]: r for r in rows}
        results = []
        for eid, score in candidates:
            r = row_map.get(eid)
            if r:
                results.append({
                    "id": r["id"],
                    "subject": r["subject"],
                    "sender_name": r["sender_name"],
                    "sender_email": r["sender_email"],
                    "date_sent": r["date_sent"],
                    "snippet": (r["body_text"] or "")[:200],
                    "mbox_source": r["mbox_source"],
                    "thread_group_id": r["thread_group_id"],
                    "similarity": round(score, 4),
                })
        return results


def hybrid_search(query: str, limit: int = 20) -> list[dict]:
    """
    Combine FTS5 keyword results + semantic results.
    Uses reciprocal rank fusion to merge rankings.
    """
    # Get FTS5 results
    fts_results = []
    with get_db() as conn:
        words = query.strip().split()
        if words:
            safe_q = " ".join(f'"{w}"' for w in words)
            try:
                rows = conn.execute("""
                    SELECT e.id, e.subject, e.sender_name, e.sender_email,
                           e.date_sent, e.body_text, e.mbox_source, e.thread_group_id
                    FROM emails_fts
                    JOIN emails e ON e.id = emails_fts.rowid
                    WHERE emails_fts MATCH ?
                    ORDER BY rank LIMIT ?
                """, (safe_q, limit * 2)).fetchall()
                fts_results = [dict(r) for r in rows]
            except Exception:
                pass

    # Get semantic results
    sem_results = semantic_search(query, limit=limit * 2)

    # Reciprocal rank fusion
    K = 60  # RRF constant
    scores = {}
    email_data = {}

    for rank, r in enumerate(fts_results):
        eid = r["id"]
        scores[eid] = scores.get(eid, 0) + 1.0 / (K + rank + 1)
        email_data[eid] = r

    for rank, r in enumerate(sem_results):
        eid = r["id"]
        scores[eid] = scores.get(eid, 0) + 1.0 / (K + rank + 1)
        if eid not in email_data:
            email_data[eid] = r

    # Sort by fused score
    ranked = sorted(scores.items(), key=lambda x: -x[1])[:limit]

    results = []
    for eid, score in ranked:
        data = email_data[eid]
        results.append({
            "id": data["id"],
            "subject": data.get("subject"),
            "sender_name": data.get("sender_name"),
            "sender_email": data.get("sender_email"),
            "date_sent": data.get("date_sent"),
            "snippet": (data.get("body_text") or data.get("snippet") or "")[:200],
            "mbox_source": data.get("mbox_source"),
            "thread_group_id": data.get("thread_group_id"),
            "score": round(score, 4),
        })
    return results


def has_embeddings() -> bool:
    """Check if any embeddings exist."""
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        return count > 0
