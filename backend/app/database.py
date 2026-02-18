"""Database setup and connection management."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from app.config import DB_PATH

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
            attachment_names TEXT, created_at TEXT DEFAULT (datetime('now')))""")
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

    print(f"✅ Database initialized at {db_path}")

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
        return stats
