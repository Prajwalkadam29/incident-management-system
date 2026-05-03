#!/usr/bin/env python3
"""
Simulate a realistic production outage scenario:
  1. RDBMS primary goes down (P0)
  2. MCP Host loses DB connectivity and starts failing (P0)
  3. API layer starts throwing errors due to dependency failure (P1)
  4. Cache cluster gets overwhelmed as fallback (P2)
  5. Async queue backs up (P1)

Usage:
  python scripts/simulate_outage.py
  python scripts/simulate_outage.py --host http://localhost:8000 --burst 50
"""

import asyncio
import httpx
import argparse
import time
import random
from datetime import datetime


# ──────────────────────────────────────────
# Outage Scenario Definition
# ──────────────────────────────────────────

OUTAGE_SCENARIO = [
    # (delay_seconds, component_id, component_type, error_code, message, severity)
    (0.0,  "DB_PRIMARY_01",     "RDBMS",    "CONNECTION_REFUSED",
     "Primary database connection refused — possible disk failure", "P0"),

    (0.5,  "DB_PRIMARY_01",     "RDBMS",    "REPLICATION_LAG",
     "Replication lag exceeded 30s threshold on primary", "P0"),

    (1.0,  "MCP_HOST_01",       "MCP_HOST", "DB_DEPENDENCY_FAILURE",
     "MCP Host lost database connectivity — all requests failing", "P0"),

    (1.2,  "MCP_HOST_01",       "MCP_HOST", "HEALTH_CHECK_FAILED",
     "MCP Host health check returning 503", "P0"),

    (1.5,  "MCP_HOST_02",       "MCP_HOST", "CASCADING_FAILURE",
     "MCP Host 02 experiencing cascading failure from Host 01", "P0"),

    (2.0,  "API_GATEWAY_01",    "API",      "UPSTREAM_TIMEOUT",
     "API Gateway upstream timeout — DB layer unresponsive", "P1"),

    (2.2,  "API_GATEWAY_01",    "API",      "ERROR_RATE_SPIKE",
     "API error rate jumped to 45% — SLO breach imminent", "P1"),

    (2.5,  "API_GATEWAY_02",    "API",      "CIRCUIT_BREAKER_OPEN",
     "Circuit breaker opened on API Gateway 02", "P1"),

    (3.0,  "CACHE_CLUSTER_01",  "CACHE",    "MEMORY_PRESSURE",
     "Cache cluster memory at 94% — eviction rate spiking", "P2"),

    (3.2,  "CACHE_CLUSTER_01",  "CACHE",    "CONNECTION_POOL_EXHAUSTED",
     "Cache connection pool exhausted due to retry storms", "P2"),

    (3.5,  "QUEUE_PRIMARY_01",  "QUEUE",    "CONSUMER_LAG",
     "Async queue consumer lag at 50,000 messages — processing stalled", "P1"),

    (4.0,  "NOSQL_CLUSTER_01",  "NOSQL",    "WRITE_TIMEOUT",
     "NoSQL write timeout — audit log writes failing", "P2"),

    (4.5,  "DB_REPLICA_01",     "RDBMS",    "REPLICA_DISCONNECT",
     "Read replica disconnected from primary", "P0"),

    (5.0,  "API_GATEWAY_01",    "API",      "LATENCY_SPIKE",
     "P99 latency spiked to 8.2s — way above 500ms SLO", "P1"),

    (5.5,  "MCP_HOST_01",       "MCP_HOST", "MEMORY_LEAK",
     "MCP Host 01 memory climbing — possible leak under error conditions", "P0"),
]


# ──────────────────────────────────────────
# Signal Sender
# ──────────────────────────────────────────

