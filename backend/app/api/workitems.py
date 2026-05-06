import uuid
import time
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, case, text
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import datetime

from app.core.security import get_current_user, require_admin
from app.db.postgres import get_db_session, AsyncSessionFactory
from app.db.redis_client import get_redis
from app.models.sql_models import WorkItem, RCARecord, WorkItemStatus, Severity
from app.models.schemas import (
    WorkItemResponse, WorkItemListResponse,
    WorkItemStatusUpdate, RCACreateRequest, RCARecordSchema,
)
from app.services.state_machine import state_machine, InvalidStateTransitionError, MissingRCAError
from app.services import timeline as tl

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
        component_id: Optional[str] = Query(None),
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
    if component_id:
        query = query.where(WorkItem.component_id == component_id)

    # Count total for pagination
    count_query = select(func.count()).select_from(
        query.subquery()
    )
    total_result = await session.execute(count_query)
    total = total_result.scalar()

    # Sort: P0 → P1 → P2 → P3 using a SQL CASE expression, then newest-first.
    # This ensures pagination is deterministic — client-side sort breaks page 2+.
    severity_order = case(
        {
            Severity.P0: 0,
            Severity.P1: 1,
            Severity.P2: 2,
            Severity.P3: 3,
        },
        value=WorkItem.severity,
        else_=99,
    )
    query = (
        query
        .order_by(severity_order.asc(), WorkItem.created_at.desc())
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


# ──────────────────────────────────────────
# History / Archive Endpoints
# ──────────────────────────────────────────

@router.get("/history/stats", summary="Get Historical Incident Statistics")
async def get_history_stats(session=Depends(get_db_session)):
    """
    Get aggregated historical statistics of closed incidents:
    - Total closed
    - Average MTTR
    - Incidents by severity
    - Monthly closures (last 6 months)
    """
    # 1. Total and Avg MTTR
    stats_query = select(
        func.count(WorkItem.id).label("total"),
        func.avg(WorkItem.mttr_minutes).label("avg_mttr")
    ).where(WorkItem.status == WorkItemStatus.CLOSED)
    
    stats_res = await session.execute(stats_query)
    overall = stats_res.one()
    total_closed = overall.total
    avg_mttr = round(float(overall.avg_mttr), 1) if overall.avg_mttr is not None else 0.0

    # 2. Incidents by severity
    sev_query = select(
        WorkItem.severity,
        func.count(WorkItem.id).label("count")
    ).where(WorkItem.status == WorkItemStatus.CLOSED).group_by(WorkItem.severity)
    
    sev_res = await session.execute(sev_query)
    severity_distribution = {row.severity.value: row.count for row in sev_res.all()}

    # 3. Monthly closures (last 6 months)
    monthly_query = select(
        func.date_trunc('month', WorkItem.closed_at).label("month"),
        func.count(WorkItem.id).label("count")
    ).where(WorkItem.status == WorkItemStatus.CLOSED).group_by(text("month")).order_by(text("month DESC")).limit(6)
    
    monthly_closures = []
    try:
        from sqlalchemy import text as sa_text
        monthly_res = await session.execute(monthly_query)
        for row in monthly_res.all():
            if row.month:
                monthly_closures.append({
                    "month": row.month.strftime("%Y-%m"),
                    "count": row.count
                })
    except Exception as e:
        logger.error("Failed to query monthly closures, falling back", error=str(e))
        pass

    return {
        "total_closed": total_closed,
        "avg_mttr_minutes": avg_mttr,
        "severity_distribution": severity_distribution,
        "monthly_closures": monthly_closures
    }


@router.get("/history", response_model=WorkItemListResponse, summary="List Closed Work Items (History)")
async def list_closed_work_items(
        severity: Optional[str] = Query(None),
        component_type: Optional[str] = Query(None),
        component_id: Optional[str] = Query(None),
        closed_by: Optional[str] = Query(None),
        start_date: Optional[datetime] = Query(None, description="Filter closures after this date"),
        end_date: Optional[datetime] = Query(None, description="Filter closures before this date"),
        query_str: Optional[str] = Query(None, description="Search keyword in title or description"),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        session=Depends(get_db_session),
):
    """
    List CLOSED Work Items (History) with extensive filters and pagination.
    Sorted by closed_at descending.
    """
    query = select(WorkItem).options(selectinload(WorkItem.rca)).where(WorkItem.status == WorkItemStatus.CLOSED)

    if severity:
        query = query.where(WorkItem.severity == severity)
    if component_type:
        query = query.where(WorkItem.component_type == component_type)
    if component_id:
        query = query.where(WorkItem.component_id == component_id)
    if closed_by:
        query = query.where(WorkItem.closed_by == closed_by)
    if start_date:
        query = query.where(WorkItem.closed_at >= start_date)
    if end_date:
        query = query.where(WorkItem.closed_at <= end_date)
    if query_str:
        query = query.where(
            (WorkItem.title.ilike(f"%{query_str}%")) | 
            (WorkItem.description.ilike(f"%{query_str}%"))
        )

    # Count total for pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar()

    # Order by closed_at descending
    query = (
        query
        .order_by(WorkItem.closed_at.desc())
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


@router.get("/history/{work_item_id}", response_model=WorkItemResponse, summary="Get Historical Work Item Detail")
async def get_historical_work_item(work_item_id: str, session=Depends(get_db_session)):
    """
    Get full detail of a historical closed work item.
    """
    work_item = await get_work_item_or_404(work_item_id, session)
    if work_item.status != WorkItemStatus.CLOSED:
        raise HTTPException(status_code=400, detail=f"Work Item {work_item_id} is not closed")
    return work_item


@router.get("/{work_item_id}", response_model=WorkItemResponse,
            summary="Get a single Work Item")
async def get_work_item(work_item_id: str, session=Depends(get_db_session)):
    return await get_work_item_or_404(work_item_id, session)


@router.patch(
    "/{work_item_id}/status",
    response_model=WorkItemResponse,
    summary="Transition Work Item status (admin only)",
)
async def update_work_item_status(
        work_item_id: str,
        update: WorkItemStatusUpdate,
        session=Depends(get_db_session),
        current_user: dict = Depends(require_admin),
):
    """
    Transition a Work Item through its lifecycle:
    OPEN → INVESTIGATING → RESOLVED → CLOSED

    **Admin role required.**
    Invalid transitions are rejected with 409 Conflict.
    Attempting to CLOSE without a submitted RCA returns 422.
    """
    work_item = await get_work_item_or_404(work_item_id, session)

    old_status = work_item.status.value
    try:
        if update.status == WorkItemStatus.CLOSED:
            state_machine.transition(work_item, update.status, closed_by=current_user["username"])
        else:
            state_machine.transition(work_item, update.status)
    except MissingRCAError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))

    await session.flush()

    # Record timeline event — actor is the authenticated user making this request
    import asyncio
    asyncio.create_task(tl.record_status_change(
        work_item_id=work_item_id,
        old_status=old_status,
        new_status=update.status.value,
        actor=current_user["username"],
        mttr_minutes=work_item.mttr_minutes,
    ))

    # Invalidate/update dashboard cache
    redis = get_redis()
    cache_key = f"ims:dashboard:{work_item_id}"
    await redis.hset(cache_key, mapping={
        "status": update.status.value,
        "updated_at": str(time.time()),
    })

    logger.info(
        "Work Item status updated",
        work_item_id=work_item_id,
        new_status=update.status,
        actor=current_user["username"],
    )

    return work_item


