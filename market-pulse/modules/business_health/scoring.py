# -*- coding: utf-8 -*-
"""Chấm điểm sức khỏe doanh nghiệp từ BCTC (market.db của module data-crawler).

Hai thước đo học thuật được dùng phổ biến:
- Altman Z''-score (phiên bản thị trường mới nổi, 1995):
    Z'' = 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4
    X1 = Vốn lưu động / Tổng tài sản
    X2 = LN giữ lại / Tổng tài sản
    X3 = EBIT / Tổng tài sản
    X4 = Vốn chủ sở hữu / Tổng nợ
    Vùng: > 2.6 an toàn | 1.1 - 2.6 xám | < 1.1 nguy hiểm
- Piotroski F-score rút gọn (7/9 tiêu chí, bỏ 2 tiêu chí cần dữ liệu phát hành CP)

Ngân hàng / công ty tài chính không có "Tài sản ngắn hạn" → chỉ tính
nhóm chỉ số phù hợp (ROA, ROE, đòn bẩy) và gắn nhãn nhóm "TCTC".

Ngoài điểm sức khỏe cơ bản, module còn xuất:
- ``watch_flags``: các cờ theo dõi trung tính (z_danger, f_low, f_drop, weak_combo)
- ``flow_score``: cường độ giao dịch gần đây từ bảng ``price`` (mô tả, KHÔNG khuyến nghị)
"""
import os
import sqlite3
import json
import pandas as pd
import numpy as np

# các alias tên chỉ tiêu (item_en) trong market.db
ITEMS = {
    "total_assets": ["TOTAL ASSETS", "Total Assets"],
    "liabilities": ["Liabilities"],
    "current_assets": ["CURRENT ASSETS"],
    "current_liab": ["Current liabilities"],
    "equity": ["OWNER'S EQUITY", "Owner's Equity", "Owners Equity"],
    "retained": ["Retained Earnings", "Retained earnings"],
    "ebit": ["EBIT"],
    "net_income": ["Net profit/(loss) after tax"],
    "revenue": ["Net sales"],
    "gross_profit": ["Gross Profit"],
    "cfo": ["Net cash inflows/(outflows) from operating activities",
            "Net cash from operating activities"],
}


def _latest_years(df: pd.DataFrame, n: int = 2) -> pd.DataFrame:
    """Giữ ``n`` kỳ năm gần nhất (period dạng '2024', '2023'...)."""
    annual = df[df["period"].str.fullmatch(r"\d{4}")].copy()
    if annual.empty:
        return annual
    annual["year"] = annual["period"].astype(int)
    years = sorted(annual["year"].unique())[-n:]
    return annual[annual["year"].isin(years)]


def _latest_two_years(df: pd.DataFrame) -> pd.DataFrame:
    """Giữ 2 kỳ năm gần nhất (giữ lại để tương thích ngược)."""
    return _latest_years(df, 2)


def _get(pivot: dict, year: int, key: str):
    for alias in ITEMS[key]:
        v = pivot.get((year, alias))
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            return float(v)
    return None


def _f_score(pivot: dict, y_curr: int, y_prev, is_financial: bool):
    """Piotroski F rút gọn cho kỳ ``y_curr`` (so sánh với ``y_prev`` nếu có).

    Trả về ``(f, f_max, checks)`` hoặc ``None`` nếu thiếu tổng tài sản kỳ ``y_curr``.
    Khi ``y_prev is None`` chỉ tính 3 tiêu chí không cần so sánh liên năm.
    Hàm thuần theo pivot → tái dùng được cho cả kỳ hiện tại lẫn kỳ năm trước.
    """
    g = lambda k, y=y_curr: _get(pivot, y, k)
    ta = g("total_assets")
    if not ta or ta <= 0:
        return None
    ni, cfo = g("net_income"), g("cfo")
    ca, cl = g("current_assets"), g("current_liab")
    rev, gp, liab = g("revenue"), g("gross_profit"), g("liabilities")
    roa = ni / ta if ni is not None else None

    f, f_max, checks = 0, 0, []

    def add(cond, label):
        nonlocal f, f_max
        if cond is None:
            return
        f_max += 1
        f += int(bool(cond))
        checks.append({"c": label, "pass": bool(cond)})

    add(roa is not None and roa > 0, "ROA > 0")
    add(cfo is not None and cfo > 0, "Dòng tiền HĐKD > 0")
    add((cfo is not None and ni is not None) and cfo > ni, "CFO > LN ròng (chất lượng LN)")
    if y_prev is not None:
        ni0, ta0 = _get(pivot, y_prev, "net_income"), _get(pivot, y_prev, "total_assets")
        roa0 = ni0 / ta0 if (ni0 is not None and ta0) else None
        add((roa is not None and roa0 is not None) and roa > roa0, "ROA cải thiện")
        liab0 = _get(pivot, y_prev, "liabilities")
        if liab is not None and liab0 is not None and ta0:
            add(liab / ta < liab0 / ta0, "Đòn bẩy giảm")
        ca0, cl0 = _get(pivot, y_prev, "current_assets"), _get(pivot, y_prev, "current_liab")
        if not is_financial and all(v is not None for v in [ca0, cl0, ca, cl]) and cl > 0 and cl0 > 0:
            add(ca / cl > ca0 / cl0, "Thanh khoản cải thiện")
        rev0, gp0 = _get(pivot, y_prev, "revenue"), _get(pivot, y_prev, "gross_profit")
        if all(v is not None for v in [rev, gp, rev0, gp0]) and rev > 0 and rev0 > 0:
            add(gp / rev > gp0 / rev0, "Biên LN gộp cải thiện")
    return f, f_max, checks


