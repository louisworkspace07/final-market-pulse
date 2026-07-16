# -*- coding: utf-8 -*-
"""legal.py — quét từ cấm khuyến nghị (dính / lách / sạch)."""
import pytest

from modules.common import legal


@pytest.mark.parametrize("text", [
    "Nhà đầu tư nên mua cổ phiếu này ngay",
    "Chúng tôi khuyến nghị mua ở vùng giá hiện tại",
    "Đây là lúc vào lệnh",
    "Nên bán để bảo toàn vốn",
    "Gia tăng tỷ trọng nhóm ngân hàng",
])
def test_check_text_catches_banned(text):
    assert legal.check_text(text)   # không rỗng


@pytest.mark.parametrize("text", [
    "Doanh thu tăng 12% so cùng kỳ",
    "Biên lãi gộp cải thiện lên 18%",
    "Rủi ro thanh khoản đang tăng theo dữ liệu khối lượng",
    "",
])
def test_check_text_clean_passes(text):
    assert legal.check_text(text) == []


def test_check_text_case_insensitive():
    assert legal.check_text("NÊN MUA NGAY")


def test_check_payload_recurses_nested():
    payload = {
        "tong_quan": "Thị trường phân hóa",
        "diem_nhan": ["Ngành thép hồi phục", "Nhà đầu tư nên bán nhóm BĐS"],
        "nested": {"deep": {"note": "khuyến nghị mua khi điều chỉnh"}},
    }
    hits = legal.check_payload(payload)
    assert "nên bán" in hits
    assert "khuyến nghị mua" in hits


def test_check_payload_clean_returns_empty():
    payload = {"a": ["số liệu mô tả", {"b": "diễn biến giá"}]}
    assert legal.check_payload(payload) == []


def test_check_payload_dedups_and_sorts():
    payload = {"x": "nên mua", "y": "nên mua lần nữa"}
    hits = legal.check_payload(payload)
    assert hits == sorted(set(hits))


def test_disclaimer_constants_present():
    assert "không phải" in legal.DISCLAIMER.lower()
    assert legal.LEGAL_PROMPT_RULE and "khuyến nghị" in legal.LEGAL_PROMPT_RULE.lower()


@pytest.mark.parametrize("text", [
    "Đội lái đang thao túng giá con này",
    "Kèo thơm, cam kết lợi nhuận x2 tài khoản trong tháng",
    "Hàng nóng, múc mạnh full margin đi anh em",
    "Con này chắc chắn tăng trần, tất tay luôn",
])
def test_check_text_catches_soitin_phrases(text):
    """Nhãn factcheck không được quy kết thao túng / hô hào / cam kết giá."""
    assert legal.check_text(text)


def test_rumor_fixtures_loadable():
    """rumors.txt tồn tại, có đúng 10 tin (bỏ dòng trống & comment)."""
    import os
    path = os.path.join(os.path.dirname(__file__), "fixtures", "rumors.txt")
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as f:
        rumors = [ln.strip() for ln in f
                  if ln.strip() and not ln.lstrip().startswith("#")]
    assert len(rumors) == 10
    # mỗi tin đủ dài để bóc claim
    assert all(len(r) > 20 for r in rumors)
