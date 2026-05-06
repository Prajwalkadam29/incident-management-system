import sys
import time
import json
import urllib.request
import urllib.error
import subprocess
import uuid

# Force UTF-8 encoding for stdout to avoid Windows charmap errors
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

INGEST_URL = "http://localhost:8000/api/v1/signals/ingest"
WORKITEMS_URL = "http://localhost:8000/api/v1/workitems"

# Generate a unique component ID for the chaos test
TEST_COMPONENT = f"CHAOS_TEST_{uuid.uuid4().hex[:6]}"

payload = {
    "component_id": TEST_COMPONENT,
    "component_type": "RDBMS",
    "error_code": "CONN_CHAOS_ERR",
    "message": "Chaos injection test during active outage.",
    "severity": "P1",
    "metadata": {"chaos": True}
}

headers = {
    "Content-Type": "application/json"
}

def send_ingest_request():
    req = urllib.request.Request(INGEST_URL, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')
    except Exception as e:
        return "ERROR", str(e)

def run_command(cmd):
    print(f"[*] Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.returncode, result.stdout, result.stderr

def test_chaos_failover():
    print(f"\n========================================================")
    print(f"🔥 SRE CHAOS TEST: DATABASE & CACHE FAILOVER RESILIENCE")
    print(f"========================================================\n")
    print(f"[*] Using Test Component ID: {TEST_COMPONENT}\n")

    # ----------------------------------------------------
    # PHASE 1: Baseline Ingestion
    # ----------------------------------------------------
    print("--- PHASE 1: Baseline Ingestion ---")
    status, res = send_ingest_request()
    if status == 202:
        print("[+] Baseline signal ingestion: SUCCESS (HTTP 202)")
    else:
        print(f"[!] FAILED: Baseline ingestion failed with status {status}: {res}")
        sys.exit(1)

    print("\n[*] Waiting 3 seconds for the baseline signal to write to DB...")
    time.sleep(3)

    # ----------------------------------------------------
    # PHASE 2: Database (Postgres) Outage Simulation
    # ----------------------------------------------------
    print("\n--- PHASE 2: Simulating PostgreSQL Outage ---")
    # Stop postgres container
    code, out, err = run_command(["docker", "compose", "stop", "postgres"])
    if code != 0:
        print(f"[!] FAILED: Could not stop postgres: {err}")
        sys.exit(1)
    print("[+] PostgreSQL container stopped.")

    # Ingest 5 signals while PostgreSQL is down
    print(f"[*] Ingesting 5 signals while PostgreSQL is DOWN...")
    success_count = 0
    for i in range(5):
        status, res = send_ingest_request()
        if status == 202:
            success_count += 1
        else:
            print(f"  [!] Signal {i+1} ingestion failed: {status}")
            
    print(f"[+] Ingestion during PostgreSQL outage results: {success_count}/5 accepted (HTTP 202)")
    if success_count == 5:
        print("[+] SUCCESS: API remains fully available for ingestion during database outage! (Decoupled architecture validated)")
    else:
        print("[!] FAILED: Decoupled ingestion was interrupted!")
        # Clean up by bringing postgres back
        run_command(["docker", "compose", "start", "postgres"])
        sys.exit(1)

    # ----------------------------------------------------
    # PHASE 3: PostgreSQL Recovery & Self-Healing (PEL)
    # ----------------------------------------------------
    print("\n--- PHASE 3: Recovering PostgreSQL & Validating Self-Healing ---")
    # Start postgres container
    code, out, err = run_command(["docker", "compose", "start", "postgres"])
    if code != 0:
        print(f"[!] FAILED: Could not start postgres: {err}")
        sys.exit(1)
    print("[+] PostgreSQL container started. Waiting 10 seconds for DB warm-up...")
    time.sleep(10)

    # Wait for PEL retry loop (runs every 15 seconds) to process the pending entries
    print("[*] Waiting 20 seconds for the background worker's PEL loop to claim and reprocess un-ACKed signals...")
    time.sleep(20)

    # Check Database state
    print("[*] Querying database to verify zero data loss...")
    query_url = f"{WORKITEMS_URL}?component_id={TEST_COMPONENT}"
    req = urllib.request.Request(query_url)
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read().decode('utf-8'))
            items = data.get("items", [])
            print(f"\n[*] DB State for {TEST_COMPONENT}:")
            print(f"  Active Work Items: {len(items)} (Expected: exactly 1)")
            if items:
                signal_count = items[0].get("signal_count")
                print(f"  Incident Signal Count: {signal_count} (Expected: exactly 6 [1 baseline + 5 during outage])")
                
                if len(items) == 1 and signal_count == 6:
                    print("\n[+] SUCCESS: PEL claiming self-healed perfectly! 0 signals were lost!")
                else:
                    print("\n[!] FAILED: Data mismatch! Signals were lost or duplicate incidents created.")
                    sys.exit(1)
            else:
                print("\n[!] FAILED: No active incident found in PostgreSQL! Signals were lost.")
                sys.exit(1)
    except Exception as e:
        print(f"[!] FAILED to query work items: {e}")
        sys.exit(1)

    # ----------------------------------------------------
    # PHASE 4: Cache (Redis) Outage Simulation
    # ----------------------------------------------------
    print("\n--- PHASE 4: Simulating Redis Outage ---")
    # Stop redis container
    code, out, err = run_command(["docker", "compose", "stop", "redis"])
    if code != 0:
        print(f"[!] FAILED: Could not stop redis: {err}")
        sys.exit(1)
    print("[+] Redis container stopped.")

    # Try to ingest a signal while Redis is down
    print("[*] Sending ingestion request while Redis is DOWN...")
    status, res = send_ingest_request()
    print(f"  HTTP Response Status: {status}")
    print(f"  HTTP Response Body: {res}")
    
    if status == 503:
        print("[+] SUCCESS: API correctly caught cache error and returned HTTP 503 Service Unavailable!")
    else:
        print(f"[!] FAILED: API did not return 503 Service Unavailable. Got status: {status}")
        # Clean up
        run_command(["docker", "compose", "start", "redis"])
        sys.exit(1)

    # ----------------------------------------------------
    # PHASE 5: Redis Recovery & Auto-Recovery Verification
    # ----------------------------------------------------
    print("\n--- PHASE 5: Recovering Redis & Verifying Auto-Recovery ---")
    # Start redis container
    code, out, err = run_command(["docker", "compose", "start", "redis"])
    if code != 0:
        print(f"[!] FAILED: Could not start redis: {err}")
        sys.exit(1)
    print("[+] Redis container started. Waiting 5 seconds for cache connection warm-up...")
    time.sleep(5)

    # Ingest a new signal to verify recovery
    print("[*] Sending ingestion request after Redis recovery...")
    status, res = send_ingest_request()
    if status == 202:
        print("[+] SUCCESS: Signal ingestion recovered automatically (HTTP 202)!")
    else:
        print(f"[!] FAILED: Ingestion failed to recover after Redis restart. Status {status}: {res}")
        sys.exit(1)

    print("\n========================================================")
    print("🎉 ALL SRE CHAOS TEST SCENARIOS PASSED SUCCESSFULLY!")
    print("========================================================\n")

if __name__ == "__main__":
    test_chaos_failover()
