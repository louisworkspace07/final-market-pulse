import os
import sys
import sqlite3
import numpy as np
import pandas as pd
import threading
import time

ROOT = r"c:\Users\MSI\Desktop\Final Market Pulse"
sys.path.insert(0, os.path.join(ROOT, "price-board"))
sys.path.insert(0, os.path.join(ROOT, "data-crawler"))
sys.path.insert(0, os.path.join(ROOT, "market-pulse"))

import board_vnstock
import app as crawler_app
from modules.market_overview import tech_full

DB_PATH = os.path.join(ROOT, "data-crawler", "database", "market.db")

print("=== CHECK 1: BOARD_VNSTOCK ARITHMETIC & DATA INTEGRITY ===")
# Generate adversarial synthetic dataframe with known values
test_data = {
    "symbol": ["AAA", "BBB", "CCC"],
    "ref_price": [10000.0, 20000.0, 50000.0],
    "ceiling": [10700.0, 21400.0, 53500.0],
    "floor": [9300.0, 18600.0, 46500.0],
    "match_price": [10500.0, 19500.0, 50000.0],
    "match_vol": [1234.0, 5678.0, 9999.0],
    "accumulated_volume": [100000.0, 200000.0, 500000.0],
    "avg_match_price": [10400.0, 19600.0, 50100.0],
    "highest": [10600.0, 20100.0, 51000.0],
    "lowest": [9900.0, 19400.0, 49800.0],
    "foreign_buy_volume": [111.0, 222.0, 333.0],
    "foreign_sell_volume": [444.0, 555.0, 666.0],
    "bid_1_price": [10450.0, 19450.0, 49950.0],
    "bid_1_volume": [100.0, 200.0, 300.0],
    "bid_2_price": [10400.0, 19400.0, 49900.0],
    "bid_2_volume": [400.0, 500.0, 600.0],
    "bid_3_price": [10350.0, 19350.0, 49850.0],
    "bid_3_volume": [700.0, 800.0, 900.0],
    "ask_1_price": [10550.0, 19550.0, 50050.0],
    "ask_1_volume": [150.0, 250.0, 350.0],
    "ask_2_price": [10600.0, 19600.0, 50100.0],
    "ask_2_volume": [450.0, 550.0, 650.0],
    "ask_3_price": [10650.0, 19650.0, 50150.0],
    "ask_3_volume": [750.0, 850.0, 950.0],
}
df_test = pd.DataFrame(test_data)
ex_map = {"AAA": "HOSE", "BBB": "HNX", "CCC": "UPCOM"}

rows = board_vnstock.parse_board_df(df_test, ex_map)
assert len(rows) == 3, f"Expected 3 rows, got {len(rows)}"

# Verify row 0 (AAA)
r0 = rows[0]
assert r0["symbol"] == "AAA"
assert r0["exchange"] == "HOSE"
assert r0["ref"] == 10000.0
assert r0["matchPrice"] == 10500.0
assert r0["foreignBuy"] == 111.0
assert r0["foreignSell"] == 444.0
# du_mua = 100 + 400 + 700 = 1200
# du_ban = 150 + 450 + 750 = 1350
assert r0["buyV1"] == 100.0 and r0["buyV2"] == 400.0 and r0["buyV3"] == 700.0
assert r0["sellV1"] == 150.0 and r0["sellV2"] == 450.0 and r0["sellV3"] == 750.0
# Check raw elements
raw0 = r0["raw"]
assert len(raw0) == 27
assert raw0[0] == "AAA"
assert raw0[1] == "10.00"   # 10000 / 1000
assert raw0[11] == "10.50"  # 10500 / 1000
assert raw0[13] == "+0.50"  # (10500 - 10000) / 1000
assert raw0[23] == "1,200"  # du_mua
assert raw0[24] == "1,350"  # du_ban
assert raw0[25] == "111"    # foreign buy
assert raw0[26] == "444"    # foreign sell
print("Row 0 arithmetic and formatting verified: PASS")

# Verify row 1 (BBB)
r1 = rows[1]
assert r1["symbol"] == "BBB"
assert r1["matchPrice"] == 19500.0
assert r1["ref"] == 20000.0
raw1 = r1["raw"]
assert raw1[13] == "-0.50"  # (19500 - 20000) / 1000
# du_mua = 200 + 500 + 800 = 1500
# du_ban = 250 + 550 + 850 = 1650
assert raw1[23] == "1,500"
assert raw1[24] == "1,650"
print("Row 1 arithmetic and formatting verified: PASS")

# Verify dynamic update: when prices change, cache does not return stale value for symbol
df_updated = df_test.copy()
df_updated.loc[0, "match_price"] = 10600.0
rows_updated = board_vnstock.parse_board_df(df_updated, ex_map)
assert rows_updated[0]["matchPrice"] == 10600.0
assert rows_updated[0]["raw"][11] == "10.60"
assert rows_updated[0]["raw"][13] == "+0.60"
print("Dynamic update with changed price: PASS")


