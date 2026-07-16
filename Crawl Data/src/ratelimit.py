"""Token-bucket rate limiter dùng chung cho nhiều worker (thread-safe).

Mục tiêu: ép tổng số request/phút sát trần cho phép (vd 55/60) thay vì delay cứng
gây lãng phí quota. Mỗi bước crawl xin trước số token ước lượng = số request nó gọi.
"""
from __future__ import annotations

import threading
import time


class TokenBucket:
    def __init__(self, rate_per_min: float, capacity: float | None = None):
        self.rate = rate_per_min / 60.0          # token/giây
        self.capacity = capacity if capacity is not None else max(rate_per_min, 20)
        self.tokens = self.capacity
        self.ts = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self, n: float = 1) -> float:
        """Chặn tới khi có đủ n token. Trả về số giây đã chờ."""
        n = min(n, self.capacity)
        waited = 0.0
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.ts) * self.rate)
                self.ts = now
                if self.tokens >= n:
                    self.tokens -= n
                    return waited
                need = (n - self.tokens) / self.rate
            sleep = min(need, 1.0)
            time.sleep(sleep)
            waited += sleep
