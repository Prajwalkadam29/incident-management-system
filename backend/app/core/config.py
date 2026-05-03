from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Incident Management System"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # PostgreSQL
    POSTGRES_URL: str = "postgresql+asyncpg://ims_user:ims_password@localhost:5432/ims_db"

    # MongoDB
    MONGO_URL: str = "mongodb://ims_user:ims_password@localhost:27017/ims_db?authSource=admin"
    MONGO_DB_NAME: str = "ims_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # JWT
    JWT_SECRET: str = "super_secret_jwt_key_change_in_production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 1000   # max requests
    RATE_LIMIT_WINDOW: int = 60       # per 60 seconds per IP

    # Redis Streams
    STREAM_NAME: str = "ims:signals"
    STREAM_CONSUMER_GROUP: str = "ims_workers"
    STREAM_MAX_LEN: int = 100_000     # cap stream length in memory

    # Debounce
    DEBOUNCE_WINDOW_SECONDS: int = 10
    DEBOUNCE_THRESHOLD: int = 100

    # Observability
    METRICS_INTERVAL_SECONDS: int = 5

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Convenience singleton — import this everywhere
settings = get_settings()