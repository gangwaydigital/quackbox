"""Model-assisted case research: suggest search terms, order emails, surface people.

The model only suggests and orders. Evidence is decided by the user; quotes
are verified against the real body and never trusted on their own.
"""
import json

import requests

from app.config import CASE_PROPOSE_MODEL, CHAT_MODEL
from app.services.case_quotes import verify_quote
from app.services.llm import complete
from app.services.summarizer import _extract_json

BODY_LIMIT = 6000
LABELS = ("relevant", "maybe", "not")

PROPOSE_SYSTEM = "You are a careful research assistant. You always respond with valid JSON only."
TRIAGE_SYSTEM = "You are a careful research assistant. You always respond with valid JSON only."

PROPOSE_PROMPT = """A researcher is searching an email archive for evidence about this issue:

{issue}

Known people (name and email addresses):
{people}

Search terms already in use:
{existing}

Suggest additional search terms likely to appear in relevant emails: names, nicknames, likely misspellings, email addresses, and topics or keywords. Do not repeat terms already in use. Give each a short reason.

Return ONLY a JSON object, no markdown, in this shape:
{{"terms": [{{"text": "term", "reason": "why it may help"}}]}}"""

TRIAGE_PROMPT = """A researcher is searching an email archive for evidence about this issue:

{issue}

Decide how relevant the email below is to the issue.
- "relevant": directly bears on the issue
- "maybe": might bear on it, unclear
- "not": unrelated

If you give "relevant" or "maybe", include ONE short quote copied verbatim, character for character, from the email body only (never from the subject or headers, never paraphrased). If no passage supports your label, use null for the quote.

Return ONLY a JSON object, no markdown, in this shape:
{{"triage": "relevant|maybe|not", "reason": "one sentence", "quote": "verbatim passage or null"}}

Email:
From: {sender}
Date: {date}
Subject: {subject}
Body:
{body}"""


def _terms(issue_msg, model, existing):
    """Run a term-proposal prompt; return {"terms": [...], "error": str|None}."""
    try:
        status, content, _ = complete(
            model,
            [{"role": "system", "content": PROPOSE_SYSTEM}, {"role": "user", "content": issue_msg}],
            temperature=0.3, max_tokens=4096, timeout=180,
        )
    except requests.RequestException as e:
        return {"terms": [], "error": f"Model unreachable: {e}"}
    if status != 200:
        return {"terms": [], "error": f"Model error (HTTP {status})"}
    parsed = _extract_json(content)
    raw = parsed.get("terms") if isinstance(parsed, dict) else None
    if not isinstance(raw, list):
        return {"terms": [], "error": "Model returned no usable terms"}
    seen = {t.strip().lower() for t in existing}
    out = []
    for t in raw:
        text = str(t.get("text", "")).strip() if isinstance(t, dict) else ""
        if text and text.lower() not in seen:
            seen.add(text.lower())
            out.append({"text": text, "reason": str(t.get("reason", "")).strip()})
    return {"terms": out, "error": None}


def propose_terms(issue: str, people: list[dict], existing: list[str]) -> dict:
    people_txt = "\n".join(f"- {p.get('name', '')}: {', '.join(p.get('emails', []))}" for p in people) or "(none)"
    existing_txt = "\n".join(f"- {t}" for t in existing) or "(none)"
    return _terms(PROPOSE_PROMPT.format(issue=issue, people=people_txt, existing=existing_txt),
                  CASE_PROPOSE_MODEL, existing)


def triage_email(issue: str, email: dict) -> dict:
    res = {"triage": "untriaged", "reason": "", "quote": None, "quote_ok": False,
           "partial": False, "error": None}
    full = email.get("body_text") or ""
    if not full.strip():
        return {**res, "triage": "not", "reason": "Empty body"}
    body = full[:BODY_LIMIT]
    res["partial"] = len(full) > BODY_LIMIT
    prompt = TRIAGE_PROMPT.format(
        issue=issue,
        sender=f"{email.get('sender_name') or ''} <{email.get('sender_email') or ''}>",
        date=email.get("date_sent") or "", subject=email.get("subject") or "", body=body)
    try:
        status, content, _ = complete(
            CHAT_MODEL,
            [{"role": "system", "content": TRIAGE_SYSTEM}, {"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=4096, timeout=180,
        )
    except requests.RequestException as e:
        return {**res, "error": f"Model unreachable: {e}"}
    if status != 200:
        return {**res, "error": f"Model error (HTTP {status})"}
    parsed = _extract_json(content)
    label = parsed.get("triage") if isinstance(parsed, dict) else None
    if label not in LABELS:
        return {**res, "error": "Model returned no valid triage label"}
    quote = parsed.get("quote")
    quote = quote.strip() if isinstance(quote, str) and quote.strip() else None
    return {**res, "triage": label, "reason": str(parsed.get("reason") or "").strip(),
            "quote": quote, "quote_ok": verify_quote(quote, full)}


def people_in_evidence(emails: list[dict], known_people: list[dict] | None = None) -> list[dict]:
    known = {e.lower() for p in known_people or [] for e in p.get("emails", [])}
    counts: dict[str, dict] = {}

    def add(addr, name):
        addr = (addr or "").strip().lower()
        if not addr or addr in known:
            return
        c = counts.setdefault(addr, {"email": addr, "name": "", "count": 0})
        c["count"] += 1
        c["name"] = c["name"] or (name or "").strip()

    for em in emails:
        # one count per email per address, even if listed in several fields
        seen = {}
        seen[(em.get("sender_email") or "").strip().lower()] = em.get("sender_name")
        try:
            rcpts = json.loads(em.get("recipients") or "[]")
        except (TypeError, ValueError):
            rcpts = []
        for r in rcpts if isinstance(rcpts, list) else []:
            if isinstance(r, dict):
                seen.setdefault((r.get("email") or "").strip().lower(), r.get("name"))
            elif isinstance(r, str):
                seen.setdefault(r.strip().lower(), None)
        for addr, name in seen.items():
            add(addr, name)
    return sorted(counts.values(), key=lambda c: -c["count"])


def find_more(issue: str, evidence: list[dict], existing_terms: list[str], known_people: list[dict]) -> dict:
    lines = [f"- {e.get('subject') or '(no subject)'}: {(e.get('body_text') or '')[:200]!r}" for e in evidence[:20]]
    msg = PROPOSE_PROMPT.format(
        issue=issue + "\n\nEmails already confirmed as evidence (subject and excerpt):\n" + "\n".join(lines),
        people="\n".join(f"- {p.get('name', '')}: {', '.join(p.get('emails', []))}" for p in known_people) or "(none)",
        existing="\n".join(f"- {t}" for t in existing_terms) or "(none)")
    r = _terms(msg, CASE_PROPOSE_MODEL, existing_terms)
    return {**r, "people": people_in_evidence(evidence, known_people)[:10]}
