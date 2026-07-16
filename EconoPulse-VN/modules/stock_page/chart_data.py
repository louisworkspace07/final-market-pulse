# -*- coding: utf-8 -*-
"""D-1 · Tầng dữ liệu biểu đồ cho trang cổ phiếu — PLAN-F0-TRUC-QUAN Phụ lục D.

RÀNG BUỘC D0 — QUAN TRỌNG NHẤT: **AI không sinh số**. Mọi con số ở đây lấy thẳng
từ `market.db` bằng SQL. AI (bước D-3 sau này) chỉ được chọn biểu đồ nào đáng
hiện và viết lời dẫn, tham chiếu tới `id` trong `CATALOG`; ID lạ sẽ bị loại.

Vì sao tách riêng file: bước D-1 và D-2 KHÔNG cần AI. Sau hai bước đó trang đã
có biểu đồ thật; nếu tầng AI hỏng hay Local API tắt thì trang vẫn dùng được.

Mỗi biểu đồ trả về một dict thống nhất để `chart_render.js` vẽ mà không cần biết
nội dung:

    {"id", "group", "title", "kind", "unit", "x": [...],
     "series": [{"name", "data", "kind"?, "axis"?}], "source", "note"?}

`kind`: bar | line | bar+line | stacked-bar | stacked-area | waterfall |
        band | scatter | radar | histogram | timeline | price

Đơn vị: `financials.value` là ĐỒNG → quy ra tỷ. `price.close` là NGHÌN ĐỒNG.
Thiếu dữ liệu thì BỎ biểu đồ (ghi vào `missing`), không trả chuỗi rỗng để
giao diện phải đoán.

Legal: chỉ mô tả quá khứ. KHÔNG có chuỗi dự báo, không đường giá mục tiêu —
trục thời gian luôn dừng ở kỳ gần nhất (xem `modules/common/legal.py`).
"""
import json
import os
import sqlite3

BN = 1e9                      # đồng → tỷ đồng
_MAX_PRICE_POINTS = 260       # ~1 năm giao dịch, đủ cho mọi biểu đồ giá


# ---------------------------------------------------------------- hạ tầng nhỏ
def _ro(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)


def _is_year(p) -> bool:
    return "-Q" not in str(p)


def _grab(conn, symbol, statement, item_ids):
    """{period: {item_id: value}} cho các chỉ tiêu cần, bỏ giá trị None."""
    if not item_ids:
        return {}
    q = (f"SELECT period, item_id, value FROM financials WHERE symbol=? AND statement=? "
         f"AND item_id IN ({','.join('?' * len(item_ids))}) AND value IS NOT NULL")
    out: dict = {}
    for period, item_id, value in conn.execute(q, (symbol, statement, *item_ids)):
        out.setdefault(str(period), {})[item_id] = value
    return out


def _years(data: dict, n=5) -> list[str]:
    return sorted((p for p in data if _is_year(p)))[-n:]


def _quarters(data: dict, n=8) -> list[str]:
    return sorted((p for p in data if not _is_year(p)))[-n:]


def _col(data, periods, item_id, scale=BN):
    """Một cột số theo danh sách kỳ; kỳ thiếu → None (giao diện tự ngắt đường)."""
    return [None if data.get(p, {}).get(item_id) is None
            else round(data[p][item_id] / scale, 2) for p in periods]


def _has(vals) -> bool:
    """Đủ ít nhất 2 điểm có số thì mới đáng vẽ."""
    return sum(1 for v in vals if v is not None) >= 2


def _chart(cid, group, title, kind, x, series, unit="tỷ đồng", source="market.db · financials",
           note=None):
    d = {"id": cid, "group": group, "title": title, "kind": kind,
         "unit": unit, "x": list(x), "series": series, "source": source}
    if note:
        d["note"] = note
    return d


# ---------------------------------------------------------------- A · kết quả kinh doanh
# Ngân hàng KHÔNG có net_sales/gross_profit → dùng total_operating_income.
_REV = ("net_sales", "total_operating_income")
_INC = (*_REV, "gross_profit", "net_profit_loss_after_tax", "eps_basic_vnd",
        "cost_of_sales", "selling_expenses", "general_and_admin_expenses",
        "financial_income", "financial_expenses")


