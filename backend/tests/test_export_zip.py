"""
Tests for the bulk attachment archive endpoint helpers.

The HTTP endpoint exercises FastAPI plumbing we don't unit-test, but the
zip-name builder and the candidate selection SQL deserve coverage.
"""
import json
import zipfile
import io

import pytest

from app import database
from app.routers import export as export_router


# ── _safe_zip_name ─────────────────────────────────────────────────────────


class TestSafeZipName:
    def test_groups_by_year_month_folder(self):
        name = export_router._safe_zip_name("2024-01-15T10:00:00", 42, "report.pdf")
        assert name.startswith("2024-01/")

    def test_includes_email_id_for_disambiguation(self):
        name = export_router._safe_zip_name("2024-01-15", 42, "report.pdf")
        assert "__42__" in name

    def test_handles_missing_date(self):
        name = export_router._safe_zip_name(None, 42, "report.pdf")
        assert name.startswith("unknown/")
        assert "__42__" in name

    def test_strips_path_traversal_and_slashes(self):
        name = export_router._safe_zip_name("2024-01-15", 7, "../../../etc/passwd")
        assert "/etc/" not in name
        assert ".." not in name.split("/")[-1]  # may have folder slashes
        # The filename portion should be sanitized
        filename_part = name.split("__")[-1]
        assert "/" not in filename_part

    def test_sanitizes_unsafe_chars_in_filename(self):
        name = export_router._safe_zip_name("2024-01-15", 7, 'weird:file*name?.pdf')
        filename_part = name.split("__")[-1]
        assert ":" not in filename_part
        assert "*" not in filename_part
        assert "?" not in filename_part

    def test_empty_filename_falls_back_to_attachment(self):
        name = export_router._safe_zip_name("2024-01-15", 7, "")
        assert "attachment" in name


# ── _select_attachments_for_zip ────────────────────────────────────────────


@pytest.fixture
def export_db(tmp_path, monkeypatch):
    """Initialize a DB with a few attachment-bearing emails and patch the
    export router to read it."""
    db_path = tmp_path / "export-test.db"
    database.init_db(db_path)
    real_get_db = database.get_db

    def get_db_override(p=db_path):
        return real_get_db(p)
    monkeypatch.setattr(export_router, "get_db", get_db_override)

    samples = [
        # (id, subject, sender_email, date_sent, date_timestamp, mbox_source, attachment_names)
        (None, "Q1 plan", "alice@x.com", "2024-01-15", 1705305600.0, "Inbox",
         json.dumps(["plan.pdf", "smime.p7s"])),
        (None, "Vacation pics", "bob@x.com", "2024-02-10", 1707523200.0, "Family",
         json.dumps(["IMG_1.JPG", "IMG_2.JPG"])),
        (None, "No attachments here", "carol@x.com", "2024-03-01", 1709251200.0, "Inbox",
         None),
    ]
    with database.get_db(db_path) as conn:
        for s in samples:
            has_attach = 0 if s[6] is None else 1
            conn.execute(
                "INSERT INTO emails (subject, sender_email, date_sent, date_timestamp, mbox_source, has_attachments, attachment_names) VALUES (?,?,?,?,?,?,?)",
                (s[1], s[2], s[3], s[4], s[5], has_attach, s[6]),
            )
    return db_path


class TestSelectAttachmentsForZip:
    def test_returns_all_real_attachments_no_filter(self, export_db):
        rows = export_router._select_attachments_for_zip(
            search=None, sender_email=None, mbox_source=None, limit=100,
        )
        # plan.pdf + IMG_1.JPG + IMG_2.JPG, smime.p7s excluded
        names = sorted(r["filename"] for r in rows)
        assert names == ["IMG_1.JPG", "IMG_2.JPG", "plan.pdf"]

    def test_filters_smime_noise_even_without_other_filters(self, export_db):
        rows = export_router._select_attachments_for_zip(
            search=None, sender_email=None, mbox_source=None, limit=100,
        )
        assert all(r["filename"].lower() not in ("smime.p7s", "smime.p7m") for r in rows)

    def test_search_filters_by_filename(self, export_db):
        rows = export_router._select_attachments_for_zip(
            search="img", sender_email=None, mbox_source=None, limit=100,
        )
        assert len(rows) == 2
        assert all("IMG" in r["filename"] for r in rows)

    def test_search_also_matches_subject(self, export_db):
        rows = export_router._select_attachments_for_zip(
            search="vacation", sender_email=None, mbox_source=None, limit=100,
        )
        assert len(rows) == 2  # both IMG_*.JPG via the "Vacation pics" subject

    def test_filter_by_sender(self, export_db):
        rows = export_router._select_attachments_for_zip(
            search=None, sender_email="alice@x.com", mbox_source=None, limit=100,
        )
        assert len(rows) == 1
        assert rows[0]["filename"] == "plan.pdf"

    def test_filter_by_mbox_source(self, export_db):
        rows = export_router._select_attachments_for_zip(
            search=None, sender_email=None, mbox_source="Family", limit=100,
        )
        assert len(rows) == 2

    def test_limit_caps_results(self, export_db):
        rows = export_router._select_attachments_for_zip(
            search=None, sender_email=None, mbox_source=None, limit=2,
        )
        assert len(rows) == 2


# ── End-to-end zip via TestClient ──────────────────────────────────────────


class TestZipEndpoint:
    def test_zip_returns_404_when_no_matches(self, export_db):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(export_router.router)
        client = TestClient(app)
        # nothing matches "zzz"
        r = client.get("/api/export/attachments.zip?search=zzz")
        assert r.status_code == 404

    def test_zip_404s_when_filters_match_nothing(self, export_db):
        """Mirror the previous test but exercise the 404 path explicitly."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(export_router.router)
        client = TestClient(app)
        r = client.get("/api/export/attachments.zip?sender_email=ghost@nope.com")
        assert r.status_code == 404
        assert "No attachments" in r.json()["detail"]
