"""Search and the index file (spec 15): `intents/_index.json`, one row per intent, and the per-viewer list query.

Other modules call `upsert_index(plane, intent)` straight after every write of `intents/<id>/intent.json`.
`query_index(plane, viewer, params)` is the whole of GET /api/intents (records.py calls it). Sealed and anonymous text never
reaches a row: card text comes only through the body source (`set_body_source`), and sealed or anonymous cards are dropped there.
ponytail: whole-file rewrite on every write, count check on every query, one process lock; a table when 2000 intents prove it slow.
"""
import base64
import json
import logging
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import APIRouter

from sh_platform.intents import store as S
from sh_platform.jsonfile import read_json_strict
from sh_platform.plane import CompanyPlane
from sh_platform.profile.view import Viewer

router = APIRouter()
log = logging.getLogger("sh.intents.search")

BODY_CAP = 4000
MIN_WORD = 2
PAGE, PAGE_MAX = 20, 50
ROLE_SLOTS = {"organiser": "organiser", "sponsor": "sponsor", "participants": "participant", "affected": "affected", "observers": "observer",
              "decider": "decider", "owner": "owner", "reporter": "reporter", "share_named": "named"}
OPEN_STATES = ("draft", "open", "in_session", "closing")
PAST_STATES = ("closed", "cancelled")
BodySource = Callable[[CompanyPlane, str], list[dict]]
_BODY: list[BodySource] = []


def set_body_source(fn: BodySource | None) -> None:
    """Register how card text is read: fn(plane, intent_id) -> [{text, sealed, anonymous}] newest first. None clears it."""
    _BODY[:] = [fn] if fn else []


# ---- who is who: the tiers and the index are the intent store's (store.tier_of, store.read_index); nothing is kept twice

def ref_name(ref: Any) -> str:
    return str((ref or {}).get("name") or "") if isinstance(ref, dict) else str(ref or "")


def tier_for(rec: dict, viewer: Viewer, areas: frozenset[str] = frozenset()) -> dict | None:
    """None when the viewer may not see this intent at all, else {tier: 0 existence only, 1 outcome, 2 area, 3 content; share_only}.
    Works on a record or an index row. `areas` is store.areas_of(plane, viewer) (computed once per request)."""
    from sh_platform.intents import event_text  # registers the What happened text resolvers once (events imports this file, so not at the top)
    event_text.register()
    t = S.tier_of(rec, viewer, areas)
    if t is None:
        return {"tier": 0, "share_only": False} if "super_admin" in viewer.roles and rec.get("state") != "draft" else None
    if t != "content":
        return {"tier": 2 if t == "card" else 1, "share_only": False}
    p = rec.get("people") or {}
    only = S.tier_of({**rec, "people": {**p, "share_named": []}}, viewer, areas) != "content"  # content only through a share link
    return {"tier": 3, "share_only": only}


def roles_held(row: dict, viewer: Viewer) -> set[str]:
    """The role chips this viewer holds in an index row."""
    p = row.get("people") or {}
    held = {role for slot, role in ROLE_SLOTS.items() if slot != "share_named" and any(S._named(x, viewer) for x in S_refs(p, slot))}
    if viewer.account_id and viewer.account_id in (p.get("share_named") or []):
        held.add("named")
    return held


def S_refs(people: dict, slot: str) -> list:
    v = people.get(slot)
    return v if isinstance(v, list) else ([v] if v else [])


# ---- time

def _ts(s: Any) -> float:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _day(s: Any) -> date | None:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def working_days(a: date, b: date) -> int:
    """Mon to Fri days after `a` up to and including `b` (negative when b is before a)."""
    if b < a:
        return -working_days(b, a)
    return sum(1 for i in range(1, (b - a).days + 1) if (a + timedelta(days=i)).weekday() < 5)


def timebox_status(row: dict, today: date) -> str:
    st, ends = row["state"], _day(row.get("ends"))
    if st == "draft":
        return "not_started"
    if st in PAST_STATES:
        closed = _day(row.get("closed_at") or row.get("cancelled_at"))
        return "closed_late" if st == "closed" and ends and closed and closed > ends else ("closed_in_time" if st == "closed" else "cancelled")
    if row["type"] == "pulse" or not ends:
        return "none"
    return "past_end" if today > ends else ("extended" if row.get("extended") else "running")


# ---- the index: one file, written by the store on every intent write

