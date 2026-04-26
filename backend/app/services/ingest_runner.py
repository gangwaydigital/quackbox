"""
Ingest runner — orchestrates a full pass over DATA_DIR and tracks progress.

Extracted from app/routers/ingest.py so the same code can be invoked from
the HTTP `/api/ingest/start` endpoint AND from the background watcher.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from app.config import DATA_DIR
from app.logging_config import get_logger
from app.services.indexer import ingest_mbox, ingest_emlx_mailbox
from app.services.emlx_parser import find_emlx_files
from app.services.folders import all_data_paths

log = get_logger("ingest_runner")


# Shared mutable status — read by the router's /progress endpoint and the
# watcher's /watcher endpoint, written by run_ingest().
INGEST_STATUS: dict = {
    "running": False, "phase": "", "progress": "",
    "current_source": "", "files_done": 0, "files_total": 0,
    "emails_imported": 0, "emails_skipped": 0,
    "started_at": None, "finished_at": None,
    "elapsed_seconds": 0, "results": None, "error": None,
    "sources_progress": [], "incremental": True,
    "triggered_by": "manual",  # "manual" or "watcher"
}


def is_ingest_running() -> bool:
    return bool(INGEST_STATUS.get("running"))


def _discover_mbox_files(data_dir: Path) -> set[str]:
    """Find both `*.mbox` files and Apple-style `mbox` bundle files under data_dir."""
    mbox_files: set[str] = set()
    for f in data_dir.rglob("mbox"):
        if f.is_file() and f.stat().st_size > 0:
            mbox_files.add(str(f))
    for f in data_dir.glob("*.mbox"):
        if f.is_file() and f.stat().st_size > 0:
            mbox_files.add(str(f))
    return mbox_files


def run_ingest(incremental: bool = True, triggered_by: str = "manual") -> dict:
    """
    Execute one ingest pass against DATA_DIR. Updates INGEST_STATUS in place
    and returns the final status dict.

    Safe to call from a background thread (used by both the executor in the
    HTTP endpoint and the watcher loop).
    """
    start_time = time.time()
    try:
        INGEST_STATUS.update({
            "running": True, "phase": "scanning",
            "progress": "Scanning data directory...",
            "started_at": start_time, "error": None, "results": None,
            "files_done": 0, "emails_imported": 0, "emails_skipped": 0,
            "current_source": "", "sources_progress": [], "elapsed_seconds": 0,
            "incremental": incremental,
            "triggered_by": triggered_by,
        })

        # Scan every registered folder + the legacy DATA_DIR. A new folder
        # added via the in-app picker is just another path in this list.
        scan_paths = all_data_paths()

        all_mailboxes: dict = {}
        all_mbox_files: set[str] = set()
        for path in scan_paths:
            for name, files in (find_emlx_files(path) or {}).items():
                if name in all_mailboxes:
                    # Merge across roots so duplicate mailbox names from
                    # different folders don't clobber each other.
                    existing_paths = {str(f) for f in all_mailboxes[name]}
                    for f in files:
                        if str(f) not in existing_paths:
                            all_mailboxes[name].append(f)
                else:
                    all_mailboxes[name] = list(files)
            all_mbox_files.update(_discover_mbox_files(path))

        total_sources = len(all_mailboxes) + len(all_mbox_files)
        INGEST_STATUS["files_total"] = total_sources
        INGEST_STATUS["phase"] = "importing"

        results = []

        if all_mailboxes:
            for mailbox_name in sorted(all_mailboxes.keys()):
                INGEST_STATUS["current_source"] = mailbox_name
                INGEST_STATUS["progress"] = f"Importing {mailbox_name}..."
                INGEST_STATUS["elapsed_seconds"] = round(time.time() - start_time)

                result = ingest_emlx_mailbox(
                    mailbox_name, all_mailboxes[mailbox_name], incremental=incremental
                )
                results.append(result)
                _record_source_result(mailbox_name, result)

        if all_mbox_files:
            for mbox_path_str in sorted(all_mbox_files):
                mbox_path = Path(mbox_path_str)
                name = mbox_path.parent.name if mbox_path.name == "mbox" else mbox_path.name
                INGEST_STATUS["current_source"] = name
                INGEST_STATUS["progress"] = f"Importing {name}..."
                INGEST_STATUS["elapsed_seconds"] = round(time.time() - start_time)

                result = ingest_mbox(mbox_path, incremental=incremental)
                results.append(result)
                _record_source_result(name, result)

        total_imported = INGEST_STATUS["emails_imported"]
        elapsed = round(time.time() - start_time)
        mode_label = "incremental" if incremental else "full"
        INGEST_STATUS.update({
            "running": False, "phase": "done",
            "progress": f"Complete! {total_imported:,} new emails ({mode_label}) in {elapsed}s.",
            "finished_at": time.time(), "results": results,
            "elapsed_seconds": elapsed, "current_source": "",
        })

        if total_imported > 0:
            _post_ingest_warmup()

    except Exception as e:
        log.exception("Ingest failed")
        INGEST_STATUS.update({
            "running": False, "phase": "error",
            "progress": f"Error: {str(e)}",
            "error": str(e), "finished_at": time.time(),
            "elapsed_seconds": round(time.time() - start_time),
        })

    return INGEST_STATUS


def _record_source_result(name: str, result: dict) -> None:
    INGEST_STATUS["files_done"] += 1
    INGEST_STATUS["emails_imported"] += result.get("imported", 0)
    INGEST_STATUS["emails_skipped"] += result.get("skipped", 0)
    INGEST_STATUS["sources_progress"].append({
        "name": name,
        "imported": result.get("imported", 0),
        "skipped": result.get("skipped", 0),
        "mode": result.get("mode", ""),
    })


def _post_ingest_warmup() -> None:
    """Run cache warming + attachment + calendar indexing after a successful
    ingest. Each step is best-effort — failure is logged but doesn't stop
    the others."""
    try:
        from app.services.analytics import warm_cache
        warm_cache()
    except Exception as e:
        log.warning("Cache warming failed (non-fatal): %s", e)
    try:
        from app.services.attachment_indexer import index_all_attachments
        index_all_attachments()
    except Exception as e:
        log.warning("Attachment indexing failed (non-fatal): %s", e)
    try:
        from app.services.calendar_extractor import index_all_calendar_events
        index_all_calendar_events()
    except Exception as e:
        log.warning("Calendar indexing failed (non-fatal): %s", e)
