"""QuackBox — FastAPI Application"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db, get_stats
from app.logging_config import setup_logging
from app.routers import emails, topics, ingest, chat, threads, analytics, contacts, export, attachments, bookmarks, settings, deduplication, saved_searches
from app.services import watcher

APP_VERSION = "4.3.0"

log = setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("🦆 QuackBox v%s starting up", APP_VERSION)
    init_db()
    watcher.start()
    yield
    log.info("🦆 QuackBox shutting down")
    await watcher.stop()

app = FastAPI(title="QuackBox", description="Your inbox, quacked open", version=APP_VERSION, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173","http://localhost:3000","http://127.0.0.1:5173","http://127.0.0.1:3000"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(ingest.router)
app.include_router(emails.router)
app.include_router(topics.router)
app.include_router(chat.router)
app.include_router(threads.router)
app.include_router(analytics.router)
app.include_router(contacts.router)
app.include_router(export.router)
app.include_router(attachments.router)
app.include_router(bookmarks.router)
app.include_router(settings.router)
app.include_router(deduplication.router)
app.include_router(saved_searches.router)

@app.get("/")
async def root():
    return {"app": "QuackBox", "version": APP_VERSION, "docs": "/docs"}

@app.get("/api/stats")
async def stats():
    s = get_stats()
    s["version"] = APP_VERSION
    return s
