"""P9 · Ảnh 1 — Crawl OHLC các chỉ số (VNINDEX/VN30/HNXINDEX) vào bảng index_ohlc.

Vì sao cần: bảng `market_index` hiện có chỉ lưu `close` (và mới ~275 phiên từ
2025-06), nên hero trang chủ buộc phải vẽ area và tab "Tất cả" thực chất chỉ là
~1 năm — đúng phàn nàn "scale sai, không đủ nến". Bảng mới này có đủ O/H/L/C nên
vẽ được nến thật, và lấy lịch sử dài.

KHÔNG đụng `market_index` (market_range đang dùng) — tạo bảng riêng, an toàn.

Chạy:
    py -3.12 -m scripts.p9_index_ohlc              # incremental (mặc định)
    py -3.12 -m scripts.p9_index_ohlc --full       # tải lại từ START_DATE
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
import warnings

warnings.filterwarnings("ignore")

from src.config import DB_PATH          # noqa: E402  (config ép UTF-8 khi import)

START_DATE = "2015-01-01"
INDEXES = ["VNINDEX", "VN30", "HNXINDEX"]

DDL = """
CREATE TABLE IF NOT EXISTS index_ohlc (
    code   TEXT,
    time   TEXT,
    open   REAL,
    high   REAL,
    low    REAL,
    close  REAL,
    volume REAL,
    PRIMARY KEY (code, time)
)
"""


def _fetch(code: str, start: str, end: str):
    """Lấy OHLC 1 chỉ số. Ưu tiên VNDirect API công khai, hỏng thì thử vnstock."""
    import pandas as pd
    from src import vndirect

    vn_code = "HNX" if code == "HNXINDEX" else code
    try:
        page = 1
        records = []
        while True:
            j = vndirect._get("vnmarket_prices", {
                "q": f"code:{vn_code}~date:gte:{start}~date:lte:{end}",
                "sort": "date", "size": 1000, "page": page,
            })
            data = j.get("data", [])
            for d in data:
                records.append({
                    "time": d.get("date"),
                    "open": d.get("open"),
                    "high": d.get("high"),
                    "low": d.get("low"),
                    "close": d.get("close"),
                    "volume": d.get("accumulatedVol") or d.get("nmVolume") or 0,
                })
            if page >= j.get("totalPages", 1) or not data:
                break
            page += 1
        if records:
            df = pd.DataFrame(records)
            df.sort_values("time", inplace=True)
            return df, "VNDirect"
    except Exception as e:
        last_err = e

    # Fallback: vnstock nếu có
    for src in ("VCI", "TCBS"):
        try:
            from vnstock import Quote
            df = Quote(symbol=code, source=src).history(
                start=start, end=end, interval="1D")
            if df is not None and len(df):
                return df, src
        except Exception as e:
            last_err = e
    raise RuntimeError(f"{code}: không nguồn nào trả dữ liệu ({last_err})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true",
                    help="tải lại toàn bộ từ START_DATE thay vì chỉ phần thiếu")
    args = ap.parse_args()

    con = sqlite3.connect(DB_PATH)
    con.execute(DDL)
    con.commit()

    today = time.strftime("%Y-%m-%d")
    total = 0
    for code in INDEXES:
        start = START_DATE
        if not args.full:
            row = con.execute(
                "SELECT MAX(time) FROM index_ohlc WHERE code=?", (code,)).fetchone()
            if row and row[0]:
                start = row[0]          # chồng lấn 1 phiên → INSERT OR REPLACE lo
        try:
            df, src = _fetch(code, start, today)
        except Exception as e:
            print(f"  {code}: BO QUA — {str(e)[:140]}")
            continue

        rows = []
        for r in df.itertuples(index=False):
            t = str(getattr(r, "time"))[:10]
            rows.append((code, t,
                         float(getattr(r, "open")), float(getattr(r, "high")),
                         float(getattr(r, "low")), float(getattr(r, "close")),
                         float(getattr(r, "volume") or 0)))
        con.executemany(
            "INSERT OR REPLACE INTO index_ohlc "
            "(code,time,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?)", rows)
        con.commit()
        total += len(rows)
        span = con.execute(
            "SELECT MIN(time), MAX(time), COUNT(*) FROM index_ohlc WHERE code=?",
            (code,)).fetchone()
        print(f"  {code} ({src}): +{len(rows)} phien | DB co {span[2]} phien {span[0]} -> {span[1]}")

    con.close()
    print(f"P9 xong: {total} dong ghi vao index_ohlc")
    return 0


if __name__ == "__main__":
    sys.exit(main())
