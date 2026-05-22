"""
Attachment extraction service.

Re-parses original mbox/emlx files on demand to extract attachment
binaries for download and full RFC822 messages for .eml export.

Performance: builds a Message-ID → byte-offset index on first access,
then seeks directly to the target message. Avoids parsing all 50K+ emails.
"""

import email
import functools
import re
from email import policy
from pathlib import Path
from typing import Optional

from app.config import DATA_DIR
from app.database import get_db
from app.logging_config import get_logger
from app.utils.email_utils import decode_email_header, _is_noise_attachment

log = get_logger("attachments")

# Mbox "From " separator line pattern (marks start of each message)
_FROM_LINE = re.compile(rb'^From ', re.MULTILINE)

# In-memory cache: mbox_path → {message_id → byte_offset}
_offset_cache: dict[str, dict[str, int]] = {}


# ── Source file discovery ──────────────────────────────────────

@functools.lru_cache(maxsize=8)
def _discover_mbox_files() -> list[Path]:
    """Find all mbox files across DATA_DIR + every registered ingest folder
    (cached). Cache is invalidated when folders are added/removed by callers
    that import _invalidate_mbox_cache."""
    from app.services.folders import all_data_paths

    files: list[Path] = []
    for root in all_data_paths():
        for f in root.rglob("*.mbox"):
            if f.is_file() and f.stat().st_size > 0:
                files.append(f)
        for f in root.rglob("mbox"):
            if f.is_file() and f.stat().st_size > 0 and f not in files:
                files.append(f)
    return files


def _invalidate_mbox_cache() -> None:
    """Drop the cached mbox-file list. Called after add/remove of an
    ingest folder so subsequent attachment downloads see the new path."""
    _discover_mbox_files.cache_clear()


def _find_source_files(mbox_source: str) -> list[Path]:
    """
    Locate the original mbox files for a given mbox_source label.
    Returns best-match files first, then all others as fallback.
    """
    all_files = _discover_mbox_files()
    primary = []
    secondary = []
    stem = mbox_source.replace(".mbox", "")

    for f in all_files:
        if f.name == mbox_source or f.parent.name == mbox_source:
            primary.append(f)
        elif stem in str(f):
            secondary.append(f)

    # Return primary matches first, then secondary, then everything else
    seen = set(str(f) for f in primary + secondary)
    rest = [f for f in all_files if str(f) not in seen]
    return primary + secondary + rest


# ── Fast message extraction via byte scanning ──────────────────

def _build_offset_index(mbox_path: Path) -> dict[str, int]:
    """
    Build a Message-ID → byte offset index for an mbox file.

    Scans raw bytes for Message-ID headers without fully parsing
    every message. Cached in memory after first build — subsequent
    lookups in the same file are O(1).
    """
    cache_key = str(mbox_path)
    if cache_key in _offset_cache:
        return _offset_cache[cache_key]

    log.info("Building offset index for %s...", mbox_path.name)
    index = {}
    try:
        data = mbox_path.read_bytes()
    except Exception as e:
        log.warning("Cannot read %s: %s", mbox_path, e)
        return {}

    # Find all "From " separators
    separators = [m.start() for m in _FROM_LINE.finditer(data)]
    if not separators:
        _offset_cache[cache_key] = index
        return index

    # For each message chunk, extract just the Message-ID header
    mid_pattern = re.compile(
        rb'^Message-ID:\s*<?([^>\r\n]+)>?', re.MULTILINE | re.IGNORECASE
    )

    for i, start in enumerate(separators):
        # Only scan the header portion (first ~8KB) for speed
        end = separators[i + 1] if i + 1 < len(separators) else len(data)
        header_end = min(start + 8192, end)
        chunk = data[start:header_end]

        match = mid_pattern.search(chunk)
        if match:
            mid = match.group(1).decode('ascii', errors='replace').strip()
            index[mid] = start

    _offset_cache[cache_key] = index
    log.info("  Indexed %d messages in %s", len(index), mbox_path.name)
    return index


def _extract_message_bytes(mbox_path: Path, offset: int) -> bytes:
    """Extract raw RFC822 message bytes starting at a known offset."""
    data = mbox_path.read_bytes()
    # Skip past the "From " separator line
    first_newline = data.index(b'\n', offset)
    # Find the next "From " line (start of next message)
    next_from = _FROM_LINE.search(data, first_newline + 1)
    end = next_from.start() if next_from else len(data)
    return data[first_newline + 1:end]


