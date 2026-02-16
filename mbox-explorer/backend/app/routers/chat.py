"""
Chat endpoints.

Conversational AI interface for exploring email data.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.chat import chat, get_available_models, get_stats_summary

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User's question about their emails")
    conversation_history: list[dict] = Field(default=[], description="Previous turns [{role, content}]")
    model: Optional[str] = Field(None, description="Ollama model to use (defaults to llama3.1:8b)")


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict] = []
    model: str
    emails_searched: int = 0
    error: bool = False


@router.post("", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Ask a question about your email archive.

    The system searches for relevant emails, then uses Ollama
    to generate a conversational answer grounded in the data.
    """
    result = chat(
        question=request.question,
        conversation_history=request.conversation_history,
        model=request.model,
    )
    return ChatResponse(**result)


@router.get("/models")
async def list_models():
    """List available Ollama models for chat."""
    models = get_available_models()
    return {
        "models": models,
        "default": "llama3.1:8b",
        "available": len(models) > 0,
    }


@router.get("/summary")
async def archive_summary():
    """Get a quick summary of the email archive."""
    return {"summary": get_stats_summary()}
