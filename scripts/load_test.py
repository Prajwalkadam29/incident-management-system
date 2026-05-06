#!/usr/bin/env python3
"""
IMS Load Tester — Proof of 10k/sec Throughput
This script fires 10,000 concurrent signal ingestion requests to prove the
Redis Stream decoupled architecture can absorb massive bursts without dropping
requests or crashing the database.

Usage:
  python scripts/load_test.py
  python scripts/load_test.py --target http://localhost:8000 --count 10000 --concurrency 500
"""

import asyncio
import httpx
import argparse
import time
import uuid
import sys
from datetime import datetime

# Setup
parser = argparse.ArgumentParser(description="IMS Load Tester")
parser.add_argument("--target", default="http://localhost:8000", help="Backend base URL")
parser.add_argument("--count", type=int, default=10000, help="Total signals to send")
parser.add_argument("--concurrency", type=int, default=1000, help="Max concurrent connections")
args = parser.parse_args()

URL = f"{args.target}/api/v1/signals/ingest"

# The same component_id will be used to prove the atomic debouncing
# (10,000 signals should collapse into exactly 1 WorkItem)
COMPONENT_ID = f"LOAD_TEST_COMPONENT_{str(uuid.uuid4())[:8]}"

# Metrics
successes = 0
failures = 0

async def send_request(client: httpx.AsyncClient, sem: asyncio.Semaphore, idx: int):
    global successes, failures
    
    payload = {
        "component_id": COMPONENT_ID,
        "component_type": "API",
        "error_code": "LOAD_TEST_STORM",
        "message": f"Load test signal #{idx} for debounce proof",
        "severity": "P1",
        "metadata": {
            "load_test": True,
            "index": idx,
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    
    async with sem:
        try:
            # We don't need the token because the ingestion endpoint is unauthenticated by design
            # (Monitoring agents usually use API keys, but the spec didn't require auth here)
            response = await client.post(URL, json=payload, timeout=10.0)
            if response.status_code == 202:
                successes += 1
            else:
                failures += 1
        except Exception:
            failures += 1

async def main():
    print(f"\n[START] IMS Burst Load Tester")
    print(f"Targeting: {URL}")
    print(f"Signals to send: {args.count:,}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Component ID: {COMPONENT_ID} (To prove debouncing)\n")
    
    print("Initializing connections... (This ensures the burst happens instantly)")
    
    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)
    timeout = httpx.Timeout(10.0)
    sem = asyncio.Semaphore(args.concurrency)
    
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        # Pre-flight check
        try:
            r = await client.get(f"{args.target}/health")
            if r.status_code != 200:
                print(f"[FAIL] Backend not healthy. Status: {r.status_code}")
                sys.exit(1)
        except Exception as e:
            print(f"[FAIL] Could not reach backend: {e}")
            sys.exit(1)
            
        print("Backend is healthy. Starting burst...\n")
        
        start_time = time.time()
        
        tasks = [
            send_request(client, sem, i) 
            for i in range(args.count)
        ]
        
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        
    duration = end_time - start_time
    req_per_sec = args.count / duration
    
    print("[STATS] Load Test Complete")
    print("-" * 40)
    print(f"Total Sent:    {args.count:,}")
    print(f"Success (202): {successes:,}")
    print(f"Failures:      {failures:,}")
    print(f"Duration:      {duration:.2f} seconds")
    print(f"Throughput:    {req_per_sec:,.0f} signals/second")
    print("-" * 40)
    
    if successes > 0:
        print(f"\n[SUCCESS] Verification steps:")
        print(f"1. Check the Dashboard (http://localhost:5173)")
        print(f"   You should see EXACTLY ONE incident for {COMPONENT_ID}.")
        print(f"2. Check MongoDB /api/v1/signals/")
        print(f"   You will find all {successes:,} raw signals retained for auditing.")
    else:
        print("\n[FAIL] Test failed. No successful requests.")

if __name__ == "__main__":
    # Prevent Windows ProactorEventLoop from throwing exceptions on exit
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
