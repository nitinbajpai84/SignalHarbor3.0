"""C2 Offer card: the industry pack's feed list (feeds.yaml) matched against the intent of work's sources.

An offer names a feed by kind only (never a vendor), the measures it would unlock (the pack's `required_for` ids, named from
kpi_tree.yaml through the market module's reader) and the fields it must contain. "We have it" adds the feed to the SOW as a
source plus one unclear line, sends the SOW back to draft at version + 1, and posts to the agent room (import guarded)."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from sh_platform.consume.market import _measures
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
_IID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
_FEED = re.compile(r"^[a-z0-9_]{1,80}$")


class Refusal(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _words(text) -> set[str]:
    return {w.rstrip("s") for w in re.findall(r"[a-z0-9]+", str(text or "").lower().replace("_", " ")) if len(w) > 1}


def kind_of(feed_id: str) -> str:
    """'fx_rates' -> 'FX rates', 'cash_balances' -> 'Cash balances': the feed's kind in plain words."""
    s = " ".join(w.upper() if len(w) <= 2 else w for w in feed_id.split("_"))
    return s[:1].upper() + s[1:]


def _has(feed_id: str, required: list[str], sources: list[dict]) -> bool:
    """A source covers the feed when its id, name or holds line names the feed, or its fields carry every required field."""
    want = _words(feed_id)
    for s in sources:
        if not isinstance(s, dict):
            continue
        if want <= _words(" ".join(str(s.get(k) or "") for k in ("id", "name", "holds"))):
            return True
        got = {str(f.get("name") or "").lower() for f in s.get("fields") or [] if isinstance(f, dict)}
        if required and set(required) <= got:
            return True
    return False


def _pack_feeds(pack) -> dict:
    if pack is None or pack.empty:
        return {}
    try:
        return (pack.section("feeds") or {}).get("feeds") or {}
    except KeyError:
        return {}


def _sow_path(plane, iid: str):
    if not isinstance(iid, str) or not _IID.match(iid):
        raise Refusal(404, "That intent of work was not found.")
    return plane.path("intents", iid, "sow.json")


def pick_intent(plane, iid: str | None) -> str | None:
    """The asked intent, else the one whose intent of work changed last; None when there is none."""
    if iid:
        if not _sow_path(plane, iid).is_file():
            raise Refusal(404, "That intent of work was not found.")
        return iid
    root = plane.path("intents")
    sows = [p for p in root.glob("*/sow.json") if _IID.match(p.parent.name)] if root.is_dir() else []
    return max(sows, key=lambda p: p.stat().st_mtime).parent.name if sows else None


def offers(plane, pack, iid: str | None) -> dict:
    iid = pick_intent(plane, iid)
    if iid is None:
        return {"intent_id": None, "offers": [], "line": "No intent of work yet, so there is nothing to compare a feed with."}
    sow = read_json_strict(_sow_path(plane, iid), dict) or {}
    feeds = _pack_feeds(pack)
    if not feeds:
        return {"intent_id": iid, "offers": [], "line": "No feed list comes with your industry yet."}
    names = {k["id"]: k.get("name") or k["id"] for k in _measures(pack)}
    in_sow = {str(k.get("code") or "").upper() for k in sow.get("kpis") or [] if isinstance(k, dict)}
    sources = sow.get("sources") or []
    out = []
    for fid, feed in feeds.items():
        fields = [f for f in (feed or {}).get("fields") or [] if isinstance(f, dict) and f.get("required_for")]
        codes = sorted({str(c) for f in fields for c in f["required_for"]})
        if not codes or _has(fid, [str(f["id"]).lower() for f in fields], sources):
            continue
        kind = kind_of(fid)
        out.append({
            "id": fid, "kind": kind, "title": f"{kind} feed: with it you would also get",
            "unlocks": [{"code": c, "name": names.get(c, c), "in_sow": c.upper() in in_sow} for c in codes],
            "must_contain": [{"name": f["id"], "label": f.get("label") or f["id"], "type": f.get("type") or ""} for f in fields],
        })
    out.sort(key=lambda o: (-sum(u["in_sow"] for u in o["unlocks"]), -len(o["unlocks"]), o["id"]))
    return {"intent_id": iid, "offers": out, "line": None if out else "Your sources already cover every feed your industry's measures need."}


def have(plane, pack, iid: str | None, feed_id: str, by: str) -> dict:
    """Add the feed as a source and one unclear line; the SOW goes back to draft at version + 1. Returns the new SOW."""
    if not _FEED.match(feed_id or ""):
        raise Refusal(404, "That offer was not found.")
    iid = pick_intent(plane, iid)
    if iid is None:
        raise Refusal(409, "There is no intent of work to add this feed to yet.")
    feed = _pack_feeds(pack).get(feed_id)
    if not isinstance(feed, dict):
        raise Refusal(404, "That offer was not found.")
    fields = [f for f in feed.get("fields") or [] if isinstance(f, dict) and f.get("required_for")]
    kind = kind_of(feed_id)
    path = _sow_path(plane, iid)
    with lock_for(path):
        sow = read_json_strict(path, dict)
        if sow is None:
            raise Refusal(404, "That intent of work was not found.")
        sources = sow.setdefault("sources", [])
        if _has(feed_id, [str(f["id"]).lower() for f in fields], sources):
            raise Refusal(409, f"The intent of work already has the {kind} source.")
        sid = f"src_{feed_id}"
        sources.append({
            "id": sid, "name": f"{kind} feed", "kind": "system",
            "holds": "Must contain: " + ", ".join(str(f.get("label") or f["id"]) for f in fields),
            "sample_path": None, "owner": None,
            "fields": [{"name": f["id"], "type": f.get("type") or "", "example": None, "meaning": f.get("label") or f["id"]} for f in fields],
        })
        sow.setdefault("unclear", []).append({
            "id": f"u_{feed_id}", "question": f"Who sends the {kind} feed, from which system, and from which month?",
            "about": sid, "who_can_settle": "Decision maker", "settled": False, "answer": None,
        })
        sow["state"], sow["signature"] = "draft", None
        sow["version"] = int(sow.get("version") or 0) + 1
        write_json_atomic(path, sow)
        try:  # the company map follows every write that changes what it shows
            from sh_platform.v1.m1_map import touch; touch(plane)
        except ImportError:
            pass
    _room(plane, iid, sow, kind, by)
    return {"intent_id": iid, "sow": sow}


def _room(plane, iid: str, sow: dict, kind: str, by: str) -> None:
    try:
        from sh_platform.v1.room import post
    except ImportError:
        return  # no room yet: the card still works
    try:
        post(plane, iid, "person", "note",
             f"{by or 'The decision maker'} says the company has the {kind} feed. It is in the intent of work as a source "
             f"with one unclear point; the statement is back to draft at version {sow['version']}.",
             to=["north"], refs=[{"kind": "sow", "id": str(sow.get("id") or iid)}], name=by or None)
    except Exception:  # the room must never break the offer
        log.exception("room post failed for %s at %s", iid, datetime.now(timezone.utc).isoformat())
