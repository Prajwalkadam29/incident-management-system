import sys
import time
import json
import urllib.request
import urllib.error
import concurrent.futures
import uuid
import redis

# Force UTF-8 encoding for stdout
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

API_BASE = "http://127.0.0.1:8000/api/v1"
REDIS_URL = "redis://127.0.0.1:6379"

# Initialize Redis client to verify cache keys
r_client = redis.from_url(REDIS_URL, decode_responses=True)

def login():
    url = f"{API_BASE}/auth/login"
    payload = {
        "username": "admin",
        "password": "Admin@IMS2026!"
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as r:
            res = json.loads(r.read().decode('utf-8'))
            return res.get("access_token")
    except Exception as e:
        print(f"[!] Login failed: {e}")
        sys.exit(1)

def send_authenticated_request(url, method="GET", payload=None, token=None):
    headers = {
        "Content-Type": "application/json"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    data = json.dumps(payload).encode('utf-8') if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    start_time = time.time()
    try:
        with urllib.request.urlopen(req) as response:
            status = response.status
            body = json.loads(response.read().decode('utf-8'))
            return status, body, time.time() - start_time
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode('utf-8'))
        except:
            err_body = e.reason
        return e.code, err_body, time.time() - start_time
    except Exception as e:
        return "ERROR", str(e), time.time() - start_time

def run_performance_test():
    print(f"\n========================================================")
    print(f"🚀 SRE PERFORMANCE & LOAD TEST: AI CACHING & TIMESERIES AGG")
    print(f"========================================================\n")

    # Log in to get token for AI endpoints
    print("[*] Authenticating as admin...")
    token = login()
    print("[+] Authentication SUCCESS!")

    # ----------------------------------------------------
    # PHASE 1: Timeseries Aggregation Cache under Load
    # ----------------------------------------------------
    print("\n--- PHASE 1: Timeseries Aggregation Cache under Load ---")
    agg_url = f"{API_BASE}/signals/aggregations?time_window_hours=24&group_by=component_id"
    
    # Clean any existing cache key
    cache_key = "ims:cache:signals:agg:24:component_id"
    r_client.delete(cache_key)
    print("[*] Evicted existing aggregation cache.")

    # 1. Fire first request to warm up the cache
    print("[*] Firing first request to warm cache (database query)...")
    status, body, duration_1 = send_authenticated_request(agg_url)
    print(f"  - Status: {status}")
    print(f"  - Cached: {body.get('cached')}")
    print(f"  - Duration: {duration_1 * 1000:.2f} ms")
    
    if status != 200 or body.get("cached") is not False:
        print("[!] FAILED: First query should hit DB and return cached=False")
        sys.exit(1)

    # 2. Fire 100 concurrent requests to test caching under load
    num_requests = 100
    print(f"[*] Firing {num_requests} concurrent requests at the aggregations endpoint...")
    
    start_time = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [executor.submit(send_authenticated_request, agg_url) for _ in range(num_requests)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    total_duration = time.time() - start_time

    # Analyze results
    status_codes = {}
    cached_counts = {True: 0, False: 0}
    durations = []
    
    for status, body, dur in results:
        status_codes[status] = status_codes.get(status, 0) + 1
        durations.append(dur)
        if isinstance(body, dict):
            cached = body.get("cached")
            cached_counts[cached] = cached_counts.get(cached, 0) + 1

    avg_duration = sum(durations) / len(durations)
    print(f"\n[*] Performance Results for {num_requests} concurrent requests:")
    print(f"  - Total Elapsed Time: {total_duration:.3f} s")
    print(f"  - Average Request Latency: {avg_duration * 1000:.2f} ms")
    print(f"  - HTTP Status Codes: {status_codes}")
    print(f"  - Cached Responses served: {cached_counts.get(True, 0)}")
    print(f"  - Database queries skipped: {cached_counts.get(True, 0)}/100")

    # Assertions
    if cached_counts.get(True, 0) < 95:
        print(f"[!] FAILED: Expected high cache-hit ratio, got only {cached_counts.get(True, 0)}")
        sys.exit(1)
    print("[+] SUCCESS: Timeseries Aggregation Cache handled concurrent load perfectly, shielding MongoDB!")

    # ----------------------------------------------------
    # PHASE 2: AI RCA Generation Caching & Outage Resilience
    # ----------------------------------------------------
    print("\n--- PHASE 2: AI RCA Caching (Mock Injection) ---")
    mock_work_item_id = str(uuid.uuid4())
    rca_cache_key = f"ims:cache:ai:rcadraft:{mock_work_item_id}"
    
    mock_rca_response = {
        "executive_summary": "Simulated RCA for load test.",
        "impact": "No real impact.",
        "root_cause": "SRE testing cache bypass.",
        "trigger": "Submitting mock data.",
        "resolution": "Cache hit successfully verified.",
        "action_items": ["Implement robust caching"],
        "provider": "mock-llm-service",
        "model": "gpt-mock-4"
    }

    # Inject mock directly into Redis
    r_client.setex(rca_cache_key, 60, json.dumps(mock_rca_response))
    print(f"[*] Injected mock RCA draft into Redis key: {rca_cache_key}")

    # Now make the API call to rca-draft
    rca_url = f"{API_BASE}/ai/rca-draft"
    payload = {
        "work_item_id": mock_work_item_id,
        "component_id": "MOCK_COMP_01",
        "component_type": "API",
        "severity": "P0",
        "title": "Mock Incident",
        "total_signals": 10,
        "duration_minutes": 15,
        "resolution_notes": "None",
        "timeline_events": []
    }

    print("[*] Firing API request to /rca-draft...")
    status, body, duration = send_authenticated_request(rca_url, method="POST", payload=payload, token=token)
    
    print(f"  - Status: {status}")
    print(f"  - Executive Summary: {body.get('executive_summary')}")
    print(f"  - Provider Field: {body.get('provider')}")
    print(f"  - Latency: {duration * 1000:.2f} ms")

    if status == 200 and body.get("provider") == "mock-llm-service (cached)":
        print("[+] SUCCESS: AI Caching validated! RCA was served instantly from Redis, preventing external API calls!")
    else:
        print(f"[!] FAILED: AI draft was not correctly served from cache. Got status {status}: {body}")
        sys.exit(1)

    print("\n========================================================")
    print("🎉 ALL PERFORMANCE & LOAD TEST SCENARIOS PASSED!")
    print("========================================================\n")

if __name__ == "__main__":
    run_performance_test()
