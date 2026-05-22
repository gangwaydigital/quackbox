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

from app.services.emlx_parser import (
    parse_emlx_file, find_emlx_files,
    external_attachments_dir, external_attachment_filenames,
)


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


# ── Apple Mail external Attachments/ sibling-dir handling ─────────────────


def _build_apple_layout(tmp_path, emlx_wrap, msg_bytes, numeric_id="12345"):
    """Create a realistic Apple Mail dir structure:
       <root>/Data/<n>/<m>/Messages/<numeric_id>.emlx
       <root>/Data/<n>/<m>/Attachments/<numeric_id>/<part>/<file>
    Returns the .emlx Path."""
    data_dir = tmp_path / "Data" / "0" / "0"
    msgs = data_dir / "Messages"
    msgs.mkdir(parents=True)
    emlx = msgs / f"{numeric_id}.emlx"
    emlx.write_bytes(emlx_wrap(msg_bytes))
    return emlx


class TestExternalAttachmentsDir:
    def test_returns_none_when_sibling_missing(self, tmp_path, msg_simple_text, emlx_wrap):
        emlx = _build_apple_layout(tmp_path, emlx_wrap, msg_simple_text)
        assert external_attachments_dir(emlx) is None

    def test_returns_path_when_sibling_exists(self, tmp_path, msg_simple_text, emlx_wrap):
        emlx = _build_apple_layout(tmp_path, emlx_wrap, msg_simple_text, "999")
        # Create the sibling Attachments/<id>/ directory
        adir = emlx.parent.parent / "Attachments" / "999"
        adir.mkdir(parents=True)
        assert external_attachments_dir(emlx) == adir


class TestExternalAttachmentFilenames:
    def test_lists_files_recursively(self, tmp_path, msg_simple_text, emlx_wrap):
        emlx = _build_apple_layout(tmp_path, emlx_wrap, msg_simple_text, "42")
        adir = emlx.parent.parent / "Attachments" / "42"
        (adir / "2.2").mkdir(parents=True)
        (adir / "2.4").mkdir(parents=True)
        (adir / "2.2" / "report.pdf").write_bytes(b"%PDF-")
        (adir / "2.4" / "photo.jpg").write_bytes(b"\xff\xd8\xff")
        names = external_attachment_filenames(emlx)
        assert set(names) == {"report.pdf", "photo.jpg"}

    def test_skips_smime_noise(self, tmp_path, msg_simple_text, emlx_wrap):
        """smime.p7s shouldn't pollute the listing — same rule as inline parts."""
        emlx = _build_apple_layout(tmp_path, emlx_wrap, msg_simple_text, "42")
        adir = emlx.parent.parent / "Attachments" / "42" / "1.2"
        adir.mkdir(parents=True)
        (adir / "real.pdf").write_bytes(b"%PDF-")
        (adir / "smime.p7s").write_bytes(b"crypto")
        names = external_attachment_filenames(emlx)
        assert names == ["real.pdf"]

    def test_skips_dotfiles(self, tmp_path, msg_simple_text, emlx_wrap):
        emlx = _build_apple_layout(tmp_path, emlx_wrap, msg_simple_text, "42")
        adir = emlx.parent.parent / "Attachments" / "42"
        adir.mkdir(parents=True)
        (adir / ".DS_Store").write_bytes(b"")
        (adir / "good.pdf").write_bytes(b"%PDF-")
        assert external_attachment_filenames(emlx) == ["good.pdf"]

    def test_returns_empty_when_dir_missing(self, tmp_path, msg_simple_text, emlx_wrap):
        emlx = _build_apple_layout(tmp_path, emlx_wrap, msg_simple_text, "42")
        assert external_attachment_filenames(emlx) == []


class TestParseEmlxIncludesExternal:
    def test_merges_external_filenames_into_record(self, tmp_path, msg_simple_text, emlx_wrap):
        """End-to-end: parse_emlx_file should include external attachments in
        the record's attachment_names + set has_attachments=1."""
        import json
        emlx = _build_apple_layout(tmp_path, emlx_wrap, msg_simple_text, "42")
        adir = emlx.parent.parent / "Attachments" / "42" / "2.2"
        adir.mkdir(parents=True)
        (adir / "external.pdf").write_bytes(b"%PDF-")

        record = parse_emlx_file(emlx, source_name="Inbox")
        assert record is not None
        names = json.loads(record["attachment_names"])
        assert "external.pdf" in names
        assert record["has_attachments"] == 1
        # source_path is stored so the extractor can find these files later
        assert record["source_path"] == str(emlx)

    def test_no_external_dir_still_works(self, tmp_path, msg_simple_text, emlx_wrap):
        emlx = _build_apple_layout(tmp_path, emlx_wrap, msg_simple_text, "42")
        record = parse_emlx_file(emlx, source_name="Inbox")
        assert record["source_path"] == str(emlx)
        # has_attachments depends only on the inline MIME tree
        import json
        assert json.loads(record["attachment_names"]) == []
