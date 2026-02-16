"""
Analytics service.

Pre-computes and caches dashboard data: volume trends,
contact rankings, activity heatmaps, and AI-generated insights.
"""

import json
import time
from collections import defaultdict
from datetime import datetime

from app.database import get_db


def email_volume_by_month() -> list[dict]:
    """Monthly email counts, optionally split by top mailboxes."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                strftime('%Y-%m', date_sent) as month,
                mbox_source,
                COUNT(*) as count
            FROM emails
            WHERE date_sent IS NOT NULL
            GROUP BY month, mbox_source
            ORDER BY month ASC
        """).fetchall()

        # Aggregate into {month: {source: count, total: count}}
        months = defaultdict(lambda: defaultdict(int))
        for r in rows:
            if r["month"]:
                months[r["month"]][r["mbox_source"] or "Unknown"] += r["count"]
                months[r["month"]]["_total"] += r["count"]

        result = []
        for month in sorted(months.keys()):
            entry = {"month": month, "total": months[month]["_total"]}
            # Include top sources
            sources = {k: v for k, v in months[month].items() if k != "_total"}
            top = sorted(sources.items(), key=lambda x: -x[1])[:5]
            for name, count in top:
                entry[name] = count
            result.append(entry)

        return result


def top_contacts(limit: int = 20) -> list[dict]:
    """Top senders by volume with monthly sparkline data."""
    with get_db() as conn:
        # Get top senders
        senders = conn.execute("""
            SELECT sender_email, sender_name, COUNT(*) as total,
                   MIN(date_sent) as first_seen, MAX(date_sent) as last_seen
            FROM emails
            WHERE sender_email != '' AND sender_email IS NOT NULL
            GROUP BY sender_email
            ORDER BY total DESC
            LIMIT ?
        """, (limit,)).fetchall()

        results = []
        for s in senders:
            # Get monthly sparkline for this sender
            sparkline = conn.execute("""
                SELECT strftime('%Y-%m', date_sent) as month, COUNT(*) as count
                FROM emails
                WHERE sender_email = ? AND date_sent IS NOT NULL
                GROUP BY month ORDER BY month ASC
            """, (s["sender_email"],)).fetchall()

            results.append({
                "email": s["sender_email"],
                "name": s["sender_name"] or s["sender_email"],
                "total": s["total"],
                "first_seen": s["first_seen"],
                "last_seen": s["last_seen"],
                "sparkline": [{"month": r["month"], "count": r["count"]} for r in sparkline],
            })

        return results


def activity_heatmap() -> list[dict]:
    """Email count by day-of-week (0=Sun) x hour-of-day (0-23)."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                CAST(strftime('%w', date_sent) AS INTEGER) as day_of_week,
                CAST(strftime('%H', date_sent) AS INTEGER) as hour,
                COUNT(*) as count
            FROM emails
            WHERE date_sent IS NOT NULL
            GROUP BY day_of_week, hour
        """).fetchall()

        return [{"day": r["day_of_week"], "hour": r["hour"], "count": r["count"]} for r in rows]


def yearly_summary() -> list[dict]:
    """Year-by-year summary statistics."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                strftime('%Y', date_sent) as year,
                COUNT(*) as total_emails,
                COUNT(DISTINCT sender_email) as unique_senders,
                COUNT(DISTINCT mbox_source) as mailboxes,
                SUM(CASE WHEN has_attachments = 1 THEN 1 ELSE 0 END) as with_attachments
            FROM emails
            WHERE date_sent IS NOT NULL
            GROUP BY year
            ORDER BY year ASC
        """).fetchall()

        return [dict(r) for r in rows]


def mailbox_breakdown() -> list[dict]:
    """Email counts per mailbox with date ranges."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT mbox_source, COUNT(*) as count,
                   MIN(date_sent) as first_date,
                   MAX(date_sent) as last_date,
                   COUNT(DISTINCT sender_email) as unique_senders
            FROM emails
            GROUP BY mbox_source
            ORDER BY count DESC
        """).fetchall()

        return [dict(r) for r in rows]


