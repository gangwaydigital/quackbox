"""Cases REST API tests (no network: semantic search and model calls are patched)."""
import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.routers import cases as cases_router
from app.services import case_search, case_triage


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "cases-api.db"
    database.init_db(db_path)
    real_get_db = database.get_db
    monkeypatch.setattr(cases_router, "get_db", lambda p=db_path: real_get_db(p))
    monkeypatch.setattr(case_search, "_generate_query_embedding", lambda t: [0.0])
    monkeypatch.setattr(case_search, "semantic_search", lambda t, n: [])
    with real_get_db(db_path) as conn:
        for subj, body, ts in [("Budget review", "Please cancel the budget meeting", 1705305600.0),
                               ("Lunch", "Pizza at noon", 1707523200.0)]:
            conn.execute("INSERT INTO emails (subject, sender_email, body_text, date_timestamp, "
                         "date_sent) VALUES (?,?,?,?,?)", (subj, "a@x.com", body, ts, "2024-01-15"))
    return TestClient(app)


def _mk(client):
    return client.post("/api/cases", json={"name": "C", "issue": "budget"}).json()["id"]


def _candidate(client):
    cid = _mk(client)
    tid = client.post(f"/api/cases/{cid}/terms", json={"text": "budget"}).json()["id"]
    client.post(f"/api/cases/{cid}/terms/{tid}/run")
    return cid, tid


def test_create_add_term_run_and_list_candidates(client):
    cid, tid = _candidate(client)
    r = client.post(f"/api/cases/{cid}/people", json={"name": "Al", "emails": ["A@x.com"]})
    assert r.status_code == 200
    case = client.get(f"/api/cases/{cid}").json()
    assert case["attachments_indexed"] is False
    assert [t["text"] for t in case["terms"]] == ["budget", "Al", "a@x.com"]
    assert {t["source"] for t in case["terms"]} == {"owner"}
    runs = client.get(f"/api/cases/{cid}/runs").json()
    assert runs[0]["status"] == "error"  # no embeddings indexed in the test DB
    c = client.get(f"/api/cases/{cid}/candidates").json()
    assert c["total"] == 1 and c["items"][0]["subject"] == "Budget review"
    assert len(client.post(f"/api/cases/{cid}/run-all").json()) == 3
    assert client.get("/api/cases").json()[0]["candidate_count"] == 2  # person terms also match a@x.com


def test_bad_review_400(client):
    cid, _ = _candidate(client)
    eid = client.get(f"/api/cases/{cid}/candidates").json()["items"][0]["email_id"]
    assert client.put(f"/api/cases/{cid}/candidates/{eid}", json={"review": "bogus"}).status_code == 400
    assert client.put(f"/api/cases/{cid}/candidates/{eid}", json={"review": "evidence"}).status_code == 200


def test_owner_quote_unverifiable_400(client):
    cid, _ = _candidate(client)
    eid = client.get(f"/api/cases/{cid}/candidates").json()["items"][0]["email_id"]
    r = client.put(f"/api/cases/{cid}/candidates/{eid}", json={"owner_quote": "not there"})
    assert r.status_code == 400 and r.json()["detail"] == "That text isn't in the email."
    assert client.put(f"/api/cases/{cid}/candidates/{eid}",
                      json={"owner_quote": "cancel the budget"}).status_code == 200


def test_partial_updates_keep_note_and_are_atomic(client):
    cid, _ = _candidate(client)
    eid = client.get(f"/api/cases/{cid}/candidates").json()["items"][0]["email_id"]
    url = f"/api/cases/{cid}/candidates/{eid}"
    first = lambda: client.get(f"/api/cases/{cid}/candidates").json()["items"][0]
    client.put(url, json={"note": "keep me"})
    client.put(url, json={"review": "evidence"})
    assert first()["note"] == "keep me" and first()["review"] == "evidence"
    r = client.put(url, json={"review": "not_relevant", "owner_quote": "nope"})
    assert r.status_code == 400 and first()["review"] == "evidence"
    client.put(url, json={"note": None})
    assert first()["note"] is None


