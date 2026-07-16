# -*- coding: utf-8 -*-
"""Tải dữ liệu kinh tế vĩ mô Việt Nam từ World Bank API (có cache CSV cục bộ).

Chỉ số sử dụng:
- NY.GDP.MKTP.KD.ZG : Tăng trưởng GDP thực (% / năm)
- FP.CPI.TOTL.ZG    : Lạm phát CPI (% / năm)
- NE.EXP.GNFS.ZG    : Tăng trưởng xuất khẩu (% / năm)
- SL.UEM.TOTL.ZS    : Tỷ lệ thất nghiệp (%)
"""
import os
import json
import requests
import pandas as pd

CACHE_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(CACHE_DIR, exist_ok=True)

INDICATORS = {
    "gdp_growth": "NY.GDP.MKTP.KD.ZG",
    "cpi": "FP.CPI.TOTL.ZG",
    "export_growth": "NE.EXP.GNFS.ZG",
    "unemployment": "SL.UEM.TOTL.ZS",
}

WB_URL = "https://api.worldbank.org/v2/country/VNM/indicator/{code}?format=json&per_page=100"


def _fetch_indicator(code: str) -> pd.Series:
    r = requests.get(WB_URL.format(code=code), timeout=30)
    r.raise_for_status()
    rows = r.json()[1]
    data = {int(d["date"]): d["value"] for d in rows if d["value"] is not None}
    return pd.Series(data).sort_index()


def load_macro(refresh: bool = False) -> pd.DataFrame:
    """Trả về DataFrame index = năm, cột = các chỉ số vĩ mô.

    Ưu tiên cache CSV; nếu refresh=True hoặc chưa có cache thì gọi World Bank API.
    """
    cache_file = os.path.join(CACHE_DIR, "vn_macro.csv")
    if not refresh and os.path.exists(cache_file):
        return pd.read_csv(cache_file, index_col=0)

    frames = {}
    for name, code in INDICATORS.items():
        try:
            frames[name] = _fetch_indicator(code)
            print(f"  [WB] {name}: {len(frames[name])} nam, moi nhat {frames[name].index.max()}")
        except Exception as e:
            print(f"  [WB] loi tai {name}: {e}")

    df = pd.DataFrame(frames)
    df.index.name = "year"
    df.to_csv(cache_file)
    return df


if __name__ == "__main__":
    df = load_macro(refresh=True)
    print(df.tail(10))
