"""
Analytics service for dashboard data.

Features:
- Write-through caching with TTL (cache on compute, serve from cache)
- Single-query sparklines (no N+1)
- Batch loading for dashboard
"""
import json, time
from collections import defaultdict
from app.database import get_db

# Cache TTL in seconds (1 hour default — data doesn't change between imports)
CACHE_TTL = 3600


def _get_cached(key, conn=None):
    """Get cached value if fresh. Returns data or None."""
    def _fetch(c):
        row = c.execute(
            "SELECT data, computed_at FROM analytics_cache WHERE key = ?", (key,)
        ).fetchone()
        if not row:
            return None
        # Check TTL
        computed = c.execute(
            "SELECT strftime('%s', ?) as ts", (row["computed_at"],)
        ).fetchone()
        now = c.execute("SELECT strftime('%s', 'now') as ts").fetchone()
        if computed and now:
            age = int(now["ts"]) - int(computed["ts"])
            if age < CACHE_TTL:
                return {"data": json.loads(row["data"]), "computed_at": row["computed_at"], "cached": True}
        return None

    if conn:
        return _fetch(conn)
    with get_db() as c:
        return _fetch(c)


def _set_cache(key, data, conn=None):
    """Write data to cache."""
    def _store(c):
        c.execute(
            "INSERT OR REPLACE INTO analytics_cache (key, data, computed_at) VALUES (?, ?, datetime('now'))",
            (key, json.dumps(data))
        )

    if conn:
        _store(conn)
    else:
        with get_db() as c:
            _store(c)


def _cached_or_compute(key, compute_fn):
    """Return cached data if fresh, otherwise compute, cache, and return."""
    cached = _get_cached(key)
    if cached:
        return cached
    data = compute_fn()
    _set_cache(key, data)
    return {"data": data, "computed_at": "live", "cached": False}


# ── Dashboard batch endpoint ────────────────────────────────

def dashboard_batch():
    """
    Load all dashboard data in a single call.
    Uses cache where available, computes and caches the rest.
    Avoids 6 separate API round-trips.
    """
    result = {}
    keys = {
        "volume": ("volume_by_month", email_volume_by_month),
        "contacts": ("top_contacts", lambda: top_contacts(15)),
        "heatmap": ("activity_heatmap", activity_heatmap),
        "yearly": ("yearly_summary", yearly_summary),
        "thread_stats": ("thread_stats", thread_stats),
    }

    with get_db() as conn:
        for section, (cache_key, compute_fn) in keys.items():
            cached = _get_cached(cache_key, conn)
            if cached:
                result[section] = cached["data"]
            else:
                data = compute_fn()
                _set_cache(cache_key, data, conn)
                result[section] = data

    return result


# ── Individual analytics functions ───────────────────────────

def email_volume_by_month():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT strftime('%Y-%m', date_sent) as month, mbox_source, COUNT(*) as count
            FROM emails WHERE date_sent IS NOT NULL
            GROUP BY month, mbox_source ORDER BY month ASC
        """).fetchall()
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
    """
    Get top contacts with sparkline data in TWO queries (not N+1).
    """
    with get_db() as conn:
        # Query 1: Top senders
        senders = conn.execute("""
            SELECT sender_email, sender_name, COUNT(*) as total,
                   MIN(date_sent) as first_seen, MAX(date_sent) as last_seen
            FROM emails
            WHERE sender_email != '' AND sender_email IS NOT NULL
            GROUP BY sender_email ORDER BY total DESC LIMIT ?
        """, (limit,)).fetchall()

        if not senders:
            return []

        # Query 2: All sparklines for top senders in ONE query
        email_list = [s["sender_email"] for s in senders]
        placeholders = ",".join("?" * len(email_list))
        sparkline_rows = conn.execute(f"""
            SELECT sender_email, strftime('%Y-%m', date_sent) as month, COUNT(*) as count
            FROM emails
            WHERE sender_email IN ({placeholders}) AND date_sent IS NOT NULL
            GROUP BY sender_email, month
            ORDER BY sender_email, month ASC
        """, email_list).fetchall()

        # Group sparklines by sender
        sparklines = defaultdict(list)
        for r in sparkline_rows:
            sparklines[r["sender_email"]].append({"month": r["month"], "count": r["count"]})

        results = []
        for s in senders:
            results.append({
                "email": s["sender_email"],
                "name": s["sender_name"] or s["sender_email"],
                "total": s["total"],
                "first_seen": s["first_seen"],
                "last_seen": s["last_seen"],
                "sparkline": sparklines.get(s["sender_email"], []),
            })
        return results


def activity_heatmap():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT CAST(strftime('%w', date_sent) AS INTEGER) as day_of_week,
                   CAST(strftime('%H', date_sent) AS INTEGER) as hour,
                   COUNT(*) as count
            FROM emails WHERE date_sent IS NOT NULL
            GROUP BY day_of_week, hour
        """).fetchall()
        return [{"day": r["day_of_week"], "hour": r["hour"], "count": r["count"]} for r in rows]


