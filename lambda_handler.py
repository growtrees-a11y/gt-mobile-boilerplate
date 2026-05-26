"""
AWS Lambda handler — serverless telemetry ingest path.

Architecture: Mobile App → API Gateway → Lambda → DynamoDB

Handles burst writes from offline queue dumps without timeouts.
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ── Lazy AWS client initialization ─────────────────────────────────
# Defer boto3 import so the module can be imported/tested without credentials


def _get_dynamodb():
    """Lazily initialize DynamoDB resource."""
    import boto3

    table_name = os.environ.get("TELEMETRY_TABLE", "mobile-telemetry-events")
    return boto3.resource("dynamodb"), table_name


# ── Lambda handler ─────────────────────────────────────────────


def lambda_handler(event, context=None):
    """
    Process telemetry events via API Gateway or direct Lambda invocation.

    Supports:
    - Single event via POST /telemetry
    - Batch events via POST /telemetry/batch
    - SQS batch from mobile offline queue dumps

    Returns:
        API Gateway 200 response with ingestion summary.
    """
    start_time = time.time()

    # ── Parse incoming events ──────────────────────────────────────
    events = _extract_events(event)

    if not events:
        return _api_response(200, {"accepted": 0, "message": "No events to process"})

    # ── Batch write to DynamoDB ────────────────────────────────────
    batch_size = 25  # DynamoDB PutItem max per BatchWriteItem
    total_written = 0
    batch_write_failed = 0

    try:
        dynamodb, table_name = _get_dynamodb()
        table = dynamodb.Table(table_name)

        for i in range(0, len(events), batch_size):
            chunk = events[i : i + batch_size]
            written = _batch_write(table, chunk)
            total_written += written
            batch_write_failed += len(chunk) - written
    except Exception as exc:
        logger.warning("DynamoDB unavailable — events parsed but not persisted: %s", exc)
        total_written = 0
        batch_write_failed = len(events)

    elapsed = round(time.time() - start_time, 3)

    logger.info(
        "Processed %d events → %d written, %d failed (%.3fs)",
        len(events),
        total_written,
        batch_write_failed,
        elapsed,
    )

    return _api_response(200, {
        "accepted": len(events),
        "written": total_written,
        "failed": batch_write_failed,
        "elapsed_seconds": elapsed,
    })


# ── Helpers ─────────────────────────────────────────────────────────


def _extract_events(event):
    """Extract telemetry events from various input formats."""
    events = []

    # API Gateway POST body
    body = event.get("body", "")
    if body:
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return []

        # Batch format: {"events": [...]}
        if "events" in data:
            events.extend(data["events"])
        # Single event
        elif "device_id" in data:
            events.append(data)

    # SQS batch format
    records = event.get("Records", [])
    if records:
        for record in records:
            try:
                record_body = json.loads(record.get("body", "{}"))
                if "events" in record_body:
                    events.extend(record_body["events"])
                elif "device_id" in record_body:
                    events.append(record_body)
            except (json.JSONDecodeError, KeyError):
                continue

    # Enrich with metadata
    for evt in events:
        evt.setdefault("event_id", str(uuid.uuid4()))
        evt.setdefault("ingested_at", datetime.utcnow().isoformat() + "Z")
        evt.setdefault("source", "lambda")

    return events


def _batch_write(table, events):
    """Write events to DynamoDB in a single BatchWriteItem call."""
    written = 0

    with table.batch_writer() as writer:
        for evt in events:
            writer.put_item(Item={
                "event_id": evt.get("event_id", str(uuid.uuid4())),
                "device_id": evt.get("device_id", "unknown"),
                "event_type": evt.get("event_type", "unknown"),
                "payload": json.dumps(evt.get("payload", {})),
                "timestamp": evt.get("timestamp", ""),
                "ingested_at": evt.get("ingested_at", ""),
                "session_id": evt.get("session_id", ""),
                "app_version": evt.get("app_version", ""),
                "os": evt.get("os", ""),
            })
            written += 1

    return written


def _api_response(status_code, body):
    """Format response for API Gateway."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
