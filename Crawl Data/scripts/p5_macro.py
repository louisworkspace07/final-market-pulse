"""P5 — Crawl bối cảnh vĩ mô & thị trường (dùng chung mọi mã).

  python -m scripts.p5_macro           # build nếu cache trong ngày đã cũ
  python -m scripts.p5_macro --force   # crawl lại ngay
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import macro


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="crawl lại kể cả khi cache còn mới")
    args = ap.parse_args()

    ctx = macro.build_context(force=args.force)
    print("→ Bối cảnh vĩ mô/thị trường:")
    for code, st in (ctx.get("indexes") or {}).items():
        if st.get("ok"):
            print(f"  {code}: {st['latest']} | 1M {st.get('pct_1m')} | YTD {st.get('pct_ytd')}")
        else:
            print(f"  {code}: (không lấy được)")
    fx = ctx.get("fx") or {}
    print(f"  USD/VND: mua {fx.get('usd_buy')} / bán {fx.get('usd_sell')} [{fx.get('source','n/a')}]")
    ind = ctx.get("indicators") or {}
    print(f"  Vĩ mô (seed as_of {ind.get('as_of')}): "
          f"GDP { (ind.get('gdp_growth_yoy') or {}).get('value') } | "
          f"CPI { (ind.get('cpi_yoy') or {}).get('value') } | "
          f"Lãi suất { (ind.get('policy_rate') or {}).get('value') }")
    print(f"  Nguồn: {ctx.get('sources')}")
    print("\n✓ Xong P5. Ghi tại data/macro/context.json")


if __name__ == "__main__":
    main()
