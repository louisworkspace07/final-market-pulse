"""Chẩn đoán nhanh cấu trúc thật của Finance.ratio() trên bản vnstock đang cài.

Chạy 1 lần để xác nhận: cột kỳ nằm ở đâu (dòng hay cột), có yearReport/
lengthReport không, MultiIndex ra sao. Kết quả dùng để viết ratio_to_records().

  python -m scripts.diag_ratio          # mặc định FPT
  python -m scripts.diag_ratio VNM
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from vnstock import Finance

from src import config

pd.set_option("display.max_columns", 30)
pd.set_option("display.width", 200)


def dump(symbol: str, ptype: str) -> None:
    print(f"\n{'='*70}\n{symbol} ratio(period={ptype!r}) source={config.FINANCE_SOURCE}\n{'='*70}")
    fin = Finance(symbol=symbol, source=config.FINANCE_SOURCE)
    df = fin.ratio(period=ptype)
    print(f"type            = {type(df)}")
    print(f"shape           = {getattr(df, 'shape', None)}")
    print(f"columns.type    = {type(df.columns)}")
    print(f"columns         = {list(df.columns)[:40]}")
    print(f"index.type      = {type(df.index)}")
    print(f"index           = {list(df.index)[:20]}")
    print("--- head(3) ---")
    print(df.head(3).to_string())


def main() -> None:
    symbol = (sys.argv[1] if len(sys.argv) > 1 else "FPT").upper()
    for ptype in ("year", "quarter"):
        try:
            dump(symbol, ptype)
        except Exception as exc:
            print(f"  [!] {symbol} ratio({ptype}): {exc}")


if __name__ == "__main__":
    main()
