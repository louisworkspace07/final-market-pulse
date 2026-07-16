"""Tính chỉ số tài chính TRỰC TIẾP từ 3 báo cáo gốc (income/balance/cash_flow).

Lý do tồn tại: bảng/`ratio` statement của đa số mã bị ĐÓNG BĂNG ở 2018 (bug nguồn
VCI cũ), trong khi income_statement/balance_sheet/cash_flow luôn tươi tới kỳ mới
nhất. Module này KHÔNG đọc statement='ratio'; nó dựng lại biên lãi, ROE/ROA, đòn
bẩy, thanh khoản, và các chỉ số ĐẶC THÙ NGÂN HÀNG (NIM/CIR/LDR) từ số liệu gốc.

Nguyên tắc trung thực:
- Chỉ số không thể suy ra từ 4 báo cáo chuẩn (NPL, CAR) → trả None, KHÔNG bịa.
  (NPL cần thuyết minh nhóm nợ; CAR cần RWA — đều không có trong báo cáo chuẩn.)
- Thiếu dữ liệu ở tử/mẫu → None, để tầng trên hiển thị "không đủ dữ liệu".

item_id đã kiểm chứng trên market.db (xem memory financials-item-id-contract):
  CFO: bank='net_cash_from_operating_activities';
       non-bank='net_cash_inflows_outflows_from_operating_activities'.
"""
from __future__ import annotations


def _series(records: list[dict], item_id: str, ptype: str) -> list[tuple[str, float]]:
    """Chuỗi (period, value) cho 1 chỉ tiêu, lọc theo loại kỳ (Y/Q), sắp tăng dần.

    Trùng logic với fundamentals._series nhưng tách riêng để module tự chứa
    (dùng được cả khi gọi độc lập trong test/peers)."""
    out = []
    for r in records:
        if r.get("item_id") == item_id and r.get("period_type", "Y") == ptype:
            v = r.get("value")
            if isinstance(v, (int, float)):
                out.append((str(r["period"]), float(v)))
    out.sort(key=lambda x: x[0])
    return out


def _last(series, n: int = 1):
    return series[-n][1] if len(series) >= n else None


def _avg2(series):
    """Trung bình kỳ mới nhất và kỳ liền trước (cho mẫu số bình quân, vd NIM/ROA).

    Chỉ có 1 kỳ → dùng luôn kỳ đó (không None) để vẫn tính được với DN mới."""
    if not series:
        return None
    if len(series) == 1:
        return series[-1][1]
    return (series[-1][1] + series[-2][1]) / 2.0


def _div(num, den):
    if num is None or den is None or den == 0:
        return None
    return num / den


def is_bank(bs: list[dict], inc: list[dict]) -> bool:
    """Nhận diện ngân hàng qua sự hiện diện item đặc thù (cho vay KH / thu nhập lãi thuần).

    An toàn hơn dựa vào NPL/CAR (vốn hay rỗng) như code cũ ở fundamentals."""
    bank_ids = {"loans_and_advances_to_customers_net", "deposits_from_customers"}
    inc_ids = {"net_interest_income", "total_operating_income"}
    have_bs = any(r.get("item_id") in bank_ids for r in bs)
    have_inc = any(r.get("item_id") in inc_ids for r in inc)
    return have_bs and have_inc


def cfo_item_id(bank: bool) -> str:
    return ("net_cash_from_operating_activities" if bank
            else "net_cash_inflows_outflows_from_operating_activities")


def _pref_qy(records, item_id):
    """Chuỗi ưu tiên QUÝ (cho chỉ số điểm-thời), fallback NĂM. Trả (series, ptype)."""
    q = _series(records, item_id, "Q")
    if q:
        return q, "Q"
    return _series(records, item_id, "Y"), "Y"


