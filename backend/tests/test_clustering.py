"""
Tests for the topic clustering service.

Covers the deterministic helpers (text shaping, keyword extraction, label
formatting) and the check_ollama_available reachability probe with mocked
HTTP. The full embedding/cluster path requires a live embedding API and
is exercised manually rather than in unit tests.

Regression: clustering.py used `log.info(...)` in 6 places without
importing get_logger, so the very first clustering run crashed with
`NameError: name 'log' is not defined`. The fix imports get_logger;
this file pins down that the module loads cleanly.
"""
from unittest.mock import patch, MagicMock

import pytest

from app.services import clustering


class TestModuleHealth:
    def test_log_is_importable_and_callable(self):
        """Regression: clustering.py used to use `log` without importing it.
        First clustering attempt crashed with NameError."""
        assert hasattr(clustering, "log")
        # Smoke: should not raise
        clustering.log.info("clustering test ping")


class TestMakeEmbeddingText:
    def test_combines_subject_sender_body(self):
        out = clustering._make_embedding_text("Q1 plan", "Alice", "We need to ship by April.")
        assert "Subject: Q1 plan" in out
        assert "From: Alice" in out
        assert "We need to ship by April." in out

    def test_truncates_long_body(self):
        long_body = "x" * 5000
        out = clustering._make_embedding_text("S", "A", long_body, max_body=500)
        # Body must not exceed max_body chars
        body_segment = out.split("\n")[-1]
        assert len(body_segment) == 500

    def test_skips_empty_fields(self):
        out = clustering._make_embedding_text("", "", "hello")
        assert "Subject:" not in out
        assert "From:" not in out
        assert "hello" in out

    def test_all_empty_returns_empty_string(self):
        assert clustering._make_embedding_text("", "", "") == ""


class TestExtractKeywords:
    def test_returns_most_common_words(self):
        subjects = ["project alpha launch", "alpha milestone update"]
        bodies = ["The alpha project is on track.", "Project alpha shipped today."]
        kws = clustering._extract_keywords(subjects, bodies, top_n=3)
        # alpha + project should both rank in the top
        assert "alpha" in kws
        assert "project" in kws

    def test_drops_stop_words(self):
        subjects = ["the and but"]
        bodies = ["the and but for to of in"]
        kws = clustering._extract_keywords(subjects, bodies)
        # All inputs were stopwords — result should be empty
        assert kws == []

    def test_drops_short_tokens(self):
        subjects = ["a b c the project"]
        kws = clustering._extract_keywords(subjects, [])
        # Only "project" survives (a/b/c are too short, "the" is a stopword)
        assert kws == ["project"]

    def test_strips_non_alphanumeric_punctuation(self):
        subjects = ["urgent!!!", "urgent?"]
        bodies = []
        kws = clustering._extract_keywords(subjects, bodies)
        assert "urgent" in kws

    def test_handles_empty_input(self):
        assert clustering._extract_keywords([], []) == []
        assert clustering._extract_keywords([""], [None]) == []

    def test_respects_top_n(self):
        subjects = ["alpha beta gamma delta epsilon zeta eta"]
        kws = clustering._extract_keywords(subjects, [], top_n=3)
        assert len(kws) == 3


class TestMakeTopicLabel:
    def test_uses_first_three_keywords_title_cased(self):
        assert clustering._make_topic_label(["alpha", "beta", "gamma"]) == "Alpha / Beta / Gamma"

    def test_falls_back_to_uncategorized_for_empty(self):
        assert clustering._make_topic_label([]) == "Uncategorized"

    def test_handles_single_keyword(self):
        assert clustering._make_topic_label(["project"]) == "Project"