def _rev_key(data, periods):
    """Chỉ tiêu doanh thu thực có của mã này (thường vs ngân hàng)."""
    for k in _REV:
        if any(data.get(p, {}).get(k) for p in periods):
            return k
    return None


def _group_a(conn, symbol) -> list[dict]:
    data = _grab(conn, symbol, "income_statement", _INC)
    if not data:
        return []
    ys, qs = _years(data), _quarters(data)
    rev_k = _rev_key(data, ys + qs)
    out = []
    if rev_k and ys:
        rev, npf = _col(data, ys, rev_k), _col(data, ys, "net_profit_loss_after_tax")
        if _has(rev):
            out.append(_chart(
                "rev_profit_year", "A", "Doanh thu & lợi nhuận theo năm", "bar", ys,
                [{"name": "Doanh thu", "data": rev},
                 {"name": "Lợi nhuận sau thuế", "data": npf}]))
    if rev_k and qs:
        rq = _col(data, qs, rev_k)
        if _has(rq):
            # TTM = tổng 4 quý liên tiếp; kỳ nào chưa đủ 4 quý phía trước → None.
            ttm = [None if i < 3 or any(v is None for v in rq[i - 3:i + 1])
                   else round(sum(rq[i - 3:i + 1]), 2) for i in range(len(rq))]
            out.append(_chart(
                "rev_quarter_ttm", "A", "Doanh thu theo quý và tổng 4 quý gần nhất",
                "bar+line", qs,
                [{"name": "Doanh thu quý", "data": rq, "kind": "bar"},
                 {"name": "TTM (4 quý)", "data": ttm, "kind": "line"}],
                note="Đường TTM mượt hơn cột quý vì đã khử yếu tố mùa vụ."))
    if rev_k:
        per = ys + qs
        gm = [None if not data.get(p, {}).get("gross_profit") or not data.get(p, {}).get(rev_k)
              else round(data[p]["gross_profit"] / data[p][rev_k] * 100, 2) for p in per]
        nm = [None if data.get(p, {}).get("net_profit_loss_after_tax") is None
              or not data.get(p, {}).get(rev_k)
              else round(data[p]["net_profit_loss_after_tax"] / data[p][rev_k] * 100, 2)
              for p in per]
        ser = [s for s in ({"name": "Biên lãi gộp", "data": gm} if _has(gm) else None,
                           {"name": "Biên lãi ròng", "data": nm} if _has(nm) else None) if s]
        if ser:
            out.append(_chart("margin_trend", "A", "Biên lãi qua các kỳ", "line", per,
                              ser, unit="%", note="Xu hướng quan trọng hơn giá trị một kỳ."))
    if ys:
        eps = _col(data, ys, "eps_basic_vnd", scale=1)
        if _has(eps):
            out.append(_chart("eps_year", "A", "Lãi cơ bản trên cổ phiếu", "bar", ys,
                              [{"name": "EPS", "data": eps}], unit="đồng/CP"))
    # Thác nước: doanh thu → các khoản trừ → LNST, cho kỳ NĂM gần nhất.
    # DẤU: vnstock đã lưu chi phí là số ÂM (kiểm FPT 2025: cost_of_sales =
    # −44.224 tỷ). Đảo dấu lần nữa sẽ ra cột chi phí DƯƠNG — biểu đồ thác nước
    # trông như doanh thu cộng thêm chi phí. Ép về âm bằng −abs() để đúng dù
    # nguồn có đổi quy ước.
    if rev_k and ys:
        p = ys[-1]
        d = data.get(p, {})
        cost = lambda k: -abs(d.get(k) or 0)          # noqa: E731 — chi phí luôn là cột âm
        fin = (d.get("financial_income") or 0) - abs(d.get("financial_expenses") or 0)
        steps = [("Doanh thu", d.get(rev_k)), ("Giá vốn", cost("cost_of_sales")),
                 ("Chi phí bán hàng", cost("selling_expenses")),
                 ("Chi phí quản lý", cost("general_and_admin_expenses")),
                 ("Tài chính ròng", fin)]
        if d.get(rev_k) and d.get("cost_of_sales"):
            out.append(_chart(
                "profit_waterfall", "A", f"Doanh thu chảy về lợi nhuận ({p})", "waterfall",
                [s[0] for s in steps] + ["LNST"],
                [{"name": p, "data": [round((v or 0) / BN, 2) for _, v in steps]
                  + [round((d.get("net_profit_loss_after_tax") or 0) / BN, 2)]}],
                note="Cột âm là chi phí; cột cuối là kết quả còn lại."))
    return out


