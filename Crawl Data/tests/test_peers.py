# -*- coding: utf-8 -*-
"""peers.py — so sánh ngang ngành + fallback raw khi bảng `ratio` thiếu.

Trọng tâm: (1) trung vị/vị thế đúng khi có ratio; (2) khi thiếu ratio, roe/net_margin/
debt_to_equity được suy từ báo cáo gốc và ĐỒNG NHẤT ĐƠN VỊ (D/E về thang % như ratio table);
(3) P/E, P/B KHÔNG raw-derive (cần giá thị trường)."""
import sqlite3

import pytest

from src import peers


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("""CREATE TABLE companies (symbol TEXT PRIMARY KEY, organ_name TEXT,
                 exchange TEXT, updated_at TEXT, sector TEXT,
                 market_cap REAL, current_price REAL)""")
    c.execute("""CREATE TABLE financials (symbol TEXT, statement TEXT, item_id TEXT,
                 item TEXT, item_en TEXT, period TEXT, value REAL,
                 PRIMARY KEY (symbol, statement, item_id, period))""")
    return c


def _company(c, sym, sector):
    c.execute("INSERT INTO companies(symbol, sector) VALUES (?,?)", (sym, sector))


def _fin(c, sym, stmt, item, period, value):
    c.execute("""INSERT INTO financials(symbol, statement, item_id, item, item_en,
                 period, value) VALUES (?,?,?,?,?,?,?)""",
              (sym, stmt, item, item, "", period, value))


# ratio table đầy đủ cho 1 mã (net_margin/roe theo %, D/E theo % như DB thật)
def _ratio_full(c, sym, pe, pb, roe, nm, de, period="2026-Q1"):
    _fin(c, sym, "ratio", "pe_ratio", period, pe)
    _fin(c, sym, "ratio", "pb_ratio", period, pb)
    _fin(c, sym, "ratio", "roe", period, roe)
    _fin(c, sym, "ratio", "net_margin", period, nm)
    _fin(c, sym, "ratio", "debt_to_equity", period, de)


# báo cáo gốc tối thiểu để raw_ratios suy roe/net_margin/debt_to_equity
def _raw_min(c, sym, sales, ni, equity, liab, assets, period="2026-Q1"):
    for p in ("2025-Q2", "2025-Q3", "2025-Q4", period):
        _fin(c, sym, "income_statement", "net_sales", p, sales)
        _fin(c, sym, "income_statement", "cost_of_sales", p, sales * 0.7)
        _fin(c, sym, "income_statement", "net_profit_loss_after_tax", p, ni)
    _fin(c, sym, "balance_sheet", "owners_equity", period, equity)
    _fin(c, sym, "balance_sheet", "liabilities", period, liab)
    _fin(c, sym, "balance_sheet", "total_assets", period, assets)


# ---------------------------------------------------------------- no sector
def test_no_sector_returns_empty(conn):
    _company(conn, "XXX", None)
    out = peers.compute(conn, "XXX")
    assert out["n_peers"] == 0
    assert out["benchmark"] == {}


# ---------------------------------------------------------------- ratio path
def test_benchmark_median_and_position_from_ratio(conn):
    for s, pe in (("AAA", 10), ("BBB", 20), ("CCC", 30)):
        _company(conn, s, "Tech")
        _ratio_full(conn, s, pe=pe, pb=2.0, roe=15, nm=10, de=50)
    out = peers.compute(conn, "AAA")
    assert out["n_peers"] == 3
    assert out["benchmark"]["pe"] == 20.0            # median(10,20,30)
    # AAA pe=10 < 20 → rẻ hơn ngành
    assert out["position"]["pe"] == "thấp hơn ngành"
    # không có mẫu nào raw-derive khi ratio đủ
    assert out["raw_derived_counts"]["net_margin"] == 0


def test_pe_pb_skip_nonpositive(conn):
    _company(conn, "AAA", "Tech"); _ratio_full(conn, "AAA", pe=-5, pb=0, roe=15, nm=10, de=50)
    _company(conn, "BBB", "Tech"); _ratio_full(conn, "BBB", pe=12, pb=2, roe=15, nm=10, de=50)
    out = peers.compute(conn, "BBB")
    # P/E âm và P/B=0 của AAA bị loại → chỉ còn 1 mẫu hợp lệ
    assert out["sample_sizes"]["pe"] == 1
    assert out["benchmark"]["pe"] == 12.0


# ---------------------------------------------------------------- raw fallback
def test_raw_fallback_when_ratio_missing(conn):
    # peer chỉ có báo cáo gốc, KHÔNG có ratio → roe/net_margin/D/E vẫn vào mẫu
    _company(conn, "RAW", "Ind")
    _raw_min(conn, "RAW", sales=1000, ni=100, equity=5000, liab=3000, assets=8000)
    # 1 peer có ratio để có gì đó so
    _company(conn, "RAT", "Ind")
    _ratio_full(conn, "RAT", pe=10, pb=1, roe=20, nm=12, de=40)
    out = peers.compute(conn, "RAW")
    # net_margin của RAW suy từ raw = 100/1000 = 10%
    assert out["self"]["net_margin"] is not None
    assert abs(out["self"]["net_margin"] - 10.0) < 1e-6
    # P/E của RAW KHÔNG raw-derive được → None
    assert out["self"]["pe"] is None
    # có ít nhất 1 mẫu raw cho net_margin (từ RAW)
    assert out["raw_derived_counts"]["net_margin"] >= 1


def test_raw_debt_to_equity_scaled_to_percent(conn):
    # D/E raw = liab/equity = 3000/5000 = 0.6 (số lần) → phải *100 = 60% để khớp ratio table
    _company(conn, "RAW", "Ind")
    _raw_min(conn, "RAW", sales=1000, ni=100, equity=5000, liab=3000, assets=8000)
    out = peers.compute(conn, "RAW")
    assert abs(out["self"]["debt_to_equity"] - 60.0) < 1e-6


def test_ratio_preferred_over_raw(conn):
    # có CẢ ratio lẫn raw → ưu tiên ratio, không raw-derive
    _company(conn, "BOTH", "Ind")
    _ratio_full(conn, "BOTH", pe=10, pb=1, roe=20, nm=12, de=40)
    _raw_min(conn, "BOTH", sales=1000, ni=100, equity=5000, liab=3000, assets=8000)
    out = peers.compute(conn, "BOTH")
    assert out["self"]["net_margin"] == 12.0          # từ ratio (12), không phải raw (10)
    assert out["raw_derived_counts"]["net_margin"] == 0


def test_widened_n_peers_counts_raw_only_symbols(conn):
    # mã chỉ có raw vẫn được tính vào n_peers (có ít nhất 1 chỉ số so sánh)
    _company(conn, "RAW", "Ind")
    _raw_min(conn, "RAW", sales=1000, ni=100, equity=5000, liab=3000, assets=8000)
    out = peers.compute(conn, "RAW")
    assert out["n_peers"] == 1
