"""Tests for the user-registered ingest folders service."""
import pytest

from app import database
from app.services import folders as folders_svc


@pytest.fixture
def folders_db(tmp_path, monkeypatch):
    db_path = tmp_path / "folders-test.db"
    database.init_db(db_path)
    real_get_db = database.get_db

    def get_db_override(p=db_path):
        return real_get_db(p)
    monkeypatch.setattr(folders_svc, "get_db", get_db_override)
    return db_path


# ── Path mapping (host ↔ container) ─────────────────────────────────────────


class TestHostContainerMapping:
    def test_users_path_maps_through_host_users(self):
        assert folders_svc.host_to_container("/Users/duck/Mail") == "/host/Users/duck/Mail"

    def test_volumes_path_maps_through_host_volumes(self):
        assert folders_svc.host_to_container("/Volumes/RAID/V10") == "/host/Volumes/RAID/V10"

    def test_root_path_maps_to_root_of_mount(self):
        assert folders_svc.host_to_container("/Users") == "/host/Users"

    def test_path_outside_roots_is_rejected(self):
        assert folders_svc.host_to_container("/etc/passwd") is None
        assert folders_svc.host_to_container("/private/var/foo") is None

    def test_traversal_attempt_is_rejected(self):
        # Even though Path normalizes ".." segments, anything that escapes
        # the allowed roots should still be refused.
        assert folders_svc.host_to_container("/Users/../etc/passwd") is None

    def test_container_to_host_strips_prefix(self):
        assert folders_svc.container_to_host("/host/Users/duck/Mail") == "/Users/duck/Mail"
        assert folders_svc.container_to_host("/host/Volumes/RAID") == "/Volumes/RAID"


# ── Folder registry CRUD ────────────────────────────────────────────────────


class TestFolderRegistry:
    def test_initially_empty(self, folders_db):
        assert folders_svc.list_folders() == []

    def test_add_rejects_path_outside_roots(self, folders_db):
        result = folders_svc.add_folder("/etc/passwd")
        assert result["error"]
        assert result["status"] == 400

    def test_add_rejects_nonexistent_path(self, folders_db, tmp_path, monkeypatch):
        # Pretend HOST_ROOTS includes our tmp path so the security check
        # passes — then verify the existence check rejects bogus paths.
        monkeypatch.setattr(folders_svc, "HOST_ROOTS", [f"/host{tmp_path}"])
        result = folders_svc.add_folder(f"{tmp_path}/does-not-exist")
        assert result["error"]
        assert "Not a readable directory" in result["error"]

    def test_add_then_list_round_trips(self, folders_db, tmp_path, monkeypatch):
        # Use tmp_path as the only root; it definitely exists + is readable
        monkeypatch.setattr(folders_svc, "HOST_ROOTS", [f"/host{tmp_path}"])

        # And patch host_to_container to map our tmp_path → tmp_path itself
        # (no /host prefix) so add_folder's existence check sees the real dir.
        def map_to_real(host):
            from pathlib import Path
            if host == str(tmp_path) or host.startswith(str(tmp_path) + "/"):
                return host
            return None
        monkeypatch.setattr(folders_svc, "host_to_container", map_to_real)

        sub = tmp_path / "Inbox"
        sub.mkdir()
        result = folders_svc.add_folder(str(sub), label="My Inbox")
        assert "error" not in result
        assert result["host_path"] == str(sub)
        assert result["label"] == "My Inbox"

        listed = folders_svc.list_folders()
        assert len(listed) == 1
        assert listed[0]["host_path"] == str(sub)
        assert listed[0]["accessible"] is True

    def test_add_duplicate_returns_409(self, folders_db, tmp_path, monkeypatch):
        monkeypatch.setattr(folders_svc, "HOST_ROOTS", [f"/host{tmp_path}"])
        monkeypatch.setattr(folders_svc, "host_to_container",
                            lambda h: h if h.startswith(str(tmp_path)) else None)
        sub = tmp_path / "Inbox"
        sub.mkdir()
        folders_svc.add_folder(str(sub))
        result = folders_svc.add_folder(str(sub))
        assert result["status"] == 409
        assert "already registered" in result["error"]

    def test_delete_unregisters(self, folders_db, tmp_path, monkeypatch):
        monkeypatch.setattr(folders_svc, "HOST_ROOTS", [f"/host{tmp_path}"])
        monkeypatch.setattr(folders_svc, "host_to_container",
                            lambda h: h if h.startswith(str(tmp_path)) else None)
        sub = tmp_path / "Inbox"
        sub.mkdir()
        added = folders_svc.add_folder(str(sub))
        result = folders_svc.delete_folder(added["id"])
        assert result["deleted"] == added["id"]
        assert folders_svc.list_folders() == []

    def test_delete_missing_returns_404(self, folders_db):
        result = folders_svc.delete_folder(99999)
        assert result["status"] == 404


