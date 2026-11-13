"""So sánh ngang ngành (peer comparison).

Tính trung vị các chỉ số định giá/hiệu quả của các công ty cùng ngành (sector)
đã có dữ liệu, để đặt doanh nghiệp trong bối cảnh ngành thay vì đánh giá cô lập.
"""
from __future__ import annotations

import re
import statistics

from . import raw_ratios

RATIO_ITEMS = {
    "pe": "pe_ratio", "pb": "pb_ratio", "roe": "roe",
    "net_margin": "net_margin", "debt_to_equity": "debt_to_equity",
}

# Chỉ số suy ra được TRỰC TIẾP từ báo cáo gốc (không cần giá thị trường) → có
# fallback raw khi bảng `ratio` thiếu. P/E, P/B cần giá + số cp nên KHÔNG raw-derive
# ở đây (giữ nguyên ratio-only). Ánh xạ key peer → đường dẫn trong raw_ratios.compute.
_RAW_PATH = {
    "roe": ("profitability", "roe"),          # đã là % (đã *100)
    "net_margin": ("margins", "net"),          # đã là %
    "debt_to_equity": ("solvency", "debt_to_equity"),  # số lần
}

# period trong DB là chuỗi: "2024" (năm) hoặc "2024-Q1" (quý). Không có cột
# period_type riêng → phân loại bằng chính định dạng chuỗi.
_QUARTER_RE = re.compile(r"^(\d{4})\D+([1-4])")   # "2024-Q1", "2024Q1", "2024-1"...
_YEAR_RE = re.compile(r"^(\d{4})\s*$")


def _period_kind(period: str) -> str | None:
    """Trả 'year' | 'quarter' | None (không nhận diện được)."""
    p = str(period).strip()
    if _YEAR_RE.match(p):
        return "year"
    if _QUARTER_RE.match(p):
        return "quarter"
    return None


def _period_key(period: str) -> int:
    """Khóa sắp xếp dạng SỐ (tránh so sánh chuỗi làm trộn kỳ).

    Năm  -> year (vd 2024)
    Quý  -> year*10 + quý (vd 2024-Q3 -> 20243) để mới nhất là lớn nhất."""
    p = str(period).strip()
    mq = _QUARTER_RE.match(p)
    if mq:
        return int(mq.group(1)) * 10 + int(mq.group(2))
    my = _YEAR_RE.match(p)
    if my:
        return int(my.group(1))
    return -1


import time

_SECTOR_CACHE: dict = {}
_CACHE_TTL: float = 300.0  # 5 minutes


def clear_sector_cache() -> None:
    """Xóa bộ nhớ đệm sector cache."""
    global _SECTOR_CACHE
    _SECTOR_CACHE.clear()


def _get_db_key(conn) -> str:
    try:
        rows = conn.execute("PRAGMA database_list").fetchall()
        for r in rows:
            if r[1] == "main" and r[2]:
                return str(r[2])
    except Exception:
        pass
    return ""


def _batch_load_ratios(conn, symbols: list[str]) -> dict[tuple[str, str], list[tuple[str, float]]]:
    """Tải trước toàn bộ ratio cho danh sách symbol trong 1 query duy nhất.
    Trả về dict: (symbol, item_id) -> [(period, value), ...]
    """
    if not symbols:
        return {}
    out: dict[tuple[str, str], list[tuple[str, float]]] = {}
    chunk_size = 500
    ratio_items = tuple(RATIO_ITEMS.values())
    placeholders_items = ",".join("?" for _ in ratio_items)

    for i in range(0, len(symbols), chunk_size):
        chunk = symbols[i:i + chunk_size]
        placeholders = ",".join("?" for _ in chunk)
        sql = f"""SELECT symbol, item_id, period, value FROM financials
                  WHERE symbol IN ({placeholders})
                    AND statement = 'ratio'
                    AND item_id IN ({placeholders_items})
                    AND value IS NOT NULL"""
        params = list(chunk) + list(ratio_items)
        rows = conn.execute(sql, params).fetchall()
        for sym, item_id, period, val in rows:
            k = (sym, item_id)
            if k not in out:
                out[k] = []
            out[k].append((period, val))
    return out


def _latest_ratio_from_batch(ratio_data: dict, symbol: str, item_id: str):
    rows = ratio_data.get((symbol, item_id))
    if not rows:
        return None
    years = [(p, v) for (p, v) in rows if _period_kind(p) == "year"]
    quarters = [(p, v) for (p, v) in rows if _period_kind(p) == "quarter"]
    chosen = years or quarters
    if not chosen:
        return None
    chosen.sort(key=lambda pv: _period_key(pv[0]))
    return chosen[-1][1]


