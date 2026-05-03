import asyncio
import structlog
from fastapi import APIRouter, Depends, Query
from typing import Optional

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

    # Storm detection — fire and forget, never blocks the response
    asyncio.create_task(
        __import__('app.api.sse', fromlist=['record_signal_for_storm_detection'])
        .record_signal_for_storm_detection()
    )

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