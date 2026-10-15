"""Market briefs kept in the plane at market/briefs.json: `added` (by hand, with the name) and `fetched` (public briefs cached for a day)."""
import logging
from datetime import datetime, timedelta, timezone

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
CACHE = timedelta(days=1)


def _path(plane):
    return plane.path("market", "briefs.json")


def read(plane) -> dict:
    try:
        data = read_json_strict(_path(plane), dict)
    except (OSError, ValueError):
        log.warning("market/briefs.json could not be read")
        data = None
    return data or {}


def add(plane, brief: dict) -> dict:
    p = _path(plane)
    p.parent.mkdir(parents=True, exist_ok=True)
    with lock_for(p):
        data = read(plane)
        data["added"] = [*data.get("added", []), brief]
        write_json_atomic(p, data)
    return brief


def cached_fetch(plane, now: datetime) -> dict | None:
    """The fetched block when it is under a day old, else None."""
    f = read(plane).get("fetched")
    try:
        if isinstance(f, dict) and now - datetime.fromisoformat(f["at"]) < CACHE:
            return f
    except (KeyError, ValueError, TypeError):
        pass
    return None


def save_fetch(plane, briefs: list[dict], now: datetime) -> dict:
    p = _path(plane)
    p.parent.mkdir(parents=True, exist_ok=True)
    with lock_for(p):
        data = read(plane)
        data["fetched"] = {"at": now.astimezone(timezone.utc).isoformat(), "briefs": briefs}
        write_json_atomic(p, data)
    return data["fetched"]


def add_news(plane, items: list[dict], keep: int = 50) -> int:
    """Outside headlines from a live API (C5 api): new ids only, the newest `keep` of them kept. Returns how many were new."""
    p = _path(plane)
    p.parent.mkdir(parents=True, exist_ok=True)
    with lock_for(p):
        data = read(plane)
        added = data.get("added", [])
        have = {b.get("id") for b in added}
        new = [b for b in items if b["id"] not in have]
        live = [b for b in [*added, *new] if b.get("live_api")]
        drop = {b["id"] for b in live[:-keep]} if keep else set()
        data["added"] = [b for b in [*added, *new] if b.get("id") not in drop]
        write_json_atomic(p, data)
    return len(new)
