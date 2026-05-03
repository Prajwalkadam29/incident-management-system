import structlog
from redis.asyncio import Redis, ConnectionPool
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = structlog.get_logger(__name__)

_redis_pool: ConnectionPool | None = None
_redis_client: Redis | None = None


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def init_redis():
    global _redis_pool, _redis_client

    _redis_pool = ConnectionPool.from_url(
        settings.REDIS_URL,
        max_connections=50,
        decode_responses=True,   # return strings not bytes
    )
    _redis_client = Redis(connection_pool=_redis_pool)

    # Verify connection
    await _redis_client.ping()

    # Create the Redis Stream consumer group (ignore if already exists)
    try:
        await _redis_client.xgroup_create(
            name=settings.STREAM_NAME,
            groupname=settings.STREAM_CONSUMER_GROUP,
            id="0",          # start from the very beginning
            mkstream=True,   # create stream if it doesn't exist
        )
        logger.info("Redis Stream consumer group created",
                    stream=settings.STREAM_NAME,
                    group=settings.STREAM_CONSUMER_GROUP)
    except Exception as e:
        if "BUSYGROUP" in str(e):
            # Group already exists — totally fine on restart
            logger.info("Redis Stream consumer group already exists, skipping")
        else:
            raise

    logger.info("Redis connected successfully")


async def close_redis():
    global _redis_client, _redis_pool
    if _redis_client:
        await _redis_client.aclose()
    if _redis_pool:
        await _redis_pool.aclose()
    logger.info("Redis connection closed")


def get_redis() -> Redis:
    if _redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis_client