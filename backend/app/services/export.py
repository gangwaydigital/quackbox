"""
Export service. Generates CSV files from email data.
"""
import csv
import io
from app.database import get_db


def export_emails_csv(
    sender_email=None, date_from=None, date_to=None,
    mbox_source=None, subject_contains=None, limit=10000
) -> str:
    """Export filtered emails as CSV string."""
    conditions = []
    params = []

    if sender_email:
        conditions.append("sender_email LIKE ?")
        params.append(f"%{sender_email}%")
    if date_from:
        conditions.append("date_sent >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("date_sent <= ?")
        params.append(date_to)
    if mbox_source:
        conditions.append("mbox_source = ?")
        params.append(mbox_source)
    if subject_contains:
        conditions.append("subject LIKE ?")
        params.append(f"%{subject_contains}%")

    where = " AND ".join(conditions) if conditions else "1=1"

    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT id, message_id, subject, sender_name, sender_email,
                   date_sent, mbox_source, has_attachments, thread_group_id
            FROM emails
            WHERE {where}
            ORDER BY date_timestamp DESC
            LIMIT ?
        """, params + [limit]).fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Message-ID", "Subject", "Sender Name", "Sender Email",
                         "Date", "Mailbox", "Has Attachments", "Thread ID"])
        for r in rows:
            writer.writerow([r["id"], r["message_id"], r["subject"], r["sender_name"],
                           r["sender_email"], r["date_sent"], r["mbox_source"],
                           r["has_attachments"], r["thread_group_id"]])
        return output.getvalue()


def export_contacts_csv(limit=5000) -> str:
    """Export contact list as CSV."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT sender_email, MAX(sender_name) as name,
                   COUNT(*) as total_emails,
                   MIN(date_sent) as first_seen, MAX(date_sent) as last_seen,
                   COUNT(DISTINCT thread_group_id) as threads,
                   COUNT(DISTINCT mbox_source) as mailboxes
            FROM emails
            WHERE sender_email != '' AND sender_email IS NOT NULL
            GROUP BY sender_email
            ORDER BY total_emails DESC
            LIMIT ?
        """, (limit,)).fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Email", "Name", "Total Emails", "First Seen", "Last Seen", "Threads", "Mailboxes"])
        for r in rows:
            writer.writerow([r["sender_email"], r["name"], r["total_emails"],
                           r["first_seen"], r["last_seen"], r["threads"], r["mailboxes"]])
        return output.getvalue()


def export_threads_csv(min_messages=2, limit=5000) -> str:
    """Export thread list as CSV."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT t.id, t.subject_normalized, t.message_count, t.participant_count,
                   t.first_date, t.last_date, t.duration_seconds, t.mailbox_sources
            FROM threads t
            WHERE t.message_count >= ?
            ORDER BY t.last_date DESC
            LIMIT ?
        """, (min_messages, limit)).fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Thread ID", "Subject", "Messages", "Participants",
                         "First Date", "Last Date", "Duration (hours)", "Mailboxes"])
        for r in rows:
            hours = round((r["duration_seconds"] or 0) / 3600, 1)
            writer.writerow([r["id"], r["subject_normalized"], r["message_count"],
                           r["participant_count"], r["first_date"], r["last_date"],
                           hours, r["mailbox_sources"]])
        return output.getvalue()
