"""Settings endpoint — expose and update AI configuration to frontend."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.config import (
    CHAT_API_URL, CHAT_MODEL, CHAT_API_TYPE,
    EMBED_API_URL, EMBED_MODEL, EMBED_API_TYPE,
    EMBEDDING_DIMENSIONS,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ChatConfig(BaseModel):
    api_url: str
    model: str
    api_type: str


class EmbeddingConfig(BaseModel):
    api_url: str
    model: str
    api_type: str
    dimensions: int


class SettingsUpdate(BaseModel):
    chat: Optional[ChatConfig] = None
    embedding: Optional[EmbeddingConfig] = None


@router.get("")
async def get_settings() -> dict:
    """Get current AI configuration."""
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


@router.post("")
async def update_settings(body: SettingsUpdate) -> dict:
    """Update AI configuration via environment variables."""
    errors = []

    if body.chat is not None:
        if body.chat.api_url:
            import os
            os.environ["CHAT_API_URL"] = body.chat.api_url
        if body.chat.model:
            import os
            os.environ["CHAT_MODEL"] = body.chat.model
        if body.chat.api_type:
            import os
            os.environ["CHAT_API_TYPE"] = body.chat.api_type

    if body.embedding is not None:
        if body.embedding.api_url:
            import os
            os.environ["EMBED_API_URL"] = body.embedding.api_url
        if body.embedding.model:
            import os
            os.environ["EMBED_MODEL"] = body.embedding.model
        if body.embedding.api_type:
            import os
            os.environ["EMBED_API_TYPE"] = body.embedding.api_type
        if body.embedding.dimensions:
            import os
            os.environ["EMBEDDING_DIMENSIONS"] = str(body.embedding.dimensions)

    # Re-read config to get updated values
    from app.config import (
        CHAT_API_URL as new_chat_url,
        CHAT_MODEL as new_chat_model,
        CHAT_API_TYPE as new_chat_type,
        EMBED_API_URL as new_embed_url,
        EMBED_MODEL as new_embed_model,
        EMBED_API_TYPE as new_embed_type,
        EMBEDDING_DIMENSIONS as new_embed_dims,
    )

    return {
        "chat": {
            "api_url": new_chat_url,
            "model": new_chat_model,
            "api_type": new_chat_type,
        },
        "embedding": {
            "api_url": new_embed_url,
            "model": new_embed_model,
            "api_type": new_embed_type,
            "dimensions": new_embed_dims,
        },
        "errors": errors,
    }
