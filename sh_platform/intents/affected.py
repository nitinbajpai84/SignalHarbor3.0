"""IC v2 (47): the affected person and the observer. The content switch, "I feel this", the note to the organiser, join requests, follow,
and the Pulse watch lines A1 to A5.

Records: the switch is `affected_may_read` on intent.json (written at creation by the start screens; each change goes to `history`).
Taps, notes and requests sit in the sibling file `intents/<id>/affected.json` (open question 12: the intent record keeps its strict key set).
Who may do what is decided by access.py (file 14); an observer holds no role in FEEL or NOTE, so the server refuses their writes.
A tap or note left unsigned carries a random `anon-` key and no account anywhere (spec 47 rule 6). Counts only ever leave for the roles that
may see them; names leave only for a signed item and only to the organiser and the sponsor.
"""
import hashlib
import json
import re
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from sh_platform.intents import _plane, _viewer, events, store
from sh_platform.intents.access import (FEEL, FOLLOW, NOTE, ORGANISER, IntentAccess, IntentRefused, IntentRoute, Me, NOT_FOUND, _entries,
                                        _is_me, _named, intent_roles, load_intent, person_name, person_of, refusal, roles_of)
from sh_platform.intents.types import load_catalogue
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

router = APIRouter(route_class=IntentRoute)

NOTE_MAX, REASON_MAX = 500, 300  # open question 1: the proposed limits
ITEM = re.compile(r"[A-Za-z0-9_.:-]{1,80}")
OPEN_STATES = ("open", "in_session")
LIVE = ("open", "in_session", "closing")
FROZEN = ("closed", "cancelled")
ASKERS = frozenset({"affected", "area_member"})  # file 14 row 117: F, M. An observer follows only.


# ---- the sidecar -----------------------------------------------------------------------------------------------------------------

def _path(plane, intent_id: str):
    return plane.path("intents", intent_id, "affected.json")


SIDE_KEYS = {"feel_taps": list, "notes_to_organiser": list, "join_requests": list, "follow": dict, "seen": dict}


def _side(plane, intent_id: str) -> dict:
    side = read_json_strict(_path(plane, intent_id), dict) or {}
    for k, empty in SIDE_KEYS.items():
        side.setdefault(k, empty())
    side.setdefault("salt", secrets.token_hex(16))
    return side


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _live(intent: dict) -> None:
    """W2F2: a closed or cancelled intent takes no taps, notes or follows; it reads as closed."""
    if intent.get("state") in FROZEN:
        raise _fail(409, "intent_closed", "This intent has closed. You can read the outcome.")


def _fail(status: int, code: str, message: str) -> IntentRefused:
    return IntentRefused(status, code, message)


def _event(plane, intent_id: str, kind: str, me: Me | None, role: str, detail: dict, anonymous: bool = False) -> None:
    """One line in events.jsonl through the one writer. An unsigned tap or note names nobody. `detail` holds keys and enums only."""
    who = None if anonymous or not me else {"account": me.account_id, "name": me.name, "role": role}
    events.try_append(plane, intent_id, kind, who, None, detail, "act", anonymous=who is None)


def _edit(plane, intent_id: str, change) -> dict:
    """The one write to intent.json: read fresh, change, write (the store checks the version under its lock)."""
    rec = store.read_intent(plane, intent_id)
    return store.update_intent(plane, intent_id, rec["version"], change)


def _display(request: Request, account_id: str | None) -> str | None:
    return str((request.app.state.account_store.get(account_id) or {}).get("display_name") or "") or None if account_id else None


def may_open_content(intent: dict, roles: frozenset[str]) -> bool:
    """Spec 47 rules 2, 3, 11: organiser, sponsor, participant, observer and share-named read; an affected person only with the switch on.
    A cancelled intent shows an affected person no content whatever the switch said."""
    if "content" not in roles:
        return False
    return not (intent.get("state") == "cancelled" and not roles & {"organiser", "closer", "participant", "observer", "share_visitor", "creator"})


def _sponsor(intent: dict, me: Me) -> bool:
    return _named(intent, "sponsor", me)


# ---- the switch ------------------------------------------------------------------------------------------------------------------

class Switch(BaseModel):
    read_content: bool


