import uuid
import json
import structlog
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from tenacity import retry, stop_after_attempt, wait_exponential

from app.db.postgres import AsyncSessionFactory
from app.models.sql_models import IncidentEvent, EventType

logger = structlog.get_logger(__name__)


# ──────────────────────────────────────────
# Core writer — used by all other services
# ──────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    reraise=True,
)
async def record_event(
    work_item_id: str,
    event_type: EventType,
    summary: str,
    actor: Optional[str] = "system",
    metadata: Optional[dict] = None,
) -> None:
    """
    Write a timeline event to PostgreSQL.
    Called by worker, API routes, and other services.
    Always fire-and-forget — never block the main flow.
    """
    async with AsyncSessionFactory() as session:
        async with session.begin():
            event = IncidentEvent(
                work_item_id=uuid.UUID(work_item_id),
                event_type=event_type,
                summary=summary,
                actor=actor,
                event_metadata=json.dumps(metadata) if metadata else None,
            )
            session.add(event)

    logger.debug(
        "Timeline event recorded",
        work_item_id=work_item_id,
        event_type=event_type,
        summary=summary,
    )


# ──────────────────────────────────────────
# Convenience helpers — semantic API
# ──────────────────────────────────────────

async def record_incident_created(
    work_item_id: str,
    component_id: str,
    severity: str,
    signal_count: int = 1,
):
    await record_event(
        work_item_id=work_item_id,
        event_type=EventType.INCIDENT_CREATED,
        summary=f"Incident created for {component_id} with severity {severity}",
        actor="system",
        metadata={"component_id": component_id, "severity": severity, "signal_count": signal_count},
    )


async def record_status_change(
    work_item_id: str,
    old_status: str,
    new_status: str,
    actor: str = "system",
    mttr_minutes: Optional[float] = None,
):
    summary = f"Status changed: {old_status} → {new_status}"
    if new_status == "CLOSED" and mttr_minutes:
        summary += f" (MTTR: {mttr_minutes:.1f} minutes)"

    await record_event(
        work_item_id=work_item_id,
        event_type=EventType.STATUS_CHANGED
            if new_status != "CLOSED" else EventType.INCIDENT_CLOSED,
        summary=summary,
        actor=actor,
        metadata={"old_status": old_status, "new_status": new_status, "mttr_minutes": mttr_minutes},
    )


async def record_signal_received(
    work_item_id: str,
    error_code: str,
    component_id: str,
    signal_count: int,
):
    await record_event(
        work_item_id=work_item_id,
        event_type=EventType.SIGNAL_RECEIVED,
        summary=f"Signal received: {error_code} on {component_id} (total: {signal_count})",
        actor="system",
        metadata={"error_code": error_code, "component_id": component_id, "signal_count": signal_count},
    )


async def record_rca_submitted(
    work_item_id: str,
    submitted_by: Optional[str],
    root_cause_category: str,
):
    await record_event(
        work_item_id=work_item_id,
        event_type=EventType.RCA_SUBMITTED,
        summary=f"RCA submitted — root cause: {root_cause_category}",
        actor=submitted_by or "unknown",
        metadata={"root_cause_category": root_cause_category},
    )


async def record_alert_fired(
    work_item_id: str,
    severity: str,
    channel: str,
):
    await record_event(
        work_item_id=work_item_id,
        event_type=EventType.ALERT_FIRED,
        summary=f"{severity} alert fired → {channel}",
        actor="system",
        metadata={"severity": severity, "channel": channel},
    )


# ──────────────────────────────────────────
# Reader
# ──────────────────────────────────────────

async def get_timeline(work_item_id: str) -> list[dict]:
    """Fetch all timeline events for a Work Item, latest first."""
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(IncidentEvent)
            .where(IncidentEvent.work_item_id == uuid.UUID(work_item_id))
            .order_by(IncidentEvent.created_at.desc())
        )
        events = result.scalars().all()

    return [
        {
            "id":           str(e.id),
            "event_type":   e.event_type.value,
            "summary":      e.summary,
            "actor":        e.actor,
            "metadata":     json.loads(e.event_metadata) if e.event_metadata else {},
            "created_at":   e.created_at.isoformat(),
        }
        for e in events
    ]