"""Engine phân tích cơ bản định lượng — tính bằng Python, không phụ thuộc AI.

Đọc các file BCTC JSON (đã gộp năm + quý) của một công ty và tính:
- Doanh thu / LNST mới nhất + tăng trưởng YoY (quý so cùng kỳ, năm so năm)
- Biên lãi gộp/ròng, ROE/ROA
- Định giá: P/E, P/B, P/S, EV/EBITDA, tỷ suất cổ tức
- Đòn bẩy: Nợ/VCSH, thanh toán hiện hành
- Điểm Piotroski F-Score (0–9) và điểm sức khỏe tổng hợp 0–100
- Nhận định định giá sơ bộ (rẻ / hợp lý / đắt)
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config, raw_ratios, sector_metrics, earnings_quality


def _load(cdir: Path, statement: str) -> list[dict]:
    p = cdir / "financials" / f"{statement}.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("records", [])
    except Exception:
        return []


def _series(records: list[dict], item_id: str, ptype: str) -> list[tuple[str, float]]:
    """Chuỗi (period, value) cho 1 chỉ tiêu, lọc theo loại kỳ (Y/Q), sắp tăng dần."""
    out = []
    for r in records:
        if r.get("item_id") == item_id and r.get("period_type", "Y") == ptype:
            v = r.get("value")
            if isinstance(v, (int, float)):
                out.append((str(r["period"]), float(v)))
    out.sort(key=lambda x: x[0])
    return out


def _last(series, n=1):
    return series[-n][1] if len(series) >= n else None


def _yoy(series, lag) -> float | None:
    """Tăng trưởng % giữa kỳ mới nhất và kỳ cách `lag` bước."""
    if len(series) < lag + 1:
        return None
    cur, prev = series[-1][1], series[-1 - lag][1]
    if prev == 0:
        return None
    return (cur - prev) / abs(prev) * 100.0


def _pct(v):
    """Chuẩn hóa giá trị tỷ lệ: vnstock có khi để 0.25 = 25%."""
    if v is None:
        return None
    return v * 100.0 if -1.5 < v < 1.5 else v


def _latest_period(records: list[dict]) -> str | None:
    """Kỳ mới nhất (chuỗi period) trong 1 statement — mốc 'tươi' để so ratio cũ."""
    ps = [str(r.get("period")) for r in records if r.get("period")]
    return max(ps) if ps else None


def _year_of(period: str | None) -> int | None:
    """Năm (int) trích từ period 'YYYY' hoặc 'YYYY-QN'. None nếu không nhận diện."""
    if not period:
        return None
    head = str(period)[:4]
    return int(head) if head.isdigit() else None


# ---------------------------------------------------------------- C1: YoY CÙNG QUÝ
# Bối cảnh (đo thật trên 1.525 thư mục công ty, 2026-07-27): chỉ 21 mã có sẵn quý
# cùng kỳ năm trước → `_yoy(rev_q, 4)` gần như luôn None, prompt chỉ còn QoQ.
# QoQ Q1-so-Q4 âm ở 67,4% thị trường vì mùa vụ (trung vị −10,6%) trong khi YoY
# cùng quý có trung vị +12,0% → QoQ đẩy AI về kết luận "suy giảm" một cách hệ thống.
# Vì số quý là RỜI RẠC (không lũy kế) và có sẵn số cả năm, suy ra được quý thiếu:
#     Q1(y-1) = FY(y-1) − Q2(y-1) − Q3(y-1) − Q4(y-1)
# Chỉ áp dụng cho chỉ tiêu DÒNG CHẢY (income_statement / cash_flow), TUYỆT ĐỐI
# không áp cho balance_sheet (số dư thời điểm, không cộng dồn được).
_QTR_TOL = 0.02   # |FY − Σ4 quý| / |FY| vượt ngưỡng này ⇒ bỏ hẳn, không suy diễn


def _quarter_key(period: str | None) -> tuple[int, int] | None:
    """'2025-Q3' → (2025, 3). None nếu không phải nhãn kỳ quý hợp lệ."""
    s = str(period or "")
    if len(s) < 7 or not s[:4].isdigit() or s[4] != "-" or s[5].upper() != "Q":
        return None
    if not s[6].isdigit():
        return None
    q = int(s[6])
    return (int(s[:4]), q) if 1 <= q <= 4 else None


def _growth(cur, prev) -> float | None:
    """Tăng trưởng % giữa 2 giá trị. prev = 0/None → None (không trả 0 giả)."""
    if cur is None or prev is None or prev == 0:
        return None
    return (cur - prev) / abs(prev) * 100.0


def _q_map(series) -> dict[tuple[int, int], float]:
    return {k: v for k, v in ((_quarter_key(p), v) for p, v in series) if k is not None}


def _y_map(series) -> dict[int, float]:
    return {k: v for k, v in ((_year_of(p), v) for p, v in series) if k is not None}


def _quarters_additive(qmap: dict, ymap: dict) -> bool:
    """Kiểm chứng giả định "4 quý cộng lại = cả năm" trên chính mã này.

    Lấy năm GẦN NHẤT có đủ 4 quý + có FY, đòi |FY − Σ4 quý| / |FY| ≤ 2%. Lệch hơn
    ⇒ số quý của mã này không rời rạc (lũy kế / lẫn đơn vị) ⇒ BỎ HẲN, không suy ra.
    Không có năm nào kiểm được ⇒ True (không có bằng chứng phản đối; nhánh gọi vẫn
    còn guard lệch-năm và guard thiếu quý)."""
    for year in sorted(ymap, reverse=True):
        qs = [qmap.get((year, k)) for k in (1, 2, 3, 4)]
        if any(v is None for v in qs):
            continue
        fy = ymap[year]
        if not fy:
            continue
        return abs(fy - sum(qs)) / abs(fy) <= _QTR_TOL
    return True


def _yoy_same_quarter(records: list[dict], item_id: str) -> tuple[float | None, str | None]:
    """Tăng trưởng % của quý mới nhất so với CÙNG QUÝ năm trước.

    Trả (value, source) với source ∈ {"reported", "derived", None}:
    - "reported": quý cùng kỳ có sẵn trong BCTC → ưu tiên tuyệt đối.
    - "derived" : suy ra bằng FY(y-1) − 3 quý còn lại của y-1.
    - None      : không đủ dữ liệu hoặc bị guard chặn (KHÔNG bịa số, KHÔNG trả 0).

    Guard: (a) quý mới nhất lệch năm >1 so với FY mới nhất → bỏ (ca quý đóng băng
    2018 trong khi FY đã 2025); (b) thiếu bất kỳ quý nào trong 3 quý còn lại → bỏ;
    (c) FY(y-1) thiếu hoặc bằng 0 → bỏ; (d) `_quarters_additive` lệch >2% → bỏ."""
    q = _series(records, item_id, "Q")
    if not q:
        return None, None
    cur_p, cur_v = q[-1]
    tk = _quarter_key(cur_p)
    if tk is None:
        return None, None
    year, qn = tk
    qmap = _q_map(q)

    prev = qmap.get((year - 1, qn))
    if prev is not None:
        g = _growth(cur_v, prev)
        return (g, "reported") if g is not None else (None, None)

    ymap = _y_map(_series(records, item_id, "Y"))
    if not ymap:
        return None, None
    # (a) Quý và FY lệch năm → chuỗi quý đã đóng băng, không được ghép với FY.
    if abs(year - max(ymap)) > 1:
        return None, None
    fy_prev = ymap.get(year - 1)
    if not fy_prev:
        return None, None
    others = [qmap.get((year - 1, k)) for k in (1, 2, 3, 4) if k != qn]
    if any(v is None for v in others):
        return None, None
    if not _quarters_additive(qmap, ymap):
        return None, None
    g = _growth(cur_v, fy_prev - sum(others))
    return (g, "derived") if g is not None else (None, None)


# ---------------------------------------------------------------- C3: TTM
def _ttm_sum(series, back: int = 0) -> float | None:
    """Tổng 4 quý LIÊN TIẾP, lùi `back` quý so với quý mới nhất.

    Đòi kỳ liên tục (không hụt quý) — hụt ⇒ None, tuyệt đối không trộn số năm vào.
    Đo thật: 1.145 mã đủ 4 quý liên tiếp (back=0); chỉ 1 mã đủ 8 quý (back=4) nên
    TTM-so-TTM-cùng-kỳ gần như luôn None."""
    ks = [(k, v) for k, v in ((_quarter_key(p), v) for p, v in series) if k is not None]
    if len(ks) < 4 + back:
        return None
    win = ks[len(ks) - 4 - back: len(ks) - back]
    idx = [y * 4 + q for (y, q), _ in win]
    if idx != list(range(idx[0], idx[0] + 4)):
        return None
    return sum(v for _, v in win)


def _latest_close_vnd(cdir: Path) -> float | None:
    """Giá đóng cửa mới nhất, quy về ĐỒNG. market/price.json để giá theo nghìn đồng
    (vd 62.9); >1000 coi như đã là đồng (không mã nào có giá >1000 nghìn đồng)."""
    p = cdir / "market" / "price.json"
    if not p.exists():
        return None
    try:
        items = json.loads(p.read_text(encoding="utf-8")).get("items", [])
    except Exception:
        return None
    rows = [(str(r.get("time")), r.get("close")) for r in items
            if isinstance(r.get("close"), (int, float))]
    if not rows:
        return None
    rows.sort(key=lambda x: x[0])
    c = float(rows[-1][1])
    return c * 1000.0 if 0 < c < 1000 else c


def compute(symbol: str, sector: str | None = None) -> dict:
    cdir = config.company_dir(symbol)
    inc = _load(cdir, "income_statement")
    cf = _load(cdir, "cash_flow")
    rat = _load(cdir, "ratio")
    bal = _load(cdir, "balance_sheet")

    # raw phải tính TRƯỚC khối doanh thu: cần cờ is_bank để chọn ĐÚNG dòng doanh thu.
    raw = raw_ratios.compute(inc, bal, cf)

    # ---- Doanh thu & lợi nhuận (quý cho YoY, năm cho xu hướng)
    # FIX: ngân hàng KHÔNG có `net_sales` (kiểm VCB/CTG: chỉ có total_operating_income
    # và net_interest_income) → trước đây toàn bộ ngân hàng có revenue.latest = None.
    # Cờ bank lấy từ raw_ratios.is_bank (dựa cơ cấu báo cáo), không tự nhận diện lại.
    rev_item = "total_operating_income" if raw["is_bank"] else "net_sales"
    rev_q = _series(inc, rev_item, "Q")
    rev_y = _series(inc, rev_item, "Y")
    np_q = _series(inc, "net_profit_loss_after_tax", "Q")
    np_y = _series(inc, "net_profit_loss_after_tax", "Y")
    gross_q = _series(inc, "gross_profit", "Q")
    eps_q = _series(inc, "eps_basic_vnd", "Q")

    # C1: YoY CÙNG QUÝ (reported, hoặc suy ra FY − 3 quý). Đây mới là thước đo
    # tăng trưởng sạch mùa vụ; `qoq` giữ nguyên tên/ý nghĩa nhưng KHÔNG còn là số
    # đại diện cho tăng trưởng (Q1-so-Q4 âm ở 2/3 thị trường chỉ vì mùa vụ).
    rev_yoy_q, rev_yoy_src = _yoy_same_quarter(inc, rev_item)
    np_yoy_q, np_yoy_src = _yoy_same_quarter(inc, "net_profit_loss_after_tax")

    # Bản community giới hạn 4 kỳ → YoY quý (lag 4) thường thiếu dữ liệu;
    # bổ sung QoQ (lag 1) luôn lấy được. YoY năm (lag 1 năm) dùng cho xu hướng.
    # Nếu KHÔNG có dữ liệu quý (dữ liệu cũ chỉ có năm) → fallback dùng chuỗi năm.
    rev_main = rev_q or rev_y
    np_main = np_q or np_y
    revenue = {
        "latest": _last(rev_main), "period": rev_main[-1][0] if rev_main else None,
        "yoy_q": rev_yoy_q, "qoq": _yoy(rev_q, 1), "yoy_y": _yoy(rev_y, 1),
        "yoy_q_source": rev_yoy_src,
        # TTM = tổng 4 quý liên tiếp gần nhất. ttm_yoy cần 8 quý → hầu như luôn None,
        # giữ khoá cho tương lai khi crawl đủ lịch sử quý.
        "ttm": _ttm_sum(rev_q),
        "ttm_yoy": _growth(_ttm_sum(rev_q), _ttm_sum(rev_q, back=4)),
        # Dòng doanh thu đang đọc — tầng trên cần biết để đặt nhãn đúng
        # ("Tổng thu nhập hoạt động" với ngân hàng, "Doanh thu thuần" với DN thường).
        "item_id": rev_item,
        "trend_q": [v for _, v in rev_main[-8:]],
        # nhãn kỳ đi kèm trend_q để UI vẽ trục (vd "2025-Q4")
        "trend_periods": [p for p, _ in rev_main[-8:]],
    }
    net_profit = {
        "latest": _last(np_main), "period": np_main[-1][0] if np_main else None,
        "yoy_q": np_yoy_q, "qoq": _yoy(np_q, 1), "yoy_y": _yoy(np_y, 1),
        "yoy_q_source": np_yoy_src,
        "ttm": _ttm_sum(np_q),
        "ttm_yoy": _growth(_ttm_sum(np_q), _ttm_sum(np_q, back=4)),
        "trend_q": [v for _, v in np_main[-8:]],
        "trend_periods": [p for p, _ in np_main[-8:]],
    }

    # Bảng `ratio` đóng băng ở 2018 cho ĐA SỐ mã (bug nguồn VCI cũ) hoặc thiếu hẳn.
    # KHÔNG chỉ kiểm None: giá trị 2018 vẫn non-None nhưng đã CŨ 5+ năm → phải coi là
    # "stale" và ưu tiên raw. Mốc tươi lấy từ báo cáo gốc (income statement). rget()
    # chỉ trả giá trị ratio khi kỳ mới nhất của nó KHÔNG cũ hơn mốc quá 1 năm.
    # Xem memory ratio-table-stale.
    _fresh_period = _latest_period(inc)          # vd "2026-Q1" / "2025"
    _fresh_year = _year_of(_fresh_period)

    def rget(item):
        s = _series(rat, item, "Q") or _series(rat, item, "Y")
        if not s:
            return None
        latest_p = s[-1][0]
        # Ratio cũ hơn báo cáo gốc >1 năm → coi như không có (để raw lấp).
        if _fresh_year is not None:
            ly = _year_of(latest_p)
            if ly is not None and ly < _fresh_year - 1:
                return None
        return s[-1][1]

    def rget_y(item):
        """Như rget nhưng ƯU TIÊN kỳ NĂM. Dùng cho roe/roa/roic: KBS trả các chỉ số
        này ở dạng % NĂM chuẩn (vd 6.06 = 6.06%); giá trị quý là đóng góp riêng quý
        (chưa niên hóa, vd 1.3) nên nếu ưu tiên quý sẽ hiểu sai là ROE thấp bất thường.
        Lấy năm để nhất quán với sector_metrics (cùng nguồn KBS annual)."""
        s = _series(rat, item, "Y") or _series(rat, item, "Q")
        if not s:
            return None
        latest_p = s[-1][0]
        if _fresh_year is not None:
            ly = _year_of(latest_p)
            if ly is not None and ly < _fresh_year - 1:
                return None
        return s[-1][1]

    def pick(rval, path):
        """Ưu tiên giá trị từ ratio (rval); None thì lấy raw theo đường dẫn 'a.b'."""
        if rval is not None:
            return rval
        cur = raw
        for k in path.split("."):
            cur = cur.get(k) if isinstance(cur, dict) else None
        return cur

    margins = {
        "gross": pick(_pct(rget("gross_margin")), "margins.gross"),
        "net": pick(_pct(rget("net_margin")), "margins.net"),
        "ebit": pick(_pct(rget("ebit_margin")), "margins.ebit"),
    }
    profitability = {
        # FIX(2026-07-22): KBS trả roe/roa/roic dạng % SẴN → KHÔNG bọc _pct (heuristic
        # "-1.5<v<1.5 ⇒ ×100" biến giá trị nhỏ như quý=1.3 thành 130). Ưu tiên kỳ NĂM
        # (rget_y) để nhất quán với sector_metrics. Xem docs/BAO-CAO-DU-AN.md §5.
        "roe": pick(rget_y("roe"), "profitability.roe"),
        "roa": pick(rget_y("roa"), "profitability.roa"),
        # KBS KHÔNG có item_id "roic" — chỉ có "return_on_capital_employed_roce"
        # (9.525 bản ghi). Trước đây hỏi "roic" nên luôn ra None và prompt báo
        # "n/a", khiến AI viết "không đủ dữ liệu về ROIC" cho thứ đang có sẵn.
        # ROCE ≠ ROIC (ROCE tính trên vốn dài hạn bình quân) nên đổi luôn TÊN
        # trường, không nhét số ROCE vào nhãn ROIC.
        "roce": pick(rget_y("return_on_capital_employed_roce"), "profitability.roic"),
    }
    valuation = {
        "pe": rget("pe_ratio"), "pb": rget("pb_ratio"), "ps": rget("ps_ratio"),
        # Bảng lưu "ev_ebitda" (9.891 bản ghi), không phải "ev_to_ebitda".
        "ev_ebitda": rget("ev_ebitda"), "ev_ebit": rget("ev_ebit"),
        "dividend_yield": _pct(rget("dividend_yield")),
        "market_cap": rget("market_cap"),
    }
    # Ưu tiên định giá từ VNDirect (nguồn yêu cầu) khi lấy được; lỗi mạng thì giữ vnstock.
    try:
        from . import vndirect
        vv = vndirect.valuation(symbol)
        for k in ("pe", "pb", "ps", "dividend_yield", "market_cap"):
            if vv.get(k) is not None:
                valuation[k] = vv[k]
        valuation["source"] = "vndirect"
    except Exception:
        valuation["source"] = "vnstock"
    # FIX(2026-07-22): KBS trả debt_to_equity dạng % (nhãn "%" ở sector_metrics, vd
    # 49.86 = 49.86% = 0.4986x); raw fallback đã trả hệ số (x). Quy % → x cho nhánh KBS
    # để 1 đơn vị "x" thống nhất (bug cũ: 49.86x sai ~100 lần, làm hỏng cờ đòn bẩy health).
    _de_kbs = rget("debt_to_equity")
    _de_kbs = _de_kbs / 100.0 if _de_kbs is not None else None
    solvency = {
        "debt_to_equity": pick(_de_kbs, "solvency.debt_to_equity"),
        "current_ratio": pick(rget("current_ratio"), "solvency.current_ratio"),
        "financial_leverage": pick(rget("financial_leverage"), "solvency.financial_leverage"),
        # NPL/CAR: nguồn KBS đôi khi có; KHÔNG suy ra từ báo cáo chuẩn nên raw trả None.
        "npl": _pct(rget("npl")), "car": _pct(rget("car")),
    }

    # P1 · Vòng quay vốn & an toàn nợ — bảng `ratio` có 58 chỉ tiêu, trước đây
    # prompt chỉ dùng 2 (P/E, P/B). Toàn bộ dưới đây đã tính sẵn, phủ 1.420–1.502
    # mã, KHÔNG cần crawl thêm. Trả lời 3 câu hệ thống chưa nói được:
    #   "bị chôn vốn bao lâu?"      → chu kỳ tiền mặt
    #   "lãi có phải tiền thật?"    → tỷ lệ dồn tích 2 phương pháp + tiền/VCSH
    #   "lãi suất tăng có trả nổi?" → khả năng trả lãi vay & trả nợ
    # PHẢI dùng rget_y (ưu tiên kỳ NĂM) — CÙNG BẪY đã ghi ở roe/roa phía trên:
    # KBS trả giá trị quý là đóng góp RIÊNG QUÝ, chưa niên hóa. Lấy quý thì vòng
    # quay bị chia 4 và số ngày bị nhân ~4. Đo thật trên FPT:
    #   theo quý (SAI): chu kỳ tiền mặt 182,1 ngày · vòng quay TS 0,24 lần
    #   theo năm (ĐÚNG): chu kỳ tiền mặt  43,2 ngày · vòng quay TS 0,88 lần
    _dio, _dso, _dpo = (rget_y("days_of_inventory_on_hand"),
                        rget_y("days_of_sales_outstanding"),
                        rget_y("number_of_days_of_payables"))
    efficiency = {
        "days_inventory": _dio, "days_receivable": _dso, "days_payable": _dpo,
        # Chu kỳ tiền mặt = tồn kho + thu tiền − trả tiền. Thiếu vế nào thì None,
        # KHÔNG coi vế thiếu là 0 (sẽ ra con số đẹp giả).
        "cash_cycle": (None if None in (_dio, _dso, _dpo)
                       else round(_dio + _dso - _dpo, 1)),
        "turnover_asset": rget_y("total_asset_turnover"),
        "turnover_inventory": rget_y("inventory_turnover"),
        "turnover_receivable": rget_y("receivables_turnover"),
        "interest_coverage": rget_y("interest_coverage"),
        "debt_coverage": rget_y("debt_coverage"),
        "quick_ratio": rget_y("quick_ratio"),
        "cash_ratio": rget_y("cash_ratio"),
        "cash_roe": rget_y("cash_return_on_equity"),
        "cash_roa": rget_y("cash_return_to_assets"),
        # KHÔNG lấy accrual_ratio_* từ bảng ratio: đo trên 6.367 bản ghi từ 2024,
        # chỉ 3,3% khác 0 — cột gần như rỗng. Gửi "dồn tích 0,00%" cho AI còn tệ
        # hơn không gửi vì nó đọc thành "lợi nhuận hoàn toàn là tiền thật".
        # Chỉ tiêu dồn tích THẬT đã có ở khối `earnings_quality` (tính từ raw).
        "period_type": "năm",
    }
    # CFO item_id KHÁC nhau theo ngành: ngân hàng dùng net_cash_from_operating_activities,
    # DN thường dùng net_cash_inflows_outflows_from_operating_activities. Thử id đúng
    # ngành trước, không có thì thử id còn lại (an toàn cho dữ liệu cũ/lẫn lộn).
    cfo_id = raw_ratios.cfo_item_id(raw["is_bank"])
    cfo_y = _series(cf, cfo_id, "Y")
    if not cfo_y:
        cfo_y = _series(cf, raw_ratios.cfo_item_id(not raw["is_bank"]), "Y")
    cfo_latest = _last(cfo_y)
    cash = {
        "cfo_latest": cfo_latest,
        "cfo_vs_profit": (cfo_latest / _last(np_y)) if cfo_latest and _last(np_y) else None,
    }

    fscore, fmax = _piotroski(inc, cf, rat, bal=bal, is_bank=raw["is_bank"])
    health = _health_score(revenue, net_profit, margins, profitability, solvency, cash,
                           is_bank=raw["is_bank"], fscore=fscore, fmax=fmax)
    verdict = _valuation_verdict(valuation)

    # Bộ chỉ tiêu ĐÚNG THEO NGÀNH (bank/non_bank) + chất lượng lợi nhuận. Ngân hàng
    # KHÔNG chấm Z-score/biên gộp; non-bank có tồn kho/phải thu/accrual.
    sector_model = sector_metrics.compute(rat, inc, bal, cf, sector, raw=raw)
    equality = earnings_quality.compute(inc, bal, cf, rat, is_bank=raw["is_bank"])
    val_band = valuation_band(rat, valuation)

    # C3: EPS TTM = tổng eps_basic_vnd 4 quý liên tiếp (VNĐ/CP, không cần số cổ phiếu
    # — bảng ratio không có outstanding_shares cho đa số mã). P/E TTM = giá / EPS TTM;
    # khác P/E của `ratio` (theo kỳ năm) rất xa ở mã có quý đột biến. EPS TTM ≤ 0 →
    # P/E TTM = None (P/E âm không mang nghĩa).
    eps_ttm = _ttm_sum(eps_q)
    close_vnd = _latest_close_vnd(cdir)
    pe_ttm = (close_vnd / eps_ttm) if (close_vnd and eps_ttm and eps_ttm > 0) else None

    return {
        "revenue": revenue, "net_profit": net_profit, "margins": margins,
        "profitability": profitability, "valuation": valuation, "solvency": solvency,
        "efficiency": efficiency,        # P1 · vòng quay vốn & an toàn nợ
        "cash": cash, "eps": _last(eps_q),
        # C3: 12 tháng gần nhất — không lệch như FY2025 (đã cũ 7 tháng) và sạch mùa vụ.
        "eps_ttm": eps_ttm, "pe_ttm": pe_ttm,
        "fscore": fscore, "fscore_max": fmax,
        "health_score": health, "valuation_verdict": verdict,
        # Cờ ngành + chỉ số đặc thù ngân hàng (None nếu không phải bank). NPL/CAR
        # trong bank_metrics luôn None: không suy ra được từ báo cáo chuẩn.
        "is_bank": raw["is_bank"],
        "bank_metrics": raw.get("bank_metrics"),
        "sector_model": sector_model,
        "earnings_quality": equality,
        "valuation_band": val_band,
        "ratio_source": "raw_derived" if rget("net_margin") is None else "ratio_table",
    }


# ---------------------------------------------------------------- F-Score (Piotroski 9 tiêu chí)
def _piotroski(inc, cf, rat, bal=None, is_bank: bool = False) -> tuple[int, int]:
    """Piotroski F-Score ĐẦY ĐỦ 9 tiêu chí, tính TRỰC TIẾP từ báo cáo gốc năm
    (income/balance/cash_flow) thay vì bảng `ratio` (hay đóng băng ở 2018 → trước
    đây chỉ ra /6). Ngân hàng bỏ 2 tiêu chí không áp dụng (biên gộp, thanh khoản
    ngắn hạn) → tối đa 7; doanh nghiệp thường tối đa 9. Tiêu chí pha loãng (#7)
    dùng số cổ phiếu từ ratio table nếu có, thiếu thì bỏ (giảm mẫu số)."""
    from . import raw_ratios
    bal = bal or []

    def yr(records, item, k=1):
        s = raw_ratios._series(records, item, "Y")
        return s[-k][1] if len(s) >= k else None

    def rt(num, den):
        return (num / den) if (num is not None and den not in (None, 0)) else None

    cfo_id = raw_ratios.cfo_item_id(is_bank)
    liab_id = "total_liabilities" if is_bank else "liabilities"
    ni, ni1 = yr(inc, "net_profit_loss_after_tax"), yr(inc, "net_profit_loss_after_tax", 2)
    ta, ta1 = yr(bal, "total_assets"), yr(bal, "total_assets", 2)
    cfo = yr(cf, cfo_id)
    lb, lb1 = yr(bal, liab_id), yr(bal, liab_id, 2)
    ca, ca1 = yr(bal, "current_assets"), yr(bal, "current_assets", 2)
    cl, cl1 = yr(bal, "current_liabilities"), yr(bal, "current_liabilities", 2)
    rv, rv1 = yr(inc, "net_sales"), yr(inc, "net_sales", 2)
    cg, cg1 = yr(inc, "cost_of_sales"), yr(inc, "cost_of_sales", 2)
    sh = yr(rat, "outstanding_shares"); sh1 = yr(rat, "outstanding_shares", 2)

    roa, roa1 = rt(ni, ta), rt(ni1, ta1)
    lev, lev1 = rt(lb, ta), rt(lb1, ta1)
    cr, cr1 = rt(ca, cl), rt(ca1, cl1)
    gm = rt((rv - cg) if (rv is not None and cg is not None) else None, rv)
    gm1 = rt((rv1 - cg1) if (rv1 is not None and cg1 is not None) else None, rv1)
    at, at1 = rt(rv, ta), rt(rv1, ta1)

    crit = [
        (roa is not None, lambda: roa > 0),                              # 1. ROA dương
        (cfo is not None, lambda: cfo > 0),                              # 2. Dòng tiền KD dương
        (roa is not None and roa1 is not None, lambda: roa > roa1),      # 3. ROA tăng
        (cfo is not None and ni is not None, lambda: cfo > ni),          # 4. CFO > LNST (chất lượng LN)
        (lev is not None and lev1 is not None, lambda: lev < lev1),      # 5. Giảm đòn bẩy
        (sh is not None and sh1 is not None, lambda: sh <= sh1),         # 7. Không pha loãng
        (at is not None and at1 is not None, lambda: at > at1),          # 9. Hiệu suất TS tăng
    ]
    if not is_bank:
        crit += [
            (cr is not None and cr1 is not None, lambda: cr > cr1),      # 6. Thanh khoản tăng
            (gm is not None and gm1 is not None, lambda: gm > gm1),      # 8. Biên gộp tăng
        ]

    score = mx = 0
    for have, test in crit:
        if have:
            mx += 1
            try:
                if test():
                    score += 1
            except Exception:
                pass
    return score, mx


# ---------------------------------------------------------------- Health 0-100
def _health_score(rev, npf, margins, prof, solv, cash, is_bank: bool = False,
                  fscore=None, fmax=None) -> int:
    pts, total = 0.0, 0.0

    def add(cond, w):
        nonlocal pts, total
        if cond is None:
            return
        total += w
        if cond:
            pts += w

    rev_g = next((g for g in (rev["yoy_q"], rev["yoy_y"], rev["qoq"]) if g is not None), None)
    np_g = next((g for g in (npf["yoy_q"], npf["yoy_y"], npf["qoq"]) if g is not None), None)
    add(rev_g is not None and rev_g > 0, 15)        # tăng trưởng doanh thu
    add(np_g is not None and np_g > 0, 15)          # tăng trưởng lợi nhuận
    add(prof["roe"] is not None and prof["roe"] > 12, 15)        # ROE tốt
    add(margins["net"] is not None and margins["net"] > 5, 10)   # biên ròng dương khỏe
    add(margins["gross"] is not None and margins["gross"] > 15, 10)

    # Ngân hàng có D/E cao là bản chất (huy động vốn), không phải rủi ro như DN thường.
    # → nếu là ngân hàng thì BỎ tiêu chí đòn bẩy VÀ thanh khoản (bank không có current
    # ratio), không cộng cũng không tính vào mẫu số. add() tự chuẩn hóa theo `total`
    # nên bỏ tiêu chí thì thang điểm vẫn công bằng. Cờ is_bank dựa vào cơ cấu báo cáo
    # (raw_ratios.is_bank), KHÔNG dựa vào NPL/CAR (giờ luôn None với dữ liệu raw).
    if not is_bank:
        add(solv["debt_to_equity"] is not None and solv["debt_to_equity"] < 1.5, 15)  # đòn bẩy an toàn
        add(solv["current_ratio"] is not None and solv["current_ratio"] > 1, 10)      # thanh khoản
    add(cash["cfo_latest"] is not None and cash["cfo_latest"] > 0, 10)            # dòng tiền dương

    # Piotroski F-Score (chất lượng cơ bản đa tiêu chí, có tính XU HƯỚNG): đưa vào để
    # điểm sức khỏe KHÔNG chạm trần khi tín hiệu xu hướng yếu (vd trước đây health 100
    # nhưng F-Score 2/6). Cho điểm theo tỉ lệ, trọng số 25.
    if fscore is not None and fmax:
        total += 25
        pts += 25 * (fscore / fmax)

    return round(pts / total * 100) if total else 0


def _percentile_rank(sorted_vals: list[float], x: float) -> float:
    """Vị trí percentile (0-100) của x trong chuỗi đã sắp tăng dần."""
    if not sorted_vals:
        return None
    below = sum(1 for v in sorted_vals if v < x)
    return round(below / len(sorted_vals) * 100, 0)


def _band_label(pct: float | None) -> str:
    """Nhãn percentile — ngôn ngữ 'so với lịch sử', KHÔNG dùng rẻ/đắt (an toàn pháp lý)."""
    if pct is None:
        return "không đủ dữ liệu"
    if pct <= 25:
        return "vùng thấp so với lịch sử"
    if pct >= 75:
        return "vùng cao so với lịch sử"
    return "vùng giữa so với lịch sử"


def valuation_band(rat: list[dict], valuation: dict, peer: dict | None = None,
                   years: int = 3) -> dict:
    """Dải định giá theo LỊCH SỬ CHÍNH MÃ (percentile P/E, P/B 3 năm) + trung vị ngành.

    Thay ngôn ngữ 'rẻ/đắt' (dễ bị coi là khuyến nghị) bằng vị trí percentile so
    với chính lịch sử của mã: hiện tại đang ở vùng thấp/giữa/cao. Thuần thống kê.

    rat: records ratio (KBS đã sạch). valuation: dict đã tính (pe/pb hiện tại).
    peer: dict so ngành (nếu có) để lấy trung vị ngành.
    """
    import statistics

    out = {}
    for key, item_id in (("pe", "pe_ratio"), ("pb", "pb_ratio")):
        # chuỗi lịch sử (ưu tiên năm để có bề dày; gồm cả quý gần đây)
        hist = [(p, v) for p, v in
                [(r["period"], r["value"]) for r in rat
                 if r.get("item_id") == item_id and isinstance(r.get("value"), (int, float))
                 and r["value"] > 0]]
        hist.sort(key=lambda x: str(x[0]))
        # lấy các kỳ trong ~`years` năm gần nhất theo nhãn năm
        if hist:
            last_year = _year_of(hist[-1][0])
            if last_year is not None:
                hist = [(p, v) for p, v in hist
                        if (_year_of(p) is None or _year_of(p) >= last_year - years)]
        vals = sorted(v for _, v in hist)
        cur = valuation.get(key)
        if not vals or cur is None or cur <= 0:
            out[key] = {"current": cur, "available": False}
            continue
        p20, p50, p80 = (statistics.quantiles(vals, n=5)[0] if len(vals) >= 4 else vals[0],
                         statistics.median(vals),
                         statistics.quantiles(vals, n=5)[3] if len(vals) >= 4 else vals[-1])
        rank = _percentile_rank(vals, cur)
        peer_med = None
        if peer:
            pm = peer.get(f"{key}_median") or (peer.get("median") or {}).get(key)
            if isinstance(pm, (int, float)):
                peer_med = round(pm, 2)
        out[key] = {
            "available": True, "current": round(cur, 2),
            "min": round(vals[0], 2), "max": round(vals[-1], 2),
            "p20": round(p20, 2), "p50": round(p50, 2), "p80": round(p80, 2),
            "percentile": rank, "label": _band_label(rank),
            "peer_median": peer_med, "n": len(vals),
        }
    out["note"] = ("Vị trí định giá hiện tại so với percentile lịch sử 3 năm CỦA CHÍNH MÃ "
                   "(không phải nhận định rẻ/đắt). Thống kê mô tả.")
    return out


def _valuation_verdict(val) -> str:
    pe, pb = val.get("pe"), val.get("pb")
    if pe is None or pe <= 0:
        return "không xác định"
    if pe < 10 and (pb is None or pb < 1.5):
        return "rẻ"
    if pe > 25 or (pb is not None and pb > 4):
        return "đắt"
    return "hợp lý"
