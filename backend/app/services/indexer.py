"""
Email indexer service — with incremental ingestion.

Supports both traditional mbox files and Apple Mail .emlx format.

Incremental strategy:
  mbox  — track file size + mtime. Skip entirely if unchanged.
           If the file has grown, seek to the last processed byte
           offset and only parse new content from there.
           Full re-scan if the file appears replaced/truncated.

  emlx  — track each ingested .emlx file path in ingest_emlx_files.
           On subsequent runs, only process paths not yet recorded.

Both paths still deduplicate by message_id as a safety net.
"""

import re
import time
import email as _email_mod
from email import policy as _policy
from pathlib import Path

# Re-import parser's _FROM_LINE for _split_mbox_bytes consistency
_FROM_LINE = re.compile(rb"^From ", re.MULTILINE)

from app.database import get_db
from app.logging_config import get_logger
from app.services.parser import parse_mbox, count_messages, _parse_message
from app.services.emlx_parser import parse_emlx_file, find_emlx_files

log = get_logger("indexer")

_INSERT_SQL = """
    INSERT INTO emails (
        message_id, subject, sender_name, sender_email, recipients,
        date_sent, date_timestamp, body_text, body_html, headers,
        mbox_source, thread_id, has_attachments, attachment_names, raw_message
    ) VALUES (
        :message_id, :subject, :sender_name, :sender_email, :recipients,
        :date_sent, :date_timestamp, :body_text, :body_html, :headers,
        :mbox_source, :thread_id, :has_attachments, :attachment_names, :raw_message
    )
"""


# ── Source tracking ────────────────────────────────────────────────────────

def _get_source_record(conn, source_name: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM ingest_sources WHERE source_name = ?", (source_name,)
    ).fetchone()
    return dict(row) if row else None


def _upsert_source(conn, source_name, source_type, source_path,
                   file_size, file_mtime, last_offset,
                   emails_total, new_count, skipped_count):
    conn.execute("""
        INSERT INTO ingest_sources
            (source_name, source_type, source_path, file_size, file_mtime,
             last_message_offset, emails_total, last_ingest_at,
             last_ingest_new, last_ingest_skipped)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?)
        ON CONFLICT(source_name) DO UPDATE SET
            source_path         = excluded.source_path,
            file_size           = excluded.file_size,
            file_mtime          = excluded.file_mtime,
            last_message_offset = excluded.last_message_offset,
            emails_total        = excluded.emails_total,
            last_ingest_at      = excluded.last_ingest_at,
            last_ingest_new     = excluded.last_ingest_new,
            last_ingest_skipped = excluded.last_ingest_skipped
    """, (source_name, source_type, source_path, file_size, file_mtime,
          last_offset, emails_total, new_count, skipped_count))


# ── mbox byte-level helpers ────────────────────────────────────────────────

def _split_mbox_bytes(data: bytes) -> list[bytes]:
    """Split raw mbox bytes into individual RFC822 message chunks."""
    separators = [m.start() for m in _FROM_LINE.finditer(data)]
    chunks = []
    for i, start in enumerate(separators):
        end = separators[i + 1] if i + 1 < len(separators) else len(data)
        nl = data.find(b"\n", start)
        if nl == -1:
            continue
        chunk = data[nl + 1:end]
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def _find_resume_offset(mbox_path: Path, last_offset: int) -> int:
    """Return the "From " separator offset nearest to last_offset."""
    if last_offset <= 0:
        return 0
    try:
        data = mbox_path.read_bytes()
        m = _FROM_LINE.search(data, last_offset)
        return m.start() if m else last_offset
    except Exception:
        return 0


# ── mbox ingestion ─────────────────────────────────────────────────────────

