# IMS Architecture

The Incident Management System (IMS) is built around an event-driven, asynchronous architecture designed to handle high-volume signal ingestion from multiple observability sources while maintaining a strict, transactional source of truth for incident state.

## Core Components

### 1. The Ingestion Layer (FastAPI)
The API layer is intentionally "dumb" and fast. When a signal arrives at `/api/v1/signals/ingest`, the FastAPI handler does exactly three things:
1. Validates the JSON schema (Pydantic).
2. Checks the sliding-window rate limiter (Redis).
3. Pushes the raw payload to a Redis Stream (`XADD`) and immediately returns `202 Accepted`.

No database writes occur on the HTTP critical path.

### 2. The Queue Layer (Redis Streams)
We use Redis Streams as the core message broker because:
- It supports consumer groups for horizontal scaling of workers.
- It provides built-in memory limits via the `MAXLEN` cap.
- It is significantly faster than RabbitMQ or Kafka for this specific payload size.

### 3. The Processing Worker (Async Python)
A separate background worker process (`worker.py`) constantly pulls batches of messages from the Redis Stream using `XREADGROUP`. It performs the heavy lifting:
- **Debouncing:** Uses atomic `SETNX` operations in Redis to collapse 10,000 identical signals in a 5-minute window into a single PostgreSQL `WorkItem`.
- **Persistence:** Writes the deduplicated state to PostgreSQL.
- **Audit Logging:** Dumps the raw, unadulterated payload into MongoDB for compliance and AI training.
- **Alerting:** Fires off async webhooks (Slack, MS Teams) based on the Alerting Strategy Pattern.
- **Cache Invalidation:** Updates the hot-path Redis Hashes used by the dashboard.

### 4. Storage Layers (Polyglot Persistence)
We strictly separate the transactional state from the audit log:
- **PostgreSQL:** The absolute source of truth. Enforces the `WorkItem` state machine, RCA relational constraints, and calculates MTTR.
- **MongoDB:** The append-only audit log. Every single signal (even duplicates that were debounced) is written here for historical RCA analysis.
- **Redis:** Used for three entirely different access patterns:
  - Streams (Queue)
  - Sorted Sets (Rate Limiting)
  - Hashes/Strings (Dashboard cache & Debounce Locks)

## Key Design Patterns Used

1. **State Pattern (`state_machine.py`)**: Enforces the strict `OPEN → INVESTIGATING → RESOLVED → CLOSED` lifecycle. Prevents illegal transitions and enforces mandatory RCA submission.
2. **Strategy Pattern (`alerting.py` & `ai_providers/`)**: Maps different `ComponentType`s to different alerting behaviors. Allows seamless swapping of AI models (Gemini vs Groq) via polymorphic interfaces.
3. **Atomic Locks (`worker.py`)**: Resolves race conditions during high-volume ingestion bursts using Redis `SETNX`.
