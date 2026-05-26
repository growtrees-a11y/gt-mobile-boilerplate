"""FastAPI application — telemetry ingest endpoint."""

import asyncio
import logging
import uuid
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import celery_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Mobile Telemetry API",
    description="High-availability telemetry ingest for mobile apps",
    version="0.1.0",
)


# ── Models ──────────────────────────────────────────────────────────────


class TelemetryEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str
    event_type: str
    payload: dict = Field(default_factory=dict)
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )
    session_id: str | None = None
    app_version: str | None = None
    os: str | None = None


class TelemetryBatch(BaseModel):
    """Accept a burst of events — used for offline queue dumps."""

    events: list[TelemetryEvent] = Field(..., min_length=1, max_length=500)


class IngestResponse(BaseModel):
    accepted: int
    queued: int
    batch_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


# ── Endpoints ──────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.post(
    "/telemetry",
    response_model=IngestResponse,
    status_code=202,
)
async def ingest(event: TelemetryEvent) -> IngestResponse:
    """Ingest a single telemetry event."""
    batch_id = str(uuid.uuid4())
    if celery_app.process_telemetry is not None:
        celery_app.process_telemetry.delay(event.model_dump())
    logger.info("Accepted event %s → queue", event.event_id)
    return IngestResponse(accepted=1, queued=1, batch_id=batch_id)


@app.post(
    "/telemetry/batch",
    response_model=IngestResponse,
    status_code=202,
)
async def ingest_batch(batch: TelemetryBatch) -> IngestResponse:
    """Ingest a batch of events (e.g. offline queue dump)."""
    batch_id = str(uuid.uuid4())
    if celery_app.process_telemetry is not None:
        for event in batch.events:
            celery_app.process_telemetry.delay(event.model_dump())
    logger.info("Accepted batch %d events → queue", len(batch.events))
    return IngestResponse(
        accepted=len(batch.events),
        queued=len(batch.events),
        batch_id=batch_id,
    )


@app.post("/telemetry/flush", status_code=202)
async def flush_queue_endpoint(request: Request) -> JSONResponse:
    """Manually trigger a queue flush (drain Redis buffer)."""
    if celery_app.flush_queue is not None:
        celery_app.flush_queue.delay()
    return JSONResponse(
        status_code=202,
        content={"status": "flush_requested"},
    )


# ── Startup ─────────────────────────────────────────────────────────────


@app.on_event("startup")
async def on_startup():
    logger.info("Telemetry API started — ingest ready")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, workers=4)