def ingest_mbox(mbox_path: Path, incremental: bool = True) -> dict:
    """
    Ingest a single .mbox file with optional incremental mode.

    incremental=True:
      - Unchanged (same size+mtime) → skip immediately, 0 parses.
      - Grown → seek to last recorded byte offset, parse only new tail.
      - Replaced/truncated → full scan (dedup by message_id is safety net).
    """
    start = time.time()
    source_label = mbox_path.parent.name if mbox_path.name == "mbox" else mbox_path.name

    try:
        stat = mbox_path.stat()
        current_size  = stat.st_size
        current_mtime = stat.st_mtime
    except Exception as e:
        log.warning("Cannot stat %s: %s", mbox_path, e)
        return {"mbox_file": source_label, "total_messages": 0, "imported": 0,
                "skipped": 0, "errors": 0, "duration_seconds": 0, "mode": "error"}

    with get_db() as conn:
        record = _get_source_record(conn, source_label)

    resume_offset = 0
    mode = "full"

    if incremental and record:
        prev_size   = record["file_size"]
        prev_mtime  = record["file_mtime"]
        prev_offset = record["last_message_offset"]

        if current_size == prev_size and abs(current_mtime - prev_mtime) < 2:
            log.info("⏭  %s unchanged — skipping", source_label)
            return {"mbox_file": source_label,
                    "total_messages": record["emails_total"],
                    "imported": 0, "skipped": record["emails_total"],
                    "errors": 0, "duration_seconds": 0, "mode": "unchanged"}

        if current_size > prev_size and prev_offset > 0:
            resume_offset = _find_resume_offset(mbox_path, prev_offset)
            mode = "incremental"
            log.info("⚡ %s grown by %d bytes — resuming from offset %d",
                     source_label, current_size - prev_size, resume_offset)
        else:
            log.info("🔄 %s appears replaced — full scan", source_label)

    imported = 0
    skipped  = 0
    errors   = 0

    if resume_offset > 0:
        # Partial parse: only read the new tail bytes
        try:
            data = mbox_path.read_bytes()
            chunks = _split_mbox_bytes(data[resume_offset:])
            log.info("📨 %s — %d new messages (incremental)", source_label, len(chunks))
            with get_db() as conn:
                for i, msg_bytes in enumerate(chunks):
                    try:
                        msg = _email_mod.message_from_bytes(msg_bytes, policy=_policy.compat32)
                        rec = _parse_message(msg, source=mbox_path.name, raw_bytes=msg_bytes)
                        if rec is None:
                            skipped += 1
                            continue
                        if rec["message_id"]:
                            if conn.execute("SELECT 1 FROM emails WHERE message_id = ?",
                                            (rec["message_id"],)).fetchone():
                                skipped += 1
                                continue
                        conn.execute(_INSERT_SQL, rec)
                        imported += 1
                        if (i + 1) % 500 == 0:
                            conn.commit()
                    except Exception as e:
                        log.warning("  ⚠ incremental parse error: %s", e)
                        errors += 1
        except Exception as e:
            log.warning("Incremental parse failed, falling back to full scan: %s", e)
            resume_offset = 0
            mode = "full"

    if resume_offset == 0:
        total = count_messages(mbox_path)
        log.info("📨 Ingesting %s (%d messages, mode=%s)", source_label, total, mode)
        with get_db() as conn:
            for i, rec in enumerate(parse_mbox(mbox_path, source_name=source_label)):
                try:
                    if rec["message_id"]:
                        if conn.execute("SELECT 1 FROM emails WHERE message_id = ?",
                                        (rec["message_id"],)).fetchone():
                            skipped += 1
                            continue
                    conn.execute(_INSERT_SQL, rec)
                    imported += 1
                    if (i + 1) % 500 == 0:
                        conn.commit()
                        log.debug("  ... %d/%d", i + 1, total)
                except Exception as e:
                    log.warning("  ⚠ insert error: %s", e)
                    errors += 1

    # Record the new file-end as the resume offset for next time
    new_offset = current_size
    with get_db() as conn:
        prev_total = record["emails_total"] if record else 0
        _upsert_source(conn, source_label, "mbox", str(mbox_path),
                       current_size, current_mtime, new_offset,
                       prev_total + imported, imported, skipped)

    duration = time.time() - start
    log.info("✅ %s: %d imported, %d skipped, %d errors (%.1fs, mode=%s)",
             source_label, imported, skipped, errors, duration, mode)
    return {"mbox_file": source_label,
            "total_messages": (record["emails_total"] if record else 0) + imported,
            "imported": imported, "skipped": skipped, "errors": errors,
            "duration_seconds": round(duration, 2), "mode": mode}


# ── emlx ingestion ─────────────────────────────────────────────────────────

def ingest_emlx_mailbox(mailbox_name: str, emlx_files: list[Path],
                        incremental: bool = True) -> dict:
    """
    Ingest Apple Mail .emlx files from a single mailbox.

    incremental=True: skip any .emlx path already in ingest_emlx_files.
    """
    start    = time.time()
    imported = 0
    skipped  = 0
    errors   = 0
    mode     = "full"

    with get_db() as conn:
        record = _get_source_record(conn, mailbox_name)

        if incremental and record:
            seen = set(r[0] for r in conn.execute(
                "SELECT path FROM ingest_emlx_files WHERE source_name = ?",
                (mailbox_name,)
            ).fetchall())
            new_files = [f for f in emlx_files if str(f) not in seen]
            if not new_files:
                log.info("⏭  %s — no new .emlx files", mailbox_name)
                return {"mbox_file": mailbox_name,
                        "total_messages": record["emails_total"],
                        "imported": 0, "skipped": len(emlx_files),
                        "errors": 0, "duration_seconds": 0, "mode": "unchanged"}
            mode = "incremental"
            files_to_process = new_files
            log.info("⚡ %s — %d new of %d total .emlx files",
                     mailbox_name, len(new_files), len(emlx_files))
        else:
            files_to_process = emlx_files

    log.info("📨 Ingesting %s (%d files, mode=%s)", mailbox_name, len(files_to_process), mode)
    with get_db() as conn:
        for i, emlx_path in enumerate(files_to_process):
            path_str = str(emlx_path)
            try:
                rec = parse_emlx_file(emlx_path, source_name=mailbox_name)
                if rec is None:
                    skipped += 1
                else:
                    if rec["message_id"] and conn.execute(
                        "SELECT 1 FROM emails WHERE message_id = ?",
                        (rec["message_id"],)
                    ).fetchone():
                        skipped += 1
                    else:
                        conn.execute(_INSERT_SQL, rec)
                        imported += 1
                conn.execute(
                    "INSERT OR IGNORE INTO ingest_emlx_files (path, source_name) VALUES (?, ?)",
                    (path_str, mailbox_name)
                )
                if (i + 1) % 500 == 0:
                    conn.commit()
                    log.debug("  ... %d/%d", i + 1, len(files_to_process))
            except Exception as e:
                log.warning("  ⚠ %s: %s", emlx_path.name, e)
                errors += 1

        prev_total = record["emails_total"] if record else 0
        _upsert_source(conn, mailbox_name, "emlx", "",
                       0, 0, 0, prev_total + imported, imported, skipped)

    duration = time.time() - start
    log.info("✅ %s: %d imported, %d skipped, %d errors (%.1fs, mode=%s)",
             mailbox_name, imported, skipped, errors, duration, mode)
    return {"mbox_file": mailbox_name,
            "total_messages": (record["emails_total"] if record else 0) + imported,
            "imported": imported, "skipped": skipped, "errors": errors,
            "duration_seconds": round(duration, 2), "mode": mode}


