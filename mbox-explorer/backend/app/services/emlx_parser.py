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
from app.utils.email_utils import (
    decode_email_header,
    parse_email_address,
    parse_recipient_list,
    parse_email_date,
    extract_body,
    extract_attachments,
    extract_thread_id,
)


def parse_emlx_file(emlx_path: Path, source_name: str = None) -> Optional[dict]:
    """
    Parse a single .emlx file into a database record.

    Args:
        emlx_path: Path to the .emlx file
        source_name: Mailbox name to use as source label

    Returns:
        dict matching the emails table schema, or None on failure
    """
    # Skip partial downloads
    if ".partial." in emlx_path.name:
        return None

    try:
        raw = emlx_path.read_bytes()
    except Exception as e:
        print(f"  ⚠ Cannot read {emlx_path}: {e}")
        return None

    # First line is the byte count
    try:
        first_newline = raw.index(b"\n")
        byte_count = int(raw[:first_newline].strip())
    except (ValueError, IndexError):
        # If we can't parse the byte count, try treating the whole file as email
        byte_count = None

    # Extract the email message portion
    if byte_count is not None:
        msg_bytes = raw[first_newline + 1 : first_newline + 1 + byte_count]
    else:
        msg_bytes = raw

    # Parse as email
    try:
        msg = email.message_from_bytes(msg_bytes, policy=policy.compat32)
    except Exception as e:
        print(f"  ⚠ Cannot parse email from {emlx_path.name}: {e}")
        return None

    return _message_to_record(msg, source_name or "Unknown")


def _message_to_record(msg, source: str) -> Optional[dict]:
    """Convert a parsed email message to a database record."""

    # -- Message ID --
    message_id = msg.get("Message-ID", "")
    if message_id:
        message_id = message_id.strip().strip("<>")

    # -- Subject --
    subject = decode_email_header(msg.get("Subject"))

    # -- Sender --
    sender_name, sender_email = parse_email_address(msg.get("From"))

    # -- Recipients --
    recipients = []
    recipients.extend(parse_recipient_list(msg, "To"))
    recipients.extend(parse_recipient_list(msg, "Cc"))
    recipients.extend(parse_recipient_list(msg, "Bcc"))

    # -- Date --
    date_iso, date_timestamp = parse_email_date(msg.get("Date"))

    # -- Body --
    body_text, body_html = extract_body(msg)
    if body_text and len(body_text) > MAX_BODY_LENGTH:
        body_text = body_text[:MAX_BODY_LENGTH] + "\n[truncated]"

    # -- Attachments --
    has_attachments, attachment_names = extract_attachments(msg)

    # -- Threading --
    thread_id = extract_thread_id(msg)

    # -- All headers --
    headers = {k: decode_email_header(v) for k, v in msg.items()}

    return {
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


def find_emlx_files(data_dir: Path) -> dict[str, list[Path]]:
    """
    Recursively find all .emlx files grouped by mailbox name.

    Returns:
        dict mapping mailbox name (e.g. "INBOX.mbox") to list of .emlx paths
    """
    mailboxes = {}

    for emlx_path in data_dir.rglob("*.emlx"):
        # Skip partial downloads
        if ".partial." in emlx_path.name:
            continue

        # Walk up to find the .mbox directory name
        mailbox_name = _find_mailbox_name(emlx_path)
        if mailbox_name not in mailboxes:
            mailboxes[mailbox_name] = []
        mailboxes[mailbox_name].append(emlx_path)

    return mailboxes


def _find_mailbox_name(emlx_path: Path) -> str:
    """
    Walk up the directory tree to find the parent .mbox folder name.

    e.g., .../INBOX.mbox/<uuid>/Data/.../Messages/12345.emlx → "INBOX"
    """
    current = emlx_path.parent
    while current != current.parent:
        if current.name.endswith(".mbox"):
            # Strip .mbox suffix for a cleaner label
            return current.name[:-5] if current.name != ".mbox" else "Unknown"
        current = current.parent
    return "Unknown"
