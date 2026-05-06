import urllib.request
import urllib.error
import json
import concurrent.futures
import time
import uuid
import sys

# Force UTF-8 encoding for stdout to avoid Windows charmap errors
sys.stdout.reconfigure(encoding='utf-8')

API_URL = "http://localhost:8000/api/v1/signals/ingest"

# Generate a unique component ID for this test run
TEST_COMPONENT_ID = f"THUNDERING_HERD_TEST_{uuid.uuid4().hex[:6]}"

payload = {
    "component_id": TEST_COMPONENT_ID,
    "component_type": "CACHE",
    "error_code": "CONCURRENT_TEST",
    "message": "Testing DB lock contention and debounce race conditions.",
    "severity": "P0",
    "metadata": {"test": True}
}

headers = {
    "Content-Type": "application/json"
}

def send_request(req_id):
    req = urllib.request.Request(API_URL, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
    try:
        start_time = time.time()
        with urllib.request.urlopen(req) as response:
            status = response.status
            response.read()
            return status, time.time() - start_time
    except urllib.error.HTTPError as e:
        return e.code, 0
    except Exception as e:
        return str(e), 0

def run_test(num_requests=100):
    print(f"[*] Firing {num_requests} concurrent requests for Component ID: {TEST_COMPONENT_ID}")
    
    start_time = time.time()
    
    # Fire requests concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [executor.submit(send_request, i) for i in range(num_requests)]
        
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
    duration = time.time() - start_time
    
    # Analyze results
    status_codes = {}
    for status, req_time in results:
        status_codes[status] = status_codes.get(status, 0) + 1
        
    print(f"\n[*] Results in {duration:.2f} seconds:")
    for status, count in status_codes.items():
        print(f"  HTTP {status}: {count} requests")
        
    print("\n[*] Now waiting 5 seconds for the Async Worker to process the Redis Stream...")
    time.sleep(5)
    
    # Now check the DB for the result
    work_items_url = f"http://localhost:8000/api/v1/workitems?component_id={TEST_COMPONENT_ID}"
    try:
        req = urllib.request.Request(work_items_url)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            items = data.get("items", [])
            print(f"\n[*] Database State for {TEST_COMPONENT_ID}:")
            print(f"  Work Items Created: {len(items)} (Expected: exactly 1)")
            
            total_signals = 0
            for item in items:
                print(f"  - Work Item ID: {item.get('id')}")
                print(f"    Signal Count: {item.get('signal_count')}")
                total_signals += item.get('signal_count', 0)
                
            print(f"\n  Total Signals Logged in DB: {total_signals} (Expected: exactly {num_requests})")
            
            if len(items) > 1:
                print("\n[!] FAILED: Duplicate incidents were created! Race condition detected.")
            elif total_signals != num_requests:
                print(f"\n[!] FAILED: Signal counts were lost or corrupted! Expected {num_requests}, got {total_signals}.")
            else:
                print("\n[+] PASSED: Worker correctly debounced and counted all signals.")
                
    except Exception as e:
        print(f"\n[!] FAILED to query work items: {e}")

if __name__ == "__main__":
    run_test(50)
