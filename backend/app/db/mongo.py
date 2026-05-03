import structlog
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Module-level client — initialized on startup
_mongo_client: AsyncIOMotorClient | None = None
_mongo_db: AsyncIOMotorDatabase | None = None


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def init_mongo():
    global _mongo_client, _mongo_db

    _mongo_client = AsyncIOMotorClient(settings.MONGO_URL)
    _mongo_db = _mongo_client[settings.MONGO_DB_NAME]

    # Verify connection
    await _mongo_client.admin.command("ping")

    # Create indexes for fast querying
    await _mongo_db.signals.create_index([("component_id", 1)])
    await _mongo_db.signals.create_index([("work_item_id", 1)])
    await _mongo_db.signals.create_index([("timestamp", -1)])  # latest first
    await _mongo_db.signals.create_index([("severity", 1)])

    logger.info("MongoDB connected and indexes created")


async def close_mongo():
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()
        logger.info("MongoDB connection closed")


def get_mongo_db() -> AsyncIOMotorDatabase:
    if _mongo_db is None:
        raise RuntimeError("MongoDB not initialized. Call init_mongo() first.")
    return _mongo_db