"""
RAG Chat service — enhanced with semantic search, thread context, and archive stats.
"""
import json
import requests
from typing import Optional
from app.config import OLLAMA_BASE_URL
from app.database import get_db
from app.services.semantic_search import has_embeddings, hybrid_search

OLLAMA_CHAT_MODEL = "llama3.1:8b"

def get_available_models():
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        pass
    return []

def search_relevant_emails(query, limit=15):
    """Search using hybrid (keyword+semantic) if embeddings exist, else FTS5 only."""
    if has_embeddings():
        results = hybrid_search(query, limit=limit)
        # Fetch full body snippets for context
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
    """Original FTS5-only search."""
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
                 "email": r["sender_email"] or "", "date": r["date_sent"] or "",
                 "mailbox": r["mbox_source"] or "",
                 "body_snippet": (r["body_text"] or "")[:800]} for r in rows]

def _get_archive_context():
    """Build a rich context summary of the entire archive."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
        senders = conn.execute("SELECT COUNT(DISTINCT sender_email) FROM emails").fetchone()[0]
        date_range = conn.execute("SELECT MIN(date_sent), MAX(date_sent) FROM emails").fetchone()
        top_senders = conn.execute("""
            SELECT sender_name, sender_email, COUNT(*) as cnt FROM emails
            WHERE sender_email != '' GROUP BY sender_email ORDER BY cnt DESC LIMIT 15
        """).fetchall()
        top_mailboxes = conn.execute("""
            SELECT mbox_source, COUNT(*) as cnt FROM emails GROUP BY mbox_source ORDER BY cnt DESC LIMIT 10
        """).fetchall()
        thread_count = conn.execute("SELECT COUNT(*) FROM threads WHERE message_count >= 2").fetchone()[0]

        ctx = f"ARCHIVE OVERVIEW: {total:,} emails from {senders:,} unique senders"
        if date_range[0]:
            ctx += f", spanning {date_range[0][:10]} to {date_range[1][:10]}"
        ctx += f". {thread_count:,} multi-message conversation threads.\n"
        ctx += "TOP CONTACTS: " + ", ".join(
            f"{r['sender_name'] or r['sender_email']} ({r['cnt']})" for r in top_senders) + "\n"
        ctx += "MAILBOXES: " + ", ".join(
            f"{r['mbox_source']} ({r['cnt']})" for r in top_mailboxes)
        return ctx

def build_context(emails):
    if not emails:
        return "No relevant emails were found for this query."
    parts = [f"Found {len(emails)} relevant email(s):\n"]
    for i, em in enumerate(emails, 1):
        parts.append(f"--- Email {i} ---")
        parts.append(f"From: {em['from']} <{em.get('email','')}>")
        parts.append(f"Subject: {em.get('subject','')}")
        parts.append(f"Date: {em.get('date','')}")
        parts.append(f"Mailbox: {em.get('mailbox','')}")
        if em.get('body_snippet'):
            parts.append(f"Body:\n{em['body_snippet']}")
        parts.append("")
    return "\n".join(parts)

def chat(question, conversation_history=None, model=None, num_context_emails=15):
    model = model or OLLAMA_CHAT_MODEL
    conversation_history = conversation_history or []

    # Search with hybrid (semantic + keyword)
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
        resp = requests.post(f"{OLLAMA_BASE_URL}/api/chat",
            json={"model": model, "messages": messages, "stream": False,
                  "options": {"temperature": 0.3, "num_predict": 1024}}, timeout=120)
        if resp.status_code != 200:
            return {"answer": f"Error from Ollama (HTTP {resp.status_code}): {resp.text[:200]}", "sources": [], "model": model, "error": True}
        answer = resp.json().get("message", {}).get("content", "No response generated.")
    except requests.exceptions.ConnectionError:
        return {"answer": "Cannot connect to Ollama. Make sure it's running: `ollama serve`", "sources": [], "model": model, "error": True}
    except requests.exceptions.Timeout:
        return {"answer": "Ollama took too long to respond. Try again in a moment.", "sources": [], "model": model, "error": True}

    sources = [{"id": e["id"], "subject": e.get("subject",""), "from": e.get("from",""), "date": e.get("date","")} for e in emails[:10]]
    return {"answer": answer, "sources": sources, "model": model, "emails_searched": len(emails), "error": False}

def get_stats_summary():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
        senders = conn.execute("SELECT COUNT(DISTINCT sender_email) FROM emails").fetchone()[0]
        return f"Archive: {total} emails from {senders} senders."