async def send_signal(
    client: httpx.AsyncClient,
    host: str,
    component_id: str,
    component_type: str,
    error_code: str,
    message: str,
    severity: str,
    attempt: int = 1,
) -> bool:
    payload = {
        "component_id": component_id,
        "component_type": component_type,
        "error_code": error_code,
        "message": message,
        "severity": severity,
        "metadata": {
            "simulated": True,
            "attempt": attempt,
            "timestamp": datetime.utcnow().isoformat(),
            "region": random.choice(["us-east-1", "us-west-2", "eu-west-1"]),
            "host_ip": f"10.0.{random.randint(1,10)}.{random.randint(1,254)}",
        }
    }

    try:
        response = await client.post(
            f"{host}/api/v1/signals/ingest",
            json=payload,
            timeout=5.0,
        )
        if response.status_code == 202:
            return True
        else:
            print(f"  ⚠️  Unexpected status {response.status_code} for {component_id}")
            return False
    except Exception as e:
        print(f"  ❌ Failed to send signal for {component_id}: {e}")
        return False


# ──────────────────────────────────────────
# Burst Sender — simulates 10k/sec scenario
# ──────────────────────────────────────────

async def send_burst(
    client: httpx.AsyncClient,
    host: str,
    component_id: str,
    component_type: str,
    count: int,
):
    """Send `count` signals concurrently to test debounce under load."""
    print(f"\n  💥 Sending burst of {count} signals for {component_id}...")
    tasks = [
        send_signal(
            client, host, component_id, component_type,
            "BURST_TEST", f"Burst signal #{i} — debounce test",
            "P1", attempt=i,
        )
        for i in range(count)
    ]
    results = await asyncio.gather(*tasks)
    success = sum(results)
    print(f"  ✅ Burst complete: {success}/{count} accepted")


# ──────────────────────────────────────────
# Main Scenario Runner
# ──────────────────────────────────────────

async def run_simulation(host: str, burst: int):
    print("\n" + "="*60)
    print("  🚨 IMS OUTAGE SIMULATION STARTING")
    print("="*60)
    print(f"  Target: {host}")
    print(f"  Scenario: RDBMS outage → MCP cascade → API degradation")
    print(f"  Signals to send: {len(OUTAGE_SCENARIO)}")
    print("="*60 + "\n")

    async with httpx.AsyncClient() as client:
        # Verify backend is up before starting
        try:
            r = await client.get(f"{host}/health", timeout=5.0)
            health = r.json()
            print(f"  ✅ Backend healthy: {health['status']}")
            print(f"  Services: {[s['name'] + '=' + s['status'] for s in health['services']]}\n")
        except Exception as e:
            print(f"  ❌ Backend not reachable at {host}: {e}")
            print("  Make sure docker-compose up is running first!")
            return

        scenario_start = time.time()
        sent = 0
        failed = 0

        # Run scenario with realistic timing
        for delay, component_id, component_type, error_code, message, severity in OUTAGE_SCENARIO:
            await asyncio.sleep(delay if delay == 0 else 0.5)  # normalized for demo

            icon = {"P0": "🔴", "P1": "🟠", "P2": "🟡"}.get(severity, "⚪")
            print(f"  {icon} [{severity}] {component_type} | {component_id}")
            print(f"     └─ {error_code}: {message[:60]}...")

            success = await send_signal(
                client, host, component_id, component_type,
                error_code, message, severity,
            )
            if success:
                sent += 1
            else:
                failed += 1

        # Burst test — demonstrates debounce under load
        if burst > 0:
            print(f"\n{'='*60}")
            print(f"  🔥 BURST TEST — {burst} rapid signals (debounce validation)")
            print(f"{'='*60}")
            await send_burst(client, host, "DB_PRIMARY_01", "RDBMS", burst)

        # Final summary
        elapsed = round(time.time() - scenario_start, 2)
        print(f"\n{'='*60}")
        print(f"  📊 SIMULATION COMPLETE")
        print(f"{'='*60}")
        print(f"  Total signals sent : {sent}")
        print(f"  Failed             : {failed}")
        print(f"  Elapsed            : {elapsed}s")
        print(f"\n  Check Work Items created:")
        print(f"  curl {host}/api/v1/workitems/")
        print(f"\n  Check raw signals in Mongo:")
        print(f"  curl {host}/api/v1/signals/")
        print("="*60 + "\n")


# ──────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IMS Outage Simulator")
    parser.add_argument("--host", default="http://localhost:8000",
                        help="Backend base URL")
    parser.add_argument("--burst", type=int, default=20,
                        help="Number of burst signals to send for debounce test")
    args = parser.parse_args()

    asyncio.run(run_simulation(args.host, args.burst))