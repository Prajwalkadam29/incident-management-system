import asyncio
import json
import time
import structlog
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from typing import AsyncGenerator

from app.db.postgres import AsyncSessionFactory
from app.db.redis_client import get_redis
from app.models.sql_models import WorkItem, WorkItemStatus, Severity, ComponentType
from app.services.worker import create_work_item_in_db, store_raw_signal_in_mongo, update_dashboard_cache
from app.services.alerting import alerting_service, AlertPayload
from app.core.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["SSE"])

# ──────────────────────────────────────────
# Signal Storm Detection
# ──────────────────────────────────────────

STORM_WINDOW_SECONDS = 30
STORM_THRESHOLD = 500
STORM_KEY = "ims:storm:signals"
STORM_WORK_ITEM_KEY = "ims:storm:work_item_id"


async def record_signal_for_storm_detection():
    """
    Called on every ingested signal.
    Uses a Redis sorted set to count unique signals across ALL components
    in the last 30 seconds. If >500 → systemic outage P0 created.
    """
    redis = get_redis()
    now = time.time()
    window_start = now - STORM_WINDOW_SECONDS

    async with redis.pipeline(transaction=True) as pipe:
        pipe.zadd(STORM_KEY, {str(now): now})
        pipe.zremrangebyscore(STORM_KEY, 0, window_start)
        pipe.zcard(STORM_KEY)
        pipe.expire(STORM_KEY, STORM_WINDOW_SECONDS * 2)
        results = await pipe.execute()

    signal_count = results[2]

    if signal_count >= STORM_THRESHOLD:
        await maybe_create_storm_incident(signal_count)


async def maybe_create_storm_incident(signal_count: int):
    """
    Creates a systemic outage Work Item if one doesn't already exist
    for this storm window. Uses Redis NX to ensure only one is created.
    """
    import uuid
    redis = get_redis()

    storm_work_item_id = str(uuid.uuid4())
    was_set = await redis.set(
        STORM_WORK_ITEM_KEY,
        storm_work_item_id,
        ex=STORM_WINDOW_SECONDS * 2,
        nx=True,
    )

    if not was_set:
        return  # Storm incident already created for this window

    logger.critical(
        "🌩️ SIGNAL STORM DETECTED — SYSTEMIC OUTAGE",
        signal_count=signal_count,
        window_seconds=STORM_WINDOW_SECONDS,
        work_item_id=storm_work_item_id,
    )

    try:
        await create_work_item_in_db(
            work_item_id=storm_work_item_id,
            component_id="SYSTEMIC_OUTAGE",
            component_type=ComponentType.API,
            severity=Severity.P0,
            title=f"[P0] SYSTEMIC OUTAGE — {signal_count} signals in {STORM_WINDOW_SECONDS}s",
        )

        await store_raw_signal_in_mongo({
            "signal_id": storm_work_item_id,
            "work_item_id": storm_work_item_id,
            "component_id": "SYSTEMIC_OUTAGE",
            "component_type": "API",
            "error_code": "SIGNAL_STORM",
            "message": f"Storm detected: {signal_count} signals in {STORM_WINDOW_SECONDS}s",
            "severity": "P0",
            "metadata": {"signal_count": signal_count, "auto_detected": True},
            "timestamp": __import__('datetime').datetime.utcnow(),
            "ingested_at": __import__('datetime').datetime.utcnow(),
        })

        await update_dashboard_cache(
            work_item_id=storm_work_item_id,
            component_id="SYSTEMIC_OUTAGE",
            severity="P0",
            status="OPEN",
        )

        await alerting_service.alert(AlertPayload(
            work_item_id=storm_work_item_id,
            component_id="SYSTEMIC_OUTAGE",
            component_type=ComponentType.API,
            severity=Severity.P0,
            title=f"SYSTEMIC OUTAGE — {signal_count} signals in {STORM_WINDOW_SECONDS}s",
            signal_count=signal_count,
            message="Automatic storm detection triggered",
        ))

    except Exception as e:
        logger.error("Failed to create storm incident", error=str(e))


# ──────────────────────────────────────────
# SSE Event Generator
# ──────────────────────────────────────────

async def incident_event_generator(request: Request) -> AsyncGenerator[str, None]:
    """
    Streams live incident updates to connected clients.
    Sends a full snapshot every 3 seconds.
    Client disconnection is detected via request.is_disconnected().
    """
    logger.info("SSE client connected", client=request.client.host)

    try:
        while True:
            if await request.is_disconnected():
                logger.info("SSE client disconnected", client=request.client.host)
                break

            try:
                async with AsyncSessionFactory() as session:
                    result = await session.execute(
                        select(WorkItem)
                        .where(WorkItem.status != WorkItemStatus.CLOSED)
                        .order_by(WorkItem.created_at.desc())
                        .limit(50)
                    )
                    work_items = result.scalars().all()

                    # Build summary stats
                    stats_result = await session.execute(
                        select(
                            func.count(WorkItem.id).label("total"),
                            func.avg(WorkItem.mttr_minutes).label("avg_mttr"),
                        )
                    )
                    stats = stats_result.one()

                    p0_result = await session.execute(
                        select(func.count(WorkItem.id))
                        .where(WorkItem.severity == Severity.P0)
                        .where(WorkItem.status != WorkItemStatus.CLOSED)
                    )
                    p0_count = p0_result.scalar()

                payload = {
                    "incidents": [
                        {
                            "id": str(wi.id),
                            "component_id": wi.component_id,
                            "component_type": wi.component_type.value,
                            "severity": wi.severity.value,
                            "status": wi.status.value,
                            "title": wi.title,
                            "signal_count": wi.signal_count,
                            "created_at": wi.created_at.isoformat(),
                            "updated_at": wi.updated_at.isoformat(),
                        }
                        for wi in work_items
                    ],
                    "stats": {
                        "total_active": len(work_items),
                        "p0_count": p0_count,
                        "avg_mttr": round(float(stats.avg_mttr), 1) if stats.avg_mttr else None,
                        "total_all_time": stats.total,
                    },
                    "timestamp": time.time(),
                }

                yield f"data: {json.dumps(payload)}\n\n"

            except Exception as e:
                logger.error("SSE generator error", error=str(e))
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

            await asyncio.sleep(3)

    except asyncio.CancelledError:
        logger.info("SSE connection cancelled")


# ──────────────────────────────────────────
# SSE Endpoint
# ──────────────────────────────────────────

@router.get("/api/v1/stream/incidents", summary="SSE — Live incident stream")
async def stream_incidents(request: Request):
    """
    Server-Sent Events endpoint.
    Connect from the frontend with:
        const es = new EventSource('/api/v1/stream/incidents')
        es.onmessage = (e) => setData(JSON.parse(e.data))
    """
    return StreamingResponse(
        incident_event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
            "Access-Control-Allow-Origin": "*",
        },
    )