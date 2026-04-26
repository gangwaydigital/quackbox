"""Tests for calendar event extraction from emails."""
import email
import json
from email import policy

import pytest

from app import database
from app.services import calendar_extractor


@pytest.fixture
def calendar_db(tmp_path, monkeypatch):
    """Fresh DB with the extractor patched to use it."""
    db_path = tmp_path / "calendar-test.db"
    database.init_db(db_path)
    real_get_db = database.get_db

    def get_db_override(p=db_path):
        return real_get_db(p)
    monkeypatch.setattr(calendar_extractor, "get_db", get_db_override)
    return db_path


def _insert_email(db_path, *, raw_message, message_id="x@x.com"):
    with database.get_db(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO emails (message_id, raw_message) VALUES (?, ?)",
            (message_id, raw_message),
        )
        return cur.lastrowid


# ── extract_events_from_message ────────────────────────────────────────────


class TestExtractEventsFromMessage:
    def test_extracts_vevent_from_text_calendar_part(self, msg_with_calendar_invite):
        msg = email.message_from_bytes(msg_with_calendar_invite, policy=policy.compat32)
        events = calendar_extractor.extract_events_from_message(msg)
        assert len(events) == 1
        ev = events[0]
        assert ev["uid"] == "event-uid-123@example.com"
        assert ev["summary"] == "Project sync"
        assert ev["location"] == "Zoom"
        assert ev["description"] == "Weekly check-in"
        assert ev["status"] == "CONFIRMED"
        assert ev["method"] == "REQUEST"
        assert ev["source"] == "text/calendar"

    def test_organizer_and_attendees_parsed(self, msg_with_calendar_invite):
        msg = email.message_from_bytes(msg_with_calendar_invite, policy=policy.compat32)
        events = calendar_extractor.extract_events_from_message(msg)
        ev = events[0]
        assert "Alice" in ev["organizer"]
        assert "alice@example.com" in ev["organizer"]
        attendees = json.loads(ev["attendees"])
        assert len(attendees) == 2
        assert any("bob@example.com" in a for a in attendees)

    def test_dtstart_parsed_as_iso_with_timestamp(self, msg_with_calendar_invite):
        msg = email.message_from_bytes(msg_with_calendar_invite, policy=policy.compat32)
        ev = calendar_extractor.extract_events_from_message(msg)[0]
        assert ev["start_time"] == "2024-01-10T14:00:00+00:00"
        assert ev["end_time"] == "2024-01-10T15:00:00+00:00"
        assert ev["start_timestamp"] == 1704895200.0

    def test_simple_text_email_yields_no_events(self, msg_simple_text):
        msg = email.message_from_bytes(msg_simple_text, policy=policy.compat32)
        assert calendar_extractor.extract_events_from_message(msg) == []

    def test_handles_none_input(self):
        assert calendar_extractor.extract_events_from_message(None) == []

    def test_ics_attachment_extracted(self, tmp_path, emlx_wrap):
        """Some clients ship the calendar as an .ics attachment, not a
        text/calendar inline part."""
        raw = (
            b"From: a@x.com\r\n"
            b"To: b@x.com\r\n"
            b"Subject: Invite\r\n"
            b'Message-ID: <a@x.com>\r\n'
            b"MIME-Version: 1.0\r\n"
            b'Content-Type: multipart/mixed; boundary="MIX"\r\n\r\n'
            b"--MIX\r\n"
            b"Content-Type: text/plain\r\n\r\n"
            b"See attached invite.\r\n"
            b"--MIX\r\n"
            b'Content-Type: text/plain; name="meeting.ics"\r\n'
            b'Content-Disposition: attachment; filename="meeting.ics"\r\n\r\n'
            b"BEGIN:VCALENDAR\r\n"
            b"VERSION:2.0\r\n"
            b"BEGIN:VEVENT\r\n"
            b"UID:abc-123\r\n"
            b"DTSTART:20240601T090000Z\r\n"
            b"DTEND:20240601T100000Z\r\n"
            b"SUMMARY:All-hands\r\n"
            b"END:VEVENT\r\n"
            b"END:VCALENDAR\r\n"
            b"--MIX--\r\n"
        )
        msg = email.message_from_bytes(raw, policy=policy.compat32)
        events = calendar_extractor.extract_events_from_message(msg)
        assert len(events) == 1
        assert events[0]["summary"] == "All-hands"
        assert events[0]["source"] == "ics_attachment"

    def test_garbage_calendar_blob_skipped_not_raised(self):
        """Malformed iCal must not blow up the extractor."""
        # text/calendar part with invalid body
        raw = (
            b"From: a@x.com\r\nMIME-Version: 1.0\r\n"
            b'Content-Type: multipart/alternative; boundary="X"\r\n\r\n'
            b"--X\r\n"
            b"Content-Type: text/calendar\r\n\r\n"
            b"this is not a real ics file at all\r\n"
            b"--X--\r\n"
        )
        msg = email.message_from_bytes(raw, policy=policy.compat32)
        # Should return [] rather than raise
        assert calendar_extractor.extract_events_from_message(msg) == []


