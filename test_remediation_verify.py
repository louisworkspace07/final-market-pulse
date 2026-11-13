import urllib.request
import urllib.error
import time
import json

endpoints = [
    ("Vercel Home", "https://vercel-full-deployment.vercel.app/"),
    ("Vercel Health", "https://vercel-full-deployment.vercel.app/api/health"),
    ("Vercel Board (Cached)", "https://vercel-full-deployment.vercel.app/api/market/board"),
    ("Vercel Stock FPT (DB)", "https://vercel-full-deployment.vercel.app/api/stock/FPT"),
    ("Vercel Stock DMX (Board Fallback)", "https://vercel-full-deployment.vercel.app/api/stock/DMX"),
    ("Vercel Stock LPS (Board Fallback)", "https://vercel-full-deployment.vercel.app/api/stock/LPS"),
    ("Price Board Embed HTML", "https://vercel-full-deployment.vercel.app/embed_banggia/"),
    ("Price Board CSS (Fixed relative)", "https://vercel-full-deployment.vercel.app/embed_banggia/style.css?v=8"),
    ("Price Board JS (Zero 127.0.0.1)", "https://vercel-full-deployment.vercel.app/embed_banggia/app.js?v=19"),
    ("Price Board API Stocks", "https://vercel-full-deployment.vercel.app/embed_banggia/api/stocks"),
    ("Price Board Real VBP FPT", "https://vercel-full-deployment.vercel.app/embed_banggia/api/vbp/FPT"),
    ("Price Board Clean Empty VBP", "https://vercel-full-deployment.vercel.app/embed_banggia/api/vbp/XYZ123"),
    ("EconoLens Embed HTML", "https://vercel-full-deployment.vercel.app/embed_econolens/"),
    ("EconoLens API Meta (Proxy)", "https://vercel-full-deployment.vercel.app/embed_econolens/api/meta"),
    ("Data Crawler UI", "https://vercel-full-deployment.vercel.app/embed_crawl/app/"),
    ("Data Crawler Group Members (VN30)", "https://vercel-full-deployment.vercel.app/embed_crawl/api/group_members?group=VN30"),
]

print("{:<36} | {:<6} | {:<9} | {:<10}".format("Endpoint", "Status", "Latency", "Size"))
print("-" * 70)

for name, url in endpoints:
    time.sleep(0.35)
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MarketPulseAudit/1.0"})
        res = urllib.request.urlopen(req, timeout=25)
        content = res.read()
        dur = time.time() - t0
        print("{:<36} | {:<6} | {:<8.3f}s | {:<10}".format(name, res.status, dur, len(content)))
    except urllib.error.HTTPError as e:
        dur = time.time() - t0
        body = e.read()
        status_desc = f"{e.code} (Auth Expected)" if e.code == 401 else f"{e.code} (HTTP Error)"
        print("{:<36} | {:<6} | {:<8.3f}s | {:<10} {}".format(name, e.code, dur, len(body), status_desc))
    except Exception as e:
        dur = time.time() - t0
        print("{:<36} | {:<6} | {:<8.3f}s | {:<10}".format(name, "ERR", dur, str(e)[:25]))