def _latest_ratio(conn, symbol, item_id):
    rows = conn.execute(
        """SELECT period, value FROM financials
           WHERE symbol=? AND statement='ratio' AND item_id=? AND value IS NOT NULL""",
        (symbol, item_id)).fetchall()
    if not rows:
        return None
    # Gom theo loại kỳ, KHÔNG trộn năm với quý giữa các peer.
    years = [(p, v) for (p, v) in rows if _period_kind(p) == "year"]
    quarters = [(p, v) for (p, v) in rows if _period_kind(p) == "quarter"]
    chosen = years or quarters   # ưu tiên năm; không có mới dùng quý
    if not chosen:
        return None
    # Sort theo period đã parse thành số → lấy kỳ mới nhất.
    chosen.sort(key=lambda pv: _period_key(pv[0]))
    return chosen[-1][1]


def _norm_pct(v):
    if v is None:
        return None
    return v * 100 if -1.5 < v < 1.5 else v


def _load_raw(conn, symbol: str, statement: str) -> list[dict]:
    """Nạp 1 báo cáo gốc từ DB về dạng records cho raw_ratios.compute.

    period_type suy từ định dạng chuỗi period (quý có 'Q'/'-N', còn lại là năm) —
    trùng quy ước với _period_kind ở trên."""
    rows = conn.execute(
        """SELECT item_id, item, period, value FROM financials
           WHERE symbol=? AND statement=? AND value IS NOT NULL""",
        (symbol, statement)).fetchall()
    out = []
    for item_id, item, period, value in rows:
        out.append({
            "item_id": item_id, "item": item, "period": str(period),
            "value": value,
            "period_type": "Q" if _period_kind(period) == "quarter" else "Y",
        })
    return out


def _raw_derived(conn, symbol: str, cache: dict) -> dict:
    """Chỉ số peer suy từ báo cáo gốc (roe/net_margin/debt_to_equity), cache theo mã.

    Chỉ tính khi cần lấp — dùng chung cho cả benchmark lẫn vị thế của chính mã, nên
    cache tránh dựng lại raw_ratios cho mỗi item_id."""
    if symbol in cache:
        return cache[symbol]
    inc = _load_raw(conn, symbol, "income_statement")
    bs = _load_raw(conn, symbol, "balance_sheet")
    cf = _load_raw(conn, symbol, "cash_flow")
    derived = {}
    if inc or bs:
        raw = raw_ratios.compute(inc, bs, cf)
        for key, (grp, sub) in _RAW_PATH.items():
            derived[key] = (raw.get(grp) or {}).get(sub)
    cache[symbol] = derived
    return derived


def _peer_value(conn, symbol: str, key: str, item: str, raw_cache: dict, ratio_data: dict | None = None):
    """Giá trị 1 chỉ số peer: ưu tiên bảng `ratio`, thiếu thì raw-derive (nếu suy được).

    Trả (value, source) với source='ratio'|'raw'|None để tầng trên báo cáo độ phủ."""
    if ratio_data is not None:
        v = _latest_ratio_from_batch(ratio_data, symbol, item)
    else:
        v = _latest_ratio(conn, symbol, item)
    if v is not None:
        if key in ("roe", "net_margin"):
            v = _norm_pct(v)
        return v, "ratio"
    if key in _RAW_PATH:
        rv = _raw_derived(conn, symbol, raw_cache).get(key)
        if rv is not None:
            # ĐỒNG NHẤT ĐƠN VỊ với bảng ratio để trung vị không lẫn thang:
            #  - roe, net_margin: raw_ratios đã trả % (khớp ratio table, cùng %).
            #  - debt_to_equity: ratio table lưu dạng % (vd HPG 70.24), raw trả số
            #    lần (0.86) → nhân 100 cho về cùng thang % trước khi trộn.
            if key == "debt_to_equity":
                rv = rv * 100.0
            return rv, "raw"
    return None, None


