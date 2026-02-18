"""
QuackBox — Logging configuration.

Structured logging with emoji prefixes for quick visual scanning in Docker logs.
"""
import logging
import sys

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)-20s %(message)s"
LOG_DATE = "%H:%M:%S"


def setup_logging(level: str = "INFO"):
    """Configure application logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=LOG_FORMAT,
        datefmt=LOG_DATE,
        stream=sys.stdout,
        force=True,
    )
    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    return logging.getLogger("quackbox")


# Module-level logger factory
def get_logger(name: str) -> logging.Logger:
    """Get a named logger under the quackbox namespace."""
    return logging.getLogger(f"quackbox.{name}")
