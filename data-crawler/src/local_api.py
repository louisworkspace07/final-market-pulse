"""Local API — cổng AI DUY NHẤT của hệ thống (thay cho Gemini CDP).

Server local (dự án "API share comunity", thư mục Desktop/API share comunity)
phơi ra endpoint kiểu OpenAI:

    POST http://localhost:4000/v1/chat/completions
    headers: {"x-api-key": <LOCAL_API_KEY>}
    body:    {"model": "gemini-cdp", "messages": [{"role": "user", "content": "..."}]}

Bên trong nó đẩy task vào hàng đợi, provider-agent lái Gemini web trả kết quả về.
Mọi luồng phân tích AI chỉ cần gọi HTTP — KHÔNG tự mở Chrome/CDP, không Playwright.

RÀNG BUỘC THẬT CỦA SERVER (đọc từ server/src/routes/openai.routes.js +
services/dispatcher.service.js — đừng vi phạm, sẽ hỏng ngầm):
1. Server gộp hội thoại bằng `${msg.content}` → **content BẮT BUỘC là chuỗi**.
   Gửi mảng "content parts" kiểu OpenAI (ảnh) sẽ thành "[object Object]" mà
   KHÔNG báo lỗi. => Kênh này chỉ nhận TEXT, không gửi được ảnh.
2. Chỉ role "user" được ghi là "User:", MỌI role khác (kể cả "system") thành
   "Assistant:" → prompt hệ thống phải gộp vào tin nhắn user, đừng gửi role
   "system" (AI sẽ tưởng đó là lời nó từng nói).
3. Provider xử lý TUẦN TỰ, cooldown 30s sau mỗi task; server chờ tối đa 1 tiếng.
   => Gọi song song chỉ xếp hàng chứ không nhanh hơn, và timeout phải rộng tay.

Đây là bản Python dùng cho "data-crawler". Các dự án khác có bản sao tương đương
(`price-board/local_api.py`, `market-pulse/modules/common/local_api.py`,
`econolens-chat/lib/local_api.js`) — cùng hợp đồng, cùng biến môi trường:

- LOCAL_API_URL     (mặc định http://localhost:4000/v1/chat/completions)
- LOCAL_API_MODEL   (mặc định gemini-cdp)
- LOCAL_API_KEY     (bắt buộc — lấy trên dashboard của server local)
- LOCAL_API_TIMEOUT (giây, mặc định 300)

Key đọc theo thứ tự: biến môi trường → `data-crawler/.env`. Nhờ vậy chỉ cần khai
báo 1 chỗ là cả 4 dự án dùng chung.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_URL = "http://localhost:4000/v1/chat/completions"
DEFAULT_MODEL = "gemini-cdp"
# Task xếp hàng + cooldown 30s/provider → chờ vài phút là bình thường. Server tự
# bỏ cuộc ở mốc 1 tiếng; để 15 phút cho pipeline không treo quá lâu vì 1 mã.
DEFAULT_TIMEOUT = 900.0

# .env dùng chung của hệ thống (chính là file cấu hình của data-crawler).
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class LocalApiError(RuntimeError):
    """Lỗi khi gọi Local API.

    `retryable` = True với lỗi tạm thời (mạng, 429/5xx) → tầng trên nên thử lại;
    False với lỗi cứng (thiếu/sai API key) → thử lại cũng vô ích."""

    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


def _env_file_value(name: str) -> str:
    """Đọc 1 biến từ .env (không cần python-dotenv, không ghi đè os.environ)."""
    try:
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == name:
                return v.strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def api_key() -> str:
    return (os.environ.get("LOCAL_API_KEY") or _env_file_value("LOCAL_API_KEY") or "").strip()


def url() -> str:
    return (os.environ.get("LOCAL_API_URL") or _env_file_value("LOCAL_API_URL")
            or DEFAULT_URL).strip()


def model() -> str:
    return (os.environ.get("LOCAL_API_MODEL") or _env_file_value("LOCAL_API_MODEL")
            or DEFAULT_MODEL).strip()


def timeout() -> float:
    raw = os.environ.get("LOCAL_API_TIMEOUT") or _env_file_value("LOCAL_API_TIMEOUT")
    try:
        return float(raw) if raw else DEFAULT_TIMEOUT
    except ValueError:
        return DEFAULT_TIMEOUT


def _base_url() -> str:
    """Gốc server (bỏ phần /v1/...) — dùng cho /health."""
    u = url()
    idx = u.find("/v1/")
    return u[:idx] if idx > 0 else u.rstrip("/")


def normalize_messages(messages: list[dict]) -> list[dict]:
    """Ép hội thoại về đúng thứ server hiểu: content là CHUỖI, role là user/assistant.

    - content không phải chuỗi (vd content-parts kèm ảnh) → server nội suy thành
      "[object Object]" trong im lặng, nên chặn ngay tại đây.
    - role "system" bị server gán nhãn "Assistant:" → gộp vào tin nhắn user kế
      tiếp để chỉ thị hệ thống không bị hiểu nhầm là lời của AI."""
    out: list[dict] = []
    pending_system = ""
    for m in messages:
        role = (m.get("role") or "user").strip().lower()
        content = m.get("content")
        if not isinstance(content, str):
            raise LocalApiError(
                "Local API chỉ nhận content dạng chuỗi (server gộp prompt bằng "
                "nội suy chuỗi) — không gửi được ảnh/content-parts qua kênh này.",
                retryable=False)
        if role == "system":
            pending_system = f"{pending_system}\n\n{content}".strip()
            continue
        if pending_system and role == "user":
            content = f"{pending_system}\n\n{content}"
            pending_system = ""
        out.append({"role": "assistant" if role == "assistant" else "user",
                    "content": content})
    if pending_system:      # chỉ có system, chưa có lượt user nào
        out.append({"role": "user", "content": pending_system})
    return out


def ask(prompt: str, retries: int = 2, messages: list[dict] | None = None) -> str:
    """Hỏi Local API 1 lượt, trả về text trả lời.

    `messages`: nếu truyền vào thì gửi nguyên hội thoại (giữ ngữ cảnh nhiều lượt);
    ngược lại gói `prompt` thành 1 message user. Lỗi tạm thời (mạng/429/5xx) được
    thử lại `retries` lần với backoff 3s/9s; lỗi auth ném ngay."""
    key = api_key()
    if not key:
        raise LocalApiError(
            "Thiếu LOCAL_API_KEY — điền vào data-crawler/.env (hoặc ô API key trên "
            "bảng điều khiển :5000) rồi chạy lại.", retryable=False)

    msgs = normalize_messages(messages if messages else [{"role": "user", "content": prompt}])
    payload = json.dumps({"model": model(), "messages": msgs}).encode("utf-8")
    attempts = max(1, retries + 1)
    last: LocalApiError | None = None

    for i in range(attempts):
        req = urllib.request.Request(
            url(), data=payload,
            headers={"Content-Type": "application/json", "x-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=timeout()) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            if not (text or "").strip():
                raise LocalApiError("Local API trả về nội dung rỗng.")
            return text
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")[:200]
            except Exception:
                pass
            # 4xx = lỗi do request (key sai, payload không hợp lệ) → lỗi cứng,
            # gửi lại y hệt chỉ tốn lượt. Chỉ 429 là đáng thử lại.
            hard = 400 <= exc.code < 500 and exc.code != 429
            last = LocalApiError(f"Local API HTTP {exc.code}: {body}", retryable=not hard)
            if hard:
                raise last
        except LocalApiError as exc:
            last = exc
            if not exc.retryable:
                raise
        except Exception as exc:
            last = LocalApiError(
                f"Không gọi được Local API ở {url()}: {str(exc)[:160]} "
                f"(server local đã chạy chưa?)")

        if i < attempts - 1:
            wait = 3.0 * (3 ** i)
            print(f"  [retry] Local API lỗi ({str(last)[:80]}) — thử lại sau {wait:.0f}s "
                  f"(lượt {i + 2}/{attempts}).")
            time.sleep(wait)

    raise last if last else LocalApiError("Local API không trả về kết quả.")


def available(timeout_s: float = 3.0) -> bool:
    """Server local có đang chạy không (gọi /health, không tốn lượt AI)."""
    try:
        with urllib.request.urlopen(f"{_base_url()}/health", timeout=timeout_s) as resp:
            return resp.status < 400
    except Exception:
        return False


def status() -> dict:
    """Tóm tắt trạng thái để bảng điều khiển hiển thị (không lộ API key)."""
    return {
        "url": url(),
        "model": model(),
        "up": available(),
        "has_key": bool(api_key()),
    }
