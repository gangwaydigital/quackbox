"""
Duplicate email detection and deduplication service.

Detection strategies (applied in order):
  1. Exact message-id match across different mbox sources (imported twice)
  2. Same sender + subject + date within 60s (missing/different Message-ID)
  3. Same sender + normalized subject + body hash (forwarded copies, re-sends)

All strategies are index-friendly — no full-table content scans.
"""

import hashlib
import re
import time
from app.database import get_db
from app.logging_config import get_logger

log = get_logger("deduplication")


# ── Text normalization ─────────────────────────────────────────────────────

def _normalize_subject(subject: str) -> str:
    """Strip Re:/Fwd: prefixes and whitespace for comparison."""
    if not subject:
        return ""
    s = re.sub(r'^(re|fwd?|aw|sv|رد|回复|返信):\s*', '', subject.strip(),
               flags=re.IGNORECASE)
    return s.lower().strip()


def _body_hash(body: str) -> str:
    """Stable hash of first 1000 chars of body after whitespace normalization."""
    if not body:
        return ""
    normalized = re.sub(r'\s+', ' ', body.strip())[:1000]
    return hashlib.sha256(normalized.encode('utf-8', errors='replace')).hexdigest()[:16]


# ── Detection ──────────────────────────────────────────────────────────────

def scan_duplicates(max_groups: int = 500) -> dict:
    """
    Scan for duplicate emails and store groups in the database.

    Returns a summary dict with counts.
    """
    start = time.time()
    log.info("🔍 Scanning for duplicate emails...")

    with get_db() as conn:
        # Clear old scan results
        conn.execute("DELETE FROM duplicate_emails")
        conn.execute("DELETE FROM duplicate_groups")

        groups_created = 0
        emails_flagged = 0

        # ── Strategy 1: Same Message-ID from multiple sources ──────────────
        # Find message_ids that appear more than once (shouldn't happen given
        # UNIQUE constraint, but covers cases where message_id was NULL on
        # first insert and got re-imported with an ID)
        dups_by_msgid = conn.execute("""
            SELECT message_id, GROUP_CONCAT(id) as ids, COUNT(*) as cnt
            FROM emails
            WHERE message_id IS NOT NULL AND message_id != ''
            GROUP BY message_id
            HAVING cnt > 1
            LIMIT ?
        """, (max_groups,)).fetchall()

        for row in dups_by_msgid:
            ids = [int(i) for i in row["ids"].split(",")]
            canonical_id = min(ids)
            dup_ids = [i for i in ids if i != canonical_id]

            res = conn.execute(
                "INSERT INTO duplicate_groups (canonical_email_id, duplicate_count, detection_method) VALUES (?, ?, ?)",
                (canonical_id, len(dup_ids), "message_id")
            )
            gid = res.lastrowid
            for did in dup_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO duplicate_emails (group_id, email_id, similarity_score) VALUES (?, ?, 1.0)",
                    (gid, did)
                )
            groups_created += 1
            emails_flagged += len(dup_ids)

        # ── Strategy 2: Same sender + subject + date (within 60s) ──────────
        similar_rows = conn.execute("""
            SELECT
                e1.id as id1, e2.id as id2,
                e1.sender_email, e1.subject, e1.date_timestamp
            FROM emails e1
            JOIN emails e2
                ON e1.sender_email = e2.sender_email
                AND e1.id < e2.id
                AND ABS(e1.date_timestamp - e2.date_timestamp) < 60
                AND e1.subject = e2.subject
                AND e1.mbox_source != e2.mbox_source
            WHERE e1.message_id IS NULL OR e1.message_id = ''
               OR e2.message_id IS NULL OR e2.message_id = ''
            LIMIT ?
        """, (max_groups - groups_created,)).fetchall()

        # Group overlapping pairs
        pair_map: dict[int, int] = {}  # email_id → canonical_id
        for row in similar_rows:
            id1, id2 = row["id1"], row["id2"]
            canon = pair_map.get(id1, pair_map.get(id2, min(id1, id2)))
            pair_map[id1] = canon
            pair_map[id2] = canon

        # Build groups from pair_map
        canon_to_dups: dict[int, list[int]] = {}
        for eid, cid in pair_map.items():
            if eid != cid:
                canon_to_dups.setdefault(cid, []).append(eid)

        for canonical_id, dup_ids in canon_to_dups.items():
            # Skip if already covered by strategy 1
            existing = conn.execute(
                "SELECT 1 FROM duplicate_groups WHERE canonical_email_id = ?",
                (canonical_id,)
            ).fetchone()
            if existing:
                continue
            res = conn.execute(
                "INSERT INTO duplicate_groups (canonical_email_id, duplicate_count, detection_method) VALUES (?, ?, ?)",
                (canonical_id, len(dup_ids), "sender_subject_date")
            )
            gid = res.lastrowid
            for did in dup_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO duplicate_emails (group_id, email_id, similarity_score) VALUES (?, ?, 0.95)",
                    (gid, did)
                )
            groups_created += 1
            emails_flagged += len(dup_ids)

        # ── Strategy 3: Same sender + normalized subject + body hash ───────
        # Compute body hashes in Python (SQLite can't SHA256 natively)
        body_rows = conn.execute("""
            SELECT id, sender_email, subject, body_text, mbox_source
            FROM emails
            WHERE id NOT IN (
                SELECT email_id FROM duplicate_emails
            )
            ORDER BY date_timestamp
        """).fetchall()

        hash_index: dict[str, list[int]] = {}
        for row in body_rows:
            ns = _normalize_subject(row["subject"] or "")
            bh = _body_hash(row["body_text"] or "")
            if not bh:
                continue
            key = f"{row['sender_email']}|{ns}|{bh}"
            hash_index.setdefault(key, []).append(row["id"])

        for key, ids in hash_index.items():
            if len(ids) < 2 or groups_created >= max_groups:
                break
            canonical_id = min(ids)
            dup_ids = [i for i in ids if i != canonical_id]
            existing = conn.execute(
                "SELECT 1 FROM duplicate_groups WHERE canonical_email_id = ?",
                (canonical_id,)
            ).fetchone()
            if existing:
                continue
            res = conn.execute(
                "INSERT INTO duplicate_groups (canonical_email_id, duplicate_count, detection_method) VALUES (?, ?, ?)",
                (canonical_id, len(dup_ids), "content_hash")
            )
            gid = res.lastrowid
            for did in dup_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO duplicate_emails (group_id, email_id, similarity_score) VALUES (?, ?, 0.85)",
                    (gid, did)
                )
            groups_created += 1
            emails_flagged += len(dup_ids)

        elapsed = round(time.time() - start, 2)
        log.info("✅ Deduplication scan done: %d groups, %d flagged (%.2fs)", groups_created, emails_flagged, elapsed)
        return {
            "groups_found": groups_created,
            "emails_flagged": emails_flagged,
            "elapsed_seconds": elapsed,
        }


