"""QuackBox — FastAPI Application"""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import init_db, get_stats
from app.logging_config import setup_logging
from app.routers import emails, topics, ingest, chat, threads, analytics, contacts, export, attachments, bookmarks, settings, deduplication, saved_searches, accounts

APP_VERSION = "4.0.0"

log = setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("🦆 QuackBox v%s starting up", APP_VERSION)
    init_db()
    yield
    log.info("🦆 QuackBox shutting down")

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
app.include_router(accounts.router)

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"

if FRONTEND_ASSETS.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_ASSETS)), name="frontend-assets")


@app.get("/")
async def root():
    if (FRONTEND_DIST / "index.html").exists():
        return FileResponse(str(FRONTEND_DIST / "index.html"))
    return {"app": "QuackBox", "version": APP_VERSION, "docs": "/docs"}

@app.get("/api/stats")
async def stats():
    s = get_stats()
    s["version"] = APP_VERSION
    return s


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if full_path.startswith("api/") or full_path in {"docs", "redoc", "openapi.json"}:
        raise HTTPException(status_code=404, detail="Not Found")

    if not (FRONTEND_DIST / "index.html").exists():
        return {"app": "QuackBox", "version": APP_VERSION, "docs": "/docs"}

    candidate = FRONTEND_DIST / full_path
    if candidate.is_file():
        return FileResponse(str(candidate))
    return FileResponse(str(FRONTEND_DIST / "index.html"))
