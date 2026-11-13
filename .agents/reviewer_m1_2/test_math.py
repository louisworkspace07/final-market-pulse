import sys, sqlite3
import numpy as np
sys.path.insert(0, "market-pulse")
from modules.market_overview import tech_full

db = "data-crawler/database/market.db"

# Query VNM directly via sqlite
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
rows = con.execute("SELECT high, low, close, volume FROM price WHERE symbol='VNM' AND close IS NOT NULL ORDER BY time DESC LIMIT 260").fetchall()
con.close()
rows.reverse()
closes = [r[2] for r in rows]

# Manual MA20 calculation
expected_ma20 = round(float(np.mean(closes[-20:])), 2)
expected_close = round(float(closes[-1]), 2)

res = tech_full.one(db, "VNM")
print("VNM close:", res["price"], "expected:", expected_close)
print("VNM ma20:", res["ma20"], "expected:", expected_ma20)

assert res["price"] == expected_close
assert res["ma20"] == expected_ma20
print("Math verification passed: Real calculations confirmed!")
