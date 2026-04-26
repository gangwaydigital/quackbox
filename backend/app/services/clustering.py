"""
AI-powered topic clustering service.

Uses embeddings to generate vector representations, then clusters them
to discover email topics automatically.
"""

import json
import threading
import time
from typing import Optional

import numpy as np
import requests
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from collections import Counter

from app.config import (
    EMBED_API_URL,
    EMBED_API_KEY,
    EMBED_MODEL,
    EMBED_API_TYPE,
    DEFAULT_NUM_CLUSTERS,
    MIN_CLUSTER_SIZE,
)
from app.database import get_db
from app.logging_config import get_logger

log = get_logger("clustering")


# Cooperative cancellation flag for the embedding loop. Set by the topics
# router when the user clicks "Cancel"; checked between batches so we can
# bail cleanly without losing the embeddings already persisted.
_cancel_event = threading.Event()


def request_cancel() -> None:
    """Signal the in-flight generate_all_embeddings loop to stop after the
    current batch. Safe to call from any thread."""
    _cancel_event.set()


def reset_cancel() -> None:
    """Clear the cancellation flag. Call before starting a new run."""
    _cancel_event.clear()


def is_cancel_requested() -> bool:
    return _cancel_event.is_set()


def check_ollama_available() -> bool:
    """Check if the embedding API is reachable."""
    try:
        if EMBED_API_TYPE == "openai":
            headers = {}
            if EMBED_API_KEY:
                headers["Authorization"] = f"Bearer {EMBED_API_KEY}"
            resp = requests.get(f"{EMBED_API_URL}/v1/models", headers=headers, timeout=5)
            return resp.status_code == 200
        else:
            resp = requests.get(f"{EMBED_API_URL}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                return (EMBED_MODEL in models or f"{EMBED_MODEL}:latest" in models)
            return False
    except Exception:
        return False


# Embedding-model heuristics for the model picker. The Ollama tag list
# contains every model installed (chat + embed mixed), so we filter on
# known-embedding family names. New families just need to be added here.
_KNOWN_EMBED_FAMILIES = (
    "embed", "minilm", "bge", "e5", "snowflake-arctic-embed", "mxbai",
    "gte-",
)

# Suggested alternatives surfaced when the current model is "slow" — the
# choices roughly span quality/speed/size so users have something to try.
_SUGGESTED_EMBED_MODELS = [
    {
        "name": "nomic-embed-text",
        "size": "274 MB",
        "dimensions": 768,
        "note": "Default. Great quality, moderate speed.",
    },
    {
        "name": "all-minilm",
        "size": "46 MB",
        "dimensions": 384,
        "note": "~5x faster, smaller dim — good for large archives.",
    },
    {
        "name": "mxbai-embed-large",
        "size": "670 MB",
        "dimensions": 1024,
        "note": "Larger, slower, slightly higher quality.",
    },
    {
        "name": "snowflake-arctic-embed",
        "size": "335 MB",
        "dimensions": 1024,
        "note": "Strong English benchmarks.",
    },
]


def list_embed_models() -> dict:
    """
    Probe the configured embedding endpoint for available models and merge
    in our suggested-alternatives list. Returns a dict the Topics UI can
    use to show the current model + offer switches.

    Switching requires editing EMBED_MODEL in .env and restarting the
    backend — we don't try to hot-swap.
    """
    info = {
        "current": EMBED_MODEL,
        "api_type": EMBED_API_TYPE,
        "api_url": EMBED_API_URL,
        "installed": [],
        "suggested": _SUGGESTED_EMBED_MODELS,
        "reachable": False,
        "error": None,
    }
    try:
        if EMBED_API_TYPE == "openai":
            headers = {}
            if EMBED_API_KEY:
                headers["Authorization"] = f"Bearer {EMBED_API_KEY}"
            resp = requests.get(f"{EMBED_API_URL}/v1/models", headers=headers, timeout=5)
            if resp.status_code == 200:
                info["reachable"] = True
                # OpenAI shape: {"data": [{"id": "...", ...}]}
                models = [m.get("id") for m in resp.json().get("data", []) if m.get("id")]
                # Filter to embedding-looking IDs to keep the list short
                info["installed"] = [
                    {"name": m} for m in models
                    if any(family in m.lower() for family in _KNOWN_EMBED_FAMILIES)
                ]
            else:
                info["error"] = f"HTTP {resp.status_code} from {EMBED_API_URL}"
        else:
            resp = requests.get(f"{EMBED_API_URL}/api/tags", timeout=5)
            if resp.status_code == 200:
                info["reachable"] = True
                # Ollama shape: {"models": [{"name": "...", "size": <bytes>, ...}]}
                for m in resp.json().get("models", []):
                    name = m.get("name", "")
                    if not any(family in name.lower() for family in _KNOWN_EMBED_FAMILIES):
                        continue
                    item = {"name": name}
                    size_bytes = m.get("size")
                    if size_bytes:
                        item["size"] = f"{round(size_bytes / 1_048_576)} MB"
                    info["installed"].append(item)
            else:
                info["error"] = f"HTTP {resp.status_code} from {EMBED_API_URL}"
    except Exception as e:
        info["error"] = str(e)
    return info


def generate_embedding(text: str) -> Optional[list[float]]:
    """Generate an embedding vector using configured API (Ollama or OpenAI-compatible)."""
    try:
        if EMBED_API_TYPE == "openai":
            headers = {"Content-Type": "application/json"}
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
                if data.get("data") and len(data["data"]) > 0:
                    return data["data"][0]["embedding"]
            return None
        else:
            resp = requests.post(
                f"{EMBED_API_URL}/api/embed",
                json={"model": EMBED_MODEL, "input": text},
                timeout=30,
            )
        if resp.status_code == 200:
            data = resp.json()
            embeddings = data.get("embeddings", [])
            if embeddings:
                return embeddings[0]
            return data.get("embedding")
        return None
    except Exception as e:
        log.warning("Embedding error: %s", e)
        return None


def generate_all_embeddings(
    batch_size: int = 50,
    regenerate: bool = False,
    progress_callback=None,
) -> dict:
    """
    Generate embeddings for all emails that don't have them yet.

    Args:
        batch_size: Number of emails to process between commits
        regenerate: If True, regenerate all embeddings
        progress_callback: Optional callable invoked as fn(done, total) every
            batch_size emails so callers (e.g. the topics router) can surface
            live progress. Errors in the callback are swallowed so they can't
            break the embedding loop.

    Returns:
        dict with processing statistics
    """
    start = time.time()
    generated = 0
    skipped = 0
    errors = 0

    def _emit(done: int, total: int) -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(done, total)
        except Exception:
            log.exception("progress_callback raised; ignoring")

    with get_db() as conn:
        if regenerate:
            conn.execute("DELETE FROM embeddings")
            condition = ""
        else:
            condition = "WHERE e.id NOT IN (SELECT email_id FROM embeddings)"

        rows = conn.execute(f"""
            SELECT e.id, e.subject, e.sender_name, e.body_text
            FROM emails e
            {condition}
        """).fetchall()

        total = len(rows)
        log.info("🧠 Generating embeddings for %d emails...", total)
        _emit(0, total)

        cancelled = False
        processed = 0
        for i, row in enumerate(rows):
            # Cooperative cancellation — check at the top of each iteration
            # so already-completed batches stay persisted.
            if is_cancel_requested():
                cancelled = True
                conn.commit()
                _emit(processed, total)
                log.info("⛔ Embedding cancelled at %d/%d", processed, total)
                break

            # Create embedding input: combine subject + sender + body snippet
            text = _make_embedding_text(
                subject=row["subject"],
                sender=row["sender_name"],
                body=row["body_text"],
            )

            if not text.strip():
                skipped += 1
                processed = i + 1
                continue

            embedding = generate_embedding(text)
            if embedding:
                # Store as numpy bytes for compact storage
                embedding_bytes = np.array(embedding, dtype=np.float32).tobytes()
                conn.execute(
                    "INSERT OR REPLACE INTO embeddings (email_id, embedding, model) VALUES (?, ?, ?)",
                    (row["id"], embedding_bytes, EMBED_MODEL),
                )
                generated += 1
            else:
                errors += 1

            processed = i + 1
            if processed % batch_size == 0:
                conn.commit()
                log.debug("  ... %d/%d (%d generated)", processed, total, generated)
                _emit(processed, total)

        if not cancelled:
            # Final emit so callers see 100%
            _emit(total, total)

    duration = time.time() - start
    result = {
        "total": total,
        "generated": generated,
        "skipped": skipped,
        "errors": errors,
        "cancelled": cancelled,
        "duration_seconds": round(duration, 2),
    }
    if cancelled:
        log.info("⛔ Embeddings cancelled: %d generated, %d errors (%.1fs)", generated, errors, duration)
    else:
        log.info("✅ Embeddings done: %d generated, %d errors (%.1fs)", generated, errors, duration)
    return result


def cluster_topics(num_clusters: Optional[int] = None) -> dict:
    """
    Cluster emails into topics based on their embeddings.

    Uses K-Means clustering. If num_clusters is None, automatically
    determines the optimal number using silhouette scoring.

    Returns:
        dict with clustering results and topic info
    """
    start = time.time()

    with get_db() as conn:
        # Load all embeddings
        rows = conn.execute("""
            SELECT emb.email_id, emb.embedding, e.subject, e.body_text
            FROM embeddings emb
            JOIN emails e ON e.id = emb.email_id
        """).fetchall()

        if len(rows) < 10:
            return {"error": "Need at least 10 emails with embeddings to cluster"}

        email_ids = [row["email_id"] for row in rows]
        subjects = [row["subject"] or "" for row in rows]
        bodies = [row["body_text"] or "" for row in rows]

        # Reconstruct numpy arrays from stored bytes
        embeddings = np.array([
            np.frombuffer(row["embedding"], dtype=np.float32)
            for row in rows
        ])

        log.info("🔬 Clustering %d emails...", len(embeddings))

        # Determine optimal cluster count if not specified
        if num_clusters is None:
            num_clusters = _find_optimal_clusters(embeddings)
            log.info("  Auto-selected %d clusters", num_clusters)

        # Run K-Means
        kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(embeddings)

        # Clear old topics
        conn.execute("DELETE FROM email_topics")
        conn.execute("DELETE FROM topics")

        # Create topics and assign emails
        topics = []
        for cluster_id in range(num_clusters):
            mask = labels == cluster_id
            cluster_email_ids = [eid for eid, m in zip(email_ids, mask) if m]
            cluster_subjects = [s for s, m in zip(subjects, mask) if m]
            cluster_bodies = [b for b, m in zip(bodies, mask) if m]

            if len(cluster_email_ids) < 1:
                continue

            # Generate topic label from most common terms
            keywords = _extract_keywords(cluster_subjects, cluster_bodies)
            label = _make_topic_label(keywords)
            description = f"Cluster of {len(cluster_email_ids)} emails about: {', '.join(keywords[:5])}"

            # Insert topic
            cursor = conn.execute(
                "INSERT INTO topics (label, description, keywords, email_count) VALUES (?, ?, ?, ?)",
                (label, description, json.dumps(keywords[:10]), len(cluster_email_ids)),
            )
            topic_id = cursor.lastrowid

            # Assign emails to topic
            # Calculate confidence as distance from cluster center
            center = kmeans.cluster_centers_[cluster_id]
            for eid, emb_row, is_member in zip(email_ids, embeddings, mask):
                if is_member:
                    distance = np.linalg.norm(emb_row - center)
                    confidence = max(0.0, 1.0 - (distance / 10.0))  # Normalize
                    conn.execute(
                        "INSERT INTO email_topics (email_id, topic_id, confidence) VALUES (?, ?, ?)",
                        (eid, topic_id, round(confidence, 4)),
                    )

            topics.append({
                "id": topic_id,
                "label": label,
                "keywords": keywords[:10],
                "email_count": len(cluster_email_ids),
            })

    duration = time.time() - start
    return {
        "num_clusters": len(topics),
        "topics": topics,
        "total_emails_clustered": len(email_ids),
        "duration_seconds": round(duration, 2),
    }


def get_topics() -> list[dict]:
    """Get all topics with their email counts."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, label, description, keywords, email_count
            FROM topics
            ORDER BY email_count DESC
        """).fetchall()

        return [
            {
                "id": row["id"],
                "label": row["label"],
                "description": row["description"],
                "keywords": json.loads(row["keywords"] or "[]"),
                "email_count": row["email_count"],
            }
            for row in rows
        ]


