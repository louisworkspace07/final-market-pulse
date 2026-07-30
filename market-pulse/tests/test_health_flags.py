# -*- coding: utf-8 -*-
"""Unit test thuần cho watch_flags + flow_score (module business_health.scoring).

Không cần DB thật: logic cờ tách thành hàm thuần; flow_score dùng SQLite :memory:.
"""
import sqlite3

import pandas as pd
import pytest

from modules.business_health import scoring as sc


# --------------------------------------------------------------------------- #
#  watch_flags — logic cờ theo dõi
# --------------------------------------------------------------------------- #
def test_flag_z_danger():
    assert sc.watch_flags("Nguy hiểm", 5) == ["z_danger"]


def test_flag_none_when_safe():
    assert sc.watch_flags("An toàn", 5) == []


def test_flag_f_low_at_threshold():
    # f_score == 3 vẫn tính là thấp (<= 3)
    assert "f_low" in sc.watch_flags("An toàn", 3)
    assert "f_low" not in sc.watch_flags("An toàn", 4)


def test_flag_weak_combo():
    flags = sc.watch_flags("Nguy hiểm", 2)
    assert "z_danger" in flags and "f_low" in flags and "weak_combo" in flags


def test_flag_no_weak_combo_when_only_one():
    assert "weak_combo" not in sc.watch_flags("Nguy hiểm", 7)   # chỉ z_danger
    assert "weak_combo" not in sc.watch_flags("An toàn", 1)     # chỉ f_low


def test_flag_f_drop_when_prior_higher():
    assert "f_drop" in sc.watch_flags("An toàn", 4, prior_f=6)


def test_flag_f_drop_silent_when_prior_none():
    # Không đủ dữ liệu năm trước → không bao giờ có f_drop (không fake)
    assert "f_drop" not in sc.watch_flags("An toàn", 4, prior_f=None)


def test_flag_no_f_drop_when_prior_lower_or_equal():
    assert "f_drop" not in sc.watch_flags("An toàn", 6, prior_f=6)
    assert "f_drop" not in sc.watch_flags("An toàn", 7, prior_f=5)


def test_flags_are_legal_neutral():
    # Không cụm từ khuyến nghị nào lọt vào giá trị cờ
    banned = ["mua", "bán", "khuyến nghị"]
    for z in ("Nguy hiểm", "An toàn", "Xám"):
        for f in range(0, 8):
            for pf in (None, 5, 9):
                for flag in sc.watch_flags(z, f, pf):
                    low = flag.lower()
                    assert not any(b in low for b in banned)


# --------------------------------------------------------------------------- #
#  _flow_score — hàm thuần (chuỗi mới → cũ)
# --------------------------------------------------------------------------- #
def test_flow_none_when_too_few_sessions():
    assert sc._flow_score([10] * 5, [100] * 5) is None


def test_flow_flat_market_low_score():
    # Giá phẳng + khối lượng đều → vol_ratio≈1 (→20đ), move=0 → ~20
    closes = [100.0] * 20
    vols = [1000.0] * 20
    s = sc._flow_score(closes, vols)
    assert s == pytest.approx(20.0, abs=0.5)


def test_flow_bounded_0_100():
    # Khối lượng bùng nổ + giá biến động mạnh → clip về trần
    closes = [130.0, 128, 126, 124, 122, 100.0] + [100.0] * 14   # +30% trong 5 phiên
    vols = [100000.0] * 5 + [10.0] * 15                          # vol5 >> vol20
    s = sc._flow_score(closes, vols)
    assert 0.0 <= s <= 100.0
    assert s == pytest.approx(100.0, abs=0.01)   # cả hai thành phần đạt trần


def test_flow_move_uses_absolute_value():
    # Giảm 10% và tăng 10% cho cùng điểm biên độ (mô tả cường độ, không hướng)
    up = sc._flow_score([110.0] + [100.0] * 19, [1000.0] * 20)
    down = sc._flow_score([90.0] + [100.0] * 19, [1000.0] * 20)
    assert up == down


