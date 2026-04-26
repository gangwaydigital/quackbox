"""Tests for email_utils — header decoding, address parsing, attachment filtering."""
import email
from email import policy

import pytest

from app.utils.email_utils import (
    decode_email_header,
    parse_email_address,
    parse_recipient_list,
    parse_email_date,
    extract_attachments,
    extract_thread_id,
    _is_noise_attachment,
    NOISE_ATTACHMENT_FILENAMES,
)


class TestDecodeEmailHeader:
    def test_plain_text(self):
        assert decode_email_header("Plain text") == "Plain text"

    def test_rfc2047_base64_utf8(self):
        # "Hello" base64-encoded as UTF-8
        assert decode_email_header("=?UTF-8?B?SGVsbG8=?=") == "Hello"

    def test_rfc2047_quoted_printable(self):
        assert decode_email_header("=?utf-8?Q?Caf=C3=A9?=") == "Café"

    def test_empty_returns_empty_string(self):
        assert decode_email_header("") == ""
        assert decode_email_header(None) == ""

    def test_strips_surrounding_whitespace(self):
        assert decode_email_header("  hello  ") == "hello"


class TestParseEmailAddress:
    def test_full_form(self):
        assert parse_email_address("Alice <alice@example.com>") == ("Alice", "alice@example.com")

    def test_bare_address(self):
        assert parse_email_address("alice@example.com") == ("", "alice@example.com")

    def test_email_lowercased(self):
        assert parse_email_address("Alice <ALICE@Example.COM>") == ("Alice", "alice@example.com")

    def test_encoded_name(self):
        name, em = parse_email_address("=?utf-8?Q?Caf=C3=A9?= <cafe@example.com>")
        assert name == "Café"
        assert em == "cafe@example.com"

    def test_empty_returns_empty_tuple(self):
        assert parse_email_address("") == ("", "")
        assert parse_email_address(None) == ("", "")


class TestParseRecipientList:
    def test_single_recipient(self, msg_simple_text):
        msg = email.message_from_bytes(msg_simple_text, policy=policy.compat32)
        rs = parse_recipient_list(msg, "To")
        assert rs == [{"name": "Bob", "email": "bob@example.com", "type": "to"}]

    def test_missing_header(self, msg_simple_text):
        msg = email.message_from_bytes(msg_simple_text, policy=policy.compat32)
        assert parse_recipient_list(msg, "Cc") == []


class TestParseEmailDate:
    def test_rfc2822_with_offset(self):
        iso, ts = parse_email_date("Mon, 1 Jan 2024 12:00:00 +0000")
        assert iso == "2024-01-01T12:00:00+00:00"
        assert ts == 1704110400.0

    def test_rfc2822_naive_treated_as_utc(self):
        iso, ts = parse_email_date("Mon, 1 Jan 2024 12:00:00")
        assert iso == "2024-01-01T12:00:00+00:00"

    def test_garbage_returns_none(self):
        assert parse_email_date("not a date") == (None, None)

    def test_empty_returns_none(self):
        assert parse_email_date("") == (None, None)
        assert parse_email_date(None) == (None, None)


class TestExtractAttachments:
    def test_simple_text_has_no_attachments(self, msg_simple_text):
        msg = email.message_from_bytes(msg_simple_text, policy=policy.compat32)
        has, names = extract_attachments(msg)
        assert has is False
        assert names == []

    def test_real_attachment_is_extracted(self, msg_with_attachment):
        msg = email.message_from_bytes(msg_with_attachment, policy=policy.compat32)
        has, names = extract_attachments(msg)
        assert has is True
        assert names == ["quarterly.pdf"]

    def test_smime_signature_is_filtered(self, msg_smime_signed):
        """The s/mime signature is not user content and should be hidden."""
        msg = email.message_from_bytes(msg_smime_signed, policy=policy.compat32)
        has, names = extract_attachments(msg)
        assert has is False
        assert names == []


class TestNoiseAttachmentDetection:
    @pytest.mark.parametrize("name", sorted(NOISE_ATTACHMENT_FILENAMES))
    def test_known_noise_filenames(self, name):
        assert _is_noise_attachment(name) is True

    def test_real_filename_passes_through(self):
        assert _is_noise_attachment("report.pdf") is False
        assert _is_noise_attachment("photo.jpg") is False

    def test_pkcs7_content_type_filtered_even_with_other_filename(self):
        # Some clients name the signature differently; content-type is the safety net
        assert _is_noise_attachment("signature.bin", "application/pkcs7-signature") is True
        assert _is_noise_attachment("signature.bin", "application/x-pkcs7-signature") is True

    def test_empty_filename(self):
        assert _is_noise_attachment("") is False
        assert _is_noise_attachment(None) is False

    def test_case_insensitive(self):
        assert _is_noise_attachment("SMIME.P7S") is True
        assert _is_noise_attachment("Smime.P7s") is True


class TestExtractThreadId:
    def test_in_reply_to(self):
        msg = email.message_from_string(
            "From: a@x.com\nIn-Reply-To: <parent-1@example.com>\n\nbody",
            policy=policy.compat32,
        )
        assert extract_thread_id(msg) == "parent-1@example.com"

    def test_references_takes_first(self):
        msg = email.message_from_string(
            "From: a@x.com\nReferences: <root-1@x.com> <child-1@x.com>\n\nbody",
            policy=policy.compat32,
        )
        assert extract_thread_id(msg) == "root-1@x.com"

    def test_references_overrides_in_reply_to(self):
        msg = email.message_from_string(
            "From: a@x.com\nReferences: <root-1@x.com>\nIn-Reply-To: <other@x.com>\n\nbody",
            policy=policy.compat32,
        )
        assert extract_thread_id(msg) == "root-1@x.com"

    def test_no_threading_returns_none(self):
        msg = email.message_from_string("From: a@x.com\n\nbody", policy=policy.compat32)
        assert extract_thread_id(msg) is None