# ── Bulk helpers ──────────────────────────────────────────────────────────

def ingest_all(data_dir: Path, incremental: bool = True) -> list[dict]:
    """Auto-discover and ingest all sources. incremental=True skips unchanged."""
    results = []
    mailboxes = find_emlx_files(data_dir)
    if mailboxes:
        for name in sorted(mailboxes):
            results.append(ingest_emlx_mailbox(name, mailboxes[name], incremental=incremental))

    mbox_map: dict[str, Path] = {}
    for f in data_dir.rglob("mbox"):
        if f.is_file() and f.stat().st_size > 0:
            mbox_map[str(f)] = f
    for f in data_dir.glob("*.mbox"):
        if f.is_file() and f.stat().st_size > 0:
            mbox_map[str(f)] = f
    for path_str in sorted(mbox_map):
        results.append(ingest_mbox(mbox_map[path_str], incremental=incremental))

    if not results:
        log.warning("No email data found in %s", data_dir)
    return results


def get_source_status(data_dir: Path) -> list[dict]:
    """
    Compare on-disk sources against ingest_sources.
    Each entry has a 'status': new | unchanged | updated | missing
    and 'new_count': estimated number of unimported messages.
    """
    on_disk: dict[str, dict] = {}

    mailboxes = find_emlx_files(data_dir) or {}
    for name, files in mailboxes.items():
        on_disk[name] = {"type": "emlx", "file_count": len(files)}

    for f in data_dir.rglob("mbox"):
        if f.is_file() and f.stat().st_size > 0:
            on_disk[f.parent.name] = {"type": "mbox", "path": str(f),
                                      "file_size": f.stat().st_size,
                                      "file_mtime": f.stat().st_mtime}
    for f in data_dir.glob("*.mbox"):
        if f.is_file() and f.stat().st_size > 0:
            on_disk[f.name] = {"type": "mbox", "path": str(f),
                               "file_size": f.stat().st_size,
                               "file_mtime": f.stat().st_mtime}

    with get_db() as conn:
        db_records = {r["source_name"]: dict(r)
                      for r in conn.execute("SELECT * FROM ingest_sources").fetchall()}
        emlx_counts = {r[0]: r[1] for r in conn.execute(
            "SELECT source_name, COUNT(*) FROM ingest_emlx_files GROUP BY source_name"
        ).fetchall()}

    results = []
    for name, info in on_disk.items():
        db = db_records.get(name)
        if db is None:
            status    = "new"
            new_count = info.get("file_count")
        elif info["type"] == "emlx":
            ingested  = emlx_counts.get(name, 0)
            new_count = max(0, info.get("file_count", 0) - ingested)
            status    = "updated" if new_count > 0 else "unchanged"
        else:
            ds, dm = info.get("file_size", 0), info.get("file_mtime", 0)
            if ds == db["file_size"] and abs(dm - db["file_mtime"]) < 2:
                status    = "unchanged"
                new_count = 0
            elif ds > db["file_size"]:
                status    = "updated"
                new_count = None   # unknown until parsed
            else:
                status    = "updated"
                new_count = None

        results.append({
            "source_name":     name,
            "source_type":     info["type"],
            "status":          status,
            "emails_total":    db["emails_total"] if db else 0,
            "last_ingest_at":  db["last_ingest_at"] if db else None,
            "last_ingest_new": db["last_ingest_new"] if db else 0,
            "new_count":       new_count,
        })

    for name, db in db_records.items():
        if name not in on_disk:
            results.append({
                "source_name":     name,
                "source_type":     db["source_type"],
                "status":          "missing",
                "emails_total":    db["emails_total"],
                "last_ingest_at":  db["last_ingest_at"],
                "last_ingest_new": db["last_ingest_new"],
                "new_count":       0,
            })

    return sorted(results, key=lambda r: r["source_name"])
