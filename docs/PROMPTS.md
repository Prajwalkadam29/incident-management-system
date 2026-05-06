# AI Assistance Log & Prompts

As per the assignment requirements, this file documents the usage of AI during the development of the Incident Management System.

## Development Approach
AI was utilized as a pair-programming partner, primarily for architectural reviews, refactoring complex concurrency logic, and generating boilerplate testing scenarios. All core design decisions (State Machine, Strategy Pattern, Debounce logic) were actively driven and reviewed by the engineer.

## Key Prompts Used

### 1. Redis Concurrency / Race Conditions
> "I am implementing a debounce mechanism using Redis SETNX to prevent duplicate incident creation when a component fails 10,000 times a second. However, I am worried about the edge case where the lock expires *while* the worker is inserting the first item into Postgres, causing the next batch to create a duplicate. How do I safely handle the lock TTL and verify existence?"

### 2. OpenTelemetry Context Propagation
> "I am using FastAPI, Redis Streams, and an async python worker. I need to propagate the OpenTelemetry trace context from the FastAPI HTTP request, across the Redis Stream boundary, and into the worker process so that Jaeger shows a single unified trace. Show me the exact `inject()` and `extract()` W3C header logic."

### 3. SQLAlchemy Multi-Process Safety
> "I have an endpoint that needs to increment a signal counter for metrics. Currently I am using a global `_signal_counter` integer, but I realize this will fail if I run multiple Uvicorn workers. Should I use Redis `INCR` or the Prometheus Python client multiprocess mode? What are the tradeoffs?"

### 4. Load Testing Asyncio
> "Write a high-performance Python script using `asyncio` and `httpx` to load test my FastAPI ingestion endpoint. It needs to send 10,000 requests as fast as possible to prove the system can handle the burst requirement. Include success/failure metrics."
