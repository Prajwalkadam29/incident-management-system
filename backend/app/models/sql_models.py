import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, DateTime, Enum, ForeignKey,
    Text, Float, Integer, func, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.postgres import Base


# --- Enums ---
class WorkItemStatus(str, PyEnum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class Severity(str, PyEnum):
    P0 = "P0"   # Critical  — e.g., RDBMS down
    P1 = "P1"   # High      — e.g., API failure
    P2 = "P2"   # Medium    — e.g., Cache miss spike
    P3 = "P3"   # Low       — e.g., queue lag


class ComponentType(str, PyEnum):
    RDBMS = "RDBMS"
    API = "API"
    CACHE = "CACHE"
    QUEUE = "QUEUE"
    NOSQL = "NOSQL"
    MCP_HOST = "MCP_HOST"


class RootCauseCategory(str, PyEnum):
    INFRASTRUCTURE = "INFRASTRUCTURE"
    APPLICATION = "APPLICATION"
    NETWORK = "NETWORK"
    DEPENDENCY = "DEPENDENCY"
    HUMAN_ERROR = "HUMAN_ERROR"
    UNKNOWN = "UNKNOWN"


# --- Work Item Table ---
class WorkItem(Base):
    __tablename__ = "work_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    component_id = Column(String(255), nullable=False, index=True)
    component_type = Column(Enum(ComponentType), nullable=False)
    severity = Column(Enum(Severity), nullable=False)
    status = Column(Enum(WorkItemStatus), nullable=False, default=WorkItemStatus.OPEN)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    # MTTR in minutes (calculated on close)
    mttr_minutes = Column(Float, nullable=True)

    # Signal count — Integer (was String in pre-Alembic schema; fixed in migration 0002)
    signal_count = Column(Integer, nullable=False, default=0, server_default="0")

    # Relationships
    rca = relationship("RCARecord", back_populates="work_item",
                       uselist=False, cascade="all, delete-orphan")

    # Composite index for common dashboard queries
    __table_args__ = (
        Index("ix_work_items_status_severity", "status", "severity"),
        Index("ix_work_items_component_status", "component_id", "status"),
        Index("uix_work_items_component_open", "component_id", unique=True, postgresql_where=(status == 'OPEN')),
    )

    def __repr__(self):
        return f"<WorkItem {self.id} [{self.status}] {self.component_id}>"


# --- RCA Record Table ---
class RCARecord(Base):
    __tablename__ = "rca_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_item_id = Column(UUID(as_uuid=True), ForeignKey("work_items.id",
                          ondelete="CASCADE"), nullable=False, unique=True)

    # Mandatory RCA fields
    incident_start = Column(DateTime(timezone=True), nullable=False)
    incident_end = Column(DateTime(timezone=True), nullable=False)
    root_cause_category = Column(Enum(RootCauseCategory), nullable=False)
    fix_applied = Column(Text, nullable=False)
    prevention_steps = Column(Text, nullable=False)

    # Optional enrichment
    affected_users_count = Column(String(50), nullable=True)
    timeline_notes = Column(Text, nullable=True)

    # Meta
    submitted_by = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now())

    # Relationship back to WorkItem
    work_item = relationship("WorkItem", back_populates="rca")

    def __repr__(self):
        return f"<RCARecord {self.id} for WorkItem {self.work_item_id}>"


class EventType(str, PyEnum):
    INCIDENT_CREATED   = "INCIDENT_CREATED"
    STATUS_CHANGED     = "STATUS_CHANGED"
    SIGNAL_RECEIVED    = "SIGNAL_RECEIVED"
    RCA_SUBMITTED      = "RCA_SUBMITTED"
    INCIDENT_CLOSED    = "INCIDENT_CLOSED"
    ALERT_FIRED        = "ALERT_FIRED"
    CORRELATION_LINKED = "CORRELATION_LINKED"
    COMMENT_ADDED      = "COMMENT_ADDED"


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("work_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(Enum(EventType), nullable=False)
    summary    = Column(String(500), nullable=False)  # human-readable description
    actor      = Column(String(255), nullable=True)   # who triggered it (username or "system")
    event_metadata   = Column(Text, nullable=True)          # JSON blob for extra context
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_incident_events_work_item_created", "work_item_id", "created_at"),
    )

    def __repr__(self):
        return f"<IncidentEvent {self.event_type} on {self.work_item_id}>"