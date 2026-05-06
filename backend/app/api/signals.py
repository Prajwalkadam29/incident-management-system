import asyncio
import structlog
from fastapi import APIRouter, Depends, Query
from typing import Optional
from datetime import datetime, timedelta, timezone

from app.core.rate_limiter import rate_limit_dependency
from app.services.ingestion import ingest_signal
from app.models.schemas import SignalIngestionRequest, SignalResponse
from app.db.mongo import get_mongo_db
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
    signal_id = await ingest_signal(signal)

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
    group_by: str = Query("component_id", description="Field to group by (e.g., component_id, severity, component_type)")
):
    """
    Aggregation endpoint for signals over a rolling time window.
    Satisfies assignment requirement: "Sink (Aggregations): Support timeseries 
    aggregations directly from the document store".
    """
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
        
    return {
        "time_window_hours": time_window_hours,
        "group_by": group_by,
        "data": formatted
    }