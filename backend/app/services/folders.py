"""
User-registered ingest folders.

Browser security prevents the frontend from reading host paths directly,
so the backend exposes a simple directory-tree API the UI can navigate.
For this to work, the container needs read access to the host filesystem
— see docker-compose.yml's `/host/Users` and `/host/Volumes` mounts.

The mapping is a straight prefix swap: a host path like
`/Users/duck/Library/Mail/V10` corresponds to the container path
`/host/Users/duck/Library/Mail/V10`. Both are persisted so the UI can
show the human-friendly version.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from app.database import get_db
from app.logging_config import get_logger

log = get_logger("folders")

# Host roots the user is allowed to browse. Each root is shown as a
# top-level entry when no path is provided. Restrict by editing the
# docker-compose mounts AND this list.
HOST_ROOTS = ["/host/Users", "/host/Volumes"]

# Common Apple-Mail / mbox file/folder shapes we should highlight in the
# browser so the user knows a folder is interesting before they pick it.
EMAIL_FILE_EXTS = {".mbox", ".emlx"}
EMAIL_FOLDER_NAMES = ("Mailboxes.mbox", ".mbox")


# ── Path mapping ───────────────────────────────────────────────────────────


def host_to_container(host_path: str) -> Optional[str]:
    """
    Map a user-facing host path to the path the container can actually open.
    Returns None if the path doesn't fall under one of HOST_ROOTS — that's
    the security guardrail.

    Uses os.path.normpath() to collapse `..` segments string-side (no
    filesystem access), so traversal attempts like /Users/../etc/passwd
    are rejected before they ever resolve.
    """
    if not host_path:
        return None
    # normpath collapses '.' and '..' without touching the filesystem so
    # /Users/../etc/passwd → /etc/passwd, which falls outside HOST_ROOTS.
    norm = os.path.normpath(host_path).rstrip("/")
    # /Users/x/y → /host/Users/x/y    /Volumes/disk → /host/Volumes/disk
    for root in HOST_ROOTS:
        # root is like /host/Users — host-side equivalent is /Users
        host_prefix = root.replace("/host", "", 1)
        if norm == host_prefix or norm.startswith(host_prefix + "/"):
            return root + norm[len(host_prefix):]
    return None


def container_to_host(container_path: str) -> str:
    """Strip the /host prefix back off so the UI shows /Users/... not /host/Users/..."""
    norm = str(Path(container_path)).rstrip("/")
    for root in HOST_ROOTS:
        if norm == root or norm.startswith(root + "/"):
            return norm[len("/host"):]
    return norm


# ── Directory browser ──────────────────────────────────────────────────────


def _count_email_artifacts(path: Path) -> dict:
    """
    Cheap heuristic: how interesting is this folder for ingestion?
    Looks one level deep so big trees stay browsable. Returns counts of
    direct .mbox / .emlx files and a flag for Apple-Mail-style nested
    `mbox` bundles (no recursion).
    """
    info = {"mbox_files": 0, "emlx_files": 0, "looks_like_mailbox": False}
    try:
        for child in path.iterdir():
            name = child.name
            if name.startswith("."):
                continue
            if child.is_file():
                suffix = child.suffix.lower()
                if suffix == ".mbox":
                    info["mbox_files"] += 1
                elif suffix == ".emlx":
                    info["emlx_files"] += 1
            else:
                if name.endswith(".mbox") or name == "Mailboxes.mbox":
                    info["looks_like_mailbox"] = True
    except (OSError, PermissionError):
        pass
    return info


def browse(host_path: Optional[str]) -> dict:
    """
    Return the directory listing the UI uses to navigate. If host_path is
    falsy, returns the configured roots so the picker has somewhere to
    start. Refuses to browse anything outside HOST_ROOTS.
    """
    if not host_path:
        # Top-level: list each root that actually exists in the container
        entries = []
        for root in HOST_ROOTS:
            p = Path(root)
            if not p.exists():
                continue
            entries.append({
                "name": container_to_host(root).lstrip("/") or root,
                "host_path": container_to_host(root),
                "is_dir": True,
                "email_artifacts": {"mbox_files": 0, "emlx_files": 0, "looks_like_mailbox": False},
            })
        return {"path": None, "parent": None, "entries": entries}

    container_path = host_to_container(host_path)
    if container_path is None:
        return {"error": f"Path '{host_path}' is outside the allowed roots ({', '.join(container_to_host(r) for r in HOST_ROOTS)})"}

    p = Path(container_path)
    if not p.exists():
        return {"error": f"Path '{host_path}' does not exist"}
    if not p.is_dir():
        return {"error": f"Path '{host_path}' is not a directory"}

    entries = []
    try:
        for child in sorted(p.iterdir(), key=lambda c: (not c.is_dir(), c.name.lower())):
            if child.name.startswith("."):
                continue
            try:
                is_dir = child.is_dir()
            except (OSError, PermissionError):
                continue
            entry = {
                "name": child.name,
                "host_path": container_to_host(str(child)),
                "is_dir": is_dir,
            }
            if is_dir:
                entry["email_artifacts"] = _count_email_artifacts(child)
            entries.append(entry)
    except (OSError, PermissionError) as e:
        return {"error": f"Cannot read directory: {e}"}

    parent_host = container_to_host(str(p.parent)) if p.parent != p else None
    # Don't let the user navigate above the root they came from
    if parent_host and host_to_container(parent_host) is None:
        parent_host = None

    return {
        "path": host_path,
        "parent": parent_host,
        "entries": entries,
    }


# ── Folder registry CRUD ───────────────────────────────────────────────────


def list_folders() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, label, host_path, container_path, added_at
            FROM ingest_folders
            ORDER BY added_at DESC
        """).fetchall()
        items = []
        for row in rows:
            d = dict(row)
            d["accessible"] = Path(d["container_path"]).is_dir()
            items.append(d)
        return items


