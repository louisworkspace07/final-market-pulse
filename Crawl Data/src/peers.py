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


def _peer_value(conn, symbol: str, key: str, item: str, raw_cache: dict):
    """Giá trị 1 chỉ số peer: ưu tiên bảng `ratio`, thiếu thì raw-derive (nếu suy được).

    Trả (value, source) với source='ratio'|'raw'|None để tầng trên báo cáo độ phủ."""
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

    peers = [r[0] for r in conn.execute(
        "SELECT symbol FROM companies WHERE sector=?", (sector,)).fetchall()]

    raw_cache: dict = {}
    bench: dict = {}
    samples: dict = {k: [] for k in RATIO_ITEMS}
    peer_pts: dict = {k: [] for k in RATIO_ITEMS}  # B7: (sym,value) từng mã để vẽ chấm strip
    raw_used: dict = {k: 0 for k in RATIO_ITEMS}   # đếm mẫu phải raw-derive để báo độ phủ
    for sym in peers:
        for key, item in RATIO_ITEMS.items():
            v, src = _peer_value(conn, sym, key, item, raw_cache)
            if v is None:
                continue
            if key in ("pe", "pb") and v <= 0:
                continue
            samples[key].append(v)
            if sym != symbol:
                peer_pts[key].append({"sym": sym, "value": round(v, 2)})
            if src == "raw":
                raw_used[key] += 1

    for key, vals in samples.items():
        if vals:
            bench[key] = round(statistics.median(vals), 2)

    # Vị thế của chính công ty so với trung vị ngành
    self_vals = {}
    position = {}
    for key, item in RATIO_ITEMS.items():
        v, _ = _peer_value(conn, symbol, key, item, raw_cache)
        self_vals[key] = v
        if v is not None and key in bench and bench[key]:
            if key in ("pe", "pb", "debt_to_equity"):     # thấp hơn = tốt/rẻ hơn
                position[key] = "thấp hơn ngành" if v < bench[key] else "cao hơn ngành"
            else:                                          # roe, margin: cao hơn = tốt
                position[key] = "cao hơn ngành" if v > bench[key] else "thấp hơn ngành"

    # n_peers = số mã có ÍT NHẤT 1 chỉ số so sánh (ratio hoặc raw), không chỉ P/E:
    # nhờ raw-derive, mẫu ngành rộng hơn so với chỉ đếm mã có định giá.
    n_with_data = sum(
        1 for p in peers
        if any(_peer_value(conn, p, k, it, raw_cache)[0] is not None
               for k, it in RATIO_ITEMS.items()))
    return {
        "sector": sector,
        "n_peers": n_with_data,        # số cty cùng ngành có ít nhất 1 chỉ số so sánh
        "n_sector": len(peers),
        "benchmark": bench, "self": self_vals, "position": position,
        # B7: giá trị từng mã cùng ngành (đã bỏ chính mã) để strip vẽ chấm peer
        "peer_values": {k: v for k, v in peer_pts.items() if v},
        # §12: percentile ngành CHUẨN HÓA CHIỀU (0–100, phải=thuận lợi) cho One Bar
        "pct": _direction_pct(self_vals, samples),
        # số mẫu mỗi chỉ số + số mẫu suy từ báo cáo gốc (minh bạch nguồn trung vị)
        "sample_sizes": {k: len(v) for k, v in samples.items()},
        "raw_derived_counts": raw_used,
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
