import time
import structlog
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.postgres import init_db, close_db
from app.db.mongo import init_mongo, close_mongo
from app.db.redis_client import init_redis, close_redis, get_redis
from app.models.schemas import HealthResponse, ServiceHealth
from app.services.worker import start_worker, stop_worker

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer(),
    ]
)

logger = structlog.get_logger(__name__)
_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Incident Management System",
                version=settings.APP_VERSION,
                environment=settings.ENVIRONMENT)
    await init_redis()
    await init_mongo()
    await init_db()
    await start_worker()
    logger.info("All services started")
    yield
    logger.info("Shutting down IMS...")
    await stop_worker()
    await close_db()
    await close_mongo()
    await close_redis()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Mission-Critical Incident Management System",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register all routers ──
from app.api.signals import router as signals_router
from app.api.workitems import router as workitems_router
from app.api.auth import router as auth_router
from app.api.metrics import router as metrics_router

app.include_router(auth_router)
app.include_router(signals_router)
app.include_router(workitems_router)
app.include_router(metrics_router)


@app.get("/health", response_model=HealthResponse, tags=["Observability"])
async def health_check():
    services = []

    try:
        from app.db.postgres import engine
        import sqlalchemy
        t0 = time.time()
        async with engine.connect() as conn:
            await conn.execute(sqlalchemy.text("SELECT 1"))
        services.append(ServiceHealth(name="postgresql", status="healthy",
                                      latency_ms=round((time.time()-t0)*1000, 2)))
    except Exception as e:
        services.append(ServiceHealth(name="postgresql", status="down", detail=str(e)))

    try:
        from app.db.mongo import get_mongo_db
        t0 = time.time()
        db = get_mongo_db()
        await db.client.admin.command("ping")
        services.append(ServiceHealth(name="mongodb", status="healthy",
                                      latency_ms=round((time.time()-t0)*1000, 2)))
    except Exception as e:
        services.append(ServiceHealth(name="mongodb", status="down", detail=str(e)))

    try:
        t0 = time.time()
        redis = get_redis()
        await redis.ping()
        services.append(ServiceHealth(name="redis", status="healthy",
                                      latency_ms=round((time.time()-t0)*1000, 2)))
    except Exception as e:
        services.append(ServiceHealth(name="redis", status="down", detail=str(e)))

    all_healthy = all(s.status == "healthy" for s in services)
    any_down = any(s.status == "down" for s in services)
    overall = "healthy" if all_healthy else ("degraded" if not any_down else "down")

    return HealthResponse(
        status=overall,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
        services=services,
        uptime_seconds=round(time.time() - _start_time, 2),
    )


@app.get("/", tags=["Root"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
    }