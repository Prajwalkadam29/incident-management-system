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
    echo=settings.sqlalchemy_echo,
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


# --- DB connection verification (schema managed by Alembic) ---
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
)
async def init_db():
    """
    Verify PostgreSQL is reachable and the schema is in place.

    Schema creation/migration is handled by Alembic — entrypoint.sh runs
    'alembic upgrade head' before this process starts. This function only
    confirms connectivity. It does NOT call create_all().
    """
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("PostgreSQL connection verified — schema managed by Alembic")


async def close_db():
    await engine.dispose()
    logger.info("PostgreSQL connection pool closed")