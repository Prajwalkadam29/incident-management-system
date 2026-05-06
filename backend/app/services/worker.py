import asyncio
import json
import time
import uuid
import structlog
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
import logging

from opentelemetry import trace
from opentelemetry.propagate import extract

from app.core.config import settings
from app.db.redis_client import get_redis
from app.db.postgres import AsyncSessionFactory
from app.db.mongo import get_mongo_db
from app.models.sql_models import WorkItem, ComponentType, Severity
from app.services.alerting import alerting_service, AlertPayload
from app.services.ingestion import get_and_reset_signal_count
from app.services import timeline as tl
from app.models.sql_models import EventType

logger = structlog.get_logger(__name__)

# Worker control flag
_worker_running = False
_worker_task: Optional[asyncio.Task] = None
_metrics_task: Optional[asyncio.Task] = None
_pel_retry_task: Optional[asyncio.Task] = None

CONSUMER_NAME = f"worker-{uuid.uuid4().hex[:8]}"  # unique per process


# ──────────────────────────────────────────
# Debounce Logic
# ──────────────────────────────────────────

async def get_or_create_debounce_lock(component_id: str) -> Optional[str]:
    """
    Atomic debounce using Redis SETNX with TTL.

    Returns:
        work_item_id (str) if this is the FIRST signal in the window
        None if a work item already exists for this component (debounced)

    Key: ims:debounce:<component_id>
    Value: work_item_id (so we know which WI to link signals to)
    TTL: DEBOUNCE_WINDOW_SECONDS (10s)
    """
    redis = get_redis()
    debounce_key = f"ims:debounce:{component_id}"
    new_work_item_id = str(uuid.uuid4())

    # SET key value EX ttl NX — atomic: only sets if key doesn't exist
    was_set = await redis.set(
        debounce_key,
        new_work_item_id,
        ex=settings.DEBOUNCE_WINDOW_SECONDS,
        nx=True,  # NX = only set if Not eXists
    )

    if was_set:
        # First signal in this window — we own the work item creation
        logger.info(
            "Debounce lock acquired — new Work Item will be created",
            component_id=component_id,
            work_item_id=new_work_item_id,
            window_seconds=settings.DEBOUNCE_WINDOW_SECONDS,
        )
        return new_work_item_id
    else:
        # Already have a work item for this component — return its ID
        existing_id = await redis.get(debounce_key)
        logger.debug(
            "Signal debounced — linking to existing Work Item",
            component_id=component_id,
            existing_work_item_id=existing_id,
        )
        return None  # caller will look up existing WI from Redis


async def get_existing_work_item_id(component_id: str) -> Optional[str]:
    """Get the current debounce work_item_id for a component."""
    redis = get_redis()
    return await redis.get(f"ims:debounce:{component_id}")


# ──────────────────────────────────────────
# DB Write with Retry (Resilience)
# ──────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
    reraise=True,
)
async def upsert_work_item_in_db(
        work_item_id: str,
        component_id: str,
        component_type: ComponentType,
        severity: Severity,
        title: str,
) -> tuple[str, bool, int]:
    """
    Atomic UPSERT in PostgreSQL using the partial unique index.
    If no OPEN WorkItem exists for this component_id, inserts a new one.
    Otherwise, increments signal_count.

    Returns:
        (actual_work_item_id, is_new_work_item, new_signal_count)
    """
    async with AsyncSessionFactory() as session:
        stmt = pg_insert(WorkItem).values(
            id=uuid.UUID(work_item_id),
            component_id=component_id,
            component_type=component_type,
            severity=severity,
            status="OPEN",
            title=title,
            signal_count=1,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=["component_id"],
            index_where=text("status = 'OPEN'"),
            set_={
                "signal_count": WorkItem.signal_count + 1,
                "updated_at": datetime.now(timezone.utc),
            }
        )

        stmt = stmt.returning(WorkItem.id, WorkItem.signal_count)

        async with session.begin():
            result = await session.execute(stmt)
            row = result.fetchone()
            if row:
                returned_id = str(row[0])
                new_signal_count = row[1]
                is_new = (returned_id == work_item_id)
                return returned_id, is_new, new_signal_count
            else:
                raise Exception("UPSERT did not return any rows")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    reraise=True,
)
async def store_raw_signal_in_mongo(signal_doc: dict) -> None:
    """Store raw signal payload in MongoDB (audit log)."""
    db = get_mongo_db()
    await db.signals.insert_one(signal_doc)


