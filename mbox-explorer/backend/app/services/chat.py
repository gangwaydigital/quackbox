"""
RAG Chat service.

Retrieves relevant emails from the database and uses Ollama
to generate conversational answers grounded in email data.
"""

import json
import requests
from typing import Optional

from app.config import OLLAMA_BASE_URL
from app.database import get_db


# Default chat model — user can change this
OLLAMA_CHAT_MODEL = "llama3.1:8b"


def get_available_models() -> list[str]:
    """List models available in Ollama."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        pass
    return []


def search_relevant_emails(query: str, limit: int = 15) -> list[dict]:
    """
    Search for emails relevant to the user's question.
    Uses FTS5 for keyword matching.
    """
    with get_db() as conn:
        # Sanitize query for FTS5
        words = query.strip().split()
        if not words:
            return []
        safe_query = " ".join(f'"{w}"' for w in words)

        try:
            rows = conn.execute("""
                SELECT e.id, e.subject, e.sender_name, e.sender_email,
                       e.date_sent, e.body_text, e.mbox_source, rank
                FROM emails_fts
                JOIN emails e ON e.id = emails_fts.rowid
                WHERE emails_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (safe_query, limit)).fetchall()
        except Exception:
            # If FTS fails, fall back to LIKE search
            like_pattern = f"%{query}%"
            rows = conn.execute("""
                SELECT id, subject, sender_name, sender_email,
                       date_sent, body_text, mbox_source
                FROM emails
                WHERE subject LIKE ? OR body_text LIKE ? OR sender_name LIKE ?
                ORDER BY date_timestamp DESC
                LIMIT ?
            """, (like_pattern, like_pattern, like_pattern, limit)).fetchall()

        results = []
        for row in rows:
            body = (row["body_text"] or "")[:800]  # Truncate for context window
            results.append({
                "id": row["id"],
                "subject": row["subject"] or "(no subject)",
                "from": row["sender_name"] or row["sender_email"] or "Unknown",
                "email": row["sender_email"] or "",
                "date": row["date_sent"] or "",
                "mailbox": row["mbox_source"] or "",
                "body_snippet": body,
            })
        return results


def build_context(emails: list[dict]) -> str:
    """Format retrieved emails into context for the LLM."""
    if not emails:
        return "No relevant emails were found for this query."

    parts = [f"Found {len(emails)} relevant email(s):\n"]
    for i, em in enumerate(emails, 1):
        parts.append(f"--- Email {i} ---")
        parts.append(f"From: {em['from']} <{em['email']}>")
        parts.append(f"Subject: {em['subject']}")
        parts.append(f"Date: {em['date']}")
        parts.append(f"Mailbox: {em['mailbox']}")
        if em['body_snippet']:
            parts.append(f"Body:\n{em['body_snippet']}")
        parts.append("")

    return "\n".join(parts)


def chat(
    question: str,
    conversation_history: list[dict] = None,
    model: str = None,
    num_context_emails: int = 15,
) -> dict:
    """
    Answer a question about the email archive.

    1. Searches for relevant emails
    2. Builds context from search results
    3. Sends to Ollama for a conversational response

    Returns:
        dict with answer, sources, and model info
    """
    model = model or OLLAMA_CHAT_MODEL
    conversation_history = conversation_history or []

    # --- 1. Extract search terms and find relevant emails ---
    # Use the question directly as search, plus try to extract key terms
    emails = search_relevant_emails(question, limit=num_context_emails)

    # Also try individual important words if we got few results
    if len(emails) < 3:
        words = [w for w in question.split() if len(w) > 3]
        for word in words[:3]:
            extra = search_relevant_emails(word, limit=5)
            seen_ids = {e["id"] for e in emails}
            for e in extra:
                if e["id"] not in seen_ids:
                    emails.append(e)
                    seen_ids.add(e["id"])

    # --- 2. Build the prompt ---
    context = build_context(emails)

    system_prompt = """You are an AI assistant helping the user explore and understand their email archive. You have access to search results from their email database.

Your job is to:
- Answer questions about their emails based on the provided context
- Summarize patterns, identify key contacts, and surface insights
- Be specific — cite sender names, dates, subjects when relevant
- If the search results don't contain enough info to fully answer, say so and suggest what they might search for
- Be conversational and concise

Important: Only reference information actually present in the provided email context. Don't make up email content."""

    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history
    for msg in conversation_history[-10:]:  # Keep last 10 turns
        messages.append(msg)

    # Add the current question with context
    user_message = f"""Based on the following emails from my archive, please answer my question.

{context}

My question: {question}"""

    messages.append({"role": "user", "content": user_message})

    # --- 3. Call Ollama ---
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 1024,
                },
            },
            timeout=120,
        )

        if resp.status_code != 200:
            return {
                "answer": f"Error from Ollama (HTTP {resp.status_code}): {resp.text[:200]}",
                "sources": [],
                "model": model,
                "error": True,
            }

        data = resp.json()
        answer = data.get("message", {}).get("content", "No response generated.")

    except requests.exceptions.ConnectionError:
        return {
            "answer": "Cannot connect to Ollama. Make sure it's running: `ollama serve`",
            "sources": [],
            "model": model,
            "error": True,
        }
    except requests.exceptions.Timeout:
        return {
            "answer": "Ollama took too long to respond. The model may still be loading — try again in a moment.",
            "sources": [],
            "model": model,
            "error": True,
        }

    # --- 4. Return response with sources ---
    sources = [
        {"id": e["id"], "subject": e["subject"], "from": e["from"], "date": e["date"]}
        for e in emails[:10]
    ]

    return {
        "answer": answer,
        "sources": sources,
        "model": model,
        "emails_searched": len(emails),
        "error": False,
    }


def get_stats_summary() -> str:
    """Get a quick summary of the email archive for chat context."""
    with get_db() as conn:
        stats = {}
        stats["total"] = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
        stats["senders"] = conn.execute("SELECT COUNT(DISTINCT sender_email) FROM emails").fetchone()[0]

        top_senders = conn.execute("""
            SELECT sender_name, sender_email, COUNT(*) as cnt
            FROM emails WHERE sender_email != ''
            GROUP BY sender_email ORDER BY cnt DESC LIMIT 10
        """).fetchall()

        mailboxes = conn.execute("""
            SELECT mbox_source, COUNT(*) as cnt
            FROM emails GROUP BY mbox_source ORDER BY cnt DESC LIMIT 10
        """).fetchall()

        summary = f"Archive: {stats['total']} emails from {stats['senders']} senders.\n"
        summary += "Top senders: " + ", ".join(
            f"{r['sender_name'] or r['sender_email']} ({r['cnt']})" for r in top_senders
        ) + "\n"
        summary += "Top mailboxes: " + ", ".join(
            f"{r['mbox_source']} ({r['cnt']})" for r in mailboxes
        )
        return summary
