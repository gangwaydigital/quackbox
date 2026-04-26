"""
Mbox file parser.

Reads .mbox files and extracts structured email data
ready for database insertion.
"""

import json
import mailbox
import re
import time
from email import policy as _policy
from email import message_from_bytes as _email_message_from_bytes
from pathlib import Path
from typing import Generator

# Mbox "From " separator pattern
_FROM_LINE = re.compile(rb'^From ', re.MULTILINE)

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
)

log = get_logger("parser")


def parse_mbox(mbox_path: Path, source_name: str = None) -> Generator[dict, None, None]:
    """
    Parse an mbox file and yield structured email records.

    Yields:
        dict with keys matching the emails table schema.
    """
    source = source_name or mbox_path.name
    mbox_bytes = mbox_path.read_bytes()

    # Find message boundaries using "From " pattern
    from_lines = list(_FROM_LINE.finditer(mbox_bytes))
    if not from_lines:
        return

    for i, start_match in enumerate(from_lines):
        start = start_match.start()
        # Get the raw message bytes (from "From " line to next "From " line)
        end = from_lines[i + 1].start() if i + 1 < len(from_lines) else len(mbox_bytes)
        raw_msg_bytes = mbox_bytes[start:end]

        # Skip "From " separator line to get the actual message
        first_nl = raw_msg_bytes.find(b"\n")
        if first_nl == -1:
            log.warning("%s: skipping malformed entry at offset %d (no newline after 'From ')", source, start)
            continue
        msg_bytes = raw_msg_bytes[first_nl + 1:]

        try:
            msg = _email_message_from_bytes(msg_bytes, policy=_policy.compat32)
            record = _parse_message(msg, source=mbox_path.name, raw_bytes=msg_bytes)
            if record:
                yield record
        except Exception as e:
            # Try to surface message-id and subject so the operator can locate the bad message
            mid = subj = "?"
            try:
                mid = (msg.get("Message-ID") or "?").strip().strip("<>")[:120]
                subj = (msg.get("Subject") or "")[:80]
            except Exception:
                pass
            log.error(
                "%s: failed to parse message at offset %d (size=%d, message_id=%s, subject=%r): %s",
                source, start, end - start, mid, subj, e,
                exc_info=True,
            )
            continue


def _parse_message(msg, source: str, raw_bytes: bytes = None) -> dict | None:
    """Parse a single email message into a database record."""

    # -- Message ID (required for dedup) --
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

    # -- All headers (for advanced queries) --
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


def count_messages(mbox_path: Path) -> int:
    """Quick count of messages in an mbox file without full parsing."""
    mbox = mailbox.mbox(str(mbox_path))
    count = len(mbox)
    mbox.close()
    return count
