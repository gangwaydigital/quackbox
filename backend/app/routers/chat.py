"""Chat endpoints."""
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.services.chat import chat, get_available_models, get_stats_summary

router = APIRouter(prefix="/api/chat", tags=["chat"])

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    conversation_history: list[dict] = Field(default=[])
    model: Optional[str] = Field(None)

class ChatResponse(BaseModel):
    answer: str
    sources: list[dict] = []
    model: str
    emails_searched: int = 0
    error: bool = False

@router.post("", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    result = chat(question=request.question, conversation_history=request.conversation_history, model=request.model)
    return ChatResponse(**result)

@router.get("/models")
async def list_models():
    models = get_available_models()
    return {"models": models, "default": "llama3.1:8b", "available": len(models) > 0}

@router.get("/summary")
async def archive_summary():
    return {"summary": get_stats_summary()}
