"""Tests for the embedding throughput tracker used by the Topics router."""
import time
from unittest.mock import patch

import pytest

from app.routers.topics import _RateTracker, _format_eta


class TestRateTracker:
    def test_returns_none_with_one_sample(self):
        t = _RateTracker(window_seconds=60)
        t.record(0)
        assert t.rate_per_second() is None
        assert t.eta_seconds(100) is None

    def test_computes_rate_with_two_samples(self):
        t = _RateTracker(window_seconds=60)
        with patch("app.routers.topics.time.time", side_effect=[100.0, 110.0]):
            t.record(0)
            t.record(50)
        # 50 items over 10 seconds = 5/sec
        assert t.rate_per_second() == 5.0

    def test_eta_uses_remaining_over_rate(self):
        t = _RateTracker(window_seconds=60)
        with patch("app.routers.topics.time.time", side_effect=[100.0, 110.0]):
            t.record(0)
            t.record(50)
        # 5/sec, 1000 - 50 = 950 remaining → 190 seconds
        assert t.eta_seconds(1000) == 190

    def test_eta_returns_zero_when_done(self):
        t = _RateTracker(window_seconds=60)
        with patch("app.routers.topics.time.time", side_effect=[100.0, 110.0]):
            t.record(0)
            t.record(100)
        assert t.eta_seconds(100) == 0

    def test_window_drops_old_samples(self):
        """Samples older than `window_seconds` are evicted on each record() so
        the rate reflects current throughput, not historical averages."""
        t = _RateTracker(window_seconds=10)
        # Push three records at three different mock-times. We patch as a
        # context manager that returns each value in sequence.
        # window=10s, times spaced so the first sample falls outside on the
        # third record() (third t=113, cutoff=103, first t=100 is evicted).
        times = iter([100.0, 105.0, 113.0])
        with patch("app.routers.topics.time.time", lambda: next(times)):
            t.record(0)
            t.record(50)
            t.record(100)
        # Window now holds [(105, 50), (113, 100)] → rate = 50/8 ≈ 6.25
        assert len(t.samples) == 2
        rate = t.rate_per_second()
        assert rate is not None
        assert 6.0 < rate < 7.0

    def test_zero_progress_returns_none(self):
        """If two samples have the same `done`, rate is undefined (not 0)."""
        t = _RateTracker(window_seconds=60)
        with patch("app.routers.topics.time.time", side_effect=[100.0, 110.0]):
            t.record(50)
            t.record(50)
        assert t.rate_per_second() is None
        assert t.eta_seconds(100) is None


class TestFormatEta:
    def test_none(self):
        assert _format_eta(None) == ""

    def test_seconds(self):
        assert _format_eta(45) == "~45s left"

    def test_minutes(self):
        assert _format_eta(180) == "~3m left"

    def test_hours_and_minutes(self):
        # 3700s = 1h 1m (60s remainder rounds down via integer division)
        assert _format_eta(3700) == "~1h 1m left"
