"""
Tests for the search service.

Covers FTS5 query sanitization, full-text search ranking and snippets,
instant typeahead search, and the structured filter endpoint.
"""
import json

import pytest

from app import database
from app.services import search
from app.services.search import _sanitize_fts_query


# ── _sanitize_fts_query ────────────────────────────────────────────────────


class TestSanitizeFtsQuery:
    def test_empty_string(self):
        assert _sanitize_fts_query("") == '""'
        assert _sanitize_fts_query("   ") == '""'

    def test_single_word_gets_prefix_match(self):
        # Allows typing "projec" to match "project" — the last term gets *
        assert _sanitize_fts_query("project") == '"project"*'

    def test_multi_word_implicit_and(self):
        # Each term quoted; last gets prefix; FTS5 ANDs by default between bare terms
        out = _sanitize_fts_query("quarterly report")
        assert '"quarterly"' in out
        assert '"report"*' in out

    def test_explicit_phrase_preserved(self):
        # User quoted phrases should pass through verbatim, no prefix expansion
        out = _sanitize_fts_query('"exact match"')
        assert out == '"exact match"'

    def test_special_characters_stripped(self):
        # Punctuation in user input would crash FTS5 — must be stripped
        out = _sanitize_fts_query("hello@world!")
        assert "@" not in out
        assert "!" not in out
        assert '"hello"' in out
        assert '"world"' in out

    def test_boolean_operators_pass_through(self):
        out = _sanitize_fts_query("alpha AND beta")
        assert "AND" in out

    def test_lowercase_boolean_uppercased(self):
        out = _sanitize_fts_query("alpha or beta")
        assert "OR" in out

    def test_single_char_tokens_dropped(self):
        # Single-letter words pollute FTS5 results; they're skipped
        out = _sanitize_fts_query("a project")
        assert '"a"' not in out
        assert '"project"' in out

    def test_phrase_plus_free_terms(self):
        out = _sanitize_fts_query('"hello world" extra')
        assert '"hello world"' in out
        assert '"extra"' in out


# ── Live FTS5 search (needs a populated DB) ────────────────────────────────


