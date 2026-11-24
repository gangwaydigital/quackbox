import json

import pytest
import requests

from app.services import case_ai


def fake(content, status=200, capture=None):
    def _c(model, messages, **kw):
        if capture is not None:
            capture.append((model, messages))
        return status, content, content
    return _c


def boom(*a, **kw):
    raise requests.ConnectionError("down")


def test_propose_dedupes_existing(monkeypatch):
    out = json.dumps({"terms": [{"text": "Alpha", "reason": "name"}, {"text": "beta", "reason": "nick"}]})
    monkeypatch.setattr(case_ai, "complete", fake(out))
    r = case_ai.propose_terms("an issue", [{"name": "Bob", "emails": ["b@x.com"]}], ["ALPHA"])
    assert r["error"] is None
    assert [t["text"] for t in r["terms"]] == ["beta"]


def test_propose_bad_json(monkeypatch):
    monkeypatch.setattr(case_ai, "complete", fake("not json"))
    r = case_ai.propose_terms("i", [], [])
    assert r["terms"] == [] and r["error"]


def test_propose_connection_error(monkeypatch):
    monkeypatch.setattr(case_ai, "complete", boom)
    r = case_ai.propose_terms("i", [], [])
    assert r["terms"] == [] and r["error"]


EMAIL = {"id": 1, "subject": "s", "sender_name": "A", "sender_email": "a@x.com",
         "date_sent": "2026-01-01", "body_text": "hello world", "recipients": "[]"}


def test_triage_truncates_and_flags_partial(monkeypatch):
    cap = []
    monkeypatch.setattr(case_ai, "complete", fake(json.dumps({"triage": "maybe", "reason": "r", "quote": None}), capture=cap))
    r = case_ai.triage_email("i", {**EMAIL, "body_text": "Q" * 7000})
    assert r["partial"] is True and r["triage"] == "maybe"
    prompt = cap[0][1][-1]["content"]
    assert prompt.count("Q") == 6000


def test_triage_quote_checked_against_full_body(monkeypatch):
    body = "a" * 6500 + " the late phrase"
    monkeypatch.setattr(case_ai, "complete", fake(json.dumps({"triage": "relevant", "reason": "r", "quote": "the late phrase"})))
    r = case_ai.triage_email("i", {**EMAIL, "body_text": body})
    assert r["quote_ok"] is True
    monkeypatch.setattr(case_ai, "complete", fake(json.dumps({"triage": "relevant", "reason": "r", "quote": "invented"})))
    r = case_ai.triage_email("i", EMAIL)
    assert r["quote_ok"] is False and r["quote"] == "invented" and r["triage"] == "relevant"


def test_triage_bad_json(monkeypatch):
    monkeypatch.setattr(case_ai, "complete", fake("nope"))
    r = case_ai.triage_email("i", EMAIL)
    assert r["triage"] == "untriaged" and r["error"]
    monkeypatch.setattr(case_ai, "complete", fake(json.dumps({"triage": "weird", "reason": "r"})))
    r = case_ai.triage_email("i", EMAIL)
    assert r["triage"] == "untriaged" and r["error"]


def test_triage_empty_body(monkeypatch):
    called = []
    monkeypatch.setattr(case_ai, "complete", fake("{}", capture=called))
    r = case_ai.triage_email("i", {**EMAIL, "body_text": "  "})
    assert r["triage"] == "not" and r["quote_ok"] is False and not called


def test_triage_connection_error(monkeypatch):
    monkeypatch.setattr(case_ai, "complete", boom)
    r = case_ai.triage_email("i", EMAIL)
    assert r["triage"] == "untriaged" and r["error"]


def _em(sender, rcpts):
    return {"sender_email": sender, "sender_name": "S", "recipients": json.dumps(rcpts)}


def test_people_in_evidence_counts_cc():
    cc = {"name": "Cee", "email": "CC@x.com", "type": "cc"}
    known = {"name": "K", "email": "k@x.com", "type": "to"}
    emails = [_em("a@x.com", [cc, known]), _em("a@x.com", [cc]), _em("K@x.com", [cc]),
              {"sender_email": "z@x.com", "recipients": None}, {"sender_email": "y@x.com", "recipients": "bad"}]
    r = case_ai.people_in_evidence(emails[:3], [{"name": "K", "emails": ["k@x.com"]}])
    assert r[0] == {"email": "cc@x.com", "name": "Cee", "count": 3}
    assert all(p["email"] != "k@x.com" for p in r)
    case_ai.people_in_evidence(emails, [])  # tolerates NULL / bad JSON


def test_find_more(monkeypatch):
    monkeypatch.setattr(case_ai, "complete", fake(json.dumps({"terms": [{"text": "t", "reason": "r"}]})))
    r = case_ai.find_more("i", [_em("a@x.com", [])], [], [])
    assert r["terms"][0]["text"] == "t" and r["people"][0]["email"] == "a@x.com" and r["error"] is None
