from __future__ import annotations

import time
from collections import deque
from threading import Lock

from .errors import RateLimitError


class InMemoryRateLimiter:
    def __init__(self, *, max_requests: int, window_seconds: int) -> None:
        if max_requests <= 0 or window_seconds <= 0:
            raise ValueError("rate limit values must be positive")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            values = self._requests.setdefault(key, deque())
            while values and values[0] <= cutoff:
                values.popleft()
            if len(values) >= self.max_requests:
                raise RateLimitError()
            values.append(now)
