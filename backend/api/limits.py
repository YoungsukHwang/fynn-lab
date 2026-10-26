"""Request limits for the public demo: a per-visitor hourly limit and a daily cap across all visitors.

Both count /chat requests. The site sends one request per bot, so one question to both bots counts twice.
Counts live in memory, so they reset when the server restarts; a spend limit on the Anthropic Console
workspace that holds the demo's key is the hard backstop. A limit left unset means no limit, which is the default for local use.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

HOUR = 3600
DAY = 86400
# Past this many visitors tracked at once, those idle for an hour are dropped.
MAX_TRACKED_VISITORS = 10_000


@dataclass(frozen=True)
class Refusal:
    scope: str  # "hour" (this visitor) or "day" (everyone)
    retry_after: int  # seconds until a request would be counted again


@dataclass
class ChatLimits:
    per_visitor_per_hour: int | None = None
    per_day: int | None = None  # all visitors, per UTC day
    clock: Callable[[], float] = time.time
    _visits: dict[str, deque[float]] = field(default_factory=dict)
    _day: int = -1
    _today: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def take(self, visitor: str) -> Refusal | None:
        """Counts one request from `visitor` and returns None, or returns why it is refused (and counts nothing)."""
        now = self.clock()
        day = int(now // DAY)
        with self._lock:
            if day != self._day:
                self._day, self._today = day, 0
            if self.per_day is not None and self._today >= self.per_day:
                return Refusal("day", max(1, int((day + 1) * DAY - now)))
            if self.per_visitor_per_hour is not None:
                visits = self._visits.setdefault(visitor, deque())
                while visits and visits[0] <= now - HOUR:
                    visits.popleft()
                if len(visits) >= self.per_visitor_per_hour:
                    return Refusal("hour", max(1, int(visits[0] + HOUR - now)))
                visits.append(now)
                if len(self._visits) > MAX_TRACKED_VISITORS:
                    self._visits = {v: q for v, q in self._visits.items() if q and q[-1] > now - HOUR}
            self._today += 1
        return None


def client_address(peer: str | None, forwarded_for: str | None, trust_forwarded: bool) -> str:
    """Who a request comes from. Behind a proxy (FYNN_TRUST_FORWARDED=1) that is the first address in
    X-Forwarded-For, which a client can set itself, so the per-visitor limit is fairness, not security.
    Neither limit bounds spending (the counts reset on restart); the key's workspace spend limit does."""
    if trust_forwarded and forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    return peer or "unknown"