# -- Internal helpers --

def _make_embedding_text(subject: str, sender: str, body: str, max_body: int = 500) -> str:
    """Combine email fields into text suitable for embedding."""
    parts = []
    if subject:
        parts.append(f"Subject: {subject}")
    if sender:
        parts.append(f"From: {sender}")
    if body:
        # Use first N chars of body — enough for topic signal
        parts.append(body[:max_body])
    return "\n".join(parts)


def _find_optimal_clusters(embeddings: np.ndarray, max_k: int = 30) -> int:
    """
    Use silhouette scoring to find optimal cluster count.

    Tests k from 5 to max_k and picks the best silhouette score.
    """
    n_samples = len(embeddings)
    max_k = min(max_k, n_samples // MIN_CLUSTER_SIZE)
    max_k = max(max_k, 3)

    best_score = -1
    best_k = DEFAULT_NUM_CLUSTERS

    for k in range(max(2, 5), max_k + 1, 2):  # Test odd numbers for speed
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=5, max_iter=100)
        labels = kmeans.fit_predict(embeddings)
        score = silhouette_score(embeddings, labels, sample_size=min(5000, n_samples))
        if score > best_score:
            best_score = score
            best_k = k

    return best_k


def _extract_keywords(subjects: list[str], bodies: list[str], top_n: int = 10) -> list[str]:
    """Extract most common meaningful words from a cluster's emails."""
    # Simple term frequency approach
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "shall", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "above", "below", "between", "out", "off", "over",
        "under", "again", "further", "then", "once", "here", "there", "when",
        "where", "why", "how", "all", "each", "every", "both", "few", "more",
        "most", "other", "some", "such", "no", "nor", "not", "only", "own",
        "same", "so", "than", "too", "very", "just", "don", "now", "re",
        "this", "that", "these", "those", "i", "me", "my", "we", "our",
        "you", "your", "he", "him", "his", "she", "her", "it", "its",
        "they", "them", "their", "what", "which", "who", "whom",
        "and", "but", "if", "or", "because", "about", "up",
        "hi", "hello", "thanks", "thank", "please", "regards", "sent",
        "am", "pm", "wrote", "subject", "from", "date",
    }

    word_counts = Counter()
    for text in (subjects or []) + [(b or "")[:300] for b in (bodies or [])]:
        if not text:
            continue
        words = text.lower().split()
        for word in words:
            cleaned = "".join(c for c in word if c.isalnum())
            if cleaned and len(cleaned) > 2 and cleaned not in stop_words:
                word_counts[cleaned] += 1

    return [word for word, _ in word_counts.most_common(top_n)]


def _make_topic_label(keywords: list[str]) -> str:
    """Create a human-readable topic label from keywords."""
    if not keywords:
        return "Uncategorized"
    # Use top 2-3 keywords as the label
    label_words = keywords[:3]
    return " / ".join(w.title() for w in label_words)
