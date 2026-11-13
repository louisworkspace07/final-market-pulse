# -*- coding: utf-8 -*-
"""Kỹ thuật TOÀN THỊ TRƯỜNG — aggregates từ ~700 mã HOSE+HNX (bảng price P6).

Khác technical.py (S/R chi tiết ~33 mã dẫn dắt), module này trả lời câu hỏi
"CẢ THỊ TRƯỜNG đang thế nào" bằng số liệu tổng hợp — thứ AI có thể phân tích
mà không phải kể chuyện từng mã:

- breadth: % mã trên MA20/MA50, số mã tăng/giảm phiên, New High/New Low 52W
- sectors: độ rộng + biến động trung vị + thanh khoản THEO NGÀNH
- indexes: VNINDEX/VN30/HNX thật (bảng market_index, nguồn VNDirect)
- market_news: tin cấp thị trường [M..] (bảng market_news, Google News RSS)
- heatmap: dữ liệu vẽ treemap (symbol, ngành, vốn hóa, %phiên, cờ MA)

Toàn bộ thuần Python/pandas — kiểm chứng được, không AI.
"""
from __future__ import annotations

import os
import sqlite3
import time as _time
from collections import defaultdict

import pandas as pd


def _price_frame(con) -> pd.DataFrame:
    """Khung giá ~1 năm cho mọi mã trong bảng price (P6 đã đổ toàn thị trường)."""
    df = pd.read_sql_query(
        "SELECT symbol, time, close, volume FROM price WHERE time >= (SELECT date(max(time), '-365 day') FROM price) ORDER BY symbol, time", con)
    return df


# _per_symbol_stats(_price_frame(con)) đọc TOÀN bảng price (~189k dòng) + groupby
# pandas ~700 mã → ~10s/lần, lại được heatmap/regime/snapshot gọi độc lập nhiều
# lần (Tổng quan tự làm mới 60s). P6 chỉ cập nhật theo NGÀY nên cache 60s an toàn;
# %phiên LIVE được overlay SAU (từ bảng giá :5555) nên vẫn tươi.
import threading

_STATS_TTL = float(os.environ.get("MP_STATS_TTL_S", "60"))
_stats_cache: dict = {}   # db_path -> {"ts": float, "df": DataFrame}
_stats_lock = threading.Lock()


def _market_stats_cached(con, db_path: str) -> pd.DataFrame:
    """Bản cache TTL của _per_symbol_stats — dùng chung mọi aggregate toàn thị
    trường. Key theo db_path (test dùng DB tạm khác nhau → không lẫn cache).
    DataFrame trả về CHỈ ĐỌC (callers .merge tạo bản mới, không mutate).
    Dùng lock + double-checked caching để tránh nhiều luồng cùng quét bảng 773k dòng."""
    now = _time.time()
    ent = _stats_cache.get(db_path)
    if ent is not None and now - ent["ts"] < _STATS_TTL:
        return ent["df"]
    with _stats_lock:
        now = _time.time()
        ent = _stats_cache.get(db_path)
        if ent is not None and now - ent["ts"] < _STATS_TTL:
            return ent["df"]
        df = _per_symbol_stats(_price_frame(con))
        _stats_cache[db_path] = {"ts": now, "df": df}
        return df