@router.put("/api/intents/{intent_id}/affected-access")
def put_affected_access(body: Switch, request: Request, a: IntentAccess = Depends(intent_roles(ORGANISER))):
    me = Me.of(request, a.plane)
    was = bool(a.intent.get("affected_may_read"))
    if was != body.read_content:
        def change(rec):
            rec["affected_may_read"] = body.read_content
            rec.setdefault("history", []).append({"at": _now(), "by": me.name, "from": "affected read: " + ("on" if was else "off"),
                                                  "to": "affected read: " + ("on" if body.read_content else "off"), "note": "affected_access"})
        _edit(a.plane, a.intent["id"], change)
    return {"read_content": body.read_content}


# ---- I feel this -----------------------------------------------------------------------------------------------------------------

class Tap(BaseModel):
    item: str
    signed: bool = False


class Untap(BaseModel):
    item: str


def _once(side: dict, me: Me, intent_id: str, item: str) -> str:
    return hashlib.sha256(f"{side['salt']}:{me.account_id}:{intent_id}:{item}".encode()).hexdigest()


def _tap_counts(request: Request, side: dict, roles: frozenset[str], intent: dict, me: Me) -> list[dict]:
    """Per item: the count split by relation. Names only for signed taps and only to the organiser and the sponsor. An affected person
    gets no counts, only their own state."""
    boss = "organiser" in roles or _sponsor(intent, me)
    counts = boss or "participant" in roles or "company_admin" in roles
    out = {}
    for t in side["feel_taps"]:
        row = out.setdefault(t["item"], {"item": t["item"], "total": 0, "affected": 0, "participant": 0, "names": []})
        row["total"] += 1
        row[t["relation"]] += 1
        if boss and t["signed"] and t.get("by"):
            row["names"].append(_display(request, t["by"]) or "Someone")
    rows = list(out.values()) if counts else []
    for r in rows:
        r["names"] = sorted(r["names"]) if boss else []
    return rows


@router.post("/api/intents/{intent_id}/feel")
def post_feel(body: Tap, request: Request, a: IntentAccess = Depends(intent_roles(FEEL))):
    _live(a.intent)
    if not ITEM.fullmatch(body.item):
        raise _fail(422, "feel_item", "Choose a card to tap.")
    me, intent = Me.of(request, a.plane), a.intent
    if body.item == "intent" and intent.get("type") != "problem":
        raise _fail(422, "feel_item", "You can tap a card, or the problem itself.")
    if body.item != "intent" and not may_open_content(intent, a.roles):
        raise refusal(intent, a.roles, frozenset({"content"}), None, a.plane)
    if "organiser" in a.roles:
        raise _fail(403, "intent_read_only", "You raised or run this, so it counts already.")
    with lock_for(_path(a.plane, intent["id"])):
        side = _side(a.plane, intent["id"])
        once = _once(side, me, intent["id"], body.item)
        if any(t["once_key"] == once for t in side["feel_taps"]):
            raise _fail(409, "feel_twice", "You have already tapped this.")
        side["feel_taps"].append({"id": "tap-" + secrets.token_hex(6), "item": body.item, "signed": body.signed,
                                  "by": me.account_id if body.signed else None, "anon_key": None if body.signed else "anon-" + secrets.token_hex(8),
                                  "once_key": once, "relation": "participant" if "participant" in a.roles else "affected", "at": _now()})
        write_json_atomic(_path(a.plane, intent["id"]), side)
    _event(a.plane, intent["id"], "tap_added", me, "participant" if "participant" in a.roles else "affected",
           {"item": body.item, "signed": body.signed}, anonymous=not body.signed)
    return {"tapped": True, "taps": _tap_counts(request, side, a.roles, intent, me)}


@router.delete("/api/intents/{intent_id}/feel")
def delete_feel(body: Untap, request: Request, a: IntentAccess = Depends(intent_roles(FEEL))):
    me, intent = Me.of(request, a.plane), a.intent
    with lock_for(_path(a.plane, intent["id"])):
        side = _side(a.plane, intent["id"])
        once = _once(side, me, intent["id"], body.item)
        side["feel_taps"] = [t for t in side["feel_taps"] if t["once_key"] != once]  # a count of removals is not kept
        write_json_atomic(_path(a.plane, intent["id"]), side)
    return {"tapped": False, "taps": _tap_counts(request, side, a.roles, intent, me)}