async def update_dashboard_cache(work_item_id: str, component_id: str,
                                 severity: str, status: str) -> None:
    """Keep Redis hot-path cache in sync with new/updated Work Items."""
    redis = get_redis()
    cache_key = f"ims:dashboard:{work_item_id}"
    await redis.hset(cache_key, mapping={
        "work_item_id": work_item_id,
        "component_id": component_id,
        "severity": severity,
        "status": status,
        "updated_at": str(time.time()),
    })
    # Dashboard cache expires after 1 hour — prevents stale data
    await redis.expire(cache_key, 3600)


_db_sem: Optional[asyncio.Semaphore] = None

def get_db_semaphore() -> asyncio.Semaphore:
    global _db_sem
    if _db_sem is None:
        _db_sem = asyncio.Semaphore(10)  # limit to 10 concurrent database sessions
    return _db_sem


# ──────────────────────────────────────────
# Process a Single Signal
# ──────────────────────────────────────────

tracer = trace.get_tracer(__name__)

async def process_signal(fields: dict) -> None:
    """
    Full processing pipeline for one signal:
    1. Debounce check
    2. Create or link Work Item in PostgreSQL
    3. Store raw signal in MongoDB
    4. Update Redis dashboard cache
    5. Fire alert (only on new Work Item creation)
    """
    # Extract tracing context from metadata if it exists
    metadata_str = fields.get("metadata", "{}")
    metadata = json.loads(metadata_str)
    
    # Create span context from injected trace headers
    ctx = extract(metadata.get("trace_headers", {}))
    
    with tracer.start_as_current_span("worker.process_signal", context=ctx) as span:
        component_id = fields["component_id"]
        component_type = ComponentType(fields["component_type"])
        severity_str = fields["severity"]
        signal_id = fields["signal_id"]
        message = fields["message"]
        error_code = fields["error_code"]
        timestamp = float(fields.get("timestamp", time.time()))

        span.set_attribute("component.id", component_id)
        span.set_attribute("component.type", fields["component_type"])
        span.set_attribute("signal.id", signal_id)

        # Determine severity from alerting strategy (overrides signal severity for P0 components)
        computed_severity = alerting_service.get_severity_for_component(component_type)

        # ── Step 1: Debounce (Optimization) ──
        existing_id = await get_existing_work_item_id(component_id)
        if existing_id:
            suggested_id = existing_id
        else:
            suggested_id = str(uuid.uuid4())

        title = f"[{computed_severity}] {component_type} failure on {component_id}"

        # ── Step 2: PostgreSQL Atomic UPSERT ──
        async with get_db_semaphore():
            work_item_id, is_new_work_item, new_signal_count = await upsert_work_item_in_db(
                work_item_id=suggested_id,
                component_id=component_id,
                component_type=component_type,
                severity=computed_severity,
                title=title,
            )

        if is_new_work_item:
            # Save to Redis debounce cache so other signals can link to it
            redis = get_redis()
            await redis.set(
                f"ims:debounce:{component_id}",
                work_item_id,
                ex=settings.DEBOUNCE_WINDOW_SECONDS,
            )
            logger.info("New Work Item created (via UPSERT)",
                        work_item_id=work_item_id,
                        component_id=component_id,
                        severity=computed_severity)
        else:
            logger.debug("Signal debounced and count incremented (via UPSERT)",
                         work_item_id=work_item_id,
                         component_id=component_id,
                         new_count=new_signal_count)

        # ── Step 3: MongoDB — store raw signal (always) ──
        signal_doc = {
            "signal_id": signal_id,
            "work_item_id": work_item_id,
            "component_id": component_id,
            "component_type": fields["component_type"],
            "error_code": error_code,
            "message": message,
            "severity": severity_str,
            "metadata": metadata,
            "timestamp": datetime.fromtimestamp(timestamp, tz=timezone.utc),
            "ingested_at": datetime.now(timezone.utc),
        }
        await store_raw_signal_in_mongo(signal_doc)

        # ── Step 4: Redis cache ──
        await update_dashboard_cache(
            work_item_id=work_item_id,
            component_id=component_id,
            severity=computed_severity.value,
            status="OPEN",
        )

        # ── Step 5: Alert — only on first signal (new Work Item) ──
        if is_new_work_item:
            alert_payload = AlertPayload(
                work_item_id=work_item_id,
                component_id=component_id,
                component_type=component_type,
                severity=computed_severity,
                title=title,
                signal_count=1,
                message=message,
            )
            await alerting_service.alert(alert_payload)

        # ── Step 6: Timeline events ──
        if is_new_work_item:
            asyncio.create_task(tl.record_incident_created(
                work_item_id=work_item_id,
                component_id=component_id,
                severity=computed_severity.value,
                signal_count=1,
            ))
            asyncio.create_task(tl.record_alert_fired(
                work_item_id=work_item_id,
                severity=computed_severity.value,
                channel=f"{computed_severity.value}_channel",
            ))
        else:
            asyncio.create_task(tl.record_signal_received(
                work_item_id=work_item_id,
                error_code=error_code,
                component_id=component_id,
                signal_count=int(new_signal_count),
            ))



