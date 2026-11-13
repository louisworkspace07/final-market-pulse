import urllib.request
import urllib.error
import http.client
import time
import json
import ssl
import re

BASE_URL = "https://vercel-full-deployment.vercel.app"

def request_url(url, method="GET", headers=None, body=None, timeout=30):
    t0 = time.time()
    req_headers = {"User-Agent": "Reviewer2-AdversarialAudit/1.0"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            dur = time.time() - t0
            return {
                "status": resp.status,
                "headers": dict(resp.headers),
                "data": data,
                "duration": dur,
                "error": None
            }
    except urllib.error.HTTPError as e:
        dur = time.time() - t0
        data = e.read()
        return {
            "status": e.code,
            "headers": dict(e.headers),
            "data": data,
            "duration": dur,
            "error": f"HTTPError {e.code}"
        }
    except Exception as e:
        dur = time.time() - t0
        return {
            "status": -1,
            "headers": {},
            "data": b"",
            "duration": dur,
            "error": str(e)
        }

print("=== STARTING COMPREHENSIVE REVIEW AUDIT ===")

# 1. VERIFY PAGES AND REVERSE PROXIES OVER HTTPS
print("\n--- 1. Testing Pages and Reverse Proxies ---")
test_endpoints = [
    ("Dashboard /", f"{BASE_URL}/", 200),
    ("Overview /banggia", f"{BASE_URL}/banggia", 200),
    ("Compare /so-sanh", f"{BASE_URL}/so-sanh", 200),
    ("Screener /bo-loc", f"{BASE_URL}/bo-loc", 200),
    ("Glossary /kien-thuc", f"{BASE_URL}/kien-thuc", 200),
    ("Getting Started /bat-dau", f"{BASE_URL}/bat-dau", 200),
    ("Portfolio /portfolio", f"{BASE_URL}/portfolio", 200),
    ("Copilot /copilot", f"{BASE_URL}/copilot", 200),
    ("Soitin /soitin", f"{BASE_URL}/soitin", 200),
    ("Health API", f"{BASE_URL}/api/health", 200),
    ("Embed Banggia HTML", f"{BASE_URL}/embed_banggia/", 200),
    ("Embed Banggia CSS", f"{BASE_URL}/embed_banggia/style.css?v=8", 200),
    ("Embed Banggia JS", f"{BASE_URL}/embed_banggia/app.js?v=19", 200),
    ("Embed Banggia API Stocks", f"{BASE_URL}/embed_banggia/api/stocks", 200),
    ("Embed Econolens HTML", f"{BASE_URL}/embed_econolens/", 200),
    ("Embed Econolens JS", f"{BASE_URL}/embed_econolens/app.js", 200),
    ("Embed Econolens API Meta", f"{BASE_URL}/embed_econolens/api/meta", 401),
    ("Embed Crawl UI", f"{BASE_URL}/embed_crawl/app/", 200),
    ("Embed Crawl VN30", f"{BASE_URL}/embed_crawl/api/group_members?group=VN30", 200),
]

for name, ep, exp_status in test_endpoints:
    res = request_url(ep)
    match = res["status"] == exp_status
    print(f"[{'PASS' if match else 'FAIL'}] {name:<30} -> Status: {res['status']} (Exp: {exp_status}) | Time: {res['duration']:.3f}s | Size: {len(res['data'])} B")
    if not match and res["error"]:
        print(f"       Error: {res['error']}")

# 2. CHECK MIXED CONTENT AND ASSET RELATIVE PATHS
print("\n--- 2. Checking Static Assets for Insecure References / Mixed Content ---")
for asset_name, asset_url in [
    ("Embed Banggia HTML", f"{BASE_URL}/embed_banggia/"),
    ("Embed Banggia JS", f"{BASE_URL}/embed_banggia/app.js?v=19"),
    ("Embed Econolens HTML", f"{BASE_URL}/embed_econolens/"),
    ("Embed Econolens JS", f"{BASE_URL}/embed_econolens/app.js"),
    ("Dashboard HTML", f"{BASE_URL}/"),
]:
    res = request_url(asset_url)
    text = res["data"].decode("utf-8", errors="replace")
    # Check for hardcoded http:// or 127.0.0.1 or localhost (excluding external cdns like highcharts)
    insecure_matches = re.findall(r'http://(?:127\.0\.0\.1|localhost|[\w.-]+)', text)
    # Filter out standard schemas or harmless mentions in comments if any
    suspicious = [m for m in insecure_matches if "w3.org" not in m and "schemas.org" not in m]
    print(f"[{'PASS' if len(suspicious) == 0 else 'FAIL'}] {asset_name}: {len(suspicious)} insecure http:// references found. {suspicious[:3] if suspicious else ''}")

# 3. CORS PREFLIGHT AND HEADERS AUDIT
print("\n--- 3. Testing CORS Headers & OPTIONS Preflight ---")
cors_tests = [
    ("OPTIONS /api/market/board", f"{BASE_URL}/api/market/board", "OPTIONS", {"Origin": "https://custom-domain.com", "Access-Control-Request-Method": "GET"}),
    ("GET /api/market/board", f"{BASE_URL}/api/market/board", "GET", {"Origin": "https://custom-domain.com"}),
    ("OPTIONS /api/health", f"{BASE_URL}/api/health", "OPTIONS", {"Origin": "https://random-site.org", "Access-Control-Request-Method": "GET"}),
    ("GET /api/health", f"{BASE_URL}/api/health", "GET", {"Origin": "https://random-site.org"}),
    ("OPTIONS /embed_banggia/api/stocks", f"{BASE_URL}/embed_banggia/api/stocks", "OPTIONS", {"Origin": "https://another-client.io", "Access-Control-Request-Method": "GET"}),
]

for name, url, meth, hdrs in cors_tests:
    res = request_url(url, method=meth, headers=hdrs)
    allow_origin = res["headers"].get("access-control-allow-origin") or res["headers"].get("Access-Control-Allow-Origin")
    allow_methods = res["headers"].get("access-control-allow-methods") or res["headers"].get("Access-Control-Allow-Methods")
    print(f"[{'PASS' if allow_origin == '*' else 'FAIL'}] {name:<35} -> Status: {res['status']} | Allow-Origin: '{allow_origin}' | Allow-Methods: '{allow_methods}'")

# 4. TESTING IN-MEMORY BOARD CACHE ON /api/market/board
print("\n--- 4. Testing Board Cache (TTL, Latency, Integrity) ---")
# Call 1 (Warm / Fetch)
r1 = request_url(f"{BASE_URL}/api/market/board")
print(f"Call 1 (Initial): Status {r1['status']} | Latency: {r1['duration']:.3f}s | Size: {len(r1['data'])} B")
try:
    d1 = json.loads(r1["data"])
    rows1 = d1.get("rows", [])
    has_liq = "liquidity" in d1
    print(f"       Data integrity: JSON valid | rows count: {len(rows1)} | liquidity annotated: {has_liq}")
    if rows1:
        s0 = rows1[0]
        print(f"       Sample row keys: {list(s0.keys())[:8]} | tradable={s0.get('tradable')} gtgd20={s0.get('gtgd20')}")
except Exception as e:
    print(f"       Data integrity check FAILED: {e}")

# Call 2 (Immediate Cache Hit)
time.sleep(1)
r2 = request_url(f"{BASE_URL}/api/market/board")
print(f"Call 2 (Cache Hit): Status {r2['status']} | Latency: {r2['duration']:.3f}s | Size: {len(r2['data'])} B")
speedup = (r1['duration'] / r2['duration']) if r2['duration'] > 0 else 1.0
print(f"       Cache speedup: {speedup:.1f}x (from {r1['duration']:.3f}s to {r2['duration']:.3f}s)")
print(f"       Identical payload size: {len(r1['data']) == len(r2['data'])}")

# Call 3 (After TTL Expiration - waiting 21 seconds)
print("Waiting 21s for TTL cache expiration (TTL=20s)...")
time.sleep(21)
r3 = request_url(f"{BASE_URL}/api/market/board")
print(f"Call 3 (Post-TTL Expiration): Status {r3['status']} | Latency: {r3['duration']:.3f}s | Size: {len(r3['data'])} B")
try:
    d3 = json.loads(r3["data"])
    rows3 = d3.get("rows", [])
    print(f"       Post-TTL integrity: valid JSON, {len(rows3)} rows")
except Exception as e:
    print(f"       Post-TTL check FAILED: {e}")

# Rapid Concurrent/Back-to-back stress test (5 requests)
print("\n--- 5. Rapid Stress Testing on /api/market/board ---")
stress_durations = []
for i in range(5):
    rs = request_url(f"{BASE_URL}/api/market/board")
    stress_durations.append(rs["duration"])
    print(f"  Stress req {i+1}: Status {rs['status']} | Latency {rs['duration']:.3f}s")
avg_stress = sum(stress_durations) / len(stress_durations)
print(f"Average cache response under rapid requests: {avg_stress:.3f}s")

# 6. CLICKABILITY & FALLBACK HANDLING FOR NON-DB BOARD TICKERS
print("\n--- 6. Testing Stock Clickability & Fallbacks ---")
test_tickers = [
    ("FPT", "Standard DB Ticker"),
    ("VNM", "Standard DB Ticker"),
    ("HPG", "Standard DB Ticker"),
    ("DMX", "Non-DB Active Board Ticker"),
    ("LPS", "Non-DB Active Board Ticker"),
    ("KAI", "Non-DB Active Board Ticker"),
    ("V68", "Non-DB Active Board Ticker"),
    ("ULG", "Non-DB Active Board Ticker"),
    ("PCB", "Non-DB Active Board Ticker"),
    ("NONEXISTENT_XYZ", "Adversarial Nonexistent Ticker"),
]

for sym, desc in test_tickers:
    r = request_url(f"{BASE_URL}/api/stock/{sym}")
    if r["status"] == 200:
        try:
            sd = json.loads(r["data"])
            is_fallback = sd.get("meta", {}).get("is_live_fallback", False)
            sym_resp = sd.get("info", {}).get("symbol")
            print(f"[{'PASS'}] {sym:<16} ({desc}) -> Status 200 | Symbol: {sym_resp} | is_fallback: {is_fallback}")
        except Exception as ex:
            print(f"[FAIL] {sym:<16} -> Status 200 but JSON invalid: {ex}")
    else:
        print(f"[{'INFO' if sym == 'NONEXISTENT_XYZ' else 'FAIL'}] {sym:<16} ({desc}) -> Status {r['status']} | Response: {r['data'][:60]}")

print("\n=== AUDIT RUN FINISHED ===")
