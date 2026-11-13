#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Empirical Adversarial Stress Harness for Market Pulse & Vercel.
Author: Challenger 1 (teamwork_challenger_1)
Mission: Stress-test ticker universe clickability, edge cases, invalid symbols, latency & concurrency.
"""
import concurrent.futures
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(ROOT, "data-crawler", "database", "market.db")
GATEWAY_URL = "http://127.0.0.1:9999"
VERCEL_URL = "https://vercel-full-deployment.vercel.app"

NON_DB_BOARD_TICKERS = ["DMX", "LPS", "KAI", "V68", "ULG", "PCB"]

def get_sample_tickers():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    c = conn.cursor()
    
    # 1. Large caps (by market cap DESC)
    c.execute("SELECT symbol FROM companies WHERE market_cap IS NOT NULL ORDER BY market_cap DESC LIMIT 10")
    large_caps = [r[0] for r in c.fetchall()]
    
    # 2. Illiquid / small caps (lowest positive market cap)
    c.execute("SELECT symbol FROM companies WHERE market_cap IS NOT NULL AND market_cap > 0 ORDER BY market_cap ASC LIMIT 10")
    small_caps = [r[0] for r in c.fetchall()]
    
    # 3. Banks / Financial institutions (group TCTC / sector Ngân hàng / Dịch vụ tài chính)
    c.execute("""SELECT symbol FROM companies 
                 WHERE sector LIKE '%Ngân hàng%' OR sector LIKE '%Tài chính%' OR sector LIKE '%Bảo hiểm%' 
                 ORDER BY market_cap DESC LIMIT 10""")
    banks = [r[0] for r in c.fetchall()]
    
    conn.close()
    return large_caps, small_caps, banks

def http_get(url, timeout=20):
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ChallengerStressTest/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            data = res.read()
            dur = time.time() - t0
            return res.status, dur, data, None
    except urllib.error.HTTPError as e:
        dur = time.time() - t0
        body = e.read()
        return e.code, dur, body, str(e)
    except Exception as e:
        dur = time.time() - t0
        return 0, dur, b"", str(e)

def run_clickability_audit():
    print("\n" + "="*75)
    print("PHASE 1: UNIVERSE CLICKABILITY & EDGE CASE TESTING")
    print("="*75)
    
    large_caps, small_caps, banks = get_sample_tickers()
    
    categories = [
        ("Large Caps (Top 10)", large_caps),
        ("Illiquid Small Caps (Bottom 10)", small_caps),
        ("Banks & Financials (TCTC)", banks),
        ("6 Non-DB Board Tickers", NON_DB_BOARD_TICKERS),
    ]
    
    results = {}
    
    for cat_name, tickers in categories:
        print(f"\n--- Testing Category: {cat_name} ({len(tickers)} tickers) ---")
        cat_results = []
        for sym in tickers:
            # Test local gateway
            url_local = f"{GATEWAY_URL}/api/stock/{sym}"
            status_l, dur_l, data_l, err_l = http_get(url_local)
            
            # Test Vercel cloud
            url_vercel = f"{VERCEL_URL}/api/stock/{sym}"
            status_v, dur_v, data_v, err_v = http_get(url_vercel)
            
            is_valid_json_l = False
            is_valid_json_v = False
            parsed_l = {}
            parsed_v = {}
            try:
                parsed_l = json.loads(data_l.decode("utf-8"))
                is_valid_json_l = True
            except Exception:
                pass
            try:
                parsed_v = json.loads(data_v.decode("utf-8"))
                is_valid_json_v = True
            except Exception:
                pass
            
            # Integrity checks
            pass_l = (status_l == 200 and is_valid_json_l and "error" not in parsed_l and parsed_l.get("info", {}).get("symbol") == sym.upper())
            pass_v = (status_v == 200 and is_valid_json_v and "error" not in parsed_v and parsed_v.get("info", {}).get("symbol") == sym.upper())
            
            extra_msg = ""
            if sym in NON_DB_BOARD_TICKERS:
                is_fb_l = parsed_l.get("meta", {}).get("is_live_fallback") is True
                is_fb_v = parsed_v.get("meta", {}).get("is_live_fallback") is True
                extra_msg = f" [Fallback flag: Local={is_fb_l}, Vercel={is_fb_v}]"
                pass_l = pass_l and is_fb_l
                pass_v = pass_v and is_fb_v
            
            status_str = "PASS" if (pass_l and pass_v) else "FAIL"
            print(f"Ticker: {sym:<6} | Local: {status_l} ({dur_l:.3f}s) | Vercel: {status_v} ({dur_v:.3f}s) | Verdict: {status_str}{extra_msg}")
            
            cat_results.append({
                "symbol": sym,
                "local_status": status_l, "local_latency": dur_l, "local_pass": pass_l,
                "vercel_status": status_v, "vercel_latency": dur_v, "vercel_pass": pass_v,
            })
            time.sleep(0.1)
        results[cat_name] = cat_results

    # Test non-DB secondary endpoints: /analysis and /charts
    print("\n--- Testing 6 Non-DB Board Tickers Secondary Endpoints (/analysis & /charts) ---")
    non_db_sub_results = []
    for sym in NON_DB_BOARD_TICKERS:
        for sub in ["analysis", "charts"]:
            u_l = f"{GATEWAY_URL}/api/stock/{sym}/{sub}"
            st_l, d_l, b_l, _ = http_get(u_l)
            u_v = f"{VERCEL_URL}/api/stock/{sym}/{sub}"
            st_v, d_v, b_v, _ = http_get(u_v)
            pass_ok = (st_l == 200 and st_v == 200)
            print(f"Ticker: {sym:<4}/{sub:<8} | Local: {st_l} ({d_l:.3f}s) | Vercel: {st_v} ({d_v:.3f}s) | {'PASS' if pass_ok else 'FAIL'}")
            non_db_sub_results.append({"sym": sym, "sub": sub, "local_st": st_l, "vercel_st": st_v, "pass": pass_ok})
            time.sleep(0.1)
    results["Non-DB Secondary Endpoints"] = non_db_sub_results

    # Test Invalid / Malicious Tickers
    print("\n--- Testing Invalid & Edge-Case Tickers (Crash Prevention / Clean 404/400) ---")
    invalid_cases = [
        ("INVALIDXYZ", "Regular non-existent uppercase symbol"),
        ("NONEXIST999", "Alphanumeric non-existent ticker"),
        ("fpt", "Lowercase valid symbol (should normalize or 200)"),
        ("vnm", "Lowercase valid symbol 2"),
        ("FPT%20", "Ticker with trailing urlencoded space"),
        ("FPT*", "Ticker with wildcard character"),
        ("..%2Fstock%2FFPT", "Path traversal probe"),
        ("SELECT*FROM", "SQL-like string probe"),
        ("<script>", "XSS angle brackets probe"),
    ]
    inv_results = []
    for raw_sym, desc in invalid_cases:
        u_l = f"{GATEWAY_URL}/api/stock/{raw_sym}"
        st_l, d_l, b_l, _ = http_get(u_l)
        u_v = f"{VERCEL_URL}/api/stock/{raw_sym}"
        st_v, d_v, b_v, _ = http_get(u_v)
        
        # Valid if: returns 200 (if normalized e.g. fpt -> FPT) OR clean error (404, 400), but NEVER 500 or 502
        safe_l = st_l in (200, 400, 404)
        safe_v = st_v in (200, 400, 404)
        verdict = "PASS (Clean/Handled)" if (safe_l and safe_v) else "FAIL (Server Crash/500/502)"
        print(f"Case: {raw_sym:<18} | Local: {st_l} ({d_l:.3f}s) | Vercel: {st_v} ({d_v:.3f}s) | {verdict} ({desc})")
        inv_results.append({"sym": raw_sym, "desc": desc, "st_l": st_l, "st_v": st_v, "safe": safe_l and safe_v})
        time.sleep(0.1)
    results["Invalid Cases"] = inv_results

    return results

def run_concurrent_worker(url, count):
    latencies = []
    statuses = []
    errors = []
    for _ in range(count):
        st, dur, data, err = http_get(url)
        latencies.append(dur)
        statuses.append(st)
        if err:
            errors.append(err)
        time.sleep(0.05)
    return latencies, statuses, errors

def benchmark_endpoint(target_name, base_url, endpoint_path, concurrency=5, requests_per_worker=4):
    full_url = f"{base_url}{endpoint_path}"
    total_requests = concurrency * requests_per_worker
    print(f"\nBenchmarking {target_name}: {endpoint_path} ({concurrency} workers x {requests_per_worker} reqs = {total_requests} total)...")
    
    t_start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(run_concurrent_worker, full_url, requests_per_worker) for _ in range(concurrency)]
        all_latencies = []
        all_statuses = []
        all_errors = []
        for f in concurrent.futures.as_completed(futures):
            lats, sts, errs = f.result()
            all_latencies.extend(lats)
            all_statuses.extend(sts)
            all_errors.extend(errs)
    tot_time = time.time() - t_start
    
    n_200 = sum(1 for s in all_statuses if s == 200)
    n_502_504 = sum(1 for s in all_statuses if s in (502, 504))
    n_other = total_requests - n_200
    
    all_latencies.sort()
    mean_lat = sum(all_latencies) / len(all_latencies) if all_latencies else 0
    p50_lat = all_latencies[int(len(all_latencies) * 0.50)] if all_latencies else 0
    p95_lat = all_latencies[min(int(len(all_latencies) * 0.95), len(all_latencies)-1)] if all_latencies else 0
    max_lat = max(all_latencies) if all_latencies else 0
    rps = total_requests / tot_time if tot_time > 0 else 0
    
    print(f"  Total Time: {tot_time:.2f}s | Throughput: {rps:.2f} req/s")
    print(f"  Statuses: 200 OK: {n_200}/{total_requests} ({(n_200/total_requests)*100:.1f}%) | 502/504 Timeouts: {n_502_504} | Other: {n_other}")
    print(f"  Latency: Mean={mean_lat:.3f}s | p50={p50_lat:.3f}s | p95={p95_lat:.3f}s | Max={max_lat:.3f}s")
    
    return {
        "target": target_name,
        "endpoint": endpoint_path,
        "total_requests": total_requests,
        "concurrency": concurrency,
        "n_200": n_200,
        "n_502_504": n_502_504,
        "mean_lat": mean_lat,
        "p50_lat": p50_lat,
        "p95_lat": p95_lat,
        "max_lat": max_lat,
        "rps": rps,
    }

def run_concurrency_stress():
    print("\n" + "="*75)
    print("PHASE 2: CONCURRENCY & LATENCY STRESS TESTING")
    print("="*75)
    
    test_endpoints = [
        "/api/market/board",
        "/api/stock/FPT",
        "/embed_banggia/",
        "/embed_econolens/",
    ]
    
    benchmarks = []
    
    # 1. Benchmark Local Gateway (concurrency=8, req_per_worker=5 -> 40 reqs per endpoint)
    print("\n--- PART 1: LOCAL GATEWAY CONCURRENCY BENCHMARK (http://127.0.0.1:9999) ---")
    for ep in test_endpoints:
        res = benchmark_endpoint("Local Gateway", GATEWAY_URL, ep, concurrency=8, requests_per_worker=5)
        benchmarks.append(res)
        time.sleep(0.5)

    # 2. Benchmark Vercel Cloud Deployment (concurrency=5, req_per_worker=4 -> 20 reqs per endpoint)
    print("\n--- PART 2: VERCEL PUBLIC URL CONCURRENCY BENCHMARK (https://vercel-full-deployment.vercel.app) ---")
    for ep in test_endpoints:
        res = benchmark_endpoint("Vercel Cloud", VERCEL_URL, ep, concurrency=5, requests_per_worker=4)
        benchmarks.append(res)
        time.sleep(0.5)

    return benchmarks

if __name__ == "__main__":
    t0_suite = time.time()
    click_results = run_clickability_audit()
    bench_results = run_concurrency_stress()
    dur_suite = time.time() - t0_suite
    
    # Summary Evaluation
    print("\n" + "="*75)
    print(f"ADVERSARIAL SUITE COMPLETED IN {dur_suite:.2f}s")
    print("="*75)
    
    # Check clickability failures
    fail_tickers = []
    for cat, items in click_results.items():
        if cat in ("Non-DB Secondary Endpoints", "Invalid Cases"):
            continue
        for it in items:
            if not (it["local_pass"] and it["vercel_pass"]):
                fail_tickers.append((cat, it["symbol"]))
                
    invalid_fails = [it["sym"] for it in click_results.get("Invalid Cases", []) if not it["safe"]]
    
    # Check 502/504 errors on Vercel
    vercel_502s = sum(b["n_502_504"] for b in bench_results if b["target"] == "Vercel Cloud")
    
    print(f"Clickability Failures: {len(fail_tickers)}")
    for c, s in fail_tickers:
        print(f"  - {c}: {s}")
    print(f"Invalid Symbol Crashes (500/502): {len(invalid_fails)}")
    for s in invalid_fails:
        print(f"  - {s}")
    print(f"Vercel 502/504 Timeouts under Concurrency: {vercel_502s}")
    
    verdict = "APPROVE" if (len(fail_tickers) == 0 and len(invalid_fails) == 0 and vercel_502s == 0) else "REQUEST_CHANGES"
    print(f"\n>>> FINAL VERDICT: {verdict} <<<")
    
    out_file = os.path.join(ROOT, ".agents", "teamwork", "teamwork_challenger_1", "raw_test_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"clickability": click_results, "benchmarks": bench_results, "verdict": verdict}, f, indent=2)
    print(f"Saved raw test results to: {out_file}")
