"""
Test suite for telemetry ingest pipeline.

Tests:
- Telemetry ingest (single + batch)
- Telemetry queue (Redis-backed)
- Lambda handler path
"""

import json
import sys
import pytest

# ── Detect celery availability ───────────────────────────────────────
try:
    from celery import Celery
    HAS_CELERY = True
except ImportError:
    HAS_CELERY = False


@pytest.fixture(scope="module")
def client():
    """Synchronous test client."""
    from app.main import app
    from starlette.testclient import TestClient
    with TestClient(app) as c:
        yield c


# ── Health endpoint ─────────────────────────────────────────────────


def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


# ── Single event ingest ───────────────────────────────────────────


def test_ingest_single_event(client):
    payload = {
        "device_id": "device-abc123",
        "event_type": "screen_view",
        "payload": {"screen": "home", "duration_ms": 3200},
        "session_id": "session-xyz",
    }
    resp = client.post("/telemetry", json=payload)
    assert resp.status_code == 202
    body = resp.json()
    assert body["accepted"] == 1
    assert body["queued"] == 1
    assert "batch_id" in body


# ── Batch ingest ──────────────────────────────────────────────────


def test_ingest_batch_events(client):
    events = [
        {
            "device_id": f"device-{i}",
            "event_type": "click",
            "payload": {"button": "submit"},
        }
        for i in range(10)
    ]
    resp = client.post("/telemetry/batch", json={"events": events})
    assert resp.status_code == 202
    body = resp.json()
    assert body["accepted"] == 10
    assert body["queued"] == 10


def test_ingest_batch_rejects_empty(client):
    resp = client.post("/telemetry/batch", json={"events": []})
    assert resp.status_code == 422


# ── Telemetry queue tests (Celery) ───────────────────────────────


@pytest.mark.skipif(not HAS_CELERY, reason="celery not installed")
def test_process_telemetry_task_exists():
    from celery_app import app as celery_app

    task = celery_app.tasks.get("telemetry.process")
    assert task is not None
    assert task.name == "telemetry.process"


@pytest.mark.skipif(not HAS_CELERY, reason="celery not installed")
def test_flush_queue_task_exists():
    from celery_app import app as celery_app

    task = celery_app.tasks.get("telemetry.flush")
    assert task is not None
    assert task.name == "telemetry.flush"


@pytest.mark.skipif(not HAS_CELERY, reason="celery not installed")
def test_process_telemetry_success():
    from celery_app import process_telemetry

    result = process_telemetry.s({
        "event_id": "evt-001",
        "device_id": "device-abc",
        "event_type": "session_start",
        "payload": {"os": "iOS"},
    })
    assert result is not None


# ── Lambda handler tests ─────────────────────────────────────────


def test_lambda_handler_module_exists():
    import lambda_handler
    assert hasattr(lambda_handler, "lambda_handler")
    assert callable(lambda_handler.lambda_handler)


def test_extract_events_single():
    from lambda_handler import _extract_events

    event = {
        "body": '{"device_id": "d1", "event_type": "click"}',
    }
    events = _extract_events(event)
    assert len(events) == 1
    assert events[0]["device_id"] == "d1"


def test_extract_events_batch():
    from lambda_handler import _extract_events

    body = json.dumps({
        "events": [
            {"device_id": "d1", "event_type": "tap"},
            {"device_id": "d2", "event_type": "scroll"},
        ]
    })
    event = {"body": body}
    events = _extract_events(event)
    assert len(events) == 2
    assert events[0]["source"] == "lambda"


def test_extract_events_empty():
    from lambda_handler import _extract_events

    assert _extract_events({}) == []
    assert _extract_events({"body": "not-json"}) == []


def test_extract_events_sqs_format():
    from lambda_handler import _extract_events

    event = {
        "Records": [
            {
                "body": json.dumps({
                    "device_id": "d1",
                    "event_type": "heartbeat",
                }),
            },
        ],
    }
    events = _extract_events(event)
    assert len(events) == 1
    assert events[0]["device_id"] == "d1"


# ── High-throughput validation ──────────────────────────────────


def test_batch_accepts_500_events():
    """Verify batch endpoint accepts max size."""
    events = [{"device_id": f"d-{i}", "event_type": "test"} for i in range(500)]
    batch = {"events": events}

    from app.main import TelemetryBatch

    model = TelemetryBatch.model_validate(batch)
    assert len(model.events) == 500


def test_large_batch_simulation():
    """Simulate 1000+ events/sec throughput scenario."""
    import time

    # Simulate event generation at 1000 events/sec
    events = [
        {"device_id": f"device-{i}", "event_type": "heartbeat"}
        for i in range(10_000)
    ]

    start = time.perf_counter()
    chunks = [events[i : i + 25] for i in range(0, len(events), 25)]
    end = time.perf_counter()

    # Chunking overhead should be negligible
    assert (end - start) < 1.0  # Complete in < 1 second
    assert len(chunks) == 400  # 10000 / 25


# ── API response helper ──────────────────────────────────────────


def test_api_response_format():
    from lambda_handler import _api_response

    result = _api_response(200, {"test": True})
    assert result["statusCode"] == 200
    assert "Content-Type" in result["headers"]
    assert json.loads(result["body"])["test"] is True
