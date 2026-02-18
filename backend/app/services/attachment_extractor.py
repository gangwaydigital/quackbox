"""
Attachment extraction service.

Re-parses original mbox/emlx files on demand to extract attachment
binaries for download and full RFC822 messages for .eml export.

Strategy: look up the email's message_id and mbox_source from the DB,
scan the matching source file(s) in DATA_DIR, and extract the payload.
"""

import email
import mailbox
import mimetypes
from email import policy
from pathlib import Path
from typing import Optional

from app.config import DATA_DIR
from app.database import get_db
from app.logging_config import get_logger
from app.utils.email_utils import decode_email_header

log = get_logger("attachments")


def _find_source_files(mbox_source: str) -> list[Path]:
    """
    Locate the original mbox or emlx files for a given mbox_source label.

    mbox_source might be:
      - "SomeName" (parent folder name for files named "mbox")
      - "something.mbox" (direct mbox filename)
      - An Apple Mail mailbox name (for .emlx)
    """
    candidates = []

    # Direct .mbox file match
    for f in DATA_DIR.rglob("*.mbox"):
        if f.is_file() and f.name == mbox_source:
            candidates.append(f)

    # Parent-folder match (e.g. "Inbox" → Inbox/mbox)
    for f in DATA_DIR.rglob("mbox"):
        if f.is_file() and f.parent.name == mbox_source:
            candidates.append(f)

    # Also search for files whose stem matches (without extension)
    stem = mbox_source.replace(".mbox", "")
    for f in DATA_DIR.rglob("mbox"):
        if f.is_file() and stem in str(f):
            if f not in candidates:
                candidates.append(f)

    return candidates


def _find_emlx_for_message(message_id: str, mbox_source: str) -> Optional[Path]:
    """Search .emlx files for one with a matching Message-ID."""
    for emlx_path in DATA_DIR.rglob("*.emlx"):
        if ".partial." in emlx_path.name:
            continue
        try:
            raw = emlx_path.read_bytes()
            first_nl = raw.index(b"\n")
            try:
                byte_count = int(raw[:first_nl].strip())
                msg_bytes = raw[first_nl + 1: first_nl + 1 + byte_count]
            except ValueError:
                msg_bytes = raw
            msg = email.message_from_bytes(msg_bytes, policy=policy.compat32)
            mid = (msg.get("Message-ID") or "").strip().strip("<>")
            if mid == message_id:
                return emlx_path
        except Exception:
            continue
    return None


def _find_message_in_mbox(message_id: str, mbox_path: Path):
    """Open an mbox file and find the message with matching Message-ID."""
    try:
        mbox = mailbox.mbox(str(mbox_path))
        for key, msg in mbox.items():
            mid = (msg.get("Message-ID") or "").strip().strip("<>")
            if mid == message_id:
                mbox.close()
                return msg
        mbox.close()
    except Exception as e:
        log.warning("Error scanning %s: %s", mbox_path, e)
    return None


def _find_message(email_id: int):
    """
    Look up an email by DB id and locate the original message object.

    Returns (email.message.Message, db_row) or (None, None).
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT message_id, mbox_source FROM emails WHERE id = ?",
            (email_id,)
        ).fetchone()

    if not row or not row["message_id"]:
        return None, None

    message_id = row["message_id"]
    mbox_source = row["mbox_source"] or ""

    # Try mbox files first
    source_files = _find_source_files(mbox_source)
    for mbox_path in source_files:
        msg = _find_message_in_mbox(message_id, mbox_path)
        if msg:
            return msg, row

    # Try all mbox files as fallback (source label might not match exactly)
    all_mbox = list(DATA_DIR.rglob("*.mbox")) + list(DATA_DIR.rglob("mbox"))
    all_mbox = list({str(f): f for f in all_mbox if f.is_file()}.values())
    for mbox_path in all_mbox:
        if mbox_path in source_files:
            continue
        msg = _find_message_in_mbox(message_id, mbox_path)
        if msg:
            return msg, row

    # Try .emlx files
    emlx_path = _find_emlx_for_message(message_id, mbox_source)
    if emlx_path:
        try:
            raw = emlx_path.read_bytes()
            first_nl = raw.index(b"\n")
            try:
                byte_count = int(raw[:first_nl].strip())
                msg_bytes = raw[first_nl + 1: first_nl + 1 + byte_count]
            except ValueError:
                msg_bytes = raw
            msg = email.message_from_bytes(msg_bytes, policy=policy.compat32)
            return msg, row
        except Exception as e:
            log.warning("Error reading emlx %s: %s", emlx_path, e)

    log.warning("Could not locate message_id=%s in source files", message_id)
    return None, None


def extract_attachment(email_id: int, filename: str) -> Optional[dict]:
    """
    Extract a specific attachment from an email.

    Returns dict with 'data' (bytes), 'content_type', 'filename',
    or None if not found.
    """
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
    """
    List all attachments from an email with their sizes.

    Returns list of dicts with 'filename', 'content_type', 'size'.
    """
    msg, row = _find_message(email_id)
    if msg is None:
        return []

    if not msg.is_multipart():
        return []

    attachments = []
    for part in msg.walk():
        content_disposition = str(part.get("Content-Disposition", ""))
        if "attachment" not in content_disposition:
            continue

        part_filename = part.get_filename()
        if part_filename:
            part_filename = decode_email_header(part_filename)
        else:
            part_filename = f"unnamed.{part.get_content_subtype()}"

        payload = part.get_payload(decode=True)
        size = len(payload) if payload else 0
        content_type = part.get_content_type() or "application/octet-stream"

        attachments.append({
            "filename": part_filename,
            "content_type": content_type,
            "size": size,
        })

    return attachments


def export_eml(email_id: int) -> Optional[dict]:
    """
    Export an email as a complete .eml (RFC822) file.

    Returns dict with 'data' (bytes), 'filename', or None.
    """
    msg, row = _find_message(email_id)
    if msg is None:
        return None

    # Reconstruct a safe filename from subject
    with get_db() as conn:
        email_row = conn.execute(
            "SELECT subject, sender_name, date_sent FROM emails WHERE id = ?",
            (email_id,)
        ).fetchone()

    subject = (email_row["subject"] or "no-subject") if email_row else "email"
    # Sanitize for filename
    safe_subject = "".join(c if c.isalnum() or c in " -_" else "_" for c in subject)[:60].strip()
    filename = f"{safe_subject}.eml"

    eml_bytes = msg.as_bytes()
    return {
        "data": eml_bytes,
        "filename": filename,
    }