def test_bad_term_source_422(client):
    cid = _mk(client)
    assert client.post(f"/api/cases/{cid}/terms", json={"text": "x", "source": "bogus"}).status_code == 422


def test_triage_conflict_409(client, monkeypatch):
    cid = _mk(client)
    monkeypatch.setattr(case_triage, "start_triage", lambda c: False)
    assert client.post(f"/api/cases/{cid}/triage").status_code == 409
    monkeypatch.setattr(case_triage, "start_triage", lambda c: True)
    assert client.post(f"/api/cases/{cid}/triage").status_code == 200
    assert "running" in client.get("/api/cases/triage/status").json()
    assert client.post("/api/cases/triage/cancel").status_code == 200
    case_triage.TRIAGE_STATUS["cancelled"] = False


def test_export_returns_zip(client):
    cid, _ = _candidate(client)
    r = client.get(f"/api/cases/{cid}/export")
    assert r.headers["content-type"] == "application/zip"
    assert f"case-{cid}-" in r.headers["content-disposition"]
    assert zipfile.ZipFile(io.BytesIO(r.content)).namelist()


def test_missing_case_404(client, monkeypatch):
    monkeypatch.setattr(case_triage, "start_triage", lambda c: True)
    for method, path in [("get", ""), ("get", "/export"), ("get", "/runs"), ("post", "/propose"),
                         ("post", "/find-more"), ("post", "/triage"), ("post", "/run-all"),
                         ("post", "/terms/1/run")]:
        assert getattr(client, method)(f"/api/cases/999{path}").status_code == 404, path


def test_missing_candidate_404(client):
    cid = _mk(client)
    assert client.put(f"/api/cases/{cid}/candidates/12345", json={"review": "evidence"}).status_code == 404


def test_retired_term_edit_409(client):
    cid, tid = _candidate(client)
    assert client.delete(f"/api/cases/terms/{tid}").status_code == 200
    assert client.put(f"/api/cases/terms/{tid}", json={"text": "x"}).status_code == 409
    assert client.post(f"/api/cases/{cid}/terms/{tid}/run").status_code == 409
    assert client.put("/api/cases/terms/9999", json={"text": "x"}).status_code == 404
    other = _mk(client)
    t2 = client.post(f"/api/cases/{cid}/terms", json={"text": "y"}).json()["id"]
    assert client.post(f"/api/cases/{other}/terms/{t2}/run").status_code == 404


def test_empty_term_400(client):
    cid = _mk(client)
    assert client.post(f"/api/cases/{cid}/terms", json={"text": " * "}).status_code == 400


def test_propose_and_find_more_use_services(client, monkeypatch):
    cid, _ = _candidate(client)
    eid = client.get(f"/api/cases/{cid}/candidates").json()["items"][0]["email_id"]
    client.put(f"/api/cases/{cid}/candidates/{eid}", json={"review": "evidence"})
    seen = {}
    monkeypatch.setattr(cases_router, "propose_terms", lambda i, p, e: {"terms": ["p"], "error": None})
    def fm(issue, ev, ex, people):
        seen.update(ev=ev, ex=ex)
        return {"terms": [], "error": None, "people": []}
    monkeypatch.setattr(cases_router, "find_more", fm)
    assert client.post(f"/api/cases/{cid}/propose").json()["terms"] == ["p"]
    client.post(f"/api/cases/{cid}/find-more")
    assert seen["ex"] == ["budget"] and seen["ev"][0]["body_text"].startswith("Please cancel")


def test_runs_report_each_runs_own_term_version(client):
    cid, tid = _candidate(client)
    new_tid = client.put(f"/api/cases/terms/{tid}", json={"text": "budget meeting"}).json()["id"]
    client.post(f"/api/cases/{cid}/terms/{new_tid}/run")
    runs = client.get(f"/api/cases/{cid}/runs").json()  # newest first
    assert [(r["term_version"], r["term_retired"]) for r in runs] == [(2, 0), (1, 1)]
