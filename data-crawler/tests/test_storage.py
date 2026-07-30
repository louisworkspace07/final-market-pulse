# -*- coding: utf-8 -*-
"""storage.py — chuẩn hóa kỳ, ratio_to_records (nguồn KBS), merge_financials lọc rác."""
import sqlite3

import pandas as pd
import pytest

from src import storage


# ---------------------------------------------------------------- CLEAN_PERIOD_RE
@pytest.mark.parametrize("period,ok", [
    ("2024", True), ("2025-Q1", True), ("2025-Q4", True),
    ("2018.1", False), ("2025-Nam", False), ("2025-Q5", False),
    ("", False), ("abcd", False), ("2025-Q0", False),
])
def test_clean_period_re(period, ok):
    assert bool(storage.CLEAN_PERIOD_RE.match(period)) is ok


# ---------------------------------------------------------------- _clean_ratio_period
@pytest.mark.parametrize("col,expected", [
    ("2025-Năm", "2025"),
    ("2025-Nam", "2025"),
    ("2025-Q4", "2025-Q4"),
    ("2025-Q4_1", "2025-Q4"),   # pandas dedup hậu tố
    ("item", None),
    ("item_id", None),
    ("random", None),
])
def test_clean_ratio_period(col, expected):
    assert storage._clean_ratio_period(col) == expected


# ---------------------------------------------------------------- ratio_to_records
def _kbs_ratio_df():
    """DataFrame KBS rút gọn dạng LONG (mỗi hàng 1 chỉ tiêu, cột kỳ YYYY-Năm/QN)."""
    return pd.DataFrame([
        {"item_id": "pe", "item": "P/E", "item_en": "PE",
         "2024-Năm": 12.5, "2025-Q1": 13.0, "2025-Q1_1": 13.0},
        {"item_id": "pb", "item": "P/B", "item_en": "PB",
         "2024-Năm": 1.8, "2025-Q1": 1.9, "2025-Q1_1": 1.9},
        {"item_id": "year", "item": "Năm", "item_en": "year",   # hàng metadata → bỏ
         "2024-Năm": 2024, "2025-Q1": 2025, "2025-Q1_1": 2025},
    ])


def test_ratio_to_records_basic():
    recs = storage.ratio_to_records(_kbs_ratio_df())
    # 2 chỉ tiêu × các kỳ; hàng "year" bị loại
    ids = {r["item_id"] for r in recs}
    assert ids == {"pe", "pb"}
    # kỳ đã chuẩn hóa
    periods = {r["period"] for r in recs}
    assert "2024" in periods and "2025-Q1" in periods
    assert all(storage.CLEAN_PERIOD_RE.match(r["period"]) for r in recs)


def test_ratio_to_records_dedup_q_column_merges_period():
    recs = storage.ratio_to_records(_kbs_ratio_df())
    # "2025-Q1" và "2025-Q1_1" đều map về period "2025-Q1"
    pe_q1 = [r for r in recs if r["item_id"] == "pe" and r["period"] == "2025-Q1"]
    assert len(pe_q1) == 2  # 2 cột trùng kỳ đều thành record (giá trị trùng)


def test_ratio_to_records_empty():
    assert storage.ratio_to_records(pd.DataFrame()) == []
    assert storage.ratio_to_records(None) == []


def test_ratio_to_records_no_period_columns():
    df = pd.DataFrame([{"item_id": "pe", "item": "P/E", "junk": 1}])
    assert storage.ratio_to_records(df) == []


# ---------------------------------------------------------------- merge_financials
def _mem_db():
    con = sqlite3.connect(":memory:")
    con.execute("""CREATE TABLE financials(
        symbol TEXT, statement TEXT, item_id TEXT, item TEXT, item_en TEXT,
        period TEXT, value,
        PRIMARY KEY(symbol, statement, item_id, period))""")
    return con


def _rec(item_id, period, value):
    return {"item_id": item_id, "item": item_id, "item_en": "", "period": period, "value": value}


def test_merge_financials_filters_dirty_periods():
    con = _mem_db()
    recs = [_rec("rev", "2024", 100), _rec("rev", "2025-Q1", 30),
            _rec("rev", "2018.1", 999),          # rác → bị lọc
            _rec("rev", "2025-Nam", 888)]        # rác → bị lọc
    storage.merge_financials(con, "AAA", "income", recs)
    rows = con.execute("SELECT period, value FROM financials ORDER BY period").fetchall()
    periods = [r[0] for r in rows]
    assert periods == ["2024", "2025-Q1"]
    assert 999 not in [r[1] for r in rows]


def test_merge_financials_accumulates_not_replaces():
    con = _mem_db()
    storage.merge_financials(con, "AAA", "income", [_rec("rev", "2023", 50)])
    storage.merge_financials(con, "AAA", "income", [_rec("rev", "2024", 60)])
    n = con.execute("SELECT COUNT(*) FROM financials").fetchone()[0]
    assert n == 2   # kỳ cũ 2023 vẫn còn sau lần merge thứ hai


def test_merge_financials_upsert_same_key():
    con = _mem_db()
    storage.merge_financials(con, "AAA", "income", [_rec("rev", "2024", 50)])
    storage.merge_financials(con, "AAA", "income", [_rec("rev", "2024", 77)])
    rows = con.execute("SELECT value FROM financials WHERE period='2024'").fetchall()
    assert len(rows) == 1 and rows[0][0] == 77   # ghi đè, không nhân đôi
