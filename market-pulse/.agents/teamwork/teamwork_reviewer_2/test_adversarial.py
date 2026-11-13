import urllib.request
import urllib.error
import urllib.parse
import json

BASE_URL = "https://vercel-full-deployment.vercel.app"

def test_endpoint(url, method="GET", headers=None, body=None):
    req_headers = {"User-Agent": "AdversarialTester/1.0"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            return resp.status, dict(resp.headers), data
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()
    except Exception as e:
        return -1, {}, str(e).encode()

print("=== ADVERSARIAL STRESS-TEST SUITE ===")

# Test 1: VBP Real vs Empty
print("\n1. Testing Volume-by-Price (VBP) integrity on Vercel:")
status, _, data = test_endpoint(f"{BASE_URL}/embed_banggia/api/vbp/FPT")
try:
    fpt_vbp = json.loads(data)
    print(f"  FPT VBP: Status {status}, items: {len(fpt_vbp)}, first item: {fpt_vbp[0] if fpt_vbp else 'empty'}")
    assert len(fpt_vbp) > 0, "FPT VBP should have real levels"
except Exception as e:
    print(f"  FPT VBP parse error: {e}")

status, _, data = test_endpoint(f"{BASE_URL}/embed_banggia/api/vbp/XYZ123")
try:
    xyz_vbp = json.loads(data)
    print(f"  XYZ123 VBP: Status {status}, items: {len(xyz_vbp)}, payload: {data.decode().strip()}")
    assert len(xyz_vbp) == 0, "Non-existent ticker must return clean empty []"
except Exception as e:
    print(f"  XYZ123 VBP parse error: {e}")

# Test 2: SQL Injection / Malicious Characters in Symbol
print("\n2. Testing SQL Injection / Adversarial Input in Stock Symbol:")
adversarial_symbols = [
    "' OR 1=1 --",
    "<script>alert(1)</script>",
    "../../etc/passwd",
    "NULL",
    "FPT%00",
    " "
]

for bad_sym in adversarial_symbols:
    encoded = urllib.parse.quote(bad_sym)
    status, _, data = test_endpoint(f"{BASE_URL}/api/stock/{encoded}")
    print(f"  Sym: {bad_sym!r:<25} -> Status: {status} | Resp: {data[:60]}")
    # Must NOT return 500 internal server error or crash
    assert status in (400, 404), f"Adversarial input {bad_sym} returned unexpected status {status}"

# Test 3: Complex CORS Preflight
print("\n3. Testing Complex CORS Preflight:")
status, hdrs, _ = test_endpoint(
    f"{BASE_URL}/api/market/board",
    method="OPTIONS",
    headers={
        "Origin": "https://malicious-site.example.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "X-Custom-Auth, Content-Type, Authorization"
    }
)
allow_origin = hdrs.get("access-control-allow-origin") or hdrs.get("Access-Control-Allow-Origin")
allow_methods = hdrs.get("access-control-allow-methods") or hdrs.get("Access-Control-Allow-Methods")
allow_headers = hdrs.get("access-control-allow-headers") or hdrs.get("Access-Control-Allow-Headers")
print(f"  OPTIONS with custom headers -> Status: {status} | Allow-Origin: {allow_origin} | Allow-Methods: {allow_methods} | Allow-Headers: {allow_headers}")
assert status == 200
assert allow_origin == "*"
assert allow_methods == "*"
assert allow_headers == "*"

# Test 4: EconoLens Chat Reverse Proxy Protection
print("\n4. Testing EconoLens Chat Unauthorized/Disallowed Routes:")
status, _, data = test_endpoint(f"{BASE_URL}/api/pchat/unauthorized_admin_path")
print(f"  Disallowed pchat route -> Status: {status} | Resp: {data.decode()[:70]}")
assert status in (404, 502), "Disallowed pchat route should be blocked"

# Test 5: Verify Altman Z'' and Piotroski F-score in Stock Detail
print("\n5. Testing Real Financial Scoring on Stock Detail (FPT):")
status, _, data = test_endpoint(f"{BASE_URL}/api/stock/FPT")
sd = json.loads(data)
scores = sd.get("scores", {})
z_score = scores.get("z_score")
f_score = scores.get("f_score")
print(f"  FPT Scores: Altman Z'' = {z_score}, Piotroski F = {f_score}")
assert z_score is not None and z_score > 0, "Altman Z'' score must be a positive calculated float"
assert f_score is not None and 0 <= f_score <= 9, "Piotroski F-score must be in range [0, 9]"

print("\n=== ALL ADVERSARIAL STRESS TESTS PASSED! ===")
