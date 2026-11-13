# -*- coding: utf-8 -*-
"""Local API — cổng AI mặc định của market-pulse (thay cho Gemini CDP).

Server local (dự án API share community) phơi endpoint kiểu OpenAI:

    POST http://localhost:4000/v1/chat/completions
    headers: {"x-api-key": <LOCAL_API_KEY>}
    body:    {"model": "gemini-cdp", "messages": [...]}

Nó đẩy task vào hàng đợi, provider-agent lái Gemini web trả kết quả về; gateway
chỉ cần gọi HTTP: không mở Chrome, không Playwright, không phụ thuộc CAPTCHA.

RÀNG BUỘC THẬT CỦA SERVER (openai.routes.js + dispatcher.service.js):
1. Server gộp hội thoại bằng nội suy chuỗi → content BẮT BUỘC là chuỗi (không
   gửi được ảnh/content-parts; sai kiểu sẽ thành "[object Object]" mà không báo lỗi).
2. Chỉ role "user" ghi là "User:", role khác (kể cả "system") thành "Assistant:"
   → chỉ thị hệ thống phải gộp vào tin nhắn user. `normalize_messages` lo việc này.
3. Provider chạy TUẦN TỰ + cooldown 30s/task, server chờ tối đa 1 tiếng → gọi
   song song chỉ xếp hàng; timeout để rộng.

Cùng hợp đồng với `data-crawler/src/local_api.py` và `econolens-chat/lib/local_api.js`:
LOCAL_API_URL · LOCAL_API_MODEL · LOCAL_API_KEY · LOCAL_API_TIMEOUT.
Key đọc theo thứ tự: biến môi trường → `data-crawler/.env` (file dùng chung).
"""
import os

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(BASE, "..", ".."))
# .env dùng chung toàn hệ thống (nằm ở dự án data-crawler).
ENV_FILE = os.path.normpath(os.path.join(ROOT, "..", "data-crawler", ".env"))

DEFAULT_URL = "http://localhost:4000/v1/chat/completions"
DEFAULT_MODEL = "gemini-cdp"
# Task xếp hàng + cooldown 30s/provider → chờ vài phút là bình thường.
DEFAULT_TIMEOUT = 900.0


def _env_file_value(name):
    """Đọc 1 biến từ .env dùng chung (không ghi đè os.environ)."""
    try:
        with open(ENV_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == name:
                    return v.strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def _cfg(name, default=""):
    return (os.environ.get(name) or _env_file_value(name) or default).strip()


def api_key():
    return _cfg("LOCAL_API_KEY")


def url():
    return _cfg("LOCAL_API_URL", DEFAULT_URL)


def model():
    return _cfg("LOCAL_API_MODEL", DEFAULT_MODEL)


def timeout():
    try:
        return float(_cfg("LOCAL_API_TIMEOUT") or DEFAULT_TIMEOUT)
    except ValueError:
        return DEFAULT_TIMEOUT


def _base_url():
    u = url()
    i = u.find("/v1/")
    return u[:i] if i > 0 else u.rstrip("/")


def configured():
    """Có đủ cấu hình để dùng kênh này không (không gọi mạng)."""
    return bool(api_key())


def available(timeout_s=3.0):
    """Server local có sống không — ping /health hoặc /api/status, không tốn lượt AI."""
    base = _base_url()
    for endpoint in ("/health", "/api/status"):
        try:
            if requests.get(f"{base}{endpoint}", timeout=timeout_s).ok:
                return True
        except Exception:
            continue
    return False


def normalize_messages(messages):
    """Ép về đúng thứ server hiểu: content là CHUỖI, role chỉ user/assistant.

    role "system" bị server gán nhãn "Assistant:" → gộp vào tin nhắn user kế tiếp
    để AI không tưởng chỉ thị hệ thống là lời chính nó đã nói."""
    out, pending = [], ""
    for m in messages:
        role = (m.get("role") or "user").strip().lower()
        content = m.get("content")
        if not isinstance(content, str):
            raise RuntimeError("Local API chỉ nhận content dạng chuỗi "
                               "(không gửi được ảnh/content-parts qua kênh này)")
        if role == "system":
            pending = f"{pending}\n\n{content}".strip()
            continue
        if pending and role == "user":
            content, pending = f"{pending}\n\n{content}", ""
        out.append({"role": "assistant" if role == "assistant" else "user",
                    "content": content})
    if pending:
        out.append({"role": "user", "content": pending})
    return out


def ask_messages(messages):
    """Gửi nguyên hội thoại messages[] (giữ ngữ cảnh) → trả text trả lời."""
    key = api_key()
    if not key:
        raise RuntimeError("Thiếu LOCAL_API_KEY (đặt trong data-crawler/.env hoặc biến môi trường)")
    r = requests.post(
        url(), json={"model": model(), "messages": normalize_messages(messages)},
        headers={"Content-Type": "application/json", "x-api-key": key},
        timeout=timeout())
    if r.status_code in (401, 403):
        raise RuntimeError(f"Local API từ chối (HTTP {r.status_code}) — kiểm tra LOCAL_API_KEY")
    if not r.ok:
        raise RuntimeError(f"Local API HTTP {r.status_code}: {r.text[:160]}")
    text = ((r.json().get("choices") or [{}])[0].get("message", {}).get("content") or "")
    if not text.strip():
        raise RuntimeError("Local API trả về nội dung rỗng")
    return text


def ask(prompt):
    """Hỏi 1 lượt không ngữ cảnh."""
    return ask_messages([{"role": "user", "content": prompt}])


def status():
    """Tóm tắt cho dashboard (KHÔNG lộ API key)."""
    return {"url": url(), "model": model(),
            "has_key": configured(), "up": available()}
