# -*- coding: utf-8 -*-
"""earnings_quality.py — CFO/LNST, DSO trend, accrual; ngân hàng KHÔNG chấm accrual."""
from src import earnings_quality


def _rec(item_id, period, value, ptype="Y"):
    return {"item_id": item_id, "item": item_id, "item_en": "",
            "period": period, "value": value, "period_type": ptype}


# ---- non-bank: lợi nhuận được tiền mặt hỗ trợ tốt -------------------------
def _healthy_inc():
    return [_rec("net_profit_loss_after_tax", "2025-Q1", 100, "Q"),
            _rec("net_profit_loss_after_tax", "2025-Q2", 100, "Q"),
            _rec("net_profit_loss_after_tax", "2025-Q3", 100, "Q"),
            _rec("net_profit_loss_after_tax", "2025-Q4", 100, "Q")]


def _healthy_cf(total_cfo=440):
    q = total_cfo / 4
    return [_rec("net_cash_inflows_outflows_from_operating_activities", f"2025-Q{i}", q, "Q")
            for i in range(1, 5)]


# ---------------------------------------------------------------- non-bank score
def test_non_bank_strong_cfo_high_score():
    eq = earnings_quality.compute(_healthy_inc(), [], _healthy_cf(440), [], is_bank=False)
    assert eq["model"] == "non_bank"
    assert eq["cfo_to_ni"] is not None and eq["cfo_to_ni"] >= 1.0
    assert eq["score"] >= 80    # 70 + 20 khi CFO/LNST >= 1.0


def test_non_bank_weak_cfo_flags_and_low_score():
    # CFO chỉ 40% LNST → cờ đỏ + trừ điểm
    eq = earnings_quality.compute(_healthy_inc(), [], _healthy_cf(160), [], is_bank=False)
    assert eq["cfo_to_ni"] < 0.5
    assert eq["score"] < 60
    assert any("CFO" in f for f in eq["flags"])


def test_non_bank_dso_spike_flag():
    rat = [_rec("days_of_sales_outstanding", "2023", 50),
           _rec("days_of_sales_outstanding", "2024", 100)]   # +100%
    eq = earnings_quality.compute(_healthy_inc(), [], _healthy_cf(440), rat, is_bank=False)
    assert eq["dso_trend"] is not None and eq["dso_trend"] > 30
    assert any("phải thu" in f for f in eq["flags"])


def test_score_clamped_0_100():
    eq = earnings_quality.compute(_healthy_inc(), [], _healthy_cf(440), [], is_bank=False)
    assert 0 <= eq["score"] <= 100


# ---------------------------------------------------------------- bank branch
def test_bank_does_not_score_accrual():
    inc = [_rec("net_interest_income", "2024", 18000),
           _rec("net_profit_loss_after_tax", "2024", 12000)]
    bs = [_rec("loans_and_advances_to_customers_net", "2024", 400000),
          _rec("deposits_from_customers", "2024", 500000)]
    eq = earnings_quality.compute(inc, bs, [], [], is_bank=True)
    assert eq["model"] == "bank"
    assert eq["cfo_to_ni"] is None
    assert eq["accrual"] is None
    assert eq["score"] is None
    assert "ngân hàng" in eq["note"].lower()


def test_bank_nim_decline_flag():
    rat = [_rec("net_interest_margin_nim", "2022", 4.0),
           _rec("net_interest_margin_nim", "2024", 3.0)]   # giảm 1.0 điểm %
    inc = [_rec("net_interest_income", "2024", 18000),
           _rec("net_profit_loss_after_tax", "2024", 12000)]
    bs = [_rec("loans_and_advances_to_customers_net", "2024", 400000),
          _rec("deposits_from_customers", "2024", 500000)]
    eq = earnings_quality.compute(inc, bs, [], rat, is_bank=True)
    assert eq["nim_trend"] is not None and eq["nim_trend"] < 0
    assert any("NIM" in f for f in eq["flags"])


def test_text_block_no_banned_words():
    from src import __init__  # noqa
    eq = earnings_quality.compute(_healthy_inc(), [], _healthy_cf(440), [], is_bank=False)
    txt = earnings_quality.text_block(eq).lower()
    for banned in ("nên mua", "nên bán", "khuyến nghị"):
        assert banned not in txt
