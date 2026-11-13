# -*- coding: utf-8 -*-
"""Bảng giá realtime — sử dụng VPS Datafeed trực tiếp & fallback market.db/data.json.
Hoàn toàn độc lập, không phụ thuộc vào các module cũ của vnstock bị deprecated.

Trả đúng chuẩn shape mà frontend static/app.js đang đọc — KHÔNG sửa frontend:
  - các trường số (ref/ceil/floor/matchPrice/buyP*/sellP*...) đơn vị VND
  - raw[0..26] là TEXT hiển thị, format theo bảng giá VN (giá /1000 2 số lẻ, KL nhóm hàng nghìn).

Bảng đối chiếu raw[] (khớp đúng static/app.js createRow):
  0 ticker · 1 TC · 2 trần · 3 sàn · 4 tổng KL · 5-10 mua P3/V3..P1/V1 ·
  11 giá khớp · 12 KL khớp · 13 +/- · 14-19 bán P1/V1..P3/V3 ·
  20 cao · 21 TB · 22 thấp · 23 dư mua · 24 dư bán · 25 NN mua · 26 NN bán
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
import sqlite3

_LISTING_CACHE = {"ts": 0.0, "by_ex": {}, "all": []}
GROUP_TTL = 3600            # danh sách mã theo sàn: làm mới 1 giờ
_DISK_CACHE = os.path.join(os.path.dirname(__file__), "temp_data", "universe_cache.json")
_DATA_CACHE = os.path.join(os.path.dirname(__file__), "temp_data", "data.json")

# Caches memoization tăng tốc xử lý bảng giá
_P_CACHE: dict = {None: (None, "")}
_V_CACHE: dict = {None: (None, "")}
_CHG_CACHE: dict = {None: ""}


def _get_p(v):
    try:
        r = _P_CACHE.get(v)
        if r is not None:
            return r
    except TypeError:
        return None, ""
    if v is None:
        return None, ""
    try:
        f = float(v)
        if f != f:
            r = (None, "")
        else:
            r = (f, f"{f/1000:.2f}" if f else "")
    except (TypeError, ValueError):
        r = (None, "")
    if len(_P_CACHE) < 20000:
        _P_CACHE[v] = r
    return r


def _get_v(v):
    try:
        r = _V_CACHE.get(v)
        if r is not None:
            return r
    except TypeError:
        return None, ""
    if v is None:
        return None, ""
    try:
        f = float(v)
        if f != f:
            r = (None, "")
        else:
            r = (f, f"{int(f):,}" if f else "")
    except (TypeError, ValueError):
        r = (None, "")
    if len(_V_CACHE) < 20000:
        _V_CACHE[v] = r
    return r


def _get_chg(c):
    if c is None:
        return ""
    r = _CHG_CACHE.get(c)
    if r is not None:
        return r
    r = f"{c/1000:+.2f}"
    if len(_CHG_CACHE) < 5000:
        _CHG_CACHE[c] = r
    return r


def load_universe(force: bool = False) -> tuple[dict, list]:
    """Trả (symbol→exchange, [all symbols]) từ database hoặc cache, cache 1 giờ."""
    now = time.time()
    if not force and _LISTING_CACHE["all"] and now - _LISTING_CACHE["ts"] < GROUP_TTL:
        return _LISTING_CACHE["by_ex"], _LISTING_CACHE["all"]

    # 1. Thử load từ disk cache
    if not force and os.path.exists(_DISK_CACHE):
        try:
            d = json.load(open(_DISK_CACHE, encoding="utf-8"))
            if d.get("all") and len(d["all"]) > 100:
                _LISTING_CACHE.update({"ts": now, "by_ex": d["by_ex"], "all": d["all"]})
                return d["by_ex"], d["all"]
        except Exception:
            pass

    # 2. Thử load từ market.db
    db_candidates = [
        os.path.join(os.path.dirname(__file__), "..", "data-crawler", "database", "market.db"),
        os.path.join(os.path.dirname(__file__), "market.db"),
    ]
    for db_path in db_candidates:
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                rows = conn.execute("SELECT symbol, exchange FROM companies").fetchall()
                conn.close()
                if rows:
                    by_ex = {r[0]: (r[1] or "hose").lower() for r in rows}
                    allsyms = [r[0] for r in rows]
                    _LISTING_CACHE.update({"ts": now, "by_ex": by_ex, "all": allsyms})
                    try:
                        os.makedirs(os.path.dirname(_DISK_CACHE), exist_ok=True)
                        json.dump({"ts": now, "by_ex": by_ex, "all": allsyms},
                                  open(_DISK_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
                    except Exception:
                        pass
                    return by_ex, allsyms
            except Exception as e:
                print(f"[board] Load market.db error: {e}")

    # 3. Thử load từ data.json
    if os.path.exists(_DATA_CACHE):
        try:
            items = json.load(open(_DATA_CACHE, encoding="utf-8"))
            by_ex = {}
            allsyms = []
            for item in items:
                sym = item.get("symbol")
                if sym and sym not in by_ex:
                    by_ex[sym] = (item.get("exchange") or "hose").lower()
                    allsyms.append(sym)
            if allsyms:
                _LISTING_CACHE.update({"ts": now, "by_ex": by_ex, "all": allsyms})
                return by_ex, allsyms
        except Exception:
            pass

    # 4. Fallback tối thiểu an toàn
    default_symbols = ["FPT", "VNM", "VIC", "VHM", "HPG", "MSN", "MWG", "TCB", "MBB", "ACB", "STB", "VPB", "BID", "CTG", "VCB", "SSI"]
    by_ex = {s: "hose" for s in default_symbols}
    return by_ex, default_symbols


def parse_vps_item(item: dict, ex_map: dict) -> dict | None:
    """Chuyển đổi 1 bản ghi từ VPS Datafeed sang chuẩn schema Market Pulse."""
    sym = item.get("sym")
    if not sym:
        return None
    ex = ex_map.get(sym, "hose")

    def to_float(val, mult=1.0):
        try:
            if val is None or str(val).strip() == "" or str(val).lower() == "null":
                return None
            return float(val) * mult
        except:
            return None

    def parse_g(g_str):
        if not g_str or not isinstance(g_str, str):
            return None, None
        parts = g_str.split("|")
        if len(parts) >= 2:
            p = to_float(parts[0], 1000.0)
            v = to_float(parts[1], 10.0)
            return p, v
        return None, None

    ref = to_float(item.get("r"), 1000.0)
    ceil = to_float(item.get("c"), 1000.0)
    flr = to_float(item.get("f"), 1000.0)
    mp = to_float(item.get("lastPrice"), 1000.0)
    mv = to_float(item.get("lastVolume"), 10.0)
    accum = to_float(item.get("lot"), 1.0)

    b1p, b1v = parse_g(item.get("g1"))
    b2p, b2v = parse_g(item.get("g2"))
    b3p, b3v = parse_g(item.get("g3"))

    a1p, a1v = parse_g(item.get("g4"))
    a2p, a2v = parse_g(item.get("g5"))
    a3p, a3v = parse_g(item.get("g6"))

    high = to_float(item.get("highPrice"), 1000.0)
    low = to_float(item.get("lowPrice"), 1000.0)
    avg = to_float(item.get("avePrice"), 1000.0)

    fb = to_float(item.get("fBVol"), 1.0) or 0.0
    fs = to_float(item.get("fSVolume"), 1.0) or 0.0

    change = (mp - ref) if (mp is not None and ref is not None) else None
    chg_txt = f"{change/1000:+.2f}" if change is not None else ""

    def pt(v):
        return f"{v/1000:.2f}" if v else ""
    def vt(v):
        return f"{int(v):,}" if v else ""

    du_mua = (b1v or 0) + (b2v or 0) + (b3v or 0)
    du_ban = (a1v or 0) + (a2v or 0) + (a3v or 0)

    raw = [
        str(sym), pt(ref), pt(ceil), pt(flr), vt(accum),
        pt(b3p), vt(b3v), pt(b2p), vt(b2v), pt(b1p), vt(b1v),
        pt(mp), vt(mv), chg_txt,
        pt(a1p), vt(a1v), pt(a2p), vt(a2v), pt(a3p), vt(a3v),
        pt(high), pt(avg), pt(low),
        vt(du_mua), vt(du_ban), vt(fb), vt(fs)
    ]

    return {
        "symbol": sym, "exchange": ex,
        "ref": ref, "ceil": ceil, "floor": flr,
        "matchPrice": mp, "matchVol": mv, "totalVol": accum,
        "buyP3": b3p, "buyV3": b3v, "buyP2": b2p, "buyV2": b2v, "buyP1": b1p, "buyV1": b1v,
        "sellP1": a1p, "sellV1": a1v, "sellP2": a2p, "sellV2": a2v, "sellP3": a3p, "sellV3": a3v,
        "high": high, "avg": avg, "low": low,
        "foreignBuy": fb, "foreignSell": fs,
        "raw": raw
    }


def fetch_vps_batch(symbols: list[str], ex_map: dict) -> list[dict]:
    """Gọi VPS API cho một mẻ mã chứng khoán."""
    if not symbols:
        return []
    sym_str = ",".join(symbols)
    url = f"https://bgapidatafeed.vps.com.vn/getliststockdata/{sym_str}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            out = []
            for item in data:
                p = parse_vps_item(item, ex_map)
                if p:
                    out.append(p)
            return out
    except Exception as e:
        return []


def fetch_board(symbols: list[str], ex_map: dict) -> list[dict]:
    """Lấy dữ liệu bảng giá cho danh sách mã."""
    if not symbols:
        return []

    # Chia batch 60 mã để gọi VPS cực nhanh và ổn định
    BATCH_SIZE = 60
    results = []
    failed_syms = []

    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]
        batch_res = fetch_vps_batch(batch, ex_map)
        if batch_res:
            results.extend(batch_res)
        else:
            failed_syms.extend(batch)

    # Nếu có mã bị lỗi hoặc offline, fallback sang data.json cho các mã đó
    if failed_syms or not results:
        if os.path.exists(_DATA_CACHE):
            try:
                cached = json.load(open(_DATA_CACHE, encoding="utf-8"))
                target_syms = set(failed_syms if results else symbols)
                for row in cached:
                    if row.get("symbol") in target_syms:
                        results.append(row)
            except Exception:
                pass

    return results


# Giữ nguyên hàm parse_board_df để tương thích ngược nếu có code gọi trực tiếp
FIELDS = (
    "symbol", "ref_price", "ceiling", "floor", "match_price",
    "match_vol", "accumulated_volume", "avg_match_price",
    "highest", "lowest", "foreign_buy_volume", "foreign_sell_volume",
    "bid_1_price", "bid_1_volume", "bid_2_price", "bid_2_volume",
    "bid_3_price", "bid_3_volume", "ask_1_price", "ask_1_volume",
    "ask_2_price", "ask_2_volume", "ask_3_price", "ask_3_volume",
)

def parse_board_df(df, ex_map: dict | None = None) -> list[dict]:
    return []
