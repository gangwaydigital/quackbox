"""
Shared fixtures for the QuackBox test suite.

Builds synthetic RFC822 messages, mbox files, and .emlx files from scratch
so we don't need to ship real email data in the repo.
"""
from __future__ import annotations

import sqlite3
import textwrap
from pathlib import Path

import pytest


# ── Raw RFC822 message fixtures ────────────────────────────────────────────


def _normalize(raw: str) -> bytes:
    """Strip leading newline + dedent + re-CRLF the headers and body."""
    return textwrap.dedent(raw).strip().replace("\n", "\r\n").encode() + b"\r\n"


@pytest.fixture
def msg_simple_text() -> bytes:
    """A minimal single-part text/plain message."""
    return _normalize("""
        From: Alice <alice@example.com>
        To: Bob <bob@example.com>
        Subject: Hello
        Date: Mon, 1 Jan 2024 12:00:00 +0000
        Message-ID: <simple-1@example.com>
        Content-Type: text/plain; charset=utf-8
        MIME-Version: 1.0

        Just a plain text message.
    """)


@pytest.fixture
def msg_with_attachment() -> bytes:
    """A multipart message with one real PDF attachment."""
    return _normalize("""
        From: Alice <alice@example.com>
        To: Bob <bob@example.com>
        Subject: Report
        Date: Mon, 2 Jan 2024 12:00:00 +0000
        Message-ID: <atta-1@example.com>
        MIME-Version: 1.0
        Content-Type: multipart/mixed; boundary="BOUNDARY1"

        --BOUNDARY1
        Content-Type: text/plain; charset=utf-8

        See attached.

        --BOUNDARY1
        Content-Type: application/pdf; name="quarterly.pdf"
        Content-Disposition: attachment; filename="quarterly.pdf"
        Content-Transfer-Encoding: base64

        JVBERi0xLjQKJfbk/N8KMSAwIG9iago8PC9UeXBlL0NhdGFsb2cKL1BhZ2VzIDIgMCBSPj4KZW5k
        b2JqCg==

        --BOUNDARY1--
    """)


@pytest.fixture
def msg_with_calendar_invite() -> bytes:
    """A multipart message carrying a text/calendar VEVENT invite."""
    return _normalize("""
        From: Alice <alice@example.com>
        To: Bob <bob@example.com>
        Subject: Project sync
        Date: Mon, 1 Jan 2024 10:00:00 +0000
        Message-ID: <invite-1@example.com>
        MIME-Version: 1.0
        Content-Type: multipart/alternative; boundary="MIX1"

        --MIX1
        Content-Type: text/plain; charset=utf-8

        Project sync — Wednesday at 2pm.

        --MIX1
        Content-Type: text/calendar; method=REQUEST; charset=UTF-8

        BEGIN:VCALENDAR
        VERSION:2.0
        PRODID:-//Test//EN
        METHOD:REQUEST
        BEGIN:VEVENT
        UID:event-uid-123@example.com
        DTSTAMP:20240101T100000Z
        DTSTART:20240110T140000Z
        DTEND:20240110T150000Z
        SUMMARY:Project sync
        DESCRIPTION:Weekly check-in
        LOCATION:Zoom
        ORGANIZER;CN=Alice:MAILTO:alice@example.com
        ATTENDEE;CN=Bob:MAILTO:bob@example.com
        ATTENDEE;CN=Carol:MAILTO:carol@example.com
        STATUS:CONFIRMED
        END:VEVENT
        END:VCALENDAR

        --MIX1--
    """)


@pytest.fixture
def msg_smime_signed() -> bytes:
    """
    A multipart/signed message with an inner text body and an smime.p7s part.
    Mirrors the structure Apple Mail / Outlook produce for signed mail.
    """
    return _normalize("""
        From: Alice <alice@example.com>
        To: Bob <bob@example.com>
        Subject: Signed
        Date: Mon, 3 Jan 2024 12:00:00 +0000
        Message-ID: <signed-1@example.com>
        MIME-Version: 1.0
        Content-Type: multipart/signed; protocol="application/pkcs7-signature"; micalg=sha-256; boundary="SIGNED"

        --SIGNED
        Content-Type: text/plain; charset=utf-8

        This message is digitally signed.

        --SIGNED
        Content-Type: application/pkcs7-signature; name="smime.p7s"
        Content-Disposition: attachment; filename="smime.p7s"
        Content-Transfer-Encoding: base64

        MIIGUgYJKoZIhvcNAQcCoIIGQzCCBj8CAQExDzANBglghkgBZQMEAgEFADCC

        --SIGNED--
    """)


# ── Mbox fixture ────────────────────────────────────────────────────────────


@pytest.fixture
def mbox_file(tmp_path: Path, msg_simple_text: bytes, msg_with_attachment: bytes) -> Path:
    """Synthesize a .mbox file containing two messages."""
    path = tmp_path / "Inbox.mbox"
    parts = [
        b"From alice@example.com Mon Jan  1 12:00:00 2024\n",
        msg_simple_text,
        b"\n",
        b"From alice@example.com Mon Jan  2 12:00:00 2024\n",
        msg_with_attachment,
        b"\n",
    ]
    path.write_bytes(b"".join(parts))
    return path


# ── Emlx fixture (Apple Mail format) ────────────────────────────────────────


def _wrap_emlx(rfc822: bytes, with_plist_trailer: bool = True) -> bytes:
    """Wrap an RFC822 message in Apple Mail's .emlx envelope."""
    header = f"{len(rfc822):>10d}\n".encode("ascii")
    parts = [header, rfc822]
    if with_plist_trailer:
        parts.append(
            b'<?xml version="1.0" encoding="UTF-8"?>\n'
            b'<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            b'"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            b'<plist version="1.0"><dict><key>flags</key><integer>1</integer></dict></plist>\n'
        )
    return b"".join(parts)


@pytest.fixture
def emlx_wrap():
    """Expose the wrapper as a fixture so tests can build .emlx blobs ad hoc."""
    return _wrap_emlx


@pytest.fixture
def emlx_signed_file(tmp_path: Path, msg_smime_signed: bytes) -> Path:
    """A real-shaped .emlx file containing a signed multipart message."""
    path = tmp_path / "12345.emlx"
    path.write_bytes(_wrap_emlx(msg_smime_signed, with_plist_trailer=True))
    return path


# ── Database fixture ────────────────────────────────────────────────────────


@pytest.fixture
def fresh_db(tmp_path: Path):
    """
    Initialize a real SQLite database in a temp dir using the production
    init_db. Yields the connection so tests can poke at it directly.
    """
    from app.database import init_db, get_connection

    db_path = tmp_path / "quackbox-test.db"
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()
