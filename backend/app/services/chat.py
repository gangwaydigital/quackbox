"""
RAG Chat service — supports Ollama and OpenAI-compatible endpoints.
"""
import json
import requests
from app.config import CHAT_API_URL, CHAT_API_KEY, CHAT_MODEL, CHAT_API_TYPE
from app.database import get_db
from app.services.semantic_search import has_embeddings, hybrid_search


def get_available_models():
    """List models from the chat endpoint."""
    try:
        if CHAT_API_TYPE == "openai":
            headers = {"Authorization": f"Bearer {CHAT_API_KEY}"} if CHAT_API_KEY else {}
            resp = requests.get(f"{CHAT_API_URL}/v1/models", headers=headers, timeout=5)
            if resp.status_code == 200:
                return [m["id"] for m in resp.json().get("data", [])]
        else:
            resp = requests.get(f"{CHAT_API_URL}/api/tags", timeout=5)
            if resp.status_code == 200:
                return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        pass
    return []


def search_relevant_emails(query, limit=15):
    """Search using hybrid (keyword+semantic) if embeddings exist, else FTS5 only."""
    if has_embeddings():
        results = hybrid_search(query, limit=limit)
        with get_db() as conn:
            for r in results:
                row = conn.execute("SELECT body_text FROM emails WHERE id = ?", (r["id"],)).fetchone()
                if row:
                    r["body_snippet"] = (row["body_text"] or "")[:800]
                r["from"] = r.get("sender_name") or r.get("sender_email") or "Unknown"
                r["email"] = r.get("sender_email") or ""
                r["date"] = r.get("date_sent") or ""
                r["mailbox"] = r.get("mbox_source") or ""
        return results
    else:
        return _fts_search(query, limit)


def _fts_search(query, limit=15):
    """Fallback FTS5 keyword search when embeddings aren't available."""
    with get_db() as conn:
        words = query.strip().split()
        if not words: return []
        safe_query = " ".join(f'"{w}"' for w in words)
        try:
            rows = conn.execute("""
                SELECT e.id, e.subject, e.sender_name, e.sender_email,
                       e.date_sent, e.body_text, e.mbox_source, rank
                FROM emails_fts JOIN emails e ON e.id = emails_fts.rowid
                WHERE emails_fts MATCH ? ORDER BY rank LIMIT ?
            """, (safe_query, limit)).fetchall()
        except Exception:
            like = f"%{query}%"
            rows = conn.execute("""
                SELECT id, subject, sender_name, sender_email, date_sent, body_text, mbox_source
                FROM emails WHERE subject LIKE ? OR body_text LIKE ? OR sender_name LIKE ?
                ORDER BY date_timestamp DESC LIMIT ?
            """, (like, like, like, limit)).fetchall()
        return [{"id": r["id"], "subject": r["subject"] or "(no subject)",
                 "from": r["sender_name"] or r["sender_email"] or "Unknown",
                 "email": r["sender_email"] or "",
                 "date": r["date_sent"] or "",
                 "body_snippet": (r["body_text"] or "")[:800],
                 "mailbox": r["mbox_source"] or ""} for r in rows]