# ── Browser ────────────────────────────────────────────────────────────────


class TestBrowse:
    def test_top_level_returns_existing_roots(self, monkeypatch, tmp_path):
        # Make our tmp_path the only "root" and ensure it exists
        host_root = f"/host{tmp_path}"
        monkeypatch.setattr(folders_svc, "HOST_ROOTS", [host_root])
        # Also patch Path(root).exists() — easier: just leave HOST_ROOTS as
        # the real tmp_path with no /host prefix so the existence check passes
        monkeypatch.setattr(folders_svc, "HOST_ROOTS", [str(tmp_path)])
        result = folders_svc.browse(None)
        assert result["path"] is None
        assert len(result["entries"]) == 1
        assert result["entries"][0]["is_dir"] is True

    def test_outside_roots_is_rejected(self, folders_db):
        result = folders_svc.browse("/etc")
        assert "error" in result
        assert "outside the allowed roots" in result["error"]

    def test_lists_subdirectories_with_artifact_counts(self, monkeypatch, tmp_path):
        # Build a fake mailbox layout:
        #   tmp/Mail/
        #     Inbox.mbox/    (directory ending in .mbox → looks_like_mailbox)
        #     archive.mbox   (file)
        #     12345.emlx     (file)
        mail_dir = tmp_path / "Mail"
        mail_dir.mkdir()
        (mail_dir / "Inbox.mbox").mkdir()
        (mail_dir / "archive.mbox").write_bytes(b"From foo\n")
        (mail_dir / "12345.emlx").write_bytes(b"100\nfoo")

        monkeypatch.setattr(folders_svc, "HOST_ROOTS", [str(tmp_path)])
        monkeypatch.setattr(folders_svc, "host_to_container",
                            lambda h: h if h and h.startswith(str(tmp_path)) else (None if h else None))
        # container_to_host patched to be identity since our paths aren't prefixed
        monkeypatch.setattr(folders_svc, "container_to_host", lambda c: c)

        result = folders_svc.browse(str(mail_dir))
        names = {e["name"] for e in result["entries"]}
        assert "Inbox.mbox" in names
        assert "archive.mbox" in names
        assert "12345.emlx" in names

        inbox_entry = next(e for e in result["entries"] if e["name"] == "Inbox.mbox")
        assert inbox_entry["is_dir"] is True

    def test_skips_dotfiles(self, monkeypatch, tmp_path):
        (tmp_path / ".hidden").mkdir()
        (tmp_path / "visible").mkdir()
        monkeypatch.setattr(folders_svc, "HOST_ROOTS", [str(tmp_path)])
        monkeypatch.setattr(folders_svc, "host_to_container",
                            lambda h: h if h and h.startswith(str(tmp_path)) else None)
        monkeypatch.setattr(folders_svc, "container_to_host", lambda c: c)
        result = folders_svc.browse(str(tmp_path))
        names = {e["name"] for e in result["entries"]}
        assert "visible" in names
        assert ".hidden" not in names


# ── all_data_paths ─────────────────────────────────────────────────────────


class TestAllDataPaths:
    def test_includes_data_dir_when_it_exists(self, folders_db, monkeypatch, tmp_path):
        from app import config
        monkeypatch.setattr(config, "DATA_DIR", tmp_path)
        # Reload the function's view of DATA_DIR by patching it at the
        # services.folders import site too (it imports lazily inside).
        paths = folders_svc.all_data_paths()
        assert tmp_path in paths

    def test_skips_inaccessible_registered_folders(self, folders_db, monkeypatch, tmp_path):
        from app import config
        monkeypatch.setattr(config, "DATA_DIR", tmp_path)
        # Insert a registered folder pointing at a path that doesn't exist
        with database.get_db(folders_db) as conn:
            conn.execute(
                "INSERT INTO ingest_folders (label, host_path, container_path) VALUES (?, ?, ?)",
                ("ghost", "/Users/me/ghost", "/host/Users/me/ghost"),
            )
        paths = folders_svc.all_data_paths()
        # Inaccessible folder is skipped, DATA_DIR still included
        assert all("ghost" not in str(p) for p in paths)
