import pytest
from unittest.mock import AsyncMock, patch
from app.services.worker import get_or_create_debounce_lock, get_existing_work_item_id

@pytest.mark.asyncio
async def test_get_or_create_debounce_lock_first_signal():
    mock_redis = AsyncMock()
    mock_redis.set.return_value = True  # Successfully acquired lock (Redis set with NX returns True/OK)
    
    with patch("app.services.worker.get_redis", return_value=mock_redis):
        work_item_id = await get_or_create_debounce_lock("TEST_COMP_01")
        assert work_item_id is not None
        mock_redis.set.assert_called_once()


@pytest.mark.asyncio
async def test_get_or_create_debounce_lock_subsequent_signal():
    mock_redis = AsyncMock()
    mock_redis.set.return_value = False  # Lock already exists
    mock_redis.get.return_value = b"existing_id_123"
    
    with patch("app.services.worker.get_redis", return_value=mock_redis):
        work_item_id = await get_or_create_debounce_lock("TEST_COMP_01")
        assert work_item_id is None  # returns None, caller looks up existing
        mock_redis.set.assert_called_once()


@pytest.mark.asyncio
async def test_get_existing_work_item_id():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = b"existing_id_123"
    
    with patch("app.services.worker.get_redis", return_value=mock_redis):
        work_item_id = await get_existing_work_item_id("TEST_COMP_01")
        assert work_item_id == b"existing_id_123"
        mock_redis.get.assert_called_once_with("ims:debounce:TEST_COMP_01")
