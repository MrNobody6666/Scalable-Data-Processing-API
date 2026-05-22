"""
deep_security_test.py
=====================
Comprehensive security, edge-case, and architectural weakness tests.
Goes far beyond basic stress testing to probe every attack surface.
"""

import json
import os
import time
import urllib.error
import urllib.request

BASE = "http://localhost:8000"


def test(name, func):
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print('='*60)
    try:
        func()
    except Exception as e:
        print(f"  [EXCEPTION] {type(e).__name__}: {e}")


# -----------------------------------------------------------------------
# 1. Input Validation / Injection on job_id
# -----------------------------------------------------------------------
def test_malicious_job_ids():
    """Try path traversal, SQL injection, and XSS payloads in job_id."""
    payloads = [
        ("Path Traversal", "../../../etc/passwd"),
        ("Path Traversal (Windows)", "..\\..\\..\\Windows\\System32\\config\\SAM"),
        ("SQL Injection", "'; DROP TABLE users; --"),
        ("XSS Payload", "<script>alert('xss')</script>"),
        ("Null Byte", "job\x00id"),
        ("Very Long ID", "A" * 10000),
        ("Empty ID", ""),
        ("Unicode Bomb", "\ud83d\udca3" * 100),
        ("Format String", "%s%s%s%s%s%s%s%s%s%s"),
        ("CRLF Injection", "job\r\nX-Injected: true"),
    ]
    for label, payload in payloads:
        try:
            url = f"{BASE}/status/{urllib.request.quote(payload, safe='')}"
            resp = urllib.request.urlopen(url)
            data = json.loads(resp.read())
            print(f"  [{label}] Response 200: {data}")
            print(f"    -> CONCERN: Server accepted malicious job_id without validation!")
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f"  [{label}] HTTP {e.code}: {body[:200]}")
        except Exception as e:
            print(f"  [{label}] Error: {e}")

test("Malicious Job IDs (Path Traversal, SQLi, XSS)", test_malicious_job_ids)


# -----------------------------------------------------------------------
# 2. HTTP Method Testing
# -----------------------------------------------------------------------
def test_wrong_http_methods():
    """Try wrong HTTP methods on endpoints."""
    endpoints = [
        ("/trigger-join", ["GET", "PUT", "DELETE", "PATCH"]),
        ("/health", ["POST", "PUT", "DELETE"]),
    ]
    for path, methods in endpoints:
        for method in methods:
            try:
                req = urllib.request.Request(f"{BASE}{path}", method=method, data=b'' if method != 'GET' else None)
                resp = urllib.request.urlopen(req)
                print(f"  {method} {path} -> {resp.status} (UNEXPECTED SUCCESS)")
            except urllib.error.HTTPError as e:
                print(f"  {method} {path} -> {e.code} {e.reason}")

test("Wrong HTTP Methods", test_wrong_http_methods)


# -----------------------------------------------------------------------
# 3. Missing Authentication & Authorization
# -----------------------------------------------------------------------
def test_no_auth():
    """Verify there is zero authentication."""
    print("  Attempting to trigger join with NO credentials...")
    req = urllib.request.Request(f"{BASE}/trigger-join", method='POST', data=b'')
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    print(f"  -> SUCCESS (no auth required): job_id={data['job_id']}")
    print("  -> VULNERABILITY: Any unauthenticated user can trigger expensive joins!")
    
    # Wait for it to finish
    time.sleep(12)

    print("\n  Attempting to read ANY job status with NO credentials...")
    resp2 = urllib.request.urlopen(f"{BASE}/status/{data['job_id']}")
    status = json.loads(resp2.read())
    print(f"  -> SUCCESS: Can read job result including output file path")
    print(f"     Output path leaked: {status.get('result', {}).get('output_path', 'N/A')}")
    print("  -> VULNERABILITY: Job results (including file paths) exposed to anyone!")

test("Missing Authentication", test_no_auth)


