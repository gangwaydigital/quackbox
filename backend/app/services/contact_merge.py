"""
Contact merge service.
Identifies duplicate contacts (same person, different email addresses)
and allows merging them for unified profiles.
"""
import re
from collections import defaultdict
from app.database import get_db


def find_merge_candidates(min_similarity=0.7):
    """
    Find contacts that might be the same person based on name similarity.
    Returns groups of potentially duplicate contacts.
    """
    with get_db() as conn:
        rows = conn.execute("""
            SELECT sender_email, MAX(sender_name) as name, COUNT(*) as count
            FROM emails
            WHERE sender_email != '' AND sender_email IS NOT NULL
              AND sender_name IS NOT NULL AND sender_name != ''
            GROUP BY sender_email
            HAVING count >= 2
            ORDER BY name ASC
        """).fetchall()

    # Group by normalized name
    name_groups = defaultdict(list)
    for row in rows:
        normalized = _normalize_name(row["name"])
        if normalized and len(normalized) > 2:
            name_groups[normalized].append({
                "email": row["sender_email"],
                "name": row["name"],
                "count": row["count"]
            })

    # Also check for same base email domain patterns
    domain_groups = defaultdict(list)
    for row in rows:
        local = row["sender_email"].split("@")[0].lower()
        # Strip numbers and dots from local part
        base = re.sub(r'[0-9._]', '', local)
        if base and len(base) > 2:
            key = base + "@" + row["sender_email"].split("@")[-1].lower()
            domain_groups[key].append({
                "email": row["sender_email"],
                "name": row["name"],
                "count": row["count"]
            })

    # Collect groups with 2+ members
    candidates = []
    seen_groups = set()

    for norm_name, contacts in name_groups.items():
        if len(contacts) >= 2:
            key = tuple(sorted(c["email"] for c in contacts))
            if key not in seen_groups:
                seen_groups.add(key)
                candidates.append({
                    "match_type": "name",
                    "match_key": norm_name,
                    "contacts": contacts,
                    "total_emails": sum(c["count"] for c in contacts)
                })

    for key, contacts in domain_groups.items():
        if len(contacts) >= 2:
            group_key = tuple(sorted(c["email"] for c in contacts))
            if group_key not in seen_groups:
                seen_groups.add(group_key)
                candidates.append({
                    "match_type": "email_pattern",
                    "match_key": key,
                    "contacts": contacts,
                    "total_emails": sum(c["count"] for c in contacts)
                })

    candidates.sort(key=lambda x: -x["total_emails"])
    return candidates


def merge_contacts(primary_email: str, secondary_emails: list):
    """
    Merge secondary contacts into a primary contact.
    Updates all emails from secondary addresses to appear under the primary's name.
    Returns count of updated records.
    """
    with get_db() as conn:
        # Get primary name
        primary = conn.execute(
            "SELECT sender_name FROM emails WHERE sender_email = ? AND sender_name IS NOT NULL LIMIT 1",
            (primary_email,)
        ).fetchone()

        if not primary:
            return {"error": f"Primary contact {primary_email} not found"}

        # Validate every secondary exists — otherwise the merge looks successful but does nothing
        targets = [e for e in secondary_emails if e and e != primary_email]
        if not targets:
            return {"error": "No secondary contacts to merge"}

        placeholders = ",".join("?" for _ in targets)
        existing = {
            row["sender_email"] for row in conn.execute(
                f"SELECT DISTINCT sender_email FROM emails WHERE sender_email IN ({placeholders})",
                targets,
            ).fetchall()
        }
        missing = [e for e in targets if e not in existing]
        if missing:
            return {"error": f"Secondary contact(s) not found: {', '.join(missing)}"}

        primary_name = primary["sender_name"]
        total_updated = 0

        for sec_email in targets:
            result = conn.execute(
                "UPDATE emails SET sender_email = ?, sender_name = ? WHERE sender_email = ?",
                (primary_email, primary_name, sec_email)
            )
            total_updated += result.rowcount

        return {
            "primary": primary_email,
            "merged": targets,
            "updated_records": total_updated,
            "primary_name": primary_name,
        }


def _normalize_name(name):
    """Normalize a name for comparison."""
    if not name:
        return ""
    # Lowercase, remove common prefixes/suffixes
    n = name.lower().strip()
    # Remove common email-style formats
    n = re.sub(r'<[^>]+>', '', n).strip()
    # Remove quotes
    n = n.strip('"\'')
    # Remove titles
    for title in ['mr', 'mrs', 'ms', 'dr', 'prof']:
        n = re.sub(rf'^{title}\.?\s+', '', n)
    # Just keep letters and spaces
    n = re.sub(r'[^a-z\s]', '', n)
    # Collapse spaces
    n = re.sub(r'\s+', ' ', n).strip()
    return n