def _flow_score(closes: list, vols: list):
    """Tính flow_score (0–100) từ chuỗi giá đóng cửa + khối lượng (mới → cũ).

    Hàm thuần (không đụng DB) để dễ kiểm thử. Xem docstring ``flow_score``.
    """
    closes = [float(c) for c in closes if c is not None]
    vols = [float(v) for v in vols if v is not None]
    if len(closes) < 6 or len(vols) < 5:
        return None

    # (a) cường độ khối lượng: TB 5 phiên gần nhất / TB tối đa 20 phiên
    vol5 = sum(vols[:5]) / 5.0
    vol20 = sum(vols) / len(vols)
    ratio = (vol5 / vol20) if vol20 > 0 else 0.0
    ratio = min(max(ratio, 0.0), 3.0)
    vol_comp = ratio / 3.0 * 60.0

    # (b) biên độ giá 5 phiên (giá trị tuyệt đối, không phân biệt tăng/giảm)
    c_now, c_5ago = closes[0], closes[5]
    move = abs((c_now - c_5ago) / c_5ago) * 100.0 if c_5ago else 0.0
    move = min(max(move, 0.0), 10.0)
    move_comp = move / 10.0 * 40.0

    return round(vol_comp + move_comp, 1)


def flow_score(conn_or_path, symbol: str):
    """Cường độ GIAO DỊCH gần đây của một mã, thang 0–100 (làm tròn 1 chữ số).

    Công thức = thành phần khối lượng (0–60) + thành phần biên độ giá (0–40):
    - Khối lượng: (TB khối lượng 5 phiên gần nhất / TB khối lượng ≤20 phiên),
      giới hạn [0, 3], quy về 0–60 điểm.
    - Biên độ giá: |% thay đổi giá đóng cửa 5 phiên|, giới hạn [0, 10]%, quy về 0–40 điểm.

    ĐÂY LÀ THƯỚC ĐO MÔ TẢ CƯỜNG ĐỘ GIAO DỊCH, **KHÔNG** phải tín hiệu mua/bán.
    Mã không có dữ liệu giá (hoặc <6 phiên) → trả về ``None``.

    ``conn_or_path`` nhận đường dẫn DB (tự mở kết nối mode=ro) hoặc một
    ``sqlite3.Connection`` sẵn có (để tái dùng khi chấm hàng loạt).
    """
    own = isinstance(conn_or_path, str)
    conn = (sqlite3.connect(f"file:{conn_or_path}?mode=ro", uri=True)
            if own else conn_or_path)
    try:
        rows = conn.execute(
            "SELECT close, volume FROM price WHERE symbol=? "
            "ORDER BY time DESC LIMIT 20", (symbol,)).fetchall()
    except sqlite3.Error:
        return None
    finally:
        if own:
            conn.close()
    if not rows:
        return None
    return _flow_score([r[0] for r in rows], [r[1] for r in rows])


