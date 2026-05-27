"""Tests for AWS Lambda handler — serverless telemetry ingest."""

import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lambda_handler import lambda_handler, _extract_events, _api_response


class TestLambdaHandler:
    """Test Lambda handler for API Gateway and SQS events."""

    def test_empty_event(self):
        """Empty event returns 0 accepted."""
        result = lambda_handler({})
        assert result["statusCode"] == 200
        assert result["body"] == json.dumps({"accepted": 0, "message": "No events to process"})

    def test_single_event_post(self):
        """Single event via API Gateway POST."""
        event = {
            "body": json.dumps({
                "device_id": "test-device-1",
                "event_type": "screen_view",
                "payload": {"screen": "Home"},
            }),
        }
        result = lambda_handler(event)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["accepted"] == 1
        assert body["elapsed_seconds"] >= 0

    def test_batch_events_post(self):
        """Batch events via API Gateway POST."""
        events = [
            {"device_id": "d1", "event_type": "app_start", "payload": {}},
            {"device_id": "d2", "event_type": "screen_view", "payload": {"screen": "Settings"}},
            {"device_id": "d3", "event_type": "button_click", "payload": {"button": "save"}},
        ]
        event = {"body": json.dumps({"events": events})}
        result = lambda_handler(event)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["accepted"] == 3

    def test_sqs_batch_format(self):
        """SQS batch with multiple records."""
        events = [
            {"device_id": "d1", "event_type": "app_start", "payload": {}},
            {"device_id": "d2", "event_type": "error", "payload": {"error": "crash"}},
        ]
        event = {
            "Records": [
                {"body": json.dumps({"events": events})},
            ],
        }
        result = lambda_handler(event)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["accepted"] == 2

    def test_invalid_json_body(self):
        """Invalid JSON body returns 0 accepted."""
        event = {"body": "not json at all"}
        result = lambda_handler(event)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["accepted"] == 0

    def test_mixed_sqs_records(self):
        """SQS batch with single events (not batch format)."""
        event = {
            "Records": [
                {"body": json.dumps({"device_id": "d1", "event_type": "test", "payload": {}})},
                {"body": json.dumps({"device_id": "d2", "event_type": "test", "payload": {}})},
            ],
        }
        result = lambda_handler(event)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["accepted"] == 2

    def test_enriched_metadata(self):
        """Events get enriched with metadata."""
        event = {
            "body": json.dumps({
                "device_id": "d1",
                "event_type": "test",
                "payload": {},
            }),
        }
        result = lambda_handler(event)
        assert result["statusCode"] == 200

    def test_large_batch(self):
        """Large batch of events (500+)."""
        events = [
            {"device_id": f"d{i}", "event_type": "test", "payload": {"i": i}}
            for i in range(500)
        ]
        event = {"body": json.dumps({"events": events})}
        result = lambda_handler(event)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["accepted"] == 500

    def test_api_response_format(self):
        """API response has correct format."""
        response = _api_response(200, {"status": "ok"})
        assert response["statusCode"] == 200
        assert response["headers"]["Content-Type"] == "application/json"
        assert "status" in json.loads(response["body"])


class TestExtractEvents:
    """Test event extraction from various input formats."""

    def test_extract_single_event(self):
        """Single event from API Gateway."""
        event = {"body": json.dumps({"device_id": "d1", "event_type": "test", "payload": {}})}
        events = _extract_events(event)
        assert len(events) == 1
        assert events[0]["device_id"] == "d1"

    def test_extract_batch_events(self):
        """Batch events from API Gateway."""
        events_data = [
            {"device_id": f"d{i}", "event_type": "test", "payload": {}}
            for i in range(3)
        ]
        event = {"body": json.dumps({"events": events_data})}
        events = _extract_events(event)
        assert len(events) == 3

    def test_extract_sqs_batch(self):
        """SQS batch format."""
        event = {
            "Records": [
                {"body": json.dumps({"events": [{"device_id": "d1", "event_type": "test", "payload": {}}]})},
            ],
        }
        events = _extract_events(event)
        assert len(events) == 1

    def test_extract_sqs_single(self):
        """SQS single event (not batch)."""
        event = {
            "Records": [
                {"body": json.dumps({"device_id": "d1", "event_type": "test", "payload": {}})},
            ],
        }
        events = _extract_events(event)
        assert len(events) == 1

    def test_extract_empty(self):
        """Empty event returns empty list."""
        events = _extract_events({})
        assert events == []

    def test_extract_invalid_json(self):
        """Invalid JSON returns empty list."""
        events = _extract_events({"body": "not json"})
        assert events == []

    def test_extract_missing_fields(self):
        """Events missing required fields still extracted."""
        event = {"body": json.dumps({"not_a_real_event": True})}
        events = _extract_events(event)
        assert events == []  # no device_id means not a valid event

    def test_enrich_with_metadata(self):
        """Events get enriched with metadata."""
        event = {"body": json.dumps({"device_id": "d1", "event_type": "test", "payload": {}})}
        events = _extract_events(event)
        assert events[0]["event_id"] is not None
        assert events[0]["ingested_at"] is not None
        assert events[0]["source"] == "lambda"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
