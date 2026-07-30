# -*- coding: utf-8 -*-
"""market_technical.py — market_snapshot + compute_regime + sector_rotation +
liquidity_concentration trên DB fixture tự sinh (không mạng, không AI)."""
import os
import sqlite3

import pytest

from modules.market_overview import market_technical as mt


def _make_db(tmp_path, trend="up"):
    """DB fixture: 6 mã × ~260 phiên + VNINDEX. trend='up' → chuỗi tăng đều."""
    db = os.path.join(tmp_path, "fixture.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE price(symbol TEXT, time TEXT, close REAL, volume REAL)")
    con.execute("CREATE TABLE companies(symbol TEXT, sector TEXT, market_cap REAL, exchange TEXT)")
    con.execute("CREATE TABLE market_index(code TEXT, time TEXT, close REAL, value REAL)")

    n = 260
    # lịch giao dịch CHUNG cho cả price và VNINDEX (dữ liệu thật dùng chung calendar)
    times = [f"2025-{i:04d}" for i in range(n)]
    # sector_rotation cần ≥5 mã/ngành → Banks có 6 mã, Real Estate 6 mã
    syms = [(f"BNK{i}", "Banks") for i in range(6)] + \
           [(f"RE{i}", "Real Estate") for i in range(6)]
    for si, (sym, sec) in enumerate(syms):
        for i in range(n):
            base = 100 + si * 10
            close = base * (1 + (i / n) * (0.5 if trend == "up" else -0.3))
            con.execute("INSERT INTO price VALUES(?,?,?,?)", (sym, times[i], close, 1000 + si * 100 + i))
        con.execute("INSERT INTO companies VALUES(?,?,?,?)", (sym, sec, 1e12 * (si + 1), "HOSE"))

    # VNINDEX: cùng mốc thời gian với price
    for i in range(n):
        vi = 1000 * (1 + (i / n) * (0.4 if trend == "up" else -0.25))
        con.execute("INSERT INTO market_index VALUES(?,?,?,?)",
                    ("VNINDEX", times[i], vi, 1e13 + i * 1e10))
    con.commit()
    con.close()
    return db


def test_market_snapshot_basic(tmp_path):
    db = _make_db(tmp_path, "up")
    snap = mt.market_snapshot(db)
    assert snap["available"] is True
    assert snap["breadth"]["n_symbols"] == 12
    assert "VNINDEX" in snap["indexes"]


def test_compute_regime_uptrend(tmp_path):
    db = _make_db(tmp_path, "up")
    reg = mt.compute_regime(db)
    assert reg["available"] is True
    assert reg["label"] in ("Uptrend", "Phục hồi")   # chuỗi tăng đều → điểm cao
    assert reg["score"] > 0
    assert len(reg["signals"]) == 5


def test_compute_regime_downtrend(tmp_path):
    db = _make_db(tmp_path, "down")
    reg = mt.compute_regime(db)
    assert reg["label"] in ("Suy yếu", "Downtrend", "Sideways")
    assert reg["score"] <= 1


def test_compute_regime_signals_have_detail(tmp_path):
    db = _make_db(tmp_path, "up")
    reg = mt.compute_regime(db)
    for s in reg["signals"]:
        assert "ten" in s and "chi_tiet" in s
        assert s["dat"] in (True, False, None)


def test_sector_rotation_shape(tmp_path):
    db = _make_db(tmp_path, "up")
    rot = mt.sector_rotation(db, weeks=8)
    assert rot["available"] is True
    assert len(rot["weeks"]) <= 8
    for row in rot["series"]:
        assert len(row["rs"]) == len(rot["weeks"])


def test_liquidity_concentration_from_price(tmp_path):
    db = _make_db(tmp_path, "up")
    lc = mt.liquidity_concentration(db)
    assert lc["available"] is True
    assert 0 <= lc["top10_pct"] <= 100
    assert lc["n_symbols"] == 12


def test_liquidity_concentration_live_board():
    board = [{"symbol": "AAA", "matchPrice": 100, "totalVol": 1000},
             {"symbol": "BBB", "matchPrice": 50, "totalVol": 500}]
    lc = mt.liquidity_concentration(":memory:", board)
    assert lc["available"] is True
    assert lc["live"] is True
    # AAA turnover 100000 vs BBB 25000 → AAA ~80%
    top = {t["symbol"]: t["pct"] for t in lc["top10"]}
    assert top["AAA"] > top["BBB"]


def test_regime_empty_db_not_available(tmp_path):
    db = os.path.join(tmp_path, "empty.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE price(symbol TEXT, time TEXT, close REAL, volume REAL)")
    con.execute("CREATE TABLE companies(symbol TEXT, sector TEXT, market_cap REAL, exchange TEXT)")
    con.execute("CREATE TABLE market_index(code TEXT, time TEXT, close REAL, value REAL)")
    con.commit()
    con.close()
    reg = mt.compute_regime(db)
    assert reg["available"] is False
