"""Normalized verification that a quoted passage appears in a message body."""
import re

_SMART = str.maketrans({
    "“": '"', "”": '"', "‘": "'", "’": "'",
    "–": "-", "—": "-",
})
_REPLY_MARKER = re.compile(r"^\s*>+", re.MULTILINE)
_WHITESPACE = re.compile(r"\s+")


def normalize_text(s: str | None) -> str:
    if not s:
        return ""
    s = _REPLY_MARKER.sub("", s)
    s = s.translate(_SMART)
    return _WHITESPACE.sub(" ", s).strip().lower()


def verify_quote(quote: str | None, body: str | None) -> bool:
    needle = normalize_text(quote)
    return bool(needle) and needle in normalize_text(body)
