"""Client Local API + chọn backend — offline, không gọi mạng thật."""
import json

import pytest

from src import analyzer, local_api


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("AI_BACKEND", "LOCAL_API_KEY", "LOCAL_API_URL",
              "LOCAL_API_MODEL", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    # Không đọc .env thật của máy dev → test tất định.
    monkeypatch.setattr(local_api, "_env_file_value", lambda name: "")
    yield


def test_defaults():
    assert local_api.url() == local_api.DEFAULT_URL
    assert local_api.model() == "gemini-cdp"
    assert local_api.api_key() == ""


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("LOCAL_API_URL", "http://127.0.0.1:9000/v1/chat/completions")
    monkeypatch.setenv("LOCAL_API_MODEL", "abc")
    assert local_api.url().endswith(":9000/v1/chat/completions")
    assert local_api.model() == "abc"


def test_env_file_is_fallback_for_key(monkeypatch):
    monkeypatch.setattr(local_api, "_env_file_value",
                        lambda name: "tu-file" if name == "LOCAL_API_KEY" else "")
    assert local_api.api_key() == "tu-file"
    monkeypatch.setenv("LOCAL_API_KEY", "tu-env")
    assert local_api.api_key() == "tu-env"      # env thắng file


def test_ask_without_key_is_hard_error():
    with pytest.raises(local_api.LocalApiError) as ei:
        local_api.ask("ping")
    assert ei.value.retryable is False          # thiếu key → retry vô ích


def test_ask_posts_openai_shape(monkeypatch):
    monkeypatch.setenv("LOCAL_API_KEY", "k123")
    seen = {}

    class _Resp:
        def read(self):
            return json.dumps({"choices": [{"message": {"content": "xin chao"}}]}).encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        seen["key"] = req.get_header("X-api-key")
        seen["body"] = json.loads(req.data.decode())
        return _Resp()

    monkeypatch.setattr(local_api.urllib.request, "urlopen", fake_urlopen)
    assert local_api.ask("ping") == "xin chao"
    assert seen["url"] == local_api.DEFAULT_URL
    assert seen["key"] == "k123"
    assert seen["body"]["model"] == "gemini-cdp"
    assert seen["body"]["messages"] == [{"role": "user", "content": "ping"}]


def test_resolve_backend_defaults_to_local_api(monkeypatch):
    assert analyzer.resolve_backend() == "local_api"          # không key nào cả
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert analyzer.resolve_backend() == "claude"             # chỉ có key Claude
    monkeypatch.setenv("LOCAL_API_KEY", "y")
    assert analyzer.resolve_backend() == "local_api"          # có server local → ưu tiên
    monkeypatch.setenv("AI_BACKEND", "gemini")
    assert analyzer.resolve_backend() == "gemini"             # khai báo tay vẫn thắng


def test_local_api_calls_are_independent(monkeypatch):
    """Mỗi lượt phân tích gửi ĐỘC LẬP, không kèm lịch sử các lượt trước.

    Server gộp mọi messages thành 1 chuỗi prompt nên phát lại lịch sử làm payload
    phình lên qua từng lượt (đo thật: lượt 3 = 10.992 ký tự) — từng làm hỏng
    3/5 lượt của mỗi mã."""
    seen = []

    def fake_ask(prompt, messages=None):
        seen.append({"prompt": prompt, "messages": messages})
        return f"tra loi {len(seen)}"

    monkeypatch.setattr(analyzer.local_api, "ask", fake_ask)
    assert analyzer._raw_local_api("cau 1") == "tra loi 1"
    assert analyzer._raw_local_api("cau 2") == "tra loi 2"
    assert [s["prompt"] for s in seen] == ["cau 1", "cau 2"]
    assert all(s["messages"] is None for s in seen)      # không đính lịch sử


def test_http_400_khong_thu_lai(monkeypatch):
    """4xx (trừ 429) là lỗi cứng — gửi lại y hệt chỉ tốn lượt."""
    import urllib.error

    calls = []

    def boom(req, timeout=None):
        calls.append(1)
        raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, None)

    monkeypatch.setenv("LOCAL_API_KEY", "k")
    monkeypatch.setattr(local_api.urllib.request, "urlopen", boom)
    with pytest.raises(local_api.LocalApiError) as exc:
        local_api.ask("hi")
    assert exc.value.retryable is False
    assert len(calls) == 1                                # đúng 1 lần, không retry
