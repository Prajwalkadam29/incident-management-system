FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Copy requirements first for layer caching — only re-installs when requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Make the entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Expose FastAPI port
EXPOSE 8000

# Entrypoint: runs Alembic migrations then starts uvicorn
# Alembic config (alembic.ini) is in /app, so migrations run from /app
ENTRYPOINT ["/app/entrypoint.sh"]