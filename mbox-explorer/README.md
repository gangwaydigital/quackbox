# 📬 Mbox Explorer

A web-based email archive explorer that indexes `.mbox` files and provides full-text search, filtering, sorting, and AI-powered topic clustering.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  React UI   │────▶│  FastAPI      │────▶│  SQLite     │
│  Dashboard  │◀────│  Backend      │◀────│  + FTS5     │
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │
                    ┌──────▼───────┐
                    │   Ollama      │
                    │  Embeddings   │
                    └──────────────┘
```

## Features

- **Ingest**: Parse `.mbox` files → extract sender, recipients, date, subject, body
- **Search**: Full-text search via SQLite FTS5
- **Filter/Sort**: By sender, date range, subject, topic
- **AI Topics**: Ollama-generated embeddings → automatic topic clustering

## Project Structure

```
mbox-explorer/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application entry point
│   │   ├── config.py            # Application settings
│   │   ├── database.py          # SQLite + FTS5 setup
│   │   ├── models.py            # Pydantic request/response models
│   │   ├── routers/
│   │   │   ├── emails.py        # Email search/filter/sort endpoints
│   │   │   ├── topics.py        # Topic clustering endpoints
│   │   │   └── ingest.py        # Mbox import endpoints
│   │   ├── services/
│   │   │   ├── parser.py        # Mbox file parsing
│   │   │   ├── indexer.py       # SQLite indexing + FTS5 population
│   │   │   ├── search.py        # Search & filter logic
│   │   │   └── clustering.py    # Ollama embeddings + topic detection
│   │   └── utils/
│   │       └── email_utils.py   # Header decoding, date parsing, etc.
│   ├── requirements.txt
│   └── run.py                   # Dev server launcher
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── App.jsx              # Root component with routing
│   │   ├── main.jsx             # Entry point
│   │   ├── components/
│   │   │   ├── EmailTable.jsx   # Sortable email list
│   │   │   ├── SearchBar.jsx    # Full-text search input
│   │   │   ├── FilterPanel.jsx  # Sender, date, topic filters
│   │   │   ├── TopicClusters.jsx# Visual topic groupings
│   │   │   └── EmailDetail.jsx  # Single email view
│   │   ├── api/
│   │   │   └── client.js        # API client for backend
│   │   └── hooks/
│   │       └── useEmails.js     # Data fetching hooks
│   └── public/
│       └── index.html
├── data/                        # Drop .mbox files here
├── docker-compose.yml           # Optional: containerized deployment
└── README.md
```

## Quick Start (Docker — Recommended)

### Prerequisites
- Docker & Docker Compose
- Ollama running on the host (`ollama serve`)

### 1. Pull the embedding model

```bash
ollama pull nomic-embed-text
```

### 2. Add your mbox files

Place your `.mbox` exports from Apple Mail into the `data/` directory:

```bash
cp ~/path/to/your/exports/*.mbox data/
```

### 3. Start everything

```bash
docker compose up --build
```

This starts:
- **Backend** at `http://localhost:8000` (API docs at `/docs`)
- **Frontend** at `http://localhost:5173`

### 4. Ingest your emails

```bash
# Ingest all mbox files in data/ at once
curl -X POST http://localhost:8000/api/ingest/all

# Or ingest a specific file
curl -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{"mbox_path": "my-archive.mbox"}'
```

### 5. Generate topic clusters

```bash
curl -X POST http://localhost:8000/api/topics/cluster
```

Or use the Topics tab in the web UI and click "Run Clustering".

### 6. Explore

Open `http://localhost:5173` — search, filter, browse topics.

---

## Local Development (without Docker)

### Prerequisites
- Python 3.11+
- Node.js 18+
- Ollama running locally

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or: source venv/bin/activate.fish
pip install -r requirements.txt
python run.py
```

Backend runs at `http://localhost:8000` — API docs at `/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`.

### Ingest Mbox Files

1. Place `.mbox` files in the `data/` directory
2. POST to `/api/ingest` or use the UI upload:

```bash
curl -X POST "http://localhost:8000/api/ingest" \
  -H "Content-Type: application/json" \
  -d '{"mbox_path": "../data/my-archive.mbox"}'
```

### Generate Topic Clusters

```bash
curl -X POST "http://localhost:8000/api/topics/cluster"
```

## Development Phases

- [x] **Phase 1**: Mbox parser + SQLite indexer + FastAPI endpoints
- [ ] **Phase 2**: Full-text search + sort/filter + React UI
- [ ] **Phase 3**: Ollama topic detection + clustering view

## Docker Management

```bash
# Start in background
docker compose up -d --build

# View logs
docker compose logs -f backend
docker compose logs -f frontend

# Stop everything
docker compose down

# Stop and remove database volume (full reset)
docker compose down -v

# Rebuild after code changes
docker compose up --build
```

## Troubleshooting

**Ollama not connecting from Docker:**
Make sure Ollama is running on the host. The `host.docker.internal` hostname
allows containers to reach host services. On Linux, the `extra_hosts` mapping
in docker-compose.yml handles this automatically.

**Mbox files not found:**
Files must be in the `data/` directory at the project root. The path you pass
to the ingest API is relative to `data/`, so `my-archive.mbox` means `data/my-archive.mbox`.

## License

MIT