def thread_stats() -> dict:
    """Statistics about email threads."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM threads").fetchone()[0]
        if total == 0:
            return {"total": 0, "message": "Run thread reconstruction first: POST /api/threads/rebuild"}

        multi = conn.execute("SELECT COUNT(*) FROM threads WHERE message_count >= 2").fetchone()[0]

        longest = conn.execute("""
            SELECT t.id, t.subject_normalized, t.message_count, t.participant_count,
                   t.first_date, t.last_date
            FROM threads t
            ORDER BY t.message_count DESC LIMIT 5
        """).fetchall()

        most_participants = conn.execute("""
            SELECT t.id, t.subject_normalized, t.message_count, t.participant_count
            FROM threads t WHERE t.message_count >= 2
            ORDER BY t.participant_count DESC LIMIT 5
        """).fetchall()

        longest_duration = conn.execute("""
            SELECT t.id, t.subject_normalized, t.message_count,
                   t.duration_seconds, t.first_date, t.last_date
            FROM threads t WHERE t.message_count >= 2
            ORDER BY t.duration_seconds DESC LIMIT 5
        """).fetchall()

        avg_length = conn.execute(
            "SELECT AVG(message_count) FROM threads WHERE message_count >= 2"
        ).fetchone()[0]

        return {
            "total_threads": total,
            "conversations": multi,
            "average_thread_length": round(avg_length or 0, 1),
            "longest_threads": [dict(r) for r in longest],
            "most_participants": [dict(r) for r in most_participants],
            "longest_duration": [dict(r) for r in longest_duration],
        }


def response_time_stats() -> dict:
    """Average response times between emails in threads."""
    with get_db() as conn:
        # Get all multi-message threads
        threads = conn.execute("""
            SELECT id FROM threads WHERE message_count >= 2
        """).fetchall()

        if not threads:
            return {"average_response_hours": None, "message": "No threads found"}

        response_times = []
        for t in threads[:1000]:  # Cap at 1000 threads for performance
            emails = conn.execute("""
                SELECT date_timestamp, sender_email
                FROM emails
                WHERE thread_group_id = ? AND date_timestamp IS NOT NULL
                ORDER BY date_timestamp ASC
            """, (t["id"],)).fetchall()

            for i in range(1, len(emails)):
                if emails[i]["sender_email"] != emails[i-1]["sender_email"]:
                    delta = emails[i]["date_timestamp"] - emails[i-1]["date_timestamp"]
                    if 0 < delta < 86400 * 30:  # Ignore > 30 day gaps
                        response_times.append(delta)

        if not response_times:
            return {"average_response_hours": None}

        avg_seconds = sum(response_times) / len(response_times)
        median_idx = len(response_times) // 2
        response_times.sort()

        return {
            "average_response_hours": round(avg_seconds / 3600, 1),
            "median_response_hours": round(response_times[median_idx] / 3600, 1),
            "total_responses_measured": len(response_times),
        }


def compute_all_analytics() -> dict:
    """Compute and cache all analytics. Returns summary."""
    start = time.time()

    with get_db() as conn:
        def cache(key, data):
            conn.execute(
                "INSERT OR REPLACE INTO analytics_cache (key, data, computed_at) VALUES (?, ?, datetime('now'))",
                (key, json.dumps(data))
            )

        print("📊 Computing analytics...")

        print("  Volume by month...")
        cache("volume_by_month", email_volume_by_month())

        print("  Top contacts...")
        cache("top_contacts", top_contacts(30))

        print("  Activity heatmap...")
        cache("activity_heatmap", activity_heatmap())

        print("  Yearly summary...")
        cache("yearly_summary", yearly_summary())

        print("  Mailbox breakdown...")
        cache("mailbox_breakdown", mailbox_breakdown())

        print("  Thread stats...")
        cache("thread_stats", thread_stats())

    duration = time.time() - start
    print(f"✅ Analytics computed in {duration:.1f}s")
    return {"duration_seconds": round(duration, 2)}


def get_cached(key: str):
    """Get cached analytics data."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT data, computed_at FROM analytics_cache WHERE key = ?",
            (key,)
        ).fetchone()
        if row:
            return {"data": json.loads(row["data"]), "computed_at": row["computed_at"]}
        return None
