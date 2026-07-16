# -*- coding: utf-8 -*-
"""sector_metrics.py — phân loại nhóm ngành + bộ chỉ tiêu + ngân hàng KHÔNG Z-score."""
from src import sector_metrics


def _rec(item_id, period, value, ptype="Y"):
    return {"item_id": item_id, "item": item_id, "item_en": "",
            "period": period, "value": value, "period_type": ptype}


# ---- fixtures rút gọn: ngân hàng vs sản xuất ------------------------------
def _bank_bs():
    return [_rec("loans_and_advances_to_customers_net", "2024", 400000),
            _rec("deposits_from_customers", "2024", 500000),
            _rec("total_assets", "2024", 600000)]


def _bank_inc():
    return [_rec("net_interest_income", "2024", 18000),
            _rec("total_operating_income", "2024", 25000),
            _rec("net_profit_loss_after_tax", "2024", 12000)]


def _mfg_bs():
    return [_rec("total_assets", "2024", 100000),
            _rec("owners_equity", "2024", 60000),
            _rec("inventories_net", "2024", 20000)]


def _mfg_inc():
    return [_rec("net_sales", "2024", 80000),
            _rec("cost_of_sales", "2024", 60000),
            _rec("net_profit_loss_after_tax", "2024", 8000)]


# ---------------------------------------------------------------- classify
def test_classify_bank_by_flag():
    group, sub = sector_metrics.classify("Banks", True)
    assert group == "bank"


def test_classify_bank_by_sector_name():
    group, _ = sector_metrics.classify("Banking services", False)
    assert group == "bank"


def test_classify_real_estate_is_non_bank():
    group, sub = sector_metrics.classify("Real Estate", False)
    assert group == "non_bank"
    assert "động sản" in sub.lower() or "bất" in sub.lower()


def test_classify_default_non_bank():
    group, _ = sector_metrics.classify("Technology", False)
    assert group == "non_bank"


# ---------------------------------------------------------------- compute
def test_compute_bank_group_and_no_zscore_flag():
    out = sector_metrics.compute([], _bank_inc(), _bank_bs(), [], "Banks")
    assert out["group"] == "bank"
    assert out["is_bank"] is True
    # ngân hàng nêu rõ NPL/CAR không có nguồn thay vì bịa số
    assert "npl" in out.get("unavailable", {})
    assert "car" in out.get("unavailable", {})


def test_compute_non_bank_group():
    out = sector_metrics.compute([], _mfg_inc(), _mfg_bs(), [], "Industrials")
    assert out["group"] == "non_bank"
    assert out["is_bank"] is False
    assert isinstance(out["metrics"], list) and out["metrics"]


def test_compute_real_estate_adds_inventory_metric():
    out = sector_metrics.compute([], _mfg_inc(), _mfg_bs(), [], "Real Estate")
    keys = {m["key"] for m in out["metrics"]}
    # hàng tồn kho/TTS được bổ sung cho BĐS
    assert "inv_ta" in keys


def test_text_block_bank_mentions_model():
    out = sector_metrics.compute([], _bank_inc(), _bank_bs(), [], "Banks")
    txt = sector_metrics.text_block(out)
    assert "ngân hàng" in txt.lower() or "bank" in txt.lower()
    # không có Z-score trong text ngân hàng
    assert "z''" not in txt.lower() and "z-score" not in txt.lower()


# ---------------------------------------------------------------- _flag ngưỡng
def test_flag_direction_low_is_better():
    # CIR kiểu "thấp tốt": vượt ngưỡng danger → 'danger'
    th = {"warn": 2.0, "danger": 3.0}
    assert sector_metrics._flag(3.5, "low", th) == "danger"
    assert sector_metrics._flag(2.5, "low", th) == "warn"
    assert sector_metrics._flag(1.0, "low", th) == "good"


def test_flag_direction_high_is_better():
    th = {"warn": 12, "danger": 8}
    assert sector_metrics._flag(5, "high", th) == "danger"
    assert sector_metrics._flag(10, "high", th) == "warn"
    assert sector_metrics._flag(15, "high", th) == "good"


def test_flag_none_is_na():
    assert sector_metrics._flag(None, "low", {"warn": 1, "danger": 2}) == "na"
