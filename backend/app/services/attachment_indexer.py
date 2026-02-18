"""
Attachment text extraction service.

Extracts full text from PDF and DOCX attachments and stores it in
attachment_content for FTS5 indexing and preview.

Extraction is best-effort: failures are logged but never crash the app.
"""

import io
import json
import time
from app.database import get_db
from app.logging_config import get_logger
from app.services.attachment_extractor import extract_attachment

log = get_logger("attachment_indexer")

INDEXABLE_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
}

MAX_EXTRACT_BYTES = 10 * 1024 * 1024   # 10 MB cap per file
MAX_TEXT_CHARS = 100_000                # Store at most 100K chars


# ── Extractors ─────────────────────────────────────────────────────────────

def _extract_pdf_text(data: bytes) -> tuple[str, int]:
    """Return (text, page_count) from PDF bytes. Requires pypdf."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pages.append("")
        text = "\n".join(pages)[:MAX_TEXT_CHARS]
        return text, len(reader.pages)
    except ImportError:
        log.warning("pypdf not installed — PDF extraction unavailable")
        return "", 0
    except Exception as e:
        log.debug("PDF extraction failed: %s", e)
        return "", 0


def _extract_docx_text(data: bytes) -> tuple[str, int]:
    """Return (text, paragraph_count) from DOCX bytes. Requires python-docx."""
    try:
        import docx
        doc = docx.Document(io.BytesIO(data))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs)[:MAX_TEXT_CHARS]
        return text, len(paragraphs)
    except ImportError:
        log.warning("python-docx not installed — DOCX extraction unavailable")
        return "", 0
    except Exception as e:
        log.debug("DOCX extraction failed: %s", e)
        return "", 0


def _extract_text(data: bytes, extension: str, content_type: str) -> tuple[str, int]:
    """Dispatch to the appropriate extractor."""
    ext = extension.lower().lstrip(".")
    if ext == "pdf" or "pdf" in content_type:
        return _extract_pdf_text(data)
    if ext in ("docx",) or "wordprocessingml" in content_type:
        return _extract_docx_text(data)
    if ext == "doc" or content_type == "application/msword":
        # Legacy .doc — try docx parser anyway (sometimes works for newer .doc)
        text, pages = _extract_docx_text(data)
        if text:
            return text, pages
        return "", 0
    return "", 0


def _is_indexable(filename: str, content_type: str = "") -> bool:
    """True if we can attempt text extraction from this file type."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in INDEXABLE_TYPES or any(t in content_type for t in INDEXABLE_TYPES.values())


# ── Main indexing functions ────────────────────────────────────────────────

def index_attachment(email_id: int, filename: str) -> dict:
    """
    Extract and store text from a single attachment.

    Returns a result dict with status, word_count, page_count.
    """
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id, extraction_status FROM attachment_content WHERE email_id = ? AND filename = ?",
            (email_id, filename)
        ).fetchone()

    if existing and existing["extraction_status"] == "ok":
        return {"status": "already_indexed", "filename": filename}

    # Extract binary from mbox/emlx
    result = extract_attachment(email_id, filename)
    if result is None:
        _store_result(email_id, filename, "", "", 0, 0, "not_found")
        return {"status": "not_found", "filename": filename}

    data = result["data"]
    content_type = result.get("content_type", "")

    if len(data) > MAX_EXTRACT_BYTES:
        _store_result(email_id, filename, content_type, "", 0, 0, "too_large")
        return {"status": "too_large", "filename": filename, "size": len(data)}

    if not _is_indexable(filename, content_type):
        _store_result(email_id, filename, content_type, "", 0, 0, "unsupported")
        return {"status": "unsupported", "filename": filename}

    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    text, page_count = _extract_text(data, ext, content_type)
    word_count = len(text.split()) if text else 0
    status = "ok" if text else "empty"

    _store_result(email_id, filename, content_type, text, page_count, word_count, status)
    log.debug("Indexed %s — %d words, %d pages", filename, word_count, page_count)
    return {
        "status": status,
        "filename": filename,
        "word_count": word_count,
        "page_count": page_count,
    }


