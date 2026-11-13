import urllib.request
import urllib.error
import json
import time

BASE_VERCEL = "https://vercel-full-deployment.vercel.app"
BASE_LOCAL = "http://127.0.0.1:9999"

TEST_ROUTES = [
    # Static & HTML pages
    ("/", "GET"),
    ("/banggia", "GET"),
    ("/copilot", "GET"),
    ("/data", "GET"),
    ("/so-sanh", "GET"),
    ("/bo-loc", "GET"),
    ("/kien-thuc", "GET"),
    ("/bat-dau", "GET"),
    ("/design-v3", "GET"),
    ("/quantum-lab", "GET"),
    ("/co-phieu/FPT", "GET"),
    ("/co-phieu/VNM", "GET"),
    
    # Embedded proxies
    ("/embed_banggia/", "GET"),
    ("/embed_banggia/style.css", "GET"),
    ("/embed_banggia/app.js", "GET"),
    ("/embed_econolens/", "GET"),
    ("/embed_econolens/style.css", "GET"),
    ("/embed_econolens/app.js", "GET"),
    ("/embed_crawl/", "GET"),
    ("/embed_crawl/app/", "GET"),
    
    # API endpoints
    ("/api/health", "GET"),
    ("/api/services", "GET"),
    ("/api/children/status", "GET"),
    ("/api/stock/FPT", "GET"),
    ("/api/stock/FPT/analysis", "GET"),
    ("/api/stock/FPT/charts", "GET"),
    ("/api/stock/FPT/sources", "GET"),
    ("/api/market/board", "GET"),
    ("/api/live", "GET"),
    ("/api/index_history", "GET"),
    ("/api/market/heatmap", "GET"),
    ("/api/market/regime", "GET"),
    ("/api/market/anomalies", "GET"),
    ("/api/crawl/coverage", "GET"),
    
    # Static CSS/JS files
    ("/static/style.css", "GET"),
    ("/static/design/tokens.css", "GET"),
    ("/static/design/tokens-v3.css", "GET"),
    ("/static/design/style-v3.css", "GET"),
    ("/static/js/common.js", "GET"),
    ("/static/js/chart-v3.js", "GET"),
    
    # Edge cases / known problem routes
    ("/style.css", "GET"),
    ("/api/stocks", "GET"),
    ("/api/meta", "GET"),
    ("/api/group_members", "GET"),
]

def check_url(base, path, method="GET"):
    url = base + path
    req = urllib.request.Request(url, method=method, headers={
        "User-Agent": "MarketPulseSurveyBot/1.0",
        "ngrok-skip-browser-warning": "true"
    })
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            elapsed = (time.time() - t0) * 1000
            content = resp.read()
            return {
                "url": url,
                "status": resp.status,
                "length": len(content),
                "elapsed_ms": round(elapsed, 1),
                "content_type": resp.headers.get("Content-Type", ""),
                "error": None
            }
    except urllib.error.HTTPError as e:
        elapsed = (time.time() - t0) * 1000
        return {
            "url": url,
            "status": e.code,
            "length": 0,
            "elapsed_ms": round(elapsed, 1),
            "content_type": e.headers.get("Content-Type", ""),
            "error": str(e)
        }
    except Exception as e:
        elapsed = (time.time() - t0) * 1000
        return {
            "url": url,
            "status": 0,
            "length": 0,
            "elapsed_ms": round(elapsed, 1),
            "content_type": "",
            "error": str(e)
        }

print("=== PROBING VERCEL DEPLOYMENT ===")
results = []
for path, meth in TEST_ROUTES:
    res = check_url(BASE_VERCEL, path, meth)
    status_str = f"HTTP {res['status']}" if res['status'] else "FAILED"
    err_str = f" | {res['error']}" if res['error'] else ""
    print(f"[{status_str:8s}] {path:35s} ({res['length']:6d} B, {res['elapsed_ms']:6.1f} ms){err_str}")
    results.append(res)

with open(r"C:\Users\toans\Desktop\Final Market Pulse\market-pulse\.agents\teamwork\teamwork_explorer_survey_1\survey_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("\nResults saved to survey_results.json")
