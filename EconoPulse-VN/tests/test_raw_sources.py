# -*- coding: utf-8 -*-
"""Đưa dữ liệu data-crawler lên gateway — trọng tâm là RÀO PHÁP LÝ.

`profile.json` của vnstock có `rating` / `target_price` / `upside_to_target_percent`
là khuyến nghị của công ty chứng khoán. Trang cổ phiếu đã chặn chúng bằng
whitelist; endpoint mới này đọc thẳng tệp nên phải chặn LẠI, nếu không thì mở
đúng cái cửa vừa khoá (legal.py · Luật CK 2019 Điều 71).
"""
import json
import os

import pytest

from modules.stock_page import raw_sources


@pytest.fixture()
def fake(tmp_path):
    """Cây thư mục giả đúng hình dạng thật: <root>/database/market.db + companies/."""
    db = tmp_path / "database" / "market.db"
    db.parent.mkdir(parents=True)
    db.write_text("")
    d = tmp_path / "companies" / "TST"
    (d / "ownership").mkdir(parents=True)
    (d / "news").mkdir(parents=True)
    (d / "market").mkdir(parents=True)
    (d / "ownership" / "officers.json").write_text(json.dumps({"items": [
        {"officer_name": "Nguyễn Văn A", "officer_position": "Chủ tịch"},
        {"officer_name": "Trần Thị B", "officer_position": "Tổng giám đốc"},
    ]}, ensure_ascii=False), encoding="utf-8")
    (d / "profile.json").write_text(json.dumps({
        "overview": {"company_profile": "Doanh nghiệp thử nghiệm",
                     "rating": "BUY", "target_price": 90300,
                     "upside_to_target_percent": 43.5},
    }, ensure_ascii=False), encoding="utf-8")
    (d / "market" / "foreign_history.jsonl").write_text(
        '{"date":"2026-07-01","net":100}\n{"date":"2026-07-02","net":-50}\n',
        encoding="utf-8")
    return str(db)


def test_liet_ke_dung_nguon_co_that(fake):
    keys = {s["key"] for s in raw_sources.available(fake, "TST")}
    assert keys == {"officers", "profile", "foreign_history"}


def test_doc_bang_va_dem_dung(fake):
    out = raw_sources.fetch(fake, "TST", "officers")
    assert out["kind"] == "table" and out["total"] == 2
    assert out["rows"][0]["officer_name"] == "Nguyễn Văn A"
    assert out["truncated"] is False


def test_doc_duoc_jsonl(fake):
    out = raw_sources.fetch(fake, "TST", "foreign_history")
    assert out["total"] == 2 and out["rows"][1]["net"] == -50


def test_loc_sach_khuyen_nghi_trong_profile(fake):
    """Đây là test quan trọng nhất của tệp này."""
    out = raw_sources.fetch(fake, "TST", "profile")
    blob = json.dumps(out, ensure_ascii=False).lower()
    for banned in ("rating", "target_price", "upside_to_target_percent"):
        assert banned not in blob, f"{banned} lọt ra ngoài qua endpoint nguồn thô"
    assert "Doanh nghiệp thử nghiệm" in json.dumps(out, ensure_ascii=False)


def test_cat_bot_khi_qua_nhieu_ban_ghi(fake):
    out = raw_sources.fetch(fake, "TST", "officers", limit=1)
    assert len(out["rows"]) == 1 and out["truncated"] is True and out["total"] == 2


def test_khoa_la_va_ma_khong_co_deu_tra_rong(fake):
    assert raw_sources.fetch(fake, "TST", "khong_ton_tai") == {}
    assert raw_sources.fetch(fake, "KHONGCO", "officers") == {}
    assert raw_sources.available(fake, "KHONGCO") == []


def test_khong_doc_ra_ngoai_thu_muc_ma(fake):
    """Khóa nguồn là danh sách cố định, không nhận đường dẫn tuỳ ý."""
    for evil in ("../../../etc/passwd", "..\\..\\market.db", "/etc/hosts"):
        assert raw_sources.fetch(fake, "TST", evil) == {}
