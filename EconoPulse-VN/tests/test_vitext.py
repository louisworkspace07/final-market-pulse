# -*- coding: utf-8 -*-
"""vitext.py — normalize + ánh xạ tên công ty → mã trên DB fixture (không mạng)."""
import os
import sqlite3

import pytest

from modules.common import vitext


@pytest.fixture
def db(tmp_path, monkeypatch):
    """DB fixture: bảng companies tối thiểu với vài mã thật + tên đầy đủ."""
    path = os.path.join(tmp_path, "fixture.db")
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE companies(symbol TEXT, organ_name TEXT)")
    con.executemany(
        "INSERT INTO companies VALUES(?,?)",
        [
            ("HPG", "Công ty Cổ phần Tập đoàn Hòa Phát"),
            ("FPT", "Công ty Cổ phần FPT"),
            ("VNM", "Công ty Cổ phần Sữa Việt Nam"),
            ("VCB", "Ngân hàng Thương mại Cổ phần Ngoại thương Việt Nam"),
            ("LAI", "CTCP Nào Đó Trùng Từ"),  # mã trùng từ thông dụng "lãi"
        ],
    )
    con.commit()
    con.close()
    monkeypatch.setattr(vitext, "_DB_PATH", path)
    vitext._load_index.cache_clear()
    yield path
    vitext._load_index.cache_clear()


def test_strip_accents():
    assert vitext.strip_accents("Hòa Phát") == "Hoa Phat"
    assert vitext.strip_accents("Đầu tư") == "Dau tu"


def test_normalize():
    assert vitext.normalize("  Hòa Phát!! ") == "hoa phat"
    assert vitext.normalize("CTCP  Sữa   Việt-Nam") == "ctcp sua viet nam"


def test_recognizes_hpg_from_plain_name(db):
    """Yêu cầu nghiệm thu: nhận HPG từ 'Hoa Phat sap chia co tuc'."""
    assert vitext.recognizes("Hoa Phat sap chia co tuc", "HPG")


def test_bare_uppercase_ticker(db):
    assert vitext.find_symbols("cp HPG va FPT hut dong tien") == ["HPG", "FPT"]


def test_lowercase_ticker_needs_cue(db):
    # có cue "ngan hang" → nhận VCB
    assert "VCB" in vitext.find_symbols("ngan hang vcb bao lai ky luc")


def test_no_false_positive_from_common_word(db):
    # "bao lai ky luc" — 'lai' là mã thật nhưng không có cue → KHÔNG dính
    assert vitext.find_symbols("doanh nghiep bao lai ky luc nam nay") == []


def test_company_name_with_suffix(db):
    assert vitext.recognizes("Sua Viet Nam tang truong manh", "VNM")


def test_missing_db_still_finds_bare_tickers(monkeypatch, tmp_path):
    """DB thiếu → index rỗng, nhưng mã trần viết hoa vẫn nhận."""
    monkeypatch.setattr(vitext, "_DB_PATH", os.path.join(tmp_path, "nope.db"))
    vitext._load_index.cache_clear()
    assert vitext.find_symbols("HPG tang tran") == ["HPG"]
    vitext._load_index.cache_clear()