def watch_flags(z_zone, f_score, prior_f=None) -> list:
    """Sinh danh sách cờ theo dõi trung tính (không có chữ mua/bán/khuyến nghị).

    - ``z_danger``  : Z'' ở vùng "Nguy hiểm".
    - ``f_low``     : F-score <= 3.
    - ``f_drop``    : có F-score kỳ NĂM TRƯỚC và F-score hiện tại thấp hơn.
                      ``prior_f=None`` → không đủ dữ liệu → bỏ qua im lặng.
    - ``weak_combo``: đồng thời z_danger và f_low.
    """
    flags = []
    if z_zone == "Nguy hiểm":
        flags.append("z_danger")
    if f_score is not None and f_score <= 3:
        flags.append("f_low")
    if prior_f is not None and f_score is not None and f_score < prior_f:
        flags.append("f_drop")
    if "z_danger" in flags and "f_low" in flags:
        flags.append("weak_combo")
    return flags


def score_company(fin: pd.DataFrame, symbol: str, name: str, exchange: str) -> dict | None:
    # Giữ tối đa 3 năm gần nhất: 2 năm cho các chỉ số chính + năm thứ 3 để
    # thử tính F-score kỳ trước (flag f_drop). Việc thêm năm không đổi kết quả
    # các chỉ số hiện tại vì tất cả đều tra cứu theo (year, item) cụ thể.
    fin = _latest_years(fin, 3)
    if fin.empty:
        return None
    pivot = {(r.year, r.item_en): r.value for r in fin.itertuples()}
    years = sorted({r.year for r in fin.itertuples()})
    y1 = years[-1]
    y0 = years[-2] if len(years) >= 2 else None
    ym1 = years[-3] if len(years) >= 3 else None

    g = lambda k, y=y1: _get(pivot, y, k)
    ta, liab, equity = g("total_assets"), g("liabilities"), g("equity")
    if not ta or ta <= 0:
        return None

    ca, cl = g("current_assets"), g("current_liab")
    is_financial = ca is None or cl is None  # ngân hàng/CTCK không có mục này

    ni, cfo, ebit = g("net_income"), g("cfo"), g("ebit")
    retained, rev, gp = g("retained"), g("revenue"), g("gross_profit")

    roa = ni / ta if ni is not None else None
    roe = ni / equity if (ni is not None and equity) else None

    result = {
        "symbol": symbol, "name": name, "exchange": exchange,
        "year": int(y1), "group": "TCTC" if is_financial else "DN",
        "total_assets_b": round(ta / 1e9, 0),
        "roa": round(roa * 100, 2) if roa is not None else None,
        "roe": round(roe * 100, 2) if roe is not None else None,
        "debt_ratio": round(liab / ta * 100, 1) if liab is not None else None,
    }

    # ---- Altman Z'' (chỉ DN phi tài chính) ----
    if not is_financial and liab and liab > 0:
        x1 = (ca - cl) / ta
        x2 = (retained or 0) / ta
        x3 = (ebit or 0) / ta
        x4 = (equity or 0) / liab
        z = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4
        result["z_score"] = round(z, 2)
        result["z_zone"] = "An toàn" if z > 2.6 else ("Xám" if z >= 1.1 else "Nguy hiểm")
    else:
        result["z_score"] = None
        result["z_zone"] = "N/A (tổ chức tài chính)"

    # ---- Piotroski F rút gọn (7 tiêu chí) — kỳ hiện tại ----
    f, f_max, checks = _f_score(pivot, y1, y0, is_financial)
    result["f_score"] = f
    result["f_max"] = f_max
    result["f_checks"] = checks

    # ---- Điểm sức khỏe tổng hợp 0-100 ----
    parts = []
    if result["z_score"] is not None:
        parts.append(min(max(result["z_score"] / 5.0, 0), 1) * 100)
    if f_max > 0:
        parts.append(f / f_max * 100)
    if roa is not None:
        parts.append(min(max(roa / 0.15, 0), 1) * 100)
    result["health_score"] = round(float(np.mean(parts)), 1) if parts else None

    # ---- Cờ theo dõi (watch_flags) ----
    # F-score kỳ năm trước: chỉ tính được khi có đủ 3 năm BCTC (y0 & ym1).
    # Không đủ → prior_f = None → flag f_drop bị bỏ qua im lặng (không fake).
    prior_f = None
    if ym1 is not None:
        prev = _f_score(pivot, y0, ym1, is_financial)
        if prev is not None and prev[1] > 0:
            prior_f = prev[0]
    result["watch_flags"] = watch_flags(result["z_zone"], result["f_score"], prior_f)

    # flow_score cần bảng price → điền ở score_all; mặc định None để schema luôn có field.
    result["flow_score"] = None
    return result


