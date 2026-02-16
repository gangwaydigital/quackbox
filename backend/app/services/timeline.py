"""Timeline milestones — key moments in the email archive."""
from collections import defaultdict
from app.database import get_db


def get_timeline_milestones():
    """
    Find notable milestones in the email archive:
    - First/last email
    - Busiest days/months
    - First email from top contacts
    - Longest threads started
    - Years with biggest volume jumps
    """
    milestones = []

    with get_db() as conn:
        # First and last email
        first = conn.execute(
            "SELECT id, subject, sender_name, sender_email, date_sent FROM emails WHERE date_sent IS NOT NULL ORDER BY date_timestamp ASC LIMIT 1"
        ).fetchone()
        if first:
            milestones.append({"type": "first_email", "date": first["date_sent"], "title": "First Email",
                "description": f"From {first['sender_name'] or first['sender_email']}: {first['subject'] or '(no subject)'}",
                "email_id": first["id"], "icon": "rocket"})

        last = conn.execute(
            "SELECT id, subject, sender_name, sender_email, date_sent FROM emails WHERE date_sent IS NOT NULL ORDER BY date_timestamp DESC LIMIT 1"
        ).fetchone()
        if last:
            milestones.append({"type": "last_email", "date": last["date_sent"], "title": "Most Recent Email",
                "description": f"From {last['sender_name'] or last['sender_email']}: {last['subject'] or '(no subject)'}",
                "email_id": last["id"], "icon": "mail"})

        # Busiest days
        busiest_days = conn.execute("""
            SELECT strftime('%Y-%m-%d', date_sent) as day, COUNT(*) as count
            FROM emails WHERE date_sent IS NOT NULL
            GROUP BY day ORDER BY count DESC LIMIT 5
        """).fetchall()
        for i, row in enumerate(busiest_days):
            milestones.append({"type": "busy_day", "date": row["day"] + "T12:00:00",
                "title": f"{'Busiest' if i == 0 else f'#{i+1} Busiest'} Day",
                "description": f"{row['count']} emails on {row['day']}",
                "icon": "zap", "count": row["count"]})

        # First email from top 10 contacts
        top_contacts = conn.execute("""
            SELECT sender_email, sender_name, COUNT(*) as cnt
            FROM emails WHERE sender_email != '' AND sender_email IS NOT NULL
            GROUP BY sender_email ORDER BY cnt DESC LIMIT 10
        """).fetchall()
        for c in top_contacts:
            fe = conn.execute("""
                SELECT id, subject, date_sent FROM emails
                WHERE sender_email = ? AND date_sent IS NOT NULL
                ORDER BY date_timestamp ASC LIMIT 1
            """, (c["sender_email"],)).fetchone()
            if fe:
                milestones.append({"type": "first_contact", "date": fe["date_sent"],
                    "title": f"First from {c['sender_name'] or c['sender_email']}",
                    "description": f"{c['sender_name'] or c['sender_email']} ({c['cnt']} total emails): {fe['subject'] or '(no subject)'}",
                    "email_id": fe["id"], "contact": c["sender_email"], "icon": "user-plus"})

        # Biggest threads started
        big_threads = conn.execute("""
            SELECT t.id, t.subject_normalized, t.message_count, t.participant_count, t.first_date
            FROM threads t WHERE t.message_count >= 5
            ORDER BY t.message_count DESC LIMIT 5
        """).fetchall()
        for t in big_threads:
            milestones.append({"type": "big_thread", "date": t["first_date"],
                "title": f"Thread: {t['subject_normalized'] or '(no subject)'}",
                "description": f"{t['message_count']} messages, {t['participant_count']} participants",
                "thread_id": t["id"], "icon": "message-square"})

        # Year-over-year volume milestones
        yearly = conn.execute("""
            SELECT strftime('%Y', date_sent) as year, COUNT(*) as count
            FROM emails WHERE date_sent IS NOT NULL
            GROUP BY year ORDER BY year ASC
        """).fetchall()
        prev = None
        for row in yearly:
            if prev and prev["count"] > 0:
                growth = ((row["count"] - prev["count"]) / prev["count"]) * 100
                if growth > 50:
                    milestones.append({"type": "volume_jump", "date": f"{row['year']}-06-15T00:00:00",
                        "title": f"Volume Surge in {row['year']}",
                        "description": f"{int(growth)}% increase — from {prev['count']} to {row['count']} emails",
                        "icon": "trending-up"})
                elif growth < -40:
                    milestones.append({"type": "volume_drop", "date": f"{row['year']}-06-15T00:00:00",
                        "title": f"Volume Drop in {row['year']}",
                        "description": f"{int(abs(growth))}% decrease — from {prev['count']} to {row['count']} emails",
                        "icon": "trending-down"})
            prev = row

        # Email count milestones (1000, 5000, 10000, etc)
        thresholds = [1000, 5000, 10000, 25000, 50000]
        for threshold in thresholds:
            row = conn.execute("""
                SELECT id, subject, sender_name, sender_email, date_sent FROM emails
                WHERE date_sent IS NOT NULL
                ORDER BY date_timestamp ASC
                LIMIT 1 OFFSET ?
            """, (threshold - 1,)).fetchone()
            if row:
                milestones.append({"type": "count_milestone", "date": row["date_sent"],
                    "title": f"Email #{threshold:,}",
                    "description": f"From {row['sender_name'] or row['sender_email']}: {row['subject'] or '(no subject)'}",
                    "email_id": row["id"], "icon": "award"})

    # Sort by date
    milestones.sort(key=lambda m: m.get("date", ""))
    return milestones


def get_notification_counts():
    """Get counts for notification badges."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
        threads = conn.execute("SELECT COUNT(*) FROM threads").fetchone()[0]
        threaded = conn.execute("SELECT COUNT(*) FROM emails WHERE thread_group_id IS NOT NULL").fetchone()[0]
        embedded = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        topics = conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0]

        return {
            "total_emails": total,
            "threaded_emails": threaded,
            "unthreaded_emails": total - threaded,
            "threads": threads,
            "embedded_emails": embedded,
            "unembedded_emails": total - embedded,
            "topics": topics,
            "needs_threads": threads == 0 and total > 0,
            "needs_embeddings": embedded == 0 and total > 0,
            "needs_topics": topics == 0 and total > 0,
        }
