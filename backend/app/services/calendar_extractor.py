"""
Calendar event extraction.

Pulls events out of two places in an email:
  - text/calendar MIME parts (the standard way meeting invites travel)
  - .ics attachments (some clients ship them as a regular attachment)

Each VEVENT is rolled into a row in the calendar_events table, keyed by
(email_id, uid) so re-indexing is idempotent and we don't double-count
recurring updates of the same invite.
"""
from __future__ import annotations

import email as email_pkg
import json
import time
from datetime import date, datetime, timezone
from email import policy
from typing import Iterable, Optional

from app.database import get_db
from app.logging_config import get_logger

log = get_logger("calendar")


def _to_iso_and_ts(value) -> tuple[Optional[str], Optional[float]]:
    """Coerce an icalendar dtstart/dtend value into (iso_string, unix_ts)."""
    if value is None:
        return None, None
    # icalendar gives us datetime, date, or vDDDTypes-wrapped values
    dt = value.dt if hasattr(value, "dt") else value
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat(), dt.timestamp()
    if isinstance(dt, date):
        # All-day event — represent as midnight UTC
        d = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
        return d.isoformat(), d.timestamp()
    return str(dt), None


def _attendee_str(att) -> str:
    """Render an icalendar attendee value as 'Name <email>' or just the email."""
    if att is None:
        return ""
    raw = str(att)
    cn = att.params.get("CN") if hasattr(att, "params") else None
    em = raw.replace("MAILTO:", "").replace("mailto:", "")
    return f"{cn} <{em}>" if cn else em


def _extract_vevents_from_blob(blob: bytes) -> list[dict]:
    """Parse iCal bytes into a list of dicts ready for DB insert."""
    try:
        from icalendar import Calendar
    except ImportError:
        log.warning("icalendar package not installed — cannot extract events")
        return []
    try:
        cal = Calendar.from_ical(blob)
    except Exception as e:
        log.debug("Could not parse iCal blob: %s", e)
        return []

    method = str(cal.get("method") or "")
    events: list[dict] = []
    for component in cal.walk("VEVENT"):
        try:
            uid = str(component.get("uid") or "")
            summary = str(component.get("summary") or "").strip()
            description = str(component.get("description") or "").strip()
            location = str(component.get("location") or "").strip()
            organizer = _attendee_str(component.get("organizer"))
            status = str(component.get("status") or "")
            attendees_field = component.get("attendee")
            if attendees_field is None:
                attendees: list[str] = []
            elif isinstance(attendees_field, list):
                attendees = [_attendee_str(a) for a in attendees_field if a]
            else:
                attendees = [_attendee_str(attendees_field)]

            start_iso, start_ts = _to_iso_and_ts(component.get("dtstart"))
            end_iso, end_ts = _to_iso_and_ts(component.get("dtend"))

            events.append({
                "uid": uid or None,
                "summary": summary or None,
                "description": description or None,
                "location": location or None,
                "organizer": organizer or None,
                "attendees": json.dumps(attendees),
                "start_time": start_iso,
                "end_time": end_iso,
                "start_timestamp": start_ts,
                "end_timestamp": end_ts,
                "status": status or None,
                "method": method or None,
            })
        except Exception:
            log.exception("Failed to parse a VEVENT component; skipping")
            continue
    return events


def extract_events_from_message(msg) -> list[dict]:
    """
    Walk a parsed email message and pull every VEVENT from its calendar
    parts. Returns a list of event dicts (each augmented with `source`
    indicating where it came from).
    """
    if msg is None:
        return []

    events: list[dict] = []

    if msg.is_multipart():
        parts = list(msg.walk())
    else:
        parts = [msg]

    for part in parts:
        ct = (part.get_content_type() or "").lower()
        filename = (part.get_filename() or "").lower()

        is_ical_part = ct in ("text/calendar", "application/ics")
        is_ics_attachment = filename.endswith(".ics")

        if not (is_ical_part or is_ics_attachment):
            continue

        payload = part.get_payload(decode=True)
        if not payload:
            continue

        source = "text/calendar" if is_ical_part else "ics_attachment"
        for ev in _extract_vevents_from_blob(payload):
            ev["source"] = source
            events.append(ev)

    return events


