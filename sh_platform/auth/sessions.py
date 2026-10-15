"""Signed session cookie plus a server-side session table, and the login lockout."""
import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from typing import Callable

IDLE_SECONDS = 30 * 60
ABSOLUTE_SECONDS = 8 * 60 * 60
MAX_FAILURES = 5
LOCK_SECONDS = 60
STALE_SECONDS = 15 * 60  # a count of failures below the limit is forgotten after this long
MAX_TRACKED = 10_000


class SessionManager:
    def __init__(self, secret: str, idle: int = IDLE_SECONDS, absolute: int = ABSOLUTE_SECONDS,
                 clock: Callable[[], float] = time.time):
        self._key = secret.encode()
        self.idle, self.absolute, self._clock = idle, absolute, clock
        self._table: dict[str, dict] = {}
        self._lock = threading.Lock()

    def _sig(self, text: str) -> str:
        return hmac.new(self._key, text.encode(), hashlib.sha256).hexdigest()

    def csrf_for(self, sid: str) -> str:
        return self._sig("csrf:" + sid)

    def _live(self, rec: dict, now: float) -> bool:
        return now - rec["last_seen"] <= self.idle and now - rec["created"] <= self.absolute

    def create(self, account: dict) -> tuple[str, str]:
        """Returns (session cookie value, csrf token)."""
        now = self._clock()
        sid = secrets.token_urlsafe(24)
        with self._lock:
            self._table = {k: v for k, v in self._table.items() if self._live(v, now)}
            self._table[sid] = {"account_id": account["account_id"], "company_id": account["company_id"],
                                "roles": list(account["roles"]), "created": now, "last_seen": now}
        payload = {"sid": sid, "account_id": account["account_id"], "iat": now, "exp": now + self.absolute}
        body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
        return f"{body}.{self._sig(body)}", self.csrf_for(sid)

    def resolve(self, cookie: str | None) -> dict | None:
        """Session record (with sid) for a valid, live cookie; touches the idle timer."""
        try:
            body, sig = (cookie or "").rsplit(".", 1)
            if not hmac.compare_digest(sig, self._sig(body)):
                return None
            payload = json.loads(base64.urlsafe_b64decode(body))
            now = self._clock()
            with self._lock:
                rec = self._table.get(payload["sid"])
                if (not rec or now > payload["exp"] or rec["account_id"] != payload["account_id"]
                        or not self._live(rec, now)):
                    self._table.pop(payload["sid"], None)
                    return None
                rec["last_seen"] = now
                return {**rec, "sid": payload["sid"]}
        except (ValueError, KeyError, TypeError):
            return None

    def is_live(self, sid) -> bool:
        """Is this server-side session still alive? Does NOT touch the idle timer: a long-lived stream asks this on
        every tick, and calling resolve() there would keep the session alive for as long as the stream is open."""
        with self._lock:
            rec = self._table.get(sid) if isinstance(sid, str) else None
            return rec is not None and self._live(rec, self._clock())

    def destroy(self, sid: str) -> None:
        with self._lock:
            self._table.pop(sid, None)


class LoginThrottle:
    """Lock a login name for LOCK_SECONDS after MAX_FAILURES; counts unknown names too."""

    def __init__(self, clock: Callable[[], float] = time.time):
        # key -> (failure count, locked until, time of last failure)
        self._clock, self._state, self._lock = clock, {}, threading.Lock()

    def locked(self, key: str) -> bool:
        with self._lock:
            return self._state.get(key, (0, 0.0, 0.0))[1] > self._clock()

    def failed(self, key: str) -> None:
        with self._lock:
            now = self._clock()
            count, until, _ = self._state.get(key, (0, 0.0, 0.0))
            count = 1 if until and until <= now else count + 1
            self._state[key] = (count, now + LOCK_SECONDS if count >= MAX_FAILURES else 0.0, now)
            if len(self._state) >= MAX_TRACKED:
                self._prune(now)

    def _prune(self, now: float) -> None:
        self._state = {k: v for k, v in self._state.items()
                       if v[1] > now or now - v[2] <= STALE_SECONDS}
        # over the cap: unlocked entries go first (oldest first); a live lock goes only if nothing else is left
        order = sorted(self._state, key=lambda k: (self._state[k][1] > now, self._state[k][2]))
        for k in order[:max(0, len(self._state) - MAX_TRACKED)]:
            del self._state[k]

    def ok(self, key: str) -> None:
        with self._lock:
            self._state.pop(key, None)
