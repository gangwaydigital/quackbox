"""
Tests for the .emlx raw_message migration.

The migration repairs rows whose raw_message contains the full .emlx file
(byte-count prefix + RFC822 + plist trailer) by trimming back to the RFC822
portion. It must be idempotent and must leave correct rows untouched.
"""
import email
from email import policy

from app.database import _migrate_emlx_raw_message


def _insert_email(conn, *, raw_message: bytes, message_id: str = "x@x.com"):
    """Insert one row directly so we can stage the broken raw_message state."""
    cur = conn.execute(
        "INSERT INTO emails (message_id, raw_message) VALUES (?, ?)",
        (message_id, raw_message),
    )
    conn.commit()
    return cur.lastrowid


class TestEmlxMigration:
    def test_repairs_broken_emlx_row(self, fresh_db, msg_smime_signed, emlx_wrap):
        """A row holding a full .emlx blob should be trimmed to the RFC822 portion."""
        broken_blob = emlx_wrap(msg_smime_signed, with_plist_trailer=True)
        rid = _insert_email(fresh_db, raw_message=broken_blob, message_id="signed@x")

        _migrate_emlx_raw_message(fresh_db)
        fresh_db.commit()

        fixed = fresh_db.execute(
            "SELECT raw_message FROM emails WHERE id = ?", (rid,)
        ).fetchone()["raw_message"]

        # After repair, re-parsing must reveal the multipart structure
        msg = email.message_from_bytes(fixed, policy=policy.compat32)
        assert msg.is_multipart()
        ctypes = [p.get_content_type() for p in msg.walk()]
        assert "application/pkcs7-signature" in ctypes
        assert "text/plain" in ctypes

    def test_leaves_clean_rfc822_rows_alone(self, fresh_db, msg_simple_text):
        """A row already in RFC822 form must not be mangled by the migration."""
        rid = _insert_email(fresh_db, raw_message=msg_simple_text, message_id="clean@x")

        _migrate_emlx_raw_message(fresh_db)
        fresh_db.commit()

        after = fresh_db.execute(
            "SELECT raw_message FROM emails WHERE id = ?", (rid,)
        ).fetchone()["raw_message"]
        assert bytes(after) == msg_simple_text

    def test_idempotent_second_run_is_a_noop(self, fresh_db, msg_smime_signed, emlx_wrap):
        """Running the migration twice must not corrupt rows that were already fixed."""
        broken_blob = emlx_wrap(msg_smime_signed)
        rid = _insert_email(fresh_db, raw_message=broken_blob, message_id="signed@x")

        _migrate_emlx_raw_message(fresh_db)
        fresh_db.commit()
        first = bytes(fresh_db.execute(
            "SELECT raw_message FROM emails WHERE id = ?", (rid,)
        ).fetchone()["raw_message"])

        _migrate_emlx_raw_message(fresh_db)
        fresh_db.commit()
        second = bytes(fresh_db.execute(
            "SELECT raw_message FROM emails WHERE id = ?", (rid,)
        ).fetchone()["raw_message"])

        assert first == second

    def test_handles_padded_byte_count_line(self, fresh_db, msg_simple_text):
        """Apple Mail pads the byte-count line with trailing spaces — must still match."""
        bc = len(msg_simple_text)
        # Hand-build a blob with extra padding spaces before the newline
        padded = f"{bc}     \n".encode() + msg_simple_text + b"trailing junk"
        rid = _insert_email(fresh_db, raw_message=padded, message_id="padded@x")

        _migrate_emlx_raw_message(fresh_db)
        fresh_db.commit()

        fixed = bytes(fresh_db.execute(
            "SELECT raw_message FROM emails WHERE id = ?", (rid,)
        ).fetchone()["raw_message"])
        assert fixed == msg_simple_text

    def test_skips_null_raw_message(self, fresh_db):
        _insert_email(fresh_db, raw_message=None, message_id="null@x")
        # Just must not raise
        _migrate_emlx_raw_message(fresh_db)