# ---------------------------------------------------------------- B · bảng cân đối
_BAL = ("total_assets", "current_assets", "cash_and_cash_equivalents", "inventories_net",
        "owners_equity", "liabilities", "total_liabilities", "current_liabilities",
        "long_term_liabilities")


def _group_b(conn, symbol) -> list[dict]:
    data = _grab(conn, symbol, "balance_sheet", _BAL)
    ys = _years(data)
    if not ys:
        return []
    out = []
    ta, ca = _col(data, ys, "total_assets"), _col(data, ys, "current_assets")
    cash, inv = _col(data, ys, "cash_and_cash_equivalents"), _col(data, ys, "inventories_net")
    if _has(ta):
        ser = [s for s in ({"name": "Tiền & tương đương", "data": cash} if _has(cash) else None,
                           {"name": "Hàng tồn kho", "data": inv} if _has(inv) else None,
                           {"name": "Tài sản ngắn hạn", "data": ca} if _has(ca) else None,
                           {"name": "Tổng tài sản", "data": ta}) if s]
        out.append(_chart("asset_structure", "B", "Cơ cấu tài sản theo năm", "line", ys, ser))
    eq = _col(data, ys, "owners_equity")
    li = _col(data, ys, "liabilities")
    if not _has(li):
        li = _col(data, ys, "total_liabilities")
    if _has(eq) and _has(li):
        out.append(_chart("capital_structure", "B", "Nguồn vốn: nợ và vốn chủ sở hữu",
                          "stacked-bar", ys,
                          [{"name": "Nợ phải trả", "data": li},
                           {"name": "Vốn chủ sở hữu", "data": eq}]))
        de = [None if not e or l is None else round(l / e, 2) for l, e in zip(li, eq)]
        cl, cur = _col(data, ys, "current_liabilities"), _col(data, ys, "current_assets")
        ratio = [None if not c or a is None else round(a / c, 2) for a, c in zip(cur, cl)]
        ser = [{"name": "Nợ / Vốn chủ", "data": de, "axis": "left"}]
        if _has(ratio):
            ser.append({"name": "Thanh toán hiện hành", "data": ratio, "axis": "right"})
        out.append(_chart("leverage_trend", "B", "Đòn bẩy và khả năng thanh toán", "line",
                          ys, ser, unit="lần"))
    return out


# ---------------------------------------------------------------- C · dòng tiền
# Tên item_id phải khớp CHÍNH XÁC với market.db. Đã từng đoán
# "purchase_of_fixed_assets" (không tồn tại) nên biểu đồ dòng tiền tự do lặng lẽ
# không dựng được. Tên thật dài hơn nhiều — xem tests/test_item_ids.py.
_CAPEX = "purchases_of_fixed_assets_and_other_long_term_assets"
# Dạng "inflows_outflows" phủ 1.496 mã; dạng "net_cash_from_*" chỉ 29 mã (nhóm
# đặc thù) nên giữ làm phương án dự phòng.
_CFO = "net_cash_inflows_outflows_from_operating_activities"
_CFI = "net_cash_inflows_outflows_from_investing_activities"
_CFF = "net_cash_inflows_outflows_from_financing_activities"
_CF = (_CFO, _CFI, _CFF, "net_cash_from_operating_activities",
       "net_cash_from_investing_activities", _CAPEX)


