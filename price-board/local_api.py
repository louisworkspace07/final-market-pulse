# -*- coding: utf-8 -*-
"""Local API — cổng AI mặc định của bảng giá (thay cho Gemini CDP).

Server local (dự án API share community) phơi endpoint kiểu OpenAI:

    POST http://localhost:4000/v1/chat/completions
    headers: {"x-api-key": <LOCAL_API_KEY>}
    body:    {"model": "gemini-cdp", "messages": [...]}

Nhờ vậy worker phân tích S/R không cần Chrome CDP + tài khoản Gemini đăng nhập nữa.

RÀNG BUỘC THẬT CỦA SERVER (server/src/routes/openai.routes.js):
- Hội thoại bị gộp bằng nội suy chuỗi `${msg.content}` → content BẮT BUỘC là
  chuỗi. **Kênh này KHÔNG gửi được ảnh** (mảng content-parts sẽ biến thành
  "[object Object]" mà server không hề báo lỗi) → phân tích chạy thuần text,
  ảnh biểu đồ chỉ dùng được ở kênh `gemini` (CDP).
- Chỉ role "user" ghi "User:", role khác thành "Assistant:".
- Provider xử lý tuần tự + cooldown 30s/task; server chờ tối đa 1 tiếng.

Cùng hợp đồng với `data-crawler/src/local_api.py`:
LOCAL_API_URL · LOCAL_API_MODEL · LOCAL_API_KEY · LOCAL_API_TIMEOUT.
Key đọc theo thứ tự: biến môi trường → `data-crawler/.env` (file dùng chung).
"""
import json
import os
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
# <root>/price-board → <root>/data-crawler/.env
ENV_FILE = os.path.normpath(os.path.join(BASE, "..", "data-crawler", ".env"))

DEFAULT_URL = "http://localhost:4000/v1/chat/completions"
DEFAULT_MODEL = "gemini-cdp"
# Task xếp hàng + cooldown 30s/provider → chờ vài phút là bình thường.
DEFAULT_TIMEOUT = 900.0


def _env_file_value(name):
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


def configured():
    return bool(api_key())


def _base_url():
    u = url()
    i = u.find("/v1/")
    return u[:i] if i > 0 else u.rstrip("/")


def available(timeout_s=3.0):
    """Server local có sống không — ping /health, không tốn lượt AI."""
    try:
        with urllib.request.urlopen(f"{_base_url()}/health", timeout=timeout_s) as r:
            return r.status < 400
    except Exception:
        return False


def _post(messages):
    key = api_key()
    if not key:
        raise RuntimeError("Thiếu LOCAL_API_KEY (đặt trong data-crawler/.env)")
    body = json.dumps({"model": model(), "messages": messages}).encode("utf-8")
    req = urllib.request.Request(
        url(), data=body,
        headers={"Content-Type": "application/json", "x-api-key": key})
    with urllib.request.urlopen(req, timeout=timeout()) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    text = ((data.get("choices") or [{}])[0].get("message", {}).get("content") or "")
    if not text.strip():
        raise RuntimeError("Local API trả về nội dung rỗng")
    return text


def ask(prompt, image_path=None):
    """Hỏi 1 lượt → text trả lời (đã bóc hàng rào ```json nếu có).

    `image_path` chỉ để tương thích chữ ký hàm với kênh CDP — server local KHÔNG
    nhận ảnh (xem docstring đầu file) nên tham số này bị bỏ qua."""
    return _clean(_post([{"role": "user", "content": prompt}]))


def _clean(text):
    t = (text or "").strip()
    if t.startswith("```json"):
        t = t[7:]
    elif t.startswith("```"):
        t = t[3:]
    if t.endswith("```"):
        t = t[:-3]
    return t.strip()


def status():
    """Tóm tắt cho UI (KHÔNG lộ API key)."""
    return {"url": url(), "model": model(),
            "has_key": configured(), "up": available()}
