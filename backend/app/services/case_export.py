"""Handoff package for a case: owner-marked evidence as a self-contained ZIP."""
import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from html import escape

CSV_COLS = ["date", "from", "to_cc", "subject", "quote", "quote_source", "note",
            "found_by_terms", "mailbox", "email_id", "eml_file"]
LOG_COLS = ["run_id", "term", "term_version", "term_source", "retired", "started_at", "status",
            "keyword", "recipients", "attachments", "semantic", "error"]


def _safe(v):
    # Spreadsheets run text starting with these characters as a formula.
    return "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


def _csv(cols, rows) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, cols)
    w.writeheader()
    w.writerows({k: _safe(v) for k, v in r.items()} for r in rows)
    return buf.getvalue()


def _to_cc(recipients_json) -> str:
    try:
        recips = json.loads(recipients_json or "[]")
    except (TypeError, ValueError):
        return ""
    out = []
    for r in recips if isinstance(recips, list) else []:
        if not isinstance(r, dict):
            continue
        addr = r.get("email") or ""
        who = f"{r['name']} <{addr}>" if r.get("name") else addr
        out.append(f"{who} ({(r.get('type') or 'to').capitalize()})")
    return "; ".join(out)


def _day(row) -> str:
    if row["date_sent"] and len(row["date_sent"]) >= 10:
        return row["date_sent"][:10]
    if row["date_timestamp"] is not None:
        return datetime.fromtimestamp(row["date_timestamp"], timezone.utc).strftime("%Y-%m-%d")
    return ""


def _counts(raw) -> dict:
    try:
        d = json.loads(raw or "{}")
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


def _timeline(case, items) -> str:
    def entry(it):
        link = f' <a href="{escape(it["eml_file"])}">original</a>' if it["eml_file"] else ""
        badge = ' <span class="b">semantic only</span>' if it["semantic_only"] else ""
        parts = [f'<h3>{escape(it["subject"] or "(no subject)")}{badge}</h3>',
                 f'<p class="meta">{escape(it["date"] or "undated")} &middot; '
                 f'{escape(it["from"])} &rarr; {escape(it["to_cc"])}{link}</p>']
        if it["quote"]:
            parts.append(f'<blockquote>{escape(it["quote"])}</blockquote>')
        if it["note"]:
            parts.append(f'<p class="note">Note: {escape(it["note"])}</p>')
        return f'<div class="e">{"".join(parts)}</div>'

    dated = [i for i in items if i["ts"] is not None]
    undated = [i for i in items if i["ts"] is None]
    body = "".join(entry(i) for i in sorted(dated, key=lambda i: i["ts"]))
    if undated:
        body += "<h2>Undated</h2>" + "".join(entry(i) for i in undated)
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<title>{escape(case["name"])} - timeline</title><style>'
        "body{font-family:sans-serif;max-width:50em;margin:2em auto;padding:0 1em}"
        ".e{border-top:1px solid #999;padding:.4em 0;break-inside:avoid}"
        ".meta{color:#444;font-size:.9em}blockquote{margin:.5em 1em;font-style:italic}"
        ".b{font-size:.7em;border:1px solid #999;padding:0 .3em}"
        "@media print{a{color:inherit}}</style></head><body>"
        f'<h1>{escape(case["name"])}</h1><p>{escape(case["issue"])}</p>{body}</body></html>')


