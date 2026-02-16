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
