# -*- coding: utf-8 -*-
"""A0 — Khảo sát item_id thật theo statement cho từng nhóm ngành.

Mục đích: chốt danh sách item_id THẬT (không đoán) để xây sector_metrics.py
- ACB : ngân hàng   -> NIM, NPL, CAR, CIR, LDR, thu nhập lãi thuần...
- VHM : bất động sản -> hàng tồn kho, người mua trả trước, nợ vay, EBIT...
- HPG : sản xuất     -> phải thu, tồn kho, doanh thu, CFO...

Chạy: python scripts/diag_items.py [SYMBOL ...]
"""
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "database" / "market.db"

# từ khoá dò theo tên tiếng Việt/Anh để lọc nhanh item liên quan mỗi nhóm
KEYWORDS = [
    "lãi", "interest", "tín dụng", "credit", "cho vay", "loan", "nợ xấu", "npl",
    "dự phòng", "provision", "an toàn vốn", "car", "capital adequacy",
    "tồn kho", "inventor", "phải thu", "receivable", "người mua", "advance",
    "chi phí hoạt động", "operating expense", "tiền gửi", "deposit",
    "doanh thu", "revenue", "net sales", "ebit", "vay", "borrow",
    "vốn chủ", "equity", "tổng tài sản", "total asset", "biên", "margin",
]


def dump(sym: str, con: sqlite3.Connection):
    print(f"\n{'='*70}\n{sym}\n{'='*70}")
    stmts = [r[0] for r in con.execute(
        "SELECT DISTINCT statement FROM financials WHERE symbol=? ORDER BY statement",
        (sym,))]
    periods = [r[0] for r in con.execute(
        "SELECT DISTINCT period FROM financials WHERE symbol=? ORDER BY period DESC LIMIT 8",
        (sym,))]
    print(f"statements: {stmts}")
    print(f"periods (mới nhất): {periods}")

    for st in stmts:
        rows = con.execute(
            "SELECT DISTINCT item_id, item, item_en FROM financials "
            "WHERE symbol=? AND statement=? ORDER BY item_id", (sym, st)).fetchall()
        print(f"\n--- {st} ({len(rows)} item) ---")
        for item_id, item, item_en in rows:
            it = (item or "").lower()
            ie = (item_en or "").lower()
            hit = any(k in it or k in ie for k in KEYWORDS)
            mark = " <<<" if hit else ""
            print(f"  [{item_id}] {item}  |  {item_en}{mark}")


def main():
    syms = [s.upper() for s in sys.argv[1:]] or ["ACB", "VHM", "HPG"]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    for s in syms:
        dump(s, con)
    con.close()


if __name__ == "__main__":
    main()
