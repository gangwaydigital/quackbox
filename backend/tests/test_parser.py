"""Tests for the .mbox parser — happy path and malformed-message handling."""
from app.services.parser import parse_mbox, count_messages


class TestParseMbox:
    def test_yields_records_for_each_message(self, mbox_file):
        records = list(parse_mbox(mbox_file))
        assert len(records) == 2

    def test_record_has_required_fields(self, mbox_file):
        record = next(parse_mbox(mbox_file))
        for key in (
            "message_id", "subject", "sender_name", "sender_email",
            "recipients", "date_sent", "date_timestamp",
            "body_text", "headers", "mbox_source",
            "has_attachments", "attachment_names", "raw_message",
        ):
            assert key in record, f"missing field {key!r}"

    def test_simple_message_fields(self, mbox_file):
        record = next(parse_mbox(mbox_file))
        assert record["message_id"] == "simple-1@example.com"
        assert record["subject"] == "Hello"
        assert record["sender_name"] == "Alice"
        assert record["sender_email"] == "alice@example.com"
        assert record["has_attachments"] is False
        assert "Just a plain text message." in record["body_text"]

    def test_attachment_message_picks_up_attachment(self, mbox_file):
        records = list(parse_mbox(mbox_file))
        attachment_record = records[1]
        assert attachment_record["has_attachments"] is True
        # attachment_names is JSON-encoded
        import json
        names = json.loads(attachment_record["attachment_names"])
        assert names == ["quarterly.pdf"]

    def test_raw_message_round_trips(self, mbox_file):
        """raw_message should re-parse as the same multipart structure."""
        import email
        from email import policy

        records = list(parse_mbox(mbox_file))
        atta = records[1]
        msg = email.message_from_bytes(atta["raw_message"], policy=policy.compat32)
        assert msg.is_multipart()
        # Should find both the text part and the pdf attachment
        ctypes = [p.get_content_type() for p in msg.walk()]
        assert "application/pdf" in ctypes

    def test_empty_mbox_yields_nothing(self, tmp_path):
        empty = tmp_path / "empty.mbox"
        empty.write_bytes(b"")
        assert list(parse_mbox(empty)) == []

    def test_malformed_message_is_skipped_not_raised(self, tmp_path):
        """A truncated message must not blow up the entire parse."""
        path = tmp_path / "broken.mbox"
        # First message valid, second truncated mid-headers
        path.write_bytes(
            b"From a@x.com Mon Jan 1 12:00:00 2024\r\n"
            b"From: a@x.com\r\nSubject: Good\r\nMessage-ID: <ok@x>\r\n\r\nbody\r\n"
            b"From b@x.com Mon Jan 2 12:00:00 2024\r\n"
            b"From: b@x.com\r\nSubject"  # truncated header
        )
        records = list(parse_mbox(path))
        # Even a totally garbage second chunk should still allow message 1 to come through
        assert len(records) >= 1
        assert records[0]["message_id"] == "ok@x"


class TestCountMessages:
    def test_counts_match_parse(self, mbox_file):
        assert count_messages(mbox_file) == len(list(parse_mbox(mbox_file)))