def yearly_summary():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT strftime('%Y', date_sent) as year, COUNT(*) as total_emails,
                   COUNT(DISTINCT sender_email) as unique_senders,
                   COUNT(DISTINCT mbox_source) as mailboxes,
                   SUM(CASE WHEN has_attachments = 1 THEN 1 ELSE 0 END) as with_attachments
            FROM emails WHERE date_sent IS NOT NULL
            GROUP BY year ORDER BY year ASC
        """).fetchall()
        return [dict(r) for r in rows]


def mailbox_breakdown():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT mbox_source, COUNT(*) as count,
                   MIN(date_sent) as first_date, MAX(date_sent) as last_date,
                   COUNT(DISTINCT sender_email) as unique_senders
            FROM emails GROUP BY mbox_source ORDER BY count DESC
        """).fetchall()
        return [dict(r) for r in rows]


def thread_stats():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM threads").fetchone()[0]
        if total == 0:
            return {"total_threads": 0, "message": "Run thread reconstruction first"}
        multi = conn.execute("SELECT COUNT(*) FROM threads WHERE message_count >= 2").fetchone()[0]
        longest = [dict(r) for r in conn.execute(
            "SELECT id, subject_normalized, message_count, participant_count, first_date, last_date FROM threads ORDER BY message_count DESC LIMIT 5"
        ).fetchall()]
        most_participants = [dict(r) for r in conn.execute(
            "SELECT id, subject_normalized, message_count, participant_count FROM threads WHERE message_count >= 2 ORDER BY participant_count DESC LIMIT 5"
        ).fetchall()]
        longest_duration = [dict(r) for r in conn.execute(
            "SELECT id, subject_normalized, message_count, duration_seconds, first_date, last_date FROM threads WHERE message_count >= 2 ORDER BY duration_seconds DESC LIMIT 5"
        ).fetchall()]
        avg_length = conn.execute("SELECT AVG(message_count) FROM threads WHERE message_count >= 2").fetchone()[0]
        return {
            "total_threads": total, "conversations": multi,
            "average_thread_length": round(avg_length or 0, 1),
            "longest_threads": longest, "most_participants": most_participants,
            "longest_duration": longest_duration,
        }


# ── Cache management ─────────────────────────────────────────

def invalidate_cache():
    """Clear all cached analytics (call after ingest or data changes)."""
    with get_db() as conn:
        conn.execute("DELETE FROM analytics_cache")
    print("🗑️  Analytics cache invalidated")


def warm_cache():
    """Pre-compute and cache all analytics. Call after ingest."""
    start = time.time()
    print("📊 Warming analytics cache...")
    with get_db() as conn:
        _set_cache("volume_by_month", email_volume_by_month(), conn)
        _set_cache("top_contacts", top_contacts(30), conn)
        _set_cache("activity_heatmap", activity_heatmap(), conn)
        _set_cache("yearly_summary", yearly_summary(), conn)
        _set_cache("mailbox_breakdown", mailbox_breakdown(), conn)
        _set_cache("thread_stats", thread_stats(), conn)
    elapsed = round(time.time() - start, 1)
    print(f"✅ Analytics cache warmed in {elapsed}s")
    return {"duration_seconds": elapsed}