# --------------------------------------------------------------------------- #
#  flow_score — qua SQLite :memory:
# --------------------------------------------------------------------------- #
def _mem_db_with_price(symbol, n=20):
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE price(symbol TEXT, time TEXT, open REAL, high REAL, "
                "low REAL, close REAL, volume REAL)")
    for i in range(n):
        con.execute("INSERT INTO price(symbol,time,close,volume) VALUES(?,?,?,?)",
                    (symbol, f"2025-{i:04d}", 100.0 + i, 1000.0))
    con.commit()
    return con


def test_flow_score_from_connection():
    con = _mem_db_with_price("AAA")
    s = sc.flow_score(con, "AAA")
    assert s is not None and 0.0 <= s <= 100.0
    con.close()


def test_flow_score_symbol_without_price_none():
    con = _mem_db_with_price("AAA")
    assert sc.flow_score(con, "ZZZ") is None
    con.close()


def test_flow_score_missing_price_table_none():
    con = sqlite3.connect(":memory:")
    assert sc.flow_score(con, "AAA") is None
    con.close()


# --------------------------------------------------------------------------- #
#  score_company — tích hợp: schema có 2 field mới, f_drop từ 3 năm BCTC
# --------------------------------------------------------------------------- #
def _fin_row(period, item_en, value):
    return {"period": period, "item_en": item_en, "value": value}


def _build_fin(years_data):
    """years_data: {year: {item_en: value}} → DataFrame giống market.db."""
    rows = []
    for year, items in years_data.items():
        for item_en, value in items.items():
            rows.append(_fin_row(str(year), item_en, value))
    return pd.DataFrame(rows)


def _healthy_year(scale=1.0):
    return {
        "TOTAL ASSETS": 1000.0, "Liabilities": 300.0, "OWNER'S EQUITY": 700.0,
        "CURRENT ASSETS": 500.0, "Current liabilities": 200.0,
        "Retained Earnings": 100.0, "EBIT": 150.0 * scale,
        "Net profit/(loss) after tax": 120.0 * scale, "Net sales": 800.0,
        "Gross Profit": 240.0 * scale,
        "Net cash inflows/(outflows) from operating activities": 200.0 * scale,
    }


def test_score_company_has_new_fields():
    fin = _build_fin({2024: _healthy_year(), 2023: _healthy_year(0.9)})
    r = sc.score_company(fin, "AAA", "Cty A", "HOSE")
    assert r is not None
    assert "watch_flags" in r and isinstance(r["watch_flags"], list)
    assert "flow_score" in r and r["flow_score"] is None  # score_company không đọc price


def test_score_company_f_drop_needs_three_years():
    # Chỉ 2 năm → không thể tính F kỳ trước → không có f_drop
    fin2 = _build_fin({2024: _healthy_year(), 2023: _healthy_year(0.9)})
    r2 = sc.score_company(fin2, "AAA", "Cty A", "HOSE")
    assert "f_drop" not in r2["watch_flags"]


def test_score_company_danger_flags():
    # DN yếu: nợ lớn, lỗ → z_danger + f_low + weak_combo
    weak = {
        "TOTAL ASSETS": 1000.0, "Liabilities": 950.0, "OWNER'S EQUITY": 50.0,
        "CURRENT ASSETS": 100.0, "Current liabilities": 400.0,
        "Retained Earnings": -300.0, "EBIT": -80.0,
        "Net profit/(loss) after tax": -90.0, "Net sales": 500.0,
        "Gross Profit": 20.0,
        "Net cash inflows/(outflows) from operating activities": -50.0,
    }
    fin = _build_fin({2024: weak, 2023: weak})
    r = sc.score_company(fin, "BAD", "Cty Yếu", "HOSE")
    assert r["z_zone"] == "Nguy hiểm"
    assert "z_danger" in r["watch_flags"]
    assert "f_low" in r["watch_flags"]
    assert "weak_combo" in r["watch_flags"]
