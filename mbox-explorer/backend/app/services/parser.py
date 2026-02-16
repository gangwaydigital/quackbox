"""
Mbox file parser.

Reads .mbox files and extracts structured email data
ready for database insertion.
"""

import json
import mailbox
import time
from pathlib import Path
from typing import Generator

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


def parse_mbox(mbox_path: Path, source_name: str = None) -> Generator[dict, None, None]:
    """
    Parse an mbox file and yield structured email records.

    Yields:
        dict with keys matching the emails table schema.
    """
    source = source_name or mbox_path.name
    mbox = mailbox.mbox(str(mbox_path))

    for key, msg in mbox.items():
        try:
            record = _parse_message(msg, source=mbox_path.name)
            if record:
                yield record
        except Exception as e:
            print(f"  ⚠ Error parsing message {key}: {e}")
            continue

    mbox.close()


def _parse_message(msg, source: str) -> dict | None:
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


def count_messages(mbox_path: Path) -> int:
    """Quick count of messages in an mbox file without full parsing."""
    mbox = mailbox.mbox(str(mbox_path))
    count = len(mbox)
    mbox.close()
    return count
