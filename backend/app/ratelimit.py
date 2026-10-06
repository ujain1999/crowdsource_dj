"""Small in-memory rate limiters. State is per process, which is enough for a
single uvicorn worker."""

import threading
import time
from collections import deque


class SlidingWindow:
    """At most `limit` hits per `window` seconds for each key."""

    def __init__(self, limit: int, window: float):
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque:
        hits = self._hits.get(key)
        if hits is None:
            hits = self._hits[key] = deque()
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        return hits

    def blocked(self, key: str) -> bool:
        with self._lock:
            hits = self._prune(key, time.monotonic())
            if not hits:
                self._hits.pop(key, None)
            return len(hits) >= self.limit

    def hit(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, now).append(now)
            if len(self._hits) > 10_000:
                # Drop idle keys so the table can't grow without bound.
                for k in [k for k, h in self._hits.items() if not h or h[-1] <= now - self.window]:
                    del self._hits[k]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def allow(self, key: str) -> bool:
        """Record a hit and report whether it was within the limit."""
        if self.blocked(key):
            return False
        self.hit(key)
        return True


class TokenBucket:
    """Per-connection limiter: `rate` messages a second, bursts up to `burst`."""

    def __init__(self, rate: float, burst: float):
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last = time.monotonic()

    def allow(self) -> bool:
        now = time.monotonic()
        self.tokens = min(self.burst, self.tokens + (now - self.last) * self.rate)
        self.last = now
        if self.tokens < 1:
            return False
        self.tokens -= 1
        return True
