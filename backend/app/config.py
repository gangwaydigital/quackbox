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

# -- Chat LLM --
# OpenAI-compatible endpoint for chat/completion
CHAT_API_URL = os.environ.get("CHAT_API_URL", os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"))
CHAT_API_KEY = os.environ.get("CHAT_API_KEY", "")  # blank = no auth (Ollama)
CHAT_MODEL = os.environ.get("CHAT_MODEL", "llama3.1:8b")
CHAT_API_TYPE = os.environ.get("CHAT_API_TYPE", "ollama")  # "ollama" or "openai"

# -- Embedding LLM --
# OpenAI-compatible endpoint for embeddings
EMBED_API_URL = os.environ.get("EMBED_API_URL", os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"))
EMBED_API_KEY = os.environ.get("EMBED_API_KEY", "")
EMBED_MODEL = os.environ.get("EMBED_MODEL", os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text"))
EMBED_API_TYPE = os.environ.get("EMBED_API_TYPE", "ollama")  # "ollama" or "openai"
EMBEDDING_DIMENSIONS = int(os.environ.get("EMBEDDING_DIMENSIONS", "768"))

# -- Clustering --
DEFAULT_NUM_CLUSTERS = 15
MIN_CLUSTER_SIZE = 5

# -- API --
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

# -- Parsing --
SUPPORTED_EXTENSIONS = {".mbox", ".mbox.gz"}
MAX_BODY_LENGTH = 100_000
