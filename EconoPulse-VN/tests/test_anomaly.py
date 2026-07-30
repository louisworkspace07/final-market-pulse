# -*- coding: utf-8 -*-
"""Radar bất thường — verify các bộ phát hiện + tính trung tính + coverage-aware.

Cập nhật cho anomaly.py viết lại (A1-A4): _detect_symbol nhận in_coverage; severity
gán theo percentile trong nhóm (test qua scan/assign); tin tách 3 trạng thái;
vol_spike lọc thanh khoản; foreign_flip đọc history/snapshot."""
import os
import sqlite3

import pandas as pd
import pytest

from modules.market_overview import anomaly
from modules.common import legal

DB = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "data-crawler", "database", "market.db"))

# KL & giá đủ lớn để qua sàn thanh khoản (TB20≥30k cp, turnover≥500tr).
_LIQ_VOL = 100_000.0
_LIQ_CLOSE = 20.0   # 100k × 20 × 1000 = 2 tỷ > 500tr


def _synthetic_group(closes, volumes, start="2026-06-01"):
    dates = pd.date_range(start, periods=len(closes)).strftime("%Y-%m-%d")
    return pd.DataFrame({
        "symbol": ["ZZZ"] * len(closes), "time": dates,
        "open": closes, "high": closes, "low": closes,
        "close": closes, "volume": volumes,
    })


# ── vol_spike ────────────────────────────────────────────────────────────────
def test_vol_spike_detected_when_liquid():
    closes = [_LIQ_CLOSE] * 25
    volumes = [_LIQ_VOL] * 24 + [_LIQ_VOL * 9]         # phiên cuối gấp 9×
    g = _synthetic_group(closes, volumes)
    sigs = anomaly._detect_symbol("ZZZ", g, set(), True, 7.0)
    assert any(s["kind"] == "vol_spike" for s in sigs)


def test_vol_spike_suppressed_when_illiquid():
    """Mã chết thanh khoản (TB20 < 30k cp) → ×9 vô nghĩa, KHÔNG báo."""
    closes = [_LIQ_CLOSE] * 25
    volumes = [1000.0] * 24 + [9000.0]                 # TB20 = 1000 < 30k
    g = _synthetic_group(closes, volumes)
    sigs = anomaly._detect_symbol("ZZZ", g, set(), True, 7.0)
    assert not any(s["kind"] == "vol_spike" for s in sigs)


def test_vol_spike_suspect_note_when_over_20x():
    closes = [_LIQ_CLOSE] * 25
    volumes = [_LIQ_VOL] * 24 + [_LIQ_VOL * 25]        # ×25 → cờ nghi thỏa thuận
    g = _synthetic_group(closes, volumes)
    sigs = anomaly._detect_symbol("ZZZ", g, set(), True, 7.0)
    vs = [s for s in sigs if s["kind"] == "vol_spike"]
    assert vs and "note" in vs[0] and "thỏa thuận" in vs[0]["note"]


# ── price_run_no_news: coverage-aware (A1, ưu tiên #1) ───────────────────────
def test_price_run_in_coverage_no_news_confirms_zero():
    """Mã CÓ trong coverage + 0 tin 30 ngày → khẳng định 'none_confirmed'."""
    closes = [10.0] * 20 + [11.0, 12.0, 13.0, 14.0, 15.0]   # +50%
    volumes = [_LIQ_VOL] * 25
    g = _synthetic_group(closes, volumes)
    sigs = anomaly._detect_symbol("ZZZ", g, set(), True, 7.0)   # in_coverage=True
    prn = [s for s in sigs if s["kind"] == "price_run_no_news"]
    assert prn and prn[0]["metrics"]["news_status"] == "none_confirmed"
    assert "0 tin" not in prn[0]["headline"]   # headline không cần chữ "0 tin"


def test_price_run_out_of_coverage_says_uncrawled_not_zero():
    """Mã NGOÀI coverage → 'uncrawled', headline CHƯA có dữ liệu, KHÔNG nói '0 tin'."""
    closes = [10.0] * 20 + [11.0, 12.0, 13.0, 14.0, 15.0]
    volumes = [_LIQ_VOL] * 25
    g = _synthetic_group(closes, volumes)
    sigs = anomaly._detect_symbol("ZZZ", g, set(), False, 7.0)  # in_coverage=False
    prn = [s for s in sigs if s["kind"] == "price_run_no_news"]
    assert prn and prn[0]["metrics"]["news_status"] == "uncrawled"
    assert "CHƯA" in prn[0]["headline"]
    assert "0 tin" not in prn[0]["headline"]


