"""Analytics service for dashboard data."""
import json, time
from collections import defaultdict
from app.database import get_db

def email_volume_by_month():
    with get_db() as conn:
        rows = conn.execute("SELECT strftime('%Y-%m', date_sent) as month, mbox_source, COUNT(*) as count FROM emails WHERE date_sent IS NOT NULL GROUP BY month, mbox_source ORDER BY month ASC").fetchall()
        months = defaultdict(lambda: defaultdict(int))
        for r in rows:
            if r["month"]:
                months[r["month"]][r["mbox_source"] or "Unknown"] += r["count"]
                months[r["month"]]["_total"] += r["count"]
        result = []
        for month in sorted(months.keys()):
            entry = {"month": month, "total": months[month]["_total"]}
            sources = {k: v for k, v in months[month].items() if k != "_total"}
            for name, count in sorted(sources.items(), key=lambda x: -x[1])[:5]:
                entry[name] = count
            result.append(entry)
        return result

def top_contacts(limit=20):
    with get_db() as conn:
        senders = conn.execute("SELECT sender_email, sender_name, COUNT(*) as total, MIN(date_sent) as first_seen, MAX(date_sent) as last_seen FROM emails WHERE sender_email != '' AND sender_email IS NOT NULL GROUP BY sender_email ORDER BY total DESC LIMIT ?", (limit,)).fetchall()
        results = []
        for s in senders:
            sparkline = conn.execute("SELECT strftime('%Y-%m', date_sent) as month, COUNT(*) as count FROM emails WHERE sender_email = ? AND date_sent IS NOT NULL GROUP BY month ORDER BY month ASC", (s["sender_email"],)).fetchall()
            results.append({"email": s["sender_email"], "name": s["sender_name"] or s["sender_email"], "total": s["total"], "first_seen": s["first_seen"], "last_seen": s["last_seen"], "sparkline": [{"month": r["month"], "count": r["count"]} for r in sparkline]})
        return results

def activity_heatmap():
    with get_db() as conn:
        rows = conn.execute("SELECT CAST(strftime('%w', date_sent) AS INTEGER) as day_of_week, CAST(strftime('%H', date_sent) AS INTEGER) as hour, COUNT(*) as count FROM emails WHERE date_sent IS NOT NULL GROUP BY day_of_week, hour").fetchall()
        return [{"day": r["day_of_week"], "hour": r["hour"], "count": r["count"]} for r in rows]

def yearly_summary():
    with get_db() as conn:
        rows = conn.execute("SELECT strftime('%Y', date_sent) as year, COUNT(*) as total_emails, COUNT(DISTINCT sender_email) as unique_senders, COUNT(DISTINCT mbox_source) as mailboxes, SUM(CASE WHEN has_attachments = 1 THEN 1 ELSE 0 END) as with_attachments FROM emails WHERE date_sent IS NOT NULL GROUP BY year ORDER BY year ASC").fetchall()
        return [dict(r) for r in rows]

def mailbox_breakdown():
    with get_db() as conn:
        rows = conn.execute("SELECT mbox_source, COUNT(*) as count, MIN(date_sent) as first_date, MAX(date_sent) as last_date, COUNT(DISTINCT sender_email) as unique_senders FROM emails GROUP BY mbox_source ORDER BY count DESC").fetchall()
        return [dict(r) for r in rows]

def thread_stats():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM threads").fetchone()[0]
        if total == 0: return {"total_threads": 0, "message": "Run thread reconstruction first"}
        multi = conn.execute("SELECT COUNT(*) FROM threads WHERE message_count >= 2").fetchone()[0]
        longest = [dict(r) for r in conn.execute("SELECT id, subject_normalized, message_count, participant_count, first_date, last_date FROM threads ORDER BY message_count DESC LIMIT 5").fetchall()]
        most_participants = [dict(r) for r in conn.execute("SELECT id, subject_normalized, message_count, participant_count FROM threads WHERE message_count >= 2 ORDER BY participant_count DESC LIMIT 5").fetchall()]
        longest_duration = [dict(r) for r in conn.execute("SELECT id, subject_normalized, message_count, duration_seconds, first_date, last_date FROM threads WHERE message_count >= 2 ORDER BY duration_seconds DESC LIMIT 5").fetchall()]
        avg_length = conn.execute("SELECT AVG(message_count) FROM threads WHERE message_count >= 2").fetchone()[0]
        return {"total_threads": total, "conversations": multi, "average_thread_length": round(avg_length or 0, 1), "longest_threads": longest, "most_participants": most_participants, "longest_duration": longest_duration}

