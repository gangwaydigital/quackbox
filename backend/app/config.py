"""
QuackBox — Application configuration.

Supports separate OpenAI-compatible endpoints for chat and embedding.
Set via environment variables or docker-compose.yml.
"""

import os
from pathlib import Path

# -- Paths --
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
DB_DIR = Path(os.environ.get("DB_DIR", BASE_DIR / "backend"))
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "quackbox.db"

def _env(name: str, default: str) -> str:
    """Env var, treating empty as unset (compose passes unset vars through as "")."""
    return os.environ.get(name) or default


# -- AI provider --
# AI_PROVIDER picks defaults for chat + embeddings: "ollama" (default) or "omlx".
# Any explicit CHAT_* / EMBED_* variable still overrides its preset value.
AI_PROVIDER = _env("AI_PROVIDER", "ollama").lower()
if AI_PROVIDER not in ("ollama", "omlx"):
    raise ValueError(f"AI_PROVIDER must be 'ollama' or 'omlx', got {AI_PROVIDER!r}")

if AI_PROVIDER == "omlx":
    _url = _env("OMLX_BASE_URL", "http://localhost:6868")
    _key = _env("OMLX_API_KEY", "")
    _type, _chat_model, _embed_model = "openai", "glm-4.7-flash", "bge-base-en-v1.5"
else:
    _url = _env("OLLAMA_BASE_URL", "http://localhost:11434")
    _key = ""
    _type, _chat_model, _embed_model = "ollama", "llama3.1:8b", _env("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# -- Chat LLM --
CHAT_API_URL = _env("CHAT_API_URL", _url)
CHAT_API_KEY = _env("CHAT_API_KEY", _key)  # blank = no auth (Ollama)
CHAT_MODEL = _env("CHAT_MODEL", _chat_model)
CHAT_API_TYPE = _env("CHAT_API_TYPE", _type)  # "ollama" or "openai"

# -- Embedding LLM --
EMBED_API_URL = _env("EMBED_API_URL", _url)
EMBED_API_KEY = _env("EMBED_API_KEY", _key)
EMBED_MODEL = _env("EMBED_MODEL", _embed_model)
EMBED_API_TYPE = _env("EMBED_API_TYPE", _type)  # "ollama" or "openai"
EMBEDDING_DIMENSIONS = int(_env("EMBEDDING_DIMENSIONS", "768"))

# -- Clustering --
DEFAULT_NUM_CLUSTERS = 15
MIN_CLUSTER_SIZE = 5

# -- API --
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

# -- Parsing --
MAX_BODY_LENGTH = 100_000

# -- Watcher --
# Background ingest scheduler. 0 disables (default). Minimum effective
# interval is 1 minute when enabled.
WATCH_INTERVAL_MINUTES = int(os.environ.get("WATCH_INTERVAL_MINUTES", "0"))
WATCH_ON_STARTUP = os.environ.get("WATCH_ON_STARTUP", "false").lower() in ("1", "true", "yes")
