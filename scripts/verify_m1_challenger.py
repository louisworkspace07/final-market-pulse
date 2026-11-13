#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Milestone 1 Empirical Challenger Benchmark & Verification Suite.

Adversarial stress-testing and empirical verification for:
1. `price-board/board_vnstock.py` realtime loop execution time (< 5ms for 726 rows).
2. `market-pulse/modules/market_overview/tech_full.py:one()` latency (< 50ms per symbol).
3. `tech_full.py:one()` edge cases ('NONEXISTENT', < 60 bars, invalid symbols, corrupt data).
4. `data-crawler/app.py` /stats and /health caching (< 2ms cache hit, stale-while-revalidate, concurrency).
"""
from __future__ import annotations

import gc
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "price-board"))
sys.path.insert(0, os.path.join(ROOT, "market-pulse"))
sys.path.insert(0, os.path.join(ROOT, "data-crawler"))

DB_PATH = os.path.join(ROOT, "data-crawler", "database", "market.db")

RESULTS = {
    "test_board_vnstock": {},
    "test_tech_full_latency": {},
    "test_tech_full_edge_cases": {},
    "test_crawler_caching": {},
}


# ============================================================================
# 1. price-board/board_vnstock.py Loop Verification
# ============================================================================
def verify_board_vnstock_loop():
    print("\n=======================================================")
    print("TEST 1: price-board/board_vnstock.py Loop Benchmark")
    print("=======================================================")
    import board_vnstock

    n_rows = 726
    fields = [
        "symbol", "ref_price", "ceiling", "floor", "match_price",
        "match_vol", "accumulated_volume", "avg_match_price",
        "highest", "lowest", "foreign_buy_volume", "foreign_sell_volume",
        "bid_1_price", "bid_1_volume", "bid_2_price", "bid_2_volume",
        "bid_3_price", "bid_3_volume", "ask_1_price", "ask_1_volume",
        "ask_2_price", "ask_2_volume", "ask_3_price", "ask_3_volume",
    ]

    # Create realistic test dataframe
    data = {
        "symbol": [f"SYM{i:04d}" for i in range(n_rows)],
        "ref_price": [50.0 + (i % 50) for i in range(n_rows)],
        "ceiling": [53.5 + (i % 50) for i in range(n_rows)],
        "floor": [46.5 + (i % 50) for i in range(n_rows)],
        "match_price": [51.2 + (i % 50) for i in range(n_rows)],
        "match_vol": [15000 + i * 10 for i in range(n_rows)],
        "accumulated_volume": [500000 + i * 100 for i in range(n_rows)],
        "avg_match_price": [50.8 + (i % 50) for i in range(n_rows)],
        "highest": [52.0 + (i % 50) for i in range(n_rows)],
        "lowest": [49.5 + (i % 50) for i in range(n_rows)],
        "foreign_buy_volume": [20000 for _ in range(n_rows)],
        "foreign_sell_volume": [15000 for _ in range(n_rows)],
        "bid_1_price": [51.0 for _ in range(n_rows)],
        "bid_1_volume": [5000 for _ in range(n_rows)],
        "bid_2_price": [50.8 for _ in range(n_rows)],
        "bid_2_volume": [6000 for _ in range(n_rows)],
        "bid_3_price": [50.5 for _ in range(n_rows)],
        "bid_3_volume": [7000 for _ in range(n_rows)],
        "ask_1_price": [51.3 for _ in range(n_rows)],
        "ask_1_volume": [5500 for _ in range(n_rows)],
        "ask_2_price": [51.5 for _ in range(n_rows)],
        "ask_2_volume": [6500 for _ in range(n_rows)],
        "ask_3_price": [51.8 for _ in range(n_rows)],
        "ask_3_volume": [7500 for _ in range(n_rows)],
    }
    df = pd.DataFrame(data)
    ex_map = {f"SYM{i:04d}": "HOSE" for i in range(n_rows)}

    # Function executing board_vnstock.parse_board_df
    def run_full_board_loop(df_in):
        return board_vnstock.parse_board_df(df_in, ex_map)

    # Warmup
    for _ in range(15):
        run_full_board_loop(df)
    gc.collect()

    # Benchmark 100 runs
    times = []
    for _ in range(100):
        t0 = time.perf_counter()
        out = run_full_board_loop(df)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000.0)

    assert len(out) == n_rows, f"Expected {n_rows} rows, got {len(out)}"
    assert len(out[0]["raw"]) == 27, f"Expected 27 raw elements, got {len(out[0]['raw'])}"

    mean_t = np.mean(times)
    median_t = np.median(times)
    p95_t = np.percentile(times, 95)
    min_t = np.min(times)
    max_t = np.max(times)

    print(f"Total iterations: 100")
    print(f"Rows processed per iteration: {n_rows}")
    print(f"Execution time (mean):   {mean_t:.3f} ms")
    print(f"Execution time (median): {median_t:.3f} ms")
    print(f"Execution time (p95):    {p95_t:.3f} ms")
    print(f"Execution time (min):    {min_t:.3f} ms")
    print(f"Execution time (max):    {max_t:.3f} ms")

    # Edge cases for board loop
    # Edge case 1: DataFrame with missing columns
    df_missing = df.drop(columns=["bid_3_price", "ask_3_volume", "foreign_buy_volume"])
    out_missing = run_full_board_loop(df_missing)
    assert len(out_missing) == n_rows
    print("Edge case: Missing columns handled gracefully: PASS")

    # Edge case 2: Empty DataFrame
    df_empty = pd.DataFrame({f: [] for f in fields})
    out_empty = run_full_board_loop(df_empty)
    assert len(out_empty) == 0
    print("Edge case: Empty DataFrame (0 rows) handled gracefully: PASS")

    # Edge case 3: DataFrame with None / NaN values
    df_nans = df.copy()
    df_nans.loc[0, "match_price"] = None
    df_nans.loc[1, "ref_price"] = None
    df_nans.loc[2, "symbol"] = None
    out_nans = run_full_board_loop(df_nans)
    assert len(out_nans) == n_rows - 1  # 1 symbol was None, so skipped
    print("Edge case: NaN / None values handled gracefully: PASS")

    passed = mean_t < 5.0 and p95_t < 5.0
    print(f"VERDICT for board_vnstock loop (< 5ms): {'PASS' if passed else 'FAIL'}")
    RESULTS["test_board_vnstock"] = {
        "passed": passed,
        "n_rows": n_rows,
        "mean_ms": round(mean_t, 3),
        "median_ms": round(median_t, 3),
        "p95_ms": round(p95_t, 3),
        "min_ms": round(min_t, 3),
        "max_ms": round(max_t, 3),
    }


# ============================================================================
# 2. tech_full.py:one() Latency Benchmark
# ============================================================================
def verify_tech_full_latency():
    print("\n=======================================================")
    print("TEST 2: tech_full.py:one() Latency Benchmark")
    print("=======================================================")
    from modules.market_overview import tech_full

    symbols = ["FPT", "HPG", "VNM", "VIC", "SSI"]
    sym_results = {}

    expected_fields = [
        "symbol", "price", "bars", "sr", "vbp", "rsi14",
        "ma20", "ma50", "above_ma20", "vol_vs_20", "hi52", "lo52",
        "pct_from_hi52", "pct_from_lo52", "pos"
    ]

    all_passed = True

    for sym in symbols:
        times = []
        # Test 20 cold queries (clearing cache before each run to guarantee SQL query executes)
        for _ in range(20):
            tech_full._cache["data"] = None
            tech_full._cache["ts"] = 0.0

            t0 = time.perf_counter()
            res = tech_full.one(DB_PATH, sym)
            t1 = time.perf_counter()
            times.append((t1 - t0) * 1000.0)

        # Verify output contract
        assert res is not None, f"Symbol {sym} returned None"
        assert "skipped" not in res, f"Symbol {sym} was skipped: {res.get('skipped')}"
        for field in expected_fields:
            assert field in res, f"Missing field '{field}' in result for {sym}"

        assert res["symbol"] == sym, f"Expected symbol {sym}, got {res['symbol']}"
        assert res["bars"] >= 60, f"Expected >= 60 bars for {sym}, got {res['bars']}"
        assert 0 <= res["rsi14"] <= 100, f"RSI out of bounds: {res['rsi14']}"
        assert res["hi52"] >= res["lo52"], f"hi52 ({res['hi52']}) < lo52 ({res['lo52']})"
        assert isinstance(res["sr"], dict) and "support" in res["sr"] and "resistance" in res["sr"]

        mean_t = np.mean(times)
        median_t = np.median(times)
        p95_t = np.percentile(times, 95)
        min_t = np.min(times)
        max_t = np.max(times)

        sym_passed = p95_t < 50.0
        if not sym_passed:
            all_passed = False

        sym_results[sym] = {
            "passed": sym_passed,
            "bars": res["bars"],
            "price": res["price"],
            "rsi14": res["rsi14"],
            "mean_ms": round(mean_t, 2),
            "median_ms": round(median_t, 2),
            "p95_ms": round(p95_t, 2),
            "min_ms": round(min_t, 2),
            "max_ms": round(max_t, 2),
        }
        print(f"Symbol {sym:<5} (bars={res['bars']}): mean={mean_t:.2f}ms, p95={p95_t:.2f}ms, max={max_t:.2f}ms -> {'PASS' if sym_passed else 'FAIL'}")

    # Also test warm cache latency
    tech_full.build(DB_PATH)  # warm cache
    warm_times = []
    for _ in range(50):
        t0 = time.perf_counter()
        r = tech_full.one(DB_PATH, "FPT")
        warm_times.append((time.perf_counter() - t0) * 1000.0)
    warm_mean = np.mean(warm_times)
    print(f"Warm cache hit latency: mean={warm_mean:.4f}ms, p95={np.percentile(warm_times, 95):.4f}ms")

    print(f"VERDICT for tech_full.py:one() latency (< 50ms): {'PASS' if all_passed else 'FAIL'}")
    RESULTS["test_tech_full_latency"] = {
        "passed": all_passed,
        "symbols": sym_results,
        "warm_mean_ms": round(warm_mean, 4),
    }


# ============================================================================
# 3. tech_full.py:one() Edge Cases
# ============================================================================
def verify_tech_full_edge_cases():
    print("\n=======================================================")
    print("TEST 3: tech_full.py:one() Edge Cases & Fault Injection")
    print("=======================================================")
    from modules.market_overview import tech_full

    tech_full._cache["data"] = None
    tech_full._cache["ts"] = 0.0

    edge_results = {}

    # Case 3.1: Non-existent symbol
    res_nonexistent = tech_full.one(DB_PATH, "NONEXISTENT")
    assert res_nonexistent is None, f"Expected None for NONEXISTENT, got {res_nonexistent}"
    edge_results["nonexistent_symbol"] = "PASS (returns None)"
    print("3.1 Non-existent symbol 'NONEXISTENT': PASS (returns None)")

    # Case 3.2: Special characters / SQL injection attempt
    res_sqli = tech_full.one(DB_PATH, "FPT'; DROP TABLE price; --")
    assert res_sqli is None, f"Expected None for SQL injection string, got {res_sqli}"
    # Verify price table still exists!
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    count = conn.execute("SELECT count(*) FROM price").fetchone()[0]
    conn.close()
    assert count > 0, "Price table was altered!"
    edge_results["sql_injection_safety"] = "PASS (returns None, table safe)"
    print("3.2 SQL injection string 'FPT\'; DROP TABLE price; --': PASS (safe, returns None)")

    # Case 3.3: Empty and whitespace strings
    res_empty = tech_full.one(DB_PATH, "")
    assert res_empty is None, f"Expected None for empty string, got {res_empty}"
    res_spaces = tech_full.one(DB_PATH, "   ")
    assert res_spaces is None, f"Expected None for spaces, got {res_spaces}"
    edge_results["empty_and_spaces"] = "PASS (returns None)"
    print("3.3 Empty and spaces strings: PASS (returns None)")

    # Case 3.4: Lowercase and padded symbol
    res_padded = tech_full.one(DB_PATH, "  fpt  ")
    assert res_padded is not None and res_padded["symbol"] == "FPT"
    edge_results["lowercase_and_padded"] = "PASS (normalized to FPT)"
    print("3.4 Padded lowercase '  fpt  ': PASS (normalized to FPT)")

    # Case 3.5: Real database symbols with < 60 bars
    # Symbols identified earlier: TAH (2 bars), ANI (19 bars), NHD (26 bars), FUEMITEC (39 bars), CLI (48 bars)
    under_60_symbols = ["TAH", "ANI", "NHD", "FUEMITEC", "CLI"]
    for sym in under_60_symbols:
        tech_full._cache["data"] = None
        res_under = tech_full.one(DB_PATH, sym)
        assert res_under is not None, f"Expected dict for {sym}, got None"
        assert res_under["symbol"] == sym, f"Expected symbol {sym}, got {res_under.get('symbol')}"
        assert "skipped" in res_under, f"Expected 'skipped' key in {res_under}"
        assert "phiên < 60" in res_under["skipped"], f"Unexpected skipped reason: {res_under['skipped']}"
        print(f"3.5 Real DB symbol < 60 bars '{sym}': PASS (skipped: '{res_under['skipped']}')")
    edge_results["real_symbols_under_60_bars"] = "PASS (all returned skipped dict without crashing)"

    # Case 3.6: Synthetic DB with corrupt / edge-case data
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        tmp_db_path = tmp_db.name

    try:
        tmp_conn = sqlite3.connect(tmp_db_path)
        tmp_conn.execute("""
            CREATE TABLE price (
                symbol TEXT,
                time TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                PRIMARY KEY (symbol, time)
            )
        """)
        tmp_conn.execute("CREATE INDEX idx_price_key ON price(symbol, time)")

        # Populate synthetic test cases:
        # A: Exactly 59 bars (boundary below 60)
        for i in range(59):
            tmp_conn.execute("INSERT INTO price VALUES (?, ?, ?, ?, ?, ?, ?)",
                             ("B59", f"2026-01-{i+1:02d}", 10, 11, 9, 10, 1000))
        # B: Exactly 60 bars (boundary threshold)
        for i in range(60):
            tmp_conn.execute("INSERT INTO price VALUES (?, ?, ?, ?, ?, ?, ?)",
                             ("B60", f"2026-01-{i+1:02d}", 10, 11, 9, 10, 1000))
        # C: 70 bars with high/low = NULL (corrupt prices)
        for i in range(70):
            tmp_conn.execute("INSERT INTO price VALUES (?, ?, ?, ?, ?, ?, ?)",
                             ("BNULL", f"2026-01-{i+1:02d}", 10, None, None, 10, 1000))
        # D: 70 bars with volume = 0
        for i in range(70):
            tmp_conn.execute("INSERT INTO price VALUES (?, ?, ?, ?, ?, ?, ?)",
                             ("BZERVOL", f"2026-01-{i+1:02d}", 10, 12, 8, 10, 0))
        tmp_conn.commit()
        tmp_conn.close()

        # Test boundary 59 bars
        res_59 = tech_full.one(tmp_db_path, "B59")
        assert "skipped" in res_59 and "59 phiên < 60" in res_59["skipped"]
        print("3.6a Boundary 59 bars: PASS (skipped correctly)")

        # Test boundary 60 bars
        res_60 = tech_full.one(tmp_db_path, "B60")
        assert "skipped" not in res_60 and res_60["bars"] == 60
        print("3.6b Boundary 60 bars: PASS (computed successfully)")

        # Test NULL high/low
        res_null = tech_full.one(tmp_db_path, "BNULL")
        assert "skipped" in res_null and "thiếu giá cao/thấp" in res_null["skipped"]
        print("3.6c NULL high/low values: PASS (skipped correctly)")

        # Test Zero volume
        res_zvol = tech_full.one(tmp_db_path, "BZERVOL")
        assert "skipped" not in res_zvol and res_zvol["bars"] == 70
        print("3.6d Zero volume: PASS (computed without ZeroDivisionError)")

    finally:
        if os.path.exists(tmp_db_path):
            os.remove(tmp_db_path)

    print("VERDICT for tech_full.py:one() edge cases: PASS")
    RESULTS["test_tech_full_edge_cases"] = edge_results


# ============================================================================
# 4. data-crawler /stats and /health Caching & Stale-While-Revalidate
# ============================================================================
def verify_crawler_caching():
    print("\n=======================================================")
    print("TEST 4: data-crawler /stats & /health Caching & Resilience")
    print("=======================================================")
    import app as crawler_app

    client = crawler_app.app.test_client()

    # 4.1 Benchmark /stats cache hit latency
    # Initial call to populate cache
    r_init = client.get("/stats")
    assert r_init.status_code == 200
    init_data = json.loads(r_init.data)
    print(f"Populated /stats cache: {init_data}")

    stats_latencies = []
    for _ in range(100):
        t0 = time.perf_counter()
        r = client.get("/stats")
        t1 = time.perf_counter()
        assert r.status_code == 200
        stats_latencies.append((t1 - t0) * 1000.0)

    stats_mean = np.mean(stats_latencies)
    stats_p95 = np.percentile(stats_latencies, 95)
    stats_p99 = np.percentile(stats_latencies, 99)
    stats_min = np.min(stats_latencies)
    stats_max = np.max(stats_latencies)

    print(f"/stats cache hit latency (100 requests):")
    print(f"  mean: {stats_mean:.3f} ms (Target < 2.0 ms)")
    print(f"  median: {np.median(stats_latencies):.3f} ms")
    print(f"  p95:  {stats_p95:.3f} ms")
    print(f"  p99:  {stats_p99:.3f} ms")
    print(f"  min:  {stats_min:.3f} ms, max: {stats_max:.3f} ms")

    passed_stats_latency = stats_mean < 2.0 and stats_p95 < 2.0
    print(f"VERDICT for /stats cache latency (< 2ms): {'PASS' if passed_stats_latency else 'FAIL'}")

    # 4.2 Benchmark /health cache hit latency
    client.get("/health")  # Warmup
    health_latencies = []
    for _ in range(20):
        t0 = time.perf_counter()
        r = client.get("/health")
        t1 = time.perf_counter()
        assert r.status_code == 200
        health_latencies.append((t1 - t0) * 1000.0)

    health_mean = np.mean(health_latencies)
    health_p95 = np.percentile(health_latencies, 95)
    print(f"/health response latency (20 requests): mean={health_mean:.3f} ms, p95={health_p95:.3f} ms (Target < 2.0 ms)")
    passed_health_latency = health_mean < 2.0 and health_p95 < 2.0
    print(f"VERDICT for /health cache latency (< 2ms): {'PASS' if passed_health_latency else 'FAIL'}")

    # 4.3 Concurrency stress test (20 threads calling simultaneously)
    def call_stats_worker(worker_id):
        worker_client = crawler_app.app.test_client()
        for _ in range(10):
            res = worker_client.get("/stats")
            if res.status_code != 200:
                return False
        return True

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(call_stats_worker, i) for i in range(20)]
        concurrency_results = [f.result() for f in futures]

    assert all(concurrency_results), "Concurrency test failed with errors!"
    print(f"Concurrency test: 20 threads, 200 total requests -> ALL 200 OK (PASS)")

    # 4.4 Stale-While-Revalidate verification under simulated database lock
    print("\nSimulating SQLite locked error with expired cache (Stale-While-Revalidate)...")
    with crawler_app._METRICS_LOCK:
        # Save valid cached data
        cached_stats_before = dict(crawler_app._METRICS_CACHE["stats"])
        # Force cache to be stale (expired 100 seconds ago)
        crawler_app._METRICS_CACHE["ts"] = time.time() - 100.0

    # Mock sqlite3.connect to simulate database locked exception
    def mock_sqlite3_connect(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked (simulated lock collision)")

    with patch("sqlite3.connect", side_effect=mock_sqlite3_connect):
        # Call /stats while database is locked and cache is expired
        r_stale_stats = client.get("/stats")
        assert r_stale_stats.status_code == 200, f"Expected 200, got {r_stale_stats.status_code}"
        stale_data = json.loads(r_stale_stats.data)
        assert stale_data == cached_stats_before, f"Expected {cached_stats_before}, got {stale_data}"

        # Call /health while database is locked and cache is expired
        r_stale_health = client.get("/health")
        assert r_stale_health.status_code == 200, f"Expected 200, got {r_stale_health.status_code}"
        health_data = json.loads(r_stale_health.data)
        assert health_data.get("db") == crawler_app._METRICS_CACHE["db"], "Stale db data missing in health"
        assert health_data.get("fresh") == crawler_app._METRICS_CACHE["fresh"], "Stale fresh data missing in health"

    print("Stale-While-Revalidate under database lock: PASS (served stale cache gracefully, 0 errors, 200 OK)")

    RESULTS["test_crawler_caching"] = {
        "stats_mean_ms": round(stats_mean, 3),
        "stats_p95_ms": round(stats_p95, 3),
        "stats_p99_ms": round(stats_p99, 3),
        "health_mean_ms": round(health_mean, 3),
        "health_p95_ms": round(health_p95, 3),
        "passed_stats_latency": bool(passed_stats_latency),
        "passed_health_latency": bool(passed_health_latency),
        "concurrency_pass": True,
        "stale_while_revalidate_pass": True,
    }


def _json_default(obj):
    if hasattr(obj, "item"):
        return obj.item()
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    return str(obj)


if __name__ == "__main__":
    t_start = time.time()
    verify_board_vnstock_loop()
    verify_tech_full_latency()
    verify_tech_full_edge_cases()
    verify_crawler_caching()
    total_duration = time.time() - t_start

    print("\n=======================================================")
    print(f"ALL CHALLENGER TESTS COMPLETED in {total_duration:.2f}s")
    print("=======================================================")
    print(json.dumps(RESULTS, indent=2, default=_json_default))

