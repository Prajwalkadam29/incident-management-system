"""
conftest.py — pytest session-level fixtures.

IMPORTANT: This module is loaded by pytest BEFORE any test module is imported.
We use it to inject the minimum required environment variables so that
`app.core.config.Settings` can be instantiated without a real `.env` file or
a running database.

These are TEST-ONLY values — no real database is connected during unit tests.
All infrastructure-level tests (integration, e2e) should use a separate
test environment with real services via Docker Compose.
"""

import os

# ── Inject minimum required env vars before any app module is imported ──
# This avoids ValidationError from pydantic-settings when required fields
# (POSTGRES_URL, MONGO_URL, JWT_SECRET, etc.) are not set in the shell env.
_TEST_ENV_DEFAULTS = {
    "POSTGRES_URL":    "postgresql+asyncpg://test:test@localhost:5432/test_db",
    "MONGO_URL":       "mongodb://test:test@localhost:27017/test_db",
    "REDIS_URL":       "redis://localhost:6379",
    "JWT_SECRET":      "test_jwt_secret_minimum_32_chars_long_00",
    "ADMIN_PASSWORD":  "TestAdmin@123",
    "VIEWER_PASSWORD": "TestViewer@123",
    "ENVIRONMENT":     "development",
}

for key, value in _TEST_ENV_DEFAULTS.items():
    os.environ.setdefault(key, value)