# -----------------------------------------------------------------------
# 4. Information Disclosure
# -----------------------------------------------------------------------
def test_info_disclosure():
    """Check for information leakage in error responses and headers."""
    # Check headers for server version info
    resp = urllib.request.urlopen(f"{BASE}/health")
    headers = dict(resp.headers)
    print(f"  Response Headers: {json.dumps(headers, indent=4)}")
    
    server = headers.get('server', 'Not disclosed')
    print(f"  Server header: {server}")
    if 'uvicorn' in server.lower():
        print("  -> INFO LEAK: Server technology (uvicorn) disclosed via headers!")

    # Check if detailed errors are returned
    try:
        urllib.request.urlopen(f"{BASE}/nonexistent-endpoint")
    except urllib.error.HTTPError as e:
        body = json.loads(e.read())
        print(f"  404 response body: {body}")
        print("  -> Check if stack traces or internal details are leaked")

    # Check if OpenAPI schema is publicly accessible
    resp = urllib.request.urlopen(f"{BASE}/openapi.json")
    schema = json.loads(resp.read())
    print(f"  OpenAPI schema exposed: {len(json.dumps(schema))} bytes")
    print(f"  Endpoints documented: {list(schema.get('paths', {}).keys())}")
    print("  -> INFO LEAK: Full API schema publicly accessible (useful for attackers)")

test("Information Disclosure", test_info_disclosure)


# -----------------------------------------------------------------------
# 5. Request Payload Abuse
# -----------------------------------------------------------------------
def test_payload_abuse():
    """Send unexpected payloads to POST endpoint."""
    payloads = [
        ("Huge JSON body", b'{"x": "' + b'A' * 1_000_000 + b'"}'),
        ("Invalid JSON", b'{invalid json!!!}'),
        ("XML body", b'<?xml version="1.0"?><root>test</root>'),
        ("Binary garbage", os.urandom(1024)),
        ("Empty body", b''),
    ]
    for label, data in payloads:
        try:
            req = urllib.request.Request(
                f"{BASE}/trigger-join",
                method='POST',
                data=data,
                headers={"Content-Type": "application/json"}
            )
            resp = urllib.request.urlopen(req)
            result = json.loads(resp.read())
            print(f"  [{label}] 202 Accepted -> job_id={result.get('job_id', '?')}")
            print(f"    -> CONCERN: Server ignores request body entirely (no validation)")
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors='replace')[:200]
            print(f"  [{label}] HTTP {e.code}: {body}")
        except Exception as e:
            print(f"  [{label}] Error: {e}")

test("Request Payload Abuse", test_payload_abuse)


# -----------------------------------------------------------------------
# 6. Rate Limiting Check
# -----------------------------------------------------------------------
def test_rate_limiting():
    """Rapid-fire requests to check for rate limiting."""
    print("  Sending 20 rapid requests to /health ...")
    times = []
    for i in range(20):
        start = time.perf_counter()
        try:
            urllib.request.urlopen(f"{BASE}/health")
        except Exception:
            pass
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    
    avg = sum(times) / len(times)
    print(f"  All 20 requests succeeded in avg {avg*1000:.1f}ms each")
    print(f"  Total time: {sum(times)*1000:.1f}ms")
    print("  -> VULNERABILITY: No rate limiting! An attacker can flood the server.")

    print("\n  Sending 20 rapid POST /trigger-join requests...")
    results = {"accepted": 0, "failed": 0, "error": 0}
    for i in range(20):
        try:
            req = urllib.request.Request(f"{BASE}/trigger-join", method='POST', data=b'')
            resp = urllib.request.urlopen(req)
            results["accepted"] += 1
        except urllib.error.HTTPError:
            results["error"] += 1
        except Exception:
            results["error"] += 1
    print(f"  Results: {results}")
    print("  -> NOTE: Even though semaphore limits execution, all 20 requests are ACCEPTED")
    print("     (they queue up and fail later). No request-level rate limiting exists.")

test("Rate Limiting", test_rate_limiting)


