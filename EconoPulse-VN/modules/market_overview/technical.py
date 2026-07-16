# -*- coding: utf-8 -*-
"""Phân tích kỹ thuật cho Tổng quan Thị trường.

Hai nguồn dữ liệu (kết hợp cả 2 khi có):
1. BẢNG GIÁ REALTIME — output của dự án "Test tool dự án":
   ưu tiên gọi API sống http://127.0.0.1:5555/api/stocks; nếu server chưa bật
   → đọc file cache "Test tool dự án/temp_data/data.json" (gắn cờ live=False).
   Cho: giá khớp so tham chiếu, dư mua/dư bán 3 mức, khối ngoại, độ rộng phiên.
2. LỊCH SỬ GIÁ — bảng price trong market.db (dự án "Crawl Data"):
   Cho: SMA20/50, RSI14, MACD, vị trí so đỉnh/đáy 52 tuần, xu hướng khối lượng,
   độ rộng thị trường (% mã trên MA20, số mã tăng/giảm 20 phiên).

Toàn bộ chỉ báo tính thuần Python/pandas — kiểm chứng được, không phụ thuộc AI.
"""
import datetime as _dt
import json
import os
import sqlite3

import numpy as np
import pandas as pd
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(BASE, "..", ".."))
TESTTOOL_DIR = os.path.normpath(os.path.join(ROOT, "..", "Test tool dự án"))
BOARD_API = "http://127.0.0.1:5555/api/stocks"
BOARD_CACHE = os.path.join(TESTTOOL_DIR, "temp_data", "data.json")


# ------------------------------------------------------------------ bảng giá
# Trang Tổng quan gọi get_board gián tiếp NHIỀU lần/lần tải (board + heatmap +
# anomalies + regime). Mỗi lần chờ tới 2s timeout :5555 → cộng dồn rất chậm.
# Cache 4s: giá bảng điện delay ≥15s nên không mất tính "trực tiếp"; khi :5555
# tắt thì khỏi phải chờ timeout lặp lại + đọc lại file cache mỗi lần.
_BOARD_TTL = float(os.environ.get("MP_BOARD_TTL_S", "4"))
_board_cache: dict = {"ts": 0.0, "data": None}

# R1: khi :5555 TẮT, mỗi lần cache hết hạn lại tốn trọn 2s timeout. Với poller
# 15s/lần thì nhịp nào cũng treo 2s vô ích. Ngắt mạch: dò thất bại → nghỉ 60s,
# phục vụ thẳng cache file. Hết 60s mới thử lại (tự hồi khi :5555 bật lên).
_BOARD_PROBE_COOLDOWN = float(os.environ.get("MP_BOARD_COOLDOWN_S", "60"))
_board_probe: dict = {"down_until": 0.0}
# nội dung file cache đã parse, nhớ theo mtime (tránh đọc/parse lại mỗi nhịp)
_board_file_cache: dict = {"mtime": None, "rows": None, "as_of": None}


def get_board() -> dict:
    """Bảng giá realtime từ Test tool; fallback cache file. Cache TTL 4s."""
    import time as _t
    now = _t.time()
    if _board_cache["data"] is not None and now - _board_cache["ts"] < _BOARD_TTL:
        return _board_cache["data"]

    data = None
    if now >= _board_probe["down_until"]:          # còn trong cooldown thì khỏi dò
        try:
            r = requests.get(BOARD_API, timeout=2)
            r.raise_for_status()
            data = {"live": True, "source": "Test tool :5555/api/stocks",
                    "as_of": None, "rows": r.json()}
            _board_probe["down_until"] = 0.0       # sống lại → bỏ cooldown
        except Exception:
            _board_probe["down_until"] = now + _BOARD_PROBE_COOLDOWN
    if data is None and os.path.exists(BOARD_CACHE):
        # cache có tuổi — trả as_of (ISO) để AI + UI biết dữ liệu cũ mức nào.
        # R1: file này không đổi khi :5555 tắt → nhớ theo mtime, khỏi parse JSON
        # lại mỗi 4s (đây là phần lớn thời gian còn lại của /api/live).
        mtime = os.path.getmtime(BOARD_CACHE)
        if _board_file_cache.get("mtime") != mtime:
            with open(BOARD_CACHE, encoding="utf-8") as f:
                _board_file_cache["mtime"] = mtime
                _board_file_cache["rows"] = json.load(f)
                _board_file_cache["as_of"] = _dt.datetime.fromtimestamp(
                    mtime).isoformat(timespec="seconds")
        data = {"live": False,
                "source": "Test tool temp_data/data.json (cache — server chưa bật)",
                "as_of": _board_file_cache["as_of"], "rows": _board_file_cache["rows"]}
    if data is None:
        data = {"live": False, "source": "không có", "as_of": None, "rows": []}

    _board_cache["ts"], _board_cache["data"] = now, data
    return data


