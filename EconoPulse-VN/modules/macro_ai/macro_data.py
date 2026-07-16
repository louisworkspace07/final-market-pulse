# -*- coding: utf-8 -*-
"""Mở rộng dữ liệu vĩ mô (C1) → gom thành macro_plus.json.

Xếp theo ĐỘ TIN CẬY nguồn:
  1. World Bank (chắc chắn — cùng API data_loader.py): 6 indicator annual, 15 năm.
  2. Daily có sẵn: tỷ giá VCB (vndirect.exchange_rate).
  3. Probe (fail thì bỏ qua có ghi chú): vàng SJC, dầu Brent (stooq). Mỗi probe theo
     pattern exchange_rate(): try/timeout/trả {} — KHÔNG BAO GIỜ chặn pipeline.
  4. Seed tay (config/macro_seed.json): lãi suất điều hành, tăng trưởng tín dụng.

Nguyên tắc trung thực: nguồn nào không lấy được → key vẫn có mặt với
{available: False, reason} thay vì biến mất hay bịa số.
"""
from __future__ import annotations

import json
import os
import time

import requests

# 6 indicator World Bank (annual). Nợ công GC.DOD... không có số cho VN → sẽ
# tự rơi vào nhánh "available: False" khi WB trả rỗng (đã kiểm chứng).
WB_INDICATORS = {
    "export_growth": {"code": "NE.EXP.GNFS.KD.ZG", "label": "Tăng trưởng xuất khẩu HH-DV", "unit": "%"},
    "fdi_net":       {"code": "BX.KLT.DINV.WD.GD.ZS", "label": "FDI ròng / GDP", "unit": "%"},
    "unemployment":  {"code": "SL.UEM.TOTL.ZS", "label": "Tỷ lệ thất nghiệp", "unit": "%"},
    "fx_official":   {"code": "PA.NUS.FCRF", "label": "Tỷ giá chính thức (LCU/USD)", "unit": "VND/USD"},
    "m2_gdp":        {"code": "FM.LBL.BMNY.GD.ZS", "label": "Cung tiền M2 / GDP", "unit": "%"},
    "gov_debt":      {"code": "GC.DOD.TOTL.GD.ZS", "label": "Nợ công / GDP", "unit": "%"},
}

WB_URL = "https://api.worldbank.org/v2/country/VNM/indicator/{code}?format=json&per_page=100"
_HISTORY_YEARS = 15
_TIMEOUT = 20

_SEED_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "Crawl Data", "config", "macro_seed.json"))


# ── Nguồn 1: World Bank ──────────────────────────────────────────────────────
def _fetch_wb(code: str) -> list[dict]:
    """[{year, value}] tăng dần, tối đa 15 năm gần nhất. Lỗi → ném để tầng trên bắt."""
    r = requests.get(WB_URL.format(code=code), timeout=_TIMEOUT)
    r.raise_for_status()
    payload = r.json()
    rows = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
    series = [{"year": int(d["date"]), "value": d["value"]}
              for d in rows if d.get("value") is not None]
    series.sort(key=lambda x: x["year"])
    return series[-_HISTORY_YEARS:]


def _wb_indicators() -> dict:
    out = {}
    for key, meta in WB_INDICATORS.items():
        try:
            series = _fetch_wb(meta["code"])
            if series:
                latest = series[-1]
                out[key] = {
                    "available": True, "label": meta["label"], "unit": meta["unit"],
                    "series": series, "latest": latest["value"],
                    "as_of": str(latest["year"]), "source": "World Bank",
                    "code": meta["code"],
                }
            else:
                out[key] = {"available": False, "label": meta["label"],
                            "reason": "World Bank không có số liệu cho VN",
                            "source": "World Bank", "code": meta["code"]}
        except Exception as e:
            out[key] = {"available": False, "label": meta["label"],
                        "reason": f"Lỗi tải World Bank: {str(e)[:80]}",
                        "source": "World Bank", "code": meta["code"]}
    return out


# ── Nguồn 2: FX daily (VCB qua vndirect.exchange_rate) ───────────────────────
def _fx() -> dict:
    try:
        import sys
        crawl_src = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "Crawl Data", "src"))
        if crawl_src not in sys.path:
            sys.path.insert(0, crawl_src)
        import vndirect
        fx = vndirect.exchange_rate()
        if fx and fx.get("usd_sell"):
            fx["available"] = True
            return fx
    except Exception as e:
        return {"available": False, "reason": f"Lỗi tỷ giá VCB: {str(e)[:80]}"}
    return {"available": False, "reason": "Không lấy được tỷ giá VCB"}