# ---- the note to the organiser ---------------------------------------------------------------------------------------------------

class NoteIn(BaseModel):
    text: str
    signed: bool = False


class Text(BaseModel):
    text: str


@router.post("/api/intents/{intent_id}/notes")
def post_note(body: NoteIn, request: Request, a: IntentAccess = Depends(intent_roles(NOTE))):
    _live(a.intent)
    text, me = body.text.strip(), Me.of(request, a.plane)
    if not text or len(text) > NOTE_MAX:
        raise _fail(422, "note_text", "Write a note of up to 500 characters." if not text else "That note is too long. Keep it to 500 characters.")
    with lock_for(_path(a.plane, a.intent["id"])):
        side = _side(a.plane, a.intent["id"])
        side["notes_to_organiser"].append({"id": "note-" + secrets.token_hex(6), "text": text, "signed": body.signed,
                                           "from": me.account_id if body.signed else None,
                                           "anon_key": None if body.signed else "anon-" + secrets.token_hex(8),
                                           "at": _now(), "seen_at": None, "reply": None})
        write_json_atomic(_path(a.plane, a.intent["id"]), side)
    _event(a.plane, a.intent["id"], "note_to_organiser", me, "affected", {"signed": body.signed}, anonymous=not body.signed)
    return {"sent": True}


def _note(side: dict, note_id: str) -> dict:
    n = next((n for n in side["notes_to_organiser"] if n["id"] == note_id), None)
    if n is None:
        raise _fail(404, "note_not_found", "We could not find that note.")
    return n


@router.post("/api/intents/{intent_id}/notes/{note_id}/seen")
def post_note_seen(note_id: str, a: IntentAccess = Depends(intent_roles(ORGANISER))):
    with lock_for(_path(a.plane, a.intent["id"])):
        side = _side(a.plane, a.intent["id"])
        _note(side, note_id)["seen_at"] = _note(side, note_id)["seen_at"] or _now()
        write_json_atomic(_path(a.plane, a.intent["id"]), side)
    return {"seen": True}


@router.post("/api/intents/{intent_id}/notes/{note_id}/reply")
def post_note_reply(note_id: str, body: Text, request: Request, a: IntentAccess = Depends(intent_roles(ORGANISER))):
    text, me = body.text.strip(), Me.of(request, a.plane)
    if not text or len(text) > NOTE_MAX:
        raise _fail(422, "note_text", "Write a reply of up to 500 characters.")
    with lock_for(_path(a.plane, a.intent["id"])):
        side = _side(a.plane, a.intent["id"])
        n = _note(side, note_id)
        if not n["signed"]:
            raise _fail(422, "note_unsigned", "This note has no name on it, so it cannot be answered.")
        n["reply"] = {"by": me.account_id, "at": _now(), "text": text, "seen_at": None}
        n["seen_at"] = n["seen_at"] or _now()
        write_json_atomic(_path(a.plane, a.intent["id"]), side)
    _event(a.plane, a.intent["id"], "note_answered", me, "organiser", {})
    return {"replied": True}


# ---- join requests ---------------------------------------------------------------------------------------------------------------

class Ask(BaseModel):
    asked_role: str = "participant"
    reason: str


class Answer(BaseModel):
    action: str  # accept | decline
    role: str | None = None
    reason: str | None = None


def _request(side: dict, request_id: str) -> dict:
    r = next((r for r in side["join_requests"] if r["id"] == request_id), None)
    if r is None:
        raise _fail(404, "request_not_found", "We could not find that request.")
    return r