def board_stats(board: dict) -> dict:
    """Độ rộng phiên + dòng tiền khối ngoại + top biến động từ bảng giá."""
    rows = [r for r in board["rows"] if r.get("matchPrice") and r.get("ref")]
    if not rows:
        return {"available": False, "live": board["live"], "source": board["source"]}

    for r in rows:
        r["_chg_pct"] = (r["matchPrice"] - r["ref"]) / r["ref"] * 100
        r["_fnet"] = (r.get("foreignBuy") or 0) - (r.get("foreignSell") or 0)
        buy = sum(r.get(f"buyV{i}") or 0 for i in (1, 2, 3))
        sell = sum(r.get(f"sellV{i}") or 0 for i in (1, 2, 3))
        r["_book_ratio"] = round(buy / sell, 2) if sell > 0 else None

    up = sum(1 for r in rows if r["_chg_pct"] > 0.1)
    down = sum(1 for r in rows if r["_chg_pct"] < -0.1)
    flat = len(rows) - up - down
    gainers = sorted(rows, key=lambda r: -r["_chg_pct"])[:5]
    losers = sorted(rows, key=lambda r: r["_chg_pct"])[:5]
    fbuy = sorted(rows, key=lambda r: -r["_fnet"])[:5]

    def brief(r):
        return {"symbol": r["symbol"], "price": r["matchPrice"],
                "chg_pct": round(r["_chg_pct"], 2),
                "vol": r.get("totalVol"),
                "foreign_net": round(r["_fnet"], 0),
                "book_ratio": r["_book_ratio"]}

    return {
        "available": True, "live": board["live"], "source": board["source"],
        "n_symbols": len(rows),
        "breadth": {"up": up, "down": down, "flat": flat},
        "foreign_net_total": round(sum(r["_fnet"] for r in rows), 0),
        "top_gainers": [brief(r) for r in gainers],
        "top_losers": [brief(r) for r in losers],
        "top_foreign_buy": [brief(r) for r in fbuy],
    }


# ------------------------------------------------- kháng cự / hỗ trợ + VBP
def _swing_levels(close: pd.Series, window: int = 10) -> tuple[list, list]:
    """Đỉnh/đáy xoay chiều (swing highs/lows) — ứng viên kháng cự/hỗ trợ."""
    highs, lows = [], []
    v = close.values
    for i in range(window, len(v) - window):
        seg = v[i - window:i + window + 1]
        if v[i] == seg.max():
            highs.append(float(v[i]))
        if v[i] == seg.min():
            lows.append(float(v[i]))
    return highs, lows


def _cluster_zones(levels: list[float], tol_pct: float = 1.5) -> list[dict]:
    """Gom các mức giá gần nhau (±tol%) thành vùng; đếm số lần chạm."""
    zones = []
    for p in sorted(levels):
        for z in zones:
            if abs(p - z["price"]) / z["price"] * 100 <= tol_pct:
                z["touches"] += 1
                z["price"] = (z["price"] * (z["touches"] - 1) + p) / z["touches"]
                break
        else:
            zones.append({"price": p, "touches": 1})
    zones.sort(key=lambda z: -z["touches"])
    return zones


def _vbp_nodes(close: pd.Series, volume: pd.Series, bins: int = 24,
               lookback: int = 120) -> list[dict]:
    """Volume-by-Price: vùng giá tích lũy khối lượng lớn nhất (POC nodes).

    Chỉ tính `lookback` phiên gần nhất — vùng KL dày của 2 năm trước không còn
    ý nghĩa kháng cự/hỗ trợ khi giá đã đi rất xa (vd cổ phiếu tăng 3-4 lần).
    """
    df = pd.DataFrame({"c": close, "v": volume}).dropna().tail(lookback)
    if len(df) < 30:
        return []
    cats, edges = pd.cut(df["c"], bins=bins, retbins=True, labels=False)
    vol_by_bin = df.groupby(cats)["v"].sum()
    top = vol_by_bin.sort_values(ascending=False).head(3)
    total = float(df["v"].sum()) or 1.0
    return [{"price": round(float((edges[int(i)] + edges[int(i) + 1]) / 2), 2),
             "vol_share_pct": round(float(v) / total * 100, 1)}
            for i, v in top.items()]


def support_resistance(close: pd.Series, volume: pd.Series) -> dict:
    """Phân tích cung-cầu theo kháng cự/hỗ trợ cho 1 mã (thuần định lượng).

    Kết hợp 2 phương pháp giống app bảng giá: (1) swing pivots gom vùng,
    (2) Volume-by-Price — vùng khối lượng dày là hỗ trợ/kháng cự "cứng".
    """
    last = float(close.iloc[-1])
    highs, lows = _swing_levels(close)
    vbp = _vbp_nodes(close, volume)
    # ứng viên: swing zones + VBP nodes
    cands = _cluster_zones(highs + lows)[:8] + \
            [{"price": n["price"], "touches": 2, "vbp": n["vol_share_pct"]} for n in vbp]
    supports = sorted([z for z in cands if z["price"] < last * 0.998],
                      key=lambda z: -z["price"])
    resistances = sorted([z for z in cands if z["price"] > last * 1.002],
                         key=lambda z: z["price"])
    ns = supports[0] if supports else None
    nr = resistances[0] if resistances else None
    d_sup = round((last / ns["price"] - 1) * 100, 1) if ns else None
    d_res = round((nr["price"] / last - 1) * 100, 1) if nr else None

    if d_res is not None and d_res <= 2:
        position = "sát kháng cự"
    elif d_sup is not None and d_sup <= 2:
        position = "về hỗ trợ"
    elif d_res is None:
        position = "vượt đỉnh (không còn kháng cự trên)"
    else:
        position = "giữa vùng"
    return {
        "nearest_support": round(ns["price"], 2) if ns else None,
        "dist_support_pct": d_sup,
        "nearest_resistance": round(nr["price"], 2) if nr else None,
        "dist_resistance_pct": d_res,
        "position": position,
        "vbp_nodes": vbp[:2],
    }


