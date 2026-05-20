"""Topic clustering endpoints."""

import asyncio
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models import ClusterRequest
from app.services.clustering import (
    check_ollama_available,
    generate_all_embeddings,
    cluster_topics,
    get_topics,
    list_embed_models,
    request_cancel,
    reset_cancel,
    is_cancel_requested,
)
from app.services.search import filter_emails

router = APIRouter(prefix="/api/topics", tags=["topics"])

# Background task tracking. Mutated in-place (never reassigned) so callers
# always read the latest values; assigning a new dict would break holders.
_task_status = {
    "running": False, "phase": "idle", "progress": "",
    "embeddings_done": 0, "embeddings_total": 0,
    "embeddings_per_second": None, "eta_seconds": None,
    "result": None, "error": None,
}
_executor = ThreadPoolExecutor(max_workers=1)


class _RateTracker:
    """
    Rolling-window estimator for embedding throughput.

    Keeps the last `window_seconds` of (timestamp, done) samples so the rate
    reflects current performance — early-batch warmup or a slow Ollama spell
    don't poison the ETA forever.
    """

    def __init__(self, window_seconds: float = 30.0):
        self.window = window_seconds
        self.samples: deque = deque()  # (timestamp, done)

    def record(self, done: int) -> None:
        now = time.time()
        self.samples.append((now, done))
        cutoff = now - self.window
        while self.samples and self.samples[0][0] < cutoff:
            self.samples.popleft()

    def rate_per_second(self) -> Optional[float]:
        if len(self.samples) < 2:
            return None
        first_t, first_d = self.samples[0]
        last_t, last_d = self.samples[-1]
        delta_t = last_t - first_t
        delta_d = last_d - first_d
        if delta_t <= 0 or delta_d <= 0:
            return None
        return delta_d / delta_t

    def eta_seconds(self, total: int) -> Optional[int]:
        rate = self.rate_per_second()
        if rate is None or rate <= 0 or not self.samples:
            return None
        remaining = total - self.samples[-1][1]
        if remaining <= 0:
            return 0
        return int(remaining / rate)


def _reset_status(phase: str = "starting", progress: str = "") -> None:
    # Clear any leftover cancel signal from a previous run
    reset_cancel()
    _task_status.update({
        "running": True, "phase": phase, "progress": progress,
        "embeddings_done": 0, "embeddings_total": 0,
        "embeddings_per_second": None, "eta_seconds": None,
        "result": None, "error": None,
    })


def _format_eta(seconds: Optional[int]) -> str:
    if seconds is None:
        return ""
    if seconds < 60:
        return f"~{seconds}s left"
    if seconds < 3600:
        return f"~{seconds // 60}m left"
    h, rem = divmod(seconds, 3600)
    return f"~{h}h {rem // 60}m left"


def _run_clustering_sync(num_clusters, regenerate):
    """Run clustering in a background thread."""
    try:
        _reset_status(phase="embedding", progress="Generating embeddings...")
        tracker = _RateTracker()

        def on_embed_progress(done: int, total: int) -> None:
            tracker.record(done)
            rate = tracker.rate_per_second()
            eta = tracker.eta_seconds(total)
            _task_status["embeddings_done"] = done
            _task_status["embeddings_total"] = total
            _task_status["embeddings_per_second"] = round(rate, 2) if rate else None
            _task_status["eta_seconds"] = eta
            if total > 0:
                pct = round(done / total * 100)
                base = f"Generating embeddings: {done:,} / {total:,} ({pct}%)"
                eta_str = _format_eta(eta)
                _task_status["progress"] = f"{base} · {eta_str}" if eta_str else base
            else:
                _task_status["progress"] = "Generating embeddings…"

        embed_result = generate_all_embeddings(
            regenerate=regenerate, progress_callback=on_embed_progress,
        )

        # If the user cancelled mid-embedding, stop here. The embeddings that
        # made it in stay persisted, so re-running picks up where we left off.
        if embed_result.get("cancelled"):
            _task_status.update({
                "running": False, "phase": "cancelled",
                "progress": (
                    f"Cancelled — {embed_result.get('generated', 0):,} embeddings "
                    f"persisted; re-run to continue"
                ),
                "result": {"embedding_stats": embed_result, "cancelled": True},
                "error": None,
            })
            return

        _task_status["phase"] = "clustering"
        _task_status["progress"] = "Clustering topics…"
        result = cluster_topics(num_clusters=num_clusters)
        result["embedding_stats"] = embed_result
        _task_status.update({
            "running": False, "phase": "done",
            "progress": (
                f"Done — {result.get('num_clusters', 0)} topics "
                f"from {result.get('total_emails_clustered', 0):,} emails"
            ),
            "result": result, "error": None,
        })
    except Exception as e:
        _task_status.update({
            "running": False, "phase": "error", "progress": "",
            "result": None, "error": str(e),
        })


@router.get("")
async def list_topics():
    topics = get_topics()
    return {"topics": topics, "total": len(topics)}


@router.get("/status")
async def clustering_status():
    """Check the status of a running clustering job."""
    return _task_status


@router.get("/embed-models")
async def embed_models():
    """
    List the configured embedding model alongside any other embedding-family
    models found on the API endpoint, plus a curated list of suggested
    alternatives. Switching requires editing EMBED_MODEL in .env and
    restarting the backend (no hot-swap).

    Registered before /{topic_id} so the catch-all int route doesn't try
    to parse "embed-models" as a topic id.
    """
    return list_embed_models()


@router.get("/{topic_id}")
async def get_topic_detail(topic_id: int, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    topics = get_topics()
    topic = next((t for t in topics if t["id"] == topic_id), None)
    if not topic:
        raise HTTPException(404, f"Topic {topic_id} not found")
    emails = filter_emails(topic_id=topic_id, page=page, page_size=page_size)
    return {**topic, "emails": emails}


@router.post("/cluster")
async def run_clustering(request: ClusterRequest = ClusterRequest()):
    if not check_ollama_available():
        raise HTTPException(503, "Ollama is not running or model not available. Run: ollama pull nomic-embed-text")
    if _task_status["running"]:
        return {"message": "Clustering already in progress", **_task_status}
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _run_clustering_sync, request.num_clusters, request.regenerate_embeddings)
    return {"message": "Clustering started in background. Check /api/topics/status for progress."}


@router.get("/status/ollama")
async def check_ollama():
    available = check_ollama_available()
    return {"available": available, "model": "nomic-embed-text", "message": "Ready" if available else "Ollama not running or model not pulled"}


@router.post("/cancel")
async def cancel_clustering():
    """
    Request cancellation of an in-flight embedding/clustering job.

    Cancellation is cooperative — the embedding loop checks the flag between
    batches, so it may take a few seconds before the task actually stops.
    Embeddings already persisted stay in the database; re-running picks up
    where this left off (skipping emails that already have embeddings).
    """
    if not _task_status.get("running"):
        return {"message": "No clustering job is currently running.", "cancelled": False}
    request_cancel()
    _task_status["progress"] = "Cancelling…"
    return {"message": "Cancellation requested. The job will stop after the current batch.", "cancelled": True}