def _store_result(email_id, filename, content_type, text, page_count, word_count, status):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO attachment_content
                (email_id, filename, content_type, extracted_text, page_count, word_count, extraction_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(email_id) DO UPDATE SET
                filename=excluded.filename,
                content_type=excluded.content_type,
                extracted_text=excluded.extracted_text,
                page_count=excluded.page_count,
                word_count=excluded.word_count,
                extraction_status=excluded.extraction_status,
                extracted_at=datetime('now')
        """, (email_id, filename, content_type, text, page_count, word_count, status))


def index_all_attachments(batch_size: int = 100) -> dict:
    """
    Index all un-indexed PDF/DOCX attachments in the archive.

    Called after ingest completes. Safe to re-run (skips already-indexed files).
    Returns a summary dict.
    """
    start = time.time()
    log.info("📎 Indexing PDF/DOCX attachments...")

    with get_db() as conn:
        rows = conn.execute("""
            SELECT e.id as email_id, e.attachment_names, e.mbox_source
            FROM emails e
            WHERE e.has_attachments = 1 AND e.attachment_names IS NOT NULL
        """).fetchall()

    processed = 0
    indexed = 0
    errors = 0

    for row in rows:
        try:
            names = json.loads(row["attachment_names"]) if row["attachment_names"] else []
        except Exception:
            continue

        for name in names:
            if not name:
                continue
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if ext not in ("pdf", "docx", "doc"):
                continue

            processed += 1
            try:
                result = index_attachment(row["email_id"], name)
                if result["status"] == "ok":
                    indexed += 1
            except Exception as e:
                log.warning("Error indexing %s (email %d): %s", name, row["email_id"], e)
                errors += 1

            if processed % 50 == 0:
                log.info("  ... indexed %d attachments", processed)

    elapsed = round(time.time() - start, 2)
    log.info("✅ Attachment indexing done: %d indexed, %d errors (%.2fs)", indexed, errors, elapsed)
    return {"processed": processed, "indexed": indexed, "errors": errors, "elapsed_seconds": elapsed}


def get_attachment_preview(email_id: int, filename: str) -> dict | None:
    """Return cached text content for an attachment, or None if not indexed."""
    with get_db() as conn:
        row = conn.execute("""
            SELECT extracted_text, page_count, word_count, extraction_status, content_type
            FROM attachment_content
            WHERE email_id = ? AND filename = ?
        """, (email_id, filename)).fetchone()

    if not row:
        return None

    return {
        "filename": filename,
        "email_id": email_id,
        "extraction_status": row["extraction_status"],
        "content_type": row["content_type"],
        "page_count": row["page_count"],
        "word_count": row["word_count"],
        "text": row["extracted_text"] or "",
    }


def search_attachment_content(query: str, page: int = 1, page_size: int = 20) -> dict:
    """Full-text search across indexed attachment content using FTS5."""
    with get_db() as conn:
        # Sanitize query for FTS5
        safe_query = query.replace('"', '""').strip()
        if not safe_query:
            return {"results": [], "total": 0, "page": page, "page_size": page_size}

        try:
            rows = conn.execute("""
                SELECT
                    ac.email_id, ac.filename, ac.page_count, ac.word_count,
                    e.subject, e.sender_name, e.sender_email, e.date_sent,
                    snippet(attachment_fts, 1, '<mark>', '</mark>', '…', 32) AS snippet
                FROM attachment_fts
                JOIN attachment_content ac ON attachment_fts.rowid = ac.id
                JOIN emails e ON ac.email_id = e.id
                WHERE attachment_fts MATCH ?
                ORDER BY rank
                LIMIT ? OFFSET ?
            """, (safe_query, page_size, (page - 1) * page_size)).fetchall()

            total_row = conn.execute("""
                SELECT COUNT(*) FROM attachment_fts WHERE attachment_fts MATCH ?
            """, (safe_query,)).fetchone()
            total = total_row[0] if total_row else 0

        except Exception as e:
            log.warning("Attachment FTS search failed: %s", e)
            return {"results": [], "total": 0, "page": page, "page_size": page_size, "error": str(e)}

    return {
        "results": [
            {
                "email_id": r["email_id"],
                "filename": r["filename"],
                "subject": r["subject"],
                "sender_name": r["sender_name"],
                "sender_email": r["sender_email"],
                "date_sent": r["date_sent"],
                "page_count": r["page_count"],
                "word_count": r["word_count"],
                "snippet": r["snippet"],
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }
