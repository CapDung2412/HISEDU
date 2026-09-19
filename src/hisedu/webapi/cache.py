from __future__ import annotations

import copy
import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass(slots=True)
class _Entry(Generic[T]):
    expires_at: float
    value: T


class TTLCache(Generic[T]):
    """Small process-local cache with bounded memory and defensive copies."""

    def __init__(self, *, ttl_seconds: int = 900, max_items: int = 256) -> None:
        if ttl_seconds <= 0 or max_items <= 0:
            raise ValueError("ttl_seconds and max_items must be positive")
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self._items: OrderedDict[str, _Entry[T]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> T | None:
        now = time.monotonic()
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return copy.deepcopy(entry.value)

    def set(self, key: str, value: T) -> None:
        now = time.monotonic()
        with self._lock:
            self._items[key] = _Entry(now + self.ttl_seconds, copy.deepcopy(value))
            self._items.move_to_end(key)
            while len(self._items) > self.max_items:
                self._items.popitem(last=False)
