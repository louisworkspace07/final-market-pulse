"""Re-crawl CHỈ stage ratio cho các mã đã có companies/<MÃ>/financials/ratio.json.

Sửa hậu quả bug cũ: ratio.json sinh từ nguồn VCI có period rác ("2018", "2018.1"...).
Script này crawl lại ratio từ nguồn KBS (period chuẩn) + validate, ghi đè file JSON
và bảng financials (chỉ statement='ratio'), giữ nguyên 3 báo cáo kia.

Dùng lại rate-limit guard hiện có (src.runner.guard + httpguard 18 req/phút).

  python scripts/refix_ratio.py --limit 1     # thử 1 mã (FPT nếu có)
  python scripts/refix_ratio.py               # toàn bộ mã có ratio.json
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vnstock import Finance

from src import config, httpguard, storage
from src.crawler_financials import _merge_json_records
from src.runner import guard, _is_ratelimit


def _symbols_with_ratio() -> list[str]:
    """Các mã đã có file ratio.json, sắp xếp (FPT lên đầu nếu có để --limit 1 test)."""
    out: list[str] = []
    if not config.COMPANIES_DIR.exists():
        return out
    for d in sorted(config.COMPANIES_DIR.iterdir()):
        if (d / "financials" / "ratio.json").exists():
            out.append(d.name.upper())
    if "FPT" in out:
        out.remove("FPT")
        out.insert(0, "FPT")
    return out


def refix_one(conn, symbol: str) -> int:
    """Crawl lại ratio (KBS) cho 1 mã, ghi đè. Trả số record; ném lại rate-limit."""
    symbol = symbol.upper()
    cdir = config.company_dir(symbol)
    fin = Finance(symbol=symbol, source="KBS")

    combined: list[dict] = []
    seen: set = set()
    dropped = 0
    ok_any = False
    for ptype in ("year", "quarter"):
        try:
            df = fin.ratio(period=ptype)
        except Exception as exc:
            if _is_ratelimit(exc):
                raise
            print(f"  [!] {symbol} ratio ({ptype}): {str(exc)[:60]}")
            continue
        ok_any = True
        for r in storage.ratio_to_records(df):
            if not storage.CLEAN_PERIOD_RE.match(str(r["period"])):
                dropped += 1
                continue
            r["period_type"] = "Q" if "-Q" in r["period"] else "Y"
            key = (r["item_id"], r["period"])
            if key not in seen:
                seen.add(key)
                combined.append(r)

    if dropped:
        print(f"  [!] {symbol} ratio: bỏ {dropped} record period không chuẩn")
    if not ok_any or not combined:
        print(f"  [!] {symbol} ratio: không có dữ liệu → bỏ qua")
        return 0

    # File ratio cũ 100% là dữ liệu VCI hỏng (kể cả kỳ "2018" format sạch nhưng
    # GIÁ TRỊ rác) → GHI ĐÈ hẳn bằng dữ liệu KBS sạch, KHÔNG merge kỳ cũ.
    # (Các lần crawl SAU này qua crawler_financials mới merge tích lũy — lúc đó
    # dữ liệu nguồn đã là KBS sạch.)
    storage.write_json(
        cdir / "financials" / "ratio.json",
        {"symbol": symbol, "statement": "ratio",
         "fetched_at": storage.now_iso(), "records": combined},
    )
    # Xóa ratio cũ (period rác) rồi ghi lại → dọn sạch record "2018.1"...
    conn.execute("DELETE FROM financials WHERE symbol=? AND statement='ratio'",
                 (symbol,))
    storage.merge_financials(conn, symbol, "ratio", combined)
    conn.commit()
    return len(combined)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0 = toàn bộ")
    ap.add_argument("--delay", type=float, default=4.0)
    args = ap.parse_args()

    config.ensure_dirs()
    httpguard.install(18)
    conn = storage.connect()

    symbols = _symbols_with_ratio()
    if args.limit > 0:
        symbols = symbols[:args.limit]
    print(f"Refix ratio: {len(symbols)} mã (nguồn KBS)")

    ok = err = 0
    for i, sym in enumerate(symbols, 1):
        try:
            n = guard(refix_one, conn, sym)
            ok += 1
            print(f"  [{i}/{len(symbols)}] ✓ {sym}: {n} record")
        except (Exception, SystemExit) as exc:
            err += 1
            print(f"  [{i}/{len(symbols)}] ✗ {sym}: {str(exc)[:80]}")
        time.sleep(args.delay)
    conn.close()
    print(f"\n✓ Xong refix_ratio: thành công {ok}, lỗi {err}")


if __name__ == "__main__":
    main()
