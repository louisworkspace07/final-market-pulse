"""Rate-limit tại đúng tầng HTTP request thật (monkeypatch requests).

vnstock gọi nhiều HTTP request ngầm cho mỗi method → đếm token theo "method" không
chính xác. Giải pháp DevOps đúng: chặn ngay ở Session.request — mỗi HTTP request tới
host vnstock phải xin 1 token. VNDirect / Google (Gemini) được MIỄN (host & quota khác).
"""
from __future__ import annotations

import requests

from .ratelimit import TokenBucket

# Host được MIỄN rate-limit (quota riêng, rộng hơn).
_EXEMPT = ("vndirect.com.vn", "google.com", "gstatic", "googleapis")

_bucket: TokenBucket | None = None
_orig_request = requests.sessions.Session.request
_installed = False


def _patched(self, method, url, *args, **kwargs):
    if _bucket is not None and not any(h in url for h in _EXEMPT):
        _bucket.acquire(1)
    return _orig_request(self, method, url, *args, **kwargs)


def install(rate_per_min: float = 18, capacity: float = 4) -> None:
    """Bật giới hạn: tối đa `rate_per_min` HTTP request/phút tới host vnstock."""
    global _bucket, _installed
    _bucket = TokenBucket(rate_per_min, capacity=capacity)
    if not _installed:
        requests.sessions.Session.request = _patched
        _installed = True


def stats() -> dict:
    if _bucket is None:
        return {}
    return {"rate_per_min": round(_bucket.rate * 60, 1), "tokens": round(_bucket.tokens, 1)}
