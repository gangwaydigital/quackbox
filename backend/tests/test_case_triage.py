import pytest

from app.database import get_connection, init_db
from app.services import case_store as cs
from app.services import case_triage as ct


@pytest.fixture(autouse=True)
def _reset_status():
    def reset():
        ct.TRIAGE_STATUS.update(running=False, case_id=None, done=0, total=0,
                                cancelled=False, error=None)
    reset()
    yield
    reset()


@pytest.fixture
def seeded(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    conn = get_connection(db)
    cid = cs.create_case(conn, "c", "the issue", None, None)
    for n in range(5):
        eid = conn.execute(
            "INSERT INTO emails (message_id, subject, sender_email, date_timestamp, body_text)"
            " VALUES (?, 's', 'n@example.com', ?, 'body')", (f"m{n}", 100 + n)).lastrowid
        conn.execute("INSERT INTO case_candidates (case_id, email_id) VALUES (?, ?)", (cid, eid))
    conn.commit()
    yield db, cid, conn
    conn.close()


def _res(triage="relevant", error=None):
    return {"triage": triage, "reason": "why", "quote": "q", "quote_ok": True,
            "partial": False, "error": error}


def _states(conn):
    return [r[0] for r in conn.execute("SELECT triage FROM case_candidates ORDER BY email_id")]


def test_triage_updates_candidates(seeded, monkeypatch):
    db, cid, conn = seeded
    monkeypatch.setattr(ct, "triage_email", lambda issue, email: _res("maybe"))
    ct.run_triage_sync(cid, db)
    row = conn.execute("SELECT * FROM case_candidates LIMIT 1").fetchone()
    assert _states(conn) == ["maybe"] * 5
    assert row["triage_reason"] == "why" and row["model_quote"] == "q" and row["model_quote_ok"] == 1
    assert ct.TRIAGE_STATUS["done"] == 5 and ct.TRIAGE_STATUS["total"] == 5
    assert ct.TRIAGE_STATUS["running"] is False


def test_cancel_leaves_untriaged(seeded, monkeypatch):
    db, cid, conn = seeded
    calls = []

    def fake(issue, email):
        calls.append(email["id"])
        if len(calls) == 2:
            ct.request_cancel()
        return _res()

    monkeypatch.setattr(ct, "triage_email", fake)
    ct.run_triage_sync(cid, db)
    assert sorted(_states(conn)) == ["relevant"] * 2 + ["untriaged"] * 3
    assert ct.TRIAGE_STATUS["cancelled"] is True and ct.TRIAGE_STATUS["running"] is False


def test_error_is_per_candidate(seeded, monkeypatch):
    db, cid, conn = seeded
    n = {"i": 0}

    def fake(issue, email):
        n["i"] += 1
        if n["i"] == 1:
            return _res("untriaged", "Model unreachable")
        if n["i"] == 2:
            raise KeyError("choices")
        return _res("not")

    monkeypatch.setattr(ct, "triage_email", fake)
    ct.run_triage_sync(cid, db)
    rows = conn.execute("SELECT triage, triage_error FROM case_candidates").fetchall()
    assert sorted(r["triage"] for r in rows) == ["not"] * 3 + ["untriaged"] * 2
    errs = [r["triage_error"] for r in rows if r["triage"] == "untriaged"]
    assert "Model unreachable" in errs and any("KeyError" in e for e in errs)
    assert all(r["triage_error"] is None for r in rows if r["triage"] == "not")
    assert ct.TRIAGE_STATUS["done"] == 5 and ct.TRIAGE_STATUS["error"] is None


def test_unknown_case_sets_error(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    ct.run_triage_sync(999, db)
    assert ct.TRIAGE_STATUS["error"] and ct.TRIAGE_STATUS["running"] is False


def test_start_triage_false_while_running(seeded):
    db, cid, _ = seeded
    ct.TRIAGE_STATUS["running"] = True
    assert ct.start_triage(cid, db) is False


def test_connection_failure_resets_running(tmp_path, monkeypatch):
    def boom(_):
        raise OSError("cannot open")

    monkeypatch.setattr(ct, "get_connection", boom)
    ct.run_triage_sync(1, tmp_path / "x.db")
    assert ct.TRIAGE_STATUS["running"] is False and "cannot open" in ct.TRIAGE_STATUS["error"]


def test_submit_failure_resets_running(monkeypatch):
    def boom(*a):
        raise RuntimeError("shutdown")

    monkeypatch.setattr(ct._executor, "submit", boom)
    with pytest.raises(RuntimeError):
        ct.start_triage(1)
    assert ct.TRIAGE_STATUS["running"] is False


def test_triage_loads_only_needed_columns(seeded, monkeypatch):
    db, cid, conn = seeded
    keys = []
    monkeypatch.setattr(ct, "triage_email", lambda issue, email: keys.append(set(email)) or _res())
    ct.run_triage_sync(cid, db)
    assert keys and all(k == {"id", "subject", "sender_name", "sender_email", "date_sent",
                              "body_text", "recipients"} for k in keys)


def test_write_failure_is_per_candidate(seeded, monkeypatch):
    db, cid, conn = seeded
    n = {"i": 0}

    def fake(issue, email):
        n["i"] += 1
        return {**_res(), "reason": object()} if n["i"] == 1 else _res()  # unbindable value

    monkeypatch.setattr(ct, "triage_email", fake)
    ct.run_triage_sync(cid, db)
    assert sorted(_states(conn)) == ["relevant"] * 4 + ["untriaged"]
    assert ct.TRIAGE_STATUS["done"] == 5 and "1 candidate" in ct.TRIAGE_STATUS["error"]


def test_triage_processes_in_range_first(seeded, monkeypatch):
    db, cid, conn = seeded
    # newest email is out of range; it must be triaged last despite the newest date
    conn.execute("UPDATE case_candidates SET out_of_range = 1 WHERE email_id = "
                 "(SELECT MAX(id) FROM emails)")
    conn.commit()
    order = []

    def fake(issue, email):
        order.append(email["id"])
        return _res("maybe")

    monkeypatch.setattr(ct, "triage_email", fake)
    ct.run_triage_sync(cid, db)
    last = conn.execute("SELECT MAX(id) FROM emails").fetchone()[0]
    assert order[-1] == last and len(order) == 5