def score_all(db_path: str) -> list[dict]:
    from collections import defaultdict
    all_items = list({alias for lst in ITEMS.values() for alias in lst})
    placeholders = ",".join("?" for _ in all_items)

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
    try:
        companies = con.execute(
            "SELECT symbol, organ_name, exchange FROM companies "
            "WHERE symbol IN (SELECT DISTINCT symbol FROM financials)"
        ).fetchall()

        fin_rows = con.execute(f"""
            SELECT symbol, item_en, CAST(period AS INTEGER), value FROM financials 
            WHERE length(period)=4 AND period >= '2020' AND value IS NOT NULL
              AND item_en IN ({placeholders})
        """, all_items).fetchall()

        pivots = defaultdict(dict)
        years_by_sym = defaultdict(set)
        for sym, item_en, yr, val in fin_rows:
            pivots[sym][(yr, item_en)] = val
            years_by_sym[sym].add(yr)

        price_rows = con.execute("""
            WITH ranked AS (
                SELECT symbol, close, volume,
                       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY time DESC) as rn
                FROM price WHERE close IS NOT NULL
            )
            SELECT symbol, close, volume FROM ranked WHERE rn <= 20
        """).fetchall()

        prices_by_sym = defaultdict(lambda: ([], []))
        for sym, close, vol in price_rows:
            prices_by_sym[sym][0].append(close)
            prices_by_sym[sym][1].append(vol)
    finally:
        con.close()

    out = []
    for sym, name, exchange in companies:
        all_yrs = sorted(years_by_sym.get(sym, []))
        yrs = all_yrs[-3:]
        if not yrs:
            continue
        pivot = pivots[sym]
        y1 = yrs[-1]
        y0 = yrs[-2] if len(yrs) >= 2 else None
        ym1 = yrs[-3] if len(yrs) >= 3 else None

        g = lambda k, y=y1: _get(pivot, y, k)
        ta, liab, equity = g("total_assets"), g("liabilities"), g("equity")
        if not ta or ta <= 0:
            continue

        ca, cl = g("current_assets"), g("current_liab")
        is_financial = ca is None or cl is None
        ni, cfo, ebit = g("net_income"), g("cfo"), g("ebit")
        retained, rev, gp = g("retained"), g("revenue"), g("gross_profit")

        roa = ni / ta if ni is not None else None
        roe = ni / equity if (ni is not None and equity) else None

        result = {
            "symbol": sym, "name": name or "", "exchange": exchange or "",
            "year": int(y1), "group": "TCTC" if is_financial else "DN",
            "total_assets_b": round(ta / 1e9, 0),
            "roa": round(roa * 100, 2) if roa is not None else None,
            "roe": round(roe * 100, 2) if roe is not None else None,
            "debt_ratio": round(liab / ta * 100, 1) if liab is not None else None,
        }

        if not is_financial and liab and liab > 0:
            x1 = (ca - cl) / ta
            x2 = (retained or 0) / ta
            x3 = (ebit or 0) / ta
            x4 = (equity or 0) / liab
            z = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4
            result["z_score"] = round(z, 2)
            result["z_zone"] = "An toàn" if z > 2.6 else ("Xám" if z >= 1.1 else "Nguy hiểm")
        else:
            result["z_score"] = None
            result["z_zone"] = "N/A (tổ chức tài chính)"

        f, f_max, checks = _f_score(pivot, y1, y0, is_financial)
        result["f_score"] = f
        result["f_max"] = f_max
        result["f_checks"] = checks

        parts = []
        if result["z_score"] is not None:
            parts.append(min(max(result["z_score"] / 5.0, 0), 1) * 100)
        if f_max > 0:
            parts.append(f / f_max * 100)
        if roa is not None:
            parts.append(min(max(roa / 0.15, 0), 1) * 100)
        result["health_score"] = round(float(np.mean(parts)), 1) if parts else None

        prior_f = None
        if ym1 is not None:
            prev = _f_score(pivot, y0, ym1, is_financial)
            if prev is not None and prev[1] > 0:
                prior_f = prev[0]
        result["watch_flags"] = watch_flags(result["z_zone"], result["f_score"], prior_f)

        c_list, v_list = prices_by_sym.get(sym, ([], []))
        result["flow_score"] = _flow_score(c_list, v_list) if len(c_list) >= 6 else None
        out.append(result)

    out.sort(key=lambda x: (x["health_score"] is None, -(x["health_score"] or 0)))
    return out


if __name__ == "__main__":
    import sys
    db = sys.argv[1] if len(sys.argv) > 1 else r"..\..\..\data-crawler\database\market.db"
    scores = score_all(db)
    print(json.dumps(scores[:5], ensure_ascii=False, indent=1))
    print(f"Tong: {len(scores)} cong ty")
