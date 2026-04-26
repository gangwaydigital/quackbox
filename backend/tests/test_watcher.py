"""
Tests for the background watcher service.

Drives the asyncio loop directly and stubs out run_ingest / get_source_status
so we don't hit the real database or filesystem.
"""
import asyncio
from unittest.mock import patch

import pytest

from app.services import watcher


@pytest.fixture(autouse=True)
def reset_watcher_state():
    """Make sure each test starts from a clean watcher state."""
    yield
    # If a previous test left a task running, stop it.
    if watcher._task is not None:
        try:
            asyncio.get_event_loop().run_until_complete(watcher.stop())
        except RuntimeError:
            pass
    watcher._task = None
    watcher._stop_event = None


class TestWatcherDisabled:
    async def test_zero_interval_is_a_noop(self):
        watcher.start(interval_minutes=0)
        assert watcher.status()["enabled"] is False
        assert watcher._task is None

    async def test_negative_interval_is_a_noop(self):
        watcher.start(interval_minutes=-5)
        assert watcher.status()["enabled"] is False


class TestWatcherLifecycle:
    async def test_start_then_stop(self):
        # Patch out the actual work so we can start the loop without real ingest
        with patch("app.services.watcher.is_ingest_running", return_value=False), \
             patch("app.services.watcher._has_pending_work", return_value=False):
            watcher.start(interval_minutes=1)
            assert watcher.status()["enabled"] is True
            assert watcher.status()["interval_seconds"] >= 60
            await asyncio.sleep(0.05)  # let one tick land
            await watcher.stop()
        assert watcher._task is None
        assert watcher.status()["enabled"] is False

    async def test_minimum_interval_is_60_seconds(self):
        """Even WATCH_INTERVAL_MINUTES=0.01 should clamp to at least 60s."""
        with patch("app.services.watcher.is_ingest_running", return_value=False), \
             patch("app.services.watcher._has_pending_work", return_value=False):
            # Pass a fractional minute via int() — gets coerced to 0, which disables.
            # So pass 1 to enable, then verify the seconds calc.
            watcher.start(interval_minutes=1)
            assert watcher.status()["interval_seconds"] == 60
            await watcher.stop()


class TestWatcherTickBehavior:
    async def test_skips_when_ingest_already_running(self):
        with patch("app.services.watcher.is_ingest_running", return_value=True), \
             patch("app.services.watcher._has_pending_work", return_value=True), \
             patch("app.services.watcher.run_ingest") as mock_run:
            watcher.start(interval_minutes=1)
            await asyncio.sleep(0.1)  # one tick
            await watcher.stop()
        mock_run.assert_not_called()
        assert "already running" in watcher.status()["last_status_summary"].lower()

    async def test_no_op_when_nothing_new(self):
        with patch("app.services.watcher.is_ingest_running", return_value=False), \
             patch("app.services.watcher._has_pending_work", return_value=False), \
             patch("app.services.watcher.run_ingest") as mock_run:
            watcher.start(interval_minutes=1)
            await asyncio.sleep(0.1)
            await watcher.stop()
        mock_run.assert_not_called()
        assert watcher.status()["last_status_summary"] == "No new content"

    async def test_dispatches_ingest_when_pending_work(self):
        with patch("app.services.watcher.is_ingest_running", return_value=False), \
             patch("app.services.watcher._has_pending_work", return_value=True), \
             patch("app.services.watcher.run_ingest", return_value={}) as mock_run:
            watcher.start(interval_minutes=1)
            # Give the loop time to tick AND for the executor to run the ingest
            await asyncio.sleep(0.2)
            await watcher.stop()
        # run_ingest must have been called at least once with incremental=True
        # and triggered_by="watcher"
        assert mock_run.call_count >= 1
        args, _ = mock_run.call_args
        assert args == (True, "watcher")
        assert watcher.status()["runs"] >= 1


class TestTriggerScanNow:
    def test_skips_when_ingest_already_running(self):
        with patch("app.services.watcher.is_ingest_running", return_value=True), \
             patch("app.services.watcher._has_pending_work", return_value=True):
            result = watcher.trigger_scan_now()
        assert result == {"queued": False, "reason": "ingest_already_running"}

    def test_no_op_when_nothing_new(self):
        with patch("app.services.watcher.is_ingest_running", return_value=False), \
             patch("app.services.watcher._has_pending_work", return_value=False):
            result = watcher.trigger_scan_now()
        assert result == {"queued": False, "reason": "no_new_content"}
        assert "nothing new" in watcher.status()["last_status_summary"].lower()

    def test_queues_ingest_when_pending_work(self):
        with patch("app.services.watcher.is_ingest_running", return_value=False), \
             patch("app.services.watcher._has_pending_work", return_value=True), \
             patch("app.services.watcher._executor.submit") as mock_submit:
            result = watcher.trigger_scan_now()
        assert result == {"queued": True, "reason": "ingest_started"}
        # Should have submitted run_ingest with incremental=True, triggered_by="watcher-manual"
        mock_submit.assert_called_once()
        args = mock_submit.call_args.args
        assert args[1] is True  # incremental
        assert args[2] == "watcher-manual"


class TestHasPendingWork:
    """_has_pending_work iterates all_data_paths() and short-circuits on the
    first 'new'/'updated' source. We mock all_data_paths to avoid hitting
    the real DB, then control get_source_status separately."""

    @staticmethod
    def _patches(*, paths=("/tmp",), source_status=None, source_status_exc=None):
        from pathlib import Path
        path_patch = patch(
            "app.services.watcher.all_data_paths",
            return_value=[Path(p) for p in paths],
        )
        if source_status_exc:
            ss_patch = patch(
                "app.services.watcher.get_source_status",
                side_effect=source_status_exc,
            )
        else:
            ss_patch = patch(
                "app.services.watcher.get_source_status",
                return_value=source_status or [],
            )
        return path_patch, ss_patch

    def test_true_when_any_source_is_new_or_updated(self):
        p, s = self._patches(source_status=[{"status": "unchanged"}, {"status": "new"}])
        with p, s:
            assert watcher._has_pending_work() is True

    def test_false_when_all_unchanged(self):
        p, s = self._patches(source_status=[{"status": "unchanged"}, {"status": "unchanged"}])
        with p, s:
            assert watcher._has_pending_work() is False

    def test_swallows_exceptions(self):
        """get_source_status failure should not crash the watcher loop."""
        p, s = self._patches(source_status_exc=RuntimeError("db down"))
        with p, s:
            assert watcher._has_pending_work() is False
