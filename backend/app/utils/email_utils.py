"""
Email utility functions.

Handles the messy reality of email parsing: encoded headers,
various date formats, MIME content extraction, etc.
"""

import re
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime, getaddresses
from typing import Optional


def decode_email_header(header: Optional[str]) -> str:
    """
    Decode an email header that may contain RFC 2047 encoded words.

    Examples:
        "=?UTF-8?B?SGVsbG8=?=" → "Hello"
        "Plain text subject" → "Plain text subject"
    """
    if not header:
        return ""
    try:
        decoded = str(make_header(decode_header(header)))
        return decoded.strip()
    except Exception:
        # Fall back to raw string if decoding fails
        return str(header).strip()


def parse_email_address(raw: Optional[str]) -> tuple[str, str]:
    """
    Parse an email address into (display_name, email).

    Examples:
        "John Doe <john@example.com>" → ("John Doe", "john@example.com")
        "john@example.com" → ("", "john@example.com")
    """
    if not raw:
        return ("", "")
    decoded = decode_email_header(raw)
    name, email = parseaddr(decoded)
    return (name.strip(), email.strip().lower())


def parse_recipient_list(msg, header_name: str) -> list[dict]:
    """
    Parse To, Cc, or Bcc headers into a list of {name, email, type}.

    Handles multiple recipients, encoded names, and group syntax.
    """
    raw = msg.get(header_name, "")
    if not raw:
        return []

    decoded = decode_email_header(raw)
    recipients = []
    for name, email in getaddresses([decoded]):
        if email:
            recipients.append({
                "name": name.strip() or None,
                "email": email.strip().lower(),
                "type": header_name.lower()
            })
    return recipients


def parse_email_date(raw: Optional[str]) -> tuple[Optional[str], Optional[float]]:
    """
    Parse email Date header into (ISO string, Unix timestamp).

    Handles the wild variety of date formats found in email.

    Returns:
        (iso_string, unix_timestamp) or (None, None) if unparseable
    """
    if not raw:
        return (None, None)

    try:
        dt = parsedate_to_datetime(raw)
        # Ensure timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        iso = dt.isoformat()
        timestamp = dt.timestamp()
        return (iso, timestamp)
    except Exception:
        pass

    # Fallback: try common non-standard formats
    fallback_formats = [
        "%Y-%m-%d %H:%M:%S",
        "%d %b %Y %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S",
    ]
    for fmt in fallback_formats:
        try:
            dt = datetime.strptime(raw.strip(), fmt).replace(tzinfo=timezone.utc)
            return (dt.isoformat(), dt.timestamp())
        except ValueError:
            continue

    return (None, None)


def extract_body(msg) -> tuple[str, Optional[str]]:
    """
    Extract plain text and HTML body from an email message.

    Walks the MIME tree, preferring text/plain but also capturing text/html.

    Returns:
        (plain_text_body, html_body_or_none)
    """
    text_parts = []
    html_parts = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            # Skip attachments
            if "attachment" in content_disposition:
                continue

            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")

                if content_type == "text/plain":
                    text_parts.append(text)
                elif content_type == "text/html":
                    html_parts.append(text)
            except Exception:
                continue
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
                content_type = msg.get_content_type()

                if content_type == "text/html":
                    html_parts.append(text)
                else:
                    text_parts.append(text)
        except Exception:
            pass

    plain_text = "\n".join(text_parts).strip()
    html_body = "\n".join(html_parts).strip() or None

    # If we only got HTML, do a rough strip for the text version
    if not plain_text and html_body:
        plain_text = strip_html(html_body)

    return (plain_text, html_body)


def strip_html(html: str) -> str:
    """Quick and dirty HTML tag removal for fallback text extraction."""
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# Filenames produced by mail clients as protocol/transport artifacts rather
# than user content. Hidden from attachment listings — users virtually never
# want to download these in isolation.
NOISE_ATTACHMENT_FILENAMES = {"smime.p7s", "smime.p7m"}


def _is_noise_attachment(filename: str, content_type: str = "") -> bool:
    if filename and filename.lower() in NOISE_ATTACHMENT_FILENAMES:
        return True
    ct = (content_type or "").lower()
    if ct in {"application/pkcs7-signature", "application/x-pkcs7-signature"}:
        return True
    return False


def extract_attachments(msg) -> tuple[bool, list[str]]:
    """
    Extract attachment info from an email.

    Returns:
        (has_attachments, list_of_filenames)

    S/MIME signature parts (smime.p7s / pkcs7-signature) are skipped — they're
    cryptographic envelopes attached to every signed message, not user content.
    """
    filenames = []
    if not msg.is_multipart():
        return (False, [])

    for part in msg.walk():
        content_disposition = str(part.get("Content-Disposition", ""))
        if "attachment" not in content_disposition:
            continue
        filename = part.get_filename()
        if filename:
            filename = decode_email_header(filename)
        else:
            filename = f"unnamed.{part.get_content_subtype()}"
        if _is_noise_attachment(filename, part.get_content_type()):
            continue
        filenames.append(filename)

    return (bool(filenames), filenames)


def extract_thread_id(msg) -> Optional[str]:
    """
    Extract thread identifier from In-Reply-To or References headers.

    Uses the first message-id in References, falling back to In-Reply-To.
    This groups emails into conversation threads.
    """
    references = msg.get("References", "")
    if references:
        # First message-id in References is the thread root
        match = re.search(r'<([^>]+)>', references)
        if match:
            return match.group(1)

    in_reply_to = msg.get("In-Reply-To", "")
    if in_reply_to:
        match = re.search(r'<([^>]+)>', in_reply_to)
        if match:
            return match.group(1)

    return None


def make_snippet(text: str, max_length: int = 200) -> str:
    """Create a short preview snippet from email body text."""
    if not text:
        return ""
    cleaned = re.sub(r'\s+', ' ', text).strip()
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[:max_length].rsplit(' ', 1)[0] + "…"
