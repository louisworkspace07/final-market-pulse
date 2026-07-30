# -*- coding: utf-8 -*-
"""Bảng giá realtime qua vnstock Trading.price_board() — KHÔNG cần Playwright/Chrome.

Thay cho việc cào DOM VNDirect (mở Chrome đầy đủ, nặng CPU, dễ vỡ khi web đổi
giao diện). price_board trả 726 mã HOSE+HNX trong ~0.8s, đủ mọi trường: khớp
lệnh, dư mua/bán 3 bậc, khối ngoại.

Giữ NGUYÊN shape mà frontend static/app.js đang đọc — KHÔNG sửa frontend:
  - các trường số (ref/ceil/floor/matchPrice/buyP*/sellP*...) để nguyên đơn vị
    VND (getColorClass so sánh nhất quán → màu trần/sàn/TC đúng);
  - raw[0..26] là TEXT hiển thị, format theo bảng giá VN (giá /1000 2 số lẻ,
    KL nhóm hàng nghìn).

Bảng đối chiếu raw[] (khớp đúng static/app.js createRow):
  0 ticker · 1 TC · 2 trần · 3 sàn · 4 tổng KL · 5-10 mua P3/V3..P1/V1 ·
  11 giá khớp · 12 KL khớp · 13 +/- · 14-19 bán P1/V1..P3/V3 ·
  20 cao · 21 TB · 22 thấp · 23 dư mua · 24 dư bán · 25 NN mua · 26 NN bán
"""
from __future__ import annotations

import json
import os
import time

# Nguồn giá dùng chung (VCI qua vnstock). Import trễ để server khởi động nhanh.
_LISTING_CACHE = {"ts": 0.0, "by_ex": {}, "all": []}
GROUP_TTL = 3600            # danh sách mã theo sàn: làm mới 1 giờ
# Cache ra đĩa để KHỞI ĐỘNG LẠI gần như tức thì (Listing 3 sàn mất ~16s).
_DISK_CACHE = os.path.join(os.path.dirname(__file__), "temp_data", "universe_cache.json")
_DISK_TTL = 86400          # 1 ngày


def _flat_col(df, field):
    """Lấy Series theo tên field, chịu được cột phẳng lẫn MultiIndex (group,field)."""
    for c in df.columns:
        if (isinstance(c, tuple) and c[-1] == field) or c == field:
            return df[c]
    return None


def _num(v):
    try:
        f = float(v)
        return None if f != f else f      # loại NaN
    except (TypeError, ValueError):
        return None


def _price_txt(v):
    """VND → hiển thị nghìn đồng 2 số lẻ (51400 → '51.40'). Rỗng nếu 0/None."""
    n = _num(v)
    if not n:
        return ""
    return f"{n/1000:.2f}"


def _vol_txt(v):
    """Khối lượng cổ phiếu → nhóm hàng nghìn ('1,862,200'). Rỗng nếu 0/None."""
    n = _num(v)
    if not n:
        return ""
    return f"{int(n):,}"


