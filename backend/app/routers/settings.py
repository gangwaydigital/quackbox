"""Settings endpoint — expose AI configuration to frontend."""
from fastapi import APIRouter
from app.config import (
    CHAT_API_URL, CHAT_MODEL, CHAT_API_TYPE,
    EMBED_API_URL, EMBED_MODEL, EMBED_API_TYPE,
    EMBEDDING_DIMENSIONS,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])

@router.get("")
async def get_settings():
    return {
        "chat": {
            "api_url": CHAT_API_URL,
            "model": CHAT_MODEL,
            "api_type": CHAT_API_TYPE,
        },
        "embedding": {
            "api_url": EMBED_API_URL,
            "model": EMBED_MODEL,
            "api_type": EMBED_API_TYPE,
            "dimensions": EMBEDDING_DIMENSIONS,
        },
    }