def _per_symbol_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Chỉ báo tối giản cho từng mã: close, %1D, %20D, MA20/50, 52W, KL 5/60.
    Tối ưu hóa: Dùng itertuples + dict thay vì groupby để tránh block GIL 
    do pandas C-extensions, giảm thời gian xử lý từ 12s xuống < 2s."""
    grouped = defaultdict(list)
    for r in df.itertuples(index=False):
        grouped[r.symbol].append(r)
        
    out = []
    for sym, rows in grouped.items():
        n = len(rows)
        if n < 25 or not rows[-1].close:
            continue
            
        last = float(rows[-1].close)
        prev1 = float(rows[-2].close) if n >= 2 and rows[-2].close else None
        prev20 = float(rows[-21].close) if n >= 21 and rows[-21].close else None
        
        closes = [r.close for r in rows]
        vols = [r.volume for r in rows]
        
        ma20 = sum(closes[-20:]) / 20
        ma50 = sum(closes[-50:]) / 50 if n >= 50 else None
        
        win = closes[-252:]
        hi52 = max(win)
        lo52 = min(win)
        
        vol5 = sum(vols[-5:]) / 5 if n >= 5 else None
        vol60 = sum(vols[-60:]) / 60 if n >= 60 else None
        
        out.append({
            "symbol": sym, "close": last,
            "chg_1d": (last / prev1 - 1) * 100 if prev1 else 0.0,
            "chg_20d": (last / prev20 - 1) * 100 if prev20 else None,
            "above_ma20": last > ma20,
            "above_ma50": (last > ma50) if ma50 else None,
            "near_high52": last >= hi52 * 0.98,
            "near_low52": last <= lo52 * 1.02,
            "vol_ratio": round(vol5 / vol60, 2) if vol5 and vol60 else None,
            "last_time": str(rows[-1].time),
        })
    return pd.DataFrame(out)


def _connect_ro(db_path: str) -> sqlite3.Connection:
    """Kết nối SQLite chỉ-đọc (URI mode=ro) an toàn với crawler."""
    try:
        from modules.common.db import connect_readonly
        return connect_readonly(db_path)
    except Exception:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def market_snapshot(db_path: str) -> dict:
    """Bức tranh toàn thị trường: breadth + ngành + chỉ số thật + tin [M..]."""
    con = _connect_ro(db_path)
    try:
        stats = _market_stats_cached(con, db_path)
        sectors = pd.read_sql_query(
            "SELECT symbol, sector, market_cap, exchange FROM companies", con)
        st = stats.merge(sectors, on="symbol", how="left")
        st["sector"] = st["sector"].fillna("Khác")

        as_of = str(st["last_time"].max()) if len(st) else None
        n = len(st)

        breadth = {
            "n_symbols": n, "as_of": as_of,
            "pct_above_ma20": round(st["above_ma20"].mean() * 100, 1) if n else None,
            "pct_above_ma50": round(st["above_ma50"].dropna().mean() * 100, 1) if n else None,
            "n_up_1d": int((st["chg_1d"] > 0.1).sum()),
            "n_down_1d": int((st["chg_1d"] < -0.1).sum()),
            "new_high_52w": int(st["near_high52"].sum()),
            "new_low_52w": int(st["near_low52"].sum()),
        }

        # ---- theo ngành (chỉ ngành có >= 5 mã cho đỡ nhiễu)
        sec_rows = []
        for sec, g in st.groupby("sector"):
            if len(g) < 5:
                continue
            sec_rows.append({
                "sector": sec, "n": len(g),
                "pct_above_ma20": round(g["above_ma20"].mean() * 100, 1),
                "median_chg_1d": round(float(g["chg_1d"].median()), 2),
                "median_chg_20d": round(float(g["chg_20d"].dropna().median()), 2)
                if g["chg_20d"].notna().any() else None,
                "n_near_high": int(g["near_high52"].sum()),
                "n_near_low": int(g["near_low52"].sum()),
            })
        sec_rows.sort(key=lambda r: -(r["median_chg_1d"] or 0))

        # ---- chỉ số thật (market_index — P7)
        indexes = {}
        try:
            idx = pd.read_sql_query(
                "SELECT code, time, close, value FROM market_index ORDER BY code, time", con)
            for code, g in idx.groupby("code"):
                g = g.reset_index(drop=True)
                c = g["close"]
                if len(c) < 2:
                    continue
                last = float(c.iloc[-1])
                val = g["value"]
                liq20 = float(val.tail(20).mean()) if len(val) >= 20 else None
                # YTD: phiên đầu tiên của năm hiện tại (fallback phiên đầu chuỗi)
                year = str(g["time"].iloc[-1])[:4]
                ytd_base = g.loc[g["time"].str.startswith(year), "close"]
                base = float(ytd_base.iloc[0]) if len(ytd_base) else float(c.iloc[0])
                indexes[code] = {
                    "close": last, "as_of": str(g["time"].iloc[-1]),
                    "pct_1d": round((last / float(c.iloc[-2]) - 1) * 100, 2),
                    "pct_5d": round((last / float(c.iloc[-6]) - 1) * 100, 2) if len(c) >= 6 else None,
                    "pct_ytd": round((last / base - 1) * 100, 2) if base else None,
                    "liquidity_last_bn": round(float(val.iloc[-1]) / 1e9, 0) if pd.notna(val.iloc[-1]) else None,
                    "liquidity_avg20_bn": round(liq20 / 1e9, 0) if liq20 else None,
                }
        except Exception:
            pass

        # ---- tin cấp thị trường [M..]
        market_news = []
        try:
            rows = con.execute(
                "SELECT title, source, link, public_date FROM market_news "
                "ORDER BY public_date DESC LIMIT 12").fetchall()
            market_news = [{"id": f"M{i+1}", "title": r[0], "press": r[1],
                            "link": r[2], "date": (r[3] or "")[:10]}
                           for i, r in enumerate(rows)]
        except Exception:
            pass

        return {"available": n > 0, "breadth": breadth, "sectors": sec_rows,
                "indexes": indexes, "market_news": market_news,
                "coverage": {"n_symbols": n, "exchanges": "HOSE+HNX",
                             "as_of": as_of}}
    finally:
        con.close()


def heatmap_data(db_path: str, board_rows: list[dict] | None = None) -> dict:
    """Dữ liệu treemap: mỗi mã {symbol, sector, cap, chg_pct, above_ma20}.

    %phiên ưu tiên bảng giá LIVE (board_rows từ Test tool); fallback %1D từ
    lịch sử. Vốn hóa từ companies.market_cap (None → ước bằng thanh khoản).
    """
    con = _connect_ro(db_path)
    try:
        stats = _market_stats_cached(con, db_path)
        sectors = pd.read_sql_query(
            "SELECT symbol, sector, market_cap FROM companies", con)
    finally:
        con.close()
    st = stats.merge(sectors, on="symbol", how="left")
    st["sector"] = st["sector"].fillna("Khác")

    live = {}
    if board_rows:
        for r in board_rows:
            sym, mp, ref = r.get("symbol"), r.get("matchPrice"), r.get("ref")
            if sym and mp and ref:
                live[sym] = (mp - ref) / ref * 100

    items = []
    for _, r in st.iterrows():
        cap = r.get("market_cap")
        items.append({
            "symbol": r["symbol"], "sector": r["sector"],
            "cap": float(cap) if pd.notna(cap) and cap else None,
            "chg_pct": round(live.get(r["symbol"], r["chg_1d"]), 2),
            "live": r["symbol"] in live,
            "above_ma20": bool(r["above_ma20"]),
            "near_high52": bool(r["near_high52"]),
            "near_low52": bool(r["near_low52"]),
        })
    # cap thiếu → gán trung vị ngành để ô không biến mất khỏi treemap
    med = {}
    for it in items:
        if it["cap"]:
            med.setdefault(it["sector"], []).append(it["cap"])
    med = {k: sorted(v)[len(v) // 2] for k, v in med.items() if v}
    fallback = sorted(med.values())[len(med) // 2] if med else 1e12
    for it in items:
        if not it["cap"]:
            it["cap"] = med.get(it["sector"], fallback) * 0.3
    return {"items": items, "n_live": len(live),
            "as_of": str(st["last_time"].max()) if len(st) else None}


def _vnindex_series(con) -> pd.Series:
    """Chuỗi close VNINDEX thật (market_index). Rỗng nếu chưa crawl P7."""
    try:
        df = pd.read_sql_query(
            "SELECT time, close, value FROM market_index WHERE code='VNINDEX' "
            "ORDER BY time", con)
        if len(df) < 2:
            return pd.DataFrame()
        return df.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def compute_regime(db_path: str) -> dict:
    """Chế độ thị trường từ 5 tín hiệu, mỗi tín hiệu ±1 điểm — MINH BẠCH.

    Tín hiệu (đều tính từ dữ liệu đã crawl, không AI, không dự phóng):
      1. VNINDEX > MA50
      2. VNINDEX > MA200
      3. Độ rộng: %mã > MA50 ≥ 50%
      4. New High − New Low (52W) > 0
      5. Thanh khoản 20 phiên tăng so 20 phiên trước

    Tổng điểm [-5..+5] → nhãn: ≥4 Uptrend · 2-3 Phục hồi · -1..1 Sideways ·
    -3..-2 Suy yếu · ≤-4 Downtrend. Trả kèm bảng tín hiệu con đạt/không.
    """
    con = _connect_ro(db_path)
    try:
        idx = _vnindex_series(con)
        stats = _market_stats_cached(con, db_path)
    finally:
        con.close()

    signals = []

    def add(name, ok, detail):
        signals.append({"ten": name, "dat": bool(ok) if ok is not None else None,
                        "chi_tiet": detail})

    # --- tín hiệu 1-2 & 5: từ VNINDEX thật
    if len(idx):
        c = idx["close"].astype(float)
        last = float(c.iloc[-1])
        ma50 = float(c.tail(50).mean()) if len(c) >= 50 else None
        ma200 = float(c.tail(200).mean()) if len(c) >= 200 else None
        add("VNINDEX > MA50", (last > ma50) if ma50 else None,
            f"{last:.1f} vs MA50 {ma50:.1f}" if ma50 else "thiếu dữ liệu 50 phiên")
        add("VNINDEX > MA200", (last > ma200) if ma200 else None,
            f"{last:.1f} vs MA200 {ma200:.1f}" if ma200 else "thiếu dữ liệu 200 phiên")
        val = idx["value"].astype(float)
        if len(val) >= 40:
            liq_now = float(val.tail(20).mean())
            liq_prev = float(val.iloc[-40:-20].mean())
            add("Thanh khoản 20 phiên tăng", liq_now > liq_prev,
                f"TB20 {liq_now/1e9:.0f} tỷ vs 20 phiên trước {liq_prev/1e9:.0f} tỷ")
        else:
            add("Thanh khoản 20 phiên tăng", None, "thiếu dữ liệu 40 phiên")
    else:
        add("VNINDEX > MA50", None, "chưa có market_index (chạy P7)")
        add("VNINDEX > MA200", None, "chưa có market_index (chạy P7)")
        add("Thanh khoản 20 phiên tăng", None, "chưa có market_index (chạy P7)")

    # --- tín hiệu 3-4: độ rộng toàn thị trường
    n = len(stats)
    if n:
        pct_ma50 = stats["above_ma50"].dropna().mean() * 100 if stats["above_ma50"].notna().any() else None
        add("Độ rộng %>MA50 ≥ 50%", (pct_ma50 >= 50) if pct_ma50 is not None else None,
            f"{pct_ma50:.1f}% mã trên MA50" if pct_ma50 is not None else "thiếu dữ liệu MA50")
        nh, nl = int(stats["near_high52"].sum()), int(stats["near_low52"].sum())
        add("New High − New Low > 0", nh - nl > 0,
            f"{nh} sát đỉnh / {nl} sát đáy 52W (chênh {nh - nl:+d})")
    else:
        add("Độ rộng %>MA50 ≥ 50%", None, "chưa có bảng giá")
        add("New High − New Low > 0", None, "chưa có bảng giá")

    score = sum(1 if s["dat"] else -1 for s in signals if s["dat"] is not None)
    n_valid = sum(1 for s in signals if s["dat"] is not None)
    if score >= 4:
        label = "Uptrend"
    elif score >= 2:
        label = "Phục hồi"
    elif score >= -1:
        label = "Sideways"
    elif score >= -3:
        label = "Suy yếu"
    else:
        label = "Downtrend"

    return {"available": n_valid > 0, "label": label, "score": score,
            "max_score": n_valid, "signals": signals,
            "note": "Nhãn tổng hợp từ 5 tín hiệu định lượng, không phải dự báo."}


def sector_rotation(db_path: str, weeks: int = 12) -> dict:
    """Sức mạnh tương đối (RS) theo ngành, chuỗi ~`weeks` tuần.

    RS ngành tại tuần t = trung vị return 20 phiên của các mã trong ngành
    − return 20 phiên VNINDEX cùng mốc. Dương = ngành khỏe hơn thị trường.
    Trả chuỗi để UI vẽ line đa ngành (dữ liệu bảng price + market_index).
    """
    con = _connect_ro(db_path)
    try:
        px = pd.read_sql_query(
            "SELECT symbol, time, close FROM price WHERE time >= (SELECT date(max(time), '-180 day') FROM price) ORDER BY symbol, time", con)
        secs = pd.read_sql_query("SELECT symbol, sector FROM companies", con)
        idx = _vnindex_series(con)
    finally:
        con.close()
    if not len(px) or not len(idx):
        return {"available": False, "series": [], "weeks": []}

    secs_dict = {r.symbol: r.sector for r in secs.itertuples(index=False)}
    
    idx_close = {}
    for r in idx.itertuples(index=False):
        if r.close:
            idx_close[r.time] = float(r.close)
            
    times = sorted(idx_close.keys())
    if len(times) < 25:
        return {"available": False, "series": [], "weeks": []}
        
    anchors = times[-1::-5][::-1]
    anchors = [t for t in anchors if times.index(t) >= 20][-weeks:]
    if not anchors:
        return {"available": False, "series": [], "weeks": []}
        
    prev_map = {t: times[times.index(t) - 20] for t in anchors}
    
    def get_ret20(d, t):
        curr = d.get(t)
        prev = d.get(prev_map.get(t))
        if curr and prev:
            return (curr / prev - 1) * 100
        return None

    idx_ret = {t: get_ret20(idx_close, t) for t in anchors}
    
    by_sym = defaultdict(dict)
    for r in px.itertuples(index=False):
        if r.close:
            by_sym[r.symbol][r.time] = float(r.close)
            
    sec_to_syms = defaultdict(list)
    for sym in by_sym.keys():
        sec = secs_dict.get(sym)
        if not sec or pd.isna(sec):
            sec = "Khác"
        sec_to_syms[sec].append(sym)
        
    rows = []
    for sec, syms in sec_to_syms.items():
        if len(syms) < 5:
            continue
            
        per_time = defaultdict(list)
        for sym in syms:
            d = by_sym[sym]
            for t in anchors:
                r = get_ret20(d, t)
                if r is not None:
                    per_time[t].append(r)
                    
        series = []
        for t in anchors:
            vals = per_time.get(t)
            base = idx_ret.get(t)
            if vals and base is not None:
                med = sorted(vals)[len(vals) // 2]
                series.append(round(float(med) - float(base), 2))
            else:
                series.append(None)
                
        if any(v is not None for v in series):
            rs_last = next((v for v in reversed(series) if v is not None), None)
            rows.append({"sector": sec, "rs": series, "rs_last": rs_last})
            
    rows.sort(key=lambda r: -(abs(r["rs_last"]) if r["rs_last"] is not None else 0))
    return {"available": bool(rows), "weeks": [str(t)[:10] for t in anchors],
            "series": rows}


def liquidity_concentration(db_path: str, board_rows: list[dict] | None = None) -> dict:
    """Mức độ tập trung thanh khoản — % GTGD top-10 mã / toàn thị trường.

    Ưu tiên bảng LIVE (board_rows: matchPrice×totalVol); fallback close×volume
    phiên gần nhất từ bảng price. Cao = "xanh vỏ đỏ lòng" (tiền dồn ít mã).
    """
    turnover = {}
    if board_rows:
        for r in board_rows:
            sym = r.get("symbol")
            mp, vol = r.get("matchPrice"), r.get("totalVol") or r.get("totalVolume")
            if sym and mp and vol:
                turnover[sym] = float(mp) * float(vol)
    if not turnover:
        con = _connect_ro(db_path)
        try:
            # Dùng Window Function lấy phiên gần nhất của từng mã, tránh nạp 752k dòng vào pandas
            rows = con.execute("""
                WITH ranked AS (
                    SELECT symbol, close, volume,
                           ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY time DESC) as rn
                    FROM price
                    WHERE close IS NOT NULL AND volume IS NOT NULL
                )
                SELECT symbol, close, volume FROM ranked WHERE rn = 1
            """).fetchall()
            for sym, close, volume in rows:
                if close and volume:
                    turnover[sym] = float(close) * float(volume)
        finally:
            con.close()
                
    if not turnover:
        return {"available": False}

    total = sum(turnover.values())
    top = sorted(turnover.items(), key=lambda kv: -kv[1])[:10]
    top10_val = sum(v for _, v in top)
    # HHI (0..10000) trên toàn thị trường — độ tập trung tổng thể
    hhi = sum((v / total * 100) ** 2 for v in turnover.values()) if total else 0
    return {"available": True,
            "top10_pct": round(top10_val / total * 100, 1) if total else None,
            "hhi": round(hhi, 0),
            "n_symbols": len(turnover),
            "top10": [{"symbol": s, "pct": round(v / total * 100, 2)} for s, v in top],
            "live": bool(board_rows) and bool(turnover),
            "note": "% giá trị giao dịch top-10 mã trên toàn thị trường; cao = tiền dồn vào ít mã."}


if __name__ == "__main__":
    import json, os
    db = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                       "data-crawler", "database", "market.db"))
    snap = market_snapshot(db)
    print(json.dumps({k: snap[k] for k in ("breadth", "coverage", "indexes")},
                     ensure_ascii=False, indent=1))
    print("sectors:", len(snap["sectors"]), "| news:", len(snap["market_news"]))
