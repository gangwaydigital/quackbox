"""Database setup and connection management."""
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from app.config import DB_PATH
from app.logging_config import get_logger

log = get_logger("database")

# .emlx files start with `<byte_count>\n` (Apple Mail pads with trailing spaces).
# An early version of emlx_parser stored the full .emlx contents as raw_message
# instead of just the RFC822 portion. This pattern detects those broken rows so
# we can repair them in place.
_EMLX_PREFIX = re.compile(rb"^(\d{1,12})[ \t]*\n")

def get_connection(db_path: Path = DB_PATH):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

@contextmanager
def get_db(db_path: Path = DB_PATH):
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db(db_path: Path = DB_PATH):
    with get_db(db_path) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT, message_id TEXT UNIQUE, subject TEXT,
            sender_name TEXT, sender_email TEXT, recipients TEXT, date_sent TEXT,
            date_timestamp REAL, body_text TEXT, body_html TEXT, headers TEXT,
            mbox_source TEXT, thread_id TEXT, has_attachments BOOLEAN DEFAULT 0,
            attachment_names TEXT, raw_message BLOB, source_path TEXT,
            created_at TEXT DEFAULT (datetime('now')))""")

        # Migration: add raw_message to pre-existing databases that don't have it.
        # Safe to run after CREATE TABLE — only ALTERs if the column is missing.
        existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(emails)").fetchall()}
        if "raw_message" not in existing_columns:
            log.info("Adding raw_message column to emails table...")
            conn.execute("ALTER TABLE emails ADD COLUMN raw_message BLOB")
        if "source_path" not in existing_columns:
            log.info("Adding source_path column to emails table...")
            conn.execute("ALTER TABLE emails ADD COLUMN source_path TEXT")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_sender_email ON emails(sender_email)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_date_timestamp ON emails(date_timestamp DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_date_sent ON emails(date_sent)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_thread_id ON emails(thread_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mbox_source ON emails(mbox_source)")
        conn.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS emails_fts USING fts5(
            subject, sender_name, sender_email, body_text,
            content='emails', content_rowid='id', tokenize='porter unicode61')""")
        conn.execute("""CREATE TRIGGER IF NOT EXISTS emails_ai AFTER INSERT ON emails BEGIN
            INSERT INTO emails_fts(rowid, subject, sender_name, sender_email, body_text)
            VALUES (new.id, new.subject, new.sender_name, new.sender_email, new.body_text); END""")
        conn.execute("""CREATE TRIGGER IF NOT EXISTS emails_ad AFTER DELETE ON emails BEGIN
            INSERT INTO emails_fts(emails_fts, rowid, subject, sender_name, sender_email, body_text)
            VALUES ('delete', old.id, old.subject, old.sender_name, old.sender_email, old.body_text); END""")
        conn.execute("""CREATE TRIGGER IF NOT EXISTS emails_au AFTER UPDATE ON emails BEGIN
            INSERT INTO emails_fts(emails_fts, rowid, subject, sender_name, sender_email, body_text)
            VALUES ('delete', old.id, old.subject, old.sender_name, old.sender_email, old.body_text);
            INSERT INTO emails_fts(rowid, subject, sender_name, sender_email, body_text)
            VALUES (new.id, new.subject, new.sender_name, new.sender_email, new.body_text); END""")
        conn.execute("""CREATE TABLE IF NOT EXISTS embeddings (
            email_id INTEGER PRIMARY KEY REFERENCES emails(id) ON DELETE CASCADE,
            embedding BLOB, model TEXT, created_at TEXT DEFAULT (datetime('now')))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, description TEXT,
            keywords TEXT, email_count INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now')))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS email_topics (
            email_id INTEGER REFERENCES emails(id) ON DELETE CASCADE,
            topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
            confidence REAL, PRIMARY KEY (email_id, topic_id))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS threads (
            id INTEGER PRIMARY KEY AUTOINCREMENT, root_message_id TEXT,
            subject_normalized TEXT, participant_count INTEGER DEFAULT 0,
            message_count INTEGER DEFAULT 0, first_date TEXT, last_date TEXT,
            duration_seconds REAL DEFAULT 0, mailbox_sources TEXT,
            created_at TEXT DEFAULT (datetime('now')))""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_threads_subject ON threads(subject_normalized)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_threads_last_date ON threads(last_date DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_threads_msg_count ON threads(message_count DESC)")
        try:
            conn.execute("ALTER TABLE emails ADD COLUMN thread_group_id INTEGER REFERENCES threads(id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_thread_group ON emails(thread_group_id)")
        except sqlite3.OperationalError:
            pass
        conn.execute("""CREATE TABLE IF NOT EXISTS analytics_cache (
            key TEXT PRIMARY KEY, data TEXT, computed_at TEXT DEFAULT (datetime('now')))""")

        # -- Bookmarks --
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookmarks (
                email_id INTEGER PRIMARY KEY REFERENCES emails(id) ON DELETE CASCADE,
                note TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # -- Tags --
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                color TEXT DEFAULT '#3b82f6',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # -- Email-tag mapping --
        conn.execute("""
            CREATE TABLE IF NOT EXISTS email_tags (
                email_id INTEGER REFERENCES emails(id) ON DELETE CASCADE,
                tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (email_id, tag_id)
            )
        """)

        # -- Attachment full-text content (PDF/DOCX extraction) --
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attachment_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER REFERENCES emails(id) ON DELETE CASCADE,
                filename TEXT NOT NULL,
                content_type TEXT,
                extracted_text TEXT,
                page_count INTEGER DEFAULT 0,
                word_count INTEGER DEFAULT 0,
                extraction_status TEXT DEFAULT 'pending',
                extracted_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_attachment_email ON attachment_content(email_id)")
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS attachment_fts USING fts5(
                filename, extracted_text,
                content='attachment_content', content_rowid='id',
                tokenize='porter unicode61'
            )
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS attachment_content_ai AFTER INSERT ON attachment_content BEGIN
                INSERT INTO attachment_fts(rowid, filename, extracted_text)
                VALUES (new.id, new.filename, new.extracted_text); END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS attachment_content_ad AFTER DELETE ON attachment_content BEGIN
                INSERT INTO attachment_fts(attachment_fts, rowid, filename, extracted_text)
                VALUES ('delete', old.id, old.filename, old.extracted_text); END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS attachment_content_au AFTER UPDATE ON attachment_content BEGIN
                INSERT INTO attachment_fts(attachment_fts, rowid, filename, extracted_text)
                VALUES ('delete', old.id, old.filename, old.extracted_text);
                INSERT INTO attachment_fts(rowid, filename, extracted_text)
                VALUES (new.id, new.filename, new.extracted_text); END
        """)

        # -- Duplicate tracking --
        conn.execute("""
            CREATE TABLE IF NOT EXISTS duplicate_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_email_id INTEGER REFERENCES emails(id) ON DELETE CASCADE,
                duplicate_count INTEGER DEFAULT 0,
                detection_method TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS duplicate_emails (
                group_id INTEGER REFERENCES duplicate_groups(id) ON DELETE CASCADE,
                email_id INTEGER REFERENCES emails(id) ON DELETE CASCADE,
                similarity_score REAL DEFAULT 1.0,
                PRIMARY KEY (group_id, email_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_dup_email ON duplicate_emails(email_id)")

        # -- Incremental ingestion tracking --
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ingest_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT UNIQUE NOT NULL,
                source_type TEXT NOT NULL,
                source_path TEXT,
                file_size INTEGER DEFAULT 0,
                file_mtime REAL DEFAULT 0,
                last_message_offset INTEGER DEFAULT 0,
                emails_total INTEGER DEFAULT 0,
                last_ingest_at TEXT DEFAULT (datetime('now')),
                last_ingest_new INTEGER DEFAULT 0,
                last_ingest_skipped INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ingest_emlx_files (
                path TEXT PRIMARY KEY,
                source_name TEXT NOT NULL,
                ingested_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_emlx_source ON ingest_emlx_files(source_name)")

        # -- Disk-scanned attachments (Apple Mail Attachments/ trees) --
        # Apple Mail stores attachment binaries in per-message Attachments/
        # subdirectories independently of the .emlx files; many archives have
        # tens of thousands that don't map cleanly to any single email row.
        # This table indexes every file found on disk so the UI can surface
        # them directly, even when the linkage to a specific email is lost.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS disk_attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL UNIQUE,
                filename TEXT NOT NULL,
                extension TEXT,
                size INTEGER,
                mailbox_hint TEXT,
                file_mtime REAL,
                indexed_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_disk_attach_filename ON disk_attachments(filename)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_disk_attach_mtime ON disk_attachments(file_mtime DESC)")

        # -- User-registered ingest folders (in addition to legacy DATA_DIR) --
        # host_path is what the user sees ("/Users/duck/Library/Mail/V10");
        # container_path is the same path mapped through the /host bind mount
        # ("/host/Users/duck/Library/Mail/V10"). Storing both lets us show the
        # human-friendly path in UI while ingesting the in-container one.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ingest_folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT NOT NULL,
                host_path TEXT NOT NULL UNIQUE,
                container_path TEXT NOT NULL,
                added_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # -- Calendar events extracted from text/calendar parts and .ics attachments --
        conn.execute("""
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER REFERENCES emails(id) ON DELETE CASCADE,
                uid TEXT,
                summary TEXT,
                description TEXT,
                location TEXT,
                organizer TEXT,
                attendees TEXT,
                start_time TEXT,
                end_time TEXT,
                start_timestamp REAL,
                end_timestamp REAL,
                status TEXT,
                method TEXT,
                source TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(email_id, uid)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_event_start ON calendar_events(start_timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_event_email ON calendar_events(email_id)")

        # -- Saved searches / smart folders --
        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                query TEXT,
                sender TEXT,
                date_from TEXT,
                date_to TEXT,
                has_attachments BOOLEAN DEFAULT 0,
                mbox_source TEXT,
                color TEXT DEFAULT '#3b82f6',
                run_count INTEGER DEFAULT 0,
                last_run_at TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # -- Cases (research workspaces) --
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                issue TEXT NOT NULL,
                date_from TEXT,
                date_to TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                emails TEXT NOT NULL DEFAULT '[]'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_terms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                text TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                replaces_id INTEGER,
                source TEXT NOT NULL DEFAULT 'owner',
                retired INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                term_id INTEGER,
                started_at TEXT,
                finished_at TEXT,
                status TEXT NOT NULL,
                channel_counts TEXT,
                error TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_candidates (
                case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                email_id INTEGER NOT NULL REFERENCES emails(id),
                review TEXT NOT NULL DEFAULT 'unreviewed',
                triage TEXT NOT NULL DEFAULT 'untriaged',
                triage_reason TEXT,
                model_quote TEXT,
                model_quote_ok INTEGER,
                owner_quote TEXT,
                note TEXT,
                semantic_only INTEGER NOT NULL DEFAULT 1,
                out_of_range INTEGER NOT NULL DEFAULT 0,
                partial_text INTEGER NOT NULL DEFAULT 0,
                triage_error TEXT,
                PRIMARY KEY (case_id, email_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_candidate_runs (
                case_id INTEGER NOT NULL,
                email_id INTEGER NOT NULL,
                run_id INTEGER NOT NULL,
                channel TEXT NOT NULL,
                PRIMARY KEY (case_id, email_id, run_id, channel)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_case_cand_review ON case_candidates(case_id, review)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_case_runs_case ON case_runs(case_id)")

        _migrate_emlx_raw_message(conn)

    log.info("Database initialized at %s", db_path)


def _migrate_emlx_raw_message(conn: sqlite3.Connection) -> None:
    """
    Repair raw_message rows that contain the full .emlx file (byte-count line
    + RFC822 message + plist trailer) by trimming back to just the message.
    Idempotent: rows already in the correct shape are skipped because they
    do not start with `<digits>\\n`.
    """
    batch_size = 200
    fixed = 0
    skipped_invalid = 0
    last_id = 0
    while True:
        rows = conn.execute(
            "SELECT id, raw_message FROM emails "
            "WHERE id > ? AND raw_message IS NOT NULL "
            "ORDER BY id LIMIT ?",
            (last_id, batch_size),
        ).fetchall()
        if not rows:
            break
        last_id = rows[-1]["id"]
        updates = []
        for row in rows:
            blob = row["raw_message"]
            if not blob:
                continue
            # 64 bytes comfortably fits a 12-digit byte count plus padding spaces
            head = bytes(blob[:64]) if isinstance(blob, (memoryview, bytes, bytearray)) else b""
            m = _EMLX_PREFIX.match(head)
            if not m:
                continue
            try:
                byte_count = int(m.group(1))
            except ValueError:
                skipped_invalid += 1
                continue
            body_start = m.end()
            full = bytes(blob)
            fixed_bytes = full[body_start: body_start + byte_count]
            if not fixed_bytes:
                skipped_invalid += 1
                continue
            updates.append((fixed_bytes, row["id"]))
        if updates:
            conn.executemany(
                "UPDATE emails SET raw_message = ? WHERE id = ?", updates
            )
            fixed += len(updates)
    if fixed:
        log.info("Repaired raw_message for %d emlx-imported emails", fixed)
    if skipped_invalid:
        log.warning(
            "Skipped %d rows with malformed emlx-style raw_message",
            skipped_invalid,
        )


def get_stats(db_path: Path = DB_PATH):
    with get_db(db_path) as conn:
        stats = {}
        stats["total_emails"] = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
        stats["total_topics"] = conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
        stats["total_embeddings"] = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        stats["total_threads"] = conn.execute("SELECT COUNT(*) FROM threads").fetchone()[0]
        row = conn.execute("SELECT COUNT(DISTINCT sender_email) as senders, COUNT(DISTINCT mbox_source) as sources, MIN(date_sent) as earliest, MAX(date_sent) as latest FROM emails").fetchone()
        stats["unique_senders"] = row["senders"]
        stats["mbox_sources"] = row["sources"]
        stats["date_range"] = {"earliest": row["earliest"], "latest": row["latest"]}
        stats["version"] = "4.6.0"
        return stats
