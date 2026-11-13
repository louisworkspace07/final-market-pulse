"""Ảnh 11 · Bộ chỉ báo kỹ thuật ĐẦY ĐỦ cho mọi mã — tính từ market.db.

Vì sao không gọi Test tool :5555 như plan gốc: service đó thường TẮT (bảng giá chỉ
mở trong phiên), mà bảng `price` trong market.db đã có đủ OHLCV theo ngày cho
1.541 mã (≥60 phiên). Chỉ báo ngày (S/R, RSI, MA, VBP, 52 tuần) chỉ cần dữ liệu
ngày → tính tại chỗ, bỏ hẳn phụ thuộc service ngoài. Giá khớp trong phiên vẫn lấy
từ bảng giá qua /api/live khi cần vị trí hiện tại.

TRUNG THỰC: mã không đủ lịch sử KHÔNG được bịa số — trả vào `skipped` kèm lý do,
UI hiện tooltip theo pattern "đủ chỗ, ghi rõ lý do" (B14).
"""
from __future__ import annotations

import os
import sqlite3
import time

import numpy as np
import pandas as pd

MIN_BARS = 60                    # dưới ngưỡng này coi như chưa đủ lịch sử
_CACHE_TTL = float(os.environ.get("MP_TECHFULL_TTL_S", "300"))
_cache: dict = {"ts": 0.0, "key": None, "data": None}