# ──────────────────────────────────────────
# Consumer Loop
# ──────────────────────────────────────────

async def worker_loop() -> None:
    """
    Redis Streams consumer group loop.
    Reads batches of messages, processes them concurrently,
    and ACKs only after successful processing.
    """
    redis = get_redis()
    logger.info("Worker started", consumer=CONSUMER_NAME,
                stream=settings.STREAM_NAME,
                group=settings.STREAM_CONSUMER_GROUP)

    while _worker_running:
        try:
            # XREADGROUP: read up to 50 messages, block for 1s if stream is empty
            messages = await redis.xreadgroup(
                groupname=settings.STREAM_CONSUMER_GROUP,
                consumername=CONSUMER_NAME,
                streams={settings.STREAM_NAME: ">"},  # ">" = only undelivered messages
                count=50,
                block=1000,  # ms — yields control to event loop while waiting
            )

            if not messages:
                continue

            # messages = [(stream_name, [(msg_id, fields), ...])]
            for stream_name, entries in messages:
                # Process all entries in this batch concurrently
                tasks = []
                msg_ids = []

                for msg_id, fields in entries:
                    tasks.append(process_signal(fields))
                    msg_ids.append(msg_id)

                # Run batch concurrently — gather with return_exceptions to not stop on one failure
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # ACK only the successful ones; failed ones stay as PEL (pending)
                acked_ids = []
                for msg_id, result in zip(msg_ids, results):
                    if isinstance(result, Exception):
                        logger.error(
                            "Signal processing failed — will retry via PEL",
                            msg_id=msg_id,
                            error=str(result),
                        )
                    else:
                        acked_ids.append(msg_id)

                if acked_ids:
                    await redis.xack(settings.STREAM_NAME,
                                     settings.STREAM_CONSUMER_GROUP,
                                     *acked_ids)

        except asyncio.CancelledError:
            logger.info("Worker loop cancelled — shutting down")
            break
        except Exception as e:
            logger.error("Worker loop error", error=str(e))
            await asyncio.sleep(1)  # brief pause before retrying


# ──────────────────────────────────────────
# PEL Claiming & Reprocessing Loop (Resiliency)
# ──────────────────────────────────────────

