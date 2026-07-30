# -*- coding: utf-8 -*-
"""macro_ai — collector text-block + engine citation/legal validation (Phần C).

Không gọi AI thật (CDP/API). Chỉ test logic thuần: đóng gói dữ liệu, bóc citation
lạ, quét từ cấm — các hàm engine dùng để bảo vệ output."""
import os

from modules.macro_ai import engine, macro_data
from modules.common import legal


# ── engine._invalid_citations ────────────────────────────────────────────────
def test_invalid_citations_flags_unknown_ids():
    valid = {"M1", "M2", "M3"}
    obj = {"diem_sang": [{"y": "x", "bang_chung": ["M1", "M9"]}],
           "note": "theo [M2] và [M15]"}
    bad = engine._invalid_citations(obj, valid)
    assert bad == ["M15", "M9"]   # M9, M15 không thuộc tập hợp lệ


def test_invalid_citations_empty_when_all_valid():
    valid = {"M1", "M2"}
    obj = {"a": "[M1]", "b": ["M2"]}
    assert engine._invalid_citations(obj, valid) == []


# ── legal guardrail dùng trong engine ────────────────────────────────────────
def test_check_payload_catches_action_words():
    payload = {"kenh_truyen_dan": [{"co_che": "nhà đầu tư nên mua khi tỷ giá giảm"}]}
    assert "nên mua" in legal.check_payload(payload)


def test_legal_prompt_rule_present():
    assert legal.LEGAL_PROMPT_RULE and "khuyến nghị" in legal.LEGAL_PROMPT_RULE.lower()


# ── macro_data: probe luôn trả dict có 'available' (không ném) ───────────────
def test_probe_gold_never_raises_and_has_available_key():
    r = macro_data.probe_gold()
    assert isinstance(r, dict) and "available" in r
    if not r["available"]:
        assert "reason" in r   # fail phải có lý do, không biến mất


def test_probe_oil_never_raises_and_has_available_key():
    r = macro_data.probe_oil()
    assert isinstance(r, dict) and "available" in r
    if not r["available"]:
        assert "reason" in r


def test_build_macro_plus_shape():
    """macro_plus phải đủ khung: ≥6 indicator KEY (dù available hay không) + fx."""
    d = macro_data.build_macro_plus()
    assert len(d["indicators"]) >= 6
    for k in ("fx", "gold", "oil", "seed", "updated_at"):
        assert k in d
    # mọi indicator (kể cả fail) đều có cờ available
    assert all("available" in v for v in d["indicators"].values())


# ── collector: text block chứa mã [M..] hợp lệ + số liệu ─────────────────────
def test_collector_produces_valid_ids_and_text():
    from modules.macro_ai import collector
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    db = os.path.normpath(os.path.join(root, "..", "data-crawler", "database", "market.db"))
    dd = os.path.join(root, "gateway", "static", "data")
    c = collector.collect(db, dd)
    assert "text_block" in c and len(c["text_block"]) > 100
    # valid_ids đều dạng M<số>
    assert all(i.startswith("M") for i in c["valid_ids"])
    # news_meta khớp valid_ids
    assert set(c["news_meta"].keys()) == set(c["valid_ids"])
