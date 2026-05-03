import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from app.services.state_machine import (
    WorkItemStateMachine,
    InvalidStateTransitionError,
    MissingRCAError,
)
from app.models.sql_models import WorkItemStatus, Severity, ComponentType


# ──────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────

def make_work_item(status: WorkItemStatus, rca=None):
    """Create a mock WorkItem ORM object."""
    wi = MagicMock()
    wi.id = uuid.uuid4()
    wi.status = status
    wi.severity = Severity.P0
    wi.component_type = ComponentType.RDBMS
    wi.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
    wi.rca = rca
    return wi


def make_rca(start_offset_hours=-2, end_offset_hours=-1):
    """Create a mock RCA object."""
    rca = MagicMock()
    rca.incident_start = datetime.now(timezone.utc) + timedelta(hours=start_offset_hours)
    rca.incident_end = datetime.now(timezone.utc) + timedelta(hours=end_offset_hours)
    return rca


sm = WorkItemStateMachine()


# ──────────────────────────────────────────
# Valid Transition Tests
# ──────────────────────────────────────────

def test_open_to_investigating():
    wi = make_work_item(WorkItemStatus.OPEN)
    sm.transition(wi, WorkItemStatus.INVESTIGATING)
    assert wi.status == WorkItemStatus.INVESTIGATING


def test_investigating_to_resolved():
    wi = make_work_item(WorkItemStatus.INVESTIGATING)
    sm.transition(wi, WorkItemStatus.RESOLVED)
    assert wi.status == WorkItemStatus.RESOLVED
    assert wi.resolved_at is not None


def test_resolved_to_closed_with_rca():
    rca = make_rca()
    wi = make_work_item(WorkItemStatus.RESOLVED, rca=rca)
    sm.transition(wi, WorkItemStatus.CLOSED)
    assert wi.status == WorkItemStatus.CLOSED
    assert wi.closed_at is not None
    assert wi.mttr_minutes is not None
    assert wi.mttr_minutes > 0


# ──────────────────────────────────────────
# Invalid Transition Tests
# ──────────────────────────────────────────

def test_open_to_closed_rejected():
    """Cannot skip states — OPEN → CLOSED must be rejected."""
    wi = make_work_item(WorkItemStatus.OPEN)
    with pytest.raises(InvalidStateTransitionError):
        sm.transition(wi, WorkItemStatus.CLOSED)


def test_open_to_resolved_rejected():
    """Cannot skip INVESTIGATING."""
    wi = make_work_item(WorkItemStatus.OPEN)
    with pytest.raises(InvalidStateTransitionError):
        sm.transition(wi, WorkItemStatus.RESOLVED)


def test_investigating_to_closed_rejected():
    """Cannot close without resolving first."""
    wi = make_work_item(WorkItemStatus.INVESTIGATING)
    with pytest.raises(InvalidStateTransitionError):
        sm.transition(wi, WorkItemStatus.CLOSED)


def test_closed_to_any_rejected():
    """Closed is a terminal state — no transitions allowed."""
    rca = make_rca()
    wi = make_work_item(WorkItemStatus.CLOSED, rca=rca)
    with pytest.raises(InvalidStateTransitionError):
        sm.transition(wi, WorkItemStatus.INVESTIGATING)
    with pytest.raises(InvalidStateTransitionError):
        sm.transition(wi, WorkItemStatus.RESOLVED)


# ──────────────────────────────────────────
# RCA Validation Tests
# ──────────────────────────────────────────

def test_close_without_rca_raises_missing_rca_error():
    """
    Core requirement from spec:
    System must reject CLOSED if RCA is missing.
    """
    wi = make_work_item(WorkItemStatus.RESOLVED, rca=None)
    with pytest.raises(MissingRCAError) as exc_info:
        sm.transition(wi, WorkItemStatus.CLOSED)
    assert "Root Cause Analysis" in str(exc_info.value)


def test_close_with_complete_rca_succeeds():
    """Valid RCA allows closing."""
    rca = make_rca(start_offset_hours=-3, end_offset_hours=-1)
    wi = make_work_item(WorkItemStatus.RESOLVED, rca=rca)
    sm.transition(wi, WorkItemStatus.CLOSED)
    assert wi.status == WorkItemStatus.CLOSED


def test_mttr_calculated_correctly():
    """
    MTTR = incident_end - work_item.created_at in minutes.
    Work item created 2 hours ago, incident ended 1 hour ago → ~60 min MTTR.
    """
    rca = make_rca(start_offset_hours=-2, end_offset_hours=-1)
    wi = make_work_item(WorkItemStatus.RESOLVED, rca=rca)
    wi.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
    sm.transition(wi, WorkItemStatus.CLOSED)
    # Should be approximately 60 minutes (allow ±2 min for test execution time)
    assert 58 <= wi.mttr_minutes <= 62


def test_mttr_positive_with_real_timestamps():
    """MTTR must always be positive when timestamps are real."""
    rca = make_rca(start_offset_hours=-5, end_offset_hours=-2)
    wi = make_work_item(WorkItemStatus.RESOLVED, rca=rca)
    wi.created_at = datetime.now(timezone.utc) - timedelta(hours=5)
    sm.transition(wi, WorkItemStatus.CLOSED)
    assert wi.mttr_minutes > 0