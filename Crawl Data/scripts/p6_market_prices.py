# -*- coding: utf-8 -*-
"""P6 — Giá lịch sử OHLCV cho TOÀN thị trường (universe HOSE+HNX) qua VNDirect.

Mục đích: bảng price hiện chỉ có ~33 mã → phân tích "toàn thị trường" thực chất
là VN30. Script này đổ 1 năm OHLCV cho toàn bộ mã trong config/universe.json
để tầng kỹ thuật (độ rộng, MA20/50, S/R theo ngành) tính được trên cả thị trường.

- Nguồn: api-finfo.vndirect.com.vn (REST công khai, không dính rate-limit vnstock).
- Resume: mã đã có dữ liệu tới phiên gần nhất (mặc định trong vòng 3 ngày) → bỏ qua.
- Ghi: INSERT OR REPLACE vào bảng price (khóa symbol+time), không xóa dữ liệu cũ.

  python scripts/p6_market_prices.py                 # toàn bộ universe
  python scripts/p6_market_prices.py --limit 20      # thử 20 mã đầu
  python scripts/p6_market_prices.py --days 365      # độ sâu lịch sử
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import storage, vndirect

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE = ROOT / "config" / "universe.json"


def load_universe() -> list[str]:
    data = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    return data["symbols"]


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS price ("
                 "symbol TEXT, time TEXT, open REAL, high REAL, low REAL, "
                 "close REAL, volume REAL, PRIMARY KEY (symbol, time))")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_price_key "
                 "ON price(symbol, time)")


def last_time(conn, symbol: str) -> str | None:
    r = conn.execute("SELECT max(time) FROM price WHERE symbol=?", (symbol,)).fetchone()
    return r[0] if r and r[0] else None


def crawl_one(conn, symbol: str, start: str, end: str) -> int:
    rows = vndirect.price_history(symbol, start, end)
    if not rows:
        return 0
    conn.executemany(
        "INSERT OR REPLACE INTO price(symbol, time, open, high, low, close, volume) "
        "VALUES (?,?,?,?,?,?,?)",
        [(symbol, r["time"], r["open"], r["high"], r["low"], r["close"], r["volume"])
         for r in rows if r.get("time") and r.get("close") is not None])
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0 = toàn bộ universe")
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--delay", type=float, default=0.25, help="giãn nhịp giữa các mã (giây)")
    ap.add_argument("--fresh-days", type=int, default=3,
                    help="mã đã có dữ liệu trong N ngày gần đây → bỏ qua (resume)")
    args = ap.parse_args()

    symbols = load_universe()
    if args.limit > 0:
        symbols = symbols[:args.limit]
    end = date.today().isoformat()
    start_full = (date.today() - timedelta(days=args.days)).isoformat()
    fresh_cut = (date.today() - timedelta(days=args.fresh_days)).isoformat()

    conn = sqlite3.connect(ROOT / "database" / "market.db")
    ensure_schema(conn)

    print(f"P6 market prices: {len(symbols)} mã · {start_full} → {end}")
    ok = skip = err = total = 0
    t0 = time.time()
    for i, sym in enumerate(symbols, 1):
        lt = last_time(conn, sym)
        if lt and lt >= fresh_cut:
            skip += 1
            continue
        # đã có 1 phần lịch sử → chỉ lấy phần thiếu (incremental)
        start = max(start_full, lt) if lt else start_full
        n = None
        for attempt in (1, 2):   # lỗi mạng/CDN tạm thời → thử lại 1 lần
            try:
                n = crawl_one(conn, sym, start, end)
                break
            except Exception as exc:
                if attempt == 2:
                    err += 1
                    print(f"  [{i}/{len(symbols)}] ✗ {sym}: {str(exc)[:80]}")
                time.sleep(2)
        if n is not None:
            conn.commit()
            ok += 1
            total += n
            if i % 25 == 0 or n == 0:
                print(f"  [{i}/{len(symbols)}] {sym}: +{n} phiên "
                      f"(ok {ok} · skip {skip} · err {err} · {time.time()-t0:.0f}s)")
        time.sleep(args.delay)

    n_sym = conn.execute("SELECT count(distinct symbol) FROM price").fetchone()[0]
    conn.close()
    print(f"\n✓ Xong P6: crawl {ok} mã (+{total} dòng), bỏ qua {skip}, lỗi {err} "
          f"trong {time.time()-t0:.0f}s. Bảng price hiện có {n_sym} mã.")


if __name__ == "__main__":
    main()
