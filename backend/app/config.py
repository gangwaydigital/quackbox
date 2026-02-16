"""
Application configuration.

Centralized settings for database paths, Ollama connection,
and application defaults. Supports both local dev and Docker.
"""

import os
from pathlib import Path

# -- Paths --
# In Docker: /app is the workdir, /app/data is the mbox mount, /app/db is persisted
# Locally: paths resolve relative to the project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
DB_DIR = Path(os.environ.get("DB_DIR", BASE_DIR / "backend"))
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "quackbox.db"

# -- Ollama --
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
EMBEDDING_DIMENSIONS = 768  # nomic-embed-text output size

# -- Clustering --
DEFAULT_NUM_CLUSTERS = 15  # Starting point, auto-tune based on email volume
MIN_CLUSTER_SIZE = 5       # Minimum emails per topic cluster

# -- API --
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

# -- Parsing --
SUPPORTED_EXTENSIONS = {".mbox", ".mbox.gz"}
MAX_BODY_LENGTH = 100_000  # Truncate extremely long email bodies
