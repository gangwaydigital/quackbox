"""
Database setup and connection management.

Creates SQLite tables for emails, embeddings, and topics,
plus FTS5 virtual table for full-text search.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import DB_PATH


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Get a new database connection with optimized settings."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db(db_path: Path = DB_PATH):
    """Context manager for database connections."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    """Initialize database schema."""
    with get_db(db_path) as conn:
        # -- Core emails table --
        conn.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE,
                subject TEXT,
                sender_name TEXT,
                sender_email TEXT,
                recipients TEXT,          -- JSON array of {name, email, type}
                date_sent TEXT,           -- ISO 8601
                date_timestamp REAL,      -- Unix timestamp for sorting
                body_text TEXT,           -- Plain text body
                body_html TEXT,           -- HTML body (if available)
                headers TEXT,             -- JSON of all headers
                mbox_source TEXT,         -- Which mbox file this came from
                thread_id TEXT,           -- For threading (In-Reply-To / References)
                has_attachments BOOLEAN DEFAULT 0,
                attachment_names TEXT,    -- JSON array of filenames
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # -- Indexes for common queries --
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sender_email ON emails(sender_email)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_date_timestamp ON emails(date_timestamp DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_thread_id ON emails(thread_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mbox_source ON emails(mbox_source)")

        # -- FTS5 virtual table for full-text search --
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS emails_fts USING fts5(
                subject,
                sender_name,
                sender_email,
                body_text,
                content='emails',
                content_rowid='id',
                tokenize='porter unicode61'
            )
        """)

        # -- Triggers to keep FTS in sync --
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS emails_ai AFTER INSERT ON emails BEGIN
                INSERT INTO emails_fts(rowid, subject, sender_name, sender_email, body_text)
                VALUES (new.id, new.subject, new.sender_name, new.sender_email, new.body_text);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS emails_ad AFTER DELETE ON emails BEGIN
                INSERT INTO emails_fts(emails_fts, rowid, subject, sender_name, sender_email, body_text)
                VALUES ('delete', old.id, old.subject, old.sender_name, old.sender_email, old.body_text);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS emails_au AFTER UPDATE ON emails BEGIN
                INSERT INTO emails_fts(emails_fts, rowid, subject, sender_name, sender_email, body_text)
                VALUES ('delete', old.id, old.subject, old.sender_name, old.sender_email, old.body_text);
                INSERT INTO emails_fts(rowid, subject, sender_name, sender_email, body_text)
                VALUES (new.id, new.subject, new.sender_name, new.sender_email, new.body_text);
            END
        """)

        # -- Embeddings table for AI clustering --
        conn.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                email_id INTEGER PRIMARY KEY REFERENCES emails(id) ON DELETE CASCADE,
                embedding BLOB,           -- Stored as numpy bytes
                model TEXT,               -- Which model generated this
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # -- Topics table --
        conn.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT,               -- Human-readable topic name
                description TEXT,         -- AI-generated description
                keywords TEXT,            -- JSON array of top keywords
                email_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # -- Email-to-topic mapping --
        conn.execute("""
            CREATE TABLE IF NOT EXISTS email_topics (
                email_id INTEGER REFERENCES emails(id) ON DELETE CASCADE,
                topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
                confidence REAL,          -- 0.0 to 1.0
                PRIMARY KEY (email_id, topic_id)
            )
        """)

        # -- Thread groups --
        conn.execute("""
            CREATE TABLE IF NOT EXISTS threads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                root_message_id TEXT,
                subject_normalized TEXT,
                participant_count INTEGER DEFAULT 0,
                message_count INTEGER DEFAULT 0,
                first_date TEXT,
                last_date TEXT,
                duration_seconds REAL DEFAULT 0,
                mailbox_sources TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_threads_subject ON threads(subject_normalized)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_threads_last_date ON threads(last_date DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_threads_msg_count ON threads(message_count DESC)")

        # -- Add thread_group_id column to emails if not exists --
        try:
            conn.execute("ALTER TABLE emails ADD COLUMN thread_group_id INTEGER REFERENCES threads(id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_thread_group ON emails(thread_group_id)")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # -- Analytics cache for fast dashboard queries --
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analytics_cache (
                key TEXT PRIMARY KEY,
                data TEXT,              -- JSON payload
                computed_at TEXT DEFAULT (datetime('now'))
            )
        """)

    print(f"✅ Database initialized at {db_path}")


def get_stats(db_path: Path = DB_PATH) -> dict:
    """Get database statistics."""
    with get_db(db_path) as conn:
        stats = {}
        stats["total_emails"] = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
        stats["total_topics"] = conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
        stats["total_embeddings"] = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        stats["total_threads"] = conn.execute("SELECT COUNT(*) FROM threads").fetchone()[0]

        row = conn.execute("""
            SELECT COUNT(DISTINCT sender_email) as senders,
                   COUNT(DISTINCT mbox_source) as sources,
                   MIN(date_sent) as earliest,
                   MAX(date_sent) as latest
            FROM emails
        """).fetchone()
        stats["unique_senders"] = row["senders"]
        stats["mbox_sources"] = row["sources"]
        stats["date_range"] = {"earliest": row["earliest"], "latest": row["latest"]}

        return stats
