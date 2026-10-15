"""Answers of the Consume reading room, kept for the next person to open the page.

The room reads many tables and works out the same figures for every visit; nothing in it changes until someone writes. An answer is kept for
one viewer and one question, and thrown away when (a) any write request has finished since, (b) the warehouse file was written since (the
scheduler and pipelines write without a request), or (c) it is a minute old (files outside the warehouse, such as the signed index map and the
outside headlines). A viewer never sees another viewer's answer: the key holds the viewer.
ponytail: one process, in memory. Several web processes would each keep their own; move to a shared store if that matters."""
from __future__ import annotations

import threading
import time
from pathlib import Path

TTL = 60.0
MAX = 200
_LOCK = threading.Lock()
_GEN = [0]
_KEPT: dict[tuple, tuple] = {}


def bump() -> None:
    """Something was written: every kept answer is out of date."""
    _GEN[0] += 1


def _stamp(path: Path) -> tuple:
    """Time and size: two commits inside one coarse clock tick still differ in size."""
    try:
        s = path.stat()
        return s.st_mtime_ns, s.st_size
    except OSError:
        return 0, 0


def _signature(db: Path) -> tuple:
    return _GEN[0], _stamp(db), _stamp(db.with_name(db.name + ".wal"))


def kept(db: Path, key: tuple, compute):
    """The answer for `key`, worked out by `compute()` when none is kept or the kept one is out of date."""
    sig = _signature(db)  # taken before computing: a write during the work leaves the answer already out of date
    with _LOCK:
        hit = _KEPT.get((str(db), *key))
    if hit and hit[0] == sig and time.monotonic() - hit[1] < TTL:
        return hit[2]
    out = compute()
    with _LOCK:
        if len(_KEPT) >= MAX:
            _KEPT.clear()
        _KEPT[(str(db), *key)] = (sig, time.monotonic(), out)
    return out


class BumpOnWrite:
    """ASGI middleware: when a request that may write (anything but GET, HEAD or OPTIONS) has finished, drop every kept answer."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] not in ("GET", "HEAD", "OPTIONS"):
            try:
                await self.app(scope, receive, send)
            finally:
                bump()
        else:
            await self.app(scope, receive, send)