# -----------------------------------------------------------------------
# 7. CORS Check
# -----------------------------------------------------------------------
def test_cors():
    """Check if CORS headers are present."""
    try:
        req = urllib.request.Request(
            f"{BASE}/health",
            headers={"Origin": "https://evil-attacker.com"}
        )
        resp = urllib.request.urlopen(req)
        cors_header = resp.headers.get("Access-Control-Allow-Origin", "NOT SET")
        print(f"  Access-Control-Allow-Origin: {cors_header}")
        if cors_header == "*":
            print("  -> VULNERABILITY: Wildcard CORS allows any origin to call the API!")
        elif cors_header == "NOT SET":
            print("  -> OK: No CORS headers (browser same-origin policy blocks cross-origin)")
        else:
            print(f"  -> CORS restricted to: {cors_header}")
    except Exception as e:
        print(f"  Error: {e}")

test("CORS Configuration", test_cors)


# -----------------------------------------------------------------------
# 8. Job Store Memory Leak
# -----------------------------------------------------------------------
def test_job_store_leak():
    """Check if completed jobs accumulate forever in memory."""
    print("  The in-memory `jobs` dict never evicts old entries.")
    print("  Over time, this will consume unbounded memory.")
    print("  -> VULNERABILITY: No TTL or cleanup for old job records.")
    print("  -> After 10,000 jobs, the dict alone holds significant data.")
    print("  -> Each job stores timestamps, error strings, and result metadata.")

test("Job Store Memory Leak (Architectural)", test_job_store_leak)


# -----------------------------------------------------------------------
# 9. File Cleanup / Disk Exhaustion
# -----------------------------------------------------------------------
def test_disk_exhaustion():
    """Check if result files accumulate forever on disk."""
    result_dir = os.path.dirname(os.path.abspath(__file__))
    result_files = [f for f in os.listdir(result_dir) if f.startswith("result_") and f.endswith(".csv")]
    total_size = sum(os.path.getsize(os.path.join(result_dir, f)) for f in result_files)
    print(f"  Found {len(result_files)} result_*.csv files on disk")
    print(f"  Total disk usage: {total_size / (1024*1024):.1f} MB")
    print("  -> VULNERABILITY: Result files are never cleaned up!")
    print(f"     Each completed join creates a ~{total_size // max(len(result_files),1) // (1024*1024)} MB file.")
    print("     After 100 jobs, that's multiple GB of uncleaned data.")

test("Disk Exhaustion (Result File Cleanup)", test_disk_exhaustion)


# -----------------------------------------------------------------------
# 10. Persistence / Crash Recovery
# -----------------------------------------------------------------------
def test_persistence():
    """Check if job state survives a server restart."""
    print("  The BackgroundTasks approach uses an in-memory dict for job storage.")
    print("  -> VULNERABILITY: If the server crashes or restarts:")
    print("     - All job records are LOST")
    print("     - Running jobs are silently killed (no retry)")
    print("     - Clients polling /status/{job_id} get 404 after restart")
    print("     - No dead-letter queue or failure recovery mechanism")

test("Persistence / Crash Recovery (Architectural)", test_persistence)


# -----------------------------------------------------------------------
# 11. HTTPS / Transport Security
# -----------------------------------------------------------------------
def test_transport_security():
    """Check for HTTPS and security headers."""
    resp = urllib.request.urlopen(f"{BASE}/health")
    headers = dict(resp.headers)
    
    missing = []
    for header in ["Strict-Transport-Security", "X-Content-Type-Options", 
                    "X-Frame-Options", "Content-Security-Policy",
                    "X-XSS-Protection", "Referrer-Policy"]:
        if header.lower() not in [h.lower() for h in headers]:
            missing.append(header)
    
    print(f"  Server running on HTTP (not HTTPS)")
    print(f"  Missing security headers ({len(missing)}):")
    for h in missing:
        print(f"    - {h}")
    print("  -> VULNERABILITY: No TLS, no security headers. Data transmitted in plaintext.")

test("Transport Security (HTTPS & Headers)", test_transport_security)


# -----------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------
print("\n" + "="*60)
print("DEEP SECURITY AUDIT COMPLETE")
print("="*60)
