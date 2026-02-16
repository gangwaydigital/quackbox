"""
Email indexer service.
Supports both traditional mbox files and Apple Mail .emlx format.
"""

import time
from pathlib import Path

from app.database import get_db
from app.services.parser import parse_mbox, count_messages
from app.services.emlx_parser import parse_emlx_file, find_emlx_files


def ingest_mbox(mbox_path: Path) -> dict:
    start = time.time()
    imported = 0
    skipped = 0
    errors = 0
    total = count_messages(mbox_path)
    if mbox_path.name == "mbox":
        source_label = mbox_path.parent.name
    else:
        source_label = mbox_path.name
    print(f"📨 Ingesting {source_label} ({total} messages)...")
    with get_db() as conn:
        for i, record in enumerate(parse_mbox(mbox_path, source_name=source_label)):
            try:
                if record["message_id"]:
                    exists = conn.execute("SELECT 1 FROM emails WHERE message_id = ?", (record["message_id"],)).fetchone()
                    if exists:
                        skipped += 1
                        continue
                conn.execute("""INSERT INTO emails (message_id, subject, sender_name, sender_email, recipients, date_sent, date_timestamp, body_text, body_html, headers, mbox_source, thread_id, has_attachments, attachment_names) VALUES (:message_id, :subject, :sender_name, :sender_email, :recipients, :date_sent, :date_timestamp, :body_text, :body_html, :headers, :mbox_source, :thread_id, :has_attachments, :attachment_names)""", record)
                imported += 1
                if (i + 1) % 500 == 0:
                    conn.commit()
                    print(f"  ... processed {i + 1}/{total}")
            except Exception as e:
                print(f"  ⚠ Error inserting message: {e}")
                errors += 1
                continue
    duration = time.time() - start
    print(f"✅ Done: {imported} imported, {skipped} skipped, {errors} errors ({duration:.1f}s)")
    return {"mbox_file": source_label, "total_messages": total, "imported": imported, "skipped": skipped, "errors": errors, "duration_seconds": round(duration, 2)}


def ingest_emlx_mailbox(mailbox_name: str, emlx_files: list[Path]) -> dict:
    start = time.time()
    imported = 0
    skipped = 0
    errors = 0
    total = len(emlx_files)
    print(f"📨 Ingesting {mailbox_name} ({total} .emlx messages)...")
    with get_db() as conn:
        for i, emlx_path in enumerate(emlx_files):
            try:
                record = parse_emlx_file(emlx_path, source_name=mailbox_name)
                if record is None:
                    skipped += 1
                    continue
                if record["message_id"]:
                    exists = conn.execute("SELECT 1 FROM emails WHERE message_id = ?", (record["message_id"],)).fetchone()
                    if exists:
                        skipped += 1
                        continue
                conn.execute("""INSERT INTO emails (message_id, subject, sender_name, sender_email, recipients, date_sent, date_timestamp, body_text, body_html, headers, mbox_source, thread_id, has_attachments, attachment_names) VALUES (:message_id, :subject, :sender_name, :sender_email, :recipients, :date_sent, :date_timestamp, :body_text, :body_html, :headers, :mbox_source, :thread_id, :has_attachments, :attachment_names)""", record)
                imported += 1
                if (i + 1) % 500 == 0:
                    conn.commit()
                    print(f"  ... processed {i + 1}/{total}")
            except Exception as e:
                print(f"  ⚠ Error processing {emlx_path.name}: {e}")
                errors += 1
                continue
    duration = time.time() - start
    print(f"✅ Done: {imported} imported, {skipped} skipped, {errors} errors ({duration:.1f}s)")
    return {"mbox_file": mailbox_name, "total_messages": total, "imported": imported, "skipped": skipped, "errors": errors, "duration_seconds": round(duration, 2)}


def ingest_all(data_dir: Path) -> list[dict]:
    results = []
    mailboxes = find_emlx_files(data_dir)
    if mailboxes:
        total_emlx = sum(len(files) for files in mailboxes.values())
        print(f"Found {len(mailboxes)} mailbox(es) with {total_emlx} total .emlx messages")
        for mailbox_name in sorted(mailboxes.keys()):
            emlx_files = mailboxes[mailbox_name]
            result = ingest_emlx_mailbox(mailbox_name, emlx_files)
            results.append(result)
    mbox_files = []
    for mbox_file in data_dir.rglob("mbox"):
        if mbox_file.is_file() and mbox_file.stat().st_size > 0:
            mbox_files.append(mbox_file)
    for f in data_dir.glob("*.mbox"):
        if f.is_file() and f.stat().st_size > 0:
            mbox_files.append(f)
    mbox_files = list({str(f): f for f in mbox_files}.values())
    if mbox_files:
        print(f"Found {len(mbox_files)} traditional mbox file(s)")
        for mbox_path in sorted(mbox_files):
            result = ingest_mbox(mbox_path)
            results.append(result)
    if not results:
        print(f"No email data found in {data_dir}")
    return results
