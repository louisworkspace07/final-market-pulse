# -*- coding: utf-8 -*-
"""Circuit breaker cho kênh CDP — offline, không cần Chrome/API key.

Kịch bản chính: CDP chết → sau N lỗi breaker MỞ → ask_gemini vẫn trả kết quả
qua API (mock) → hết cooldown half-open → CDP sống lại → breaker RESET.
"""
import time

import pytest

from modules.market_overview import gemini_transport as gt


@pytest.fixture(autouse=True)
def _reset_breaker(monkeypatch):
    """Mỗi test bắt đầu với breaker sạch + ngưỡng nhỏ cho nhanh."""
    gt._breaker["fails"].clear()
    gt._breaker["opened_at"] = None
    monkeypatch.setattr(gt, "BREAKER_FAIL_MAX", 3)
    monkeypatch.setattr(gt, "BREAKER_WINDOW", 60)
    monkeypatch.setattr(gt, "BREAKER_COOLDOWN", 120)
    # môi trường sạch: không để env thật ghi đè prefer
    monkeypatch.delenv("AI_TRANSPORT_REALTIME", raising=False)
    # File này chỉ kiểm breaker của kênh CDP → tắt kênh local_api (kênh mặc định)
    # để thứ tự thử rút về cdp → api đúng như kịch bản đang test.
    monkeypatch.setattr(gt, "_local_api_ready", lambda: False)
    yield
    gt._breaker["fails"].clear()
    gt._breaker["opened_at"] = None


def _cdp_up(monkeypatch):
    """Giả lập worker CDP đang chạy + đã login."""
    monkeypatch.setitem(gt._state, "running", True)
    monkeypatch.setitem(gt._state, "logged_in", True)


def test_breaker_opens_after_max_fails(monkeypatch):
    _cdp_up(monkeypatch)
    monkeypatch.setattr(gt, "_ask_cdp",
                        lambda p, timeout=120: (_ for _ in ()).throw(RuntimeError("tab chết")))
    monkeypatch.setattr(gt, "_ask_api", lambda p: "API OK")

    for _ in range(3):
        out = gt.ask_gemini("ping", prefer="auto")
        assert out["transport"] == "api"          # fallback hoạt động từng lượt

    st = gt.breaker_status()
    assert st["open"] is True                     # đủ 3 lỗi → breaker mở
    assert st["fails_in_window"] >= 3


def test_when_open_skips_cdp_entirely(monkeypatch):
    _cdp_up(monkeypatch)
    gt._breaker["opened_at"] = time.time()        # ép breaker mở

    calls = {"cdp": 0}
    def _cdp(p, timeout=120):
        calls["cdp"] += 1
        return "CDP OK"
    monkeypatch.setattr(gt, "_ask_cdp", _cdp)
    monkeypatch.setattr(gt, "_ask_api", lambda p: "API OK")

    out = gt.ask_gemini("ping", prefer="auto")
    assert out["transport"] == "api"
    assert calls["cdp"] == 0                      # CDP không được đụng tới


def test_half_open_then_reset(monkeypatch):
    _cdp_up(monkeypatch)
    gt._breaker["opened_at"] = time.time() - 999  # đã quá cooldown 120s → half-open
    monkeypatch.setattr(gt, "_ask_cdp", lambda p, timeout=120: "CDP OK")

    out = gt.ask_gemini("ping", prefer="auto")
    assert out["transport"].startswith("cdp")     # half-open cho thử lại CDP
    assert gt.breaker_status()["open"] is False   # thành công → RESET


def test_prefer_cdp_bypasses_breaker(monkeypatch):
    """User ép prefer='cdp' → vẫn được thử CDP dù breaker mở (chủ động)."""
    _cdp_up(monkeypatch)
    gt._breaker["opened_at"] = time.time()
    monkeypatch.setattr(gt, "_ask_cdp", lambda p, timeout=120: "CDP OK")

    out = gt.ask_gemini("ping", prefer="cdp")
    assert out["transport"].startswith("cdp")


def test_env_realtime_forces_api(monkeypatch):
    """AI_TRANSPORT_REALTIME=api → prefer='auto' đi thẳng API, không đụng CDP."""
    _cdp_up(monkeypatch)
    monkeypatch.setenv("AI_TRANSPORT_REALTIME", "api")
    calls = {"cdp": 0}
    def _cdp(p, timeout=120):
        calls["cdp"] += 1
        return "CDP OK"
    monkeypatch.setattr(gt, "_ask_cdp", _cdp)
    monkeypatch.setattr(gt, "_ask_api", lambda p: "API OK")

    out = gt.ask_gemini("ping", prefer="auto")
    assert out["transport"] == "api"
    assert calls["cdp"] == 0


def test_open_session_falls_to_api_when_breaker_open(monkeypatch):
    _cdp_up(monkeypatch)
    gt._breaker["opened_at"] = time.time()
    monkeypatch.setattr(gt, "_gemini_api_config", lambda: ("fake-key", "gemini-x"))

    s = gt.open_session(prefer="auto")
    assert s.backend == "api"                     # không thử mở tab CDP
    s.close()


def test_facade_reexports():
    from modules.common import ai_transport as fa
    assert fa.ask_gemini is gt.ask_gemini
    assert fa.open_session is gt.open_session
    assert fa.parse_json_answer is gt.parse_json_answer
    assert fa.breaker_status is gt.breaker_status