def _group_c(conn, symbol) -> list[dict]:
    data = _grab(conn, symbol, "cash_flow", _CF)
    inc = _grab(conn, symbol, "income_statement", ("net_profit_loss_after_tax",))
    ys = _years(data)
    if not ys:
        return []
    cfo = _col(data, ys, _CFO)
    if not _has(cfo):                      # nhóm đặc thù dùng item_id khác
        cfo = _col(data, ys, "net_cash_from_operating_activities")
    cfi = _col(data, ys, _CFI)
    if not _has(cfi):
        cfi = _col(data, ys, "net_cash_from_investing_activities")
    cff = _col(data, ys, _CFF)
    out = []
    if _has(cfo):
        ser = [{"name": "Kinh doanh", "data": cfo}]
        if _has(cfi):
            ser.append({"name": "Đầu tư", "data": cfi})
        if _has(cff):
            ser.append({"name": "Tài chính", "data": cff})
        out.append(_chart("cashflow_year", "C", "Ba dòng tiền theo năm", "bar", ys, ser,
                          note="Kinh doanh dương và bù được đầu tư là dấu hiệu tự chủ vốn."))
        npf = _col(inc, ys, "net_profit_loss_after_tax")
        if _has(npf):
            out.append(_chart(
                "cfo_vs_profit", "C", "Tiền thật so với lợi nhuận ghi sổ", "line", ys,
                [{"name": "Dòng tiền kinh doanh", "data": cfo},
                 {"name": "Lợi nhuận sau thuế", "data": npf}],
                note="Lợi nhuận cao mà tiền không về là dấu hiệu cần soi kỹ."))
        capex = _col(data, ys, _CAPEX)
        if _has(capex):
            fcf = [None if a is None or b is None else round(a - abs(b), 2)
                   for a, b in zip(cfo, capex)]
            if _has(fcf):
                out.append(_chart("fcf_year", "C", "Dòng tiền tự do (kinh doanh − đầu tư TSCĐ)",
                                  "bar", ys, [{"name": "FCF", "data": fcf}]))
    return out


# ---------------------------------------------------------------- D · hiệu quả sinh lời
def _group_d(conn, symbol) -> list[dict]:
    inc = _grab(conn, symbol, "income_statement",
                (*_REV, "net_profit_loss_after_tax", "attributable_to_parent_company"))
    bal = _grab(conn, symbol, "balance_sheet", ("total_assets", "owners_equity"))
    ys = [p for p in _years(inc) if p in bal]
    if len(ys) < 2:
        return []
    rev_k = _rev_key(inc, ys)
    out, roe, roa, nm, at, lev = [], [], [], [], [], []
    for p in ys:
        i, b = inc.get(p, {}), bal.get(p, {})
        npf = i.get("attributable_to_parent_company") or i.get("net_profit_loss_after_tax")
        eq, ta = b.get("owners_equity"), b.get("total_assets")
        rv = i.get(rev_k) if rev_k else None
        roe.append(round(npf / eq * 100, 2) if npf and eq else None)
        roa.append(round(npf / ta * 100, 2) if npf and ta else None)
        nm.append(round(npf / rv * 100, 2) if npf and rv else None)
        at.append(round(rv / ta, 2) if rv and ta else None)
        lev.append(round(ta / eq, 2) if ta and eq else None)
    if _has(roe):
        ser = [{"name": "ROE", "data": roe}]
        if _has(roa):
            ser.append({"name": "ROA", "data": roa})
        out.append(_chart("return_trend", "D", "Hiệu quả sinh lời theo năm", "line", ys,
                          ser, unit="%"))
    if _has(nm) and _has(at) and _has(lev):
        # NHÃN PHẢI GHI RÕ "cổ đông công ty mẹ": DuPont dùng lợi nhuận phần công ty
        # mẹ (đúng với mẫu số vốn chủ), còn biểu đồ `margin_trend` dùng LNST toàn
        # phần. Hai con số khác nhau là đúng — nhưng nếu cùng gọi "biên lãi ròng"
        # thì người xem thấy 13,4% ở đây và 16,0% ở kia, tưởng hệ thống mâu thuẫn.
        out.append(_chart(
            "dupont_trend", "D", "Phân rã DuPont: ROE đến từ đâu", "line", ys,
            [{"name": "Biên lãi ròng — cổ đông công ty mẹ (%)", "data": nm},
             {"name": "Vòng quay tài sản (lần)", "data": at},
             {"name": "Hệ số nhân vốn (lần)", "data": lev}], unit="hỗn hợp",
            note="ROE ≈ tích ba đường. Nếu ROE tăng chủ yếu nhờ hệ số nhân vốn thì "
                 "đó là tăng nhờ vay thêm, không phải nhờ hiệu quả. Biên ở đây tính "
                 "trên phần lợi nhuận của cổ đông công ty mẹ nên thấp hơn biên ròng "
                 "toàn phần ở biểu đồ Biên lãi."))
    return out


