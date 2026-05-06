import asyncio
import structlog
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from datetime import datetime, timedelta, timezone

from app.core.rate_limiter import rate_limit_dependency
from app.services.ingestion import ingest_signal
from app.models.schemas import SignalIngestionRequest, SignalResponse
from app.db.mongo import get_mongo_db
from app.db.redis_client import get_redis
from app.models.sql_models import ComponentType, Severity

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/signals", tags=["Signals"])


@router.post(
    "/ingest",
    response_model=SignalResponse,
    status_code=202,
    summary="Ingest a signal from a monitored component",
    dependencies=[Depends(rate_limit_dependency)],
)
async def ingest(signal: SignalIngestionRequest):
    try:
        signal_id = await ingest_signal(signal)
    except Exception as e:
        logger.critical(
            "Signal ingestion failed: Redis stream/queue is unavailable",
            component_id=signal.component_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=503,
            detail="Signal ingestion service is temporarily unavailable due to downstream queue connection issues.",
        )

    # Storm detection — deferred import avoids circular dependency at module level.
    # Long-term fix: extract storm detection into services/storm.py (Step 3 refactor).
    from app.api.sse import record_signal_for_storm_detection
    asyncio.create_task(record_signal_for_storm_detection())

    return SignalResponse(
        signal_id=signal_id,
        message="Signal accepted for processing",
        queued=True,
    )


@router.get(
    "/",
    summary="Query raw signals from MongoDB",
)
async def list_signals(
        work_item_id: Optional[str] = Query(None, description="Filter by Work Item ID"),
        component_id: Optional[str] = Query(None, description="Filter by Component ID"),
        limit: int = Query(50, ge=1, le=500),
        skip: int = Query(0, ge=0),
):
    """
    Retrieve raw signals from MongoDB audit log.
    Used by the Incident Detail page to show all linked signals.
    """
    db = get_mongo_db()

    query = {}
    if work_item_id:
        query["work_item_id"] = work_item_id
    if component_id:
        query["component_id"] = component_id

    cursor = db.signals.find(
        query,
        {"_id": 0}  # exclude MongoDB internal _id from response
    ).sort("timestamp", -1).skip(skip).limit(limit)

    signals = await cursor.to_list(length=limit)
    total = await db.signals.count_documents(query)

    # Convert datetime objects to ISO strings for JSON
    for s in signals:
        for key in ("timestamp", "ingested_at"):
            if key in s and hasattr(s[key], "isoformat"):
                s[key] = s[key].isoformat()

    return {"signals": signals, "total": total, "skip": skip, "limit": limit}


@router.get(
    "/aggregations",
    summary="Time-series aggregations from MongoDB",
)
async def get_signals_aggregation(
    time_window_hours: int = Query(24, ge=1, le=168, description="Time window in hours"),
    group_by: str = Query("component_id", description="Field to group by (e.g., component_id, severity, component_type)"),
    bypass_cache: bool = Query(False, description="Bypass the cache and query the database directly")
):
    """
    Aggregation endpoint for signals over a rolling time window.
    Satisfies assignment requirement: "Sink (Aggregations): Support timeseries 
    aggregations directly from the document store".

    Includes a high-performance 10-second Redis read-through caching layer
    to shield the database from dashboard storming.
    """
    redis = get_redis()
    cache_key = f"ims:cache:signals:agg:{time_window_hours}:{group_by}"

    if not bypass_cache:
        try:
            cached_val = await redis.get(cache_key)
            if cached_val:
                import json
                logger.info("Serving signal aggregations from Redis cache", window_hours=time_window_hours, group_by=group_by)
                return json.loads(cached_val)
        except Exception as e:
            logger.error("Failed to read signal aggregation cache", error=str(e))

    db = get_mongo_db()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)
    
    # MongoDB Aggregation Pipeline
    pipeline = [
        # 1. Filter by time window
        {"$match": {"timestamp": {"$gte": cutoff}}},
        # 2. Group by the requested field and count
        {"$group": {
            "_id": f"${group_by}",
            "count": {"$sum": 1},
            "last_seen": {"$max": "$timestamp"}
        }},
        # 3. Sort by count descending
        {"$sort": {"count": -1}}
    ]
    
    cursor = db.signals.aggregate(pipeline)
    results = await cursor.to_list(length=100)
    
    # Format for JSON response
    formatted = []
    for r in results:
        last_seen = r.get("last_seen")
        formatted.append({
            group_by: r["_id"] or "unknown",
            "count": r["count"],
            "last_seen": last_seen.isoformat() if hasattr(last_seen, "isoformat") else last_seen
        })
        
    response_data = {
        "time_window_hours": time_window_hours,
        "group_by": group_by,
        "data": formatted,
        "cached": False
    }

    # Store in Redis with a short 10-second TTL
    try:
        import json
        cache_payload = response_data.copy()
        cache_payload["cached"] = True
        await redis.setex(cache_key, 10, json.dumps(cache_payload))
    except Exception as e:
        logger.error("Failed to write signal aggregation cache", error=str(e))

    return response_data