def upsert_index(plane: CompanyPlane, intent: dict) -> None:
    """The agreed call after any write of intents/<id>/intent.json. The store's own write path already does this; other writers call it.
    Never raises: a failure is logged and the next read rebuilds."""
    try:
        S.append_index(plane, intent)
    except (OSError, ValueError, KeyError):
        log.error("the list could not be updated for intent %s; it will be rebuilt on the next read", intent.get("id"))


def _body(plane: CompanyPlane, intent_id: str) -> str:
    """Card text of one intent that is neither sealed nor anonymous, newest first, capped. Read at search time, never stored, so a
    sealed or anonymous card cannot be found even after a seal is lifted and re-sealed. Empty with no source."""
    if not _BODY:
        return ""
    out, size = [], 0
    for c in _BODY[0](plane, intent_id):
        text = str(c.get("text") or "").strip()
        if not text or c.get("sealed") or c.get("anonymous"):
            continue
        if size + len(text) > BODY_CAP:
            break
        out.append(text)
        size += len(text) + 1
    return chr(10).join(out)


# ---- matching

def fold(text: Any) -> str:
    s = unicodedata.normalize("NFKD", str(text).lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip()


def _words(q: str) -> list[str]:
    return [w for w in fold(q).split() if len(w) >= MIN_WORD]


def _has(text: Any, word: str) -> bool:
    return any(t.startswith(word) for t in fold(text).split())


def _fields(row: dict, tier: int, titles_private: bool, body: str) -> list[tuple[str, str]]:
    """(label, text) the viewer's tier may search, in the order a match line names them."""
    f = [] if tier == 0 and titles_private else [("title", row["title"])]
    f.append(("areas", " ".join(row["areas"])))
    if tier >= 1:
        f.append(("outcome", row["outcome_text"]))
    if tier >= 2:
        f += [("purpose", row["purpose"]), ("organiser", row["organiser"]["name"])]
    if tier >= 3:
        f.append(("card text", body))
    return f


def _match(row: dict, words: list[str], tier: int, titles_private: bool, body: str) -> dict | None:
    """None when a word is missing; else the first non-title field a word is found in, with a 60-character snippet."""
    fields = _fields(row, tier, titles_private, body)
    if not all(any(_has(t, w) for _, t in fields) for w in words):
        return None
    for label, text in fields:
        if label != "title" and any(_has(text, w) for w in words):
            low, first = str(text), min((i for w in words for i in [fold(text).find(w)] if i >= 0), default=0)
            start = max(0, min(first - 10, max(0, len(low) - 60)))
            return {"field": label, "snippet": low[start:start + 60].replace("\n", " ")}
    return {"field": "title", "snippet": ""}


# ---- the query

GROUPS = ("type", "state", "area", "role", "timebox", "outcome", "rated")


def _vals(params: dict, key: str) -> set[str]:
    return {v for v in str(params.get(key) or "").split(",") if v}


def _passes(row: dict, held: set[str], tb: str, f: dict) -> dict[str, bool]:
    return {"type": not f["type"] or row["type"] in f["type"], "state": not f["state"] or row["state"] in f["state"],
            "area": not f["area"] or bool(set(row["areas"]) & f["area"]), "role": not f["role"] or bool(held & f["role"]),
            "timebox": not f["timebox"] or tb in f["timebox"], "outcome": not f["outcome"] or bool(set(row["next_kinds"]) & f["outcome"]),
            "rated": not f["rated"] or ("rated" if row["rating_n"] >= 3 else "not_rated") in f["rated"]}


def _created(row: dict) -> str:
    """The index row carries no created_at yet (shared file needed: store._row); the time box start is the nearest date."""
    return str(row.get("created_at") or row.get("starts") or row.get("updated_at") or "")


def _sort_key(row: dict, sort: str, view: str) -> list:
    made = -_ts(_created(row))
    if sort == "ending":
        live = row["state"] in ("open", "in_session", "closing") and row["type"] != "pulse" and row.get("ends")
        return [0, _ts(row["ends"]), made, row["id"]] if live else [1, 0, made, row["id"]]
    if sort == "people":
        return [-row["people_count"], made, row["id"]]
    if sort == "rated":
        return [0 if row["rating_n"] >= 3 else 1, -(row["rating_avg"] or 0), -row["rating_n"], made, row["id"]]
    when = _ts(row.get("closed_at") or row.get("cancelled_at")) if view == "past" else 0
    return [-(when or _ts(_created(row))), row["id"]]


def _card(row: dict, tier: int, today: date, match: dict | None, titles_private: bool) -> dict:
    ends = _day(row.get("ends"))
    card = {
        "id": row["id"], "type": row["type"], "title": None if tier == 0 and titles_private else row["title"],
        "title_private": tier == 0 and titles_private, "state": row["state"], "stage_name": row["stage_name"] if tier >= 1 else None,
        "areas": row["areas"], "people_count": row["people_count"], "can_open": tier >= 3, "tier": tier,
        "purpose": row["purpose"] if tier >= 2 else None, "organiser": row["organiser"]["name"] if tier >= 2 else None,
        "timebox": {"status": timebox_status(row, today), "ends": row.get("ends"), "closed_at": row.get("closed_at"), "cancelled_at": row.get("cancelled_at"),
                    "days_left": working_days(today, ends) if ends and row["state"] in ("open", "in_session", "closing") else None, "extended": row["extended"]},
        "outcome_text": row["outcome_text"] if tier >= 1 and row["state"] == "closed" else None,
        "rating": {"n": row["rating_n"], "avg": row["rating_avg"]} if tier >= 2 and row["type"] != "pulse" else None,
        "match": match,
    }
    return card


def query_index(plane: CompanyPlane, viewer: Viewer, params: dict, *, titles_private: bool = False, today: date | None = None) -> dict:
    """GET /api/intents: only what the viewer may see; the same rows give the cards, the totals and every chip count."""
    today = today or datetime.now(timezone.utc).date()
    rows, areas = S.read_index(plane), S.areas_of(plane, viewer)
    view, sort = str(params.get("view") or ""), str(params.get("sort") or "newest")
    f = {g: _vals(params, g) for g in GROUPS}
    words = _words(str(params.get("q") or ""))
    try:
        limit = max(0, min(int(params.get("limit", PAGE)), PAGE_MAX))
    except (TypeError, ValueError):
        limit = PAGE
    seen, everything = [], 0
    for row in rows:
        t = tier_for(row, viewer, areas)
        named = False
        if t is None and "participant" in f["role"] and row["state"] != "draft":  # named on a source, process or charter: same as the record route
            rec = S.read_intent(plane, row["id"])
            named = bool(rec) and S.named_in_records(plane, rec, viewer, areas.ctx)
            t = {"tier": 3, "share_only": False} if named else None
        if t is None or (view == "home" and row["state"] in PAST_STATES) or (view == "past" and row["state"] not in PAST_STATES):
            continue
        everything += 1
        m = _match(row, words, t["tier"], titles_private, _body(plane, row["id"]) if t["tier"] >= 3 else "") if words else None
        if words and m is None:
            continue
        held = roles_held(row, viewer) | ({"participant"} if named else set())
        seen.append((row, t["tier"], m, held, timebox_status(row, today), _passes(row, held, timebox_status(row, today), f)))
    facets: dict[str, dict[str, int]] = {g: {} for g in GROUPS}
    for row, _t, _m, held, tb, ok in seen:
        for g in GROUPS:
            if all(ok[o] for o in GROUPS if o != g):
                vals = {"type": [row["type"]], "state": [row["state"]], "area": row["areas"], "role": sorted(held), "timebox": [tb],
                        "outcome": row["next_kinds"], "rated": ["rated" if row["rating_n"] >= 3 else "not_rated"]}[g]
                for v in set(vals):
                    facets[g][v] = facets[g].get(v, 0) + 1
    hit = sorted(((_sort_key(r[0], sort, view), r) for r in seen if all(r[5].values())), key=lambda x: x[0])
    total = len(hit)
    cursor = None
    if params.get("cursor"):
        try:
            cursor = json.loads(base64.urlsafe_b64decode(str(params["cursor"]).encode()))
        except (ValueError, TypeError):
            cursor = None
    if cursor is not None:
        hit = [h for h in hit if h[0] > cursor]
    page = hit[:limit]
    nxt = base64.urlsafe_b64encode(json.dumps(page[-1][0]).encode()).decode() if limit and len(hit) > limit else None
    return {"items": [_card(r[0], r[1], today, r[2], titles_private) for _k, r in page], "total": total,
            "total_visible": everything, "next_cursor": nxt, "facets": facets,
            "index": {"built_at": _built_at(plane), "rows": len(rows)}}


def _built_at(plane: CompanyPlane) -> str | None:
    try:
        return (read_json_strict(plane.path("intents", "_index.json"), dict) or {}).get("built_at")
    except (OSError, ValueError):
        return None
