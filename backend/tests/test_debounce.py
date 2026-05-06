import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from app.services.worker import maybe_debounce_signal

@pytest.mark.asyncio
async def test_debounce_creates_work_item_on_first_signal():
    mock_redis = AsyncMock()
    mock_redis.setnx.return_value = True  # Successfully acquired lock
    
    with patch("app.services.worker.get_redis", return_value=mock_redis):
        with patch("app.services.worker.create_work_item_in_db", new_callable=AsyncMock) as mock_create_db:
            mock_create_db.return_value = "new_work_item_id"
            
            payload = {
                "component_id": "TEST_COMP_01",
                "severity": "P1",
                "component_type": "API",
                "error_code": "TEST_ERR",
                "message": "Test error",
                "metadata": "{}"
            }
            
            work_item_id = await maybe_debounce_signal(payload, "signal-123")
            
            assert work_item_id == "new_work_item_id"
            mock_redis.setnx.assert_called_once()
            mock_create_db.assert_called_once()


@pytest.mark.asyncio
async def test_debounce_skips_creation_if_locked():
    mock_redis = AsyncMock()
    mock_redis.setnx.return_value = False  # Lock already exists
    mock_redis.get.return_value = b"existing_work_item_id"
    
    with patch("app.services.worker.get_redis", return_value=mock_redis):
        with patch("app.services.worker.update_work_item_signal_count", new_callable=AsyncMock) as mock_update:
            payload = {
                "component_id": "TEST_COMP_01",
                "severity": "P1",
                "component_type": "API",
                "error_code": "TEST_ERR",
                "message": "Test error",
                "metadata": "{}"
            }
            
            work_item_id = await maybe_debounce_signal(payload, "signal-123")
            
            assert work_item_id == "existing_work_item_id"
            mock_redis.setnx.assert_called_once()
            mock_update.assert_called_once_with("existing_work_item_id")
