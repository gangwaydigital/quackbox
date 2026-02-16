"""
Mbox Explorer — FastAPI Application

Main entry point for the backend API.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db, get_stats
from app.routers import emails, topics, ingest, chat, threads, analytics


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    init_db()
    yield


app = FastAPI(
    title="Mbox Explorer",
    description="Index, search, and explore email archives from .mbox files",
    version="0.1.0",
    lifespan=lifespan,
)

# -- CORS (allow React dev server) --
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",   # CRA dev server
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- Mount routers --
app.include_router(ingest.router)
app.include_router(emails.router)
app.include_router(topics.router)
app.include_router(chat.router)
app.include_router(threads.router)
app.include_router(analytics.router)


# -- Root / health endpoints --

@app.get("/")
async def root():
    return {
        "app": "Mbox Explorer",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/api/stats")
async def stats():
    """Get database statistics."""
    return get_stats()
