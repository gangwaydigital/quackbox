"""
Tests for attachment_extractor.

Exercises the public extraction API against rows whose raw_message column
holds a real RFC822 multipart message — the path that actually runs in
production after the v4.2.0 .emlx fix and migration.
"""
import pytest

from app import database
from app.services import attachment_extractor


@pytest.fixture
def extractor_db(tmp_path, monkeypatch):
    """
    Fresh DB + patched extractor service. The extractor binds get_db at
    module import time, so we patch the symbol on the service module.
    """
    db_path = tmp_path / "extractor-test.db"
    database.init_db(db_path)
    real_get_db = database.get_db

    def get_db_override(p=db_path):
        return real_get_db(p)
    monkeypatch.setattr(attachment_extractor, "get_db", get_db_override)
    return db_path


def _insert(db_path, *, message_id, raw_message, mbox_source="Inbox"):
    with database.get_db(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO emails (message_id, mbox_source, raw_message) VALUES (?, ?, ?)",
            (message_id, mbox_source, raw_message),
        )
        return cur.lastrowid


# ── extract_attachment ─────────────────────────────────────────────────────


class TestExtractAttachment:
    def test_returns_payload_for_real_attachment(self, extractor_db, msg_with_attachment):
        eid = _insert(extractor_db, message_id="atta-1@x", raw_message=msg_with_attachment)

        result = attachment_extractor.extract_attachment(eid, "quarterly.pdf")
        assert result is not None
        assert result["filename"] == "quarterly.pdf"
        assert result["content_type"] == "application/pdf"
        # The base64-decoded payload should start with the PDF magic bytes
        assert result["data"].startswith(b"%PDF-")

    def test_missing_email_returns_none(self, extractor_db):
        assert attachment_extractor.extract_attachment(99999, "anything.pdf") is None

    def test_unknown_filename_returns_none(self, extractor_db, msg_with_attachment):
        eid = _insert(extractor_db, message_id="atta-1@x", raw_message=msg_with_attachment)
        assert attachment_extractor.extract_attachment(eid, "nope.pdf") is None

    def test_simple_text_email_returns_none(self, extractor_db, msg_simple_text):
        """Single-part text email has no attachments to extract."""
        eid = _insert(extractor_db, message_id="simple-1@x", raw_message=msg_simple_text)
        assert attachment_extractor.extract_attachment(eid, "anything.pdf") is None


# ── list_extractable_attachments ────────────────────────────────────────────


class TestListExtractableAttachments:
    def test_lists_real_attachment_with_size_and_type(self, extractor_db, msg_with_attachment):
        eid = _insert(extractor_db, message_id="atta-1@x", raw_message=msg_with_attachment)
        attachments = attachment_extractor.list_extractable_attachments(eid)
        assert len(attachments) == 1
        assert attachments[0]["filename"] == "quarterly.pdf"
        assert attachments[0]["content_type"] == "application/pdf"
        assert attachments[0]["size"] > 0

    def test_smime_signature_filtered(self, extractor_db, msg_smime_signed):
        """smime.p7s parts are noise — must not appear in the extractable list."""
        eid = _insert(extractor_db, message_id="signed-1@x", raw_message=msg_smime_signed)
        attachments = attachment_extractor.list_extractable_attachments(eid)
        # The signed message has only the smime.p7s "attachment" — should be empty after filter
        assert attachments == []

    def test_missing_email_returns_empty(self, extractor_db):
        assert attachment_extractor.list_extractable_attachments(99999) == []

    def test_simple_text_email_returns_empty(self, extractor_db, msg_simple_text):
        eid = _insert(extractor_db, message_id="simple-1@x", raw_message=msg_simple_text)
        assert attachment_extractor.list_extractable_attachments(eid) == []


# ── export_eml ──────────────────────────────────────────────────────────────


class TestExportEml:
    def test_returns_raw_message_when_stored(self, extractor_db, msg_with_attachment):
        eid = _insert(extractor_db, message_id="atta-1@x", raw_message=msg_with_attachment)
        # Add a subject so the filename has something meaningful
        with database.get_db(extractor_db) as conn:
            conn.execute("UPDATE emails SET subject = ? WHERE id = ?", ("Q1 Report", eid))

        result = attachment_extractor.export_eml(eid)
        assert result is not None
        assert result["data"] == msg_with_attachment
        assert "Q1 Report" in result["filename"]
        assert result["filename"].endswith(".eml")

    def test_filename_strips_unsafe_characters(self, extractor_db, msg_with_attachment):
        eid = _insert(extractor_db, message_id="atta-1@x", raw_message=msg_with_attachment)
        with database.get_db(extractor_db) as conn:
            conn.execute(
                "UPDATE emails SET subject = ? WHERE id = ?",
                ("../../etc/passwd: weird/chars", eid),
            )
        result = attachment_extractor.export_eml(eid)
        # Slashes, dots, colons, etc. should be sanitized to underscores
        assert "/" not in result["filename"]
        assert ":" not in result["filename"]
        assert ".." not in result["filename"].rstrip(".eml")

    def test_missing_email_returns_none(self, extractor_db):
        assert attachment_extractor.export_eml(99999) is None
