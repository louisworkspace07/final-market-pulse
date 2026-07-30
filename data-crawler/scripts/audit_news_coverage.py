"""Ảnh 12 · Kiểm kê độ phủ tin tức theo mã — mã nào 0 tin, mã nào tin quá cũ.

Vì sao: timeline tin của nhiều mã dừng ở 2019 (LNC…), có mã trắng tin. Cần biết
CHÍNH XÁC bao nhiêu mã cần re-crawl trước khi chạy P2 cho 1.527 mã (rất tốn).

Chạy:
    py -3.12 -m scripts.audit_news_coverage                 # báo cáo + ghi CSV
    py -3.12 -m scripts.audit_news_coverage --stale-days 90
    py -3.12 -m scripts.audit_news_coverage --out-list logs/need_recrawl.txt
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import sqlite3
import sys

from src.config import DB_PATH, ROOT     # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stale-days", type=int, default=180,
                    help="tin mới nhất cũ hơn ngần này ngày = stale (mặc định 180)")
    ap.add_argument("--out-list", default="",
                    help="ghi danh sách mã cần re-crawl (1 mã/dòng) ra file này")
    args = ap.parse_args()

    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    # LEFT JOIN từ companies để BẮT ĐƯỢC cả mã 0 tin — query thẳng news sẽ sót.
    rows = con.execute("""
        SELECT c.symbol, c.exchange, COUNT(n.news_id) AS n, MAX(n.public_date) AS latest
        FROM companies c LEFT JOIN news n ON n.symbol = c.symbol
        GROUP BY c.symbol ORDER BY c.symbol
    """).fetchall()
    con.close()

    today = dt.date.today()
    cutoff = today - dt.timedelta(days=args.stale_days)
    empty, stale, ok = [], [], []
    for sym, exch, n, latest in rows:
        if not n:
            empty.append((sym, exch, 0, ""))
            continue
        try:
            d = dt.date.fromisoformat(str(latest)[:10])
        except ValueError:
            d = None
        if d is None or d < cutoff:
            stale.append((sym, exch, n, str(latest)[:10]))
        else:
            ok.append((sym, exch, n, str(latest)[:10]))

    logs = os.path.join(ROOT, "logs")
    os.makedirs(logs, exist_ok=True)
    csv_path = os.path.join(logs, "news_coverage.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "exchange", "so_tin", "tin_moi_nhat", "nhom"])
        for grp, items in (("0_tin", empty), ("qua_cu", stale), ("on", ok)):
            for sym, exch, n, latest in items:
                w.writerow([sym, exch, n, latest, grp])

    total = len(rows)
    print(f"Tong so ma trong bang companies: {total}")
    print(f"  0 tin      : {len(empty):5d} ({len(empty)/total*100:.1f}%)")
    print(f"  qua cu >{args.stale_days}d: {len(stale):5d} ({len(stale)/total*100:.1f}%)")
    print(f"  con moi    : {len(ok):5d} ({len(ok)/total*100:.1f}%)")
    print(f"CSV: {csv_path}")

    if stale:
        oldest = sorted(stale, key=lambda x: x[3])[:8]
        print("\n8 ma co tin cu nhat:")
        for sym, exch, n, latest in oldest:
            print(f"  {sym:6s} {exch or '?':5s} {n:4d} tin, moi nhat {latest}")

    need = [s for s, *_ in empty + stale]
    if args.out_list:
        p = args.out_list if os.path.isabs(args.out_list) else os.path.join(ROOT, args.out_list)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(need))
        print(f"\nDanh sach {len(need)} ma can re-crawl: {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