@router.post(
    "/{work_item_id}/rca",
    response_model=RCARecordSchema,
    status_code=201,
    summary="Submit RCA for a Work Item",
)
async def submit_rca(
        work_item_id: str,
        rca_data: RCACreateRequest,
        session=Depends(get_db_session),
        current_user: dict = Depends(get_current_user),
):
    """
    Submit a Root Cause Analysis for a Work Item.
    RCA is mandatory before the Work Item can be CLOSED.
    Only one RCA per Work Item is allowed.
    """
    work_item = await get_work_item_or_404(work_item_id, session)

    if work_item.status == WorkItemStatus.CLOSED:
        raise HTTPException(
            status_code=409,
            detail="Cannot modify RCA of a closed Work Item",
        )

    if work_item.rca:
        raise HTTPException(
            status_code=409,
            detail="RCA already submitted for this Work Item.",
        )

    # Resolve submitter: prefer explicit field, fall back to authenticated user
    submitted_by = rca_data.submitted_by or current_user["username"]

    rca = RCARecord(
        work_item_id=uuid.UUID(work_item_id),
        incident_start=rca_data.incident_start,
        incident_end=rca_data.incident_end,
        root_cause_category=rca_data.root_cause_category,
        fix_applied=rca_data.fix_applied,
        prevention_steps=rca_data.prevention_steps,
        affected_users_count=rca_data.affected_users_count,
        timeline_notes=rca_data.timeline_notes,
        submitted_by=submitted_by,
    )
    session.add(rca)
    await session.flush()
    await session.refresh(rca)

    import asyncio
    asyncio.create_task(tl.record_rca_submitted(
        work_item_id=work_item_id,
        submitted_by=submitted_by,
        root_cause_category=rca_data.root_cause_category.value,
    ))

    logger.info(
        "RCA submitted",
        work_item_id=work_item_id,
        category=rca_data.root_cause_category,
        submitted_by=submitted_by,
    )

    return rca


