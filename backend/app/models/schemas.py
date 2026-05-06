from uuid import UUID
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator

from app.models.sql_models import (
    WorkItemStatus, Severity, ComponentType, RootCauseCategory
)


# ──────────────────────────────────────────
# Signal Schemas (what producers send us)
# ──────────────────────────────────────────

class SignalIngestionRequest(BaseModel):
    """Payload sent by monitoring agents / producers."""
    component_id: str = Field(..., min_length=1, max_length=255,
                               example="CACHE_CLUSTER_01")
    component_type: ComponentType = Field(..., example="CACHE")
    error_code: str = Field(..., max_length=100, example="CONNECTION_TIMEOUT")
    message: str = Field(..., max_length=2000,
                          example="Cache cluster failed to respond within 5s")
    severity: Severity = Field(..., example="P2")
    metadata: Optional[dict] = Field(default={},
                                      example={"host": "10.0.1.5", "region": "us-east-1"})

    class Config:
        json_schema_extra = {
            "example": {
                "component_id": "CACHE_CLUSTER_01",
                "component_type": "CACHE",
                "error_code": "CONNECTION_TIMEOUT",
                "message": "Cache cluster failed to respond within 5s",
                "severity": "P2",
                "metadata": {"host": "10.0.1.5", "region": "us-east-1"}
            }
        }


class SignalResponse(BaseModel):
    """Returned immediately after ingestion (non-blocking)."""
    signal_id: str
    work_item_id: Optional[str] = None
    message: str
    queued: bool = True


# ──────────────────────────────────────────
# Work Item Schemas
# ──────────────────────────────────────────

class WorkItemBase(BaseModel):
    component_id: str
    component_type: ComponentType
    severity: Severity
    title: str
    description: Optional[str] = None


class WorkItemCreate(WorkItemBase):
    pass


class WorkItemStatusUpdate(BaseModel):
    status: WorkItemStatus
    comment: Optional[str] = None


class RCARecordSchema(BaseModel):
    id: UUID
    work_item_id: UUID
    incident_start: datetime
    incident_end: datetime
    root_cause_category: RootCauseCategory
    fix_applied: str
    prevention_steps: str
    affected_users_count: Optional[str] = None
    timeline_notes: Optional[str] = None
    submitted_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkItemResponse(BaseModel):
    id: UUID
    component_id: str
    component_type: ComponentType
    severity: Severity
    status: WorkItemStatus
    title: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    mttr_minutes: Optional[float] = None
    signal_count: int = 0
    rca: Optional[RCARecordSchema] = None

    class Config:
        from_attributes = True


class WorkItemListResponse(BaseModel):
    items: List[WorkItemResponse]
    total: int
    page: int
    page_size: int


# ──────────────────────────────────────────
# RCA Schemas
# ──────────────────────────────────────────

class RCACreateRequest(BaseModel):
    incident_start: datetime = Field(..., example="2024-01-15T10:00:00Z")
    incident_end: datetime = Field(..., example="2024-01-15T11:30:00Z")
    root_cause_category: RootCauseCategory = Field(..., example="INFRASTRUCTURE")
    fix_applied: str = Field(..., min_length=10,
                              example="Restarted cache cluster nodes and flushed stale connections")
    prevention_steps: str = Field(..., min_length=10,
                                   example="Add automated health checks every 30s with auto-restart")
    affected_users_count: Optional[str] = Field(None, example="~5000")
    timeline_notes: Optional[str] = None
    submitted_by: Optional[str] = None

    @validator("incident_end")
    def end_must_be_after_start(cls, v, values):
        if "incident_start" in values and v <= values["incident_start"]:
            raise ValueError("incident_end must be after incident_start")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "incident_start": "2024-01-15T10:00:00Z",
                "incident_end": "2024-01-15T11:30:00Z",
                "root_cause_category": "INFRASTRUCTURE",
                "fix_applied": "Restarted cache cluster nodes",
                "prevention_steps": "Add automated health checks every 30s",
                "affected_users_count": "~5000",
                "submitted_by": "john.doe@company.com"
            }
        }


# ──────────────────────────────────────────
# Health & Metrics Schemas
# ──────────────────────────────────────────

class ServiceHealth(BaseModel):
    name: str
    status: str   # "healthy" | "degraded" | "down"
    latency_ms: Optional[float] = None
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    timestamp: datetime
    services: List[ServiceHealth]
    uptime_seconds: float