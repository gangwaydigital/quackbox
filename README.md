# 🦆 QuackBox

**Your inbox, quacked open.**

QuackBox is a self-hosted email intelligence platform that transforms `.mbox` and Apple Mail archives into a searchable, analyzable knowledge base. Explore decades of email with AI-powered search, conversation threading, contact profiling, and interactive visualizations — all running locally in Docker.

![Version](https://img.shields.io/badge/version-4.6.0-blue) ![Stack](https://img.shields.io/badge/stack-Python%20%7C%20React%20%7C%20SQLite-green) ![License](https://img.shields.io/badge/license-MIT-gray)

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
- **Dark Mode** — Full dark theme toggle, theme-aware across every view (Dashboard, Contacts, Threads, Mailboxes, email reader, Calendar, Timeline, Topics, Chat, Sentiment, Saved Searches, Setup Wizard, Filter Panel, Deduplication, Search) including all charts: recharts axes, tooltips, gridlines, and the activity heatmap palette adapt to light/dark
- **Keyboard Shortcuts** — Vim-style navigation (`g d`, `g e`, `g t`, `g c`, etc.)
- **Setup Wizard** — First-run auto-detection with live import progress bar showing per-source counts and elapsed time
- **Friendly Error Messages** — API failures surface user-readable messages for network failures and bare HTTP statuses, but pass through informative server details (e.g. "Attachment not found — original mbox/emlx source must be accessible") so users see actionable explanations
- **Empty States** — Icon-led, helpful empty states across Contacts, Threads, Mailboxes, and the email reader (search vs. no-data hints)
- **Inline UX Explainers** — First-visit hints explain non-obvious behavior (e.g. why `smime.p7s` files don't appear in the attachment list)
- **Accessible Modals** — Attachment preview modal traps focus, closes on Escape, restores focus on close, locks background scroll, and is announced with `role="dialog"` + `aria-labelledby`
- **Export** — CSV export for emails, contacts, and threads; printable HTML thread export; single-email .eml export; attachment binary download from original source files
- **Configurable Data Path** — Point `DATA_PATH` to any directory via `.env` instead of copying files
- **Auto Re-Import (Watcher)** — Set `WATCH_INTERVAL_MINUTES=15` in `.env` to have the backend periodically scan `DATA_PATH` and incrementally ingest any new email content. Status panel + "Scan now" button on the Mailboxes page (no more `.env`-only). Endpoint at `/api/ingest/watcher`
- **Events** — Meeting invites + `.ics` attachments extracted into a searchable timeline view, with organizer / attendees / location / status / time-range / link back to the source email
- **Bulk Attachment Zip** — Download up to 500 attachments matching any filter (search, sender, mailbox) as a single archive grouped into `YYYY-MM/` folders

### v4.6.0 What's New
- **Apple Mail attachments finally visible** — V10 archives store attachment binaries in sibling `Attachments/<numeric_id>/<part>/` directories independently of the `.emlx` files, and many don't link cleanly to any single email. A real archive went from 24 attachments shown → **13,374** after this release. Two complementary paths: a sibling-dir match for the cases that DO link (augments the email row's `attachment_names`), and a filesystem walk that indexes every file under `*/Attachments/` regardless. Both run in a single backfill job, ~25s for a 50k-message archive
- **New "On Disk" attachments tab** — search by filename, filter by mailbox (INBOX, Sent Messages, named sub-folders), download straight from disk. Path safety check ensures the file is under a configured `/host` root
- **Diagnostic banner** on the Attachments page explains the Apple Mail issue and offers a one-click "Scan now" trigger for the backfill (idempotent — already-indexed files skipped, not duplicated)
- **CLAUDE.md-driven cleanup** — dropped ~300 lines of dead code (unused `OnboardingTip`, redundant `NetworkGraph` treemap, orphan `/api/topics/embed` endpoint, `SUPPORTED_EXTENSIONS` config). Split `ImportStatus.jsx` (466 → 240 lines) into focused `WatcherPanel.jsx` + `IngestProgressPanel.jsx` siblings
- **Vite host allowlist** — set to `true` so the app works behind reverse proxies, `.local` mDNS hostnames, and LAN aliases like `ai` without blocking with "Blocked request" errors
- **Tests:** 179 → 206 passing in ~2.7s

### v4.5.0 What's New
- **In-app folder picker** — first-run setup wizard and the Mailboxes page now have a real directory browser for selecting mailbox sources, replacing the "edit `.env` and restart" flow. Each folder is shown with email-artifact badges (mbox / emlx counts, Apple-Mail-bundle detection) so you know what you're picking. The container reads `/Users` and `/Volumes` read-only via new `/host` mounts; path-traversal attempts are rejected before they touch the filesystem
- **Multi-folder ingestion** — registered folders are persisted in a new `ingest_folders` table and scanned on every import alongside the legacy `DATA_PATH`. The watcher and attachment extractor read from all of them too. Folders that become unreachable (drive unplugged) are skipped with a warning, not a crash
- **Embedding model picker** — Topics page header surfaces the active model and lists installed alternatives + curated suggestions. README documents the speed/quality tradeoffs (`all-minilm` runs ~5× faster than the default `nomic-embed-text` at slightly lower quality)
- **Embedding ETA + throughput** — clustering progress now shows live rate (`12.4/s`) and remaining time estimate (`~14m left`) using a rolling 30-second window
- **Tests:** 174 → 198 passing in ~2.3s

### v4.4.0 What's New
- **Events** — new sidebar entry that surfaces every meeting invite + `.ics` attachment hiding in your archive. Organizer, attendees, location, status, time range, and a link back to the source email. Backed by the `icalendar` library so timezones and recurrences parse properly. Run "Index events" once to scan all your imported emails
- **Bulk attachment archive** — "Zip N" button on the Attachments page downloads up to 500 attachments matching the current filter as a single zip, grouped into `YYYY-MM/` folders inside the archive with collision-safe naming
- **Topic clustering UX** — fixed a `NameError` that crashed every clustering run, added live progress polling with embedding count + percentage, a Cancel button so a 30-90 minute run can be aborted (already-completed embeddings stay persisted), and resume-on-mount if a job is in flight
- **Watcher status panel** — the background auto-import watcher is no longer `.env`-only. Mailboxes page shows enabled/interval/last check/runs count, plus a "Scan now" button to bypass the next tick
- **Reproducible installs** — `frontend/package-lock.json` now committed

### v4.3.0 What's New
- **Background watcher** — when `WATCH_INTERVAL_MINUTES` is set, the backend periodically scans `DATA_PATH` and runs an incremental ingest whenever new mail arrives. No-op when the disk is unchanged. Optional `WATCH_ON_STARTUP=true` triggers an immediate scan on boot. Status visible at `/api/ingest/watcher`
- **66% smaller initial JS bundle** — route components now lazy-load via `React.lazy()`, and recharts ships in its own chunk that downloads only on chart-bearing pages. Initial gzipped JS dropped from ~215 kB to ~72 kB; each route is its own ~5–15 kB chunk
- **Dark mode parity** — every view (Dashboard, Threads, Calendar, Timeline, Chat, Sentiment, Topics, Saved Searches, Setup Wizard, Filter Panel, Deduplication, Search, Mailboxes, Contacts, email reader) now renders correctly in dark mode. Charts (axes, tooltips, gridlines, the activity heatmap palette) are theme-aware via a shared `useChartTheme` hook
- **Refactored ingest runner** — the ingest worker + status are now in `app/services/ingest_runner.py`, shared between the manual `/api/ingest/start` endpoint and the watcher
- **Expanded test coverage** — pytest suite went from 65 → 106 tests (~1s runtime) covering FTS5 search ranking + sanitization, attachment extraction, the .emlx migration, and the watcher lifecycle

### v4.2.0 What's New
- **Apple Mail (.emlx) attachments now download correctly** — earlier builds stored the full `.emlx` file (byte-count prefix + plist trailer) as the raw message, breaking attachment extraction and `.eml` export for every signed/multipart email. Fixed with a one-time idempotent startup migration that repairs existing rows
- **S/MIME signature noise hidden** — `smime.p7s` / `smime.p7m` parts no longer pollute attachment listings or counts
- **`DATA_PATH` actually works** — `.env` overrides the data bind-mount; `DATA_MOUNT_MODE=ro` makes it read-only. New `.env.example` ships with the project
- **Atomic thread rebuild** — single transaction with batched updates; mid-rebuild crash rolls back cleanly
- **Accessible attachment preview modal** — focus trap, Escape closes, focus restored on close, proper ARIA roles
- **Friendlier API errors** — network failures and bare statuses get user-readable messages, but informative server detail still passes through
- **Polish** — dark-mode variants and icon-led empty states across Contacts and Threads

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
- **SQL-Side Attachment Listing** — Attachment browser uses SQLite `json_each` to filter, sort, and paginate inside the database rather than loading every attachment-bearing email into memory
- **Code-Split Frontend Bundle** — Route components are lazy-loaded with `React.lazy()`; recharts ships in its own chunk that downloads only on chart-bearing pages. Initial JS dropped from ~215 kB gzipped to ~72 kB (66% smaller), with each route on its own ~5–15 kB chunk

### Reliability
- **Diagnostic Parse Failures** — Mbox parser logs `Message-ID`, subject, file source, byte offset, and stack on parse errors instead of swallowing them as a one-line warning
- **Validated Contact Merges** — Merging contacts now verifies every secondary address exists before any UPDATE, so an unknown address fails loudly instead of silently merging zero records (and returns a proper `404` when an address is missing, `400` when nothing was supplied)
- **Audited JSON Skips** — Email rows whose `attachment_names` JSON is malformed are surfaced in the logs (with a sample of offending email IDs) rather than dropped silently
- **Atomic Thread Rebuild** — Reconstructing threads now runs in a single transaction with batched `UPDATE`s; a mid-rebuild crash rolls back cleanly instead of leaving you with empty `threads` and nulled `thread_group_id`s
- **Correct .emlx Storage** — Apple Mail `.emlx` files are stored as `<byte-count>\n<RFC822 message>\n<plist trailer>`. The parser now stores only the RFC822 portion as `raw_message`, and a one-time startup migration repairs any existing rows that contain the byte-count prefix or plist trailer — fixing attachment downloads and `.eml` exports for signed and multipart emails imported from `.emlx` archives
- **S/MIME Noise Filtered** — `smime.p7s` and `smime.p7m` cryptographic signature parts are excluded from attachment listings, counts, and extraction. They're protocol metadata, not user content

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

**Option B** — Point to an existing mail directory (no copy required):

```bash
cp .env.example .env
# then edit .env and set DATA_PATH to your archive
```

Or one-liner:

```bash
echo "DATA_PATH=/Users/you/Library/Mail/V10" > .env
```

Any path works — external drives, Google Takeout folders, Thunderbird profiles, etc. For backup directories you never want QuackBox to write to, also set `DATA_MOUNT_MODE=ro` in `.env` for a read-only bind mount.

**Option C** — Pick folders from inside the app:

The setup wizard (first run with no email data) and the Mailboxes page both have a folder picker that browses your filesystem. Folders you add this way persist and are scanned on every import. The container needs read access to the host paths you want to browse — by default `/Users` and `/Volumes` are mounted read-only inside the container; edit `docker-compose.yml` if you want to expose more or restrict that access.

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

#### Choosing an embedding model

The Topics page shows the active model + a picker; this is the same data:

| Model | Size | Dim | Speed | Notes |
|-------|------|-----|-------|-------|
| `nomic-embed-text` (default) | 274 MB | 768 | moderate | Solid quality, balanced |
| `all-minilm` | 46 MB | 384 | ~5× faster | Good for large archives where speed matters |
| `mxbai-embed-large` | 670 MB | 1024 | slower | Higher quality |
| `snowflake-arctic-embed` | 335 MB | 1024 | moderate | Strong English benchmarks |
| `text-embedding-3-small` (OpenAI) | hosted | 1536 | very fast | Cheap, hosted, requires API key |
| `text-embedding-3-large` (OpenAI) | hosted | 3072 | fast | Highest quality |

To switch:
1. (Ollama only) `ollama pull <model-name>`
2. Edit `EMBED_MODEL` in `.env` (and `EMBEDDING_DIMENSIONS` to match)
3. `docker compose up -d backend`
4. Re-run clustering on the Topics page — old embeddings from a different model aren't interchangeable

For a 50k-email archive on local Ollama, `nomic-embed-text` typically takes 60–90 minutes; `all-minilm` runs the same archive in roughly 15–25 minutes; `text-embedding-3-small` over the OpenAI API finishes in a few minutes (you pay ~$0.50 for 50k emails at current pricing).

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

A `Makefile` wraps the common flows:

```bash
make help        # list available targets
make rebuild     # docker compose up --build
make logs        # tail backend logs
make test        # run the backend test suite
make test-cov    # tests + coverage report
```

Or use `docker compose` directly:

```bash
# Backend only (hot-reload via volume mount)
docker compose up backend

# Frontend only (Vite HMR)
cd frontend && npm run dev

# View logs
docker compose logs -f backend
```

The database persists in a Docker volume (`db-data`). Email data lives in `data/` (or wherever `DATA_PATH` points) and is gitignored.

### Tests

`backend/tests/` contains pytest coverage of the parsers (mbox + emlx), email utilities, the .emlx raw-message migration, contact merge, FTS5 search (sanitization, ranking, snippets, instant search, filters), the attachment extractor (real attachments, smime filtering, .eml export sanitization), and the background watcher (lifecycle + tick behavior). Run with `make test`.

The suite is intentionally fast (~1s for 100+ tests) and uses synthetic mbox/emlx fixtures built in-memory; no real email data is required.

---

## License

MIT

---

*Built by Duck at [Gangway Digital](https://gangwaydigital.com)* 🦆