# ── Nguồn 3: probe (fail → {available:false, reason}, không chặn pipeline) ────
_PROBE_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MarketPulse/1.0)"}
_PROBE_TIMEOUT = 8


def probe_gold() -> dict:
    """Giá vàng SJC qua endpoint công khai. Probe: try/timeout/không lấy được → reason."""
    try:
        r = requests.get("https://sjc.com.vn/giavang/textContent.php",
                         headers=_PROBE_HEADERS, timeout=_PROBE_TIMEOUT)
        r.raise_for_status()
        txt = r.text
        # Endpoint trả bảng HTML; bóc cặp số mua/bán đầu tiên (SJC 1L).
        import re
        nums = re.findall(r"[\d.,]{7,}", txt)
        prices = [int(n.replace(".", "").replace(",", "")) for n in nums
                  if len(n.replace(".", "").replace(",", "")) >= 7][:2]
        if len(prices) >= 2:
            return {"available": True, "buy": prices[0], "sell": prices[1],
                    "unit": "VND/lượng", "source": "SJC", "as_of": _today()}
        return {"available": False, "reason": "SJC trả dữ liệu không parse được"}
    except Exception as e:
        return {"available": False, "reason": f"SJC không phản hồi: {str(e)[:80]}"}


def probe_oil() -> dict:
    """Giá dầu Brent qua stooq CSV (không cần key). Probe: fail → reason."""
    try:
        r = requests.get("https://stooq.com/q/l/?s=cb.f&f=sd2t2ohlcv&h&e=csv",
                         headers=_PROBE_HEADERS, timeout=_PROBE_TIMEOUT)
        r.raise_for_status()
        lines = r.text.strip().splitlines()
        if len(lines) >= 2 and "," in lines[1] and not lines[0].startswith("<"):
            cols = lines[0].split(",")
            vals = lines[1].split(",")
            row = dict(zip(cols, vals))
            close = row.get("Close")
            if close and close not in ("N/D", ""):
                return {"available": True, "brent_usd": float(close),
                        "unit": "USD/thùng", "source": "stooq (Brent cb.f)",
                        "as_of": row.get("Date") or _today()}
        return {"available": False, "reason": "stooq trả dữ liệu không hợp lệ"}
    except Exception as e:
        return {"available": False, "reason": f"stooq không phản hồi: {str(e)[:80]}"}


# ── Nguồn 4: seed tay ────────────────────────────────────────────────────────
def _seed() -> dict:
    try:
        with open(_SEED_PATH, encoding="utf-8") as f:
            seed = json.load(f)
        as_of = seed.get("as_of")
        keep = {}
        for k in ("policy_rate", "credit_growth_ytd", "gdp_growth_yoy", "cpi_yoy"):
            if isinstance(seed.get(k), dict):
                v = dict(seed[k])
                v["source_type"] = "seed"   # nhãn "cập nhật tay"
                v["as_of"] = as_of
                keep[k] = v
        return {"available": bool(keep), "as_of": as_of, "data": keep,
                "note": "Cập nhật tay theo GSO/SBV"}
    except Exception as e:
        return {"available": False, "reason": f"Lỗi đọc seed: {str(e)[:80]}"}


def _today() -> str:
    return time.strftime("%Y-%m-%d")


# ── Gom tất cả ───────────────────────────────────────────────────────────────
def build_macro_plus() -> dict:
    """Bước [1b/4]: gom mọi nguồn → dict cho macro_plus.json."""
    return {
        "indicators": _wb_indicators(),
        "fx": _fx(),
        "gold": probe_gold(),
        "oil": probe_oil(),
        "seed": _seed(),
        "updated_at": time.strftime("%Y-%m-%d %H:%M"),
    }


if __name__ == "__main__":
    d = build_macro_plus()
    ind = d["indicators"]
    n_ok = sum(1 for v in ind.values() if v.get("available"))
    print(f"indicators: {n_ok}/{len(ind)} available")
    for k, v in ind.items():
        s = f"latest={v.get('latest')} ({v.get('as_of')})" if v.get("available") else f"✗ {v.get('reason')}"
        print(f"  {k:14} {s}")
    for k in ("fx", "gold", "oil"):
        v = d[k]
        print(f"  {k:14} {'OK '+str({x:v[x] for x in v if x!='available'}) if v.get('available') else '✗ '+v.get('reason','')}")
