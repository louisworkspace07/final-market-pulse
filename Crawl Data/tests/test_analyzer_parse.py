# -*- coding: utf-8 -*-
"""analyzer.py — parse JSON từ output LLM (fenced / thừa chữ / lồng ngoặc) + trọng số tin."""
import pytest

from src import analyzer


# ---------------------------------------------------------------- _first_json_block
def test_first_json_block_plain():
    assert analyzer._first_json_block('{"a": 1}') == '{"a": 1}'


def test_first_json_block_with_prose_around():
    txt = 'Đây là kết quả: {"a": 1, "b": 2} — hết.'
    assert analyzer._first_json_block(txt) == '{"a": 1, "b": 2}'


def test_first_json_block_nested_and_braces_in_string():
    txt = 'x {"a": {"b": 1}, "note": "có { ngoặc } trong chuỗi"} y'
    block = analyzer._first_json_block(txt)
    assert block == '{"a": {"b": 1}, "note": "có { ngoặc } trong chuỗi"}'


def test_first_json_block_none_when_no_brace():
    assert analyzer._first_json_block("không có json") is None


def test_first_json_block_stops_at_balanced_close():
    # có 2 object; chỉ lấy cái đầu tiên cân bằng
    txt = '{"a": 1} {"b": 2}'
    assert analyzer._first_json_block(txt) == '{"a": 1}'


# ---------------------------------------------------------------- _parse_json
def test_parse_json_fenced():
    raw = '```json\n{"ticker": "FPT", "risk_level": "low"}\n```'
    d = analyzer._parse_json(raw)
    assert d["ticker"] == "FPT" and d["risk_level"] == "low"


def test_parse_json_fenced_no_lang():
    raw = '```\n{"x": 5}\n```'
    assert analyzer._parse_json(raw)["x"] == 5


def test_parse_json_with_leading_prose():
    raw = 'Kết quả phân tích như sau:\n{"verdict": "ổn định", "score": 7}'
    d = analyzer._parse_json(raw)
    assert d["score"] == 7


def test_parse_json_does_not_eat_json_letters():
    # regex bỏ nhãn "json" không được bào mòn nội dung bắt đầu bằng j/s/o/n
    raw = '```json\n{"note": "json là định dạng"}\n```'
    assert analyzer._parse_json(raw)["note"] == "json là định dạng"


def test_parse_json_braces_in_values():
    raw = '{"formula": "f(x) = {a+b}", "ok": true}'
    d = analyzer._parse_json(raw)
    assert d["ok"] is True and "{a+b}" in d["formula"]


# ---------------------------------------------------------------- _weight
@pytest.mark.parametrize("text,expected", [
    ("Doanh nghiệp bị khởi tố hình sự", 5),
    ("Công ty công bố phát hành riêng lẻ tăng vốn", 4),
    ("Ký kết hợp đồng dự án mới", 3),
    ("Bổ nhiệm phó tổng giám đốc", 1),
    ("Một tin tức bình thường không từ khóa", 2),   # mặc định
])
def test_weight(text, expected):
    assert analyzer._weight(text) == expected


def test_weight_empty():
    assert analyzer._weight("") == 2
    assert analyzer._weight(None) == 2