def compute(conn, symbol: str) -> dict:
    row = conn.execute("SELECT sector FROM companies WHERE symbol=?", (symbol,)).fetchone()
    sector = row[0] if row and row[0] else None
    if not sector:
        return {"sector": None, "n_peers": 0, "benchmark": {}, "position": {}}

    db_key = _get_db_key(conn)
    now = time.time()

    # Kiểm tra cache ngành (chỉ cache với real file DB)
    cached_sector = None
    if db_key:
        cache_entry = _SECTOR_CACHE.get((db_key, sector))
        if cache_entry and (now - cache_entry[0] < _CACHE_TTL):
            cached_sector = cache_entry[1]

    if cached_sector is None:
        peers = [r[0] for r in conn.execute(
            "SELECT symbol FROM companies WHERE sector=?", (sector,)).fetchall()]

        # Batch load toàn bộ ratio của các công ty trong ngành trong 1 query
        ratio_data = _batch_load_ratios(conn, peers)

        raw_cache: dict = {}
        bench: dict = {}
        samples: dict = {k: [] for k in RATIO_ITEMS}
        peer_pts: dict = {k: [] for k in RATIO_ITEMS}
        raw_used: dict = {k: 0 for k in RATIO_ITEMS}
        sym_values: dict = {s: {} for s in peers}

        for sym in peers:
            for key, item in RATIO_ITEMS.items():
                v, src = _peer_value(conn, sym, key, item, raw_cache, ratio_data)
                sym_values[sym][key] = (v, src)
                if v is None:
                    continue
                if key in ("pe", "pb") and v <= 0:
                    continue
                samples[key].append(v)
                peer_pts[key].append({"sym": sym, "value": round(v, 2)})
                if src == "raw":
                    raw_used[key] += 1

        for key, vals in samples.items():
            if vals:
                bench[key] = round(statistics.median(vals), 2)

        n_with_data = sum(
            1 for p in peers
            if any(sym_values[p].get(k, (None, None))[0] is not None
                   for k in RATIO_ITEMS))

        cached_sector = {
            "peers": peers,
            "sym_values": sym_values,
            "samples": samples,
            "peer_pts": peer_pts,
            "bench": bench,
            "n_with_data": n_with_data,
            "raw_used": raw_used,
            "sample_sizes": {k: len(v) for k, v in samples.items()},
            "raw_cache": raw_cache,
            "ratio_data": ratio_data,
        }
        if db_key:
            _SECTOR_CACHE[(db_key, sector)] = (now, cached_sector)

    # Trích xuất dữ liệu cho symbol được yêu cầu từ cached_sector
    peers = cached_sector["peers"]
    sym_values = cached_sector["sym_values"]
    bench = cached_sector["bench"]
    samples = cached_sector["samples"]
    peer_pts = cached_sector["peer_pts"]

    # Vị thế của chính công ty so với trung vị ngành
    if symbol in sym_values:
        self_vals = {k: sym_values[symbol].get(k, (None, None))[0] for k in RATIO_ITEMS}
    else:
        self_vals = {}
        for key, item in RATIO_ITEMS.items():
            v, _ = _peer_value(conn, symbol, key, item, cached_sector.get("raw_cache", {}), cached_sector.get("ratio_data"))
            self_vals[key] = v

    position = {}
    for key, item in RATIO_ITEMS.items():
        v = self_vals.get(key)
        if v is not None and key in bench and bench[key]:
            if key in ("pe", "pb", "debt_to_equity"):     # thấp hơn = tốt/rẻ hơn
                position[key] = "thấp hơn ngành" if v < bench[key] else "cao hơn ngành"
            else:                                          # roe, margin: cao hơn = tốt
                position[key] = "cao hơn ngành" if v > bench[key] else "thấp hơn ngành"

    # B7: giá trị từng mã cùng ngành (đã bỏ chính mã) để strip vẽ chấm peer
    filtered_peer_pts = {}
    for k, pts in peer_pts.items():
        filtered = [pt for pt in pts if pt["sym"] != symbol]
        if filtered:
            filtered_peer_pts[k] = filtered

    return {
        "sector": sector,
        "n_peers": cached_sector["n_with_data"],
        "n_sector": len(peers),
        "benchmark": bench, "self": self_vals, "position": position,
        "peer_values": filtered_peer_pts,
        "pct": _direction_pct(self_vals, samples),
        "sample_sizes": cached_sector["sample_sizes"],
        "raw_derived_counts": cached_sector["raw_used"],
    }


# §12.2 · bảng chiều: chỉ số nào "thấp = tốt" thì đảo percentile (100 − pct).
_INVERT = {"pe", "pb", "debt_to_equity"}   # thấp hơn = rẻ/an toàn hơn = phải


def _direction_pct(self_vals: dict, samples: dict) -> dict:
    """Percentile của chính mã trong phân phối ngành, đã CHUẨN HÓA CHIỀU về
    0–100 (100 = thuận lợi nhất theo mô hình). Cần ≥3 mẫu ngành mới tính."""
    out = {}
    for key, vals in samples.items():
        sv = self_vals.get(key)
        if sv is None or len(vals) < 3:
            continue
        below = sum(1 for x in vals if x < sv)
        equal = sum(1 for x in vals if x == sv)
        pct = (below + 0.5 * equal) / len(vals) * 100.0   # percentile rank thô
        if key in _INVERT:
            pct = 100.0 - pct
        out[key] = round(pct, 1)
    return out
