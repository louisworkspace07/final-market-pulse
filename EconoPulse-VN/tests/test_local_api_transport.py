# -*- coding: utf-8 -*-
"""Kênh Local API là kênh MẶC ĐỊNH của transport — offline, không gọi mạng thật.

Kiểm: thứ tự thử kênh, phiên hội thoại giữ lịch sử, và fallback khi server local
chưa cấu hình.
"""
import pytest

from modules.common import local_api as la
from modules.market_overview import gemini_transport as gt


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("AI_TRANSPORT_REALTIME", raising=False)
    gt._breaker["fails"].clear()
    gt._breaker["opened_at"] = None
    # CDP coi như chưa chạy để không đụng Chrome thật.
    monkeypatch.setitem(gt._state, "running", False)
    monkeypatch.setitem(gt._state, "logged_in", False)
    yield


def _local_on(monkeypatch, answer="LOCAL OK"):
    monkeypatch.setattr(gt, "_local_api_ready", lambda: True)
    monkeypatch.setattr(la, "ask", lambda p: answer)
    monkeypatch.setattr(gt, "_ask_local_api", lambda p: answer)


def test_auto_order_puts_local_first():
    assert gt._order_for("auto")[0] == "local"
    assert gt._order_for("local") == ["local"]
    assert gt._order_for("cdp") == ["cdp"]


def test_prefer_aliases_normalize():
    assert gt._resolve_prefer("local_api") == "local"
    assert gt._resolve_prefer("localapi") == "local"


def test_env_can_force_local(monkeypatch):
    monkeypatch.setenv("AI_TRANSPORT_REALTIME", "local")
    assert gt._resolve_prefer("auto") == "local"


def test_ask_uses_local_by_default(monkeypatch):
    _local_on(monkeypatch)
    out = gt.ask_gemini("ping", prefer="auto")
    assert out["transport"] == "local_api"
    assert out["text"] == "LOCAL OK"


def test_ask_falls_through_when_local_not_configured(monkeypatch):
    """Chưa có LOCAL_API_KEY → bỏ qua kênh local, dùng API (không chết)."""
    monkeypatch.setattr(gt, "_local_api_ready", lambda: False)
    monkeypatch.setattr(gt, "_ask_api", lambda p: "API OK")
    out = gt.ask_gemini("ping", prefer="auto")
    assert out["transport"] == "api"


def test_prefer_local_without_key_raises(monkeypatch):
    monkeypatch.setattr(gt, "_local_api_ready", lambda: False)
    with pytest.raises(RuntimeError):
        gt.ask_gemini("ping", prefer="local")


def test_open_session_default_is_local(monkeypatch):
    _local_on(monkeypatch)
    s = gt.open_session(prefer="auto")
    assert s.backend == "local_api"
    assert s.transport == "local_api"
    s.close()


def test_session_accumulates_history(monkeypatch):
    """Endpoint stateless → phiên phải gửi lại lịch sử để giữ ngữ cảnh."""
    seen = []

    def fake(messages):
        seen.append(list(messages))
        return f"tra loi {len(seen)}"

    monkeypatch.setattr(gt, "_local_api_ready", lambda: True)
    monkeypatch.setattr(la, "ask_messages", fake)

    with gt.open_session(prefer="local") as s:
        assert s.ask("cau 1") == "tra loi 1"
        assert s.ask("cau 2") == "tra loi 2"

    assert [m["content"] for m in seen[0]] == ["cau 1"]
    # Lượt 2 phải mang theo hỏi-đáp của lượt 1.
    assert [m["role"] for m in seen[1]] == ["user", "assistant", "user"]
    assert [m["content"] for m in seen[1]] == ["cau 1", "tra loi 1", "cau 2"]


def test_cdp_status_reports_local_channel(monkeypatch):
    monkeypatch.setattr(la, "available", lambda timeout_s=3.0: True)
    monkeypatch.setattr(la, "api_key", lambda: "k")
    st = gt.cdp_status()
    assert st["local_api"]["has_key"] is True
    assert st["local_api"]["up"] is True
    assert "breaker" in st            # giữ nguyên khóa cũ cho UI