def compute(inc: list[dict], bs: list[dict], cf: list[dict]) -> dict:
    """Dựng chỉ số từ 3 báo cáo gốc. Trả dict cùng KHÓA với các nhóm ở
    fundamentals.compute (margins/profitability/valuation-phần-raw/solvency)
    để tầng trên chỉ việc lấp None. Giá trị %/tỷ lệ trả dạng ĐÃ nhân 100 (%),
    trừ các hệ số (D/E, current_ratio, LDR) trả dạng số lần.

    valuation (P/E, P/B, P/S) KHÔNG tính ở đây vì cần giá thị trường — để tầng
    trên (fundamentals) ghép với price/EPS. Chỉ trả eps & bvps để hỗ trợ."""
    bank = is_bank(bs, inc)

    # --- Tử/mẫu dùng chung: ưu tiên quý mới nhất cho P&L, năm cho một số mẫu.
    rev = _last(_pref_qy(inc, "net_sales")[0]) if not bank else None
    cogs = _last(_pref_qy(inc, "cost_of_sales")[0]) if not bank else None
    ni_q = _last(_pref_qy(inc, "net_profit_loss_after_tax")[0])
    equity_s = _pref_qy(bs, "owners_equity")[0]
    assets_s = _pref_qy(bs, "total_assets")[0]
    equity = _last(equity_s)
    assets = _last(assets_s)

    out: dict = {"is_bank": bank, "source": "raw_derived"}

    # ---- Biên lãi (%). Ngân hàng không có gross/cogs kiểu DN thường.
    if bank:
        toi = _last(_pref_qy(inc, "total_operating_income")[0])
        out["margins"] = {
            "gross": None,
            "net": _pct(_div(ni_q, toi)),   # LNST / tổng thu nhập hoạt động
            "ebit": None,
        }
    else:
        gross = (rev - cogs) if (rev is not None and cogs is not None) else None
        out["margins"] = {
            "gross": _pct(_div(gross, rev)),
            "net": _pct(_div(ni_q, rev)),
            "ebit": None,   # cần EBIT tách riêng; để None thay vì bịa
        }

    # ---- Hiệu quả: ROE/ROA dùng LNST 4 quý gần nhất (TTM) trên vốn/tài sản bình quân.
    ni_ttm = _ttm(inc, "net_profit_loss_after_tax")
    out["profitability"] = {
        "roe": _pct(_div(ni_ttm, _avg2(equity_s))),
        "roa": _pct(_div(ni_ttm, _avg2(assets_s))),
        "roic": None,   # cần NOPAT & vốn đầu tư; không suy ra đơn giản → None
    }

    # ---- Đòn bẩy & thanh khoản.
    liabilities = _last(_pref_qy(bs, "total_liabilities" if bank else "liabilities")[0])
    solvency = {
        "debt_to_equity": _div(liabilities, equity),
        "financial_leverage": _div(assets, equity),
        "npl": None,   # cần thuyết minh nhóm nợ — KHÔNG có trong báo cáo chuẩn
        "car": None,   # cần RWA — KHÔNG công bố trong báo cáo chuẩn
    }
    if bank:
        # Ngân hàng không có khái niệm current ratio (không phân ngắn/dài hạn).
        solvency["current_ratio"] = None
    else:
        ca = _last(_pref_qy(bs, "current_assets")[0])
        cl = _last(_pref_qy(bs, "current_liabilities")[0])
        solvency["current_ratio"] = _div(ca, cl)
    out["solvency"] = solvency

    # ---- Chỉ số đặc thù ngân hàng (chỉ khi là bank).
    out["bank_metrics"] = _bank_metrics(inc, bs) if bank else None

    # ---- Hỗ trợ định giá: EPS (TTM) & BVPS — tầng trên ghép với giá.
    out["eps_ttm"] = ni_ttm  # ghi chú: đây là LNST TTM, chưa /số cp; fundamentals dùng eps_basic_vnd riêng
    out["book_value"] = equity
    return out


def _pct(v):
    return None if v is None else v * 100.0


def _ttm(records, item_id):
    """Tổng 4 quý gần nhất (trailing twelve months). Thiếu quý → None (không lấy năm
    để tránh trộn đơn vị)."""
    q = _series(records, item_id, "Q")
    if len(q) >= 4:
        return sum(v for _, v in q[-4:])
    # Không đủ 4 quý: thử dùng năm mới nhất như xấp xỉ.
    y = _series(records, item_id, "Y")
    return y[-1][1] if y else None


def _bank_metrics(inc: list[dict], bs: list[dict]) -> dict:
    """NIM / CIR / LDR / tăng trưởng tín dụng / độ phủ dự phòng — từ báo cáo gốc.

    NIM  = thu nhập lãi thuần (TTM) / tổng tài sản sinh lãi bình quân (xấp xỉ = tổng TS).
    CIR  = (chi phí QLDN + chi phí dịch vụ) / tổng thu nhập hoạt động.
    LDR  = cho vay khách hàng ròng / tiền gửi khách hàng.
    """
    nii_ttm = _ttm(inc, "net_interest_income")
    assets_avg = _avg2(_pref_qy(bs, "total_assets")[0])
    nim = _pct(_div(nii_ttm, assets_avg))

    toi = _last(_pref_qy(inc, "total_operating_income")[0])
    admin = _last(_pref_qy(inc, "general_and_admin_expenses")[0]) or 0.0
    fee_exp = _last(_pref_qy(inc, "fees_and_commission_expenses")[0]) or 0.0
    # Chi phí thường mang dấu âm trong báo cáo → lấy trị tuyệt đối cho CIR.
    opex = abs(admin) + abs(fee_exp)
    cir = _pct(_div(opex, toi)) if toi else None

    loans = _last(_pref_qy(bs, "loans_and_advances_to_customers_net")[0])
    deposits = _last(_pref_qy(bs, "deposits_from_customers")[0])
    ldr = _div(loans, deposits)

    # Tăng trưởng tín dụng YoY (nếu đủ 5 quý) hoặc so năm.
    loans_q = _series(bs, "loans_and_advances_to_customers_net", "Q")
    credit_growth = None
    if len(loans_q) >= 5 and loans_q[-5][1]:
        credit_growth = (loans_q[-1][1] - loans_q[-5][1]) / abs(loans_q[-5][1]) * 100.0

    # Độ phủ dự phòng = dự phòng rủi ro cho vay / dư nợ (xấp xỉ, dấu âm → abs).
    prov = _last(_pref_qy(bs, "less_provision_for_losses_on_loans_and_advances_to_customers")[0])
    provision_coverage = _pct(_div(abs(prov), loans)) if (prov is not None and loans) else None

    return {
        "nim": nim, "cir": cir, "ldr": ldr,
        "credit_growth_yoy": credit_growth,
        "provision_coverage": provision_coverage,
        "npl": None, "car": None,   # không suy ra được từ báo cáo chuẩn
    }
