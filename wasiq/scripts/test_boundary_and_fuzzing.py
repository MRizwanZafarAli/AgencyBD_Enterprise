import urllib.request
import urllib.error
import json
import time

BASE_URL = "http://localhost:8001"
ADMIN_KEY = "agy_live_9e614f185dc6fdf9d13560bfa539118e8d87aaeaff9045fa"

headers = {
    "X-API-Key": ADMIN_KEY,
    "Content-Type": "application/json"
}

def make_req(method, endpoint, body=None):
    url = f"{BASE_URL}{endpoint}"
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            elapsed = time.time() - start
            raw = resp.read().decode('utf-8')
            return {
                "endpoint": f"{method} {endpoint}",
                "status": resp.status,
                "elapsed_ms": int(elapsed * 1000),
                "is_500": False,
                "data": raw[:150]
            }
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start
        raw = e.read().decode('utf-8')
        return {
            "endpoint": f"{method} {endpoint}",
            "status": e.code,
            "elapsed_ms": int(elapsed * 1000),
            "is_500": e.code >= 500,
            "data": raw[:150]
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "endpoint": f"{method} {endpoint}",
            "status": 0,
            "elapsed_ms": int(elapsed * 1000),
            "is_500": True,
            "error": str(e)
        }

fuzz_cases = [
    # 1. Non-existent IDs (Should return 404, NEVER 500)
    ("POST", "/api/proposals/999999/send", {"channel": "email", "recipient": "test@example.com", "body": "test"}),
    ("POST", "/api/opportunities/999999/analyze", None),
    ("POST", "/api/proposals/draft", {"opportunity_id": 999999}),
    ("GET", "/api/clients/999999", None),
    ("POST", "/api/clients/999999/notes", {"body": "test"}),
    ("GET", "/api/audits/999999", None),
    ("GET", "/api/evidence/999999", None),
    ("GET", "/api/autopilot/runs/run_nonexistent", None),
    ("POST", "/api/approvals/999999/decide", {"decision": "approved"}),

    # 2. Invalid platform names (Should return 404 or 422, NEVER 500)
    ("GET", "/api/channels/invalid_platform_xyz/records", None),
    ("GET", "/api/channels/invalid_platform_xyz/summary", None),
    ("POST", "/api/channels/invalid_platform_xyz/records", {"type": "routine", "data": {"label": "test"}}),

    # 3. Text length boundaries & NLP edge cases
    ("POST", "/api/channels/parse", {"text": ""}),
    ("POST", "/api/channels/parse", {"text": "A" * 399}),
    ("POST", "/api/channels/parse", {"text": "A" * 450}),
    ("POST", "/api/search/parse", {"q": ""}),
    ("POST", "/api/search/parse", {"q": "test emoji query 123"}),
    ("POST", "/api/search/parse", {"q": "' OR '1'='1"}),

    # 4. SSRF & Security boundary testing (Must block internal/private ranges cleanly)
    ("POST", "/api/audits/run", {"domain": "127.0.0.1"}),
    ("POST", "/api/audits/run", {"domain": "localhost"}),
    ("POST", "/api/audits/run", {"domain": "169.254.169.254"}),
    ("POST", "/api/audits/run", {"domain": "10.0.0.1"}),
    ("POST", "/api/native/fingerprint_tech", {"domain": "127.0.0.1"}),

    # 5. Email verification edge cases
    ("POST", "/api/native/verify_email", {"email": ""}),
    ("POST", "/api/native/verify_email", {"email": "not-an-email"}),
    ("POST", "/api/native/verify_email", {"email": "user@"}),
    ("POST", "/api/native/verify_email", {"email": "@domain.com"}),
    ("POST", "/api/native/verify_email", {"email": "a" * 200 + "@example.com"}),

    # 6. Copy coach & Sales call analysis edge cases
    ("POST", "/api/native/score_copy", {"subject": "", "body": ""}),
    ("POST", "/api/native/score_copy", {"subject": "Normal Subject", "body": "A" * 10000}),
    ("POST", "/api/native/analyze_sales_call", {"transcript": ""}),
    ("POST", "/api/native/analyze_sales_call", {"transcript": "Gibberish without speaker tags: hello world how are you"}),

    # 7. Local hunt edge cases
    ("POST", "/api/hunt/local", {"category": "", "city": ""}),
    ("POST", "/api/hunt/local", {"category": "dentists", "city": "NonExistentCityXYZ12345", "limit": 1}),
]

print(f"Running {len(fuzz_cases)} Edge-Case & Boundary Tests...\n", flush=True)

bugs = []
for m, p, b in fuzz_cases:
    res = make_req(m, p, b)
    is_500 = res.get('is_500', False)
    status_str = f"[{res['status']}]"
    clean_preview = res.get('data', '')[:60].encode('ascii', errors='replace').decode('ascii')
    
    if is_500:
        print(f"CRITICAL 500 {status_str:<6} {res['endpoint']:<45} ({res['elapsed_ms']}ms) -> {clean_preview}", flush=True)
        bugs.append((res['endpoint'], res['status'], res.get('data', '')))
    else:
        print(f"CLEAN {status_str:<6} {res['endpoint']:<45} ({res['elapsed_ms']}ms) -> {clean_preview}", flush=True)

print(f"\n==========================================", flush=True)
print(f"Total Fuzzed: {len(fuzz_cases)} | 500 Errors: {len(bugs)}", flush=True)
print(f"==========================================", flush=True)

if bugs:
    print(f"\nDiscovered {len(bugs)} Unhandled 500 Bugs:")
    for ep, st, d in bugs:
        print(f"  {ep} -> HTTP {st}: {d}")
else:
    print("\nALL boundary tests passed cleanly with proper HTTP client codes (200, 400, 404, 422). ZERO 500 errors!")
