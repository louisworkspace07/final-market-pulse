# -*- coding: utf-8 -*-
"""raw_ratios.py — dựng chỉ số từ báo cáo GỐC (không đọc statement='ratio').

Kiểm: nhận diện ngân hàng, biên lãi/ROE/ROA/đòn bẩy, chỉ số ngân hàng (NIM/CIR/LDR),
và trung thực với chỉ số không suy được (NPL/CAR/ROIC → None)."""
from src import raw_ratios


def _rec(item_id, period, value, ptype="Y"):
    return {"item_id": item_id, "item": item_id, "item_en": "",
            "period": period, "value": value, "period_type": ptype}


# ---- fixtures: ngân hàng vs sản xuất --------------------------------------
def _bank_inc():
    # 4 quý để TTM tính được (net_interest_income, net_profit, total_operating_income)
    q = []
    for i, p in enumerate(("2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1")):
        q += [_rec("net_interest_income", p, 4000 + i * 100, "Q"),
              _rec("total_operating_income", p, 6000 + i * 100, "Q"),
              _rec("net_profit_loss_after_tax", p, 3000 + i * 50, "Q"),
              _rec("general_and_admin_expenses", p, -1500, "Q"),
              _rec("fees_and_commission_expenses", p, -200, "Q")]
    return q


def _bank_bs():
    return [_rec("total_assets", "2025-Q4", 580000, "Q"),
            _rec("total_assets", "2026-Q1", 600000, "Q"),
            _rec("total_liabilities", "2026-Q1", 540000, "Q"),
            _rec("owners_equity", "2026-Q1", 60000, "Q"),
            _rec("loans_and_advances_to_customers_net", "2026-Q1", 400000, "Q"),
            _rec("deposits_from_customers", "2026-Q1", 500000, "Q"),
            _rec("less_provision_for_losses_on_loans_and_advances_to_customers",
                 "2026-Q1", -8000, "Q")]


def _mfg_inc():
    q = []
    for p in ("2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1"):
        q += [_rec("net_sales", p, 20000, "Q"),
              _rec("cost_of_sales", p, 15000, "Q"),
              _rec("net_profit_loss_after_tax", p, 2000, "Q")]
    return q


def _mfg_bs():
    return [_rec("total_assets", "2025-Q4", 95000, "Q"),
            _rec("total_assets", "2026-Q1", 100000, "Q"),
            _rec("owners_equity", "2026-Q1", 60000, "Q"),
            _rec("liabilities", "2026-Q1", 40000, "Q"),
            _rec("current_assets", "2026-Q1", 50000, "Q"),
            _rec("current_liabilities", "2026-Q1", 25000, "Q")]


# ---------------------------------------------------------------- is_bank
def test_is_bank_true_for_bank_shape():
    assert raw_ratios.is_bank(_bank_bs(), _bank_inc()) is True


def test_is_bank_false_for_manufacturer():
    assert raw_ratios.is_bank(_mfg_bs(), _mfg_inc()) is False


def test_cfo_item_id_differs_by_sector():
    assert raw_ratios.cfo_item_id(True) == "net_cash_from_operating_activities"
    assert raw_ratios.cfo_item_id(False) == \
        "net_cash_inflows_outflows_from_operating_activities"


# ---------------------------------------------------------------- non-bank
def test_manufacturer_margins_and_leverage():
    out = raw_ratios.compute(_mfg_inc(), _mfg_bs(), [])
    assert out["is_bank"] is False
    # biên gộp = (20000-15000)/20000 = 25%
    assert abs(out["margins"]["gross"] - 25.0) < 1e-6
    # biên ròng = 2000/20000 = 10%
    assert abs(out["margins"]["net"] - 10.0) < 1e-6
    # D/E = liabilities/equity = 40000/60000
    assert abs(out["solvency"]["debt_to_equity"] - (40000 / 60000)) < 1e-6
    # current ratio = 50000/25000 = 2
    assert abs(out["solvency"]["current_ratio"] - 2.0) < 1e-6
    # ROE = LNST TTM (4*2000) / vốn bình quân (chỉ 1 kỳ → dùng luôn 60000) = 8000/60000
    assert abs(out["profitability"]["roe"] - (8000 / 60000 * 100)) < 1e-6
    # ngân hàng-metrics None với DN thường
    assert out["bank_metrics"] is None


def test_manufacturer_gross_none_when_cogs_missing():
    inc = [_rec("net_sales", "2026-Q1", 20000, "Q"),
           _rec("net_profit_loss_after_tax", "2026-Q1", 2000, "Q")]
    out = raw_ratios.compute(inc, _mfg_bs(), [])
    assert out["margins"]["gross"] is None
    assert out["margins"]["net"] is not None  # net vẫn tính được


# ---------------------------------------------------------------- bank
def test_bank_metrics_present_and_reasonable():
    out = raw_ratios.compute(_bank_inc(), _bank_bs(), [])
    assert out["is_bank"] is True
    bm = out["bank_metrics"]
    assert bm is not None
    # NIM = NII TTM / TS bình quân (2 kỳ) — dương, nhỏ (%)
    assert bm["nim"] is not None and 0 < bm["nim"] < 20
    # CIR = (|admin|+|fee|) / TOI mới nhất = (1500+200)/6300 ≈ 26.98%
    assert abs(bm["cir"] - ((1500 + 200) / 6300 * 100)) < 1e-6
    # LDR = 400000/500000 = 0.8
    assert abs(bm["ldr"] - 0.8) < 1e-6
    # bank không có current ratio / gross margin
    assert out["solvency"]["current_ratio"] is None
    assert out["margins"]["gross"] is None


def test_bank_npl_car_always_none():
    out = raw_ratios.compute(_bank_inc(), _bank_bs(), [])
    # KHÔNG suy ra được từ báo cáo chuẩn → phải None, không bịa
    assert out["solvency"]["npl"] is None
    assert out["solvency"]["car"] is None
    assert out["bank_metrics"]["npl"] is None
    assert out["bank_metrics"]["car"] is None
    # ROIC cũng None (cần NOPAT + vốn đầu tư)
    assert out["profitability"]["roic"] is None


# ---------------------------------------------------------------- rỗng/thiếu
def test_empty_inputs_no_crash():
    out = raw_ratios.compute([], [], [])
    assert out["is_bank"] is False
    assert out["margins"]["net"] is None
    assert out["profitability"]["roe"] is None


def test_div_guards_zero_denominator():
    assert raw_ratios._div(10, 0) is None
    assert raw_ratios._div(None, 5) is None
    assert raw_ratios._div(10, 5) == 2.0