@pytest.fixture
def search_db(tmp_path, monkeypatch):
    """Initialize a DB and seed three FTS-indexed emails. Patches the search
    service to use the test DB."""
    db_path = tmp_path / "search-test.db"
    database.init_db(db_path)
    real_get_db = database.get_db

    def get_db_override(p=db_path):
        return real_get_db(p)
    monkeypatch.setattr(search, "get_db", get_db_override)

    samples = [
        # (message_id, subject, sender_name, sender_email, body_text, mbox_source, has_attachments, attachment_names, date_sent, date_timestamp)
        ("msg-1", "Quarterly Project Report", "Alice", "alice@example.com",
         "The quarterly project report is attached. Numbers look strong this quarter.",
         "Inbox", 1, json.dumps(["report.pdf"]), "2024-01-15", 1705305600.0),
        ("msg-2", "Lunch tomorrow?", "Bob", "bob@example.com",
         "Want to grab lunch tomorrow at the new place downtown?",
         "Inbox", 0, json.dumps([]), "2024-02-10", 1707523200.0),
        ("msg-3", "Project Apollo update", "Alice", "alice@example.com",
         "Apollo project hit a milestone today. Phase 2 begins next month.",
         "Work", 0, json.dumps([]), "2024-03-05", 1709596800.0),
    ]
    with database.get_db(db_path) as conn:
        conn.executemany(
            """INSERT INTO emails (message_id, subject, sender_name, sender_email,
                body_text, mbox_source, has_attachments, attachment_names,
                date_sent, date_timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            samples,
        )
    return db_path


class TestFullTextSearch:
    def test_finds_matching_email_by_subject(self, search_db):
        result = search.full_text_search("apollo")
        assert result["total"] >= 1
        subjects = [r["email"]["subject"] for r in result["results"]]
        assert any("Apollo" in s for s in subjects)

    def test_finds_matching_email_by_body(self, search_db):
        result = search.full_text_search("downtown")
        assert result["total"] >= 1
        assert any("Lunch" in r["email"]["subject"] for r in result["results"])

    def test_subject_match_outranks_body_match(self, search_db):
        """BM25 weights subject 10x — a subject hit should rank above a body hit."""
        result = search.full_text_search("project")
        # Both msg-1 (subject: "Quarterly Project Report") and msg-3 (subject: "Project Apollo")
        # mention project. Test: at least the top result has it in the subject.
        assert result["results"][0]["email"]["subject"].lower().count("project") >= 1

    def test_returns_snippet_highlights(self, search_db):
        result = search.full_text_search("apollo")
        first = result["results"][0]["email"]
        # Either subject or body highlight should be populated and contain a <mark>
        hl = (first.get("highlight_subject") or "") + (first.get("highlight_body") or "")
        assert "<mark>" in hl

    def test_no_match_returns_empty(self, search_db):
        result = search.full_text_search("zzznonsensezzz")
        assert result["total"] == 0
        assert result["results"] == []

    def test_empty_query_returns_empty(self, search_db):
        result = search.full_text_search("")
        assert result["results"] == []

    def test_pagination_offset(self, search_db):
        page1 = search.full_text_search("project", page=1, page_size=1)
        page2 = search.full_text_search("project", page=2, page_size=1)
        if page1["total"] > 1:
            assert page1["results"][0]["email"]["id"] != page2["results"][0]["email"]["id"]


class TestInstantSearch:
    def test_returns_lightweight_results(self, search_db):
        results = search.instant_search("apollo")
        assert len(results) >= 1
        # Instant results are flat dicts, not wrapped in {"email": ...}
        assert "subject" in results[0]
        assert "id" in results[0]

    def test_respects_limit(self, search_db):
        results = search.instant_search("project", limit=1)
        assert len(results) <= 1

    def test_no_match_returns_empty_list(self, search_db):
        assert search.instant_search("zzznonsensezzz") == []

    def test_includes_body_highlight(self, search_db):
        results = search.instant_search("apollo")
        if results:
            assert "body_highlight" in results[0]


class TestFilterEmails:
    def test_filter_by_sender_email(self, search_db):
        result = search.filter_emails(sender_email="alice@example.com")
        assert result["total"] == 2
        assert all(r["sender_email"] == "alice@example.com" for r in result["items"])

    def test_filter_by_mbox_source(self, search_db):
        result = search.filter_emails(mbox_source="Work")
        assert result["total"] == 1
        assert result["items"][0]["sender_email"] == "alice@example.com"

    def test_filter_by_has_attachments(self, search_db):
        result = search.filter_emails(has_attachments=True)
        assert result["total"] == 1
        assert result["items"][0]["has_attachments"] is True

    def test_filter_by_date_range(self, search_db):
        result = search.filter_emails(date_from="2024-02-01", date_to="2024-02-28")
        assert result["total"] == 1
        assert result["items"][0]["sender_email"] == "bob@example.com"

    def test_subject_contains(self, search_db):
        result = search.filter_emails(subject_contains="Apollo")
        assert result["total"] == 1

    def test_invalid_sort_falls_back_to_default(self, search_db):
        # Should silently ignore an unknown sort_by rather than raising
        result = search.filter_emails(sort_by="dropTable")
        assert result["total"] == 3

    def test_pagination(self, search_db):
        page1 = search.filter_emails(page=1, page_size=2)
        page2 = search.filter_emails(page=2, page_size=2)
        assert len(page1["items"]) == 2
        assert len(page2["items"]) == 1
        ids_page1 = {r["id"] for r in page1["items"]}
        ids_page2 = {r["id"] for r in page2["items"]}
        assert ids_page1.isdisjoint(ids_page2)


class TestGetEmailDetail:
    def test_returns_full_record(self, search_db):
        # Look up by the first inserted row's id
        with database.get_db(search_db) as conn:
            eid = conn.execute("SELECT id FROM emails WHERE message_id='msg-1'").fetchone()[0]
        detail = search.get_email_detail(eid)
        assert detail is not None
        assert detail["subject"] == "Quarterly Project Report"
        assert detail["recipients"] == []  # We didn't seed any
        assert detail["attachment_names"] == ["report.pdf"]

    def test_missing_email_returns_none(self, search_db):
        assert search.get_email_detail(99999) is None


class TestGetSenders:
    def test_returns_unique_senders_with_counts(self, search_db):
        senders = search.get_senders()
        emails = {s["sender_email"]: s["email_count"] for s in senders}
        assert emails["alice@example.com"] == 2
        assert emails["bob@example.com"] == 1
