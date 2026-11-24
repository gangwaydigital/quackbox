"""AI_PROVIDER preset selection in app.config."""
import importlib

import pytest

_VARS = [
    "AI_PROVIDER", "OMLX_BASE_URL", "OMLX_API_KEY", "OLLAMA_BASE_URL", "OLLAMA_EMBED_MODEL",
    "CHAT_API_URL", "CHAT_API_KEY", "CHAT_MODEL", "CHAT_API_TYPE", "CHAT_ENABLE_THINKING", "CASE_PROPOSE_MODEL",
    "EMBED_API_URL", "EMBED_API_KEY", "EMBED_MODEL", "EMBED_API_TYPE", "EMBEDDING_DIMENSIONS",
]


def _load(monkeypatch, tmp_path, **env):
    for v in _VARS:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("DB_DIR", str(tmp_path))
    for k, val in env.items():
        monkeypatch.setenv(k, val)
    import app.config
    return importlib.reload(app.config)


def test_default_is_ollama(monkeypatch, tmp_path):
    c = _load(monkeypatch, tmp_path)
    assert (c.CHAT_API_TYPE, c.EMBED_API_TYPE) == ("ollama", "ollama")
    assert c.CHAT_API_URL == "http://localhost:11434"
    assert (c.CHAT_MODEL, c.EMBED_MODEL) == ("llama3.1:8b", "nomic-embed-text")


def test_omlx_preset(monkeypatch, tmp_path):
    c = _load(monkeypatch, tmp_path, AI_PROVIDER="omlx", OMLX_API_KEY="k")
    assert (c.CHAT_API_TYPE, c.EMBED_API_TYPE) == ("openai", "openai")
    assert c.CHAT_API_URL == c.EMBED_API_URL == "http://localhost:6868"
    assert c.CHAT_API_KEY == c.EMBED_API_KEY == "k"
    assert (c.CHAT_MODEL, c.EMBED_MODEL) == ("glm-4.7-flash", "bge-base-en-v1.5")


def test_explicit_override_and_blank_passthrough(monkeypatch, tmp_path):
    # Compose passes unset overrides through as "", which must not clobber the preset.
    c = _load(monkeypatch, tmp_path, AI_PROVIDER="omlx", CHAT_MODEL="qwen3-coder", EMBED_MODEL="")
    assert c.CHAT_MODEL == "qwen3-coder"
    assert c.EMBED_MODEL == "bge-base-en-v1.5"


def test_case_propose_model(monkeypatch, tmp_path):
    c = _load(monkeypatch, tmp_path, AI_PROVIDER="omlx")
    assert c.CASE_PROPOSE_MODEL == "qwen3.5-122b"
    c = _load(monkeypatch, tmp_path)
    assert c.CASE_PROPOSE_MODEL == c.CHAT_MODEL
    c = _load(monkeypatch, tmp_path, AI_PROVIDER="omlx", CASE_PROPOSE_MODEL="x")
    assert c.CASE_PROPOSE_MODEL == "x"
    c = _load(monkeypatch, tmp_path, AI_PROVIDER="omlx", CASE_PROPOSE_MODEL="")
    assert c.CASE_PROPOSE_MODEL == "qwen3.5-122b"


def test_bad_provider_rejected(monkeypatch, tmp_path):
    with pytest.raises(ValueError):
        _load(monkeypatch, tmp_path, AI_PROVIDER="lmstudio")
    _load(monkeypatch, tmp_path)  # leave app.config in a valid state for other tests


def test_omlx_disables_thinking_by_default(monkeypatch, tmp_path):
    c = _load(monkeypatch, tmp_path, AI_PROVIDER="omlx")
    assert c.CHAT_EXTRA_BODY == {"chat_template_kwargs": {"enable_thinking": False}}
    c = _load(monkeypatch, tmp_path, AI_PROVIDER="omlx", CHAT_ENABLE_THINKING="true")
    assert c.CHAT_EXTRA_BODY == {"chat_template_kwargs": {"enable_thinking": True}}


def test_non_omlx_sends_no_extra_fields(monkeypatch, tmp_path):
    c = _load(monkeypatch, tmp_path, CHAT_API_TYPE="openai")
    assert c.CHAT_EXTRA_BODY == {}
