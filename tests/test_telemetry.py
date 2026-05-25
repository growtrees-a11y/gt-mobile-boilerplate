"""
PROJ-07 Phase 4 – Telemetry Queue Tests

Covers:
  • log_event / log_error enqueueing
  • queue_size / is_empty
  • flush success / no-op / already-flushing guard
  • MAX_QUEUE eviction
"""
import pytest
import asyncio
from main import TelemetryQueue


def run(coro):
    """Run an async coroutine compatible with Python 3.14."""
    return asyncio.run(coro)


# ── tests ───────────────────────────────────────────────────────────────────

class TestLogEvent:
    def test_single_event(self):
        tq = TelemetryQueue()
        tq.log_event("test", {"key": "value"})
        assert tq.queue_size == 1
        assert tq.is_empty is False

    def test_multiple_events(self):
        tq = TelemetryQueue()
        for i in range(5):
            tq.log_event("tick", {"i": i})
        assert tq.queue_size == 5

    def test_log_error(self):
        tq = TelemetryQueue()
        tq.log_error("oops", "traceback here")
        assert tq.queue_size == 1
        assert tq._queue[0]["event_type"] == "error.oops"
        assert tq._queue[0]["payload"]["traceback"] == "traceback here"

    def test_timestamp_is_iso(self):
        tq = TelemetryQueue()
        tq.log_event("x", {})
        ts = tq._queue[0]["timestamp"]
        assert isinstance(ts, str)
        assert len(ts) > 10


class TestMaxQueue:
    def test_eviction_at_cap(self):
        tq = TelemetryQueue()
        tq.MAX_QUEUE = 3
        tq.log_event("a", {})
        tq.log_event("b", {})
        tq.log_event("c", {})
        tq.log_event("d", {})  # should evict 'a'
        assert tq.queue_size == 3
        assert tq._queue[0]["event_type"] == "b"

    def test_default_cap_is_256(self):
        tq = TelemetryQueue()
        assert tq.MAX_QUEUE == 256


class TestFlush:
    def test_flush_clears(self):
        tq = TelemetryQueue()
        tq.log_event("e", {})
        assert run(tq.flush()) is True
        assert tq.queue_size == 0

    def test_flush_empty_is_noop(self):
        tq = TelemetryQueue()
        assert run(tq.flush()) is False

    def test_flush_idempotent(self):
        tq = TelemetryQueue()
        tq.log_event("e", {})
        assert run(tq.flush()) is True
        assert run(tq.flush()) is False

    def test_flush_attempts_counter(self):
        tq = TelemetryQueue()
        assert tq.flush_attempts == 0
        tq.log_event("e", {})
        run(tq.flush())
        assert tq.flush_attempts == 1
        # flush on empty returns early, no increment
        run(tq.flush())
        assert tq.flush_attempts == 1


class TestIsFlushingGuard:
    """The flush method returns False when already flushing."""
    def test_concurrent_flush_returns_false(self):
        tq = TelemetryQueue()
        tq.log_event("e", {})
        tq._is_flushing = True
        assert run(tq.flush()) is False
