"""
Apple Mail .emlx file parser.

The .emlx format stores individual emails as:
  - Line 1: byte count of the email message
  - Lines 2+: raw RFC 822 email message (exactly byte_count bytes)
  - Remainder: Apple plist XML metadata (ignored)

Files ending in .partial.emlx are incomplete downloads and are skipped.
"""

import email
import json
from email import policy
from pathlib import Path
from typing import Optional

from app.config import MAX_BODY_LENGTH
from app.logging_config import get_logger
from app.utils.email_utils import (
    decode_email_header,
    parse_email_address,
    parse_recipient_list,
    parse_email_date,
    extract_body,
    extract_attachments,
    extract_thread_id,
    _is_noise_attachment,
)

log = get_logger("emlx")


def parse_emlx_file(emlx_path: Path, source_name: str = None) -> Optional[dict]:
    """Parse a single .emlx file into a database-ready record dict."""
    if ".partial." in emlx_path.name:
        return None
    try:
        raw = emlx_path.read_bytes()
    except Exception as e:
        log.warning("Cannot read %s: %s", emlx_path, e)
        return None
    try:
        first_newline = raw.index(b"\n")
        byte_count = int(raw[:first_newline].strip())
    except (ValueError, IndexError):
        byte_count = None
    if byte_count is not None:
        msg_bytes = raw[first_newline + 1 : first_newline + 1 + byte_count]
    else:
        msg_bytes = raw
    try:
        msg = email.message_from_bytes(msg_bytes, policy=policy.compat32)
    except Exception as e:
        log.warning("Cannot parse email from %s: %s", emlx_path.name, e)
        return None
    # Store only the RFC822 message bytes — NOT the full .emlx file, which has
    # a byte-count prefix line and an Apple plist trailer that confuse later
    # re-parsing (the email library would see the digits as the body and miss
    # all the multipart structure, including signed attachments).
    record = _message_to_record(msg, source_name or "Unknown", raw_bytes=msg_bytes)
    if record is None:
        return None
    # Track the source .emlx path so the extractor can find sibling attachments
    # later (Apple Mail stores attachment binaries in a sibling Attachments/
    # directory keyed by the numeric .emlx filename — see external_attachments_for).
    record["source_path"] = str(emlx_path)
    # Merge in externally-stored attachment filenames so the listing API picks
    # them up. The .emlx MIME tree usually doesn't carry the binaries.
    external = external_attachment_filenames(emlx_path)
    if external:
        try:
            inline = json.loads(record.get("attachment_names") or "[]")
        except Exception:
            inline = []
        merged = list(dict.fromkeys(inline + external))  # preserve order, dedupe
        record["attachment_names"] = json.dumps(merged)
        record["has_attachments"] = 1 if merged else 0
    return record


def external_attachments_dir(emlx_path: Path) -> Optional[Path]:
    """
    Return the sibling Attachments/<numeric_id>/ directory for an .emlx
    file, or None if that path doesn't exist. Apple Mail layout:
       .../Data/N/M/Messages/12345.emlx
       .../Data/N/M/Attachments/12345/<part>/<filename>
    """
    candidate = emlx_path.parent.parent / "Attachments" / emlx_path.stem
    return candidate if candidate.is_dir() else None


def external_attachment_filenames(emlx_path: Path) -> list[str]:
    """List user-content filenames in the sibling Attachments/ dir, recursively.
    Skips directories, hidden files, and S/MIME signature noise."""
    root = external_attachments_dir(emlx_path)
    if root is None:
        return []
    names: list[str] = []
    try:
        for p in root.rglob("*"):
            if not p.is_file() or p.name.startswith("."):
                continue
            if _is_noise_attachment(p.name):
                continue
            names.append(p.name)
    except (OSError, PermissionError):
        pass
    return names


def _message_to_record(msg, source: str, raw_bytes: bytes = None) -> Optional[dict]:
    """Convert an email.message.Message into a flat dict for database insertion."""
    message_id = msg.get("Message-ID", "")
    if message_id:
        message_id = message_id.strip().strip("<>")
    subject = decode_email_header(msg.get("Subject"))
    sender_name, sender_email = parse_email_address(msg.get("From"))
    recipients = []
    recipients.extend(parse_recipient_list(msg, "To"))
    recipients.extend(parse_recipient_list(msg, "Cc"))
    recipients.extend(parse_recipient_list(msg, "Bcc"))
    date_iso, date_timestamp = parse_email_date(msg.get("Date"))
    body_text, body_html = extract_body(msg)
    if body_text and len(body_text) > MAX_BODY_LENGTH:
        body_text = body_text[:MAX_BODY_LENGTH] + "\n[truncated]"
    has_attachments, attachment_names = extract_attachments(msg)
    thread_id = extract_thread_id(msg)
    headers = {k: decode_email_header(v) for k, v in msg.items()}
    result = {
        "message_id": message_id or None,
        "subject": subject,
        "sender_name": sender_name,
        "sender_email": sender_email,
        "recipients": json.dumps(recipients),
        "date_sent": date_iso,
        "date_timestamp": date_timestamp,
        "body_text": body_text,
        "body_html": body_html,
        "headers": json.dumps(headers),
        "mbox_source": source,
        "thread_id": thread_id,
        "has_attachments": has_attachments,
        "attachment_names": json.dumps(attachment_names),
    }
    # Store raw message bytes if provided (for .eml export)
    if raw_bytes is not None:
        result["raw_message"] = raw_bytes
    return result


def find_emlx_files(data_dir: Path) -> dict[str, list[Path]]:
    """Discover .emlx files grouped by mailbox name."""
    mailboxes = {}
    for emlx_path in data_dir.rglob("*.emlx"):
        if ".partial." in emlx_path.name:
            continue
        mailbox_name = _find_mailbox_name(emlx_path)
        if mailbox_name not in mailboxes:
            mailboxes[mailbox_name] = []
        mailboxes[mailbox_name].append(emlx_path)
    return mailboxes


def _find_mailbox_name(emlx_path: Path) -> str:
    """Walk up from an .emlx file to find the parent .mbox folder name."""
    current = emlx_path.parent
    while current != current.parent:
        if current.name.endswith(".mbox"):
            return current.name[:-5] if current.name != ".mbox" else "Unknown"
        current = current.parent
    return "Unknown"