@router.get("/{work_item_id}/rca", response_model=RCARecordSchema,
            summary="Get RCA for a Work Item")
async def get_rca(work_item_id: str, session=Depends(get_db_session)):
    work_item = await get_work_item_or_404(work_item_id, session)
    if not work_item.rca:
        raise HTTPException(status_code=404,
                            detail="No RCA submitted for this Work Item yet")
    return work_item.rca


@router.get(
    "/{work_item_id}/timeline",
    summary="Get incident timeline / audit trail",
)
async def get_work_item_timeline(work_item_id: str):
    """
    Returns chronological audit trail of all events
    for this Work Item — creation, status changes,
    signals received, RCA submission, closure.
    """
    from app.services.timeline import get_timeline
    events = await get_timeline(work_item_id)
    return {"work_item_id": work_item_id, "events": events, "count": len(events)}


@router.get("/{work_item_id}/similar-past", summary="Find similar past closed incidents")
async def get_similar_past_incidents(
    work_item_id: str,
    limit: int = Query(3, ge=1, le=10),
    session=Depends(get_db_session)
):
    """
    Find past closed incidents that occurred on the same component_id or component_type
    and return their details along with their RCAs to help engineers resolve active incidents.
    """
    work_item = await get_work_item_or_404(work_item_id, session)
    
    # Query CLOSED work items excluding the current one
    query = (
        select(WorkItem)
        .options(selectinload(WorkItem.rca))
        .where(WorkItem.status == WorkItemStatus.CLOSED)
        .where(WorkItem.id != uuid.UUID(work_item_id))
    )
    
    # Filter by same component_id first
    same_component_query = query.where(WorkItem.component_id == work_item.component_id).limit(limit)
    res = await session.execute(same_component_query)
    similar = list(res.scalars().all())
    
    # If we need more to fill the limit, query by same component_type
    if len(similar) < limit:
        remaining = limit - len(similar)
        existing_ids = [wi.id for wi in similar]
        
        same_type_query = (
            query
            .where(WorkItem.component_type == work_item.component_type)
            .where(~WorkItem.id.in_(existing_ids) if existing_ids else True)
            .limit(remaining)
        )
        res_type = await session.execute(same_type_query)
        similar.extend(res_type.scalars().all())
        
    return [
        {
            "id": str(wi.id),
            "title": wi.title,
            "component_id": wi.component_id,
            "component_type": wi.component_type.value,
            "severity": wi.severity.value,
            "closed_at": wi.closed_at.isoformat() if wi.closed_at else None,
            "mttr_minutes": wi.mttr_minutes,
            "rca": {
                "root_cause_category": wi.rca.root_cause_category.value if wi.rca else None,
                "fix_applied": wi.rca.fix_applied if wi.rca else None,
                "prevention_steps": wi.rca.prevention_steps if wi.rca else None,
            } if wi.rca else None
        }
        for wi in similar
    ]