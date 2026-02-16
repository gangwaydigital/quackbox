"""
Thread reconstruction service.

Groups individual emails into conversation threads using:
1. Message-ID / In-Reply-To / References headers (primary)
2. Normalized subject matching (fallback)
"""

import json
import re
import time
from collections import defaultdict
from typing import Optional

from app.database import get_db


# Patterns to strip from subjects for normalization
RE_PREFIX = re.compile(r'^(?:\s*(?:Re|Fwd|Fw|FWD|RE|FW)\s*[:]\s*)+', re.IGNORECASE)


def normalize_subject(subject: str) -> str:
    """Strip Re:/Fwd: prefixes and whitespace for thread matching."""
    if not subject:
        return ""
    s = RE_PREFIX.sub("", subject).strip()
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s)
    return s.lower()


def rebuild_threads() -> dict:
    """
    Scan all emails and group them into conversation threads.

    Strategy:
    1. Build a graph from In-Reply-To / References headers
    2. Walk chains to find root messages
    3. Group remaining ungrouped emails by normalized subject
    4. Store thread groups in the threads table

    Returns:
        dict with rebuild statistics
    """
    start = time.time()

    with get_db() as conn:
        # Clear existing thread data
        conn.execute("DELETE FROM threads")
        conn.execute("UPDATE emails SET thread_group_id = NULL")

        # Load all emails with threading info
        rows = conn.execute("""
            SELECT id, message_id, thread_id, subject,
                   sender_email, date_sent, date_timestamp, mbox_source
            FROM emails
            ORDER BY date_timestamp ASC
        """).fetchall()

        print(f"🧵 Rebuilding threads for {len(rows)} emails...")

        # --- Phase 1: Build reply graph from headers ---
        # message_id → email row
        by_msg_id = {}
        # message_id → set of message_ids that reference it
        children = defaultdict(set)
        # email.id → normalized subject
        subjects = {}

        for row in rows:
            msg_id = row["message_id"]
            if msg_id:
                by_msg_id[msg_id] = row
            subjects[row["id"]] = normalize_subject(row["subject"] or "")

            # thread_id contains the In-Reply-To value
            parent_id = row["thread_id"]
            if parent_id and msg_id:
                children[parent_id].add(msg_id)

        # Walk up reply chains to find root
        def find_root(msg_id, visited=None):
            if visited is None:
                visited = set()
            if msg_id in visited:
                return msg_id  # Circular reference
            visited.add(msg_id)
            row = by_msg_id.get(msg_id)
            if not row:
                return msg_id
            parent = row["thread_id"]
            if parent and parent in by_msg_id:
                return find_root(parent, visited)
            return msg_id

        # Group emails by root message_id
        root_groups = defaultdict(list)
        grouped_ids = set()

        for row in rows:
            msg_id = row["message_id"]
            if not msg_id:
                continue
            parent = row["thread_id"]
            if parent or msg_id in children:
                root_id = find_root(msg_id)
                root_groups[root_id].append(row)
                grouped_ids.add(row["id"])

        print(f"  Phase 1: {len(root_groups)} threads from reply headers")

        # --- Phase 2: Group remaining by normalized subject ---
        subject_groups = defaultdict(list)
        for row in rows:
            if row["id"] in grouped_ids:
                continue
            norm_subj = subjects[row["id"]]
            if norm_subj and len(norm_subj) > 3:  # Skip very short subjects
                subject_groups[norm_subj].append(row)

        # Only keep subject groups with 2+ messages
        subject_thread_count = 0
        for norm_subj, group_rows in subject_groups.items():
            if len(group_rows) >= 2:
                # Create a synthetic root key
                key = f"subj:{norm_subj}"
                root_groups[key] = group_rows
                for row in group_rows:
                    grouped_ids.add(row["id"])
                subject_thread_count += 1

        print(f"  Phase 2: {subject_thread_count} threads from subject matching")

        # --- Phase 3: Remaining singletons ---
        singleton_count = 0
        for row in rows:
            if row["id"] not in grouped_ids:
                key = f"single:{row['id']}"
                root_groups[key] = [row]
                singleton_count += 1

        print(f"  Singletons: {singleton_count}")

        # --- Phase 4: Write thread groups to database ---
        thread_count = 0
        multi_count = 0

        for root_key, group_rows in root_groups.items():
            group_rows.sort(key=lambda r: r["date_timestamp"] or 0)

            participants = set()
            mailboxes = set()
            for r in group_rows:
                if r["sender_email"]:
                    participants.add(r["sender_email"])
                if r["mbox_source"]:
                    mailboxes.add(r["mbox_source"])

            first_date = group_rows[0]["date_sent"]
            last_date = group_rows[-1]["date_sent"]

            first_ts = group_rows[0]["date_timestamp"] or 0
            last_ts = group_rows[-1]["date_timestamp"] or 0
            duration = last_ts - first_ts if last_ts > first_ts else 0

            root_msg_id = None
            if not root_key.startswith(("subj:", "single:")):
                root_msg_id = root_key

            norm_subj = normalize_subject(group_rows[0]["subject"] or "")

            cursor = conn.execute("""
                INSERT INTO threads (
                    root_message_id, subject_normalized,
                    participant_count, message_count,
                    first_date, last_date, duration_seconds,
                    mailbox_sources
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                root_msg_id, norm_subj,
                len(participants), len(group_rows),
                first_date, last_date, duration,
                json.dumps(sorted(mailboxes))
            ))

            thread_id = cursor.lastrowid

            # Link emails to this thread
            email_ids = [r["id"] for r in group_rows]
            for eid in email_ids:
                conn.execute(
                    "UPDATE emails SET thread_group_id = ? WHERE id = ?",
                    (thread_id, eid)
                )

            thread_count += 1
            if len(group_rows) > 1:
                multi_count += 1

            if thread_count % 5000 == 0:
                conn.commit()
                print(f"  ... processed {thread_count} threads")

    duration = time.time() - start
    result = {
        "total_threads": thread_count,
        "multi_message_threads": multi_count,
        "singletons": singleton_count,
        "duration_seconds": round(duration, 2),
    }
    print(f"✅ Thread rebuild complete: {multi_count} conversations, {singleton_count} singletons ({duration:.1f}s)")
    return result


def get_threads(
    min_messages: int = 2,
    sort_by: str = "last_date",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """List threads with pagination."""
    allowed_sorts = {"last_date", "message_count", "participant_count", "duration_seconds"}
    if sort_by not in allowed_sorts:
        sort_by = "last_date"
    sort_dir = "ASC" if sort_order == "asc" else "DESC"
    offset = (page - 1) * page_size

    with get_db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM threads WHERE message_count >= ?",
            (min_messages,)
        ).fetchone()[0]

        rows = conn.execute(f"""
            SELECT t.*,
                   (SELECT subject FROM emails WHERE thread_group_id = t.id
                    ORDER BY date_timestamp ASC LIMIT 1) as original_subject
            FROM threads t
            WHERE t.message_count >= ?
            ORDER BY t.{sort_by} {sort_dir}
            LIMIT ? OFFSET ?
        """, (min_messages, page_size, offset)).fetchall()

        items = []
        for row in rows:
            item = dict(row)
            item["mailbox_sources"] = json.loads(item.get("mailbox_sources") or "[]")
            items.append(item)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }


def get_thread_detail(thread_id: int) -> Optional[dict]:
    """Get a thread with all its emails ordered chronologically."""
    with get_db() as conn:
        thread = conn.execute("SELECT * FROM threads WHERE id = ?", (thread_id,)).fetchone()
        if not thread:
            return None

        thread_data = dict(thread)
        thread_data["mailbox_sources"] = json.loads(thread_data.get("mailbox_sources") or "[]")

        # Get all emails in this thread
        emails = conn.execute("""
            SELECT id, message_id, subject, sender_name, sender_email,
                   recipients, date_sent, date_timestamp, body_text,
                   has_attachments, attachment_names, mbox_source
            FROM emails
            WHERE thread_group_id = ?
            ORDER BY date_timestamp ASC
        """, (thread_id,)).fetchall()

        thread_data["emails"] = []
        for row in emails:
            email = dict(row)
            email["recipients"] = json.loads(email.get("recipients") or "[]")
            email["attachment_names"] = json.loads(email.get("attachment_names") or "[]")
            # Truncate body for thread view
            if email["body_text"] and len(email["body_text"]) > 2000:
                email["body_text"] = email["body_text"][:2000] + "\n[truncated — open email for full text]"
            thread_data["emails"].append(email)

        return thread_data


def get_thread_participants(thread_id: int) -> list[dict]:
    """Get all participants in a thread with message counts."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT sender_email, sender_name, COUNT(*) as message_count
            FROM emails
            WHERE thread_group_id = ?
            GROUP BY sender_email
            ORDER BY message_count DESC
        """, (thread_id,)).fetchall()
        return [dict(r) for r in rows]