def _get_archive_context():
    """Build a one-line summary of the archive for the system prompt."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
        senders = conn.execute("SELECT COUNT(DISTINCT sender_email) FROM emails").fetchone()[0]
        dates = conn.execute("SELECT MIN(date_sent), MAX(date_sent) FROM emails WHERE date_sent IS NOT NULL").fetchone()
        return f"Archive: {total:,} emails from {senders:,} senders ({dates[0][:10] if dates[0] else '?'} to {dates[1][:10] if dates[1] else '?'})"


def build_context(emails):
    """Format retrieved emails into a text block for the LLM context window."""
    parts = [f"=== RELEVANT EMAILS ({len(emails)} found) ===\n"]
    for i, em in enumerate(emails[:15], 1):
        parts.append(f"--- Email {i} ---")
        parts.append(f"Subject: {em.get('subject','')}")
        parts.append(f"From: {em.get('from','')} <{em.get('email','')}>")
        parts.append(f"Date: {em.get('date','')}")
        parts.append(f"Mailbox: {em.get('mailbox','')}")
        if em.get('body_snippet'):
            parts.append(f"Body:\n{em['body_snippet']}")
        parts.append("")
    return "\n".join(parts)


def chat(question, conversation_history=None, model=None, num_context_emails=15):
    """RAG chat: retrieve relevant emails, build context, and query the LLM."""
    model = model or CHAT_MODEL
    conversation_history = conversation_history or []

    emails = search_relevant_emails(question, limit=num_context_emails)
    if len(emails) < 3:
        words = [w for w in question.split() if len(w) > 3]
        for word in words[:3]:
            extra = search_relevant_emails(word, limit=5)
            seen = {e["id"] for e in emails}
            for e in extra:
                if e["id"] not in seen: emails.append(e); seen.add(e["id"])

    context = build_context(emails)
    archive_context = _get_archive_context()

    system_prompt = f"""You are an AI assistant helping the user explore their personal email archive. Here is an overview of the archive:

{archive_context}

Your job is to:
- Answer questions about their emails based on the provided search results
- Summarize patterns, identify key contacts, and surface insights
- Be specific — cite sender names, dates, subjects when relevant
- If the search results don't fully answer the question, say so and suggest better search terms
- Be conversational and concise
- Only reference information from the provided email context — don't fabricate content"""

    messages = [{"role": "system", "content": system_prompt}]
    for msg in conversation_history[-10:]:
        messages.append(msg)
    messages.append({"role": "user", "content": f"{context}\n\nMy question: {question}"})

    try:
        if CHAT_API_TYPE == "openai":
            headers = {"Content-Type": "application/json"}
            if CHAT_API_KEY:
                headers["Authorization"] = f"Bearer {CHAT_API_KEY}"
            resp = requests.post(f"{CHAT_API_URL}/v1/chat/completions",
                headers=headers,
                # Thinking models (e.g. GLM-4.7) spend tokens on reasoning before answering.
                json={"model": model, "messages": messages,
                      "temperature": 0.3, "max_tokens": 4096},
                timeout=180)
            if resp.status_code != 200:
                return {"answer": f"Error (HTTP {resp.status_code}): {resp.text[:200]}", "sources": [], "model": model, "error": True}
            answer = resp.json()["choices"][0]["message"].get("content")
            if not answer:
                return {"answer": "The model used its whole token budget thinking and returned no answer. Try a shorter question or a non-thinking model.", "sources": [], "model": model, "error": True}
        else:
            resp = requests.post(f"{CHAT_API_URL}/api/chat",
                json={"model": model, "messages": messages, "stream": False,
                      "options": {"temperature": 0.3, "num_predict": 1024}},
                timeout=120)
            if resp.status_code != 200:
                return {"answer": f"Error (HTTP {resp.status_code}): {resp.text[:200]}", "sources": [], "model": model, "error": True}
            answer = resp.json().get("message", {}).get("content", "No response generated.")

    except requests.exceptions.ConnectionError:
        return {"answer": "Cannot connect to chat API. Check CHAT_API_URL setting.", "sources": [], "model": model, "error": True}
    except requests.exceptions.Timeout:
        return {"answer": "Chat API timed out. Try again.", "sources": [], "model": model, "error": True}

    sources = [{"id": e["id"], "subject": e.get("subject",""), "from": e.get("from",""), "date": e.get("date","")} for e in emails[:10]]
    return {"answer": answer, "sources": sources, "model": model, "emails_searched": len(emails), "error": False}


def get_stats_summary():
    """Quick archive stats for the chat UI header."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
        senders = conn.execute("SELECT COUNT(DISTINCT sender_email) FROM emails").fetchone()[0]
        return f"Archive: {total} emails from {senders} senders."
