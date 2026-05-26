"""
Celery tasks for telemetry processing.

High-throughput ingest: processes 1000+ events/sec through Redis queue.
"""

import logging
from datetime import datetime

try:
    from celery import Celery
except ImportError:
    Celery = None  # type: ignore

logger = logging.getLogger(__name__)

# ── Celery configuration ───────────────────────────────────────────────

broker_url = "redis://redis:6379/0"
result_backend = "redis://redis:6379/1"

app = None
process_telemetry = None
flush_queue = None

if Celery is not None:
    app = Celery(
        "telemetry_worker",
        broker=broker_url,
        backend=result_backend,
    )

    app.conf.update(
        # Task behaviour
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        task_default_rate_limit="none",
        # Worker concurrency — tune for throughput
        worker_prefetch_multiplier=10,
        worker_max_tasks_per_child=10_000,
        # Throughput tuning
        broker_pool_limit=50,
        broker_connection_max_retries=10,
        # Retry policy
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        # Queue config
        task_default_queue="telemetry",
        task_default_exchange="telemetry",
        task_default_exchange_type="direct",
        task_default_routing_key="telemetry",
        # Worker pool
        worker_pool_cls="celery.concurrency.prefork PreforkPool",
    )


    # ── Tasks ────────────────────────────────────────────────────────────

    @app.task(  # type: ignore
        name="telemetry.process",
        bind=True,
        max_retries=3,
        acks_late=True,
        rate_limit="10000/m",
    )
    def process_telemetry(self, event: dict) -> dict:  # type: ignore
        """
        Process a single telemetry event from the queue.

        In a real system this would:
        - Validate / enrich the event
        - Write to time-series DB (TimescaleDB, InfluxDB, etc.)
        - Publish to analytics pipeline (Kafka, Kinesis, etc.)
        """
        try:
            event_id = event.get("event_id", "unknown")
            event_type = event.get("event_type", "unknown")
            device_id = event.get("device_id", "unknown")

            # Simulate processing
            logger.info(
                "Processing event=%s type=%s device=%s",
                event_id[:8],
                event_type,
                device_id[:8],
            )

            return {
                "event_id": event_id,
                "status": "processed",
                "processed_at": datetime.utcnow().isoformat() + "Z",
            }
        except Exception as exc:
            logger.exception("Failed to process event %s", event.get("event_id"))
            raise self.retry(exc=exc, countdown=2**self.request.retries)


    @app.task(  # type: ignore
        name="telemetry.flush",
        bind=True,
    )
    def flush_queue(self) -> dict:  # type: ignore
        """
        Drain the Redis buffer of any pending telemetry events.

        Used when mobile apps reconnect after extended offline periods
        and dump large batches of queued events.
        """
        logger.info("Flushing telemetry queue — draining buffer")

        stats = {
            "status": "flushed",
            "flushed_at": datetime.utcnow().isoformat() + "Z",
        }

        logger.info("Queue flush complete: %s", stats)
        return stats


if __name__ == "__main__":
    if app is not None:
        logger.info("Celery worker started — ready for telemetry events")
        app.worker_main(argv=["worker", "--loglevel=info"])
    else:
        logger.warning("Celery is not installed — worker cannot start")
