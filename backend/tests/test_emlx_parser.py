"""
Tests for the .emlx parser.

The original .emlx parser bug — storing the full file (byte-count prefix +
plist trailer) as raw_message instead of just the RFC822 portion — broke
attachment downloads for every signed/multipart Apple Mail email. These tests
pin down the correct behavior so the bug can't come back.
"""
import email
import json
from email import policy

from app.services.emlx_parser import parse_emlx_file, find_emlx_files


class TestParseEmlxFile:
    def test_parses_signed_message(self, emlx_signed_file):
        record = parse_emlx_file(emlx_signed_file, source_name="Inbox")
        assert record is not None
        assert record["message_id"] == "signed-1@example.com"
        assert record["subject"] == "Signed"
        assert record["sender_email"] == "alice@example.com"
        assert record["mbox_source"] == "Inbox"

    def test_smime_signature_filtered_from_attachment_names(self, emlx_signed_file):
        record = parse_emlx_file(emlx_signed_file, source_name="Inbox")
        names = json.loads(record["attachment_names"])
        # smime.p7s is noise — must not appear
        assert names == []
        assert record["has_attachments"] is False

    def test_raw_message_excludes_byte_count_prefix(self, emlx_signed_file):
        """
        Regression test for the .emlx bug. raw_message must be ONLY the
        RFC822 portion — no leading "<digits>\\n" header from the .emlx
        envelope, no trailing plist XML.
        """
        record = parse_emlx_file(emlx_signed_file, source_name="Inbox")
        raw = record["raw_message"]
        # Must not start with the byte-count line
        assert not raw[:10].lstrip().startswith(b"0"), "raw_message looks like .emlx envelope"
        # Re-parsing the stored bytes should give back the multipart structure
        msg = email.message_from_bytes(raw, policy=policy.compat32)
        assert msg.is_multipart()
        ctypes = [p.get_content_type() for p in msg.walk()]
        assert "multipart/signed" in ctypes
        assert "application/pkcs7-signature" in ctypes
        assert "text/plain" in ctypes

    def test_handles_emlx_without_plist_trailer(self, tmp_path, msg_simple_text, emlx_wrap):
        """Some .emlx files have no plist trailer — must still parse cleanly."""
        path = tmp_path / "1.emlx"
        path.write_bytes(emlx_wrap(msg_simple_text, with_plist_trailer=False))
        record = parse_emlx_file(path, source_name="Sent")
        assert record is not None
        assert record["message_id"] == "simple-1@example.com"
        assert record["mbox_source"] == "Sent"

    def test_partial_emlx_files_are_skipped(self, tmp_path, msg_simple_text, emlx_wrap):
        """Apple Mail names in-progress downloads *.partial.emlx — they're not real emails."""
        path = tmp_path / "999.partial.emlx"
        path.write_bytes(emlx_wrap(msg_simple_text))
        assert parse_emlx_file(path) is None

    def test_unreadable_byte_count_falls_back_to_full_content(self, tmp_path, msg_simple_text):
        """If the leading byte-count line is missing, parser should still try to parse the body."""
        path = tmp_path / "no-count.emlx"
        path.write_bytes(msg_simple_text)
        record = parse_emlx_file(path, source_name="Inbox")
        assert record is not None
        # No byte count → entire file is treated as the message
        assert record["message_id"] == "simple-1@example.com"


class TestFindEmlxFiles:
    def test_groups_by_mailbox_directory(self, tmp_path, msg_simple_text, emlx_wrap):
        # Build a fake V10-style structure:
        # tmp/Mailboxes.mbox/Inbox.mbox/Messages/12345.emlx
        # tmp/Mailboxes.mbox/Sent.mbox/Messages/67890.emlx
        for box in ("Inbox", "Sent"):
            d = tmp_path / "Mailboxes.mbox" / f"{box}.mbox" / "Messages"
            d.mkdir(parents=True)
            (d / f"{hash(box) % 100000}.emlx").write_bytes(emlx_wrap(msg_simple_text))
        groups = find_emlx_files(tmp_path)
        assert set(groups.keys()) == {"Inbox", "Sent"}
        assert all(len(files) == 1 for files in groups.values())

    def test_partial_emlx_files_excluded(self, tmp_path, msg_simple_text, emlx_wrap):
        d = tmp_path / "Inbox.mbox" / "Messages"
        d.mkdir(parents=True)
        (d / "1.emlx").write_bytes(emlx_wrap(msg_simple_text))
        (d / "2.partial.emlx").write_bytes(emlx_wrap(msg_simple_text))
        groups = find_emlx_files(tmp_path)
        all_files = [f for files in groups.values() for f in files]
        assert len(all_files) == 1