# ---------------------------------------------------------------- E · định giá
def _group_e(conn, symbol) -> list[dict]:
    data = _grab(conn, symbol, "ratio", ("pe_ratio", "pb_ratio"))
    per = sorted(data)[-16:]
    out = []
    for item, cid, lab in (("pe_ratio", "pe_band", "P/E"), ("pb_ratio", "pb_band", "P/B")):
        vals = _col(data, per, item, scale=1)
        pts = [v for v in vals if v is not None and v > 0]
        if len(pts) < 4:
            continue
        s = sorted(pts)
        med = s[len(s) // 2]
        p20, p80 = s[int(len(s) * 0.2)], s[min(len(s) - 1, int(len(s) * 0.8))]
        out.append(_chart(
            cid, "E", f"{lab} qua các kỳ so với dải lịch sử của chính mã", "band", per,
            [{"name": lab, "data": vals},
             {"name": "Trung vị", "data": [med] * len(per), "kind": "line"},
             {"name": "Vùng thường gặp (P20–P80)", "data": [[p20, p80]] * len(per),
              "kind": "band"}],
            unit="lần", source="market.db · financials (ratio)",
            note="Thống kê mô tả vị trí so với quá khứ — KHÔNG phải nhận định rẻ/đắt."))
    return out


# ---------------------------------------------------------------- F · giá & thị trường
def _group_f(conn, symbol) -> list[dict]:
    rows = conn.execute(
        "SELECT time, close, volume FROM price WHERE symbol=? AND close IS NOT NULL "
        "ORDER BY time", (symbol,)).fetchall()
    rows = rows[-_MAX_PRICE_POINTS:]
    if len(rows) < 20:
        return []
    x = [str(r[0])[:10] for r in rows]
    close = [round(r[1], 2) for r in rows]
    vol = [int(r[2] or 0) for r in rows]
    out = [_chart("price_volume", "F", "Diễn biến giá và khối lượng", "price", x,
                  [{"name": "Giá đóng cửa", "data": close, "kind": "line", "axis": "left"},
                   {"name": "Khối lượng", "data": vol, "kind": "bar", "axis": "right"}],
                  unit="nghìn đồng / cổ phiếu", source="market.db · price")]

    # F3 — so với VNINDEX, quy cả hai về mốc 100 để nhìn được ai hơn ai.
    idx = dict(conn.execute(
        "SELECT time, close FROM index_ohlc WHERE code='VNINDEX' AND close IS NOT NULL"))
    pair = [(d, c, idx[d]) for d, c in zip(x, close) if d in idx]
    if len(pair) >= 30:
        b0, i0 = pair[0][1], pair[0][2]
        out.append(_chart(
            "vs_vnindex", "F", "Mã so với VNINDEX (cùng quy về 100)", "line",
            [p[0] for p in pair],
            [{"name": symbol, "data": [round(p[1] / b0 * 100, 2) for p in pair]},
             {"name": "VNINDEX", "data": [round(p[2] / i0 * 100, 2) for p in pair]}],
            unit="điểm (mốc 100)", source="market.db · price + index_ohlc",
            note="Đường nào cao hơn nghĩa là tăng nhiều hơn kể từ mốc đầu kỳ."))

    # F2 — chấm sự kiện lên trục giá: trả kèm mốc để giao diện gắn markPoint.
    ev = conn.execute(
        "SELECT public_date, event_name, title FROM events WHERE symbol=? "
        "AND public_date >= ? ORDER BY public_date", (symbol, x[0])).fetchall()
    marks = [{"date": str(d)[:10], "label": (k or "")[:40], "text": (t or k or "")[:110]}
             for d, k, t in ev if str(d)[:10] in set(x)]
    if marks:
        c = _chart("price_events", "F", "Giá và các sự kiện doanh nghiệp", "price", x,
                   [{"name": "Giá đóng cửa", "data": close}],
                   unit="nghìn đồng / cổ phiếu", source="market.db · price + events",
                   note="Mỗi chấm là một công bố — xem giá phản ứng thế nào.")
        c["marks"] = marks[-40:]
        out.append(c)

    # F7 — phân bố mật độ giá: giá hay dừng ở vùng nào trong 1 năm qua.
    lo, hi = min(close), max(close)
    if hi > lo:
        n = 12
        step = (hi - lo) / n
        buckets = [0] * n
        for v in close:
            buckets[min(n - 1, int((v - lo) / step))] += 1
        out.append(_chart(
            "price_distribution", "F", "Giá đã dừng ở vùng nào nhiều nhất", "histogram",
            [f"{lo + i * step:,.1f}–{lo + (i + 1) * step:,.1f}" for i in range(n)],
            [{"name": "Số phiên", "data": buckets}], unit="phiên",
            source="market.db · price"))
    return out


# ---------------------------------------------------------------- G · cổ tức
def _group_g(conn, symbol) -> list[dict]:
    rows = conn.execute(
        "SELECT public_date, value_per_share FROM events WHERE symbol=? "
        "AND event_name LIKE '%cổ tức bằng tiền%' AND value_per_share > 0 "
        "ORDER BY public_date", (symbol,)).fetchall()
    if not rows:
        return []
    by_year: dict = {}
    for d, v in rows:
        by_year[str(d)[:4]] = by_year.get(str(d)[:4], 0) + v
    ys = sorted(by_year)[-6:]
    if len(ys) < 2:
        return []
    return [_chart("dividend_year", "G", "Cổ tức tiền mặt theo năm", "bar", ys,
                   [{"name": "Cổ tức", "data": [round(by_year[y]) for y in ys]}],
                   unit="đồng/cổ phiếu", source="market.db · events",
                   note="Tính theo năm công bố chốt quyền, gộp mọi đợt trong năm.")]


# ---------------------------------------------------------------- I · tổng hợp
def _group_i(conn, symbol) -> list[dict]:
    rows = conn.execute(
        "SELECT public_date, event_name, title FROM events WHERE symbol=? "
        "ORDER BY public_date DESC LIMIT 20", (symbol,)).fetchall()
    if len(rows) < 3:
        return []
    items = [{"date": str(d)[:10], "kind": k or "", "text": (t or k or "")[:120]}
             for d, k, t in rows]
    c = _chart("event_timeline", "I", "Dòng thời gian sự kiện doanh nghiệp", "timeline",
               [i["date"] for i in items], [{"name": "Sự kiện", "data": items}],
               unit="", source="market.db · events")
    return [c]


# ---------------------------------------------------------------- P2 · phần bổ sung
# 11 biểu đồ mở khoá sau khi C1–C7 và B4 xong. Bỏ "khối ngoại lũy kế" vì
# foreign_history.jsonl chỉ có ~4 dòng/mã — quá mỏng để dựng chuỗi.

_RATIO_DAYS = ("days_of_inventory_on_hand", "days_of_sales_outstanding",
               "number_of_days_of_payables", "beta")


def _group_a2(conn, symbol) -> list[dict]:
    """A5 cùng quý năm trước + A6 heatmap mùa vụ — đều dựa trên C1."""
    data = _grab(conn, symbol, "income_statement", _INC)
    qs = sorted(p for p in data if not _is_year(p))
    ys = _years(data)
    rev_k = _rev_key(data, qs + ys)
    if not rev_k or len(qs) < 2:
        return []
    out = []

    # A5: quý mới nhất so CÙNG QUÝ năm trước. Nếu kỳ đó không được công bố riêng,
    # suy ra bằng FY − 3 quý còn lại (C1) và ghi rõ là số suy ra.
    last = qs[-1]
    y, qn = int(last[:4]), int(last[-1])
    prev, fy = f"{y - 1}-Q{qn}", str(y - 1)
    others = [f"{y - 1}-Q{i}" for i in (1, 2, 3, 4) if i != qn]
    cur = data.get(last, {}).get(rev_k)
    ref, derived = data.get(prev, {}).get(rev_k), False
    if ref is None and data.get(fy, {}).get(rev_k) and all(data.get(o, {}).get(rev_k) for o in others):
        ref = data[fy][rev_k] - sum(data[o][rev_k] for o in others)
        derived = True
    if cur and ref:
        out.append(_chart(
            "yoy_same_quarter", "A", f"Quý {last} so với cùng quý năm trước", "bar",
            [prev + (" (suy ra)" if derived else ""), last],
            [{"name": "Doanh thu", "data": [round(ref / BN, 2), round(cur / BN, 2)]}],
            note=("Số kỳ trước suy ra từ báo cáo năm trừ ba quý còn lại — không phải "
                  "số công bố riêng." if derived else
                  "So cùng quý để loại yếu tố mùa vụ, khác với so quý liền trước.")))

    # A6: heatmap doanh thu theo quý × năm — nhìn ra quý cao điểm của doanh nghiệp.
    cells, years = [], sorted({p[:4] for p in qs})
    for yy in years:
        for qi in (1, 2, 3, 4):
            v = data.get(f"{yy}-Q{qi}", {}).get(rev_k)
            if v is not None:
                cells.append({"row": yy, "col": f"Q{qi}", "v": round(v / BN, 2)})
    if len(cells) >= 6 and len(years) >= 2:
        out.append(_chart("seasonality", "A", "Doanh thu theo quý qua các năm", "heatmap",
                          ["Q1", "Q2", "Q3", "Q4"],
                          [{"name": "Doanh thu", "data": cells, "rows": years}],
                          note="Ô đậm là quý cao điểm — lý do so quý liền trước dễ gây hiểu nhầm."))
    return out


def _group_b2(conn, symbol) -> list[dict]:
    """B4 số ngày vốn lưu động + B5 chu kỳ tiền mặt (nguồn: bảng ratio, kỳ NĂM)."""
    data = _grab(conn, symbol, "ratio", _RATIO_DAYS)
    ys = _years(data, 5)
    if len(ys) < 2:
        return []
    dio, dso, dpo = (_col(data, ys, k, scale=1) for k in _RATIO_DAYS[:3])
    if not (_has(dio) and _has(dso)):
        return []                       # ngân hàng không có tồn kho/phải thu kiểu này
    ccc = [None if None in (a, b, c) else round(a + b - c, 1)
           for a, b, c in zip(dio, dso, dpo)]
    out = [_chart("working_capital_days", "B", "Vốn lưu động quy ra số ngày", "line", ys,
                  [{"name": "Tồn kho", "data": dio},
                   {"name": "Thu tiền khách hàng", "data": dso},
                   {"name": "Trả tiền nhà cung cấp", "data": dpo}],
                  unit="ngày", source="market.db · financials (ratio)")]
    if _has(ccc):
        out.append(_chart("cash_cycle", "B", "Chu kỳ tiền mặt theo năm", "bar", ys,
                          [{"name": "Chu kỳ tiền mặt", "data": ccc}], unit="ngày",
                          source="market.db · financials (ratio)",
                          note="Tồn kho + thu tiền − trả tiền. Càng ngắn thì vốn quay "
                               "vòng càng nhanh; tăng dần là dấu hiệu bị chôn vốn."))
    return out


def _peer_stats(conn, symbol):
    """(ngành, {mã: (roe, pe)}) của các mã cùng ngành — dùng cho D3/E3/H1."""
    try:
        row = conn.execute("SELECT sector FROM companies WHERE symbol=?", (symbol,)).fetchone()
    except sqlite3.Error:
        return None, {}          # DB rút gọn không có bảng `companies` → bỏ nhóm này
    sector = row[0] if row else None
    if not sector:
        return None, {}
    syms = [r[0] for r in conn.execute(
        "SELECT symbol FROM companies WHERE sector=?", (sector,))]
    if len(syms) < 5:
        return sector, {}
    out = {}
    q = ("SELECT symbol, item_id, value FROM financials WHERE statement='ratio' "
         "AND item_id IN ('roe','pe_ratio') AND period >= '2024' AND value IS NOT NULL "
         f"AND symbol IN ({','.join('?' * len(syms))})")
    tmp: dict = {}
    for s, iid, v in conn.execute(q, syms):
        tmp.setdefault(s, {})[iid] = v
    for s, d in tmp.items():
        if d.get("roe") is not None:
            out[s] = (d["roe"], d.get("pe_ratio"))
    return sector, out


def _group_peer(conn, symbol) -> list[dict]:
    """D3 vị trí trên phân phối ngành · E3 tán xạ P/E×ROE · H1 xếp hạng."""
    sector, stats = _peer_stats(conn, symbol)
    if not stats or symbol not in stats or len(stats) < 5:
        return []
    roes = sorted(v[0] for v in stats.values())
    mine = stats[symbol][0]
    rank = sum(1 for r in roes if r > mine) + 1
    out = [_chart(
        "roe_distribution", "D", f"ROE của {symbol} trên phân phối ngành {sector}",
        "histogram", [f"{r:.0f}" for r in roes],
        [{"name": "ROE từng mã", "data": roes}], unit="%",
        source="market.db · financials (ratio) + companies",
        note=f"{symbol} đứng thứ {rank}/{len(roes)} về ROE trong ngành.")]

    pts = [{"x": v[1], "y": v[0], "label": s, "self": s == symbol}
           for s, v in stats.items() if v[1] is not None and 0 < v[1] < 100]
    if len(pts) >= 5:
        out.append(_chart(
            "sector_scatter", "E", f"Ngành {sector}: định giá và hiệu quả", "scatter",
            [], [{"name": "Mã trong ngành", "data": pts}], unit="P/E (ngang) × ROE % (dọc)",
            source="market.db · financials (ratio) + companies",
            note="Mỗi chấm là một doanh nghiệp; chấm được tô đậm là mã đang xem."))
    return out


def _group_f2(conn, symbol) -> list[dict]:
    """F4 sụt sâu nhất theo thời gian — bổ sung cho nhóm giá."""
    rows = conn.execute(
        "SELECT time, close FROM price WHERE symbol=? AND close IS NOT NULL ORDER BY time",
        (symbol,)).fetchall()
    rows = rows[-_MAX_PRICE_POINTS:]
    if len(rows) < 40:
        return []
    x = [str(r[0])[:10] for r in rows]
    peak, dd = None, []
    for _, c in rows:
        peak = c if peak is None else max(peak, c)
        dd.append(round((c - peak) / peak * 100, 2) if peak else None)
    return [_chart("drawdown", "F", "Khoảng cách so với đỉnh gần nhất", "line", x,
                   [{"name": "Sụt so đỉnh", "data": dd}], unit="%",
                   source="market.db · price",
                   note="Luôn ≤ 0. Chạm 0 nghĩa là giá đang ở đỉnh của giai đoạn.")]


# Tên nhóm hiện trên giao diện. `group` của từng biểu đồ trỏ vào đây.
GROUP_TITLES = {
    "A": "Kết quả kinh doanh",
    "B": "Tài sản & nguồn vốn",
    "C": "Dòng tiền",
    "D": "Hiệu quả sinh lời",
    "E": "Định giá",
    "F": "Giá & thị trường",
    "G": "Cổ tức",
    "I": "Tổng hợp",
}

# Danh sách hàm dựng. Một hàm có thể phát ra biểu đồ thuộc NHIỀU nhóm
# (vd `_group_peer` trả cả D và E) nên không gắn cứng nhóm ở đây.
_BUILDERS = (
    ("A", _group_a), ("A+", _group_a2),
    ("B", _group_b), ("B+", _group_b2),
    ("C", _group_c),
    ("D", _group_d), ("peer", _group_peer),
    ("E", _group_e),
    ("F", _group_f), ("F+", _group_f2),
    ("G", _group_g),
    ("I", _group_i),
)


def build(db_path: str, symbol: str) -> dict:
    """Toàn bộ biểu đồ dựng được cho 1 mã. Không gọi AI, không crawl."""
    symbol = (symbol or "").strip().upper()
    charts, errors = [], {}
    conn = _ro(db_path)
    try:
        for key, fn in _BUILDERS:
            try:
                charts.extend(fn(conn, symbol))
            except Exception as exc:            # 1 nhóm hỏng không được giết cả trang
                errors[key] = str(exc)[:160]
    finally:
        conn.close()
    # Giữ thứ tự A→I của GROUP_TITLES, chỉ liệt kê nhóm thực sự có biểu đồ.
    return {
        "symbol": symbol,
        "charts": charts,
        "groups": [{"key": k, "title": t} for k, t in GROUP_TITLES.items()
                   if any(c["group"] == k for c in charts)],
        "count": len(charts),
        "errors": errors,
        "note": ("Mọi số liệu lấy trực tiếp từ market.db. Thống kê mô tả quá khứ, "
                 "KHÔNG phải dự báo hay khuyến nghị đầu tư."),
    }
