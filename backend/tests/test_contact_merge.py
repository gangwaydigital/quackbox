"""Tests for the contact-merge service — validates the error-status contract."""
import pytest

from app import database
from app.services import contact_merge


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """
    Initialize a fresh DB at a temp path and patch the contact_merge service
    to read/write it. The service binds `get_db` at import time, so we patch
    the symbol on the service module rather than on the database module.
    """
    db_path = tmp_path / "merge-test.db"
    database.init_db(db_path)
    real_get_db = database.get_db

    def get_db_override(p=db_path):
        return real_get_db(p)

    monkeypatch.setattr(contact_merge, "get_db", get_db_override)
    return db_path


def _seed(db_path):
    with database.get_db(db_path) as conn:
        conn.executemany(
            "INSERT INTO emails (sender_name, sender_email) VALUES (?, ?)",
            [
                ("Alice", "alice@example.com"),
                ("Alice", "alice.work@example.com"),
                ("Alice", "a@example.com"),
                ("Bob", "bob@example.com"),
            ],
        )


class TestMergeContacts:
    def test_happy_path_renames_secondary_rows(self, isolated_db):
        _seed(isolated_db)

        result = contact_merge.merge_contacts(
            "alice@example.com", ["alice.work@example.com"]
        )
        assert "error" not in result
        assert result["primary"] == "alice@example.com"
        assert result["merged"] == ["alice.work@example.com"]
        assert result["updated_records"] == 1

        with database.get_db(isolated_db) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM emails WHERE sender_email = ?",
                ("alice@example.com",),
            ).fetchone()[0]
        assert count == 2

    def test_missing_primary_returns_404(self, isolated_db):
        _seed(isolated_db)
        result = contact_merge.merge_contacts(
            "ghost@example.com", ["alice@example.com"]
        )
        assert result["error"]
        assert result["status"] == 404

    def test_missing_secondary_returns_404(self, isolated_db):
        _seed(isolated_db)
        result = contact_merge.merge_contacts(
            "alice@example.com", ["ghost@example.com"]
        )
        assert result["error"]
        assert result["status"] == 404
        assert "ghost@example.com" in result["error"]

    def test_only_self_target_returns_400(self, isolated_db):
        """Passing only the primary as a secondary leaves nothing to merge."""
        _seed(isolated_db)
        result = contact_merge.merge_contacts(
            "alice@example.com", ["alice@example.com"]
        )
        assert result["error"]
        assert result["status"] == 400

    def test_mixed_missing_secondary_aborts_before_any_update(self, isolated_db):
        """If any secondary is missing, no rows should be touched."""
        _seed(isolated_db)
        result = contact_merge.merge_contacts(
            "alice@example.com",
            ["alice.work@example.com", "ghost@example.com"],
        )
        assert result["status"] == 404

        with database.get_db(isolated_db) as conn:
            still_there = conn.execute(
                "SELECT COUNT(*) FROM emails WHERE sender_email = ?",
                ("alice.work@example.com",),
            ).fetchone()[0]
        assert still_there == 1