def _rsi(closes: np.ndarray, period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    d = np.diff(closes)
    gain = np.where(d > 0, d, 0.0)
    loss = np.where(d < 0, -d, 0.0)
    # Wilder smoothing
    ag, al = gain[:period].mean(), loss[:period].mean()
    for i in range(period, len(d)):
        ag = (ag * (period - 1) + gain[i]) / period
        al = (al * (period - 1) + loss[i]) / period
    if al == 0:
        return 100.0
    rs = ag / al
    return float(round(100 - 100 / (1 + rs), 1))


def _pivots(high: np.ndarray, low: np.ndarray, close: float, k: int = 3):
    """Kháng cự/hỗ trợ = các đỉnh/đáy cục bộ (fractal k nến mỗi bên), gom sát nhau.

    Đây là cách đọc S/R phổ thông nhất và giải thích được cho người dùng: 'vùng giá
    thị trường đã nhiều lần quay đầu', chứ không phải con số mô hình hộp đen.
    """
    res, sup = [], []
    n = len(high)
    for i in range(k, n - k):
        if high[i] == max(high[i - k:i + k + 1]):
            res.append(float(high[i]))
        if low[i] == min(low[i - k:i + k + 1]):
            sup.append(float(low[i]))

    def _cluster(levels, above: bool):
        """Gom mức cách nhau <1.5% thành 1 vùng, chỉ giữ phía trên/dưới giá hiện tại."""
        sel = sorted({round(x, 2) for x in levels if (x > close if above else x < close)})
        if not sel:
            return []
        out, cur = [], [sel[0]]
        for x in sel[1:]:
            if abs(x - cur[-1]) / max(cur[-1], 1e-9) < 0.015:
                cur.append(x)
            else:
                out.append(sum(cur) / len(cur))
                cur = [x]
        out.append(sum(cur) / len(cur))
        # gần giá hiện tại trước
        out.sort(key=lambda x: abs(x - close))
        return [round(x, 2) for x in out[:3]]

    return _cluster(sup, above=False), _cluster(res, above=True)


def _vbp(close: np.ndarray, vol: np.ndarray, bins: int = 20, top: int = 2):
    """Volume-by-price: vùng giá tích tụ khối lượng lớn nhất (hỗ trợ/kháng cự mềm)."""
    if len(close) < 20 or vol.sum() <= 0:
        return []
    lo, hi = float(close.min()), float(close.max())
    if hi <= lo:
        return []
    idx = np.clip(((close - lo) / (hi - lo) * bins).astype(int), 0, bins - 1)
    agg = np.zeros(bins)
    for i, v in zip(idx, vol):
        agg[i] += v
    order = np.argsort(agg)[::-1][:top]
    step = (hi - lo) / bins
    return [round(float(lo + (b + 0.5) * step), 2) for b in order]


def _one(sym: str, c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> dict:
    last = float(c[-1])

    ma20 = float(c[-20:].mean())
    ma50 = float(c[-50:].mean()) if len(c) >= 50 else None
    sup, res = _pivots(h, l, last)
    hi52, lo52 = float(h[-260:].max()), float(l[-260:].min())
    vol20 = float(v[-20:].mean()) if v[-20:].sum() > 0 else None

    # nhãn vị trí: gần kháng cự / về hỗ trợ / vượt đỉnh / giữa vùng
    near_res = res and abs(res[0] - last) / last <= 0.03
    near_sup = sup and abs(last - sup[0]) / last <= 0.03
    if not res and last >= hi52 * 0.995:
        pos = "breakout"
    elif near_res:
        pos = "near_res"
    elif near_sup:
        pos = "near_sup"
    else:
        pos = "mid"

    return {
        "symbol": sym, "price": round(last, 2), "bars": int(len(c)),
        "sr": {"support": sup, "resistance": res},
        "vbp": _vbp(c, v),
        "rsi14": _rsi(c),
        "ma20": round(ma20, 2), "ma50": round(ma50, 2) if ma50 else None,
        "above_ma20": bool(last > ma20),
        "vol_vs_20": round(float(v[-1] / vol20), 2) if vol20 else None,
        "hi52": round(hi52, 2), "lo52": round(lo52, 2),
        "pct_from_hi52": round((last / hi52 - 1) * 100, 1) if hi52 else None,
        "pct_from_lo52": round((last / lo52 - 1) * 100, 1) if lo52 else None,
        "pos": pos,
    }


def build(db_path: str) -> dict:
    """Tính cho toàn bộ mã có giá. Cache theo mtime của DB + TTL."""
    try:
        key = os.path.getmtime(db_path)
    except OSError:
        key = None
    now = time.time()
    if (_cache["data"] is not None and _cache["key"] == key
            and now - _cache["ts"] < _CACHE_TTL):
        return _cache["data"]

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        df = pd.read_sql_query(
            "SELECT symbol, time, high, low, close, volume FROM price "
            "WHERE close IS NOT NULL ORDER BY symbol, time", con)
    finally:
        con.close()

    items, skipped = {}, {}
    from collections import defaultdict
    by_sym = defaultdict(lambda: {"close": [], "high": [], "low": [], "volume": []})
    
    for r in df.itertuples(index=False):
        d = by_sym[r.symbol]
        d["close"].append(r.close)
        d["high"].append(r.high)
        d["low"].append(r.low)
        d["volume"].append(r.volume if r.volume is not None and pd.notna(r.volume) else 0.0)

    for sym, d in by_sym.items():
        if len(d["close"]) < MIN_BARS:
            skipped[sym] = f"mới niêm yết / thiếu lịch sử ({len(d['close'])} phiên < {MIN_BARS})"
            continue
            
        c = np.array(d["close"], dtype=float)
        h = np.array(d["high"], dtype=float)
        l = np.array(d["low"], dtype=float)
        v = np.array(d["volume"], dtype=float)
        
        if np.isnan(h).any() or np.isnan(l).any():
            skipped[sym] = "thiếu giá cao/thấp trong lịch sử"
            continue
            
        try:
            items[sym] = _one(sym, c, h, l, v)
        except Exception as e:                       # 1 mã hỏng không phá cả bộ
            skipped[sym] = f"lỗi tính toán: {str(e)[:60]}"

    out = {
        "as_of": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "market.db · price (OHLCV ngày)",
        "n_items": len(items), "n_skipped": len(skipped),
        "min_bars": MIN_BARS,
        "items": items, "skipped": skipped,
    }
    _cache.update({"ts": now, "key": key, "data": out})
    return out


def one(db_path: str, symbol: str) -> dict | None:
    """Chỉ báo của 1 mã (dùng cho trang cổ phiếu §18).

    Tối ưu hóa P0 (BN-07): Thay vì nạp toàn bộ 752k dòng của 1.541 mã qua build(),
    ưu tiên đọc từ cache nếu đã sẵn sàng; nếu chưa, thực hiện truy vấn riêng biệt
    giới hạn 260 nến gần nhất của mã đó.
    """
    sym = symbol.upper().strip()
    now = time.time()

    # 1. Fast path: Nếu cache toàn thị trường đã sẵn sàng và còn tươi (TTL 300s), dùng luôn
    if _cache["data"] is not None and now - _cache["ts"] < _CACHE_TTL:
        full = _cache["data"]
        if sym in full.get("items", {}):
            return full["items"][sym]
        if sym in full.get("skipped", {}):
            return {"symbol": sym, "skipped": full["skipped"][sym]}
        return None

    # 2. Dedicated single-symbol query (phản hồi trong < 5ms thay vì 13s)
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = con.execute(
            "SELECT high, low, close, volume FROM price "
            "WHERE symbol = ? AND close IS NOT NULL "
            "ORDER BY time DESC LIMIT 260",
            (sym,)
        )
        rows = cur.fetchall()
    finally:
        con.close()

    if not rows:
        return None

    # SQLite trả về thứ tự thời gian giảm dần; đảo ngược để đúng thứ tự thời gian tăng dần
    rows.reverse()
    n_bars = len(rows)
    if n_bars < MIN_BARS:
        return {"symbol": sym, "skipped": f"mới niêm yết / thiếu lịch sử ({n_bars} phiên < {MIN_BARS})"}

    highs = np.array([r[0] for r in rows], dtype=float)
    lows = np.array([r[1] for r in rows], dtype=float)
    closes = np.array([r[2] for r in rows], dtype=float)
    volumes = np.array([r[3] if r[3] is not None and pd.notna(r[3]) else 0.0 for r in rows], dtype=float)

    if np.isnan(highs).any() or np.isnan(lows).any():
        return {"symbol": sym, "skipped": "thiếu giá cao/thấp trong lịch sử"}

    try:
        return _one(sym, closes, highs, lows, volumes)
    except Exception as e:
        return {"symbol": sym, "skipped": f"lỗi tính toán: {str(e)[:60]}"}