@router.post("/api/intents/{intent_id}/join-requests")
def post_join_request(body: Ask, request: Request, a: IntentAccess = Depends(intent_roles(ASKERS))):
    me, intent, reason = Me.of(request, a.plane), a.intent, body.reason.strip()
    if a.roles & {"organiser", "participant"}:
        raise _fail(409, "already_in", "You are already taking part.")
    if intent.get("state") not in OPEN_STATES:
        raise _fail(409, "not_open", "This intent is not taking new people now.")
    if body.asked_role not in ("participant", "observer"):
        raise _fail(422, "asked_role", "Choose Take part or Read along.")
    if not reason or len(reason) > REASON_MAX:
        raise _fail(422, "reason", "Write one line of up to 300 characters on why you would like to join.")
    with lock_for(_path(a.plane, intent["id"])):
        side = _side(a.plane, intent["id"])
        mine = [r for r in side["join_requests"] if r["by"] == me.account_id]
        if any(r["state"] == "open" for r in mine):
            raise _fail(409, "request_open", "You have already asked. Waiting for the organiser.")
        if any(r["state"] == "declined" for r in mine):
            raise _fail(409, "request_declined", "Declined: " + next(r["decline_reason"] for r in mine if r["state"] == "declined"))
        side["join_requests"].append({"id": "req-" + secrets.token_hex(6), "by": me.account_id, "asked_role": body.asked_role, "reason": reason,
                                      "at": _now(), "state": "open", "answered_by": None, "answered_at": None, "role_given": None,
                                      "decline_reason": None, "seen_at": None})
        write_json_atomic(_path(a.plane, intent["id"]), side)
    _event(a.plane, intent["id"], "join_requested", me, "affected", {"asked_role": body.asked_role})
    return {"state": "open"}


def _move(rec: dict, who: Me, name: str, role: str) -> str:
    """Take the person out of affected and observers and put them in the new role. `via` stays as it was. Returns the earlier role."""
    p, was, kept = rec.setdefault("people", {}), "affected", None
    for k in ("affected", "observers", "participants"):
        left = []
        for e in _entries(p.get(k)):
            if _is_me(e, who):
                kept, was = e, "observer" if k == "observers" else was
            else:
                left.append(e)
        p[k] = left
    entry = dict(kept) if isinstance(kept, dict) else {"account_id": who.account_id, "name": name, "via": "area"}
    p.setdefault("participants" if role == "participant" else "observers", []).append(entry)
    return was


@router.post("/api/intents/{intent_id}/join-requests/{request_id}/answer")
def post_join_answer(request_id: str, body: Answer, request: Request, a: IntentAccess = Depends(intent_roles(ORGANISER))):
    me, intent = Me.of(request, a.plane), a.intent
    if intent.get("state") not in OPEN_STATES:
        raise _fail(409, "not_open", "The intent is closing. Requests can no longer be answered.")
    reason = (body.reason or "").strip()
    if body.action not in ("accept", "decline"):
        raise _fail(422, "action", "Accept or decline.")
    if body.action == "decline" and (not reason or len(reason) > REASON_MAX):
        raise _fail(422, "reason", "Say why in a short line, up to 300 characters.")
    with lock_for(_path(a.plane, intent["id"])):
        side = _side(a.plane, intent["id"])
        r = _request(side, request_id)
        if r["state"] != "open":
            raise _fail(409, "request_answered", "This request has already been answered.")
        role = body.role or r["asked_role"]
        if body.action == "accept":
            if role not in ("participant", "observer"):
                raise _fail(422, "role", "Choose Participant or Observer.")
            name = _display(request, r["by"]) or "Someone"
            asker = Me(r["by"], name, frozenset())

            def change(rec):
                was = _move(rec, asker, name, role)
                rec.setdefault("history", []).append({"at": _now(), "by": me.name, "from": was, "to": role, "note": f"{name}: asked to join, accepted"})
            _edit(a.plane, intent["id"], change)
            r.update(state="accepted", role_given=role)
        else:
            r.update(state="declined", decline_reason=reason)
        r.update(answered_by=me.account_id, answered_at=_now())
        write_json_atomic(_path(a.plane, intent["id"]), side)
    _event(a.plane, intent["id"], "join_answered", me, "organiser", {"state": r["state"], "role_given": r["role_given"]})
    return {"state": r["state"]}


@router.post("/api/intents/{intent_id}/join-requests/{request_id}/withdraw")
def post_join_withdraw(request_id: str, request: Request, a: IntentAccess = Depends(intent_roles(ASKERS))):
    me = Me.of(request, a.plane)
    with lock_for(_path(a.plane, a.intent["id"])):
        side = _side(a.plane, a.intent["id"])
        r = _request(side, request_id)
        if r["by"] != me.account_id:
            raise _fail(404, "request_not_found", "We could not find that request.")
        if r["state"] != "open":
            raise _fail(409, "request_answered", "This request has already been answered.")
        r.update(state="withdrawn", answered_at=_now(), answered_by=me.account_id)
        write_json_atomic(_path(a.plane, a.intent["id"]), side)
    return {"state": "withdrawn"}


