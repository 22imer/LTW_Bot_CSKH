"""Per-user sliding-window rate limiter."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimiter:
    def __init__(
        self,
        max_events: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_events
        self._window = window_seconds
        self._clock = clock
        self._events: dict[int, deque[float]] = defaultdict(deque)

    def allow(self, user_id: int) -> bool:
        """Record an attempt; return False if the user is over the limit."""
        now = self._clock()
        events = self._events[user_id]
        while events and now - events[0] >= self._window:
            events.popleft()
        if len(events) >= self._max:
            return False
        events.append(now)
        return True
