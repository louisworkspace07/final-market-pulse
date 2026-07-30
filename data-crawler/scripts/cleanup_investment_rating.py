"""Dọn các khoá bị cấm khỏi ai_analysis.analysis trong market.db (§6 + A7).

VÌ SAO CẦN: plan ghi 25 bản ghi, nhưng đo thật có 41 — plan chỉ đếm khoá gốc
`/investment_rating` (25) và bỏ sót 16 bản ghi nằm sâu trong
`/aspects/{valuation,growth,risk,financial}/investment_rating`.

Khoá bị xoá (đệ quy MỌI độ sâu, khớp không phân biệt hoa-thường):
    investment_rating, target_price, upside_to_target_percent,
    recommendation, winner

KHÔNG xoá `verdict` / `valuation_verdict`: theo schema của analyzer.py đây là
văn xuôi mô tả, và tầng API của EconoPulse đã lọc ở biên. Muốn xoá thì thêm vào
EXTRA_KEYS bên dưới — nhưng đó là quyết định của người chạy, không phải mặc định.

CÁCH CHẠY (mặc định là chạy thử, KHÔNG ghi):
    py -3.12 scripts/cleanup_investment_rating.py            # dry-run
    py -3.12 scripts/cleanup_investment_rating.py --apply    # ghi thật

--apply sẽ tự sao lưu bằng sqlite backup API (an toàn với WAL, không copy file
thô) ra database/market.db.bak-legal-<timestamp> trước khi UPDATE.
Nên dừng service đang ghi vào DB trước khi chạy --apply.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "database" / "market.db"

BANNED_KEYS = frozenset({
    "investment_rating",
    "target_price",
    "upside_to_target_percent",
    "recommendation",
    "winner",
})

# Thêm khoá ở đây nếu muốn dọn cả verdict/valuation_verdict.
EXTRA_KEYS: frozenset[str] = frozenset()


def _drop(key) -> bool:
    if not isinstance(key, str):
        return False
    k = key.strip().lower()
    return k in BANNED_KEYS or k in EXTRA_KEYS


def scrub(obj):
    """Bản sao của obj đã loại mọi khoá bị cấm ở mọi độ sâu."""
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items() if not _drop(k)}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    return obj


def find_paths(obj, prefix=""):
    """Đường dẫn tới các khoá bị cấm CÓ GIÁ TRỊ THẬT (bỏ qua null/rỗng)."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}/{k}"
            if _drop(k):
                if v not in (None, "", [], {}):
                    out.append((p, v))
            else:
                out += find_paths(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += find_paths(v, f"{prefix}[{i}]")
    return out


def backup(db_path: Path) -> Path:
    """Sao lưu qua sqlite backup API — an toàn khi DB đang ở chế độ WAL."""
    dest = db_path.with_name(
        f"{db_path.name}.bak-legal-{time.strftime('%Y%m%d-%H%M%S')}")
    src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    dst = sqlite3.connect(str(dest))
    try:
        with dst:
            src.backup(dst)
    finally:
        src.close()
        dst.close()
    return dest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="Ghi thật vào DB (mặc định chỉ chạy thử)")
    ap.add_argument("--db", default=str(DB))
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"KHONG THAY DB: {db_path}", file=sys.stderr)
        return 2

    mode = "ro" if not args.apply else "rw"
    conn = sqlite3.connect(f"file:{db_path}?mode={mode}", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT symbol, analysis FROM ai_analysis").fetchall()

    hits: list[tuple[str, str, object]] = []   # (symbol, path, value)
    changed: list[tuple[str, str]] = []        # (symbol, new_json)
    bad_json = 0

    for r in rows:
        try:
            before = json.loads(r["analysis"])
        except Exception:
            bad_json += 1
            continue
        for p, v in find_paths(before):
            hits.append((r["symbol"], p, v))
        after = scrub(before)
        if after != before:
            changed.append((r["symbol"],
                            json.dumps(after, ensure_ascii=False)))

    by_path: dict[str, int] = {}
    for _sym, p, _v in hits:
        by_path[p] = by_path.get(p, 0) + 1

    print(f"Tong ban ghi ai_analysis      : {len(rows)}")
    print(f"JSON loi (bo qua)             : {bad_json}")
    print(f"Ban ghi co GIA TRI that       : {len({s for s, _, _ in hits})}")
    print(f"Ban ghi se bi UPDATE          : {len(changed)}"
          "  (gom ca ban ghi chi co khoa rong)")
    if by_path:
        print("\nPhan bo theo duong dan:")
        for p, n in sorted(by_path.items(), key=lambda x: -x[1]):
            print(f"  {n:5d}  {p}")
        print("\nGia tri cu the:")
        for sym, p, v in sorted(hits):
            print(f"  {sym:6s} {p} = {v!r}")

    if not args.apply:
        print("\n[DRY-RUN] Chua ghi gi. Chay lai voi --apply de ghi that.")
        return 0

    if not changed:
        print("\nKhong co gi phai sua.")
        return 0

    dest = backup(db_path)
    print(f"\nDa sao luu: {dest} ({os.path.getsize(dest)} bytes)")

    with conn:
        conn.executemany(
            "UPDATE ai_analysis SET analysis = ? WHERE symbol = ?",
            [(js, sym) for sym, js in changed])
    print(f"Da UPDATE {len(changed)} ban ghi.")

    left = 0
    for r in conn.execute("SELECT symbol, analysis FROM ai_analysis"):
        try:
            if find_paths(json.loads(r["analysis"])):
                left += 1
        except Exception:
            pass
    print(f"Kiem tra lai — con lai: {left} (ky vong 0)")
    return 0 if left == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
