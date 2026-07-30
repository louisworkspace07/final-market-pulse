"""P1 — Crawl tài chính/dòng tiền cho các mã trong config/companies.txt.

Lưu JSON theo từng công ty + đồng bộ SQLite.
Chạy:  python -m scripts.p1_financials
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, httpguard, storage
from src.crawler_financials import crawl_one
from src.runner import guard


def main() -> None:
    config.ensure_dirs()
    # Ép ≤18 HTTP request/phút tới host vnstock (Guest = 20) để tránh bị chặn.
    httpguard.install(18)
    tickers = config.load_tickers()
    if not tickers:
        print("Không có mã nào trong config/companies.txt"); return

    print(f"→ Crawl tài chính cho {len(tickers)} mã: {', '.join(tickers)}\n")
    conn = storage.connect()
    for i, sym in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] {sym}")
        try:
            summary = guard(crawl_one, conn, sym)
            print(f"  ✓ {summary}")
        except (Exception, SystemExit) as exc:
            print(f"  ✗ Lỗi {sym}: {str(exc)[:80]}")
        if i < len(tickers):
            time.sleep(config.REQUEST_DELAY)
    conn.close()
    print(f"\n✓ Xong. Dữ liệu JSON: {config.COMPANIES_DIR}")
    print(f"  SQLite: {config.DB_PATH}")


if __name__ == "__main__":
    main()
