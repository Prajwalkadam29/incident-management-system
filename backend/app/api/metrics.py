import time
import structlog
from fastapi import APIRouter, Response
from prometheus_client import (
    Counter, Gauge, Histogram,
    generate_latest, CONTENT_TYPE_LATEST,
    CollectorRegistry, multiprocess
)
from prometheus_client import (
    REGISTRY,
    Counter as PCounter,
    Gauge as PGauge,
    Histogram as PHistogram,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Observability"])

# ──────────────────────────────────────────
# Prometheus Metrics Definitions
# ──────────────────────────────────────────

# Total signals ingested (ever)
SIGNALS_INGESTED = PCounter(
    "ims_signals_ingested_total",
    "Total number of signals ingested",
    ["component_type", "severity"],
)

# Currently active (non-closed) incidents
ACTIVE_INCIDENTS = PGauge(
    "ims_active_incidents",
    "Number of active (non-closed) incidents",
    ["severity"],
)

# MTTR distribution in minutes
MTTR_HISTOGRAM = PHistogram(
    "ims_mttr_minutes",
    "Mean Time To Repair distribution in minutes",
    buckets=[5, 15, 30, 60, 120, 240, 480, 1440],
)

# HTTP request latency
REQUEST_LATENCY = PHistogram(
    "ims_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)

# Worker processing rate
WORKER_PROCESSED = PCounter(
    "ims_worker_signals_processed_total",
    "Total signals processed by worker",
    ["status"],  # success | error
)


# ──────────────────────────────────────────
# Helper — update gauges from DB
# ──────────────────────────────────────────

async def refresh_active_incident_gauges():
    """Recalculate active incident counts from PostgreSQL."""
    try:
        from app.db.postgres import AsyncSessionFactory
        from app.models.sql_models import WorkItem, WorkItemStatus, Severity
        from sqlalchemy import select, func

        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(WorkItem.severity, func.count(WorkItem.id))
                .where(WorkItem.status != WorkItemStatus.CLOSED)
                .group_by(WorkItem.severity)
            )
            rows = result.all()

        # Reset all severity gauges first
        for sev in ["P0", "P1", "P2", "P3"]:
            ACTIVE_INCIDENTS.labels(severity=sev).set(0)

        for severity, count in rows:
            ACTIVE_INCIDENTS.labels(severity=severity.value).set(count)

    except Exception as e:
        logger.error("Failed to refresh metrics gauges", error=str(e))


# ──────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────

@router.get("/metrics", summary="Prometheus metrics endpoint")
async def metrics():
    """
    Prometheus-compatible metrics endpoint.
    Scrape this with your Prometheus instance.
    """
    await refresh_active_incident_gauges()
    data = generate_latest(REGISTRY)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)