def load_universe(force: bool = False) -> tuple[dict, list]:
    """Trả (symbol→exchange, [all symbols]) từ vnstock Listing, cache 1 giờ."""
    now = time.time()
    if not force and _LISTING_CACHE["all"] and now - _LISTING_CACHE["ts"] < GROUP_TTL:
        return _LISTING_CACHE["by_ex"], _LISTING_CACHE["all"]
    # Cache đĩa: tránh chờ Listing ~16s mỗi lần khởi động server.
    if not force and os.path.exists(_DISK_CACHE):
        try:
            d = json.load(open(_DISK_CACHE, encoding="utf-8"))
            if now - d.get("ts", 0) < _DISK_TTL and d.get("all"):
                _LISTING_CACHE.update({"ts": now, "by_ex": d["by_ex"], "all": d["all"]})
                return d["by_ex"], d["all"]
        except Exception:
            pass
    from vnstock import Listing
    L = Listing()
    by_ex, allsyms = {}, []
    for ex in ("HOSE", "HNX", "UPCOM"):
        try:
            syms = list(L.symbols_by_group(ex))
        except Exception as e:
            print(f"[board] symbols_by_group({ex}) lỗi: {str(e)[:80]}")
            syms = []
        for s in syms:
            by_ex[s] = ex.lower()
        allsyms += syms
    # loại trùng, giữ thứ tự
    seen, uniq = set(), []
    for s in allsyms:
        if s not in seen:
            seen.add(s); uniq.append(s)
    _LISTING_CACHE.update({"ts": now, "by_ex": by_ex, "all": uniq})
    try:
        os.makedirs(os.path.dirname(_DISK_CACHE), exist_ok=True)
        json.dump({"ts": now, "by_ex": by_ex, "all": uniq},
                  open(_DISK_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    except Exception:
        pass
    return by_ex, uniq


def fetch_board(symbols: list[str], ex_map: dict) -> list[dict]:
    """Gọi price_board cho danh sách mã → list dict đúng shape frontend."""
    from vnstock import Trading
    df = Trading(source="VCI").price_board(symbols)
    n = len(df)
    F = {f: (_flat_col(df, f) if _flat_col(df, f) is not None else [None] * n)
         for f in ("symbol", "ref_price", "ceiling", "floor", "match_price",
                   "match_vol", "accumulated_volume", "avg_match_price",
                   "highest", "lowest", "foreign_buy_volume", "foreign_sell_volume",
                   "bid_1_price", "bid_1_volume", "bid_2_price", "bid_2_volume",
                   "bid_3_price", "bid_3_volume", "ask_1_price", "ask_1_volume",
                   "ask_2_price", "ask_2_volume", "ask_3_price", "ask_3_volume")}

    out = []
    for i in range(n):
        g = lambda k: list(F[k])[i]
        sym = g("symbol")
        if not sym:
            continue
        ref = _num(g("ref_price")); mp = _num(g("match_price"))
        change = (mp - ref) if (mp is not None and ref) else None
        # "Dư" = tổng KL đặt 3 bậc mỗi bên (price_board không có trường dư riêng).
        du_mua = sum(_num(g(k)) or 0 for k in ("bid_1_volume", "bid_2_volume", "bid_3_volume"))
        du_ban = sum(_num(g(k)) or 0 for k in ("ask_1_volume", "ask_2_volume", "ask_3_volume"))
        # raw[] TEXT hiển thị — đúng thứ tự cột bảng giá
        raw = [
            str(sym),                                   # 0 ticker
            _price_txt(g("ref_price")),                 # 1 TC
            _price_txt(g("ceiling")),                   # 2 trần
            _price_txt(g("floor")),                     # 3 sàn
            _vol_txt(g("accumulated_volume")),          # 4 tổng KL
            _price_txt(g("bid_3_price")), _vol_txt(g("bid_3_volume")),   # 5,6
            _price_txt(g("bid_2_price")), _vol_txt(g("bid_2_volume")),   # 7,8
            _price_txt(g("bid_1_price")), _vol_txt(g("bid_1_volume")),   # 9,10
            _price_txt(g("match_price")),               # 11 giá khớp
            _vol_txt(g("match_vol")),                   # 12 KL khớp
            (f"{change/1000:+.2f}" if change is not None else ""),      # 13 +/-
            _price_txt(g("ask_1_price")), _vol_txt(g("ask_1_volume")),   # 14,15
            _price_txt(g("ask_2_price")), _vol_txt(g("ask_2_volume")),   # 16,17
            _price_txt(g("ask_3_price")), _vol_txt(g("ask_3_volume")),   # 18,19
            _price_txt(g("highest")),                   # 20 cao
            _price_txt(g("avg_match_price")),           # 21 TB
            _price_txt(g("lowest")),                    # 22 thấp
            _vol_txt(du_mua), _vol_txt(du_ban),         # 23,24 dư mua/bán = tổng KL 3 bậc
            _vol_txt(g("foreign_buy_volume")),          # 25 NN mua
            _vol_txt(g("foreign_sell_volume")),         # 26 NN bán
        ]
        out.append({
            "symbol": sym, "exchange": ex_map.get(sym, ""),
            "ref": ref, "ceil": _num(g("ceiling")), "floor": _num(g("floor")),
            "matchPrice": mp, "matchVol": _num(g("match_vol")),
            "totalVol": _num(g("accumulated_volume")),
            "buyP3": _num(g("bid_3_price")), "buyV3": _num(g("bid_3_volume")),
            "buyP2": _num(g("bid_2_price")), "buyV2": _num(g("bid_2_volume")),
            "buyP1": _num(g("bid_1_price")), "buyV1": _num(g("bid_1_volume")),
            "sellP1": _num(g("ask_1_price")), "sellV1": _num(g("ask_1_volume")),
            "sellP2": _num(g("ask_2_price")), "sellV2": _num(g("ask_2_volume")),
            "sellP3": _num(g("ask_3_price")), "sellV3": _num(g("ask_3_volume")),
            "high": _num(g("highest")), "avg": _num(g("avg_match_price")),
            "low": _num(g("lowest")),
            "foreignBuy": _num(g("foreign_buy_volume")) or 0,
            "foreignSell": _num(g("foreign_sell_volume")) or 0,
            "raw": raw,
        })
    return out


if __name__ == "__main__":
    ex_map, allsyms = load_universe()
    print("universe:", len(allsyms))
    t = time.time()
    rows = fetch_board(allsyms[:300], ex_map)
    print(f"fetch 300: {time.time()-t:.2f}s, rows={len(rows)}")
    print("sample:", {k: rows[0][k] for k in ("symbol", "exchange", "matchPrice")})
    print("raw:", rows[0]["raw"])