print("\n=== CHECK 2: DATA-CRAWLER /STATS & /HEALTH DB INTEGRITY ===")
# Connect directly to market.db and query ground truth counts
conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
q = lambda s: conn.execute(s).fetchone()[0]
real_companies = q("SELECT COUNT(*) FROM companies")
real_fin_symbols = q("SELECT COUNT(DISTINCT symbol) FROM financials")
real_news = q("SELECT COUNT(*) FROM news")
real_analyzed = q("SELECT COUNT(*) FROM ai_analysis")
real_fin_done = q("SELECT COUNT(*) FROM crawl_state WHERE stage='financials' AND status='ok'")
real_co_done = q("SELECT COUNT(*) FROM crawl_state WHERE stage='company' AND status='ok'")
real_price_time = q("SELECT MAX(time) FROM price")
real_analyzed_time = q("SELECT MAX(updated_at) FROM ai_analysis")
real_crawl_time = q("SELECT MAX(updated_at) FROM crawl_state")
conn.close()

# Invalidate crawler app cache
crawler_app._METRICS_CACHE["ts"] = 0.0
crawler_app._METRICS_CACHE["stats"] = None
crawler_app._METRICS_CACHE["db"] = None
crawler_app._METRICS_CACHE["fresh"] = None

stats_data, db_data, fresh_data = crawler_app._get_db_metrics(force=True)

assert stats_data["companies"] == real_companies, f"companies mismatch: {stats_data['companies']} vs {real_companies}"
assert stats_data["fin_symbols"] == real_fin_symbols, f"fin_symbols mismatch: {stats_data['fin_symbols']} vs {real_fin_symbols}"
assert stats_data["news"] == real_news, f"news mismatch: {stats_data['news']} vs {real_news}"
assert stats_data["analyzed"] == real_analyzed, f"analyzed mismatch: {stats_data['analyzed']} vs {real_analyzed}"
assert stats_data["fin_done"] == real_fin_done, f"fin_done mismatch: {stats_data['fin_done']} vs {real_fin_done}"
assert stats_data["co_done"] == real_co_done, f"co_done mismatch: {stats_data['co_done']} vs {real_co_done}"

assert fresh_data["price"] == real_price_time, f"price time mismatch: {fresh_data['price']} vs {real_price_time}"
assert fresh_data["analyzed"] == real_analyzed_time, f"analyzed time mismatch: {fresh_data['analyzed']} vs {real_analyzed_time}"
assert fresh_data["crawl"] == real_crawl_time, f"crawl time mismatch: {fresh_data['crawl']} vs {real_crawl_time}"
print(f"Crawler DB metrics match ground-truth SQLite database 100%: PASS (companies={real_companies}, news={real_news})")

# Test /health background probe thread
crawler_app._HEALTH_PROBE_CACHE["ts"] = 0.0
probe_before = crawler_app._get_health_probes()
time.sleep(0.5) # allow background thread to complete
probe_after = crawler_app._HEALTH_PROBE_CACHE
assert "backend" in probe_after and "local_api" in probe_after
print("Crawler health background probe verified: PASS")


print("\n=== CHECK 3: TECH_FULL MATHEMATICAL INTEGRITY ===")
# Invalidate tech_full cache
tech_full._cache["data"] = None
tech_full._cache["ts"] = 0.0

res_fpt = tech_full.one(DB_PATH, "FPT")
assert res_fpt is not None
assert res_fpt["symbol"] == "FPT"
assert res_fpt["bars"] == 260

# Compare with ground-truth manual calculation on the exact same 260 bars from SQLite
conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
cur = conn.execute(
    "SELECT high, low, close, volume FROM price WHERE symbol = 'FPT' AND close IS NOT NULL ORDER BY time DESC LIMIT 260"
)
raw_rows = cur.fetchall()
conn.close()
raw_rows.reverse()

c = np.array([r[2] for r in raw_rows], dtype=float)
h = np.array([r[0] for r in raw_rows], dtype=float)
l = np.array([r[1] for r in raw_rows], dtype=float)
v = np.array([r[3] for r in raw_rows], dtype=float)

expected_last = float(c[-1])
expected_ma20 = float(c[-20:].mean())
expected_ma50 = float(c[-50:].mean())
expected_hi52 = float(h.max())
expected_lo52 = float(l.min())

assert abs(res_fpt["price"] - expected_last) < 1e-4, f"Price mismatch: {res_fpt['price']} vs {expected_last}"
assert abs(res_fpt["ma20"] - round(expected_ma20, 2)) < 1e-2, f"MA20 mismatch: {res_fpt['ma20']} vs {expected_ma20}"
assert abs(res_fpt["ma50"] - round(expected_ma50, 2)) < 1e-2, f"MA50 mismatch: {res_fpt['ma50']} vs {expected_ma50}"
assert abs(res_fpt["hi52"] - expected_hi52) < 1e-4, f"Hi52 mismatch: {res_fpt['hi52']} vs {expected_hi52}"
assert abs(res_fpt["lo52"] - expected_lo52) < 1e-4, f"Lo52 mismatch: {res_fpt['lo52']} vs {expected_lo52}"
print(f"Tech indicators for FPT match mathematical ground truth (price={expected_last}, ma20={res_fpt['ma20']}, hi52={expected_hi52}): PASS")

print("\nALL INTEGRITY FORENSIC CHECKS PASSED EMPIRICALLY!")
