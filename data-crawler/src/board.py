"""Bảng giá realtime kiểu VNDirect — dùng vnstock Trading.price_board().

Trả về snapshot giá khớp + dư mua/bán 3 bậc + ĐTNN cho một nhóm (VN30/HOSE/...).
Có cache ngắn để tránh gọi quá nhiều (price_board chỉ tốn 1 request/lần).
"""
from __future__ import annotations

import time

_GROUP_CACHE: dict = {}        # group -> (ts, [symbols])
_BOARD_CACHE: dict = {}        # group -> (ts, payload)
GROUP_TTL = 3600               # danh sách mã: 1 giờ
BOARD_TTL = 4                  # bảng giá: 4 giây

GROUPS = ["VN30", "VN100", "HOSE", "HNX", "UPCOM", "VN30F1M"]


def _flat(df):
    """Phẳng hóa MultiIndex (group, field) -> dict truy cập theo field."""
    def col(field):
        for c in df.columns:
            if (isinstance(c, tuple) and c[-1] == field) or c == field:
                return df[c]
        return None
    return col


def group_symbols(group: str) -> list[str]:
    group = group.upper()
    now = time.time()
    hit = _GROUP_CACHE.get(group)
    if hit and now - hit[0] < GROUP_TTL:
        return hit[1]
    
    syms = []
    try:
        from vnstock import Listing
        syms = list(Listing().symbols_by_group(group))
    except Exception:
        # Fallback vào market.db SQLite khi vnstock không có Listing
        try:
            from src import storage
            conn = storage.connect()
            if group in ("HOSE", "HNX", "UPCOM"):
                cur = conn.execute("SELECT symbol FROM companies WHERE upper(exchange) = ? ORDER BY symbol", (group,))
                syms = [r[0] for r in cur.fetchall()]
            elif group == "VN30":
                vn30 = ['ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG', 
                        'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 
                        'TCB', 'TPB', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE']
                syms = vn30
            elif group == "VN100":
                cur = conn.execute("SELECT symbol FROM companies WHERE upper(exchange) = 'HOSE' ORDER BY market_cap DESC LIMIT 100")
                syms = [r[0] for r in cur.fetchall()]
            else:
                cur = conn.execute("SELECT symbol FROM companies ORDER BY symbol LIMIT 100")
                syms = [r[0] for r in cur.fetchall()]
            conn.close()
        except Exception as e:
            print(f"[board] group_symbols fallback db lỗi: {e}")
            syms = []

    # HOSE/UPCOM rất đông → giới hạn để bảng nhẹ và 1 request không quá tải
    if group in ("HOSE",):
        syms = syms[:300]
    elif group in ("UPCOM",):
        syms = syms[:200]
    elif group == "HNX":
        syms = syms[:250]
    _GROUP_CACHE[group] = (now, syms)
    return syms


def resolve_symbols(group: str) -> list[str]:
    """Phân giải danh sách mã theo tên nhóm (VN30, VN100, HOSE, HNX, UPCOM, ALL, CUSTOM)."""
    group = (group or "VN30").strip().upper()
    if group in ("CUSTOM", "CONFIG"):
        from src import config
        syms = config.load_companies()
        if not syms:
            from src import storage
            conn = storage.connect()
            syms = storage.list_symbols(conn)
            conn.close()
        return syms
    if group == "ALL":
        hose = group_symbols("HOSE")
        hnx = group_symbols("HNX")
        upcom = group_symbols("UPCOM")
        seen = set()
        out = []
        for s in hose + hnx + upcom:
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out
    if group in GROUPS:
        return group_symbols(group)
    return group_symbols("VN30")



def _num(v):
    try:
        if v is None:
            return None
        f = float(v)
        return f
    except (TypeError, ValueError):
        return None


def get_board(group: str = "VN30") -> dict:
    group = group.upper()
    now = time.time()
    hit = _BOARD_CACHE.get(group)
    if hit and now - hit[0] < BOARD_TTL:
        return hit[1]

    from vnstock import Trading
    syms = group_symbols(group)
    df = Trading(source="VCI").price_board(syms)
    col = _flat(df)

    def series(field):
        s = col(field)
        return list(s) if s is not None else [None] * len(df)

    fields = ["symbol", "ceiling", "floor", "ref_price", "organ_name",
              "match_price", "match_vol", "accumulated_volume", "avg_match_price",
              "highest", "lowest", "open_price",
              "foreign_buy_volume", "foreign_sell_volume",
              "bid_1_price", "bid_1_volume", "bid_2_price", "bid_2_volume",
              "bid_3_price", "bid_3_volume",
              "ask_1_price", "ask_1_volume", "ask_2_price", "ask_2_volume",
              "ask_3_price", "ask_3_volume"]
    cols = {f: series(f) for f in fields}

    rows = []
    n = len(df)
    for i in range(n):
        ref = _num(cols["ref_price"][i])
        mp = _num(cols["match_price"][i])
        change = (mp - ref) if (mp is not None and ref) else None
        pct = (change / ref * 100) if (change is not None and ref) else None
        rows.append({
            "symbol": cols["symbol"][i],
            "ceiling": _num(cols["ceiling"][i]),
            "floor": _num(cols["floor"][i]),
            "ref": ref,
            "match_price": mp,
            "match_vol": _num(cols["match_vol"][i]),
            "change": change, "pct": pct,
            "total_vol": _num(cols["accumulated_volume"][i]),
            "avg": _num(cols["avg_match_price"][i]),
            "high": _num(cols["highest"][i]),
            "low": _num(cols["lowest"][i]),
            "open": _num(cols["open_price"][i]),
            "f_buy": _num(cols["foreign_buy_volume"][i]),
            "f_sell": _num(cols["foreign_sell_volume"][i]),
            "bid": [[_num(cols["bid_3_price"][i]), _num(cols["bid_3_volume"][i])],
                    [_num(cols["bid_2_price"][i]), _num(cols["bid_2_volume"][i])],
                    [_num(cols["bid_1_price"][i]), _num(cols["bid_1_volume"][i])]],
            "ask": [[_num(cols["ask_1_price"][i]), _num(cols["ask_1_volume"][i])],
                    [_num(cols["ask_2_price"][i]), _num(cols["ask_2_volume"][i])],
                    [_num(cols["ask_3_price"][i]), _num(cols["ask_3_volume"][i])]],
        })

    payload = {"group": group, "count": len(rows), "ts": now, "rows": rows}
    _BOARD_CACHE[group] = (now, payload)
    return payload
