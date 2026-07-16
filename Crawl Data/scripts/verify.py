import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config  # bật UTF-8

c = sqlite3.connect(str(config.DB_PATH))
print("Companies:", c.execute("SELECT COUNT(*) FROM companies").fetchone()[0])
print("Financial rows:", c.execute("SELECT COUNT(*) FROM financials").fetchone()[0])

print("\nVNM dòng tiền - LN trước thuế (mới->cũ):")
q = ("SELECT period, value FROM financials WHERE symbol='VNM' "
     "AND statement='cash_flow' AND item_id='net_profit_loss_before_tax' "
     "ORDER BY period DESC")
for period, value in c.execute(q):
    print(f"  {period}: {value:,.0f}")

print("\nSố item theo statement (VNM):")
q2 = ("SELECT statement, COUNT(DISTINCT item_id) FROM financials "
      "WHERE symbol='VNM' GROUP BY statement")
for s, n in c.execute(q2):
    print(f"  {s}: {n} chỉ tiêu")

print("\nCây thư mục companies/VNM:")
vnm_dir = config.COMPANIES_DIR / "VNM"
for p in sorted(vnm_dir.rglob("*")):
    if p.is_file():
        print("  ", p.relative_to(config.COMPANIES_DIR))
c.close()
