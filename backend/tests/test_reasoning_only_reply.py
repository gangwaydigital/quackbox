"""Thinking models can exhaust max_tokens on reasoning and return no `content`."""
from unittest.mock import MagicMock

from app.services import chat as chat_mod
from app.services import summarizer

_REASONING_ONLY = {
    "choices": [{"finish_reason": "length",
                 "message": {"role": "assistant", "reasoning_content": "thinking..."}}],
}


def _fake_post(*args, **kwargs):
    r = MagicMock(status_code=200, text="{}")
    r.json.return_value = _REASONING_ONLY
    return r


def test_chat_reasoning_only_reply_is_an_error_not_a_crash(monkeypatch):
    monkeypatch.setattr(chat_mod, "CHAT_API_TYPE", "openai")
    monkeypatch.setattr(chat_mod, "search_relevant_emails", lambda q, limit=15: [])
    monkeypatch.setattr(chat_mod, "_get_archive_context", lambda: "")
    monkeypatch.setattr(chat_mod.requests, "post", _fake_post)
    result = chat_mod.chat("anything")
    assert result["error"] is True
    assert "token" in result["answer"].lower()


def test_summarizer_reasoning_only_reply_returns_empty_content(monkeypatch):
    monkeypatch.setattr(summarizer, "CHAT_API_TYPE", "openai")
    monkeypatch.setattr(summarizer.requests, "post", _fake_post)
    status, content, _ = summarizer._complete("m", [], 0.2, 100, 5)
    assert (status, content) == (200, "")
