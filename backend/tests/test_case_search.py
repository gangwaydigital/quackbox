import json

import pytest

from app.services import case_search as srch
from app.services import case_store as cs

DAY = 86400
T0 = 1704067200.0  # 2024-01-01 UTC


@pytest.fixture(autouse=True)
def no_semantic(monkeypatch):
    monkeypatch.setattr(srch, "semantic_search", lambda q, limit: [])


def _email(conn, n, body="body", recipients="[]", ts=T0, subject="s", sender="n@example.com"):
    return conn.execute(
        "INSERT INTO emails (message_id, subject, sender_name, sender_email, recipients, date_timestamp, body_text)"
        " VALUES (?, ?, 'N', ?, ?, ?, ?)",
        (f"m{n}", subject, sender, recipients, ts, body)).lastrowid


def _case(conn, term, df=None, dt=None):
    cid = cs.create_case(conn, "c", "issue", df, dt)
    return cid, cs.add_term(conn, cid, term)


def _cands(conn, cid):
    return {r["email_id"]: dict(r) for r in conn.execute("SELECT * FROM case_candidates WHERE case_id=?", (cid,))}


def test_keyword_hit_beyond_500_chars(fresh_db):
    e = _email(fresh_db, 1, body="x " * 1000 + "zebrafish")
    cid, tid = _case(fresh_db, "zebrafish")
    r = srch.run_term(fresh_db, cid, tid)
    assert r["status"] == "ok" and e in _cands(fresh_db, cid)
    assert r["channel_counts"]["keyword"] == 1


def test_recipient_only_match(fresh_db):
    e = _email(fresh_db, 1, recipients=json.dumps(["Carol <carol@corp.test>"]))
    cid, tid = _case(fresh_db, "carol@corp.test")
    r = srch.run_term(fresh_db, cid, tid)
    assert e in _cands(fresh_db, cid)
    assert r["channel_counts"]["recipients"] == 1
    ch = fresh_db.execute("SELECT channel FROM case_candidate_runs WHERE email_id=?", (e,)).fetchall()
    assert "recipients" in [c[0] for c in ch]


def test_semantic_only_flag(fresh_db, monkeypatch):
    a = _email(fresh_db, 1, body="nothing here")
    b = _email(fresh_db, 2, body="the quokka is here")
    monkeypatch.setattr(srch, "semantic_search", lambda q, limit: [{"id": a}, {"id": b}])
    cid, tid = _case(fresh_db, "quokka")
    srch.run_term(fresh_db, cid, tid)
    c = _cands(fresh_db, cid)
    assert c[a]["semantic_only"] == 1 and c[b]["semantic_only"] == 0


def test_null_date_kept_and_out_of_range_badged(fresh_db):
    old = _email(fresh_db, 1, body="gizmo", ts=T0 - 10 * DAY)
    inside = _email(fresh_db, 2, body="gizmo", ts=T0 + DAY)
    nodate = _email(fresh_db, 3, body="gizmo", ts=None)
    cid, tid = _case(fresh_db, "gizmo", "2024-01-01", "2024-01-31")
    srch.run_term(fresh_db, cid, tid)
    c = _cands(fresh_db, cid)
    assert (c[old]["out_of_range"], c[inside]["out_of_range"], c[nodate]["out_of_range"]) == (1, 0, 0)


@pytest.mark.parametrize("term", ["O'Brien", "re: offsite", '"quoted"', "x-ray"])
def test_hostile_terms_run_and_log(fresh_db, term):
    _email(fresh_db, 1, body="x-ray re: offsite")
    cid, tid = _case(fresh_db, term)
    r = srch.run_term(fresh_db, cid, tid)
    assert r["status"] == "ok" and r["error"] is None
    assert fresh_db.execute("SELECT COUNT(*) FROM case_runs").fetchone()[0] == 1


def test_star_only_term_raises_before_run(fresh_db):
    cid, tid = _case(fresh_db, "*")
    with pytest.raises(ValueError):
        srch.run_term(fresh_db, cid, tid)
    assert fresh_db.execute("SELECT COUNT(*) FROM case_runs").fetchone()[0] == 0


def test_to_fts_phrase():
    assert srch.to_fts_phrase('a"b') == '"a""b"'
    assert srch.to_fts_phrase("apol*") == '"apol"*'
    with pytest.raises(ValueError):
        srch.to_fts_phrase("")


def test_broad_term_no_duplicates(fresh_db):
    ids = [_email(fresh_db, i, body="acme deal", sender="acme@x.test") for i in range(3)]
    cid, tid = _case(fresh_db, "acme")
    srch.run_term(fresh_db, cid, tid)
    assert set(_cands(fresh_db, cid)) == set(ids)
    assert fresh_db.execute("SELECT COUNT(*) FROM case_candidate_runs").fetchone()[0] == 6


def test_attachment_channel(fresh_db):
    e = _email(fresh_db, 1, body="see attached")
    fresh_db.execute("INSERT INTO attachment_content (email_id, filename, extracted_text) VALUES (?, 'a.pdf', 'contains walrus text')", (e,))
    cid, tid = _case(fresh_db, "walrus")
    r = srch.run_term(fresh_db, cid, tid)
    assert r["channel_counts"]["attachments"] == 1 and e in _cands(fresh_db, cid)


def test_rerun_preserves_review(fresh_db):
    a = _email(fresh_db, 1, body="the ledger shows it")
    cid, tid = _case(fresh_db, "ledger")
    srch.run_term(fresh_db, cid, tid)
    cs.set_review(fresh_db, cid, a, "evidence", "keep")
    cs.set_owner_quote(fresh_db, cid, a, "ledger shows")
    b = _email(fresh_db, 2, body="another ledger")
    r = srch.run_term(fresh_db, cid, tid)
    c = _cands(fresh_db, cid)
    assert r["new_candidates"] == 1 and b in c
    assert (c[a]["review"], c[a]["note"], c[a]["owner_quote"]) == ("evidence", "keep", "ledger shows")
    assert fresh_db.execute("SELECT COUNT(*) FROM case_runs").fetchone()[0] == 2


def test_run_logs_channel_counts(fresh_db):
    _email(fresh_db, 1, body="plover")
    cid, tid = _case(fresh_db, "plover")
    r = srch.run_term(fresh_db, cid, tid)
    row = fresh_db.execute("SELECT * FROM case_runs WHERE id=?", (r["run_id"],)).fetchone()
    assert json.loads(row["channel_counts"]) == r["channel_counts"] == {
        "keyword": 1, "recipients": 0, "attachments": 0, "semantic": 0}
    assert row["status"] == "ok" and row["finished_at"]


def test_channel_error_logged_others_run(fresh_db, monkeypatch):
    _email(fresh_db, 1, body="heron")
    def boom(q, limit):
        raise RuntimeError("index missing")
    monkeypatch.setattr(srch, "semantic_search", boom)
    cid, tid = _case(fresh_db, "heron")
    r = srch.run_term(fresh_db, cid, tid)
    assert r["status"] == "error" and "semantic" in r["error"] and r["channel_counts"]["keyword"] == 1
