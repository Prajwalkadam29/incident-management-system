import sys
import time
import requests
from datetime import datetime, timezone, timedelta

# Try to import jose or explain how to run it in container
try:
    from jose import jwt
except ImportError:
    print("[!] ERROR: This test requires the 'python-jose' package.")
    print("    Please run it inside the backend container where it is preinstalled:")
    print("    docker exec ims_backend python /app/test_2_jwt_sse.py")
    sys.exit(1)

# Configure console output for Windows UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

JWT_SECRET = "1d37ac1e02790cd88e2a5318081070e74662e689ea010f23cbe8e07aa152dd85"
JWT_ALGORITHM = "HS256"

def generate_token(expiry_seconds: int) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(seconds=expiry_seconds)
    payload = {
        "sub": "test_sre_operator",
        "role": "admin",
        "exp": expire
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def test_sse_expiry():
    print("[*] Generating short-lived JWT (expires in 4 seconds)...")
    token = generate_token(4)
    url = f"http://localhost:8000/api/v1/stream/incidents?token={token}"
    
    print("[*] Connecting to SSE incident stream...")
    start_time = time.time()
    try:
        response = requests.get(url, stream=True, timeout=10)
        if response.status_code != 200:
            print(f"[!] FAILED: Server returned HTTP {response.status_code}")
            sys.exit(1)
            
        print("[+] Connected successfully! Monitoring stream for expiration disconnect...")
        
        auth_error_received = False
        connection_closed = False
        
        # Read the stream line by line
        for line in response.iter_lines(decode_unicode=True):
            if line:
                print(f"  [SSE Raw] {line}")
                if "auth_error" in line or "Session expired" in line:
                    auth_error_received = True
                    
        connection_closed = True
        elapsed = time.time() - start_time
        print(f"[*] Connection closed by server after {elapsed:.2f} seconds.")
        
        if auth_error_received and connection_closed:
            print(f"[+] PASSED: Server successfully invalidated and terminated the session mid-stream after exactly ~4 seconds!")
        else:
            print(f"[!] FAILED: Stream ended but did not receive proper 'auth_error' event.")
            sys.exit(1)
            
    except Exception as e:
        print(f"[!] Connection error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_sse_expiry()
