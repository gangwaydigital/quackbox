import json

import pytest

from app.services import case_search as srch
from app.services import case_store as cs

DAY = 86400
T0 = 1704067200.0  # 2024-01-01 UTC


@pytest.fixture(autouse=True)
def no_semantic(monkeypatch):
    monkeypatch.setattr(srch, "semantic_search", lambda q, limit: [])
    monkeypatch.setattr(srch, "_generate_query_embedding", lambda t: object())


def _email(conn, n, body="body", recipients="[]", ts=T0, subject="s", sender="n@example.com"):
    eid = _email_row(conn, n, body, recipients, ts, subject, sender)
    conn.execute("INSERT INTO embeddings (email_id, embedding) VALUES (?, x'00')", (eid,))
    return eid


def _email_row(conn, n, body, recipients, ts, subject, sender):
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
        "keyword": 1, "recipients": 0, "attachments": 0, "semantic": 0, "semantic_capped": False}
    assert row["status"] == "ok" and row["finished_at"]


def test_channel_error_logged_others_run(fresh_db, monkeypatch):
    _email(fresh_db, 1, body="heron")
    def boom(q, limit):
        raise RuntimeError("index missing")
    monkeypatch.setattr(srch, "semantic_search", boom)
    cid, tid = _case(fresh_db, "heron")
    r = srch.run_term(fresh_db, cid, tid)
    assert r["status"] == "error" and "semantic" in r["error"] and r["channel_counts"]["keyword"] == 1


def test_semantic_embedding_failure_is_error(fresh_db, monkeypatch):
    e = _email(fresh_db, 1, body="egret")
    monkeypatch.setattr(srch, "_generate_query_embedding", lambda t: None)
    cid, tid = _case(fresh_db, "egret")
    r = srch.run_term(fresh_db, cid, tid)
    assert r["status"] == "error" and "embedding" in r["error"]
    assert e in _cands(fresh_db, cid)


def test_semantic_no_embeddings_indexed_is_error(fresh_db):
    fresh_db.execute(
        "INSERT INTO emails (message_id, subject, sender_email, body_text) VALUES ('x','s','a@b.test','kite')")
    cid, tid = _case(fresh_db, "kite")
    r = srch.run_term(fresh_db, cid, tid)
    assert r["status"] == "error" and "no embeddings" in r["error"]
    assert r["channel_counts"]["keyword"] == 1


def test_recipient_non_ascii_and_quote(fresh_db):
    a = _email(fresh_db, 1, recipients=json.dumps(["Jos\u00e9 N\u00fa\u00f1ez <jn@corp.test>"]))
    b = _email(fresh_db, 2, recipients=json.dumps(['Bob "The Boss" <bb@corp.test>']))
    for term, eid in (("Jos\u00e9", a), ("N\u00fa\u00f1ez", a), ('"The Boss"', b)):
        cid, tid = _case(fresh_db, term)
        srch.run_term(fresh_db, cid, tid)
        assert eid in _cands(fresh_db, cid), term


def test_semantic_capped_flag(fresh_db, monkeypatch):
    ids = [_email(fresh_db, i, body="zzz") for i in range(3)]
    monkeypatch.setattr(srch, "semantic_search", lambda q, limit: [{"id": i} for i in ids[:limit]])
    cid, tid = _case(fresh_db, "nomatchterm")
    assert srch.run_term(fresh_db, cid, tid, semantic_limit=2)["channel_counts"]["semantic_capped"] is True
    assert srch.run_term(fresh_db, cid, tid, semantic_limit=10)["channel_counts"]["semantic_capped"] is False
