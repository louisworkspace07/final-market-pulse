# -*- coding: utf-8 -*-
"""P7 — Bối cảnh thị trường: chỉ số THẬT (VNINDEX/VN30/HNXINDEX) + tin cấp thị trường.

Hai bảng mới trong market.db:
- market_index(code, time, close, volume, value): lịch sử điểm số + thanh khoản,
  nguồn VNDirect (vndirect.index_history) — thay cho "proxy vốn hoá 33 mã" tự chế.
- market_news(id, query, title, source, link, public_date): tin BÁO CHÍ cấp
  thị trường (không gắn mã) qua Google News RSS — bằng chứng [M..] cho AI giải
  thích nguyên nhân TOÀN thị trường.

  python scripts/p7_market_context.py            # cập nhật cả 2
  python scripts/p7_market_context.py --days 400 # độ sâu index lần đầu
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import news_rss, storage, vndirect

ROOT = Path(__file__).resolve().parent.parent
INDEXES = ("VNINDEX", "VN30", "HNX")   # HNX = HNX-Index trên VNDirect
# Query tin cấp thị trường (tiếng Việt) — mỗi query 1 nhóm chủ đề.
MARKET_QUERIES = [
    "chứng khoán Việt Nam VN-Index",
    "khối ngoại chứng khoán",
    "lãi suất ngân hàng nhà nước",
    "kinh tế vĩ mô Việt Nam GDP CPI",
    "xuất khẩu Việt Nam",
    "FDI Việt Nam giải ngân",
]


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS market_index ("
                 "code TEXT, time TEXT, close REAL, volume REAL, value REAL, "
                 "PRIMARY KEY (code, time))")
    conn.execute("CREATE TABLE IF NOT EXISTS market_news ("
                 "id INTEGER PRIMARY KEY AUTOINCREMENT, query TEXT, title TEXT, "
                 "source TEXT, link TEXT UNIQUE, public_date TEXT, fetched_at TEXT)")


def crawl_indexes(conn, days: int) -> None:
    start = (date.today() - timedelta(days=days)).isoformat()
    end = date.today().isoformat()
    for code in INDEXES:
        # incremental: chỉ lấy phần sau phiên mới nhất đã có
        lt = conn.execute("SELECT max(time) FROM market_index WHERE code=?",
                          (code,)).fetchone()[0]
        s = max(start, lt) if lt else start
        try:
            rows = vndirect.index_history(code, s, end)
        except Exception as exc:
            print(f"  [!] {code}: {str(exc)[:80]}")
            continue
        conn.executemany(
            "INSERT OR REPLACE INTO market_index(code, time, close, volume, value) "
            "VALUES (?,?,?,?,?)",
            [(code, r["time"], r["close"], r["volume"], r["value"])
             for r in rows if r.get("time") and r.get("close") is not None])
        conn.commit()
        n = conn.execute("SELECT count(*) FROM market_index WHERE code=?", (code,)).fetchone()[0]
        last = conn.execute("SELECT time, close FROM market_index WHERE code=? "
                            "ORDER BY time DESC LIMIT 1", (code,)).fetchone()
        print(f"  {code}: +{len(rows)} phiên (tổng {n}) · mới nhất {last}")


def crawl_market_news(conn) -> None:
    total = 0
    for q in MARKET_QUERIES:
        # news_rss.fetch nhận (symbol, company_name) và query "symbol cổ phiếu";
        # với tin thị trường ta truyền thẳng chủ đề làm company_name, symbol rỗng
        # sẽ tạo query " <chủ đề>" — vẫn hợp lệ với Google News RSS.
        items = news_rss.fetch("", q, limit=15)
        for it in items:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO market_news"
                    "(query, title, source, link, public_date, fetched_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (q, it.get("title"), it.get("source"), it.get("link"),
                     it.get("public_date"), storage.now_iso()))
                total += conn.total_changes and 0 or 0
            except Exception:
                pass
        conn.commit()
        print(f"  RSS '{q}': {len(items)} bài")
    n = conn.execute("SELECT count(*) FROM market_news").fetchone()[0]
    print(f"  → bảng market_news: {n} bài (unique theo link)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=400)
    args = ap.parse_args()
    conn = sqlite3.connect(ROOT / "database" / "market.db")
    ensure_schema(conn)
    print("[1/2] Chỉ số thị trường (VNDirect)...")
    crawl_indexes(conn, args.days)
    print("[2/2] Tin cấp thị trường (Google News RSS)...")
    crawl_market_news(conn)
    conn.close()
    print("✓ Xong P7.")


if __name__ == "__main__":
    main()
