"""The frozen wall (IC-2f): the cards on the wall at the moment the private rooms closed, stored once beside the board.

intents/m1_intent/wall/<session id>.json   {session_id, closed_at, lanes: [{lane, cards: [{id, text, quarters, author, sealed}]}]}

The stored form is neutral (full content, every card). It never holds an anonymous author: such a card says "Anonymous".
`served` filters it per viewer with the profile's own card rule (`read(plane, viewer)["cards"]`), so the frozen wall and the live
wall cannot disagree about who sees a sealed card. Counts include silhouettes. Written once: a second freeze changes nothing.
"""
from datetime import datetime, timezone

from modules.m1_intent.store.files import UNREADABLE, StoreError, lock_for, read_json, write_json
from modules.m1_intent.store.board import _hex
from sh_platform.plane import CompanyPlane
from sh_platform.profile import Viewer, read, store
from sh_platform.profile.cards import LANES
from sh_platform.profile.view import NOBODY, SILHOUETTE

ANONYMOUS = "Anonymous"
_Q = ("q1", "q2", "q3", "q4")


def _path(plane: CompanyPlane, sid: str):
    if not _hex(sid):
        raise StoreError(UNREADABLE)
    return plane.path("intents", "m1_intent", "wall", f"{sid}.json")


def _val(cell) -> object:
    return cell.get("value") if isinstance(cell, dict) and cell.get("mark") != "unknown" else None


def _neutral(card_id: str, c: dict) -> dict:
    anon = _val(c.get("anonymous")) is True
    author = c.get("author") if isinstance(c.get("author"), dict) else {}
    texts = [str(_val(c.get(q)) or "") for q in _Q]
    return {"id": card_id, "text": next((t for t in texts if t), ""),
            "quarters": {q: (c.get(q) or {}).get("mark", "unknown") if isinstance(c.get(q), dict) else "unknown" for q in _Q},
            "author": ANONYMOUS if anon else str(author.get("by") or _val(author) or ANONYMOUS), "sealed": _val(c.get("sealed")) is True}


def freeze(plane: CompanyPlane, sid: str, now: datetime | None = None) -> dict:
    """Stores the wall as it is now, unless this session's wall is already frozen. Returns the stored snapshot."""
    path = _path(plane, sid)
    with lock_for(plane.root / ".m1_wall"):
        have = read_json(path)
        if have is not None:
            return have
        cards = store.raw(plane).get("cards", {})
        lanes = [{"lane": lane, "cards": [_neutral(k, c) for k, c in sorted(cards.items()) if _val(c.get("lane")) == lane and _val(c.get("room")) == sid]} for lane in LANES]
        snap = {"session_id": sid, "closed_at": (now or datetime.now(timezone.utc)).isoformat(), "lanes": lanes}
        write_json(path, snap)
        return snap


def get(plane: CompanyPlane, sid: str) -> dict | None:
    return read_json(_path(plane, sid))


def served(plane: CompanyPlane, sid: str, viewer: Viewer = NOBODY) -> dict | None:
    """The frozen wall as this viewer sees it: {closed_at, lanes: [{lane, count, cards}]}; None before the wall is frozen.
    A sealed card the viewer may not see is a silhouette (id, lane, sealed, silhouette); the default viewer sees every sealed card so."""
    snap = get(plane, sid)
    if snap is None:
        return None
    live = read(plane, viewer)["cards"]

    def one(c: dict, lane: str) -> dict:
        seen = live.get(c["id"])
        if c["sealed"] and (seen is None or "silhouette" in seen):  # no longer on the live wall counts as not whole to this viewer
            return {"id": c["id"], "lane": lane, "sealed": True, "silhouette": SILHOUETTE}
        return c

    lanes = [{"lane": l["lane"], "count": len(l["cards"]), "cards": [one(c, l["lane"]) for c in l["cards"]]} for l in snap["lanes"]]
    return {"closed_at": snap["closed_at"], "lanes": lanes}