def test_price_run_suppressed_when_recent_news_in_coverage():
    closes = [10.0] * 20 + [11.0, 12.0, 13.0, 14.0, 15.0]
    volumes = [_LIQ_VOL] * 25
    g = _synthetic_group(closes, volumes)
    news_days = set(g["time"].iloc[-3:])       # có tin gần đây
    sigs = anomaly._detect_symbol("ZZZ", g, news_days, True, 7.0)
    assert not any(s["kind"] == "price_run_no_news" for s in sigs)


# ── limit_streak ─────────────────────────────────────────────────────────────
def test_limit_streak_detected():
    closes = [10.0] * 22 + [10.68, 11.4, 12.17]
    volumes = [_LIQ_VOL] * 25
    g = _synthetic_group(closes, volumes)
    sigs = anomaly._detect_symbol("ZZZ", g, set(), True, 7.0)
    lim = [s for s in sigs if s["kind"] == "limit_streak"]
    assert lim and lim[0]["metrics"]["streak"] >= 2


def test_short_series_yields_nothing():
    g = _synthetic_group([10.0] * 10, [_LIQ_VOL] * 10)
    assert anomaly._detect_symbol("ZZZ", g, set(), True, 7.0) == []


# ── severity theo percentile ─────────────────────────────────────────────────
def test_assign_severity_percentile_top25():
    # nhóm 8 mã vol_spike, mag 1..8 → top 25% (mag ≥ mốc phân vị 75) = cao
    sigs = [{"kind": "vol_spike", "_mag": float(i), "metrics": {}} for i in range(1, 9)]
    anomaly._assign_severity(sigs)
    cao = [s for s in sigs if s["severity"] == "cao"]
    assert 0 < len(cao) <= 3          # ~25% của 8
    assert all(s["_mag"] >= max(x["_mag"] for x in sigs if x["severity"] == "vua")
               for s in cao)


def test_assign_severity_downgrades_uncrawled():
    # mag=18 < ngưỡng hard 25 → khởi 'vua'; ngoài coverage hạ 1 bậc → 'thap'.
    sigs = [{"kind": "price_run_no_news", "_mag": 18.0,
             "metrics": {"news_status": "uncrawled"}}]
    anomaly._assign_severity(sigs)
    assert sigs[0]["severity"] == "thap"   # bị hạ bậc vì ngoài coverage


def test_assign_severity_uncrawled_high_mag_downgraded_from_cao():
    # mag=40 ≥ 25 → hard 'cao'; ngoài coverage hạ 1 bậc → 'vua'.
    sigs = [{"kind": "price_run_no_news", "_mag": 40.0,
             "metrics": {"news_status": "uncrawled"}}]
    anomaly._assign_severity(sigs)
    assert sigs[0]["severity"] == "vua"


# ── foreign_flip (A2) ────────────────────────────────────────────────────────
def test_foreign_flip_insufficient_data_message():
    """Thiếu chuỗi khối ngoại → message tích lũy CHÍNH XÁC, không 'chưa tích hợp'."""
    fx = anomaly._detect_foreign_flip({}, [], "2026-07-08")
    assert fx["available"] is False
    assert "tích lũy" in fx["reason"]
    assert "chưa tích hợp" not in fx["reason"].lower()


# ── scan tổng ────────────────────────────────────────────────────────────────
def test_scan_missing_db_graceful():
    r = anomaly.scan_anomalies("C:/khong/ton/tai.db")
    assert r["available"] is False
    assert r["foreign_flip"]["available"] is False


def test_foreign_flip_marked_unavailable_not_faked():
    r = anomaly.scan_anomalies("C:/khong/ton/tai.db")
    assert "reason" in r["foreign_flip"]


@pytest.mark.skipif(not os.path.exists(DB), reason="market.db chưa có")
def test_scan_real_db_neutral_and_no_false_zero():
    r = anomaly.scan_anomalies(DB, limit=200)
    assert r["available"] is True
    assert "stale" in r and "coverage" in r
    valid_kinds = {"vol_spike", "price_run_no_news", "limit_streak", "divergence"}
    for s in r["signals"]:
        assert s["kind"] in valid_kinds
        assert s["severity"] in {"cao", "vua", "thap"}
        assert legal.check_text(s["headline"]) == []
        assert legal.check_text(s["verify"]) == []
        # KHÔNG mã nào ngoài coverage lại mang chữ "0 tin"
        if s["kind"] == "price_run_no_news" and \
           s["metrics"].get("news_status") == "uncrawled":
            assert "0 tin" not in s["headline"]
    assert "không" in r["note"].lower()


@pytest.mark.skipif(not os.path.exists(DB), reason="market.db chưa có")
def test_scan_vol_spike_liquidity_reduced():
    """Sau lọc thanh khoản, vol_spike phải ít lại (kỳ vọng ≤ ~15, trước ~23)."""
    r = anomaly.scan_anomalies(DB, limit=500)
    n_vol = r["by_kind"].get("vol_spike", 0)
    assert n_vol <= 15
