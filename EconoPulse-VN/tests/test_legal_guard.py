# -*- coding: utf-8 -*-
"""legal.check_keys / legal.scrub — lớp quét TÊN KHOÁ (bổ sung cho check_text).

Lý do tồn tại: check_text/check_payload chỉ soi GIÁ TRỊ string, nên payload
{"investment_rating": "mua"} lọt lưới (trả []). Các test dưới đây khoá lại hành
vi mới: bắt tên khoá, gỡ đệ quy, và KHÔNG phá payload hợp lệ.

Toàn bộ dùng dữ liệu giả — không cần mạng, không cần DB.
"""
import pytest

from modules.common import legal


# ── 1. Case mà check_text bỏ sót ────────────────────────────────────────────

def test_check_text_misses_investment_rating_value():
    """Chốt lại lỗ hổng gốc: 'mua' đứng một mình KHÔNG bị BANNED bắt."""
    assert legal.check_payload({"investment_rating": "mua"}) == []


def test_check_keys_catches_investment_rating():
    """check_keys() bắt đúng case check_payload() bỏ sót."""
    assert legal.check_keys({"investment_rating": "mua"}) == ["investment_rating"]


def test_check_all_flags_what_check_payload_missed():
    payload = {"symbol": "ACB", "investment_rating": "mua"}
    res = legal.check_all(payload)
    assert res["ok"] is False
    assert res["banned_text"] == []            # lớp cũ vẫn nói "sạch"
    assert res["banned_keys"] == ["investment_rating"]


# ── 2. Toàn bộ drop-list tối thiểu ──────────────────────────────────────────

@pytest.mark.parametrize("key", [
    "investment_rating", "target_price", "upside_to_target_percent",
    "rating", "recommendation", "winner",
])
def test_all_banned_keys_detected(key):
    assert legal.check_keys({key: "bất kỳ"}) == [key]
    assert key not in legal.scrub({key: "bất kỳ"})


def test_banned_key_case_insensitive():
    assert legal.check_keys({"Investment_Rating": "MUA"}) == ["investment_rating"]
    assert legal.scrub({"TARGET_PRICE": 27100}) == {}


def test_is_banned_key_exact_match_only():
    """Chỉ khớp chính xác — không gỡ oan khoá chứa chuỗi con."""
    assert legal.is_banned_key("rating") is True
    assert legal.is_banned_key("rating_history") is False
    assert legal.is_banned_key("credit_rating_agency") is False
    assert legal.is_banned_key(None) is False
    assert legal.is_banned_key(42) is False


# ── 3. Đệ quy sâu, kể cả list of dict ───────────────────────────────────────

def test_scrub_recurses_into_list_of_dicts():
    payload = {
        "peers": [
            {"symbol": "ACB", "pe": 6.1, "rating": "BUY", "target_price": 27100},
            {"symbol": "BID", "pe": 12.4, "rating": "BUY", "target_price": 50500},
        ],
        "meta": {"source": "profile.json"},
    }
    out = legal.scrub(payload)
    assert [p["symbol"] for p in out["peers"]] == ["ACB", "BID"]
    assert all("rating" not in p and "target_price" not in p for p in out["peers"])
    assert out["peers"][0]["pe"] == 6.1          # số liệu trung tính còn nguyên
    assert out["meta"] == {"source": "profile.json"}


def test_check_keys_recurses_into_list_of_dicts():
    payload = {"rows": [{"ok": 1}, {"nested": [{"winner": "FPT"}]}]}
    assert legal.check_keys(payload) == ["winner"]


def test_scrub_handles_deeply_nested_mixed_containers():
    payload = {"a": [[{"investment_rating": "nắm giữ", "x": 1}]],
               "b": ({"winner": "VNM"},)}
    out = legal.scrub(payload)
    assert out["a"] == [[{"x": 1}]]
    assert out["b"] == ({},)


# ── 4. Không phá payload hợp lệ ─────────────────────────────────────────────

def test_scrub_leaves_clean_payload_untouched():
    payload = {
        "symbol": "FPT",
        "health_score": 78,
        "metrics": {"pe": 21.3, "pb": 4.8, "roe": 0.271},
        "news": [{"title": "Doanh thu tăng 12%", "date": "2026-07-01"}],
        "risk_level": "trung bình",
        "note": None,
    }
    assert legal.check_keys(payload) == []
    assert legal.scrub(payload) == payload
    assert legal.check_all(payload)["ok"] is True


def test_scrub_does_not_mutate_input():
    payload = {"investment_rating": "mua", "keep": {"target_price": 1, "pe": 9}}
    snapshot = {"investment_rating": "mua", "keep": {"target_price": 1, "pe": 9}}
    legal.scrub(payload)
    assert payload == snapshot


def test_scrub_passes_through_scalars_and_empty():
    assert legal.scrub(None) is None
    assert legal.scrub("chuỗi thường") == "chuỗi thường"
    assert legal.scrub(12.5) == 12.5
    assert legal.scrub({}) == {}
    assert legal.scrub([]) == []
    assert legal.check_keys(None) == []
    assert legal.check_keys("investment_rating") == []   # string ≠ tên khoá


# ── 5. extra_keys cho từng call site ────────────────────────────────────────

def test_scrub_extra_keys_is_call_site_local():
    payload = {"verdict": "nên chọn FPT", "pe": 9}
    assert "verdict" in legal.scrub(payload)                      # mặc định giữ
    assert legal.scrub(payload, extra_keys=["verdict"]) == {"pe": 9}
    assert "verdict" not in legal.BANNED_KEYS                     # không nới toàn hệ


# ── 6. Không phá API cũ ─────────────────────────────────────────────────────

def test_legacy_api_still_intact():
    assert legal.check_text("Nhà đầu tư nên mua ngay")
    assert legal.check_text("Doanh thu tăng 12%") == []
    assert legal.check_payload({"a": ["khuyến nghị mua"]}) == ["khuyến nghị mua"]
    assert legal.DISCLAIMER and legal.LEGAL_PROMPT_RULE and legal.BANNED
