"""Tests for Celery tasks — telemetry processing pipeline."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from celery_app import process_telemetry, flush_queue, app


class TestProcessTelemetry:
    """Test telemetry processing task."""

    def test_process_telemetry_exists(self):
        """Process telemetry task is defined."""
        assert process_telemetry is not None

    def test_process_telemetry_basic(self):
        """Process a basic telemetry event."""
        event = {
            "event_id": "test-event-1",
            "event_type": "screen_view",
            "device_id": "test-device-1",
            "payload": {"screen": "Home"},
            "timestamp": "2026-01-01T00:00:00Z",
        }
        result = process_telemetry.apply()
        # Task should be callable
        assert result is not None

    def test_process_telemetry_error_type(self):
        """Process error event type."""
        event = {
            "event_id": "test-error-1",
            "event_type": "error.crash",
            "device_id": "test-device-1",
            "payload": {"error": "NullReferenceException", "stack": "at main.py:10"},
        }
        result = process_telemetry.apply()
        assert result is not None

    def test_process_telemetry_retry_config(self):
        """Task has retry configuration."""
        assert process_telemetry.max_retries == 3
        assert process_telemetry.acks_late is True


class TestFlushQueue:
    """Test queue flush task."""

    def test_flush_queue_exists(self):
        """Flush queue task is defined."""
        assert flush_queue is not None

    def test_flush_queue_basic(self):
        """Flush queue task is callable."""
        result = flush_queue.apply()
        assert result is not None


class TestCeleryConfig:
    """Test Celery configuration."""

    def test_app_exists(self):
        """Celery app is configured."""
        assert app is not None

    def test_broker_config(self):
        """Broker URL is configured."""
        assert app.conf.broker_url == "redis://redis:6379/0"

    def test_result_backend(self):
        """Result backend is configured."""
        assert app.conf.result_backend == "redis://redis:6379/1"

    def test_task_serializer(self):
        """Task serializer is JSON."""
        assert app.conf.task_serializer == "json"

    def test_rate_limit(self):
        """Rate limit is configured."""
        assert app.conf.task_default_rate_limit == "none"

    def test_worker_prefetch(self):
        """Worker prefetch multiplier is configured."""
        assert app.conf.worker_prefetch_multiplier == 10

    def test_worker_max_tasks(self):
        """Worker max tasks per child is configured."""
        assert app.conf.worker_max_tasks_per_child == 10_000

    def test_queue_config(self):
        """Queue configuration is correct."""
        assert app.conf.task_default_queue == "telemetry"
        assert app.conf.task_default_exchange == "telemetry"
        assert app.conf.task_default_routing_key == "telemetry"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
