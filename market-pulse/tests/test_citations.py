# -*- coding: utf-8 -*-
"""orchestrator._scan_citations + parse_json_answer — id hợp lệ/bịa/bare-id."""
from modules.market_overview.orchestrator import _scan_citations
from modules.market_overview.gemini_transport import parse_json_answer


VALID = {"N1", "N2", "M1", "TT-ACB", "CD-1", "R-5"}


def test_scan_valid_only_returns_empty():
    obj = {"nguyen_nhan": [{"quan_sat": "x", "bang_chung": ["N1", "M1", "TT-ACB"]}]}
    assert _scan_citations(obj, VALID) == []


def test_scan_detects_bare_id_fabricated():
    obj = {"nguyen_nhan": [{"bang_chung": ["N99", "TT-XYZ"]}]}
    bad = _scan_citations(obj, VALID)
    assert "N99" in bad and "TT-XYZ" in bad


def test_scan_detects_bracketed_in_free_text():
    obj = {"tong_quan": "Theo [N5] và [M1], thị trường phân hóa"}
    bad = _scan_citations(obj, VALID)
    assert "N5" in bad          # bịa
    assert "M1" not in bad      # hợp lệ


def test_scan_ignores_non_citation_text():
    obj = {"note": "khối lượng tăng 20% [không phải id]"}
    # "[không phải id]" không khớp mẫu id → không báo
    assert _scan_citations(obj, VALID) == []


def test_scan_bare_id_only_in_bangchung_field():
    # id trần "N1" nằm ngoài mảng bang_chung KHÔNG bị soi như bare-id
    obj = {"random_field": "N99"}
    assert _scan_citations(obj, VALID) == []


def test_scan_nested_lists():
    obj = {"a": [{"b": [{"bang_chung": ["CD-999"]}]}]}
    assert "CD-999" in _scan_citations(obj, VALID)


# ---------------------------------------------------------------- parse_json_answer
def test_parse_plain_json():
    assert parse_json_answer('{"da_nhan": true}')["da_nhan"] is True


def test_parse_fenced_json():
    assert parse_json_answer('```json\n{"x": 1}\n```')["x"] == 1


def test_parse_json_with_extra_text():
    raw = 'Kết quả: {"score": 5, "note": "ổn"} xong'
    assert parse_json_answer(raw)["score"] == 5


def test_parse_json_invalid_raises():
    import pytest
    with pytest.raises(Exception):
        parse_json_answer("hoàn toàn không phải json")