def get_duplicate_groups(page: int = 1, page_size: int = 20) -> dict:
    """List all detected duplicate groups with canonical + duplicate emails."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM duplicate_groups").fetchone()[0]
        offset = (page - 1) * page_size

        groups_rows = conn.execute("""
            SELECT dg.id, dg.canonical_email_id, dg.duplicate_count,
                   dg.detection_method, dg.created_at,
                   e.subject, e.sender_name, e.sender_email,
                   e.date_sent, e.mbox_source
            FROM duplicate_groups dg
            JOIN emails e ON e.id = dg.canonical_email_id
            ORDER BY dg.duplicate_count DESC, dg.id
            LIMIT ? OFFSET ?
        """, (page_size, offset)).fetchall()

        groups = []
        for g in groups_rows:
            dup_rows = conn.execute("""
                SELECT de.email_id, de.similarity_score,
                       e.subject, e.sender_name, e.sender_email,
                       e.date_sent, e.mbox_source, e.message_id
                FROM duplicate_emails de
                JOIN emails e ON e.id = de.email_id
                WHERE de.group_id = ?
                ORDER BY e.date_sent
            """, (g["id"],)).fetchall()

            groups.append({
                "group_id": g["id"],
                "detection_method": g["detection_method"],
                "canonical": {
                    "id": g["canonical_email_id"],
                    "subject": g["subject"],
                    "sender_name": g["sender_name"],
                    "sender_email": g["sender_email"],
                    "date_sent": g["date_sent"],
                    "mbox_source": g["mbox_source"],
                },
                "duplicates": [
                    {
                        "id": r["email_id"],
                        "subject": r["subject"],
                        "sender_name": r["sender_name"],
                        "sender_email": r["sender_email"],
                        "date_sent": r["date_sent"],
                        "mbox_source": r["mbox_source"],
                        "message_id": r["message_id"],
                        "similarity_score": r["similarity_score"],
                    }
                    for r in dup_rows
                ],
            })

        return {
            "groups": groups,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }


def delete_duplicates(group_ids: list[int] | None = None, delete_all: bool = False) -> dict:
    """
    Delete duplicate emails, keeping the canonical (oldest / lowest ID).

    Args:
        group_ids: specific group IDs to process, or None for all
        delete_all: if True and group_ids is None, process every group

    Returns summary of deleted count, plus duplicates kept because a case references them.
    """
    deleted = kept = 0
    with get_db() as conn:
        if delete_all or group_ids is None:
            rows = conn.execute("SELECT id FROM duplicate_groups").fetchall()
            group_ids = [r["id"] for r in rows]

        for gid in group_ids:
            dup_email_ids = conn.execute(
                "SELECT email_id FROM duplicate_emails WHERE group_id = ?", (gid,)
            ).fetchall()
            group_kept = 0
            for row in dup_email_ids:
                # Case candidates reference emails; keep those rather than drop evidence.
                if conn.execute("SELECT 1 FROM case_candidates WHERE email_id = ? LIMIT 1",
                                (row["email_id"],)).fetchone():
                    group_kept += 1
                    continue
                conn.execute("DELETE FROM emails WHERE id = ?", (row["email_id"],))
                deleted += 1
            kept += group_kept
            if group_kept:  # group stays listed with only the kept duplicates
                conn.execute("UPDATE duplicate_groups SET duplicate_count = ? WHERE id = ?",
                             (group_kept, gid))
            else:
                conn.execute("DELETE FROM duplicate_groups WHERE id = ?", (gid,))

    log.info("🗑  Deleted %d duplicate emails (%d kept: used in cases)", deleted, kept)
    return {"deleted": deleted, "kept_in_cases": kept}


def dismiss_group(group_id: int) -> dict:
    """Mark a group as reviewed (not duplicates) without deleting emails."""
    with get_db() as conn:
        conn.execute("DELETE FROM duplicate_emails WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM duplicate_groups WHERE id = ?", (group_id,))
    return {"dismissed": group_id}
