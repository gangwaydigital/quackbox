"""Topic clustering endpoints."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, Query

from app.models import ClusterRequest
from app.services.clustering import (
    check_ollama_available,
    generate_all_embeddings,
    cluster_topics,
    get_topics,
)
from app.services.search import filter_emails

router = APIRouter(prefix="/api/topics", tags=["topics"])

# Background task tracking. Mutated in-place (never reassigned) so callers
# always read the latest values; assigning a new dict would break holders.
_task_status = {
    "running": False, "phase": "idle", "progress": "",
    "embeddings_done": 0, "embeddings_total": 0,
    "result": None, "error": None,
}
_executor = ThreadPoolExecutor(max_workers=1)


def _reset_status(phase: str = "starting", progress: str = "") -> None:
    _task_status.update({
        "running": True, "phase": phase, "progress": progress,
        "embeddings_done": 0, "embeddings_total": 0,
        "result": None, "error": None,
    })


def _run_clustering_sync(num_clusters, regenerate):
    """Run clustering in a background thread."""
    try:
        _reset_status(phase="embedding", progress="Generating embeddings...")

        def on_embed_progress(done: int, total: int) -> None:
            _task_status["embeddings_done"] = done
            _task_status["embeddings_total"] = total
            if total > 0:
                pct = round(done / total * 100)
                _task_status["progress"] = f"Generating embeddings: {done:,} / {total:,} ({pct}%)"
            else:
                _task_status["progress"] = "Generating embeddings…"

        embed_result = generate_all_embeddings(
            regenerate=regenerate, progress_callback=on_embed_progress,
        )
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


@router.get("/{topic_id}")
async def get_topic_detail(topic_id: int, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    topics = get_topics()
    topic = next((t for t in topics if t["id"] == topic_id), None)
    if not topic:
        raise HTTPException(404, f"Topic {topic_id} not found")
    emails = filter_emails(topic_id=topic_id, page=page, page_size=page_size)
    return {**topic, "emails": emails}


def _run_embed_only_sync(regenerate: bool) -> None:
    """Run embedding generation in a background thread + report progress."""
    try:
        _reset_status(phase="embedding", progress="Generating embeddings…")

        def on_embed_progress(done: int, total: int) -> None:
            _task_status["embeddings_done"] = done
            _task_status["embeddings_total"] = total
            if total > 0:
                pct = round(done / total * 100)
                _task_status["progress"] = f"Generating embeddings: {done:,} / {total:,} ({pct}%)"

        embed_result = generate_all_embeddings(
            regenerate=regenerate, progress_callback=on_embed_progress,
        )
        _task_status.update({
            "running": False, "phase": "done",
            "progress": f"Done — {embed_result.get('generated', 0):,} embeddings generated",
            "result": embed_result, "error": None,
        })
    except Exception as e:
        _task_status.update({
            "running": False, "phase": "error", "progress": "",
            "result": None, "error": str(e),
        })


@router.post("/embed")
async def generate_embeddings(regenerate: bool = False):
    if not check_ollama_available():
        raise HTTPException(503, "Ollama is not running or model not available. Run: ollama pull nomic-embed-text")
    if _task_status["running"]:
        return {"message": "Already running", **_task_status}
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _run_embed_only_sync, regenerate)
    return {"message": "Embedding generation started in background. Check /api/topics/status for progress."}


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
