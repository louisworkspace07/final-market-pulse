# -*- coding: utf-8 -*-
"""A7 · Không được lưu khuyến nghị mua/bán ở bất kỳ đâu.

Căn cứ: Luật Chứng khoán 2019 Điều 71 — hệ thống chỉ mô tả dữ kiện, không đưa
khuyến nghị đầu tư. Xem `EconoPulse-VN/modules/common/legal.py`.

Bối cảnh: schema P4 từng cho AI trả về `investment_rating` ("tích lũy",
"giảm tỷ trọng"…). Tầng API đã lọc trường này, nhưng 25 bản ghi vẫn còn giá trị
nằm trong market.db — lọc ở một tầng không phải là xoá. Đã dọn ngày 2026-07-27;
các test dưới đây chặn nó quay lại.
"""
import json
import sqlite3

import pytest

from src import analyzer, config


def test_quant_only_khong_co_khuyen_nghi():
    """Nhánh AI lỗi (quant-only) cũng không được sinh khuyến nghị."""
    metrics = {
        "revenue": {"latest": 1e9, "period": "2026-Q1", "qoq": 1.0, "yoy_y": 2.0,
                    "yoy_q": None, "trend_q": [], "trend_periods": []},
        "net_profit": {"latest": 1e8, "period": "2026-Q1", "qoq": 1.0, "yoy_y": 2.0,
                       "yoy_q": None, "trend_q": [], "trend_periods": []},
        "margins": {"gross": 10.0, "net": 10.0, "ebit": 10.0},
        "profitability": {"roe": 10.0, "roa": 5.0, "roic": None},
        "valuation": {"pe": 10.0, "pb": 1.0, "ev_ebitda": None, "dividend_yield": None},
        "solvency": {"debt_to_equity": 0.5, "current_ratio": 1.5},
        "cash": {"cfo_latest": None, "cfo_vs_profit": None},
        "fscore": 5, "fscore_max": 8, "health_score": 60, "valuation_verdict": "hợp lý",
    }
    out = analyzer._quant_only("TEST", metrics, {}, [], "loi gia lap")
    assert not out.get("investment_rating"), "quant-only không được gán khuyến nghị"


def test_db_khong_con_ban_ghi_nao_mang_khuyen_nghi():
    """Quét toàn bộ market.db — không bản ghi nào còn giá trị khuyến nghị."""
    db = config.DB_PATH
    if not db.exists():
        pytest.skip("chưa có market.db trên máy này")
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT symbol, analysis FROM ai_analysis").fetchall()
    except sqlite3.Error:
        pytest.skip("market.db chưa có bảng ai_analysis")
    finally:
        conn.close()

    ban = []
    for sym, raw in rows:
        try:
            if json.loads(raw or "{}").get("investment_rating"):
                ban.append(sym)
        except (TypeError, ValueError):
            continue          # bản ghi hỏng là việc khác, không phải việc của test này
    assert not ban, (
        f"{len(ban)} bản ghi còn khuyến nghị đầu tư trong ai_analysis: "
        f"{', '.join(ban[:15])} — chạy lại bước dọn A7.")
