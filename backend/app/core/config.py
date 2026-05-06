"""
Centralised settings using pydantic-settings.

Rules:
- No secret has a default value in production.
- Settings are validated at startup; a missing required secret causes
  an immediate, loud failure rather than a runtime error mid-request.
- Use @lru_cache so settings are instantiated only once per process.
"""

from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field, HttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",          # silently ignore unknown env vars
    )

    # ── Application ───────────────────────────────────────────
    APP_NAME:    str = "Incident Management System"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG:       bool = False

    # ── PostgreSQL ────────────────────────────────────────────
    POSTGRES_URL: str  # required — no default

    # ── MongoDB ───────────────────────────────────────────────
    MONGO_URL:     str   # required — no default
    MONGO_DB_NAME: str = "ims_db"

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379"

    # ── JWT ───────────────────────────────────────────────────
    JWT_SECRET:     str   # required — no default
    JWT_ALGORITHM:  str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60   # 1 hour (was 24h — reduced for security)

    # ── Static Users ──────────────────────────────────────────
    # In production these should be backed by a users table + registration flow.
    ADMIN_USERNAME:  str = "admin"
    ADMIN_PASSWORD:  str   # required — no default
    VIEWER_USERNAME: str = "viewer"
    VIEWER_PASSWORD: str   # required — no default

    # ── Rate Limiting ─────────────────────────────────────────
    RATE_LIMIT_REQUESTS: int = 1000
    RATE_LIMIT_WINDOW:   int = 60

    # ── Redis Streams ─────────────────────────────────────────
    STREAM_NAME:           str = "ims:signals"
    STREAM_CONSUMER_GROUP: str = "ims_workers"
    STREAM_MAX_LEN:        int = 100_000

    # ── Debounce ──────────────────────────────────────────────
    DEBOUNCE_WINDOW_SECONDS: int = 10
    DEBOUNCE_THRESHOLD:      int = 100

    # ── Observability ─────────────────────────────────────────
    METRICS_INTERVAL_SECONDS: int = 5

    # ── Alerting Integrations ─────────────────────────────────
    # Optional: leave empty to disable Slack alerts
    SLACK_WEBHOOK_URL: Optional[str] = None

    # ── AI Provider ───────────────────────────────────────────
    AI_PROVIDER: Literal["gemini", "openai", "claude", "ollama", "groq"] = "gemini"

    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL:   str = "gemini-2.0-flash"

    # Groq
    GROQ_API_KEY: str = ""
    GROQ_MODEL:   str = "llama-3.3-70b-versatile"

    # Claude
    CLAUDE_API_KEY: str = ""
    CLAUDE_MODEL:   str = "claude-3-5-sonnet-20241022"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL:   str = "gpt-4o-mini"

    # Ollama (local, no key)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL:    str = "llama3"

    # ── Validators ────────────────────────────────────────────

    @field_validator("JWT_SECRET")
    @classmethod
    def jwt_secret_must_be_strong(cls, v: str) -> str:
        """
        Prevent the well-known placeholder from being used in production.
        In development, a short secret is allowed (but warned about).
        """
        blocked = {
            "super_secret_jwt_key_change_in_production",
            "secret",
            "changeme",
            "password",
            "CHANGE_ME_generate_with_secrets_token_hex_32",
        }
        if v.lower() in blocked:
            raise ValueError(
                "JWT_SECRET is set to a known insecure placeholder. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        if len(v) < 32:
            raise ValueError(
                f"JWT_SECRET is too short ({len(v)} chars). "
                "Minimum 32 characters required."
            )
        return v

    @model_validator(mode="after")
    def validate_ai_provider_key(self) -> "Settings":
        """Warn at startup if the configured AI provider has no API key."""
        provider_key_map = {
            "gemini": self.GEMINI_API_KEY,
            "openai": self.OPENAI_API_KEY,
            "claude": self.CLAUDE_API_KEY,
            "groq": self.GROQ_API_KEY,
        }
        # Ollama is local — no key needed
        if self.AI_PROVIDER != "ollama":
            key = provider_key_map.get(self.AI_PROVIDER, "")
            if not key:
                import warnings
                warnings.warn(
                    f"AI_PROVIDER is '{self.AI_PROVIDER}' but "
                    f"{self.AI_PROVIDER.upper()}_API_KEY is not set. "
                    "The /api/v1/ai/runbook endpoint will return 503.",
                    stacklevel=2,
                )
        return self

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def sqlalchemy_echo(self) -> bool:
        """Only echo SQL in development — never in production (leaks data)."""
        return self.DEBUG and not self.is_production


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()