def _find_message_fast(message_id: str, mbox_source: str):
    """
    Locate and parse a single message using the byte offset index.

    First-time access builds the index (~1s for 50K emails).
    Subsequent lookups are instant (dict lookup + targeted read).
    """
    source_files = _find_source_files(mbox_source)

    for mbox_path in source_files:
        index = _build_offset_index(mbox_path)
        if message_id in index:
            try:
                msg_bytes = _extract_message_bytes(mbox_path, index[message_id])
                return email.message_from_bytes(msg_bytes, policy=policy.compat32)
            except Exception as e:
                log.warning("Error parsing message at offset %d in %s: %s",
                            index[message_id], mbox_path.name, e)

    return None


def _find_emlx_message(message_id: str) -> Optional[object]:
    """Search .emlx files for a matching Message-ID. Slower fallback.
    Walks every registered ingest folder + DATA_DIR."""
    from app.services.folders import all_data_paths

    needle = message_id.encode('ascii', errors='replace')
    for root in all_data_paths():
        for emlx_path in root.rglob("*.emlx"):
            if ".partial." in emlx_path.name:
                continue
            try:
                raw = emlx_path.read_bytes()
                if needle not in raw:
                    continue
                first_nl = raw.index(b"\n")
                try:
                    byte_count = int(raw[:first_nl].strip())
                    msg_bytes = raw[first_nl + 1: first_nl + 1 + byte_count]
                except ValueError:
                    msg_bytes = raw
                msg = email.message_from_bytes(msg_bytes, policy=policy.compat32)
                mid = (msg.get("Message-ID") or "").strip().strip("<>")
                if mid == message_id:
                    return msg
            except Exception:
                continue
    return None


def _find_message(email_id: int):
    """
    Look up an email by DB id and locate the original message.

    Returns (email.message.Message, db_row) or (None, None).
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT message_id, mbox_source, raw_message FROM emails WHERE id = ?",
            (email_id,)
        ).fetchone()

    if not row or not row["message_id"]:
        return None, None

    # If raw bytes exist, parse them directly
    if row["raw_message"]:
        try:
            msg = email.message_from_bytes(row["raw_message"], policy=policy.compat32)
            return msg, row
        except Exception as e:
            log.warning("Error parsing stored raw_message for email %d: %s", email_id, e)

    message_id = row["message_id"]
    mbox_source = row["mbox_source"] or ""

    # Try fast mbox byte-offset lookup first
    msg = _find_message_fast(message_id, mbox_source)
    if msg:
        return msg, row

    # Fallback to emlx scan
    msg = _find_emlx_message(message_id)
    if msg:
        return msg, row

    log.warning("Could not locate message_id=%s in source files", message_id)
    return None, None


# ── External-attachment (Apple Mail) helpers ────────────────────

import mimetypes


def _external_attachment_path(email_id: int, filename: str) -> Optional[Path]:
    """
    For Apple Mail emails, look up the sibling Attachments/<numeric_id>/
    directory via the stored source_path and find a file matching filename.
    Returns the Path or None if not found / not applicable.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT source_path FROM emails WHERE id = ?", (email_id,)
        ).fetchone()
    if not row or not row["source_path"]:
        return None
    emlx_path = Path(row["source_path"])
    if not emlx_path.name.endswith(".emlx"):
        return None
    attach_dir = emlx_path.parent.parent / "Attachments" / emlx_path.stem
    if not attach_dir.is_dir():
        return None
    # Apple stores files under part-numbered subdirs (2.2/, 2.4/, …).
    # rglob handles both layouts: nested by part, or flat.
    for p in attach_dir.rglob(filename):
        if p.is_file():
            return p
    return None


