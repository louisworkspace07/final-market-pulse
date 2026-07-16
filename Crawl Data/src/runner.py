"""Tiện ích chạy crawl chịu được rate-limit (60 req/phút bản community).

vnstock có thể ném SystemExit khi chạm giới hạn → guard() bắt cả BaseException,
nghỉ cooldown rồi thử lại.
"""
from __future__ import annotations

import time

COOLDOWN = 65       # nghỉ khi chạm rate-limit (giây)
RETRIES = 2


def _is_ratelimit(exc: BaseException) -> bool:
    s = str(exc).lower()
    return ("rate" in s or "60 request" in s or "request/ph" in s
            or "quá nhiều" in s or isinstance(exc, SystemExit))


def guard(fn, *args, **kwargs):
    """Chạy fn(*args), retry với cooldown khi rate-limit. Ném lại nếu vẫn lỗi.

    Chỉ bắt Exception + SystemExit (vnstock đôi khi ném SystemExit khi rate-limit).
    KeyboardInterrupt (Ctrl+C) KHÔNG bị bắt → người dùng vẫn dừng được tiến trình.
    """
    last = None
    for k in range(RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except (Exception, SystemExit) as exc:
            last = exc
            if _is_ratelimit(exc):
                print(f"      ⏳ rate-limit, nghỉ {COOLDOWN}s...", flush=True)
                time.sleep(COOLDOWN)
            else:
                time.sleep(2 * (k + 1))
    raise last
