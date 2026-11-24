"""Storage layer for cases: people, search terms, candidate emails and review state."""
import json

from app.services.case_quotes import verify_quote

REVIEWS = ("unreviewed", "evidence", "not_relevant")
_TRIAGE_RANK = ("CASE triage WHEN 'relevant' THEN 0 WHEN 'maybe' THEN 1 "
                "WHEN 'untriaged' THEN 2 ELSE 3 END")


def create_case(conn, name, issue, date_from, date_to) -> int:
    cur = conn.execute(
        "INSERT INTO cases (name, issue, date_from, date_to) VALUES (?, ?, ?, ?)",
        (name, issue, date_from, date_to),
    )
    conn.commit()
    return cur.lastrowid


def get_case(conn, case_id) -> dict | None:
    row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    if not row:
        return None
    case = dict(row)
    case["people"] = [
        {**dict(p), "emails": json.loads(p["emails"])}
        for p in conn.execute("SELECT * FROM case_people WHERE case_id = ? ORDER BY id", (case_id,))
    ]
    case["terms"] = [
        dict(t) for t in conn.execute(
            "SELECT * FROM case_terms WHERE case_id = ? AND retired = 0 ORDER BY id", (case_id,))
    ]
    return case


def list_cases(conn) -> list[dict]:
    rows = conn.execute("""
        SELECT c.*,
          (SELECT COUNT(*) FROM case_candidates WHERE case_id = c.id) AS candidate_count,
          (SELECT COUNT(*) FROM case_candidates WHERE case_id = c.id AND review = 'evidence') AS evidence_count
        FROM cases c ORDER BY c.id DESC
    """).fetchall()
    return [dict(r) for r in rows]


def add_person(conn, case_id, name, emails) -> int:
    cur = conn.execute(
        "INSERT INTO case_people (case_id, name, emails) VALUES (?, ?, ?)",
        (case_id, name, json.dumps([e.strip().lower() for e in emails])),
    )
    conn.commit()
    return cur.lastrowid


def add_term(conn, case_id, text, source="owner") -> int:
    cur = conn.execute(
        "INSERT INTO case_terms (case_id, text, source) VALUES (?, ?, ?)", (case_id, text, source))
    conn.commit()
    return cur.lastrowid


def edit_term(conn, term_id, new_text) -> int:
    old = conn.execute("SELECT * FROM case_terms WHERE id = ?", (term_id,)).fetchone()
    if not old:
        raise ValueError(f"term {term_id} not found")
    conn.execute("UPDATE case_terms SET retired = 1 WHERE id = ?", (term_id,))
    cur = conn.execute(
        "INSERT INTO case_terms (case_id, text, version, replaces_id, source) VALUES (?, ?, ?, ?, ?)",
        (old["case_id"], new_text, old["version"] + 1, term_id, old["source"]),
    )
    conn.commit()
    return cur.lastrowid


def retire_term(conn, term_id) -> None:
    conn.execute("UPDATE case_terms SET retired = 1 WHERE id = ?", (term_id,))
    conn.commit()


def set_review(conn, case_id, email_id, review, note=None) -> None:
    if review not in REVIEWS:
        raise ValueError(f"review must be one of {REVIEWS}")
    conn.execute(
        "UPDATE case_candidates SET review = ?, note = ? WHERE case_id = ? AND email_id = ?",
        (review, note, case_id, email_id),
    )
    conn.commit()


def set_owner_quote(conn, case_id, email_id, quote) -> None:
    if quote is not None:
        row = conn.execute("SELECT body_text FROM emails WHERE id = ?", (email_id,)).fetchone()
        if not row or not verify_quote(quote, row["body_text"]):
            raise ValueError("quote not found in email body")
    conn.execute(
        "UPDATE case_candidates SET owner_quote = ? WHERE case_id = ? AND email_id = ?",
        (quote, case_id, email_id),
    )
    conn.commit()


def list_candidates(conn, case_id, review, triage, page, page_size) -> dict:
    where, args = ["cc.case_id = ?"], [case_id]
    if review:
        where.append("cc.review = ?")
        args.append(review)
    if triage:
        where.append("cc.triage = ?")
        args.append(triage)
    w = " AND ".join(where)
    total = conn.execute(f"SELECT COUNT(*) FROM case_candidates cc WHERE {w}", args).fetchone()[0]
    rows = conn.execute(
        f"""SELECT cc.*, e.subject, e.sender_name, e.sender_email, e.date_sent, e.date_timestamp
            FROM case_candidates cc JOIN emails e ON e.id = cc.email_id
            WHERE {w}
            ORDER BY cc.semantic_only ASC, {_TRIAGE_RANK},
                     e.date_timestamp IS NULL, e.date_timestamp DESC
            LIMIT ? OFFSET ?""",
        args + [page_size, (max(page, 1) - 1) * page_size],
    ).fetchall()
    return {"items": [dict(r) for r in rows], "total": total}