# ── index_events_for_email + table integration ─────────────────────────────


class TestIndexEventsForEmail:
    def test_persists_events_for_one_email(self, calendar_db, msg_with_calendar_invite):
        eid = _insert_email(calendar_db, raw_message=msg_with_calendar_invite, message_id="invite-1")
        n = calendar_extractor.index_events_for_email(eid)
        assert n == 1
        with database.get_db(calendar_db) as conn:
            row = conn.execute(
                "SELECT summary, location, status FROM calendar_events WHERE email_id = ?",
                (eid,),
            ).fetchone()
        assert row["summary"] == "Project sync"
        assert row["location"] == "Zoom"
        assert row["status"] == "CONFIRMED"

    def test_idempotent_re_indexing(self, calendar_db, msg_with_calendar_invite):
        eid = _insert_email(calendar_db, raw_message=msg_with_calendar_invite, message_id="invite-1")
        calendar_extractor.index_events_for_email(eid)
        calendar_extractor.index_events_for_email(eid)
        with database.get_db(calendar_db) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM calendar_events WHERE email_id = ?", (eid,),
            ).fetchone()[0]
        # UNIQUE(email_id, uid) means re-indexing replaces, doesn't duplicate
        assert count == 1

    def test_no_raw_message_returns_zero(self, calendar_db):
        eid = _insert_email(calendar_db, raw_message=None, message_id="no-raw")
        assert calendar_extractor.index_events_for_email(eid) == 0

    def test_missing_email_returns_zero(self, calendar_db):
        assert calendar_extractor.index_events_for_email(99999) == 0


class TestListEvents:
    def test_lists_with_pagination(self, calendar_db, msg_with_calendar_invite, msg_simple_text):
        eid = _insert_email(calendar_db, raw_message=msg_with_calendar_invite, message_id="i1")
        _insert_email(calendar_db, raw_message=msg_simple_text, message_id="t1")
        calendar_extractor.index_events_for_email(eid)

        result = calendar_extractor.list_events(upcoming_only=False)
        assert result["total"] == 1
        assert result["items"][0]["summary"] == "Project sync"
        # attendees comes back as a list (re-deserialized)
        assert isinstance(result["items"][0]["attendees"], list)

    def test_search_filters_by_summary(self, calendar_db, msg_with_calendar_invite):
        eid = _insert_email(calendar_db, raw_message=msg_with_calendar_invite, message_id="i1")
        calendar_extractor.index_events_for_email(eid)
        assert calendar_extractor.list_events(search="project")["total"] == 1
        assert calendar_extractor.list_events(search="nonsense")["total"] == 0

    def test_get_event_stats_smoke(self, calendar_db, msg_with_calendar_invite):
        eid = _insert_email(calendar_db, raw_message=msg_with_calendar_invite, message_id="i1")
        calendar_extractor.index_events_for_email(eid)
        stats = calendar_extractor.get_event_stats()
        assert stats["total_events"] == 1
        assert stats["emails_with_events"] == 1
        # Event was in the past (Jan 2024) — upcoming should be 0
        assert stats["upcoming_events"] == 0