def compute_all_analytics():
    start = time.time()
    with get_db() as conn:
        def cache(key, data):
            conn.execute("INSERT OR REPLACE INTO analytics_cache (key, data, computed_at) VALUES (?, ?, datetime('now'))", (key, json.dumps(data)))
        print("📊 Computing analytics...")
        cache("volume_by_month", email_volume_by_month())
        cache("top_contacts", top_contacts(30))
        cache("activity_heatmap", activity_heatmap())
        cache("yearly_summary", yearly_summary())
        cache("mailbox_breakdown", mailbox_breakdown())
        cache("thread_stats", thread_stats())
    print(f"✅ Analytics computed in {time.time()-start:.1f}s")
    return {"duration_seconds": round(time.time()-start, 2)}

def get_cached(key):
    with get_db() as conn:
        row = conn.execute("SELECT data, computed_at FROM analytics_cache WHERE key = ?", (key,)).fetchone()
        if row: return {"data": json.loads(row["data"]), "computed_at": row["computed_at"]}
        return None

def response_time_stats():
    with get_db() as conn:
        threads = conn.execute("SELECT id FROM threads WHERE message_count >= 2").fetchall()
        if not threads: return {"average_response_hours": None, "message": "No threads found"}
        response_times = []
        for t in threads[:1000]:
            emails = conn.execute("SELECT date_timestamp, sender_email FROM emails WHERE thread_group_id = ? AND date_timestamp IS NOT NULL ORDER BY date_timestamp ASC", (t["id"],)).fetchall()
            for i in range(1, len(emails)):
                if emails[i]["sender_email"] != emails[i-1]["sender_email"]:
                    delta = emails[i]["date_timestamp"] - emails[i-1]["date_timestamp"]
                    if 0 < delta < 86400 * 30: response_times.append(delta)
        if not response_times: return {"average_response_hours": None}
        avg_s = sum(response_times) / len(response_times)
        response_times.sort()
        return {"average_response_hours": round(avg_s/3600, 1), "median_response_hours": round(response_times[len(response_times)//2]/3600, 1), "total_responses_measured": len(response_times)}


def communication_network(min_shared_threads=1, limit_contacts=80):
    """
    Build a communication network graph.
    Nodes = email addresses, edges = shared thread participation.
    Returns nodes + edges for D3 force-directed layout.
    """
    with get_db() as conn:
        # Find contacts who share threads
        # First get all threads with 2+ participants
        threads = conn.execute("""
            SELECT thread_group_id, sender_email
            FROM emails
            WHERE thread_group_id IS NOT NULL AND sender_email != '' AND sender_email IS NOT NULL
            ORDER BY thread_group_id
        """).fetchall()

        # Group participants by thread
        from collections import defaultdict
        thread_members = defaultdict(set)
        email_counts = defaultdict(int)
        email_names = {}

        for row in threads:
            tid = row["thread_group_id"]
            addr = row["sender_email"].lower()
            thread_members[tid].add(addr)
            email_counts[addr] += 1

        # Get display names
        name_rows = conn.execute("""
            SELECT sender_email, sender_name, COUNT(*) as cnt
            FROM emails WHERE sender_email != '' AND sender_email IS NOT NULL
            GROUP BY sender_email ORDER BY cnt DESC
        """).fetchall()
        for r in name_rows:
            email_names[r["sender_email"].lower()] = r["sender_name"] or r["sender_email"]

        # Build edge weights (shared thread count between pairs)
        edges_map = defaultdict(int)
        for tid, members in thread_members.items():
            members_list = sorted(members)
            for i in range(len(members_list)):
                for j in range(i + 1, len(members_list)):
                    pair = (members_list[i], members_list[j])
                    edges_map[pair] += 1

        # Filter to top contacts by email volume
        top_emails = sorted(email_counts.keys(), key=lambda e: -email_counts[e])[:limit_contacts]
        top_set = set(top_emails)

        # Build nodes
        nodes = []
        for addr in top_emails:
            nodes.append({
                "id": addr,
                "name": email_names.get(addr, addr),
                "email_count": email_counts[addr],
                "size": min(40, max(8, email_counts[addr] ** 0.4 * 3)),
            })

        # Build edges (only between top contacts, above threshold)
        edges = []
        for (a, b), weight in edges_map.items():
            if a in top_set and b in top_set and weight >= min_shared_threads:
                edges.append({
                    "source": a,
                    "target": b,
                    "weight": weight,
                    "strength": min(5, weight ** 0.5),
                })

        return {
            "nodes": nodes,
            "edges": edges,
            "total_contacts": len(email_counts),
            "shown_contacts": len(nodes),
            "total_edges": len(edges),
        }