def _list_external_attachments(email_id: int) -> list[dict]:
    """List externally-stored attachments for an Apple Mail email."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT source_path FROM emails WHERE id = ?", (email_id,)
        ).fetchone()
    if not row or not row["source_path"]:
        return []
    emlx_path = Path(row["source_path"])
    if not emlx_path.name.endswith(".emlx"):
        return []
    attach_dir = emlx_path.parent.parent / "Attachments" / emlx_path.stem
    if not attach_dir.is_dir():
        return []
    items = []
    try:
        for p in attach_dir.rglob("*"):
            if not p.is_file() or p.name.startswith("."):
                continue
            ct, _ = mimetypes.guess_type(p.name)
            ct = ct or "application/octet-stream"
            if _is_noise_attachment(p.name, ct):
                continue
            try:
                size = p.stat().st_size
            except OSError:
                size = 0
            items.append({
                "filename": p.name,
                "content_type": ct,
                "size": size,
            })
    except (OSError, PermissionError):
        pass
    return items


# ── Public API ─────────────────────────────────────────────────

def extract_attachment(email_id: int, filename: str) -> Optional[dict]:
    """
    Extract a specific attachment from an email.

    Returns dict with 'data' (bytes), 'content_type', 'filename',
    or None if not found.

    For Apple Mail emails, tries the on-disk Attachments/ sibling
    directory first (where most attachments actually live) before
    falling back to MIME parsing.
    """
    # Fast path: file on disk in the sibling Attachments dir
    disk = _external_attachment_path(email_id, filename)
    if disk is not None:
        try:
            data = disk.read_bytes()
        except OSError as e:
            log.warning("Could not read external attachment %s: %s", disk, e)
        else:
            ct, _ = mimetypes.guess_type(disk.name)
            return {
                "data": data,
                "content_type": ct or "application/octet-stream",
                "filename": disk.name,
            }

    # Fallback: walk the MIME tree of the stored raw_message
    msg, row = _find_message(email_id)
    if msg is None:
        return None

    if not msg.is_multipart():
        return None

    for part in msg.walk():
        content_disposition = str(part.get("Content-Disposition", ""))
        if "attachment" not in content_disposition:
            continue

        part_filename = part.get_filename()
        if part_filename:
            part_filename = decode_email_header(part_filename)
        else:
            part_filename = f"unnamed.{part.get_content_subtype()}"

        if part_filename == filename:
            payload = part.get_payload(decode=True)
            if payload is None:
                return None

            content_type = part.get_content_type() or "application/octet-stream"
            return {
                "data": payload,
                "content_type": content_type,
                "filename": part_filename,
            }

    return None


def list_extractable_attachments(email_id: int) -> list[dict]:
    """List all attachments from an email with sizes and MIME types.

    Merges inline (MIME-tree) attachments and externally-stored ones
    (Apple Mail sibling Attachments/ directory). Deduplicates by filename.
    """
    seen: dict[str, dict] = {}

    # External (Apple Mail) — usually the majority
    for item in _list_external_attachments(email_id):
        seen[item["filename"]] = item

    # Inline (MIME tree) — for mbox + signed/encrypted emlx with embedded parts
    msg, _ = _find_message(email_id)
    if msg is not None and msg.is_multipart():
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" not in content_disposition:
                continue

            part_filename = part.get_filename()
            if part_filename:
                part_filename = decode_email_header(part_filename)
            else:
                part_filename = f"unnamed.{part.get_content_subtype()}"

            content_type = part.get_content_type() or "application/octet-stream"
            if _is_noise_attachment(part_filename, content_type):
                continue
            if part_filename in seen:
                continue

            payload = part.get_payload(decode=True)
            size = len(payload) if payload else 0

            seen[part_filename] = {
                "filename": part_filename,
                "content_type": content_type,
                "size": size,
            }

    return list(seen.values())


def export_eml(email_id: int) -> Optional[dict]:
    """
    Export an email as a complete .eml (RFC822) file.

    Returns dict with 'data' (bytes), 'filename', or None.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT raw_message, subject FROM emails WHERE id = ?",
            (email_id,)
        ).fetchone()

    if not row:
        return None

    # If raw bytes exist in database, use them directly (best for .eml export)
    if row["raw_message"]:
        subject = (row["subject"] or "no-subject") if row else "email"
        safe_subject = "".join(
            c if c.isalnum() or c in " -_" else "_" for c in subject
        )[:60].strip()
        filename = f"{safe_subject}.eml"
        return {
            "data": row["raw_message"],
            "filename": filename,
        }

    # Fallback: reconstruct from parsed fields
    msg, _ = _find_message(email_id)
    if msg is None:
        return None

    subject = (row["subject"] or "no-subject") if row else "email"
    safe_subject = "".join(
        c if c.isalnum() or c in " -_" else "_" for c in subject
    )[:60].strip()
    filename = f"{safe_subject}.eml"

    eml_bytes = msg.as_bytes()
    return {
        "data": eml_bytes,
        "filename": filename,
    }