def index_events_for_email(email_id: int) -> int:
    """
    Extract events from a single email's stored raw_message and persist them.
    Returns the number of events written.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT raw_message FROM emails WHERE id = ?", (email_id,)
        ).fetchone()
        if not row or not row["raw_message"]:
            return 0
        try:
            msg = email_pkg.message_from_bytes(bytes(row["raw_message"]), policy=policy.compat32)
        except Exception:
            return 0

        events = extract_events_from_message(msg)
        if not events:
            return 0

        for ev in events:
            conn.execute(
                """
                INSERT OR REPLACE INTO calendar_events
                  (email_id, uid, summary, description, location, organizer,
                   attendees, start_time, end_time, start_timestamp, end_timestamp,
                   status, method, source)
                VALUES (:email_id, :uid, :summary, :description, :location, :organizer,
                        :attendees, :start_time, :end_time, :start_timestamp, :end_timestamp,
                        :status, :method, :source)
                """,
                {**ev, "email_id": email_id},
            )
        return len(events)


def index_all_calendar_events(batch_size: int = 200) -> dict:
    """
    Scan every email with a stored raw_message for calendar parts and persist
    the events. Idempotent — UNIQUE(email_id, uid) means re-indexing won't
    duplicate. Returns processing stats.
    """
    start = time.time()
    scanned = 0
    events_indexed = 0
    emails_with_events = 0

    with get_db() as conn:
        # Only consider emails likely to carry calendar data: those whose
        # headers / body mention text/calendar OR have an .ics attachment.
        # Cheap heuristic: scan all emails with raw_message and let the
        # extractor decide. For very large archives this could be optimized
        # with a Content-Type LIKE filter, but raw_message is text-ish so
        # SQLite LIKE on it is slow. Skip that for now.
        rows = conn.execute(
            "SELECT id, raw_message FROM emails WHERE raw_message IS NOT NULL"
        ).fetchall()
        log.info("📅 Scanning %d emails for calendar events…", len(rows))

        for i, row in enumerate(rows):
            scanned += 1
            try:
                msg = email_pkg.message_from_bytes(bytes(row["raw_message"]), policy=policy.compat32)
            except Exception:
                continue
            events = extract_events_from_message(msg)
            if not events:
                continue
            emails_with_events += 1
            for ev in events:
                try:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO calendar_events
                          (email_id, uid, summary, description, location, organizer,
                           attendees, start_time, end_time, start_timestamp, end_timestamp,
                           status, method, source)
                        VALUES (:email_id, :uid, :summary, :description, :location, :organizer,
                                :attendees, :start_time, :end_time, :start_timestamp, :end_timestamp,
                                :status, :method, :source)
                        """,
                        {**ev, "email_id": row["id"]},
                    )
                    events_indexed += 1
                except Exception:
                    log.exception("Failed to insert event for email %d", row["id"])

            if (i + 1) % batch_size == 0:
                conn.commit()

    duration = round(time.time() - start, 2)
    log.info("✅ Calendar indexing done: %d events from %d emails (scanned %d, %.1fs)",
             events_indexed, emails_with_events, scanned, duration)
    return {
        "scanned": scanned,
        "emails_with_events": emails_with_events,
        "events_indexed": events_indexed,
        "duration_seconds": duration,
    }


def list_events(
    upcoming_only: bool = False,
    page: int = 1,
    page_size: int = 50,
    search: Optional[str] = None,
) -> dict:
    """List calendar events with simple paging and optional filters."""
    conditions = []
    params: dict = {}

    if upcoming_only:
        conditions.append("start_timestamp >= :now")
        params["now"] = time.time()

    if search:
        conditions.append("(LOWER(summary) LIKE :pat OR LOWER(location) LIKE :pat OR LOWER(organizer) LIKE :pat)")
        params["pat"] = f"%{search.lower()}%"

    where = " AND ".join(conditions) if conditions else "1=1"
    offset = (page - 1) * page_size

    with get_db() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM calendar_events WHERE {where}", params
        ).fetchone()[0]

        order = "start_timestamp ASC" if upcoming_only else "start_timestamp DESC"
        rows = conn.execute(
            f"""
            SELECT id, email_id, uid, summary, description, location, organizer,
                   attendees, start_time, end_time, status, method, source
            FROM calendar_events
            WHERE {where}
            ORDER BY {order} NULLS LAST
            LIMIT :ps OFFSET :off
            """,
            {**params, "ps": page_size, "off": offset},
        ).fetchall()

        items = []
        for row in rows:
            d = dict(row)
            try:
                d["attendees"] = json.loads(d.get("attendees") or "[]")
            except Exception:
                d["attendees"] = []
            items.append(d)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }


def get_event_stats() -> dict:
    """Quick counts for the UI header."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM calendar_events").fetchone()[0]
        upcoming = conn.execute(
            "SELECT COUNT(*) FROM calendar_events WHERE start_timestamp >= ?",
            (time.time(),),
        ).fetchone()[0]
        with_emails = conn.execute(
            "SELECT COUNT(DISTINCT email_id) FROM calendar_events"
        ).fetchone()[0]
        return {
            "total_events": total,
            "upcoming_events": upcoming,
            "emails_with_events": with_emails,
        }
