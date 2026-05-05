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
    JWT_EXPIRE_MINUTES: int = 60 * 24

    # Auth
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    VIEWER_USERNAME: str = "viewer"
    VIEWER_PASSWORD: str = "viewer123"

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 1000
    RATE_LIMIT_WINDOW: int = 60

    # Redis Streams
    STREAM_NAME: str = "ims:signals"
    STREAM_CONSUMER_GROUP: str = "ims_workers"
    STREAM_MAX_LEN: int = 100_000

    # Debounce
    DEBOUNCE_WINDOW_SECONDS: int = 10
    DEBOUNCE_THRESHOLD: int = 100

    # Observability
    METRICS_INTERVAL_SECONDS: int = 5

    # ── AI Runbook Suggester ──────────────────────────────
    # Which provider to use: gemini | claude | openai | ollama
    AI_PROVIDER: str = "gemini"

    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Claude (future)
    CLAUDE_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"

    # OpenAI (future)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Ollama (future — local model, no API key needed)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"
    # ─────────────────────────────────────────────────────

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()