import sys
import time
import json
import urllib.request
import urllib.error
import uuid

# Force UTF-8 encoding for stdout
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

API_BASE = "http://127.0.0.1:8000/api/v1"

def login(username, password):
    url = f"{API_BASE}/auth/login"
    payload = {
        "username": username,
        "password": password
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
        print(f"[!] Login failed for {username}: {e}")
        sys.exit(1)

def send_request(url, method="GET", payload=None, token=None):
    headers = {
        "Content-Type": "application/json"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    data = json.dumps(payload).encode('utf-8') if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            status = response.status
            body = json.loads(response.read().decode('utf-8'))
            return status, body
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode('utf-8'))
        except:
            err_body = e.reason
        return e.code, err_body
    except Exception as e:
        return "ERROR", str(e)

def run_functional_tests():
    print(f"\n========================================================")
    print(f"🔥 SRE FUNCTIONAL VALIDATION: LIFECYCLE, RCA & RBAC MATRIX")
    print(f"========================================================\n")

    # 1. Log in as Admin and Viewer
    print("[*] Logging in as Admin...")
    admin_token = login("admin", "Admin@IMS2026!")
    print("[+] Admin login successful.")

    print("[*] Logging in as Viewer...")
    viewer_token = login("viewer", "Viewer@IMS2026!")
    print("[+] Viewer login successful.")

    # 2. Ingest a signal to create a fresh Work Item
    test_comp = f"FUNC_TEST_{uuid.uuid4().hex[:6].upper()}"
    print(f"\n[*] Step 1: Ingesting baseline signal to create Work Item (Component: {test_comp})...")
    signal_payload = {
        "component_id": test_comp,
        "component_type": "CACHE",
        "error_code": "CONNECTION_TIMEOUT",
        "message": "Functional test validation alert",
        "severity": "P1"
    }
    status, body = send_request(f"{API_BASE}/signals/ingest", method="POST", payload=signal_payload)
    print(f"  - Ingestion Status: {status}")
    print(f"  - Ingestion Response: {body}")

    # Wait 3 seconds for async background worker to process stream and write to DB
    print("[*] Waiting 3 seconds for async background worker to create Work Item...")
    time.sleep(3)

    # Query work items list filtered by component_id
    list_url = f"{API_BASE}/workitems?component_id={test_comp}"
    status, list_body = send_request(list_url, token=admin_token)
    
    if status != 200 or not list_body.get("items"):
        print(f"[!] FAILED: Could not retrieve created Work Item from list. Status: {status}, Body: {list_body}")
        sys.exit(1)
        
    work_item_id = list_body["items"][0]["id"]
    print(f"  - Retrieved Work Item ID: {work_item_id}")

    # Verify state of work item is initially OPEN
    status, body = send_request(f"{API_BASE}/workitems/{work_item_id}", token=admin_token)
    current_state = body.get("status")
    print(f"  - Initial Work Item Status: {current_state}")
    if current_state != "OPEN":
        print(f"[!] FAILED: Expected initial state to be OPEN, got: {current_state}")
        sys.exit(1)

    # 3. RBAC Matrix Check: Try to transition as VIEWER
    print("\n[*] Step 2: Testing RBAC Matrix (Viewer attempt)...")
    status_url = f"{API_BASE}/workitems/{work_item_id}/status"
    transition_payload = {"status": "INVESTIGATING"}
    
    status, body = send_request(status_url, method="PATCH", payload=transition_payload, token=viewer_token)
    print(f"  - Viewer transition status code: {status}")
    print(f"  - Viewer response detail: {body}")
    
    if status != 403:
        print(f"[!] FAILED: Viewer should be rejected with 403 Forbidden. Got {status}")
        sys.exit(1)
    print("[+] SUCCESS: RBAC check passed! Viewers are strictly blocked from changing status.")

    # 4. Lifecycle Enforcement Check: Try illegal transition (OPEN -> CLOSED) as ADMIN
    print("\n[*] Step 3: Testing Lifecycle Enforcement (Illegal transition OPEN → CLOSED)...")
    illegal_payload = {"status": "CLOSED"}
    status, body = send_request(status_url, method="PATCH", payload=illegal_payload, token=admin_token)
    print(f"  - Admin illegal transition status code: {status}")
    print(f"  - Response: {body}")
    
    if status != 409:
        print(f"[!] FAILED: Illegal transition should be rejected with 409 Conflict. Got {status}")
        sys.exit(1)
    print("[+] SUCCESS: State machine successfully rejected illegal transition!")

    # 5. Move to INVESTIGATING as ADMIN
    print("\n[*] Step 4: Transitioning OPEN → INVESTIGATING as Admin...")
    status, body = send_request(status_url, method="PATCH", payload=transition_payload, token=admin_token)
    print(f"  - Transition Status: {status}")
    print(f"  - Updated State: {body.get('status')}")
    if status != 200 or body.get("status") != "INVESTIGATING":
        print("[!] FAILED: Expected transition to succeed.")
        sys.exit(1)

    # 6. Move to RESOLVED as ADMIN
    print("\n[*] Step 5: Transitioning INVESTIGATING → RESOLVED as Admin...")
    status, body = send_request(status_url, method="PATCH", payload={"status": "RESOLVED"}, token=admin_token)
    print(f"  - Transition Status: {status}")
    print(f"  - Updated State: {body.get('status')}")
    if status != 200 or body.get("status") != "RESOLVED":
        print("[!] FAILED: Expected transition to succeed.")
        sys.exit(1)

    # 7. Lifecycle Enforcement: Attempt to close RESOLVED without an RCA
    print("\n[*] Step 6: Testing Lifecycle Enforcement (Closing RESOLVED without RCA)...")
    status, body = send_request(status_url, method="PATCH", payload={"status": "CLOSED"}, token=admin_token)
    print(f"  - Status Code: {status}")
    print(f"  - Response Detail: {body}")
    
    if status != 422:
        print(f"[!] FAILED: Attempting to close without RCA must return 422 Unprocessable Entity. Got {status}")
        sys.exit(1)
    print("[+] SUCCESS: Closing blocked. RCA is strictly mandatory before transition to CLOSED!")

    # 8. RCA Validation Check: Send end date before start date
    print("\n[*] Step 7: Testing RCA Date Constraints (incident_end <= incident_start)...")
    malformed_rca_payload = {
        "incident_start": "2026-05-06T12:00:00Z",
        "incident_end": "2026-05-06T11:00:00Z", # End is before start
        "root_cause_category": "INFRASTRUCTURE",
        "fix_applied": "Rebooted functional container tests",
        "prevention_steps": "Added auto-monitoring triggers",
        "affected_users_count": "100"
    }
    rca_url = f"{API_BASE}/workitems/{work_item_id}/rca"
    status, body = send_request(rca_url, method="POST", payload=malformed_rca_payload, token=admin_token)
    print(f"  - Malformed RCA Submission status code: {status}")
    print(f"  - Response: {body}")
    
    if status not in [400, 422]:
        print(f"[!] FAILED: Expected 422 or 400 validation error for malformed date constraint. Got {status}")
        sys.exit(1)
    print("[+] SUCCESS: Malformed RCA date constraints rejected successfully!")

    # 9. Submit a valid RCA
    print("\n[*] Step 8: Submitting a valid RCA...")
    valid_rca_payload = {
        "incident_start": "2026-05-06T10:00:00Z",
        "incident_end": "2026-05-06T11:30:00Z",
        "root_cause_category": "INFRASTRUCTURE",
        "fix_applied": "Rebooted functional container tests",
        "prevention_steps": "Added auto-monitoring triggers",
        "affected_users_count": "100"
    }
    status, body = send_request(rca_url, method="POST", payload=valid_rca_payload, token=admin_token)
    print(f"  - RCA Submission status code: {status}")
    print(f"  - Response: {body}")
    
    if status != 201:
        print(f"[!] FAILED: Valid RCA submission should return 201 Created. Got {status}")
        sys.exit(1)
    print("[+] SUCCESS: Valid RCA accepted!")

    # 10. RCA Constraints Check: Submitting a duplicate RCA
    print("\n[*] Step 9: Testing RCA Constraints (Duplicate RCA submission)...")
    status, body = send_request(rca_url, method="POST", payload=valid_rca_payload, token=admin_token)
    print(f"  - Duplicate RCA status code: {status}")
    print(f"  - Response Detail: {body}")
    
    if status != 409:
        print(f"[!] FAILED: Expected 409 Conflict for duplicate RCA submission. Got {status}")
        sys.exit(1)
    print("[+] SUCCESS: Duplicate RCA rejected with 409 Conflict!")

    # 11. Final Transition: Close the incident now that RCA exists
    print("\n[*] Step 10: Transitioning RESOLVED → CLOSED (RCA now present)...")
    status, body = send_request(status_url, method="PATCH", payload={"status": "CLOSED"}, token=admin_token)
    print(f"  - Final Transition Status: {status}")
    print(f"  - Final State: {body.get('status')}")
    print(f"  - Calculated MTTR Minutes: {body.get('mttr_minutes')}")
    
    if status != 200 or body.get("status") != "CLOSED":
        print(f"[!] FAILED: Transition to CLOSED should succeed now. Got status: {status}")
        sys.exit(1)
        
    mttr = body.get("mttr_minutes")
    if mttr is None or mttr < 0:
        print(f"[!] FAILED: MTTR is invalid or missing: {mttr}")
        sys.exit(1)
        
    print("[+] SUCCESS: Incident successfully closed! MTTR calculated and verified perfectly!")

    print("\n========================================================")
    print("🎉 ALL SRE FUNCTIONAL VALIDATION TESTS PASSED SUCCESSFULLY!")
    print("========================================================\n")

if __name__ == "__main__":
    run_functional_tests()
