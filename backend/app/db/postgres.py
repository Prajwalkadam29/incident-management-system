import structlog
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
import logging

from app.core.config import settings

logger = structlog.get_logger(__name__)

# --- SQLAlchemy Async Engine ---
engine = create_async_engine(
    settings.POSTGRES_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,   # verify connection is alive before using from pool
)

# Session factory
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# --- Base class for all ORM models ---
class Base(DeclarativeBase):
    pass


# --- Dependency for FastAPI routes ---
async def get_db_session() -> AsyncSession:
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# --- DB init with retry (resilience) ---
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
)
async def init_db():
    """Create all tables. Retries on failure (e.g., Postgres not ready yet)."""
    async with engine.begin() as conn:
        # Import here to ensure models are registered on Base.metadata
        from app.models.sql_models import WorkItem, RCARecord  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
    logger.info("PostgreSQL tables created successfully")


async def close_db():
    await engine.dispose()
    logger.info("PostgreSQL connection pool closed")