def build_case_zip(conn, case_id: int) -> bytes:
    case = dict(conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone())

    found = {}
    for r in conn.execute(
        "SELECT DISTINCT cr.email_id, t.text, t.version FROM case_candidate_runs cr"
        " JOIN case_runs r ON r.id = cr.run_id JOIN case_terms t ON t.id = r.term_id"
        " WHERE cr.case_id = ? ORDER BY t.id", (case_id,)):
        found.setdefault(r["email_id"], []).append(f"{r['text']} v{r['version']}")

    items, files, unavailable = [], {}, []
    rows = conn.execute(
        "SELECT c.review, c.semantic_only, c.owner_quote, c.model_quote, c.model_quote_ok, c.note, e.id, e.subject,"
        " e.sender_name, e.sender_email, e.date_sent, e.date_timestamp, e.recipients,"
        " e.raw_message, e.mbox_source FROM case_candidates c JOIN emails e ON e.id = c.email_id"
        " WHERE c.case_id = ? AND c.review = 'evidence' ORDER BY e.date_timestamp IS NULL,"
        " e.date_timestamp, e.id", (case_id,)).fetchall()
    for r in rows:
        day = _day(r)
        raw = r["raw_message"]
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        eml = ""
        if raw:
            eml = f"eml/{day or 'undated'}_{r['id']}.eml"
            files[eml] = bytes(raw)
        else:
            unavailable.append(r)
        if r["owner_quote"]:
            quote, src = r["owner_quote"], "owner"
        elif r["model_quote"] and r["model_quote_ok"] == 1:
            quote, src = r["model_quote"], "model"
        else:
            quote, src = "", ""
        sender = r["sender_email"] or ""
        if r["sender_name"]:
            sender = f"{r['sender_name']} <{sender}>"
        items.append({
            "date": day, "from": sender, "to_cc": _to_cc(r["recipients"]),
            "subject": r["subject"] or "", "quote": quote, "quote_source": src,
            "note": r["note"] or "", "found_by_terms": "; ".join(found.get(r["id"], []))
            + (" (semantic only)" if r["semantic_only"] else ""),
            "mailbox": r["mbox_source"] or "", "semantic_only": bool(r["semantic_only"]), "email_id": r["id"], "eml_file": eml,
            "ts": r["date_timestamp"]})

    runs = conn.execute(
        "SELECT r.*, t.text, t.version, t.source, t.retired FROM case_runs r"
        " LEFT JOIN case_terms t ON t.id = r.term_id WHERE r.case_id = ? ORDER BY r.id",
        (case_id,)).fetchall()
    log_rows, errors, capped, unfinished = [], [], [], []
    for r in runs:
        c = _counts(r["channel_counts"])
        log_rows.append({
            "run_id": r["id"], "term": r["text"] or "", "term_version": r["version"] or "",
            "term_source": r["source"] or "", "retired": r["retired"] or 0,
            "started_at": r["started_at"] or "", "status": r["status"],
            "keyword": c.get("keyword", ""), "recipients": c.get("recipients", ""),
            "attachments": c.get("attachments", ""), "semantic": c.get("semantic", ""),
            "error": r["error"] or ""})
        label = f"run {r['id']} (term: {r['text'] or 'n/a'})"
        if r["status"] == "error":
            errors.append(f"{label}: {r['error'] or 'unknown error'}")
        if r["status"] == "running":
            unfinished.append(label)
        if c.get("semantic_capped"):
            capped.append(label)

    n_cands = conn.execute("SELECT COUNT(*) FROM case_candidates WHERE case_id = ?",
                           (case_id,)).fetchone()[0]
    n_terms = conn.execute("SELECT COUNT(*) FROM case_terms WHERE case_id = ?", (case_id,)).fetchone()[0]
    unindexed = conn.execute("SELECT COUNT(*) FROM attachment_content").fetchone()[0] == 0

    readme = [
        f"# {case['name']}", "", f"Issue: {case['issue']}", "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", "",
        "## Counts", "",
        f"- Search terms (all versions, including retired): {n_terms}",
        f"- Search runs: {len(runs)}", f"- Candidate emails found: {n_cands}",
        f"- Emails marked as evidence by the owner: {len(items)}", "",
        "## Method", "",
        "- Keyword search covers subject, sender name and address, and the full body. It returns "
        "all matches for each term, with no cap.",
        "- Person search matches sender and To/Cc/Bcc addresses and display names.",
        "- Meaning-based (semantic) search is a separate, lower-confidence tier: the top 50 results "
        "per term. Emails found only this way are marked \"semantic only\".",
        "- Attachment text is searched only where it has been indexed (see warning below, if any).",
        "- The date range and people are hints, never filters: nothing outside the range and no "
        "undated email was dropped.",
        "- AI triage read at most the first 6,000 characters of each email and only ordered the "
        "review queue. It decided nothing.",
        "- Only emails the owner marked as evidence are in this package. Other candidates are "
        "counted above but not included.",
        "- A quote marked `owner` was entered by the owner. A quote marked `model` was suggested by "
        "an AI model and checked to appear in the email body, ignoring case, whitespace, "
        "quote/dash style and reply markers (>). Failed model quotes are left blank.",
        "- In the CSV files, text starting with a character that spreadsheets run as a formula "
        "(= + - @) was prefixed with an apostrophe. The .eml files are the exact stored originals.",
        "",
        "## Files", "",
        "- `evidence.csv`: one row per evidence email. `to_cc` lists recipients as "
        "`Name <address> (Type)` separated by `;`. `eml_file` points to the original.",
        "- `timeline.html`: printable timeline sorted by date. Undated items come last.",
        "- `eml/`: original messages exactly as stored at ingest, bytes unmodified.",
        "- `search_log.csv`: every search run, including runs for retired terms.", ""]
    if unindexed:
        readme += ["## Attachment text not indexed", "",
                   "No attachment text is indexed in this archive, so attachment contents were "
                   "not searched. Matches inside attachments may be missing.", ""]
    if errors:
        readme += ["## Search errors", ""] + [f"- {e}" for e in errors] + [
            "", "Results from these runs may be incomplete.", ""]
    if unfinished:
        readme += ["## Search runs that did not finish", ""] + [f"- {u}" for u in unfinished] + [
            "", "Results from these runs may be incomplete.", ""]
    if capped:
        readme += ["## Semantic results capped", ""] + [f"- {c}" for c in capped] + [
            "", "More semantic matches existed than were returned.", ""]
    if unavailable:
        readme += ["## Originals unavailable", "",
                   "The original message was not stored for these evidence emails, so no .eml "
                   "file is included:", ""]
        readme += [f"- id {r['id']}, {_day(r) or 'undated'}, {r['subject'] or '(no subject)'}"
                   for r in unavailable]
        readme.append("")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("evidence.csv", _csv(CSV_COLS, [{k: i[k] for k in CSV_COLS} for i in items]))
        z.writestr("timeline.html", _timeline(case, items))
        for name, data in files.items():
            z.writestr(name, data)
        z.writestr("search_log.csv", _csv(LOG_COLS, log_rows))
        z.writestr("README.md", "\n".join(readme))
    return buf.getvalue()
