# -*- coding: utf-8 -*-
"""P0-1 · Sự cố AI tạm thời KHÔNG được xoá mất bản phân tích tốt.

Bối cảnh: 2026-07-27, Local API tắt vài giây giữa lúc chạy lại ACB. `analyze_one`
nuốt lỗi, rơi về `_quant_only` rồi ghi đè — một bản 5 lượt đầy đủ suýt bị thay
bằng bản báo lỗi. Nguyên nhân chỉ là mạng chớp, nhưng hậu quả là mất dữ liệu phải
chạy lại 2 phút/mã mới có lại.
"""
import json
import sqlite3

import pytest

from src import analyzer

_GOOD = {
    "ticker": "TST", "mode": "local_api", "n_passes": 5,
    "verdict": "nhận định cũ", "risk_level": "medium",
    "generated_at": "2026-07-20T10:00:00+00:00",
    "aspects": {"financial": {"score": 70, "summary": "..."}},
    "causes": [{"factor": "x", "impact": "positive", "weight": 4}],
    "metrics": {"health_score": 10}, "peer": {"sector": "cũ"},
}


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE ai_analysis (symbol TEXT PRIMARY KEY, analysis TEXT, updated_at TEXT)")
    return c


def _put(conn, sym, payload):
    conn.execute("INSERT INTO ai_analysis VALUES (?,?,?)",
                 (sym, json.dumps(payload, ensure_ascii=False), "2026-07-20"))


def test_giu_lai_ban_tot_khi_ai_loi(conn):
    _put(conn, "TST", _GOOD)
    kept = analyzer._keep_previous(conn, "TST", {"health_score": 88},
                                   {"sector": "mới"}, "Local API sập")
    assert kept is not None, "phải giữ lại bản cũ thay vì vứt đi"
    assert kept["verdict"] == "nhận định cũ"          # phần chữ của AI còn nguyên
    assert kept["n_passes"] == 5
    assert kept["metrics"]["health_score"] == 88      # số liệu được làm mới
    assert kept["peer"]["sector"] == "mới"
    assert kept["stale"] is True                      # UI biết đây là nhận định cũ
    assert "Local API sập" in kept["last_error"]


def test_khong_giu_neu_ban_cu_cung_la_ban_loi(conn):
    """Bản cũ `ai_error` không đáng giữ — để `_quant_only` chạy như thường."""
    _put(conn, "TST", {"mode": "ai_error", "aspects": {}, "causes": []})
    assert analyzer._keep_previous(conn, "TST", {}, {}, "lỗi") is None


def test_khong_giu_neu_chua_tung_co_ban_nao(conn):
    assert analyzer._keep_previous(conn, "MOI", {}, {}, "lỗi") is None


def test_ban_ghi_hong_khong_lam_vo_luong(conn):
    """JSON hỏng trong DB → coi như không có bản cũ, không ném lỗi ra ngoài."""
    conn.execute("INSERT INTO ai_analysis VALUES (?,?,?)", ("TST", "{khong-phai-json", "x"))
    assert analyzer._keep_previous(conn, "TST", {}, {}, "lỗi") is None
