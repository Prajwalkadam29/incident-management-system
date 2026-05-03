import uuid
import json
import time
import structlog
from typing import Optional

from app.db.redis_client import get_redis
from app.core.config import settings
from app.models.schemas import SignalIngestionRequest

logger = structlog.get_logger(__name__)

# In-memory counter for throughput metrics (reset every interval)
_signal_counter = 0
_counter_reset_time = time.time()


async def ingest_signal(signal: SignalIngestionRequest) -> str:
    """
    Push a signal onto the Redis Stream (non-blocking).
    Returns the signal_id (Redis stream entry ID).

    This is the ONLY thing the HTTP handler does — push to stream and return.
    All heavy processing (debounce, DB writes) happens in the worker.
    """
    global _signal_counter

    redis = get_redis()
    signal_id = str(uuid.uuid4())

    # Serialize payload for Redis Stream
    # Redis Streams store flat key-value pairs (no nested dicts)
    stream_payload = {
        "signal_id":      signal_id,
        "component_id":   signal.component_id,
        "component_type": signal.component_type.value,
        "error_code":     signal.error_code,
        "message":        signal.message,
        "severity":       signal.severity.value,
        "metadata":       json.dumps(signal.metadata or {}),
        "timestamp":      str(time.time()),
    }

    # XADD with MAXLEN to cap memory usage (backpressure)
    # MAXLEN ~ means "approximately" — faster than exact trimming
    await redis.xadd(
        name=settings.STREAM_NAME,
        fields=stream_payload,
        maxlen=settings.STREAM_MAX_LEN,
        approximate=True,
    )

    _signal_counter += 1

    logger.debug(
        "Signal queued to stream",
        signal_id=signal_id,
        component_id=signal.component_id,
        severity=signal.severity.value,
    )

    return signal_id


def get_and_reset_signal_count() -> int:
    """Called by the metrics loop every 5 seconds."""
    global _signal_counter, _counter_reset_time
    count = _signal_counter
    _signal_counter = 0
    _counter_reset_time = time.time()
    return count