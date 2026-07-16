"""P0 — Lấy danh sách toàn bộ mã thị trường VN, lưu JSON + bảng companies (SQLite).

Chạy:  python -m scripts.p0_symbols
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vnstock import Listing

from src import config, storage


def main() -> None:
    config.ensure_dirs()
    print("→ Lấy danh sách mã toàn thị trường (vnstock)...")
    df = Listing().all_symbols()
    print(f"  Tổng số mã: {len(df)}")

    records = df.to_dict(orient="records")
    storage.write_json(
        config.DATABASE_DIR / "symbols.json",
        {"fetched_at": storage.now_iso(), "count": len(records), "symbols": records},
    )

    conn = storage.connect()
    for r in records:
        storage.upsert_company(
            conn, str(r.get("symbol", "")),
            organ_name=str(r.get("organ_name", "")),
        )
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    conn.close()
    print(f"✓ Đã lưu {n} công ty vào SQLite + database/symbols.json")


if __name__ == "__main__":
    main()
