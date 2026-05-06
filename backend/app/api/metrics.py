import time
from datetime import datetime, timedelta, timezone
import structlog
from fastapi import APIRouter, Response, Depends, Query

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

from app.core.security import get_current_user
from app.db.postgres import AsyncSessionFactory
from app.db.mongo import get_mongo_db
from app.models.sql_models import WorkItem, WorkItemStatus
from sqlalchemy import select, func, and_

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


@router.get("/api/v1/metrics/mttr-trend", summary="MTTR timeseries for dashboard")
async def get_mttr_trend(
    days: int = Query(14, ge=1, le=90),
    current_user: dict = Depends(get_current_user)
):
    """
    Returns the daily average MTTR (Mean Time To Resolution) for the past N days.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    async with AsyncSessionFactory() as session:
        # Postgres date_trunc and average
        result = await session.execute(
            select(
                func.date_trunc('day', WorkItem.closed_at).label('date'),
                func.avg(WorkItem.mttr_minutes).label('avg_mttr')
            )
            .where(
                and_(
                    WorkItem.status == WorkItemStatus.CLOSED,
                    WorkItem.closed_at >= cutoff,
                    WorkItem.mttr_minutes > 0
                )
            )
            .group_by('date')
            .order_by('date')
        )
        
        rows = result.all()
        
    trend = []
    for row in rows:
        if row.date is not None:
            trend.append({
                "date": row.date.strftime('%Y-%m-%d'),
                "mttr": round(float(row.avg_mttr), 1)
            })
            
    return {"trend": trend}


@router.get("/api/v1/metrics/signals-per-hour", summary="Signal ingestion timeseries")
async def get_signals_per_hour(
    hours: int = Query(24, ge=1, le=168),
    current_user: dict = Depends(get_current_user)
):
    """
    Uses MongoDB aggregation to return the count of raw signals ingested per hour.
    """
    db = get_mongo_db()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    pipeline = [
        {"$match": {"ingested_at": {"$gte": cutoff}}},
        {
            "$group": {
                "_id": {
                    "year": {"$year": "$ingested_at"},
                    "month": {"$month": "$ingested_at"},
                    "day": {"$dayOfMonth": "$ingested_at"},
                    "hour": {"$hour": "$ingested_at"}
                },
                "count": {"$sum": 1}
            }
        },
        {"$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1, "_id.hour": 1}}
    ]
    
    cursor = db.signals.aggregate(pipeline)
    
    trend = []
    async for doc in cursor:
        _id = doc["_id"]
        # Format as ISO string for the specific hour
        dt = datetime(_id["year"], _id["month"], _id["day"], _id["hour"], 0, 0, tzinfo=timezone.utc)
        trend.append({
            "timestamp": dt.isoformat(),
            "count": doc["count"]
        })
        
    return {"trend": trend}