# ------------------------------------------------------------- lịch sử giá
def _rsi(close: pd.Series, n: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(n).mean()
    loss = (-delta.clip(upper=0)).rolling(n).mean()
    rs = gain / loss.replace(0, np.nan)
    return float((100 - 100 / (1 + rs)).iloc[-1])


def _macd_state(close: pd.Series) -> str:
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    hist = (macd - signal).iloc[-1]
    prev = (macd - signal).iloc[-6]
    if hist > 0:
        return "dương (mở rộng)" if hist > prev else "dương (thu hẹp)"
    return "âm (thu hẹp)" if hist > prev else "âm (mở rộng)"


def technical_snapshot(db_path: str) -> dict:
    """Chỉ báo kỹ thuật từng mã + độ rộng thị trường từ lịch sử giá."""
    con = sqlite3.connect(db_path)
    px = pd.read_sql("select symbol, time, close, volume from price", con)
    con.close()
    px["date"] = pd.to_datetime(px["time"].str[:10])
    wide = px.pivot_table(index="date", columns="symbol", values="close")
    vol = px.pivot_table(index="date", columns="symbol", values="volume")

    per_symbol, above_ma20, up20 = [], 0, 0
    counted = 0
    for s in wide.columns:
        c = wide[s].dropna()
        if len(c) < 60:
            continue
        counted += 1
        sma20 = float(c.rolling(20).mean().iloc[-1])
        sma50 = float(c.rolling(50).mean().iloc[-1])
        last = float(c.iloc[-1])
        chg20 = (last / float(c.iloc[-21]) - 1) * 100
        hi52 = float(c.iloc[-250:].max()) if len(c) >= 250 else float(c.max())
        v = vol[s].dropna()
        vol_ratio = (float(v.iloc[-5:].mean()) / float(v.iloc[-60:].mean())
                     if len(v) >= 60 and v.iloc[-60:].mean() > 0 else None)
        if last > sma20:
            above_ma20 += 1
        if chg20 > 0:
            up20 += 1
        sr = support_resistance(c, vol[s])
        per_symbol.append({
            "symbol": s, "close": last,
            "vs_sma20_pct": round((last / sma20 - 1) * 100, 1),
            "vs_sma50_pct": round((last / sma50 - 1) * 100, 1),
            **sr,
            "rsi14": round(_rsi(c), 1),
            "macd": _macd_state(c),
            "chg_20d_pct": round(chg20, 1),
            "vs_52w_high_pct": round((last / hi52 - 1) * 100, 1),
            "vol_5d_vs_60d": round(vol_ratio, 2) if vol_ratio else None,
        })

    per_symbol.sort(key=lambda x: -x["chg_20d_pct"])
    at_res = [x["symbol"] for x in per_symbol if x["position"] == "sát kháng cự"]
    at_sup = [x["symbol"] for x in per_symbol if x["position"] == "về hỗ trợ"]
    breakout = [x["symbol"] for x in per_symbol
                if x["position"].startswith("vượt đỉnh")]
    overbought = [x["symbol"] for x in per_symbol if x["rsi14"] >= 70]
    oversold = [x["symbol"] for x in per_symbol if x["rsi14"] <= 30]
    return {
        "as_of": str(wide.index[-1].date()),
        "n_symbols": counted,
        "breadth_ma20_pct": round(above_ma20 / counted * 100, 1) if counted else None,
        "breadth_up20d_pct": round(up20 / counted * 100, 1) if counted else None,
        "sr_at_resistance": at_res,
        "sr_at_support": at_sup,
        "sr_breakout": breakout,
        "overbought_rsi70": overbought,
        "oversold_rsi30": oversold,
        "symbols": per_symbol,
        "source": "market.db · bảng price (Crawl Data) — swing pivots + Volume-by-Price",
    }


if __name__ == "__main__":
    db = os.path.join(ROOT, "..", "Crawl Data", "database", "market.db")
    b = board_stats(get_board())
    print("BOARD:", json.dumps({k: v for k, v in b.items() if k != "top_foreign_buy"},
                                ensure_ascii=False)[:600])
    t = technical_snapshot(db)
    print("TECH breadth:", t["breadth_ma20_pct"], "% tren MA20 · as_of", t["as_of"])
    print("top:", json.dumps(t["symbols"][:3], ensure_ascii=False))
