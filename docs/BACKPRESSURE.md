# Backpressure Strategy

Handling high-volume signal storms (e.g., a cascading network failure triggering 10,000 alerts per second) is a critical requirement of the IMS. If the system attempts to process these synchronously, the database connection pool will exhaust, and the API will crash with `503 Service Unavailable`.

To guarantee system survival, we implemented a **Three-Tier Backpressure Strategy**.

## Tier 1: Asynchronous Decoupling
The HTTP ingestion endpoint (`/api/v1/signals/ingest`) **never talks to PostgreSQL or MongoDB**.
When a request arrives, the API validates it and pushes it to a Redis Stream via an asynchronous `XADD` command, instantly returning a `202 Accepted`. 

Because Redis operates entirely in memory and is single-threaded (avoiding lock contention), the API can ingest thousands of signals per second while using very few ASGI worker threads.

## Tier 2: Stream Truncation (Memory Safety)
To prevent the Redis server from running out of memory if the background workers crash or fall behind (Consumer Lag), we apply a strict cap on the queue size using the `MAXLEN` argument.

```python
# ingestion.py
await redis.xadd(
    name=settings.STREAM_NAME,
    fields=stream_payload,
    maxlen=100000,       # ← Hard memory limit
    approximate=True,    # ← "~" optimization for O(1) performance
)
```
If the stream exceeds 100,000 unhandled signals, Redis will automatically drop the oldest signals. While dropping signals is undesirable, **sacrificing older signals is vastly preferable to the entire ingestion layer running out of memory and crashing.**

## Tier 3: Atomic Debouncing (Database Protection)
Even if the queue absorbs 10,000 signals for a single failing component, we must not execute 10,000 `INSERT` statements against PostgreSQL.

The background worker utilizes an atomic Redis `SETNX` (Set if Not Exists) lock with a TTL (Time-To-Live).

1. Worker pops a batch of 500 signals from the stream.
2. For each signal, it attempts to acquire a lock: `SETNX ims:debounce:{component_id}`.
3. **If successful:** It writes exactly ONE `WorkItem` to PostgreSQL and sets a 5-minute TTL on the lock.
4. **If unsuccessful:** The signal is recognized as a duplicate. It skips PostgreSQL entirely and is only written to the MongoDB audit log.

This collapses a 10,000-signal burst into exactly **one DB transaction**, protecting the RDBMS connection pool from exhaustion.
