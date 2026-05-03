import uuid
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional

from app.db.postgres import get_db_session, AsyncSessionFactory
from app.db.redis_client import get_redis
from app.models.sql_models import WorkItem, RCARecord, WorkItemStatus
from app.models.schemas import (
    WorkItemResponse, WorkItemListResponse,
    WorkItemStatusUpdate, RCACreateRequest, RCARecordSchema,
)
from app.services.state_machine import state_machine, InvalidStateTransitionError, MissingRCAError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/workitems", tags=["Work Items"])


# ──────────────────────────────────────────
# Helper
# ──────────────────────────────────────────

async def get_work_item_or_404(work_item_id: str, session) -> WorkItem:
    result = await session.execute(
        select(WorkItem)
        .options(selectinload(WorkItem.rca))
        .where(WorkItem.id == uuid.UUID(work_item_id))
    )
    work_item = result.scalar_one_or_none()
    if not work_item:
        raise HTTPException(status_code=404, detail=f"Work Item {work_item_id} not found")
    return work_item


# ──────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────

@router.get("/", response_model=WorkItemListResponse, summary="List all Work Items")
async def list_work_items(
        status: Optional[WorkItemStatus] = Query(None),
        severity: Optional[str] = Query(None),
        component_type: Optional[str] = Query(None),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        session=Depends(get_db_session),
):
    """
    List Work Items with optional filters.
    Results sorted by severity (P0 first) then created_at descending.
    """
    query = select(WorkItem).options(selectinload(WorkItem.rca))

    if status:
        query = query.where(WorkItem.status == status)
    if severity:
        query = query.where(WorkItem.severity == severity)
    if component_type:
        query = query.where(WorkItem.component_type == component_type)

    # Count total for pagination
    count_query = select(func.count()).select_from(
        query.subquery()
    )
    total_result = await session.execute(count_query)
    total = total_result.scalar()

    # Sort: P0 → P1 → P2 → P3, then newest first
    severity_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    query = (
        query
        .order_by(WorkItem.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await session.execute(query)
    items = result.scalars().all()

    return WorkItemListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{work_item_id}", response_model=WorkItemResponse,
            summary="Get a single Work Item")
async def get_work_item(work_item_id: str, session=Depends(get_db_session)):
    return await get_work_item_or_404(work_item_id, session)


@router.patch("/{work_item_id}/status", response_model=WorkItemResponse,
              summary="Transition Work Item status")
async def update_work_item_status(
        work_item_id: str,
        update: WorkItemStatusUpdate,
        session=Depends(get_db_session),
):
    """
    Transition a Work Item through its lifecycle:
    OPEN → INVESTIGATING → RESOLVED → CLOSED

    Invalid transitions are rejected with a 409 Conflict.
    Attempting to CLOSE without an RCA returns a 422.
    """
    work_item = await get_work_item_or_404(work_item_id, session)

    try:
        state_machine.transition(work_item, update.status)
    except MissingRCAError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))

    await session.flush()

    # Invalidate/update dashboard cache
    redis = get_redis()
    cache_key = f"ims:dashboard:{work_item_id}"
    await redis.hset(cache_key, mapping={
        "status": update.status.value,
        "updated_at": str(__import__("time").time()),
    })

    logger.info("Work Item status updated",
                work_item_id=work_item_id,
                new_status=update.status)

    return work_item


@router.post("/{work_item_id}/rca", response_model=RCARecordSchema,
             status_code=201, summary="Submit RCA for a Work Item")
async def submit_rca(
        work_item_id: str,
        rca_data: RCACreateRequest,
        session=Depends(get_db_session),
):
    """
    Submit a Root Cause Analysis for a Work Item.
    RCA is mandatory before the Work Item can be CLOSED.
    Only one RCA per Work Item is allowed (updates are rejected).
    """
    work_item = await get_work_item_or_404(work_item_id, session)

    if work_item.status == WorkItemStatus.CLOSED:
        raise HTTPException(status_code=409,
                            detail="Cannot modify RCA of a closed Work Item")

    if work_item.rca:
        raise HTTPException(status_code=409,
                            detail="RCA already exists for this Work Item. Use PATCH to update.")

    rca = RCARecord(
        work_item_id=uuid.UUID(work_item_id),
        incident_start=rca_data.incident_start,
        incident_end=rca_data.incident_end,
        root_cause_category=rca_data.root_cause_category,
        fix_applied=rca_data.fix_applied,
        prevention_steps=rca_data.prevention_steps,
        affected_users_count=rca_data.affected_users_count,
        timeline_notes=rca_data.timeline_notes,
        submitted_by=rca_data.submitted_by,
    )
    session.add(rca)
    await session.flush()
    await session.refresh(rca)

    logger.info("RCA submitted",
                work_item_id=work_item_id,
                category=rca_data.root_cause_category)

    return rca


@router.get("/{work_item_id}/rca", response_model=RCARecordSchema,
            summary="Get RCA for a Work Item")
async def get_rca(work_item_id: str, session=Depends(get_db_session)):
    work_item = await get_work_item_or_404(work_item_id, session)
    if not work_item.rca:
        raise HTTPException(status_code=404,
                            detail="No RCA submitted for this Work Item yet")
    return work_item.rca