def close_sweep(plane, intent_id: str) -> None:
    """When the intent has closed or been cancelled, a request still open is withdrawn with "Intent closed" (journey step 13)."""
    with lock_for(_path(plane, intent_id)):
        side = _side(plane, intent_id)
        open_ = [r for r in side["join_requests"] if r["state"] == "open"]
        for r in open_:
            r.update(state="withdrawn", answered_at=_now(), decline_reason="Intent closed")
        if open_:
            write_json_atomic(_path(plane, intent_id), side)


# ---- follow ----------------------------------------------------------------------------------------------------------------------

class Follow(BaseModel):
    follow: bool


@router.post("/api/intents/{intent_id}/follow")
def post_follow(body: Follow, request: Request, a: IntentAccess = Depends(intent_roles(FOLLOW))):
    _live(a.intent)
    me = Me.of(request, a.plane)
    with lock_for(_path(a.plane, a.intent["id"])):
        side = _side(a.plane, a.intent["id"])
        side["follow"][me.account_id] = body.follow
        write_json_atomic(_path(a.plane, a.intent["id"]), side)
    return {"follow": body.follow}


# ---- reading: my part, and the organiser's panel ---------------------------------------------------------------------------------

def _label(intent: dict) -> str:
    return {"initiative": "wall", "brainstorm": "wall", "pulse": "answers", "problem": "notes", "decision": "views"}.get(intent.get("type"), "wall")


def _mine(request: Request, side: dict, intent: dict, roles: frozenset[str], me: Me) -> dict:
    req = next((r for r in reversed(side["join_requests"]) if r["by"] == me.account_id), None)
    once = {t["item"] for t in side["feel_taps"] if t["once_key"] == _once(side, me, intent["id"], t["item"])}
    notes = [n for n in side["notes_to_organiser"] if n["from"] and n["from"] == me.account_id]
    fuller = (roles & {"organiser", "participant", "closer", "creator", "named"} or _sponsor(intent, me)  # their part is elsewhere: no panel
              or any(_named(intent, s, me) for s in ("decider", "owner", "reporter", "advisers")))
    return {"role": None if fuller else "observer" if "observer" in roles else "affected" if "affected" in roles
            else "member" if "area_member" in roles else None,
            "follow": bool(side["follow"].get(me.account_id)), "tapped": sorted(once),
            "request": ({"id": req["id"], "state": req["state"], "asked_role": req["asked_role"], "at": req["at"], "role_given": req["role_given"],
                         "decline_reason": req["decline_reason"]} if req else None),
            "replies": [{"id": n["id"], "by": _display(request, n["reply"]["by"]), "text": n["reply"]["text"], "at": n["reply"]["at"]}
                        for n in notes if n["reply"]],
            "notes_sent": len(notes)}


def _panel(request: Request, plane, side: dict, intent: dict, roles: frozenset[str], me: Me) -> dict:
    full = "organiser" in roles or _sponsor(intent, me)
    notes, reqs = side["notes_to_organiser"], side["join_requests"]
    by_state = {s: sum(1 for r in reqs if r["state"] == s) for s in ("open", "accepted", "declined", "withdrawn")}
    out = {"switch": {"read_content": bool(intent.get("affected_may_read")), "label": _label(intent), "can_set": "organiser" in roles
                      and intent.get("state") not in FROZEN},
           "counts": {"notes": len(notes), "notes_seen": sum(1 for n in notes if n["seen_at"]), "notes_replied": sum(1 for n in notes if n["reply"]),
                      "requests": by_state, "followers": sum(1 for v in side["follow"].values() if v)},
           "open_things": sum(1 for n in notes if not n["seen_at"]) + by_state["open"], "taps": _tap_counts(request, side, roles, intent, me)}
    if full:
        out["notes"] = [{"id": n["id"], "text": n["text"], "at": n["at"], "from": _display(request, n["from"]) if n["signed"] else None,
                         "seen_at": n["seen_at"], "reply": n["reply"] and {"text": n["reply"]["text"], "at": n["reply"]["at"]}} for n in notes]
        out["requests"] = [{"id": r["id"], "name": _display(request, r["by"]) or "Someone", "asked_role": r["asked_role"], "reason": r["reason"],
                            "at": r["at"], "state": r["state"], "decline_reason": r["decline_reason"],
                            "area": ", ".join(sorted(person_of(plane, r["by"])[1] & {a.lower() for a in intent.get("areas") or []}))}
                           for r in reqs]
        out["can_answer"] = "organiser" in roles and intent.get("state") in OPEN_STATES
    return out


