import urllib.request, json

headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

def test_post(name, url, payload):
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(f"http://127.0.0.1:9999{url}", data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            res_body = resp.read()
            parsed = json.loads(res_body)
            print(f"[POST OK] {name} ({url})")
            keys = list(parsed.keys()) if isinstance(parsed, dict) else len(parsed)
            print(f"       Keys/Count: {keys}")
            if isinstance(parsed, dict):
                for k in list(parsed.keys())[:4]:
                    val = str(parsed[k])[:80]
                    print(f"       {k}: {val}")
    except Exception as e:
        print(f"[POST FAIL] {name} ({url}) -> {e}")

# 1. Test compare_ai
test_post("Compare AI", "/api/compare_ai", {"symbols": ["FPT", "CMG"]})

# 2. Test portfolio analyze
test_post("Portfolio Analyze", "/api/portfolio/analyze", {"portfolio": [{"symbol": "FPT", "weight": 50}, {"symbol": "HPG", "weight": 50}]})

# 3. Test factcheck
test_post("Factcheck", "/api/factcheck", {"text": "FPT tăng trưởng doanh thu quý 3", "symbol": "FPT"})

# 4. Test quantum run
test_post("Quantum Run", "/api/quantum/run", {"symbols": ["FPT", "HPG", "VNM", "VIC"], "objective": "max_sharpe", "risk_aversion": 0.5})

# 5. Test Copilot ask
test_post("Copilot Ask", "/api/copilot/ask", {"question": "Đánh giá tình hình tài chính của FPT"})