def add_folder(host_path: str, label: Optional[str] = None) -> dict:
    """
    Register a host_path as a permanent ingest source.

    Validates that:
      1. The path falls under HOST_ROOTS (security)
      2. The container can actually read it (mount sanity)
      3. It's a directory
      4. Same path isn't already registered (UNIQUE constraint catches this too)
    """
    container_path = host_to_container(host_path)
    if container_path is None:
        return {
            "error": (
                f"Path '{host_path}' is outside the allowed roots. "
                f"To browse other locations, add their parent directory as a "
                f"read-only mount in docker-compose.yml under /host/."
            ),
            "status": 400,
        }
    p = Path(container_path)
    if not p.exists() or not p.is_dir():
        return {"error": f"Not a readable directory: {host_path}", "status": 400}

    final_label = (label or "").strip() or Path(host_path).name or host_path

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM ingest_folders WHERE host_path = ?", (host_path,)
        ).fetchone()
        if existing:
            return {"error": f"Folder is already registered: {host_path}", "status": 409}
        cur = conn.execute(
            """
            INSERT INTO ingest_folders (label, host_path, container_path)
            VALUES (?, ?, ?)
            """,
            (final_label, host_path, container_path),
        )
        new_id = cur.lastrowid
        row = conn.execute(
            "SELECT id, label, host_path, container_path, added_at FROM ingest_folders WHERE id = ?",
            (new_id,),
        ).fetchone()
    log.info("📂 Registered ingest folder: %s (%s)", final_label, host_path)
    return dict(row)


def delete_folder(folder_id: int) -> dict:
    with get_db() as conn:
        row = conn.execute(
            "SELECT host_path FROM ingest_folders WHERE id = ?", (folder_id,)
        ).fetchone()
        if not row:
            return {"error": "Folder not found", "status": 404}
        conn.execute("DELETE FROM ingest_folders WHERE id = ?", (folder_id,))
    log.info("📂 Unregistered ingest folder: %s", row["host_path"])
    return {"deleted": folder_id, "host_path": row["host_path"]}


def all_data_paths() -> list[Path]:
    """
    Return every Path that should be scanned for mail content during ingest:
    the legacy DATA_DIR plus every accessible registered folder.

    Used by ingest_runner / watcher / attachment_extractor. Inaccessible
    registered folders (e.g. external drive unplugged) are skipped with a
    log warning so they don't break the run.
    """
    from app.config import DATA_DIR

    paths: list[Path] = []
    if DATA_DIR.exists():
        paths.append(DATA_DIR)

    seen = {str(DATA_DIR.resolve())}
    for folder in list_folders():
        cp = Path(folder["container_path"])
        try:
            real = str(cp.resolve())
        except OSError:
            real = folder["container_path"]
        if real in seen:
            continue
        if not cp.is_dir():
            log.warning(
                "📂 Registered folder not accessible (skipping): %s — is the drive mounted?",
                folder["host_path"],
            )
            continue
        seen.add(real)
        paths.append(cp)
    return paths