async def pel_retry_loop() -> None:
    """
    SRE Resiliency Task: Periodically checks the consumer group's Pending Entries List (PEL)
    to claim and reprocess orphaned or failed signals.
    """
    redis = get_redis()
    logger.info("PEL Claim and Retry loop started")

    while _worker_running:
        try:
            # 1. Fetch pending messages overview
            pending_info = await redis.xpending_range(
                settings.STREAM_NAME,
                settings.STREAM_CONSUMER_GROUP,
                min="-",
                max="+",
                count=50,
            )

            if not pending_info:
                await asyncio.sleep(15)
                continue

            # Filter messages that have been pending for more than 15 seconds
            to_claim = []
            for item in pending_info:
                # Some versions return bytes, handle both
                msg_id = item["message_id"].decode("utf-8") if isinstance(item["message_id"], bytes) else item["message_id"]
                idle_ms = item.get("time_since_delivered") or item.get("milliseconds_delivered") or 0
                if idle_ms >= 15000:
                    to_claim.append(msg_id)

            if not to_claim:
                await asyncio.sleep(15)
                continue

            logger.info("PEL Retry: claiming orphaned pending signals", count=len(to_claim))

            # 2. Claim the pending messages under our current CONSUMER_NAME
            claimed_entries = await redis.xclaim(
                settings.STREAM_NAME,
                settings.STREAM_CONSUMER_GROUP,
                CONSUMER_NAME,
                min_idle_time=15000,
                message_ids=to_claim,
            )

            if not claimed_entries:
                await asyncio.sleep(15)
                continue

            # 3. Process the claimed messages!
            tasks = []
            msg_ids = []
            for msg_id, fields in claimed_entries:
                # Ensure fields is decoded properly if needed
                decoded_fields = {}
                for k, v in fields.items():
                    k_str = k.decode("utf-8") if isinstance(k, bytes) else k
                    v_str = v.decode("utf-8") if isinstance(v, bytes) else v
                    decoded_fields[k_str] = v_str
                tasks.append(process_signal(decoded_fields))
                msg_ids.append(msg_id)

            if not tasks:
                await asyncio.sleep(15)
                continue

            results = await asyncio.gather(*tasks, return_exceptions=True)

            acked_ids = []
            for msg_id, result in zip(msg_ids, results):
                if isinstance(result, Exception):
                    logger.error(
                        "PEL Retry: reprocessing failed again — will retry next interval",
                        msg_id=msg_id,
                        error=str(result),
                    )
                else:
                    acked_ids.append(msg_id)

            if acked_ids:
                await redis.xack(
                    settings.STREAM_NAME,
                    settings.STREAM_CONSUMER_GROUP,
                    *acked_ids,
                )
                logger.info("PEL Retry: successfully reprocessed and ACKed signals", count=len(acked_ids))

        except Exception as e:
            logger.error("Error in PEL claim loop", error=str(e))

        await asyncio.sleep(15)


# ──────────────────────────────────────────
# Throughput Metrics Loop
# ──────────────────────────────────────────

async def metrics_loop() -> None:
    """
    Prints signals/sec to console every METRICS_INTERVAL_SECONDS.
    Satisfies the observability requirement from the spec.
    """
    logger.info("Metrics loop started",
                interval_seconds=settings.METRICS_INTERVAL_SECONDS)

    while _worker_running:
        await asyncio.sleep(settings.METRICS_INTERVAL_SECONDS)
        count = await get_and_reset_signal_count()
        rate = count / settings.METRICS_INTERVAL_SECONDS
        logger.info(
            "📊 THROUGHPUT METRICS",
            signals_last_interval=count,
            signals_per_second=round(rate, 2),
            interval_seconds=settings.METRICS_INTERVAL_SECONDS,
        )


# ──────────────────────────────────────────
# Start / Stop
# ──────────────────────────────────────────

async def start_worker() -> None:
    global _worker_running, _worker_task, _metrics_task, _pel_retry_task
    _worker_running = True
    _worker_task = asyncio.create_task(worker_loop())
    _metrics_task = asyncio.create_task(metrics_loop())
    _pel_retry_task = asyncio.create_task(pel_retry_loop())
    logger.info("Background worker, metrics, and PEL retry loops started")


async def stop_worker() -> None:
    global _worker_running, _worker_task, _metrics_task, _pel_retry_task
    _worker_running = False

    if _worker_task:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass

    if _metrics_task:
        _metrics_task.cancel()
        try:
            await _metrics_task
        except asyncio.CancelledError:
            pass

    if _pel_retry_task:
        _pel_retry_task.cancel()
        try:
            await _pel_retry_task
        except asyncio.CancelledError:
            pass

    logger.info("Worker stopped cleanly")