class TestCancellation:
    def test_request_cancel_sets_flag(self):
        clustering.reset_cancel()
        assert clustering.is_cancel_requested() is False
        clustering.request_cancel()
        assert clustering.is_cancel_requested() is True
        clustering.reset_cancel()
        assert clustering.is_cancel_requested() is False

    def test_embedding_loop_stops_when_cancel_requested(self, tmp_path, monkeypatch):
        """When the cancel flag is set, the loop bails after the current batch
        and reports cancelled=True with embeddings already generated preserved."""
        from app import database
        db_path = tmp_path / "cancel.db"
        database.init_db(db_path)
        real_get_db = database.get_db

        def get_db_override(p=db_path):
            return real_get_db(p)
        monkeypatch.setattr(clustering, "get_db", get_db_override)

        # Seed 10 emails
        with database.get_db(db_path) as conn:
            for i in range(10):
                conn.execute(
                    "INSERT INTO emails (subject, sender_name, body_text) VALUES (?, ?, ?)",
                    (f"Subject {i}", "alice@x.com", f"body {i}"),
                )

        # Set the cancel flag BEFORE running. Loop should bail immediately.
        clustering.reset_cancel()
        clustering.request_cancel()
        with patch.object(clustering, "generate_embedding", return_value=[0.1] * 768):
            result = clustering.generate_all_embeddings(batch_size=2)
        clustering.reset_cancel()  # cleanup

        assert result["cancelled"] is True
        assert result["generated"] == 0  # bailed before any work
        assert result["total"] == 10

    def test_embedding_loop_completes_when_no_cancel(self, tmp_path, monkeypatch):
        """Sanity: without a cancel signal, the loop runs to completion and
        reports cancelled=False."""
        from app import database
        db_path = tmp_path / "nocancel.db"
        database.init_db(db_path)
        real_get_db = database.get_db

        def get_db_override(p=db_path):
            return real_get_db(p)
        monkeypatch.setattr(clustering, "get_db", get_db_override)

        with database.get_db(db_path) as conn:
            for i in range(3):
                conn.execute(
                    "INSERT INTO emails (subject, sender_name, body_text) VALUES (?, ?, ?)",
                    (f"S {i}", "a@x.com", f"b {i}"),
                )

        clustering.reset_cancel()
        with patch.object(clustering, "generate_embedding", return_value=[0.1] * 768):
            result = clustering.generate_all_embeddings(batch_size=1)
        assert result["cancelled"] is False
        assert result["generated"] == 3


class TestGenerateAllEmbeddingsProgressCallback:
    """Verify the progress_callback hook fires correctly without breaking the loop."""

    def _seed(self, db_path, n_emails: int):
        from app import database
        with database.get_db(db_path) as conn:
            for i in range(n_emails):
                conn.execute(
                    "INSERT INTO emails (subject, sender_name, body_text) VALUES (?, ?, ?)",
                    (f"Subject {i}", f"sender{i}@x.com", f"body content {i}"),
                )

    def _patched_clustering(self, tmp_path, monkeypatch):
        from app import database
        db_path = tmp_path / "embed.db"
        database.init_db(db_path)
        real_get_db = database.get_db

        def get_db_override(p=db_path):
            return real_get_db(p)
        monkeypatch.setattr(clustering, "get_db", get_db_override)
        return db_path

    def test_callback_fires_on_zero_then_completion_for_empty_db(self, tmp_path, monkeypatch):
        """With no emails, callback should still fire once at start (0/0) and once at end."""
        self._patched_clustering(tmp_path, monkeypatch)
        calls = []
        with patch.object(clustering, "generate_embedding", return_value=None):
            clustering.generate_all_embeddings(progress_callback=lambda d, t: calls.append((d, t)))
        # Initial 0/0 + final 0/0 (deduped is fine if both 0/0)
        assert (0, 0) in calls

    def test_callback_fires_at_batch_boundaries(self, tmp_path, monkeypatch):
        db_path = self._patched_clustering(tmp_path, monkeypatch)
        self._seed(db_path, 5)
        calls = []
        with patch.object(clustering, "generate_embedding", return_value=[0.1] * 768):
            clustering.generate_all_embeddings(
                batch_size=2,
                progress_callback=lambda d, t: calls.append((d, t)),
            )
        # Expect callbacks at: start(0,5), batch(2,5), batch(4,5), final(5,5)
        assert (0, 5) in calls
        assert (2, 5) in calls
        assert (4, 5) in calls
        assert (5, 5) in calls

    def test_callback_exception_does_not_break_embedding_loop(self, tmp_path, monkeypatch):
        """If the caller's callback raises, embedding generation should keep going."""
        db_path = self._patched_clustering(tmp_path, monkeypatch)
        self._seed(db_path, 3)

        def angry_callback(done, total):
            raise RuntimeError("boom")

        with patch.object(clustering, "generate_embedding", return_value=[0.1] * 768):
            result = clustering.generate_all_embeddings(
                batch_size=1, progress_callback=angry_callback,
            )
        # All 3 emails should still be embedded despite the angry callback
        assert result["generated"] == 3
        assert result["errors"] == 0


