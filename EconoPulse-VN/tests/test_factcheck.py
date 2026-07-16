# -*- coding: utf-8 -*-
"""Soi Tin — verify extractor/checker/engine trên bộ tin đồn mẫu."""
import os

import pytest

from modules.common import legal
from modules.factcheck import checker
from modules.factcheck.extractor import extract_claims, all_symbols, Claim
from modules.factcheck.engine import factcheck, LABELS, _offline_answer

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "rumors.txt")
DB = checker.DB_PATH
TODAY = "2026-07-08"


def _rumors():
    with open(FIX, encoding="utf-8") as f:
        return [ln.strip() for ln in f
                if ln.strip() and not ln.lstrip().startswith("#")]


# ---------------------------------------------------------------- extractor
def test_extractor_tags_known_symbols():
    claims = extract_claims("Nghe nói HPG sắp chia cổ tức, còn FPT thì báo lãi lớn.")
    syms = all_symbols(claims)
    assert "HPG" in syms and "FPT" in syms


@pytest.mark.parametrize("text,kind", [
    ("HPG sắp chia cổ tức tiền mặt 20%", "dividend"),
    ("VCB phát hành thêm cổ phiếu tăng vốn", "issuance"),
    ("ABC sắp bị hủy niêm yết do thua lỗ", "delist"),
    ("VIC bắt tay đối tác ngoại làm dự án", "ma"),
    ("Nội bộ MWG đăng ký bán ra cổ phiếu", "insider"),
    ("Thị trường điều chỉnh vì áp lực tỷ giá", "macro"),
])
def test_extractor_classifies_kind(text, kind):
    claims = extract_claims(text)
    assert claims and claims[0].kind == kind


def test_extractor_handles_empty():
    assert extract_claims("") == []


def test_extractor_covers_all_fixture_rumors():
    for r in _rumors():
        claims = extract_claims(r)
        assert claims, f"không bóc được claim từ: {r}"


# ------------------------------------------------------------------ checker
@pytest.mark.skipif(not os.path.exists(DB), reason="market.db chưa có")
def test_checker_signal_is_neutral_enum():
    for r in _rumors():
        for ch in checker.check_claims(extract_claims(r), today=TODAY):
            assert ch.signal in {"co_cong_bo", "khong_thay", "khong_kiem_chung"}


@pytest.mark.skipif(not os.path.exists(DB), reason="market.db chưa có")
def test_checker_macro_never_claims_confirmation():
    """Tin vĩ mô/không mã không bao giờ bị gán 'có công bố xác nhận'."""
    ch = checker.check_claim(
        Claim(text="Thị trường sắp điều chỉnh vì tỷ giá", symbols=[], kind="macro"),
        today=TODAY)
    assert ch.signal == "khong_kiem_chung"


@pytest.mark.skipif(not os.path.exists(DB), reason="market.db chưa có")
def test_checker_dividend_finds_published_event():
    """HPG có sự kiện trả cổ tức thật gần đây → co_cong_bo, kèm bằng chứng id."""
    ch = checker.check_claim(
        Claim(text="HPG sắp chia cổ tức", symbols=["HPG"], kind="dividend"),
        today=TODAY)
    assert ch.signal == "co_cong_bo"
    assert ch.evidence and all(e["id"][0] in ("E", "N") for e in ch.evidence)


def test_checker_missing_db_is_graceful():
    ch = checker.check_claim(
        Claim(text="HPG chia cổ tức", symbols=["HPG"], kind="dividend"),
        db_path="C:/khong/ton/tai.db", today=TODAY)
    assert ch.signal == "khong_kiem_chung"


# ------------------------------------------------------------------- engine
def test_offline_answer_labels_are_legal_and_valid():
    """Nhãn offline hợp lệ + không chứa từ cấm pháp lý."""
    checks = checker.check_claims(extract_claims(
        "HPG chia cổ tức. VNM bị nghi gian lận. Thị trường sắp giảm."), today=TODAY)
    ans = _offline_answer(checks)
    assert all(c["nhan"] in LABELS for c in ans["claims"])
    assert legal.check_payload(ans) == []
    assert "không phải" in ans["disclaimer"].lower()


def test_factcheck_offline_end_to_end():
    """prefer=cdp khi worker tắt → rơi xuống offline, không được crash."""
    r = factcheck("Nghe nói HPG sắp chia cổ tức 20%. Thị trường sắp điều chỉnh.",
                  prefer="cdp", today=TODAY)
    assert r["mode"] == "offline"
    assert r["n_claims"] == 2
    assert legal.check_payload(r["answer"]) == []


def test_factcheck_empty_input():
    assert "error" in factcheck("", today=TODAY)