def _note_opened(plane, intent: dict, side: dict, me: Me, roles: frozenset[str]) -> bool:
    """The first time an affected person or observer opens the intent, and later its outcome, is kept (it clears lines A1 and A2)."""
    if not roles & {"affected", "observer"} or roles & {"organiser", "participant"} or not me.account_id:
        return False
    key = "closed_seen_at" if intent.get("state") in FROZEN else "opened_at"
    seen = side["seen"].setdefault(me.account_id, {"opened_at": None, "closed_seen_at": None})
    if seen[key]:
        return False
    seen[key] = _now()
    return True


def _seen_dep(request: Request, intent_id: str) -> IntentAccess:
    """Everybody who knows the intent exists, and the sponsor of any type (access.py gives the sponsor a role only on an Initiative)."""
    plane = _plane(request)
    intent, me = load_intent(plane, intent_id), Me.of(request, plane)
    roles = roles_of(intent, me)
    if intent.get("state") != "draft" and _sponsor(intent, me):
        roles = roles | {"sponsor"}
    if not roles and "super_admin" not in me.roles:  # R1: an adviser or a person named in the intent's records (charter role, source owner)
        from sh_platform.intents import north
        tier = north.tier(plane, intent, _viewer(request))
        roles = frozenset({"named"} | ({"content"} if tier == "content" else set())) if tier else roles
    if not roles:
        raise IntentRefused(404, "intent_not_found", NOT_FOUND)
    return IntentAccess(intent, roles, plane)


@router.get("/api/intents/{intent_id}/notes")
def get_notes(request: Request, a: IntentAccess = Depends(_seen_dep)):
    """My part of this intent (everybody), and the panel "From affected people" for the organiser, sponsor and company admin."""
    me, intent = Me.of(request, a.plane), a.intent
    with lock_for(_path(a.plane, intent["id"])):
        side = _side(a.plane, intent["id"])
        dirty = _note_opened(a.plane, intent, side, me, a.roles)
        if intent.get("state") in FROZEN and any(r["state"] == "open" for r in side["join_requests"]):
            for r in side["join_requests"]:
                if r["state"] == "open":
                    r.update(state="withdrawn", answered_at=_now(), decline_reason="Intent closed")
            dirty = True
        for r in side["join_requests"]:  # the asker has now read the answer (clears line A5)
            if r["by"] == me.account_id and r["state"] != "open" and not r.get("seen_at"):
                r["seen_at"], dirty = _now(), True
        for n in side["notes_to_organiser"]:
            if n["reply"] and n["from"] == me.account_id and not n["reply"].get("seen_at"):
                n["reply"]["seen_at"], dirty = _now(), True
        if dirty:
            write_json_atomic(_path(a.plane, intent["id"]), side)
    out = {"mine": _mine(request, side, intent, a.roles, me), "may_read": may_open_content(intent, a.roles), "state": intent.get("state")}
    if a.roles & {"organiser", "company_admin", "participant"} or _sponsor(intent, me):
        out["panel"] = _panel(request, a.plane, side, intent, a.roles, me)
    return out


# ---- the Pulse lines A1 to A5 ----------------------------------------------------------------------------------------------------

def _pline(id: str, title: str, detail: str, href: str, action: str, record: str, at) -> dict:
    return {"id": id, "kind": "outcome", "title": title, "detail": detail, "href": href, "action": action, "minutes": 1, "due": None,
            "source": {"record": record, "at": str(at) if at else None}}


