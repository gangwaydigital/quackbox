"""
Thread summarization service.

Uses Ollama to generate structured summaries of email threads:
- Summary narrative
- Key decisions
- Action items
- Open questions
- Sentiment assessment
"""
import json
import requests
from typing import Optional
from app.config import OLLAMA_BASE_URL
from app.database import get_db

SUMMARIZE_MODEL = "llama3.1:8b"


def summarize_thread(thread_id: int, model: str = None) -> dict:
    """
    Generate a structured AI summary of an email thread.

    Returns dict with: summary, decisions, action_items, open_questions, sentiment
    """
    model = model or SUMMARIZE_MODEL

    with get_db() as conn:
        thread = conn.execute("SELECT * FROM threads WHERE id = ?", (thread_id,)).fetchone()
        if not thread:
            return {"error": f"Thread {thread_id} not found"}

        emails = conn.execute("""
            SELECT sender_name, sender_email, subject, date_sent, body_text
            FROM emails WHERE thread_group_id = ?
            ORDER BY date_timestamp ASC
        """, (thread_id,)).fetchall()

        if not emails:
            return {"error": "No emails in thread"}

    # Build thread text for the LLM
    thread_text = _format_thread_for_llm(emails)

    # Truncate if too long (keep ~6000 chars to leave room for prompt + response)
    if len(thread_text) > 6000:
        thread_text = thread_text[:6000] + "\n\n[... thread truncated for length ...]"

    prompt = f"""Analyze this email thread and provide a structured summary. Respond in valid JSON format only, with no other text.

EMAIL THREAD ({len(emails)} messages):
{thread_text}

Respond with this exact JSON structure:
{{
  "summary": "2-3 sentence overview of what this thread is about",
  "key_decisions": ["list of decisions that were made or agreed upon"],
  "action_items": [
    {{"task": "description", "owner": "person name or email", "status": "open/done/unclear"}}
  ],
  "open_questions": ["unresolved questions or pending items"],
  "sentiment": "one of: collaborative, neutral, tense, urgent, casual, professional",
  "key_participants": ["most active or important participants"],
  "topic_tags": ["3-5 topic keywords"]
}}

Important: Return ONLY valid JSON. No markdown, no explanations, just the JSON object."""

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a precise email analyst. You always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 2048},
            },
            timeout=120,
        )

        if resp.status_code != 200:
            return {"error": f"Ollama error (HTTP {resp.status_code})", "raw": resp.text[:200]}

        content = resp.json().get("message", {}).get("content", "")

        # Try to parse JSON from response
        parsed = _extract_json(content)
        if parsed:
            parsed["thread_id"] = thread_id
            parsed["model"] = model
            parsed["message_count"] = len(emails)
            return parsed
        else:
            return {
                "thread_id": thread_id,
                "summary": content.strip(),
                "key_decisions": [],
                "action_items": [],
                "open_questions": [],
                "sentiment": "unknown",
                "key_participants": [],
                "topic_tags": [],
                "model": model,
                "message_count": len(emails),
                "parse_note": "Could not parse structured JSON, raw summary provided"
            }

    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to Ollama. Make sure it's running: ollama serve"}
    except requests.exceptions.Timeout:
        return {"error": "Ollama timed out. The model may be loading — try again."}


def summarize_email(email_id: int, model: str = None) -> dict:
    """Generate a quick summary of a single email."""
    model = model or SUMMARIZE_MODEL

    with get_db() as conn:
        row = conn.execute(
            "SELECT sender_name, sender_email, subject, date_sent, body_text FROM emails WHERE id = ?",
            (email_id,)
        ).fetchone()
        if not row:
            return {"error": f"Email {email_id} not found"}

    body = (row["body_text"] or "")[:4000]
    sender = row["sender_name"] or row["sender_email"] or "Unknown"

    prompt = f"""Summarize this email concisely. Identify any action items or requests.

From: {sender}
Subject: {row['subject'] or '(no subject)'}
Date: {row['date_sent'] or 'Unknown'}

{body}

Respond with JSON:
{{
  "summary": "1-2 sentence summary",
  "action_items": ["any tasks or requests mentioned"],
  "sentiment": "one of: positive, neutral, negative, urgent",
  "key_points": ["main points of the email"]
}}"""

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 1024},
            },
            timeout=60,
        )

        if resp.status_code != 200:
            return {"error": f"Ollama error: {resp.status_code}"}

        content = resp.json().get("message", {}).get("content", "")
        parsed = _extract_json(content)
        if parsed:
            parsed["email_id"] = email_id
            parsed["model"] = model
            return parsed
        return {"email_id": email_id, "summary": content.strip(), "model": model}

    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to Ollama"}
    except requests.exceptions.Timeout:
        return {"error": "Ollama timed out"}


def _format_thread_for_llm(emails) -> str:
    """Format thread emails into readable text for the LLM."""
    parts = []
    for i, e in enumerate(emails, 1):
        sender = e["sender_name"] or e["sender_email"] or "Unknown"
        date = e["date_sent"] or "Unknown date"
        body = (e["body_text"] or "").strip()
        # Truncate individual emails in long threads
        if len(body) > 1500:
            body = body[:1500] + "..."
        parts.append(f"[Message {i}] From: {sender} | Date: {date}\nSubject: {e['subject'] or '(no subject)'}\n{body}")
    return "\n\n---\n\n".join(parts)


def _extract_json(text: str) -> Optional[dict]:
    """Try to extract JSON from LLM response, handling markdown fences."""
    text = text.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last fence lines
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
    return None
