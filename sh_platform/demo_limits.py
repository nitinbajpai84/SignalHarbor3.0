"""Public-demo guards, all read from the environment (names only; no value is printed). They apply in SH_MODE=prod and stay out of the way in dev.

- SH_DAILY_MODEL_CAP_USD: model spend per company per UTC day (default 2 in prod, off elsewhere; 0 switches it off). The router refuses a call
  once the day's cost log reaches it, and the agents carry on by rules.
- SH_CHAT_TURNS_PER_HOUR: agent chat turns per account per hour (default 30 in prod, off elsewhere; 0 switches it off).
- SH_ENABLE_SUPERADMIN=1: opens the super-admin routes in prod (closed by default).
- SH_ALLOW_REAL_MODE=1: lets a company switch to Real use in prod (the public demo stays on Testing).
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone


def _prod() -> bool:
    return (os.environ.get("SH_MODE") or "").strip().lower() == "prod"


def _number(name: str, prod_default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    try:
        return max(0.0, float(raw)) if raw else (prod_default if _prod() else 0.0)
    except ValueError:
        return prod_default if _prod() else 0.0


def daily_cap_usd() -> float:
    return _number("SH_DAILY_MODEL_CAP_USD", 2.0)


def turns_per_hour() -> int:
    return int(_number("SH_CHAT_TURNS_PER_HOUR", 30))


def superadmin_open() -> bool:
    return not _prod() or (os.environ.get("SH_ENABLE_SUPERADMIN") or "").strip() == "1"


def real_mode_allowed() -> bool:
    return not _prod() or (os.environ.get("SH_ALLOW_REAL_MODE") or "").strip() == "1"


def spent_today(log_path, now: datetime | None = None) -> float:
    """Sum of cost_usd in a model cost log for the current UTC day. ponytail: re-reads the log per call; a per-day running total if it grows large."""
    day = (now or datetime.now(timezone.utc)).date().isoformat()
    total = 0.0
    try:
        for line in open(log_path, encoding="utf-8"):
            if day not in line[:40]:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict) and str(r.get("at", "")).startswith(day) and isinstance(r.get("cost_usd"), (int, float)):
                total += r["cost_usd"]
    except OSError:
        pass
    return total


def over_cap(log_path, now: datetime | None = None) -> bool:
    cap = daily_cap_usd()
    return cap > 0 and spent_today(log_path, now) >= cap


# the agent chat routes (POST only): where a model turn can start. Matched by ending so a new room's chat or ask route is
# covered without a list to keep (…/chat, …/ask, …/ask_finance, …/north/turns, …/room/messages, …/chat/files)
CHAT_ROUTE = re.compile(r"^/api/.*/(?:chat(?:/files)?|ask|ask_finance|north/turns|room/messages)$")


class TurnLimiter:
    """Sliding window per account. Simple mode: process memory. Production mode: Redis, so every web replica counts the same turns."""

    def __init__(self, clock=time.time):
        from sh_platform import mode
        from sh_platform.state import kv
        self.clock, self.hits, self.lock = clock, defaultdict(deque), threading.Lock()
        self.win = kv.window() if mode.production() else None

    def allow(self, account_id: str, limit: int | None = None, window: int = 3600) -> bool:
        limit = turns_per_hour() if limit is None else limit
        if limit <= 0:
            return True
        now = self.clock()
        if self.win is not None:
            return self.win.allow(account_id, limit, window, now)
        with self.lock:
            q = self.hits[account_id]
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

