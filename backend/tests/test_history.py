import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from app.models.sql_models import WorkItem, WorkItemStatus, Severity, ComponentType, RCARecord
from app.services.state_machine import state_machine
from app.api.workitems import list_closed_work_items, get_history_stats, get_similar_past_incidents

@pytest.mark.asyncio
async def test_reopen_closed_incident():
    """Verify that a CLOSED incident can be transitioned to INVESTIGATING (reopened)."""
    wi = MagicMock()
    wi.status = WorkItemStatus.CLOSED
    wi.closed_at = datetime.now(timezone.utc)
    wi.closed_by = "admin_user"
    
    # Trigger transition CLOSED -> INVESTIGATING
    state_machine.transition(wi, WorkItemStatus.INVESTIGATING)
    
    assert wi.status == WorkItemStatus.INVESTIGATING
    assert wi.closed_at is None
    assert wi.closed_by is None


@pytest.mark.asyncio
async def test_history_stats_aggregation():
    """Verify that get_history_stats compiles statistics properly."""
    mock_session = AsyncMock()
    
    # Mock return values for:
    # 1. Total and Avg MTTR
    # 2. Severity distribution
    # 3. Monthly closures
    mock_res_1 = MagicMock()
    mock_res_1.one.return_value = MagicMock(total=15, avg_mttr=42.5)
    
    mock_res_2 = MagicMock()
    mock_res_2.all.return_value = [
        MagicMock(severity=Severity.P0, count=3),
        MagicMock(severity=Severity.P1, count=12)
    ]
    
    mock_res_3 = MagicMock()
    mock_res_3.all.return_value = [
        MagicMock(month=datetime(2026, 5, 1), count=10),
        MagicMock(month=datetime(2026, 4, 1), count=5)
    ]
    
    mock_session.execute.side_effect = [mock_res_1, mock_res_2, mock_res_3]
    
    stats = await get_history_stats(session=mock_session)
    
    assert stats["total_closed"] == 15
    assert stats["avg_mttr_minutes"] == 42.5
    assert stats["severity_distribution"]["P0"] == 3
    assert stats["severity_distribution"]["P1"] == 12
    assert len(stats["monthly_closures"]) == 2
    assert stats["monthly_closures"][0]["month"] == "2026-05"


@pytest.mark.asyncio
async def test_list_closed_work_items():
    """Verify that list_closed_work_items executes queries with the correct filters."""
    mock_session = AsyncMock()
    
    # Mock count total and items execution
    mock_count_res = MagicMock()
    mock_count_res.scalar.return_value = 1
    
    mock_items_res = MagicMock()
    wi_mock = MagicMock(spec=WorkItem)
    wi_mock.id = uuid.uuid4()
    wi_mock.status = WorkItemStatus.CLOSED
    wi_mock.severity = Severity.P1
    wi_mock.component_type = ComponentType.API
    wi_mock.component_id = "API_GATEWAY"
    wi_mock.title = "Incident Gateway Fail"
    wi_mock.description = "Timeout"
    wi_mock.created_at = datetime.now()
    wi_mock.updated_at = datetime.now()
    wi_mock.closed_at = datetime.now()
    wi_mock.closed_by = None
    wi_mock.archived_reason = None
    wi_mock.rca_submitted_at = None
    wi_mock.rca = None
    mock_items_res.scalars().all.return_value = [wi_mock]
    
    mock_session.execute.side_effect = [mock_count_res, mock_items_res]
    
    res = await list_closed_work_items(
        severity="P1",
        component_id="API_GATEWAY",
        page=1,
        page_size=20,
        session=mock_session
    )
    
    assert res.total == 1
    assert len(res.items) == 1
    assert res.items[0].component_id == "API_GATEWAY"


@pytest.mark.asyncio
async def test_similar_past_incidents():
    """Verify that the similar past incidents endpoint retrieves past closed RCAs correctly."""
    mock_session = AsyncMock()
    
    # Target active incident
    wi_active = MagicMock(spec=WorkItem)
    wi_active.id = uuid.UUID("440026e6-12ef-4573-9bf2-601937ff22ad")
    wi_active.component_id = "AUTH_SERVICE"
    wi_active.component_type = ComponentType.API
    
    # Past similar incident
    wi_past = MagicMock(spec=WorkItem)
    wi_past.id = uuid.uuid4()
    wi_past.title = "Auth crash"
    wi_past.component_id = "AUTH_SERVICE"
    wi_past.component_type = ComponentType.API
    wi_past.severity = Severity.P1
    wi_past.closed_at = datetime.now()
    wi_past.mttr_minutes = 20.0
    
    # Past similar RCA
    rca_past = MagicMock(spec=RCARecord)
    rca_past.root_cause_category = MagicMock(value="APPLICATION")
    rca_past.fix_applied = "Upgraded libraries"
    rca_past.prevention_steps = "Added memory limits"
    wi_past.rca = rca_past
    
    # Mock get_work_item_or_404 behavior and query results
    mock_get_wi = AsyncMock(return_value=wi_active)
    
    mock_query_res = MagicMock()
    mock_query_res.scalars().all.return_value = [wi_past]
    
    mock_query_empty = MagicMock()
    mock_query_empty.scalars().all.return_value = []
    
    # Mock sequential calls: first by component_id, second by component_type
    mock_session.execute.side_effect = [mock_query_res, mock_query_empty]
    
    with patch("app.api.workitems.get_work_item_or_404", mock_get_wi):
        similar = await get_similar_past_incidents(
            work_item_id=str(wi_active.id),
            limit=3,
            session=mock_session
        )
        
        assert len(similar) == 1
        assert similar[0]["title"] == "Auth crash"
        assert similar[0]["rca"]["root_cause_category"] == "APPLICATION"
        assert similar[0]["rca"]["fix_applied"] == "Upgraded libraries"
