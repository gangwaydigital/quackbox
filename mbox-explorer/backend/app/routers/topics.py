"""
Topic clustering endpoints.

Manage AI-powered topic detection and clustering.
"""

from typing import Optional

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


@router.get("")
async def list_topics():
    """Get all discovered topics with email counts."""
    topics = get_topics()
    return {"topics": topics, "total": len(topics)}


@router.get("/{topic_id}")
async def get_topic_detail(
    topic_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Get a topic with its associated emails."""
    topics = get_topics()
    topic = next((t for t in topics if t["id"] == topic_id), None)
    if not topic:
        raise HTTPException(404, f"Topic {topic_id} not found")

    emails = filter_emails(topic_id=topic_id, page=page, page_size=page_size)
    return {**topic, "emails": emails}


@router.post("/embed")
async def generate_embeddings(regenerate: bool = False):
    """
    Generate Ollama embeddings for all emails.

    This is the first step before clustering. Each email's subject,
    sender, and body are combined and embedded.
    """
    if not check_ollama_available():
        raise HTTPException(
            503,
            f"Ollama is not running or model not available. "
            f"Run: ollama pull nomic-embed-text"
        )

    result = generate_all_embeddings(regenerate=regenerate)
    return result


@router.post("/cluster")
async def run_clustering(request: ClusterRequest = ClusterRequest()):
    """
    Run topic clustering on embedded emails.

    If embeddings haven't been generated yet, this will generate
    them first. Optionally specify the number of clusters.
    """
    if not check_ollama_available():
        raise HTTPException(
            503,
            f"Ollama is not running or model not available. "
            f"Run: ollama pull nomic-embed-text"
        )

    # Generate embeddings if needed
    if request.regenerate_embeddings:
        embed_result = generate_all_embeddings(regenerate=True)
    else:
        embed_result = generate_all_embeddings(regenerate=False)

    # Run clustering
    result = cluster_topics(num_clusters=request.num_clusters)
    result["embedding_stats"] = embed_result

    return result


@router.get("/status/ollama")
async def check_ollama():
    """Check if Ollama is available for embedding generation."""
    available = check_ollama_available()
    return {
        "available": available,
        "model": "nomic-embed-text",
        "message": "Ready" if available else "Ollama not running or model not pulled",
    }
