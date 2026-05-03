# Incident Management System (IMS)

A mission-critical, production-grade Incident Management System built for
monitoring distributed infrastructure stacks — APIs, MCP Hosts, distributed
caches, async queues, RDBMS, and NoSQL stores.

Built as part of the Zeotap Infrastructure / SRE Intern assignment.

**GitHub:** https://github.com/Prajwalkadam29/incident-management-system

---

## Table of Contents

- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Features](#features)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Design Patterns](#design-patterns)
- [Backpressure Strategy](#backpressure-strategy)
- [Observability](#observability)
- [Security](#security)
- [Testing](#testing)
- [Simulating an Outage](#simulating-an-outage)
- [Non-Functional Additions](#non-functional-additions)

---

## Architecture

```architecture
                ┌─────────────────────────────────┐
                │         Signal Producers        │
                │  (APIs, Caches, DBs, MCP Hosts) │
                └──────────────┬──────────────────┘
                               │ HTTP POST /api/v1/signals/ingest
                               │ (Rate Limited — 1000 req/min per IP)
                               ▼
                ┌─────────────────────────────────┐
                │     FastAPI Ingestion Layer     │
                │  • Pydantic validation          │
                │  • Token bucket rate limiter    │
                │  • Returns 202 immediately      │
                └──────────────┬──────────────────┘
                               │ Non-blocking XADD
                               ▼
                ┌─────────────────────────────────┐
                │        Redis Streams            │  ← BACKPRESSURE BUFFER
                │   MAXLEN ~100,000 entries       │
                │   Consumer Group: ims_workers   │
                └──────────────┬──────────────────┘
                               │ XREADGROUP (batch 50)
                               ▼
                ┌─────────────────────────────────┐
                │      Async Worker Pool          │
                │  • Debounce (Redis SETNX + TTL) │
                │  • Alerting Strategy Pattern    │
                │  • Work Item State Machine      │
                │  • Retry logic (tenacity)       │
                └──────┬───────────────┬──────────┘
                       │               │
          ┌────────────▼───┐    ┌──────▼──────────┐
          │   MongoDB      │    │   PostgreSQL    │
          │  Raw Signals   │    │   Work Items    │
          │  (Audit Log)   │    │   RCA Records   │
          └────────────────┘    └──────┬──────────┘
                                        │
                          ┌─────────────▼──────────┐
                          │      Redis Cache       │
                          │  • Dashboard hot-path  │
                          │  • Debounce locks      │
                          │  • TimeSeries metrics  │
                          └─────────────┬──────────┘
                                        │
                          ┌─────────────▼──────────┐
                          │     React Frontend     │
                          │ • Live incident feed   │
                          │ • Incident detail view │
                          │ • RCA submission form  │
                          └────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Reason |
|---|---|---|
| **API Framework** | FastAPI + Uvicorn | Async-native, auto OpenAPI docs, high throughput |
| **Message Buffer** | Redis Streams | Durable in-memory queue, consumer groups, backpressure |
| **Cache / Hot-path** | Redis (redis-stack) | Sub-millisecond dashboard reads, debounce locks |
| **Source of Truth** | PostgreSQL 15 | ACID transactions for Work Item state transitions |
| **Audit Log** | MongoDB 6 | Flexible schema, high-volume raw signal writes |
| **Auth** | JWT (python-jose) | Stateless, scalable, industry standard |
| **Resilience** | Tenacity | Exponential backoff retry on all DB writes |
| **Observability** | Prometheus + structlog | Industry-standard metrics + structured logging |
| **Containerisation** | Docker + Docker Compose | One-command setup, production parity |
| **Frontend** | React + Vite + Tailwind | Fast, responsive, modern UI |

---

## Features

### Core
- **High-throughput ingestion** — non-blocking signal intake via Redis Streams
- **Debounce logic** — 100 signals for the same component in 10s → 1 Work Item
- **Incident lifecycle** — OPEN → INVESTIGATING → RESOLVED → CLOSED (state machine)
- **Mandatory RCA** — system rejects CLOSED transition without a complete RCA
- **MTTR calculation** — automatically computed on incident close
- **Multi-store persistence** — raw signals in MongoDB, Work Items in PostgreSQL, hot-path in Redis

### Resilience
- **Backpressure** — Redis Streams act as bounded buffer; ingestion never crashes even if DB is slow
- **Rate limiting** — sliding window limiter (1000 req/60s per IP) backed by Redis
- **Retry logic** — exponential backoff (up to 3 attempts) on all PostgreSQL and MongoDB writes
- **Selective ACK** — failed signals stay in Redis PEL for reprocessing; only successful ones are ACKed
- **Graceful shutdown** — worker drains in-flight messages before process exits

### Observability
- **`/health`** — per-service health check with latency (PostgreSQL, MongoDB, Redis)
- **`/metrics`** — Prometheus-compatible endpoint with custom IMS metrics
- **Throughput logging** — signals/sec printed to console every 5 seconds
- **Structured logging** — all logs in structured format via structlog

### Security
- **JWT authentication** — Bearer token auth on all write endpoints
- **Role-based access** — admin and viewer roles
- **CORS** — configured for frontend origin only

---

## Project Structure

```
ims/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py          # Login, /me endpoints
│   │   │   ├── metrics.py       # Prometheus /metrics endpoint
│   │   │   ├── signals.py       # Signal ingestion + query
│   │   │   └── workitems.py     # Work Item CRUD + RCA
│   │   ├── core/
│   │   │   ├── config.py        # Centralised settings (pydantic-settings)
│   │   │   ├── rate_limiter.py  # Sliding window rate limiter
│   │   │   └── security.py      # JWT creation + verification
│   │   ├── db/
│   │   │   ├── mongo.py         # Motor async client + indexes
│   │   │   ├── postgres.py      # SQLAlchemy async engine + Base
│   │   │   └── redis_client.py  # Redis async pool + stream group init
│   │   ├── models/
│   │   │   ├── schemas.py       # Pydantic request/response models
│   │   │   └── sql_models.py    # SQLAlchemy ORM models
│   │   ├── services/
│   │   │   ├── alerting.py      # Strategy pattern — P0/P1/P2 alerts
│   │   │   ├── ingestion.py     # Redis Streams producer
│   │   │   ├── state_machine.py # State pattern — Work Item lifecycle
│   │   │   └── worker.py        # Consumer group + debounce + DB writes
│   │   └── main.py              # FastAPI app, lifespan, router registration
│   ├── tests/
│   │   └── test_rca_validation.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/                 # Axios API client
│   │   ├── components/          # Reusable UI components
│   │   └── pages/               # Dashboard, Incident Detail, Login
│   ├── Dockerfile
│   └── package.json
├── scripts/
│   └── simulate_outage.py       # Mock RDBMS → MCP cascade scenario
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## Quick Start

### Prerequisites
- Docker Desktop (running)
- Git

### 1. Clone the repository

```bash
git clone https://github.com/Prajwalkadam29/incident-management-system.git
cd incident-management-system
```

### 2. Start all services

```bash
docker compose up --build
```

This starts PostgreSQL, MongoDB, Redis (with RedisInsight), and the FastAPI backend.
Wait for this line in the logs before proceeding:

✅ All services started
Worker started   consumer=worker-xxxx   stream=ims:signals

### 3. Verify everything is healthy

```bash
curl http://localhost:8000/health
```

Expected:
```json
{
  "status": "healthy",
  "services": [
    {"name": "postgresql", "status": "healthy", "latency_ms": 1.2},
    {"name": "mongodb",    "status": "healthy", "latency_ms": 0.9},
    {"name": "redis",      "status": "healthy", "latency_ms": 0.3}
  ]
}
```

### 4. Open the API docs

http://localhost:8000/docs

### 5. (Optional) RedisInsight dashboard

http://localhost:8001

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/login` | Get JWT token |
| GET | `/api/v1/auth/me` | Get current user |

**Login:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

Default credentials:

| Username | Password | Role |
|---|---|---|
| admin | admin123 | admin |
| viewer | viewer123 | viewer |

---

### Signals

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/signals/ingest` | Ingest a signal (202 Accepted) |
| GET | `/api/v1/signals/` | Query raw signals from MongoDB |

**Ingest a signal:**
```bash
curl -X POST http://localhost:8000/api/v1/signals/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "component_id": "DB_PRIMARY_01",
    "component_type": "RDBMS",
    "error_code": "CONNECTION_REFUSED",
    "message": "Primary database connection refused",
    "severity": "P0",
    "metadata": {"host": "10.0.1.5", "region": "us-east-1"}
  }'
```

**Supported component types:** `RDBMS`, `API`, `CACHE`, `QUEUE`, `NOSQL`, `MCP_HOST`

**Severity levels:** `P0` (Critical), `P1` (High), `P2` (Medium), `P3` (Low)

---

### Work Items

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/workitems/` | List all Work Items (paginated, filterable) |
| GET | `/api/v1/workitems/{id}` | Get single Work Item |
| PATCH | `/api/v1/workitems/{id}/status` | Transition status |
| POST | `/api/v1/workitems/{id}/rca` | Submit RCA |
| GET | `/api/v1/workitems/{id}/rca` | Get RCA |

**Valid state transitions:**
OPEN → INVESTIGATING → RESOLVED → CLOSED

Any other transition returns `409 Conflict`. Attempting to CLOSE without an RCA returns `422 Unprocessable Entity`.

**Transition a Work Item:**
```bash
curl -X PATCH http://localhost:8000/api/v1/workitems/{id}/status \
  -H "Content-Type: application/json" \
  -d '{"status": "INVESTIGATING"}'
```

**Submit RCA:**
```bash
curl -X POST http://localhost:8000/api/v1/workitems/{id}/rca \
  -H "Content-Type: application/json" \
  -d '{
    "incident_start": "2026-05-03T10:00:00Z",
    "incident_end":   "2026-05-03T11:30:00Z",
    "root_cause_category": "INFRASTRUCTURE",
    "fix_applied": "Restarted all DB nodes and flushed stale connection pools",
    "prevention_steps": "Implement automated failover with 30s health check interval",
    "affected_users_count": "~12,000",
    "submitted_by": "john.doe@company.com"
  }'
```

**Root cause categories:** `INFRASTRUCTURE`, `APPLICATION`, `NETWORK`, `DEPENDENCY`, `HUMAN_ERROR`, `UNKNOWN`

---

### Observability

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Service health + per-store latency |
| GET | `/metrics` | Prometheus metrics |

---

## Design Patterns

### Strategy Pattern — Alerting

Different component failures trigger different alert strategies, each mapping to a severity and notification channel. Adding a new component type requires only a new strategy class and one line in the registry — no changes to existing code (Open/Closed Principle).

```
ComponentType → AlertStrategy
─────────────────────────────
RDBMS         → P0RDBMSAlertStrategy     (page on-call immediately)
MCP_HOST      → P0MCPHostAlertStrategy   (page on-call immediately)
API           → P1APIAlertStrategy       (notify on-call channel)
QUEUE         → P1QueueAlertStrategy     (notify on-call channel)
CACHE         → P2CacheAlertStrategy     (notify team channel)
NOSQL         → P2NoSQLAlertStrategy     (notify team channel)
```

### State Pattern — Work Item Lifecycle

Each status is a concrete state class that knows which transitions it permits. Invalid transitions raise `InvalidStateTransitionError`. The `RESOLVED → CLOSED` transition additionally guards for a complete RCA, raising `MissingRCAError` if absent.

```angular2html
OPEN ──► INVESTIGATING ──► RESOLVED ──► CLOSED
│                                        ▲
└── any other path ──────────────────── 409
```

---

## Backpressure Strategy

This is the most critical SRE design decision in the system.

**Problem:** Signals can arrive at 10,000/sec. If the persistence layer (PostgreSQL, MongoDB) is slow or temporarily unavailable, a naive system would either crash (OOM) or block the HTTP server.

**Solution — Redis Streams as a bounded buffer:**

1. The HTTP ingestion endpoint does exactly one thing: `XADD` to a Redis Stream and return `202 Accepted`. This is a sub-millisecond in-memory operation and never blocks.

2. A separate async worker loop reads from the stream using `XREADGROUP` with `block=1000ms`. It processes signals in batches of 50 concurrently.

3. The stream is capped at `MAXLEN ~100,000` entries. If the worker falls behind, old entries are trimmed automatically — preventing Redis from running out of memory.

4. If a signal fails processing (DB timeout, etc.), it is NOT ACKed. It stays in the Redis PEL (Pending Entries List) and can be reclaimed and retried.

5. All DB writes use `tenacity` exponential backoff — 3 attempts, 1–5s wait — before giving up and leaving the message in PEL.

**Result:** The HTTP layer can absorb any burst. Workers process at the rate the DB allows. No crashes, no data loss.

---

## Observability

### Prometheus Metrics

| Metric | Type | Description |
|---|---|---|
| `ims_signals_ingested_total` | Counter | Total signals ingested, labelled by component_type and severity |
| `ims_active_incidents` | Gauge | Active (non-closed) incidents by severity |
| `ims_mttr_minutes` | Histogram | MTTR distribution across all closed incidents |
| `ims_http_request_duration_seconds` | Histogram | Request latency by method and endpoint |
| `ims_worker_signals_processed_total` | Counter | Worker throughput labelled by success/error |

### Throughput Logging

Every 5 seconds the worker prints:

📊 THROUGHPUT METRICS   signals_last_interval=142   signals_per_second=28.4

### Health Endpoint

`GET /health` checks each downstream service with a live ping and reports latency:
```json
{
  "status": "healthy",
  "services": [
    {"name": "postgresql", "status": "healthy", "latency_ms": 1.4},
    {"name": "mongodb",    "status": "healthy", "latency_ms": 0.8},
    {"name": "redis",      "status": "healthy", "latency_ms": 0.2}
  ],
  "uptime_seconds": 3842.1
}
```

---

## Security

- **JWT Bearer tokens** — all write endpoints require a valid JWT
- **Role-based access** — `admin` role for write operations, `viewer` for reads
- **Bcrypt password hashing** — passwords never stored in plaintext
- **Sliding window rate limiter** — 1000 requests per 60 seconds per IP, backed by Redis
- **CORS** — restricted to frontend origin only
- **No secrets in code** — all credentials injected via environment variables

---

## Testing

### Run unit tests

```bash
docker-compose exec backend pytest tests/ -v
```

### RCA Validation tests

The test suite covers:

- RCA with `incident_end` before `incident_start` is rejected
- Closing a Work Item without RCA returns 422
- Invalid state transitions return 409
- MTTR is calculated correctly on close

---

## Simulating an Outage

The `simulate_outage.py` script fires a realistic cascade: RDBMS failure → MCP Host cascade → API degradation → Cache pressure → Queue backup.

```bash
# Install httpx if running locally (outside Docker)
pip install httpx

# Run with default settings
python scripts/simulate_outage.py

# Custom host + larger burst
python scripts/simulate_outage.py --host http://localhost:8000 --burst 100
```

Sample output:

```terminaloutput
============================================================
🚨 IMS OUTAGE SIMULATION STARTING
Target: http://localhost:8000
Scenario: RDBMS outage → MCP cascade → API degradation
🔴 [P0] RDBMS | DB_PRIMARY_01
└─ CONNECTION_REFUSED: Primary database connection refused...
🔴 [P0] MCP_HOST | MCP_HOST_01
└─ DB_DEPENDENCY_FAILURE: MCP Host lost database connectivity...
🟠 [P1] API | API_GATEWAY_01
└─ UPSTREAM_TIMEOUT: API Gateway upstream timeout...
🟡 [P2] CACHE | CACHE_CLUSTER_01
└─ MEMORY_PRESSURE: Cache cluster memory at 94%...
📊 SIMULATION COMPLETE
Total signals sent : 15
Elapsed            : 8.3s
```

After running, check the created Work Items:
```bash
curl http://localhost:8000/api/v1/workitems/
```

---

## Non-Functional Additions

These were implemented beyond the base requirements and earn bonus points:

| Addition | Description |
|---|---|
| **JWT Authentication** | Full Bearer token auth with role-based access control |
| **Prometheus `/metrics`** | Production-grade metrics endpoint with 5 custom IMS metrics |
| **RedisInsight UI** | Visual Redis debugger at `http://localhost:8001` |
| **Selective ACK** | Failed signals stay in Redis PEL for guaranteed redelivery |
| **`SELECT FOR UPDATE`** | Row-level locking on signal_count increments — no race conditions |
| **Structured logging** | All logs via structlog with ISO timestamps and log levels |
| **Hot reload** | Backend restarts automatically on code changes via volume mount |
| **Composite DB indexes** | `(status, severity)` and `(component_id, status)` for fast dashboard queries |
| **CORS** | Properly configured for frontend integration |

---