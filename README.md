# 🦆 QuackBox

**Your inbox, quacked open.**

QuackBox is a self-hosted email intelligence platform that transforms `.mbox` and Apple Mail archives into a searchable, analyzable knowledge base. Explore decades of email with AI-powered search, conversation threading, contact profiling, and interactive visualizations — all running locally in Docker.

![Version](https://img.shields.io/badge/version-4.1.1-blue) ![Stack](https://img.shields.io/badge/stack-Python%20%7C%20React%20%7C%20SQLite-green) ![License](https://img.shields.io/badge/license-MIT-gray)

---

## Features

### Core
- **Dashboard** — Gradient hero stat cards, volume chart with month-over-month trend indicators, insight strips (peak month, year totals), top contacts with relative volume bars and sparklines, activity heatmap with peak detection, year-by-year breakdown, thread insights, quick navigation actions
- **Email Browser** — Full-text search (FTS5), filter by sender/date/mailbox/attachments, pagination, sort controls
- **Advanced Search** — Boolean operators (AND / OR / NOT), "quoted phrases", prefix matching, date range pickers, FTS5-powered with BM25 relevance ranking and highlighted snippets
- **Instant Search Preview** — Typeahead dropdown shows top results as you type with highlighted context, keyboard navigation (↑↓ Enter), and search history
- **Calendar** — Monthly heat-mapped grid with day drilldown showing email density
- **Timeline** — Scrollable milestone view: first/last emails, busiest days, volume surges, first contact from top senders, biggest threads, email count milestones (#1K, #5K, #10K…)

### AI-Powered
- **Chat** — RAG-powered Q&A against your entire archive with source citations
- **Topics** — Embedding-based topic clustering that auto-discovers themes across your emails
- **Summarization** — One-click AI summaries for individual emails and full threads with action items and key points
- **Semantic Search** — "Smart" search mode that understands meaning, not just keywords
- **Similar Emails** — Find related messages using embedding similarity

### Organization
- **Threads** — Reconstructed email conversations from References/In-Reply-To headers with participant tracking, expandable tree view with color-coded avatars
- **Contacts** — Directory with relationship scoring, communication frequency sparklines, and duplicate merge detection
- **Sentiment Analysis** — Contact-level sentiment trends across your archive
- **Bookmarks & Tags** — Star emails, create color-coded tags, bulk operations from search results
- **Mailboxes** — Browse by source mailbox with per-source statistics
- **Attachments** — Searchable file index with type-coded icons, extension filters, sort controls, and one-click download from original mbox/emlx source files

### Interface
- **Sidebar Navigation** — Collapsible left sidebar, persistent state, notification badges for unconfigured features
- **Dark Mode** — Full dark theme toggle
- **Keyboard Shortcuts** — Vim-style navigation (`g d`, `g e`, `g t`, `g c`, etc.)
- **Setup Wizard** — First-run auto-detection with live import progress bar showing per-source counts and elapsed time
- **Export** — CSV export for emails, contacts, and threads; printable HTML thread export; single-email .eml export; attachment binary download from original source files
- **Configurable Data Path** — Point `DATA_PATH` to any directory via `.env` instead of copying files

### v4.1.0 New Features
- **Thread List View** — Thread summary cards with expandable email trees in chronological order
- **Thread Tree Visualization** — Full tree diagram showing reply hierarchy with sender avatars and color coding
- **Thread Summary Cards** — Message count, participant count, and duration displayed in thread cards
- **Email Table Thread Indicators** — Thread badge and reply count indicator on individual emails

### Performance
- **Batch Dashboard API** — Single endpoint loads all dashboard data in one request instead of 6
- **Write-Through Caching** — Analytics auto-cache on first compute with 1-hour TTL; no manual "Compute" step needed
- **Auto Cache Warming** — Analytics cache pre-populates after email import completes
- **Client-Side SWR** — Dashboard shows cached data instantly on revisit while refreshing in the background
- **Optimized Queries** — Batch sparkline loading (N+1 → 2 queries), index-friendly calendar date ranges
- **BM25 Ranked Search** — Column-weighted relevance scoring (subject 10×, sender 5×, body 1×) for better search results
- **FTS5 Everywhere** — Advanced Search uses FTS5 instead of slow LIKE queries; instant search skips COUNT for speed
- **Batch Semantic Lookups** — Similar/semantic search fetches all results in one query instead of N individual lookups

---

## Quick Start

### Prerequisites

- **Docker** & **Docker Compose**
- **Ollama** (optional — for AI features like chat, topics, summarization, semantic search)

### 1. Clone & point to your data

```bash
git clone https://github.com/YOUR_USERNAME/quackbox.git
cd quackbox
```

**Option A** — Use the default `data/` directory:

```bash
mkdir -p data
cp ~/path/to/All\ mail.mbox data/
cp -r ~/Library/Mail/V10 data/     # Apple Mail
```

**Option B** — Point to an existing mail directory:

```bash
echo "DATA_PATH=/Users/you/Library/Mail/V10" > .env
```

Any path works — external drives, Google Takeout folders, Thunderbird profiles, etc. See `.env.example` for more examples.

### 2. (Optional) Start Ollama

```bash
ollama serve &
ollama pull nomic-embed-text    # for semantic search & topics
ollama pull llama3.1:8b          # for chat & summarization
```

### 3. Launch

```bash
docker compose up --build
```

Open **http://localhost:5173** — the setup wizard will detect your data and guide you through import.

### Supported Formats

| Format | Source | Notes |
|--------|--------|-------|
| `.mbox` | Gmail Takeout, Thunderbird, most clients | Standard mbox format |
| `.emlx` | Apple Mail | V10 mailbox directories with `.emlx` files |
| Apple Mail `.mbox` bundles | Apple Mail export | Nested folder structure with `mbox` files |

---

## AI Configuration

QuackBox supports separate endpoints for chat and embedding, each configurable as either **Ollama** (default) or any **OpenAI-compatible** API.

Edit `docker-compose.yml` environment variables:

### Chat LLM (Q&A, summarization)

| Variable | Default | Description |
|----------|---------|-------------|
| `CHAT_API_URL` | `http://host.docker.internal:11434` | API base URL |
| `CHAT_API_KEY` | *(empty)* | API key (blank for Ollama) |
| `CHAT_MODEL` | `llama3.1:8b` | Model name |
| `CHAT_API_TYPE` | `ollama` | `ollama` or `openai` |

### Embedding LLM (semantic search, topics)

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBED_API_URL` | `http://host.docker.internal:11434` | API base URL |
| `EMBED_API_KEY` | *(empty)* | API key (blank for Ollama) |
| `EMBED_MODEL` | `nomic-embed-text` | Model name |
| `EMBED_API_TYPE` | `ollama` | `ollama` or `openai` |
| `EMBEDDING_DIMENSIONS` | `768` | Vector size (match your model) |

### Example: OpenAI chat + local Ollama embeddings

```yaml
environment:
  - CHAT_API_URL=https://api.openai.com
  - CHAT_API_KEY=sk-your-key-here
  - CHAT_MODEL=gpt-4o-mini
  - CHAT_API_TYPE=openai
  - EMBED_API_URL=http://host.docker.internal:11434
  - EMBED_MODEL=nomic-embed-text
  - EMBED_API_TYPE=ollama
```

Works with any OpenAI-compatible API: **OpenAI**, **vLLM**, **LiteLLM**, **Ollama**, **LocalAI**, **llama.cpp server**, etc.

---

## Architecture

```
quackbox/
├── backend/               # Python 3.12 / FastAPI
│   ├── app/
│   │   ├── routers/       # API endpoints (12 modules)
│   │   │   ├── emails.py        # Search, filter, advanced search
│   │   │   ├── threads.py       # Thread reconstruction & summarization
│   │   │   ├── contacts.py      # Contact profiles, merge, sentiment
│   │   │   ├── analytics.py     # Dashboard data, timeline, badges
│   │   │   ├── chat.py          # RAG chat interface
│   │   │   ├── topics.py        # Embedding & clustering
│   │   │   ├── bookmarks.py     # Stars & tags
│   │   │   ├── attachments.py   # File index
│   │   │   ├── ingest.py        # Data import with progress
│   │   │   ├── export.py        # CSV & HTML export
│   │   │   └── settings.py      # AI config endpoint
│   │   ├── services/      # Business logic
│   │   ├── database.py    # SQLite + FTS5
│   │   └── config.py      # Environment-based config
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/              # React 18 / Vite
│   ├── src/
│   │   ├── components/    # 21 React components
│   │   ├── hooks/         # Keyboard shortcuts
│   │   └── api/           # API client
│   ├── Dockerfile
│   └── package.json
├── data/                  # Your email files (gitignored)
├── docker-compose.yml
└── .gitignore
```

**Stack:** Python 3.12 · FastAPI · SQLite FTS5 · React 18 · Vite · Tailwind CSS · Recharts · Lucide Icons

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `/` | Focus search |
| `Esc` | Close / go back |
| `?` | Show all shortcuts |
| `g d` | Dashboard |
| `g e` | Emails |
| `g s` | Advanced Search |
| `g t` | Threads |
| `g c` | Contacts |
| `g l` | Timeline |
| `g p` | Topics |
| `g h` | Chat |
| `g m` | Mailboxes |

---

## API

The backend exposes a full REST API at `http://localhost:8000`. Interactive docs at `/docs` (Swagger) or `/redoc`.

Key endpoints:

```
GET  /api/stats                    # Archive overview
GET  /api/emails                   # List/filter emails
GET  /api/emails/advanced-search   # Boolean search with combined filters
GET  /api/emails/{id}              # Full email detail
POST /api/chat                     # RAG Q&A
GET  /api/threads                  # List threads
GET  /api/contacts                 # Contact directory
GET  /api/analytics/timeline       # Milestone timeline
GET  /api/analytics/badges         # Notification badge counts
GET  /api/bookmarks/tags           # List tags
GET  /api/attachments              # File index
GET  /api/settings                 # Current AI configuration
GET  /api/export/email/{id}/eml    # Download email as .eml
GET  /api/export/email/{id}/attachments  # List extractable attachments
GET  /api/export/email/{id}/attachment/{name}  # Download attachment binary
GET  /api/export/thread/{id}/html  # Printable thread export
```

---

## Development

```bash
# Backend only (hot-reload via volume mount)
docker compose up backend

# Frontend only (Vite HMR)
cd frontend && npm run dev

# View logs
docker compose logs -f backend
```

The database persists in a Docker volume (`db-data`). Email data lives in `data/` which is gitignored.

---

## License

MIT

---

*Built by Duck at [Gangway Digital](https://gangwaydigital.com)* 🦆
