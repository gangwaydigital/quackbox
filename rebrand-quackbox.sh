#!/bin/bash
# QuackBox Rebrand + Git Setup
# Renames everything from "Mbox Explorer" to "QuackBox" and inits git
# Run from mbox-explorer directory
set -e
echo "🦆 Rebranding to QuackBox..."

# ============================================================
# 1. BACKEND: main.py
# ============================================================
cat > backend/app/main.py << 'PYEOF'
"""QuackBox — FastAPI Application"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db, get_stats
from app.routers import emails, topics, ingest, chat, threads, analytics, contacts, export, attachments, bookmarks

APP_VERSION = "3.1.0"

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="QuackBox", description="Your inbox, quacked open — email intelligence platform", version=APP_VERSION, lifespan=lifespan)
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

@app.get("/")
async def root():
    return {"app": "QuackBox", "version": APP_VERSION, "docs": "/docs"}

@app.get("/api/stats")
async def stats():
    s = get_stats()
    s["version"] = APP_VERSION
    return s
PYEOF

# ============================================================
# 2. BACKEND: config.py — rename DB
# ============================================================
sed -i '' 's/mbox_explorer\.db/quackbox.db/g' backend/app/config.py

# ============================================================
# 3. BACKEND: export footer
# ============================================================
sed -i '' 's/Exported from Mbox Explorer/Exported from QuackBox/g' backend/app/routers/export.py

# Backend: run.py + __init__.py
sed -i '' 's/Mbox Explorer/QuackBox/g' backend/run.py backend/app/__init__.py

# ============================================================
# 4. FRONTEND: index.html
# ============================================================
cat > frontend/index.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>QuackBox</title>
  </head>
  <body class="bg-gray-50 text-gray-900">
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
HTMLEOF

# ============================================================
# 5. FRONTEND: package.json
# ============================================================
sed -i '' 's/"mbox-explorer-frontend"/"quackbox-frontend"/g' frontend/package.json

# ============================================================
# 6. FRONTEND: App.jsx — rebrand header
# ============================================================
python3 << 'PYEOF'
with open('frontend/src/App.jsx', 'r') as f:
    c = f.read()

# Replace title and short title
c = c.replace("Mbox Explorer", "QuackBox")
c = c.replace(">MBX<", ">QBX<")

# Replace localStorage keys
c = c.replace("mbox-theme", "quackbox-theme")

with open('frontend/src/App.jsx', 'w') as f:
    f.write(c)
print("✓ App.jsx rebranded")
PYEOF

# ============================================================
# 7. FRONTEND: SetupWizard — rebrand welcome
# ============================================================
sed -i '' 's/Welcome to Mbox Explorer/Welcome to QuackBox 🦆/g' frontend/src/components/SetupWizard.jsx

# ============================================================
# 8. FRONTEND: SearchBar localStorage keys
# ============================================================
sed -i '' 's/mbox-saved-searches/quackbox-saved-searches/g' frontend/src/components/SearchBar.jsx

# ============================================================
# 9. docker-compose.yml — rebrand
# ============================================================
cat > docker-compose.yml << 'YMLEOF'
# QuackBox — Docker Compose
# Your inbox, quacked open.
#
# Usage:
#   1. Place .mbox files in the data/ directory
#   2. Make sure Ollama is running on the host: ollama serve
#   3. Pull the embedding model: ollama pull nomic-embed-text
#   4. Run: docker compose up --build
#   5. Open http://localhost:5173

services:
  backend:
    build:
      context: ./backend
    container_name: quackbox-backend
    ports:
      - "8000:8000"
    volumes:
      - ./backend/app:/app/app
      - ./data:/app/data
      - db-data:/app/db
    environment:
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
      - DATA_DIR=/app/data
      - DB_DIR=/app/db
    extra_hosts:
      - "host.docker.internal:host-gateway"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/')"]
      interval: 10s
      timeout: 5s
      retries: 3

  frontend:
    build:
      context: ./frontend
    container_name: quackbox-frontend
    ports:
      - "5173:5173"
    volumes:
      - ./frontend/src:/app/src
      - ./frontend/index.html:/app/index.html
    environment:
      - API_URL=http://quackbox-backend:8000
    depends_on:
      backend:
        condition: service_healthy

volumes:
  db-data:
YMLEOF

# ============================================================
# 10. .gitignore
# ============================================================
echo "📝 Creating .gitignore..."
cat > .gitignore << 'GITEOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.venv/
venv/
env/
*.egg-info/
dist/
build/

# Node
node_modules/
frontend/node_modules/
frontend/dist/

# Database
*.db
*.db-journal
*.db-wal
*.db-shm

# Data (email archives — don't commit personal data!)
data/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Docker
db-data/

# Logs
*.log

# Environment
.env
.env.local
GITEOF

# ============================================================
# 11. README.md
# ============================================================
echo "📝 Creating README.md..."
cat > README.md << 'MDEOF'
# 🦆 QuackBox

**Your inbox, quacked open.**

QuackBox is an email intelligence platform that transforms your email archive into a searchable, analyzable knowledge base. Built for power users who want to explore decades of email history with modern tools.

## Features

- **📊 Dashboard** — Volume trends, top contacts, activity heatmaps, communication network treemap
- **📧 Email Browser** — Search, filter, paginate through your entire archive with keyword and AI-powered semantic search
- **🔍 Advanced Search** — Boolean operators (AND/OR/NOT), date ranges, sender filters, mailbox selection, attachment filtering, tag/bookmark filters with bulk actions
- **📅 Calendar** — Monthly heat-mapped grid showing email density by day
- **📜 Timeline** — Visual timeline of key milestones: first emails, busiest days, volume surges, contact firsts, biggest threads
- **🧵 Threads** — Reconstructed email threads with AI summarization
- **👥 Contacts** — Directory with relationship scoring, sentiment analysis, duplicate merge detection
- **📁 Mailboxes** — Browse by source mailbox
- **📎 Files** — Searchable attachment index with type-coded icons
- **🏷️ Topics** — AI-powered topic clustering with embeddings
- **💬 Chat** — RAG-powered Q&A against your entire archive
- **⭐ Bookmarks & Tags** — Star emails, create color-coded tags, bulk operations
- **🌙 Dark Mode** — Full dark theme
- **⌨️ Keyboard Shortcuts** — Vim-style navigation (g+d, g+e, g+t, etc.)
- **🧙 Setup Wizard** — First-run auto-detection and one-click import with live progress

## Quick Start

### Prerequisites

- Docker & Docker Compose
- [Ollama](https://ollama.ai) (for AI features — optional but recommended)

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/quackbox.git
cd quackbox

# 2. Add your email data
# Place .mbox files, Apple Mail exports, or .emlx directories in data/
mkdir -p data
cp ~/path/to/your/archive.mbox data/

# 3. (Optional) Start Ollama for AI features
ollama serve &
ollama pull nomic-embed-text

# 4. Launch
docker compose up --build

# 5. Open http://localhost:5173
# The setup wizard will detect your data and guide you through import.
```

### Supported Formats

| Format | Source |
|--------|--------|
| `.mbox` | Gmail Takeout, Thunderbird, most email clients |
| `.emlx` | Apple Mail (V10 mailbox directories) |
| Apple Mail `.mbox` bundles | Apple Mail export |

## Architecture

```
quackbox/
├── backend/          # Python/FastAPI
│   ├── app/
│   │   ├── routers/  # API endpoints
│   │   ├── services/ # Business logic
│   │   └── database.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/         # React/Vite
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   └── api/
│   ├── Dockerfile
│   └── package.json
├── data/             # Your email files (gitignored)
└── docker-compose.yml
```

**Stack:** Python 3.12 · FastAPI · SQLite FTS5 · React 18 · Vite · Tailwind CSS · Recharts · Ollama

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `/` | Focus search |
| `Esc` | Close/back |
| `?` | Show shortcuts |
| `g d` | Dashboard |
| `g e` | Emails |
| `g t` | Threads |
| `g c` | Contacts |
| `g s` | Advanced Search |
| `g l` | Timeline |
| `g p` | Topics |
| `g h` | Chat |
| `g m` | Mailboxes |

## License

MIT

---

*Built by Duck 🦆 at Gangway Digital*
MDEOF

# ============================================================
# 12. Initialize git
# ============================================================
echo "📝 Initializing git..."
git init
git config user.email "duck@gangwaydigital.com"
git config user.name "Duck"
git add -A
git commit -m "🦆 QuackBox v3.1.0 — initial commit

Email intelligence platform: 52K+ email archive explorer
Features: dashboard, search, threads, contacts, timeline, 
calendar, attachments, topics, chat, bookmarks, tags, 
dark mode, keyboard shortcuts, setup wizard.

Stack: Python/FastAPI + React/Vite + SQLite FTS5 + Ollama"

echo ""
echo "✅ QuackBox rebrand complete!"
echo ""
echo "  🦆 All references updated: Mbox Explorer → QuackBox"
echo "  📁 .gitignore created (ignores data/, *.db, node_modules, etc.)"
echo "  📖 README.md with full feature list, setup guide, architecture"
echo "  🎬 Git initialized with initial commit"
echo ""
echo "  Next steps:"
echo "    docker compose down"
echo "    docker compose up --build   (rebuilds with new container names)"
echo ""
echo "  To push to GitHub:"
echo "    git remote add origin https://github.com/yourusername/quackbox.git"
echo "    git push -u origin main"
