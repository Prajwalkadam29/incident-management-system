import uuid
import json
import time
import structlog
from typing import Optional

from app.db.redis_client import get_redis
from app.core.config import settings
from app.models.schemas import SignalIngestionRequest

logger = structlog.get_logger(__name__)

# We use a Redis counter for throughput metrics so it works across multi-process deployments.
# (Previously this was a global variable, which is unsafe in gunicorn/uvicorn workers).
REDIS_METRICS_KEY = "ims:metrics:signal_count"


async def ingest_signal(signal: SignalIngestionRequest) -> str:
    """
    Push a signal onto the Redis Stream (non-blocking).
    Returns the signal_id (Redis stream entry ID).

    This is the ONLY thing the HTTP handler does — push to stream and return.
    All heavy processing (debounce, DB writes) happens in the worker.
    """

    redis = get_redis()
    signal_id = str(uuid.uuid4())

    # Inject OpenTelemetry context for distributed tracing across Redis boundary
    from opentelemetry.propagate import inject
    trace_headers = {}
    inject(trace_headers)

    metadata = signal.metadata or {}
    metadata["trace_headers"] = trace_headers

    # Serialize payload for Redis Stream
    # Redis Streams store flat key-value pairs (no nested dicts)
    stream_payload = {
        "signal_id":      signal_id,
        "component_id":   signal.component_id,
        "component_type": signal.component_type.value,
        "error_code":     signal.error_code,
        "message":        signal.message,
        "severity":       signal.severity.value,
        "metadata":       json.dumps(metadata),
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

    # Multi-process safe counter
    await redis.incr(REDIS_METRICS_KEY)

    logger.debug(
        "Signal queued to stream",
        signal_id=signal_id,
        component_id=signal.component_id,
        severity=signal.severity.value,
    )

    return signal_id


async def get_and_reset_signal_count() -> int:
    """Called by the metrics loop every 5 seconds. Multi-process safe."""
    redis = get_redis()
    
    # Atomically GET and DELETE the counter
    count = await redis.getdel(REDIS_METRICS_KEY)
    
    return int(count) if count else 0