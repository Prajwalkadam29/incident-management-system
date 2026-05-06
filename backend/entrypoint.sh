#!/bin/bash
# ============================================================
# IMS Backend Entrypoint
# Runs Alembic migrations before starting the application.
# This ensures the schema is always up-to-date on container start.
# ============================================================

set -e  # Exit immediately if any command fails

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  IMS Backend Starting"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "[1/2] Running Alembic migrations..."
alembic upgrade head
echo "      ✅ Migrations complete"

echo "[2/2] Starting FastAPI application..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# exec replaces the shell process — signals (SIGTERM, SIGINT) go
# directly to uvicorn for clean graceful shutdown
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --reload-dir /app/app
