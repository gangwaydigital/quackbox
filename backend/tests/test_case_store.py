import pytest

from app.services import case_store as cs


def _email(conn, n, ts=None, body="body", subject="s"):
    cur = conn.execute(
        "INSERT INTO emails (message_id, subject, sender_name, sender_email, date_timestamp, body_text)"
        " VALUES (?, ?, 'N', 'n@example.com', ?, ?)",
        (f"m{n}", subject, ts, body),
    )
    return cur.lastrowid


def _cand(conn, case_id, email_id, triage="untriaged", semantic_only=0):
    conn.execute(
        "INSERT INTO case_candidates (case_id, email_id, triage, semantic_only) VALUES (?, ?, ?, ?)",
        (case_id, email_id, triage, semantic_only),
    )


def test_create_and_get_case(fresh_db):
    cid = cs.create_case(fresh_db, "Case A", "an issue", "2024-01-01", None)
    cs.add_person(fresh_db, cid, "Alice", ["Alice@Example.com"])
    cs.add_term(fresh_db, cid, "invoice")
    case = cs.get_case(fresh_db, cid)
    assert case["name"] == "Case A" and case["issue"] == "an issue"
    assert case["people"][0]["emails"] == ["alice@example.com"]
    assert [t["text"] for t in case["terms"]] == ["invoice"]
    assert cs.get_case(fresh_db, 999) is None
    assert cs.list_cases(fresh_db)[0]["id"] == cid


def test_edit_term_versions_and_retires(fresh_db):
    cid = cs.create_case(fresh_db, "c", "i", None, None)
    old = cs.add_term(fresh_db, cid, "foo")
    new = cs.edit_term(fresh_db, old, "bar")
    o = fresh_db.execute("SELECT * FROM case_terms WHERE id=?", (old,)).fetchone()
    n = fresh_db.execute("SELECT * FROM case_terms WHERE id=?", (new,)).fetchone()
    assert o["retired"] == 1
    assert n["version"] == 2 and n["replaces_id"] == old and n["text"] == "bar"
    assert [t["id"] for t in cs.get_case(fresh_db, cid)["terms"]] == [new]


def test_retire_hides_term_from_get_case(fresh_db):
    cid = cs.create_case(fresh_db, "c", "i", None, None)
    t = cs.add_term(fresh_db, cid, "foo")
    cs.retire_term(fresh_db, t)
    assert cs.get_case(fresh_db, cid)["terms"] == []


def test_set_review_rejects_bad_value(fresh_db):
    cid = cs.create_case(fresh_db, "c", "i", None, None)
    e = _email(fresh_db, 1)
    _cand(fresh_db, cid, e)
    with pytest.raises(ValueError):
        cs.set_review(fresh_db, cid, e, "bogus")
    cs.set_review(fresh_db, cid, e, "evidence", "note")
    row = fresh_db.execute("SELECT review, note FROM case_candidates").fetchone()
    assert (row["review"], row["note"]) == ("evidence", "note")


def test_owner_quote_must_exist_in_body(fresh_db):
    cid = cs.create_case(fresh_db, "c", "i", None, None)
    e = _email(fresh_db, 1, body="Please pay the invoice by Friday.")
    _cand(fresh_db, cid, e)
    with pytest.raises(ValueError):
        cs.set_owner_quote(fresh_db, cid, e, "not in the body")
    cs.set_owner_quote(fresh_db, cid, e, "pay the invoice")
    q = lambda: fresh_db.execute("SELECT owner_quote FROM case_candidates").fetchone()[0]
    assert q() == "pay the invoice"
    cs.set_owner_quote(fresh_db, cid, e, None)
    assert q() is None


def test_list_candidates_order(fresh_db):
    cid = cs.create_case(fresh_db, "c", "i", None, None)
    sem = _email(fresh_db, 1, 500.0)
    maybe = _email(fresh_db, 2, 100.0)
    rel_old = _email(fresh_db, 3, 100.0)
    rel_new = _email(fresh_db, 4, 200.0)
    rel_null = _email(fresh_db, 5, None)
    _cand(fresh_db, cid, sem, "relevant", 1)
    _cand(fresh_db, cid, maybe, "maybe")
    _cand(fresh_db, cid, rel_old, "relevant")
    _cand(fresh_db, cid, rel_new, "relevant")
    _cand(fresh_db, cid, rel_null, "relevant")
    res = cs.list_candidates(fresh_db, cid, None, None, 1, 10)
    assert res["total"] == 5
    assert [i["email_id"] for i in res["items"]] == [rel_new, rel_old, rel_null, maybe, sem]
    assert res["items"][0]["subject"] == "s"
    page = cs.list_candidates(fresh_db, cid, None, "maybe", 1, 10)
    assert page["total"] == 1
    assert len(cs.list_candidates(fresh_db, cid, None, None, 2, 2)["items"]) == 2
