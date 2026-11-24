"""Run one case search term across keyword, recipient, attachment and semantic channels."""
import json
from datetime import datetime, timezone

from app.services.semantic_search import _generate_query_embedding, semantic_search


def to_fts_phrase(term: str) -> str:
    """Quote a term as an FTS5 phrase; a trailing * stays outside the quotes as a prefix match."""
    t = term.strip()
    prefix = t.endswith("*")
    t = t.rstrip("*").strip()
    if not t:
        raise ValueError("empty search term")
    return '"' + t.replace('"', '""') + '"' + ("*" if prefix else "")


def person_terms(person: dict) -> list[str]:
    return [person["name"], *person["emails"]]


def _like(text: str) -> str:
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _epoch(date_iso, end_of_day=False):
    if not date_iso:
        return None
    ts = datetime.fromisoformat(date_iso).replace(tzinfo=timezone.utc).timestamp()
    return ts + 86400 if end_of_day else ts


def _keyword(conn, term):
    phrase = to_fts_phrase(term)
    return [r[0] for r in conn.execute("SELECT rowid FROM emails_fts WHERE emails_fts MATCH ?", (phrase,))]


def _recipients(conn, term):
    like = _like(term.strip().rstrip("*"))
    # Match recipient values (name/email), never the JSON keys. Plain-string elements and
    # non-JSON rows fall back to matching their raw text. Unindexed scan: fine per term.
    return [r[0] for r in conn.execute(
        """SELECT id FROM emails WHERE sender_email LIKE ? ESCAPE '\\' OR sender_name LIKE ? ESCAPE '\\'
           OR (json_valid(recipients) AND EXISTS (
                 SELECT 1 FROM json_each(CASE WHEN json_valid(recipients) THEN recipients ELSE '[]' END) j
                 WHERE CASE WHEN j.type = 'object'
                            THEN json_extract(j.value, '$.email') LIKE ? ESCAPE '\\'
                                 OR json_extract(j.value, '$.name') LIKE ? ESCAPE '\\'
                            ELSE j.type = 'text' AND j.value LIKE ? ESCAPE '\\' END))
           OR (NOT json_valid(recipients) AND recipients LIKE ? ESCAPE '\\')""",
        (like,) * 6)]


def _attachments(conn, term):
    phrase = to_fts_phrase(term)
    return [r[0] for r in conn.execute(
        """SELECT DISTINCT ac.email_id FROM attachment_fts
           JOIN attachment_content ac ON ac.id = attachment_fts.rowid
           WHERE attachment_fts MATCH ? AND ac.email_id IS NOT NULL""", (phrase,))]


def _semantic(conn, term, limit):
    # semantic_search swallows embedding failures and returns []; surface them instead.
    if _generate_query_embedding(term) is None:
        raise RuntimeError("query embedding failed")
    if conn.execute("SELECT 1 FROM embeddings LIMIT 1").fetchone() is None:
        raise RuntimeError("no embeddings indexed")
    return [r["id"] for r in semantic_search(term, limit)]


def run_term(conn, case_id: int, term_id: int, semantic_limit: int = 50) -> dict:
    case = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    term = conn.execute(
        "SELECT * FROM case_terms WHERE id = ? AND case_id = ?", (term_id, case_id)).fetchone()
    if not case or not term:
        raise ValueError("case or term not found")
    text = term["text"]
    to_fts_phrase(text)  # ValueError before any run row

    started = datetime.now(timezone.utc).isoformat()
    run_id = conn.execute(
        "INSERT INTO case_runs (case_id, term_id, started_at, status) VALUES (?, ?, ?, 'running')",
        (case_id, term_id, started)).lastrowid

    channels = {
        "keyword": lambda: _keyword(conn, text),
        "recipients": lambda: _recipients(conn, text),
        "attachments": lambda: _attachments(conn, text),
        "semantic": lambda: _semantic(conn, text, semantic_limit),
    }
    counts, errors, hits = {}, [], {}
    for name, fn in channels.items():
        try:
            hits[name] = list(dict.fromkeys(fn()))
            counts[name] = len(hits[name])
        except Exception as e:  # one channel failing must not hide the others
            counts[name] = 0
            errors.append(f"{name}: {e}")

    counts["semantic_capped"] = counts["semantic"] == semantic_limit
    lo, hi = _epoch(case["date_from"]), _epoch(case["date_to"], True)
    existing = {r[0] for r in conn.execute("SELECT email_id FROM case_candidates WHERE case_id = ?", (case_id,))}
    new = 0
    for name, ids in hits.items():
        sem = 1 if name == "semantic" else 0
        for eid in ids:
            ts = conn.execute("SELECT date_timestamp FROM emails WHERE id = ?", (eid,)).fetchone()
            if ts is None:
                continue
            ts = ts[0]
            oor = int(ts is not None and ((lo is not None and ts < lo) or (hi is not None and ts >= hi)))
            conn.execute(
                """INSERT INTO case_candidates (case_id, email_id, semantic_only, out_of_range)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(case_id, email_id) DO UPDATE SET
                     semantic_only = CASE WHEN excluded.semantic_only = 0 THEN 0
                                          ELSE case_candidates.semantic_only END,
                     out_of_range = excluded.out_of_range""",
                (case_id, eid, sem, oor))
            conn.execute(
                "INSERT OR IGNORE INTO case_candidate_runs (case_id, email_id, run_id, channel) VALUES (?, ?, ?, ?)",
                (case_id, eid, run_id, name))
            if eid not in existing:
                existing.add(eid)
                new += 1

    status = "error" if errors else "ok"
    error = "; ".join(errors) or None
    conn.execute(
        "UPDATE case_runs SET finished_at = ?, status = ?, channel_counts = ?, error = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), status, json.dumps(counts), error, run_id))
    conn.commit()
    return {"run_id": run_id, "status": status, "channel_counts": counts,
            "new_candidates": new, "error": error}