def _first(text: str, n: int = 140) -> str:
    t = " ".join(str(text or "").split())
    return t if len(t) <= n else t[:n].rstrip() + "..."


def watch_lines(plane, me: Me, display=lambda _id: None) -> list[dict]:
    """Lines A1 to A5 for one person, read from the records. Only at open and close, and on answers: nothing for stage changes, taps or reads.
    `display(account_id)` gives a name for A4. The Pulse page adds these beside its other lines (shared edit, see the report)."""
    from sh_platform.pulse.intent_lines import records  # one read of the records per Pulse request
    out, types, base = [], load_catalogue()["types"], plane.path("intents")
    for rec in records(plane):
        if (set(rec) - store.KEYS or not store.ID_RE.fullmatch(str(rec["id"])) or rec.get("state") not in store.STATES
                or rec.get("type") not in store.PREFIX or rec["state"] == "draft"):  # what store.read_intent refuses
            continue
        roles, iid, title = roles_of(rec, me), rec["id"], rec.get("title") or "An intent"
        side = _side(plane, iid) if (base / iid / "affected.json").is_file() else {k: empty() for k, empty in SIDE_KEYS.items()}
        seen = side["seen"].get(me.account_id) or {}
        watcher = bool(roles & {"affected", "observer"}) and not roles & {"organiser", "participant"}
        if watcher and rec["state"] in LIVE and not seen.get("opened_at"):
            kind = types.get(rec["type"], {}).get("title", "intent")
            areas = [a for a in rec.get("areas") or [] if a.lower() in me.areas] or rec.get("areas") or []
            org = person_name(rec, "organiser", plane) or "The organiser"
            out.append(_pline(f"affected-open:{iid}", title, f"{org} opened {'an' if kind[:1] in 'AEIOU' else 'a'} {kind} that touches "
                              f"{' and '.join(areas) or 'your area'}. Nothing is asked of you.", f"/centre/intent/{iid}", "Have a look", f"intents/{iid}",
                              rec.get("updated_at")))
        if watcher and rec["state"] in FROZEN and not seen.get("closed_seen_at"):
            c = rec.get("closure") or {}
            text = f"Cancelled: {c.get('cancel_reason') or 'no reason recorded'}" if rec["state"] == "cancelled" else _first(c.get("summary")) or "Not available yet"
            out.append(_pline(f"affected-close:{iid}", f"What came out of {title}", text, f"/centre/intent/{iid}#outcome", "Read what came out",
                              f"intents/{iid}", c.get("closed_at")))
        for r in side["join_requests"]:
            if r["by"] == me.account_id and r["state"] in ("accepted", "declined") and not r.get("seen_at"):
                who = person_name(rec, "organiser", plane) or "The organiser"
                said = f"accepted as {r['role_given']}" if r["state"] == "accepted" else f"declined: {r['decline_reason']}"
                out.append(_pline(f"affected-reply:{r['id']}", title, f"{who} answered your request to join {title}: {said}", f"/centre/intent/{iid}",
                                  "Open the intent", f"intents/{iid}", r["answered_at"]))
        for n in side["notes_to_organiser"]:
            if n["from"] == me.account_id and n["reply"] and not n["reply"].get("seen_at"):
                who = person_name(rec, "organiser", plane) or "The organiser"
                out.append(_pline(f"affected-note:{n['id']}", title, f"{who} answered your note", f"/centre/intent/{iid}", "Open the intent",
                                  f"intents/{iid}", n["reply"]["at"]))
        if "organiser" in roles and rec["state"] in LIVE:
            fresh = sum(1 for n in side["notes_to_organiser"] if not n["seen_at"])
            if fresh:  # a count, never a person
                out.append(_pline(f"affected-notes:{iid}", f"{fresh} {'thing' if fresh == 1 else 'things'} from affected people", title,
                                  f"/centre/intent/{iid}/people", "Read them", f"intents/{iid}", rec.get("updated_at")))
            for r in side["join_requests"]:
                if r["state"] == "open":
                    out.append(_pline(f"affected-ask:{r['id']}", f"{display(r['by']) or 'Someone'} asks to join {title}", _first(r["reason"], 140),
                                      f"/centre/intent/{iid}/people", "Answer", f"intents/{iid}", r["at"]))
    return out