def compute_all_analytics():
    """Legacy compat — alias for warm_cache."""
    return warm_cache()


def get_cached(key):
    """Public cache getter for router layer."""
    result = _get_cached(key)
    if result:
        return result
    return None


# ── Expensive analytics (not cached by default) ──────────────

def response_time_stats():
    with get_db() as conn:
        # Single query approach: get all thread emails at once
        rows = conn.execute("""
            SELECT thread_group_id, date_timestamp, sender_email
            FROM emails
            WHERE thread_group_id IN (
                SELECT id FROM threads WHERE message_count >= 2 LIMIT 1000
            )
            AND date_timestamp IS NOT NULL
            ORDER BY thread_group_id, date_timestamp ASC
        """).fetchall()

        if not rows:
            return {"average_response_hours": None, "message": "No threads found"}

        response_times = []
        current_thread = None
        prev_email = None

        for row in rows:
            if row["thread_group_id"] != current_thread:
                current_thread = row["thread_group_id"]
                prev_email = row
                continue
            if row["sender_email"] != prev_email["sender_email"]:
                delta = row["date_timestamp"] - prev_email["date_timestamp"]
                if 0 < delta < 86400 * 30:
                    response_times.append(delta)
            prev_email = row

        if not response_times:
            return {"average_response_hours": None}

        avg_s = sum(response_times) / len(response_times)
        response_times.sort()
        return {
            "average_response_hours": round(avg_s / 3600, 1),
            "median_response_hours": round(response_times[len(response_times) // 2] / 3600, 1),
            "total_responses_measured": len(response_times),
        }


def communication_network(min_shared_threads=1, limit_contacts=80):
    """
    Build a communication network graph.
    Nodes = email addresses, edges = shared thread participation.
    """
    with get_db() as conn:
        threads = conn.execute("""
            SELECT thread_group_id, sender_email
            FROM emails
            WHERE thread_group_id IS NOT NULL
              AND sender_email != '' AND sender_email IS NOT NULL
            ORDER BY thread_group_id
        """).fetchall()

        thread_members = defaultdict(set)
        email_counts = defaultdict(int)
        email_names = {}

        for row in threads:
            tid = row["thread_group_id"]
            addr = row["sender_email"].lower()
            thread_members[tid].add(addr)
            email_counts[addr] += 1

        name_rows = conn.execute("""
            SELECT sender_email, sender_name, COUNT(*) as cnt
            FROM emails WHERE sender_email != '' AND sender_email IS NOT NULL
            GROUP BY sender_email ORDER BY cnt DESC
        """).fetchall()
        for r in name_rows:
            email_names[r["sender_email"].lower()] = r["sender_name"] or r["sender_email"]

        edges_map = defaultdict(int)
        for tid, members in thread_members.items():
            members_list = sorted(members)
            for i in range(len(members_list)):
                for j in range(i + 1, len(members_list)):
                    edges_map[(members_list[i], members_list[j])] += 1

        top_emails = sorted(email_counts.keys(), key=lambda e: -email_counts[e])[:limit_contacts]
        top_set = set(top_emails)

        nodes = [{
            "id": addr,
            "name": email_names.get(addr, addr),
            "email_count": email_counts[addr],
            "size": min(40, max(8, email_counts[addr] ** 0.4 * 3)),
        } for addr in top_emails]

        edges = [{
            "source": a, "target": b, "weight": weight,
            "strength": min(5, weight ** 0.5),
        } for (a, b), weight in edges_map.items()
            if a in top_set and b in top_set and weight >= min_shared_threads]

        return {
            "nodes": nodes, "edges": edges,
            "total_contacts": len(email_counts),
            "shown_contacts": len(nodes),
            "total_edges": len(edges),
        }