class TestListEmbedModels:
    def test_returns_current_and_suggestions_when_unreachable(self):
        with patch("app.services.clustering.requests.get",
                   side_effect=Exception("connection refused")):
            info = clustering.list_embed_models()
        assert info["reachable"] is False
        assert info["error"]
        assert info["current"]  # always set from EMBED_MODEL constant
        # Suggested alternatives are static — present even when offline
        assert info["suggested"]
        assert any(s["name"] == "all-minilm" for s in info["suggested"])

    def test_ollama_filters_to_embed_family_models(self):
        """The Ollama tag list mixes chat + embed models; we filter to
        embed-family names so the picker stays useful."""
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "models": [
                {"name": "nomic-embed-text:latest", "size": 274_000_000},
                {"name": "all-minilm:latest", "size": 46_000_000},
                {"name": "llama3.1:8b", "size": 4_700_000_000},  # chat — should be filtered
                {"name": "qwen2.5", "size": 5_000_000_000},      # chat — should be filtered
            ],
        }
        with patch.object(clustering, "EMBED_API_TYPE", "ollama"), \
             patch("app.services.clustering.requests.get", return_value=mock_resp):
            info = clustering.list_embed_models()
        assert info["reachable"] is True
        installed_names = {m["name"] for m in info["installed"]}
        assert installed_names == {"nomic-embed-text:latest", "all-minilm:latest"}

    def test_ollama_size_formatted_as_mb(self):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "models": [{"name": "nomic-embed-text", "size": 274_000_000}],
        }
        with patch.object(clustering, "EMBED_API_TYPE", "ollama"), \
             patch("app.services.clustering.requests.get", return_value=mock_resp):
            info = clustering.list_embed_models()
        assert info["installed"][0]["size"] == "261 MB"  # round(274e6 / 1_048_576)

    def test_openai_filters_by_id(self):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "data": [
                {"id": "text-embedding-3-small"},
                {"id": "gpt-4o-mini"},      # not an embedding
                {"id": "embed-english-v3"},  # cohere-style
            ],
        }
        with patch.object(clustering, "EMBED_API_TYPE", "openai"), \
             patch("app.services.clustering.requests.get", return_value=mock_resp):
            info = clustering.list_embed_models()
        names = {m["name"] for m in info["installed"]}
        assert "text-embedding-3-small" in names
        assert "embed-english-v3" in names
        assert "gpt-4o-mini" not in names

    def test_http_error_surfaces_in_error_field(self):
        mock_resp = MagicMock(status_code=500)
        with patch.object(clustering, "EMBED_API_TYPE", "ollama"), \
             patch("app.services.clustering.requests.get", return_value=mock_resp):
            info = clustering.list_embed_models()
        assert info["reachable"] is False
        assert "500" in info["error"]


class TestCheckOllamaAvailable:
    def test_returns_false_on_connection_error(self):
        with patch("app.services.clustering.requests.get",
                   side_effect=Exception("connection refused")):
            assert clustering.check_ollama_available() is False

    def test_ollama_returns_true_when_model_present(self):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"models": [{"name": "nomic-embed-text"}]}
        with patch.object(clustering, "EMBED_API_TYPE", "ollama"), \
             patch.object(clustering, "EMBED_MODEL", "nomic-embed-text"), \
             patch("app.services.clustering.requests.get", return_value=mock_resp):
            assert clustering.check_ollama_available() is True

    def test_ollama_accepts_latest_tag_variant(self):
        """Ollama lists models as 'name:latest' — both should match."""
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"models": [{"name": "nomic-embed-text:latest"}]}
        with patch.object(clustering, "EMBED_API_TYPE", "ollama"), \
             patch.object(clustering, "EMBED_MODEL", "nomic-embed-text"), \
             patch("app.services.clustering.requests.get", return_value=mock_resp):
            assert clustering.check_ollama_available() is True

    def test_ollama_returns_false_when_model_missing(self):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"models": [{"name": "llama3.1:8b"}]}
        with patch.object(clustering, "EMBED_API_TYPE", "ollama"), \
             patch.object(clustering, "EMBED_MODEL", "nomic-embed-text"), \
             patch("app.services.clustering.requests.get", return_value=mock_resp):
            assert clustering.check_ollama_available() is False

    def test_openai_returns_true_on_200(self):
        mock_resp = MagicMock(status_code=200)
        with patch.object(clustering, "EMBED_API_TYPE", "openai"), \
             patch("app.services.clustering.requests.get", return_value=mock_resp) as mg:
            assert clustering.check_ollama_available() is True
            # Should have hit /v1/models, not /api/tags
            url = mg.call_args[0][0]
            assert "/v1/models" in url

    def test_openai_passes_auth_header(self):
        mock_resp = MagicMock(status_code=200)
        with patch.object(clustering, "EMBED_API_TYPE", "openai"), \
             patch.object(clustering, "EMBED_API_KEY", "sk-secret"), \
             patch("app.services.clustering.requests.get", return_value=mock_resp) as mg:
            clustering.check_ollama_available()
            headers = mg.call_args.kwargs.get("headers", {})
            assert headers.get("Authorization") == "Bearer sk-secret"
