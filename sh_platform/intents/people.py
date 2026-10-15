"""IC v2 (06): people and roles in an intent. The list lives in `people_detail` of `intents/<id>/intent.json`; `people` is rebuilt from it
on every write so other cards keep reading the ruling 21 shape. Each change appends one event to `intents/<id>/events.jsonl`.
Agents never invite, remove or answer for anyone; North and Nira only draft.
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.intents import _plane, _viewer
from sh_platform.intents import events as ev
from sh_platform.intents import lifecycle as L
from sh_platform.intents import store as S
from sh_platform.jsonfile import read_json_strict, write_json_atomic
from sh_platform.profile import view as pview
from sh_platform.pulse import lines as pulse_lines
from sh_platform.pulse import templates

log = logging.getLogger(__name__)
router = APIRouter()

ROLES = ("organiser", "sponsor", "decider", "participant", "affected", "observer", "adviser", "reporter", "owner")
ALLOWED = {  # file 06 "Named slots per type"; the organiser is never picked, only handed over
    "initiative": ("sponsor", "participant", "affected", "observer"),
    "brainstorm": ("participant", "observer", "affected"),
    "pulse": ("participant", "observer", "affected"),
    "problem": ("reporter", "owner", "affected", "observer"),
    "decision": ("decider", "adviser", "affected", "observer"),
}
SINGLE = ("organiser", "sponsor", "decider", "owner", "reporter")  # one person each
LISTS = {"participant": "participants", "adviser": "advisers", "affected": "affected", "observer": "observers"}
REASON_ROLES = frozenset({"sponsor", "decider", "participant", "adviser", "owner"})  # a decline needs a reason
DEFAULT = {"decision": "adviser", "problem": "affected"}  # file 06, invite dialog: the role a pick gets when none is chosen
COOLDOWN = 3600  # seconds between two recorded reminders to one person
RANGE = {"brainstorm": (4, 8)}  # brief section 2; a guide, not a cap
STATUSES = ("invited", "joined", "contributed", "confirmed", "declined", "removed")
CLOSED = ("closed", "cancelled")
# The Brainstorm start flow (file 35) keeps its own word for a participant's answer on `people.participants`; the two are kept in step.
STATUS_OUT = {"invited": "Invited", "joined": "Accepted", "contributed": "Accepted", "confirmed": "Accepted", "declined": "Declined"}
ROLE_WORDS = {"sponsor": "You are asked to sponsor this.", "decider": "You are asked to make the decision.",
              "participant": "You are asked to take part.", "adviser": "You are asked to give your view on the decision.",
              "owner": "You are asked to own this problem and its fix.", "reporter": "You raised this."}
NOTES = {"affected": "You are told because this touches {areas}. You do not have to do anything.",
         "observer": "You can read along. You do not add cards."}
CLOSED_MSG = "This intent has closed."
NOT_FOUND = "We could not find that."
ONLY_ORGANISER = "Only the organiser can do that."
_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


class Refuse(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


# ---- the record -------------------------------------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read(plane, intent_id: str) -> dict:
    try:
        rec = S.read_intent(plane, intent_id)
    except S.Unreadable:
        raise Refuse(404, S.UNREADABLE) from None
    if rec is None:
        raise Refuse(404, NOT_FOUND)
    return rec


def _side(plane, intent_id: str):
    # the list itself is on the record (`people_detail`); this file keeps only the history strip, and the list of records written before the move
    return plane.path("intents", intent_id, "people.json")


def _detail(plane, intent_id: str) -> dict:
    try:
        doc = read_json_strict(_side(plane, intent_id), dict) or {}
    except (OSError, ValueError):
        raise Refuse(404, S.UNREADABLE) from None
    rec = S.read_intent(plane, intent_id)  # a damaged record is refused by _read where it matters; here the old file is the fallback
    return {"people_detail": (rec or {}).get("people_detail") or doc.get("people_detail") or [], "history": doc.get("history") or []}


def _note(det: dict, kind: str, by: str | None, person: dict | None, to: str | None = None, reason: str | None = None) -> None:
    """One history row (the strip). Events 16 carries only kinds it lists; the reason stays here, for the organiser."""
    det["history"].append({"at": _now(), "kind": kind, "by": by, "person": person and person["name"], "role": person and person["role"],
                           "to": to, "reason": reason or None})


def _adopt(rec: dict, det: dict) -> None:
    """People the record already names (the start screen wrote them into `people`) join the list as Invited; the organiser is Joined."""
    have, p, at = {e["person_id"] for e in det["people_detail"]}, rec.get("people") or {}, rec.get("created_at") or _now()
    for role, item in [(r, p.get(r)) for r in SINGLE] + [(r, x) for r, k in LISTS.items() for x in p.get(k) or []]:
        if isinstance(item, dict) and item.get("account_id") and item["account_id"] not in have:
            e = _entry_new(item["account_id"], item["name"], role, "picked", (p.get("organiser") or {}).get("account_id"), at)
            if role == "organiser":
                e.update(status="joined", joined_at=at, invited_by=None, required=True)
            det["people_detail"].append(e)
            have.add(item["account_id"])
    for x in p.get("participants") or []:  # an answer given on the record itself (the brainstorm's own invitation) reaches the list
        e = _entry(det, x.get("account_id")) if isinstance(x, dict) else None
        if not e or e["role"] != "participant" or e["status"] != "invited" or x.get("status") not in ("Accepted", "Declined"):
            continue
        when = x.get("answered_at") or at
        if x["status"] == "Accepted":
            e.update(status="joined", joined_at=when)
        else:
            e.update(status="declined", declined={"at": when, "reason": x.get("reason") or None})
        _note(det, e["status"], e["person_id"], e, reason=x.get("reason"))
    _tidy_problem(rec, det)


def _tidy_problem(rec: dict, det: dict) -> None:
    """Spec 53: a person who passes a Problem leaves the people list (the pass stays in `passes`, the audit trail). After two passes the
    company admin is asked to name an owner; that is a card on Pulse, not an invitation, so the admin's grant is not listed either."""
    if rec.get("type") != "problem":
        return
    passers = {x.get("from_id") for x in rec.get("passes") or []}
    owner = (rec["people"].get("owner") or {}).get("account_id")
    drop = lambda e: e["status"] == "invited" and e["role"] == "participant" and (e["person_id"] in passers or len(passers) >= 2) and e["person_id"] != owner  # noqa: E731
    det["people_detail"] = [e for e in det["people_detail"] if not drop(e)]


def _sync(rec: dict, det: dict) -> None:
    """Rebuild `people` (person objects, as the store keeps them) from the list. Declined and removed people are not in it.
    A name with no account, put there by the start screen, is kept as it was."""
    live = [e for e in det["people_detail"] if e["status"] != "removed" and (e["status"] != "declined" or e["role"] == "participant")]
    old = rec.get("people") or {}
    was = {x["account_id"]: x for x in old.get("participants") or [] if isinstance(x, dict) and x.get("account_id")}
    ids = {e["person_id"] for e in live}
    # a single slot (reporter, owner, decider...) stays when its person is still live under another role (T24): the list
    # keeps one role per person, so it alone cannot rebuild a slot held by someone who is also a participant
    keep = lambda p: isinstance(p, dict) and (not p.get("account_id") or p["account_id"] in ids)  # noqa: E731
    people = {k: old.get(k) if keep(old.get(k)) else None for k in SINGLE} | {v: [x for x in old.get(v) or [] if isinstance(x, dict) and not x.get("account_id")] for v in LISTS.values()}
    people["organiser"] = old.get("organiser")
    for e in live:
        who = {"account_id": e["person_id"], "name": e["name"]}
        if e["role"] == "participant":  # a declined participant stays listed, as the brainstorm lists them
            who = {**was.get(e["person_id"], {}), **who, "status": STATUS_OUT[e["status"]], "reason": (e.get("declined") or {}).get("reason")}
        if e["role"] in SINGLE:
            people[e["role"]] = who
        else:
            people[LISTS[e["role"]]].append(who)
    rec["people"] = people


def _mutate(plane, intent_id: str, fn: Callable[[dict, dict], object]):
    """Read the record and the list under one lock, let `fn(rec, det)` change them, write both. A refusal writes nothing."""
    with S.locked(plane):
        rec = _read(plane, intent_id)
        det = _detail(plane, intent_id)
        mark = lambda: json.dumps([rec.get("people"), rec.get("history"), det["people_detail"]], sort_keys=True)  # noqa: E731
        before = mark()
        _adopt(rec, det)
        out = fn(rec, det)
        _sync(rec, det)
        write_json_atomic(_side(plane, intent_id), {"history": det["history"]})
        if before != mark() or "people_detail" not in rec:
            def change(r: dict) -> None:
                r["people"], r["history"], r["people_detail"] = rec["people"], rec.get("history") or [], det["people_detail"]
            S.update_intent(plane, intent_id, rec["version"], change)
        return out


# ---- who is looking ---------------------------------------------------------------------------------------------------
def _accounts(request: Request) -> dict[str, dict]:
    st = request.app.state
    return {a["account_id"]: a for a in st.account_store.in_company(request.state.company_id) if not a.get("disabled")}


def _company_people(request: Request, plane) -> list[dict]:
    """The pick list: the company's accounts, with the role the profile holds for the person and the areas they are tagged to."""
    from sh_platform.profile import areas as areas_store
    from sh_platform.profile import store as pstore
    from sh_platform.profile import view
    shown = set(view.read(plane, _viewer(request)).get("people", {}))  # people in a restricted area drop out for this viewer
    doc = pstore.load(plane)
    names = {a["id"]: a["name"] for a in areas_store.listing(doc) if a["status"] == "active"}
    by_account = {view._v(p, "account_id"): p for k, p in doc["people"].items() if k in shown and view._v(p, "account_id")}
    out = []
    for aid, a in _accounts(request).items():
        p = by_account.get(aid) or {}
        ids = [i for i in areas_store.people_areas(p) if i in names] if p else []
        out.append({"person_id": aid, "name": a["display_name"], "role": view._v(p, "role") if p else None, "area_ids": ids,
                    "is_sponsor": view._v(p, "is_sponsor") is True if p else False,  # the roster's flag (profile/reader.py): the start screen's guess
                    "area": ", ".join(names[i] for i in ids) or (view._v(p, "team") if p else None)})
    return sorted(out, key=lambda x: x["name"].lower())


def _me(request: Request) -> dict:
    return {"account": request.state.account_id, "name": _viewer(request).name, "role": (request.state.roles or ["participant"])[0]}


def _entry(det: dict, person_id: str | None) -> dict | None:
    return next((p for p in det["people_detail"] if p["person_id"] == person_id), None) if person_id else None


def _level(plane, rec: dict, det: dict, request: Request) -> str:
    """organiser, member, affected (names and roles), admin or area (the organiser and counts only); anyone else gets 404."""
    me = request.state.account_id
    if rec["state"] == "draft":
        if me not in (rec.get("created_by"), (rec["people"].get("organiser") or {}).get("account_id")):
            raise Refuse(404, NOT_FOUND)
        return "organiser"
    if me and me == (rec["people"].get("organiser") or {}).get("account_id"):
        return "organiser"
    e = _entry(det, me)
    if e and e["status"] != "removed":
        return "affected" if e["role"] == "affected" else "member"
    viewer = _viewer(request)
    from sh_platform.profile import areas as areas_store
    from sh_platform.profile import store as pstore
    tagged = areas_store.areas_of_account(pstore.load(plane), me) & set(_area_ids(plane, rec))
    if S.tier_of(rec, viewer, S.areas_of(plane, viewer)) is None and not tagged:
        raise Refuse(404, NOT_FOUND)
    return "admin" if "company_admin" in (request.state.roles or []) else "area"


def _need_organiser(plane, rec: dict, det: dict, request: Request) -> None:
    if _level(plane, rec, det, request) != "organiser":
        raise Refuse(403, ONLY_ORGANISER)


def _need_live(rec: dict) -> None:
    if rec.get("state") in CLOSED:
        raise Refuse(409, CLOSED_MSG)


# ---- dates ------------------------------------------------------------------------------------------------------------
def _tz(plane):
    return L.company_zone(plane)


def _fmt(iso: str | None, tz) -> str | None:
    """'8 Oct' in the company zone, else UTC."""
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    d = (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(tz)
    return f"{d.day} {d.strftime('%b')}"


# ---- the view ---------------------------------------------------------------------------------------------------------
def _last(p: dict) -> str | None:
    marks = [p.get("invited_at"), p.get("joined_at"), p.get("first_contribution_at"), p.get("confirmed_at"),
             (p.get("declined") or {}).get("at"), (p.get("removed") or {}).get("at"), *[r.get("at") for r in p.get("reminders") or []]]
    return max((m for m in marks if m), default=None)


def _row(p: dict, level: str, names: dict, tz) -> dict:
    base = {"person_id": p["person_id"], "name": p["name"], "role": p["role"]}
    if level in ("affected", "area"):
        return base
    base["status"] = p["status"]
    if level != "organiser":
        return base
    return base | {"via": p["via"], "invited_by": names.get(p.get("invited_by")), "invited_on": _fmt(p.get("invited_at"), tz),
                   "last_activity": _fmt(_last(p), tz), "required": p["required"], "joined_on": _fmt(p.get("joined_at"), tz),
                   "declined": p.get("declined") and {"on": _fmt(p["declined"]["at"], tz), "reason": p["declined"].get("reason")},
                   "removed": p.get("removed") and {"on": _fmt(p["removed"]["at"], tz), "reason": p["removed"].get("reason"),
                                                    "by": names.get(p["removed"].get("by"))},
                   "role_history": [{**h, "at": _fmt(h["at"], tz), "by": names.get(h["by"])} for h in p.get("role_history") or []],
                   "reminders": [_fmt(r["at"], tz) for r in p.get("reminders") or []], "seat": p.get("seat_ref")}


def _history(det: dict, level: str, names: dict, tz) -> list[dict]:
    """Every invitation, answer, role change, removal and reminder, in time order. The company admin sees that each happened, no reasons."""
    if level not in ("organiser", "admin"):
        return []
    return [{"at": _fmt(h["at"], tz), "kind": h["kind"], "by": names.get(h["by"]) or ("North" if h["kind"] == "reminded" else None),
             "person": h["person"], "role": h["role"], "to": h["to"], "reason": h["reason"] if level == "organiser" else None} for h in det["history"]]


def _waiting(det: dict, tz) -> dict:
    """North's 'waiting for' line from people_detail: invited and not answered, or a joined participant with no card yet."""
    ppl = [p for p in det["people_detail"] if p["required"] and (p["status"] == "invited" or (p["status"] == "joined" and p["role"] == "participant"))]
    last = max((r["at"] for p in det["people_detail"] for r in p.get("reminders") or []), default=None)
    return {"names": [p["name"].split()[0] for p in ppl], "ids": [p["person_id"] for p in ppl], "last_reminder": _fmt(last, tz)}


def _nameless(rec: dict, det: dict) -> int:
    """People the start screen named without an account: on the record's `people`, not in the list. Counted once each, by name."""
    have = {str(p["name"]).strip().lower() for p in det["people_detail"]}
    p, names = rec.get("people") or {}, set()
    for x in [*(p.get(r) for r in SINGLE), *(y for k in LISTS.values() for y in p.get(k) or [])]:
        if isinstance(x, dict) and not x.get("account_id") and x.get("name"):
            names.add(str(x["name"]).strip().lower())
    return len(names - have)


def _counts(det: dict, level: str, rec: dict | None = None) -> dict:
    ppl = det["people_detail"]
    c = {s: sum(1 for p in ppl if p["status"] == s) for s in STATUSES}
    live = [p for p in ppl if p["status"] != "removed"]
    extra = _nameless(rec, det) if rec else 0  # one headcount everywhere: panel, home card, wall card
    out = {"people": len(live) + extra, "joined": c["joined"], "contributed": c["contributed"], "confirmed": c["confirmed"], "invited": c["invited"],
           "named": sum(1 for p in live if p["role"] != "organiser") + extra,
           "affected": sum(1 for p in live if p["role"] == "affected"),
           "not_answered": sum(1 for p in ppl if p["status"] == "invited" and p["required"])}
    if level == "organiser":
        out |= {"declined": c["declined"], "removed": c["removed"]}
    return out


def _origin(request: Request) -> str:
    o = request.query_params.get("origin") or ""
    return o.rstrip("/") if re.fullmatch(r"https?://[A-Za-z0-9.:\[\]-]+/?", o) else ""


def _closes(rec: dict, tz) -> str | None:
    """When the thing people are asked to join closes: the open stage's due date (the wall's, for an Initiative), else the intent's end."""
    from sh_platform.intents import clock
    stage = next((x for x in rec.get("stages") or [] if x.get("opened_at") and not x.get("closed_at")), None)
    due = clock._due(rec, stage) if stage else None
    return _fmt(due.isoformat() if due else (rec.get("time_box") or {}).get("ends"), tz)


def _drafts(rec: dict, det: dict, tz, origin: str) -> dict:
    link = f"{origin}/centre/intent/{rec['id']}"
    org = (rec["people"].get("organiser") or {}).get("name") or "your organiser"
    what = rec.get("title") or rec.get("purpose")
    waiting = any(p["status"] == "invited" and p["role"] != "affected" for p in det["people_detail"])
    told = any(p["status"] == "invited" and p["role"] == "affected" for p in det["people_detail"])
    fyi = {"subject": f"Nothing is asked of you: {what}",
           "body": (f"Hello,\n\n{org} has started {what}, which touches your area. You do not have to do anything. "
                    f"You can read about it here: {link}" + templates.SIGN)}
    inv = templates.invite({"organiser": org, "purpose": what, "closes": _closes(rec, tz), "link": link})
    return {"invite": inv if waiting else None, "fyi": fyi if told else None}


def _acted(rec: dict, me: dict) -> bool:
    """The person has already done the type's own act (decided, signed, confirmed the closure): no "asked to" card is shown for it."""
    out, cl = rec.get("outcome") or {}, rec.get("closure") or {}
    return me["name"] in (out.get("decided_by"), out.get("signed_by")) or me["person_id"] in json.dumps(cl.get("confirmed") or []) or me["name"] in json.dumps(cl.get("confirmed") or [])


def _invitation(plane, rec: dict, me: dict | None, names: dict, tz) -> dict | None:
    if not me or me["status"] not in ("invited", "declined"):
        return None
    # the type's own action for this person comes first (T24): a Problem's proposed owner has the Problem's Accept; a sponsor or decider who has acted has nothing to accept
    if me["status"] == "invited" and ((rec["type"] == "problem" and me["role"] == "owner") or (me["role"] in ("sponsor", "decider") and _acted(rec, me))):
        return None
    areas = ", ".join(a["name"] for a in _area_names(plane, rec)) or "your area"
    ask = "You are asked to add ideas on the wall." if rec["type"] == "brainstorm" and me["role"] == "participant" else ROLE_WORDS.get(me["role"])
    cl = rec.get("closure") or {}
    return {"inviter": (names.get(me.get("invited_by")) or "your organiser").split()[0], "title": rec.get("title"),
            "purpose": rec.get("purpose") or None, "ask": ask, "note": (NOTES.get(me["role"]) or "").format(areas=areas) or None,
            "ends": _fmt((rec.get("time_box") or {}).get("ends"), tz), "minutes": pulse_lines.MINUTES["invite"],
            "reason_required": me["role"] in REASON_ROLES, "closed": rec["state"] in CLOSED,
            "closed_note": (cl.get("cancel_reason") if rec["state"] == "cancelled" else cl.get("summary")) or None}


def _area_ids(plane, rec: dict) -> list[str]:
    """The intent's areas as profile area ids. Records hold an id or the area's name (the start screen wrote names); both resolve."""
    from sh_platform.profile import areas as areas_store
    from sh_platform.profile import store as pstore
    key = {k.lower(): a["id"] for a in areas_store.listing(pstore.load(plane)) for k in (a["id"], a["name"])}
    return [key.get(str(v).lower(), v) for v in rec.get("areas") or []]


def _area_names(plane, rec: dict) -> list[dict]:
    from sh_platform.profile import areas as areas_store
    from sh_platform.profile import store as pstore
    names = {a["id"]: a["name"] for a in areas_store.listing(pstore.load(plane))}
    return [{"id": i, "name": names.get(i) or i} for i in _area_ids(plane, rec)]


def _view(request: Request, plane, rec: dict, det: dict) -> dict:
    level = _level(plane, rec, det, request)
    tz, names = _tz(plane), {a: v["display_name"] for a, v in _accounts(request).items()}
    mine = _entry(det, request.state.account_id)
    if level == "organiser":
        shown = det["people_detail"]
    elif level in ("area", "admin"):
        shown = [p for p in det["people_detail"] if p["role"] == "organiser"]
    else:
        shown = [p for p in det["people_detail"] if p["status"] not in ("declined", "removed")]
    kind = rec["type"]
    n = len([p for p in det["people_detail"] if p["status"] not in ("declined", "removed") and p["role"] != "organiser"])
    gone = [p["role"] for p in det["people_detail"] if p["status"] == "declined" and p["role"] in ("decider", "owner")
            and not any(q["role"] == p["role"] and q["status"] not in ("declined", "removed") for q in det["people_detail"])]
    return {"intent": {"id": rec["id"], "type": kind, "title": rec.get("title"), "state": rec["state"], "areas": _area_names(plane, rec),
                       "area_ids": _area_ids(plane, rec), "ends": _fmt((rec.get("time_box") or {}).get("ends"), tz)},
            "level": level, "me": mine and {"person_id": mine["person_id"], "role": mine["role"], "status": mine["status"]},
            "people": [_row(p, level, names, tz) for p in shown], "counts": None if level == "area" else _counts(det, level, rec),
            "roles_allowed": list(ALLOWED.get(kind, ())), "can_invite": level == "organiser" and rec["state"] in ("open", "in_session"),
            "can_ask": rec["state"] not in CLOSED and level == "member" and (mine or {}).get("role") == "sponsor",
            "range": RANGE.get(kind) and {"low": RANGE[kind][0], "high": RANGE[kind][1], "have": n},
            "waiting": _waiting(det, tz) if level == "organiser" else None,
            "gone": gone if level == "organiser" else [], "drafts": _drafts(rec, det, tz, _origin(request)) if level == "organiser" else None,
            "wall_session_id": next(iter((rec.get("refs") or {}).get("wall_session_ids") or []), None) if level == "organiser" else None,
            "history": _history(det, level, names, tz), "invitation": _invitation(plane, rec, mine, names, tz)}


# ---- changes ----------------------------------------------------------------------------------------------------------
def _entry_new(person_id: str, name: str, role: str, via: str, by: str | None, at: str) -> dict:
    return {"person_id": person_id, "name": name, "role": role, "status": "invited", "required": role not in ("affected", "observer"), "via": via,
            "invited_by": by, "invited_at": at, "joined_at": None, "first_contribution_at": None, "confirmed_at": None, "declined": None,
            "removed": None, "role_history": [], "reminders": [], "seat_ref": None}


def _vacate(rec: dict, det: dict, role: str, keep: dict, by: str, at: str) -> None:
    """A single slot held by someone else goes to that person as Participant (Observer where the type has no participants)."""
    old = next((q for q in det["people_detail"] if q["role"] == role and q is not keep and q["status"] not in ("declined", "removed")), None)
    if old:
        _set_role(rec, det, old, "participant" if "participant" in ALLOWED.get(rec["type"], ()) else "observer", by, f"Replaced as {role}", at)


def _set_role(rec: dict, det: dict, p: dict, role: str, by: str, reason: str | None, at: str) -> None:
    if role in SINGLE:
        _vacate(rec, det, role, p, by, at)
    p["role_history"].append({"from": p["role"], "to": role, "by": by, "at": at, "reason": reason or None})
    p["role"] = role
    p["required"] = role not in ("affected", "observer")
    if role == "organiser":
        rec["people"] = {**rec["people"], "organiser": {"account_id": p["person_id"], "name": p["name"]}}
    if role in ("observer", "affected") and p["status"] in ("contributed", "confirmed"):
        p["status"] = "joined"  # they read; their earlier cards stay


def _event(plane, intent_id: str, kind: str, who: dict, pid: str, **detail) -> None:
    ev.try_append(plane, intent_id, kind, who, {"store": "intent_people", "id": pid, "version": None}, detail, "act")


def _invite(plane, request: Request, intent_id: str, body: dict) -> dict:
    accounts, me = _accounts(request), _me(request)
    picks = body.get("people") or []
    if not isinstance(picks, list):
        raise Refuse(422, "Pick people from the list.")
    sent: list = []

    def work(rec: dict, det: dict) -> dict:
        _need_organiser(plane, rec, det, request)
        _need_live(rec)
        if rec["state"] == "draft":
            raise Refuse(409, "Open the intent first. Your picks are sent when it opens.")
        if rec["state"] == "closing":
            raise Refuse(409, "This intent is closing. No one can be added now.")
        kind, at, who = rec["type"], _now(), request.state.account_id
        allowed, done = ALLOWED.get(kind, ()), []
        wanted = [(x.get("person_id"), x.get("role") or DEFAULT.get(kind, allowed[0]), "picked") for x in picks if isinstance(x, dict)]
        wanted += [(body.get(s), s, "picked") for s in ("decider", "owner") if body.get(s) and s in allowed]
        areas = body.get("areas") or []
        if [a for a in areas if a not in _area_ids(plane, rec)]:
            raise Refuse(422, "Choose areas from the first screen.")
        if areas:
            wanted += [(x["person_id"], "affected", "area") for x in _company_people(request, plane) if set(areas) & set(x["area_ids"])]
        if not wanted:
            raise Refuse(422, "Pick at least one person.")
        for pid, role, via in wanted:
            if pid not in accounts or pid == who:
                continue
            if role not in allowed:
                raise Refuse(422, f"That role is not used in a {kind} intent.")
            p = _entry(det, pid)
            if p and p["status"] not in ("declined", "removed"):
                continue  # already in: told once
            if p:  # invite again: the earlier decline or removal stays in the history
                p.update(status="invited", invited_at=at, invited_by=who, declined=None, removed=None, joined_at=None, via=via)
                if p["role"] != role:
                    _set_role(rec, det, p, role, who, None, at)
            else:
                p = _entry_new(pid, accounts[pid]["display_name"], role, via, who, at)
                det["people_detail"].append(p)
                if role in SINGLE:
                    _vacate(rec, det, role, p, who, at)
            _note(det, "invited", who, p)
            sent.append(dict(p))
            done.append(pid)
        return {"invited": done}

    out = _mutate(plane, intent_id, work)
    for p in sent:
        _event(plane, intent_id, "person_invited", me, p["person_id"], role=p["role"], required=p["required"])
    seat_invited(plane, intent_id)
    return out


def _remind(plane, request: Request, intent_id: str, ids: list) -> list[dict]:
    def work(rec: dict, det: dict) -> list[dict]:
        _need_organiser(plane, rec, det, request)
        _need_live(rec)
        tz, out = _tz(plane), []
        org = (rec["people"].get("organiser") or {}).get("name")
        for pid in ids:
            p = _entry(det, pid)
            if not p or p["role"] == "affected" or p["status"] in ("declined", "removed"):
                continue
            last = (p["reminders"] or [{}])[-1].get("at")
            if not last or (datetime.now(timezone.utc) - datetime.fromisoformat(last.replace("Z", "+00:00"))).total_seconds() > COOLDOWN:
                p["reminders"].append({"at": _now(), "drafted_by": "north", "sent_note": None})  # a repeat press inside the cooldown shows the draft, writes nothing
                _note(det, "reminded", None, p)
                fresh = True
            else:
                fresh = False
            d = templates.reminder({"organiser": org, "purpose": rec.get("title"), "closes": _closes(rec, tz),
                                    "link": f"{_origin(request)}/centre/intent/{intent_id}"})
            out.append({"person_id": pid, "name": p["name"], "_new": fresh, **d})
        return out

    out = _mutate(plane, intent_id, work)
    for d in out:
        if d.pop("_new", False):
            _event(plane, intent_id, "person_reminded", _me(request), d["person_id"])
    return out


def _answer(plane, request: Request, intent_id: str, person_id: str, body: dict) -> str:
    me, joined, declined = _me(request), [], []

    def work(rec: dict, det: dict) -> str:
        viewer = _viewer(request)
        mine = _entry(det, request.state.account_id)
        if (not mine or mine["status"] == "removed") and S.tier_of(rec, viewer, S.areas_of(plane, viewer)) is None:
            raise Refuse(404, NOT_FOUND)  # hidden answers exactly like missing, before any state or role check (file 05)
        _need_live(rec)
        p = _entry(det, person_id)
        if not p or person_id != request.state.account_id:
            raise Refuse(403, "Only you can answer for yourself.")
        action, reason, at = body.get("action"), str(body.get("reason") or "").strip(), _now()
        if action == "ask_role":
            note = str(body.get("note") or "").strip()
            if not note:
                raise Refuse(422, "Write one line first.")
            rec["history"] = (rec.get("history") or []) + [{"at": at, "by": person_id, "from": p["role"], "to": "",
                                                            "note": "Asked for a different role: " + note}]
            _note(det, "asked", person_id, p, reason=note)
            return p["status"]
        if p["status"] != "invited":
            raise Refuse(409, "You have already answered.")
        if action == "accept":
            p["status"], p["joined_at"] = "joined", at
            _note(det, "joined", person_id, p)
            joined.append(dict(p))
        elif action == "decline":
            if not reason and p["role"] in REASON_ROLES:
                raise Refuse(422, "A short reason helps the organiser plan.")
            p["status"], p["declined"] = "declined", {"at": at, "reason": reason or None}
            _note(det, "declined", person_id, p, reason=reason)
            declined.append(dict(p))
        else:
            raise Refuse(422, "Accept or decline.")
        return p["status"]

    status = _mutate(plane, intent_id, work)
    for p in joined:
        _event(plane, intent_id, "joined", me, person_id, role=p["role"], how="accepted")
    for p in declined:
        _event(plane, intent_id, "person_declined", me, person_id, role=p["role"])
    return status


def _role(plane, request: Request, intent_id: str, person_id: str, body: dict) -> None:
    def work(rec: dict, det: dict) -> None:
        _need_organiser(plane, rec, det, request)
        _need_live(rec)
        p, role, who = _entry(det, person_id), body.get("role"), request.state.account_id
        reason = str(body.get("reason") or "").strip()
        if not p or p["status"] in ("declined", "removed"):
            raise Refuse(404, NOT_FOUND)
        if role != "organiser" and role not in ALLOWED.get(rec["type"], ()):
            raise Refuse(422, f"That role is not used in a {rec['type']} intent.")
        if role == p["role"]:
            return
        if person_id == who:
            raise Refuse(409, "You cannot change your own role. Hand over to another person first.")
        if role == "organiser" and p["status"] not in ("joined", "contributed", "confirmed"):
            raise Refuse(409, "The new organiser must have joined first.")
        if (p["role"] == "participant" and role in ("observer", "affected") or "reporter" in (p["role"], role)) and not reason:
            raise Refuse(422, "Write one line saying why.")
        at, old = _now(), p["role"]
        if role == "organiser":
            boss = _entry(det, who)
            if boss:
                _set_role(rec, det, boss, "participant" if "participant" in ALLOWED.get(rec["type"], ()) else "observer", who, reason or None, at)
        _set_role(rec, det, p, role, who, reason, at)
        _note(det, "role_changed", who, {**p, "role": old}, to=role, reason=reason)
        changed.append((old, role))

    changed: list = []
    _mutate(plane, intent_id, work)
    for old, new in changed:
        _event(plane, intent_id, "person_role_changed", _me(request), person_id, role=new, **{"from": old})


def _remove(plane, request: Request, intent_id: str, person_id: str, body: dict) -> None:
    reason, seat = str(body.get("reason") or "").strip(), []

    def work(rec: dict, det: dict) -> None:
        _need_organiser(plane, rec, det, request)
        _need_live(rec)
        p = _entry(det, person_id)
        if not p or p["status"] == "removed":
            raise Refuse(404, NOT_FOUND)
        if person_id == request.state.account_id:
            raise Refuse(409, "You cannot remove yourself. Hand over to another person first.")
        if not reason:
            raise Refuse(422, "Write one line saying why.")
        p["status"], p["removed"] = "removed", {"by": request.state.account_id, "at": _now(), "reason": reason}
        seat.append(p.get("seat_ref"))
        _note(det, "removed", request.state.account_id, p, reason=reason)

    _mutate(plane, intent_id, work)
    _event(plane, intent_id, "person_removed", _me(request), person_id)
    if seat and seat[0]:  # the seat is taken back through the existing room store; the person's cards stay
        try:
            from modules.m1_intent.store.room import RoomStore
            RoomStore(plane).revoke(seat[0]["session_id"], request.state.account_id, int(seat[0]["n"]))
        except Exception:  # a seat already gone must not undo the removal
            log.warning("the seat could not be taken back")


def _ask_add(plane, request: Request, intent_id: str, text: str) -> None:
    def work(rec: dict, det: dict) -> None:
        _need_live(rec)
        e = _entry(det, request.state.account_id)
        if not e or e["role"] != "sponsor":
            raise Refuse(403, ONLY_ORGANISER)
        if not text.strip():
            raise Refuse(422, "Write one line first.")
        rec["history"] = (rec.get("history") or []) + [{"at": _now(), "by": e["person_id"], "from": "", "to": "",
                                                        "note": "Asked the organiser to add someone: " + text.strip()}]
        _note(det, "asked", e["person_id"], e, reason=text.strip())

    _mutate(plane, intent_id, work)


# ---- hooks for the other cards (join link, first card, confirm) ---------------------------------------------------------
def record_join(plane, intent_id: str, account_id: str | None, name: str, session_id: str, seat: int) -> None:
    """Called by the join route once a seat is taken: Joined, via link, pointing at the seat. A person already listed keeps their entry."""
    pid = account_id or f"guest-{session_id}-{seat}"

    def work(rec: dict, det: dict) -> None:
        _need_live(rec)
        at = _now()
        p = _entry(det, pid)
        if not p:
            p = _entry_new(pid, name, "participant", "link", None, at)
            det["people_detail"].append(p)
        p.update(status="joined", joined_at=p["joined_at"] or at, seat_ref={"session_id": session_id, "n": seat})
        _note(det, "joined", pid, p)
    _mutate(plane, intent_id, work)
    _event(plane, intent_id, "joined", {"account": pid, "name": name, "role": "participant"}, pid, role="participant", how="link")


def seat_invited(plane, intent_id: str) -> None:
    """Inviting gives a wall seat (F51): every invited participant or sponsor with an account and no seat takes the next free seat
    of the wall's room, once the room has been started (the room's start calls this too). Never fails the invite."""
    try:
        from modules.m1_intent.store.room import RoomStore
        from sh_platform.intents import wall
        rec = S.read_intent(plane, intent_id)
        sids = wall.session_ids(rec) if rec else []
        rooms = RoomStore(plane)
        room = rooms.get(sids[0]) if sids else None
        if not room or rec["state"] in ("closed", "cancelled"):
            return
        for e in _detail(plane, intent_id)["people_detail"]:
            if e["status"] not in ("invited", "joined", "contributed") or e["role"] not in ("participant", "sponsor") or e["person_id"].startswith("guest-"):
                continue
            room = rooms.get(sids[0])
            free = next((x["n"] for x in room["seats"] if x["state"] == "free"), None)
            if free is None:
                return
            if rooms.seat_of_account(sids[0], e["person_id"]):
                continue
            seat, _ = rooms.take(sids[0], free, e["name"], "Participant", e["person_id"])
            record_join(plane, intent_id, e["person_id"], e["name"], sids[0], seat["n"])
    except Exception:  # noqa: BLE001 - a person without a seat can still join with the link
        log.warning("seats for the invited could not be taken on %s", intent_id, exc_info=True)


def mark_contributed(plane, intent_id: str, account_id: str) -> None:
    """The person's first card, answer or view: Joined to Contributed. Observers and affected people stay as they are."""
    def work(rec: dict, det: dict) -> None:
        p = _entry(det, account_id)
        if p and p["status"] == "joined" and p["role"] not in ("observer", "affected"):
            p.update(status="contributed", first_contribution_at=_now())
    _mutate(plane, intent_id, work)


def mark_confirmed(plane, intent_id: str, account_id: str, stage: str) -> None:
    def work(rec: dict, det: dict) -> None:
        p = _entry(det, account_id)
        if p and p["status"] in ("joined", "contributed") and p["role"] not in ("observer", "affected"):
            p.update(status="confirmed", confirmed_at=_now(), confirmed_stage=stage)
    _mutate(plane, intent_id, work)


def confirmed_in_baseline(plane, baseline_id: str, name: str, accounts: list[dict], stage: str = "define") -> None:
    """A person confirmed something in this baseline's governed state: Confirmed on the intent that owns the baseline. Never raises."""
    try:
        who = [a["account_id"] for a in accounts if pview.norm(a.get("display_name")) == pview.norm(name) and not a.get("disabled")]
        for row in S.read_index(plane):
            if len(who) == 1 and baseline_id in ((S.read_intent(plane, row["id"]) or {}).get("refs") or {}).get("baseline_ids", []):
                mark_confirmed(plane, row["id"], who[0], stage)
    except Exception:  # noqa: BLE001 - the confirm has happened; a people record that cannot be written never undoes it
        log.warning("a confirm could not be recorded on the intent", exc_info=True)


def pulse_people(plane, v, now) -> list[dict]:
    """Pulse lines for the reader to add (SHAPES section 1): invited, told, and the organiser's 'not answered' line."""
    out = []
    for row in S.read_index(plane):
        if row["state"] not in ("open", "in_session") or not v.account_id:
            continue
        try:
            rec, det = S.read_intent(plane, row["id"]), _detail(plane, row["id"])
        except (S.Unreadable, Refuse):
            continue
        href, ref = f"/centre/intent/{rec['id']}", f"intents/{rec['id']}"
        ends = (rec.get("time_box") or {}).get("ends")
        mine = next((p for p in det["people_detail"] if p["person_id"] == v.account_id and p["status"] == "invited"), None)
        if mine:
            told = mine["role"] == "affected"
            out.append(pulse_lines.line(f"intent-invite:{rec['id']}", "invite", rec.get("title") or "An intent",
                                        "Nothing is asked of you." if told else ROLE_WORDS.get(mine["role"], "You are invited."),
                                        href if told else href + "?view=invitation", "Read it" if told else "Open the invitation", ref,
                                        mine["invited_at"], ends))
        if (rec["people"].get("organiser") or {}).get("account_id") == v.account_id:
            n = sum(1 for p in det["people_detail"] if p["status"] == "invited" and p["required"])
            if n:
                out.append(pulse_lines.line(f"intent-wait:{rec['id']}", "ops", rec.get("title") or "An intent", f"{n} invited {'person has' if n == 1 else 'people have'} not answered",
                                            href + "/people", "Open people", ref, rec.get("updated_at")))
    return out


# ---- routes -----------------------------------------------------------------------------------------------------------
def _go(fn: Callable[[], object]):
    try:
        return fn()
    except Refuse as e:
        return JSONResponse({"error": "not_allowed" if e.status == 403 else "bad_request", "message": e.message}, status_code=e.status)
    except S.VersionConflict:
        return JSONResponse({"error": "bad_request", "message": S.CONFLICT}, status_code=409)
    except PermissionError:
        return JSONResponse({"error": "forbidden", "message": NOT_FOUND}, status_code=403)


def _show(request: Request, intent_id: str) -> dict:
    plane, me = _plane(request), request.state.account_id

    def told(rec: dict, det: dict) -> None:  # an affected person who opens the intent is shown as Joined
        p = _entry(det, me)
        if p and p["role"] == "affected" and p["status"] == "invited":
            p.update(status="joined", joined_at=_now())
    p = _entry(_detail(plane, intent_id), me)
    if p and p["role"] == "affected" and p["status"] == "invited":
        _mutate(plane, intent_id, told)
    rec, det = _read(plane, intent_id), _detail(plane, intent_id)
    _adopt(rec, det)
    return _masked(request, plane, _view(request, plane, rec, det))


def _masked(request: Request, plane, out):
    """Other people's account ids never leave (SEC0 #4): person ids instead; the viewer keeps their own."""
    return S.mask_accounts(out, _viewer(request), S.refs_of(plane))


def _acct(request: Request, plane, ref) -> str:
    """What a screen sends back (a person id, or the viewer's own account id) as the account id the list is keyed by."""
    if not isinstance(ref, str):
        return ref
    return S.account_for(ref, S.refs_of(plane), _accounts(request)) or ref


@router.get("/api/intents/people")
def get_intents_people(request: Request):
    """The company people list for the invite dialog, with how many people each area holds."""
    def run():
        plane = _plane(request)
        from sh_platform.profile import areas as areas_store
        from sh_platform.profile import store as pstore
        ppl = _company_people(request, plane)
        listing = [a for a in areas_store.listing(pstore.load(plane)) if a["status"] == "active"]
        refs, me = S.refs_of(plane), request.state.account_id  # `ref`: the id an intent's people list shows for the same person
        return {"people": [{**{k: v for k, v in p.items() if k != "area_ids"}, "ref": p["person_id"] if p["person_id"] == me else S.public_ref(p["person_id"], refs)}
                           for p in ppl],
                "areas": [{"id": a["id"], "name": a["name"], "count": sum(1 for p in ppl if a["id"] in p["area_ids"])} for a in listing]}
    return _go(run)


@router.get("/api/intents/{intent_id}/people")
def get_intents_by_intent_id_people(request: Request, intent_id: str):
    return _go(lambda: _show(request, intent_id))


def _post(request: Request, intent_id: str, body: dict):
    plane = _plane(request)
    if body.get("ask") is not None:
        _ask_add(plane, request, intent_id, str(body["ask"]))
    elif body.get("remind") is not None:
        drafts = _remind(plane, request, intent_id, [_acct(request, plane, x) for x in body["remind"] if isinstance(x, str)])
        return {**_show(request, intent_id), "reminders": _masked(request, plane, drafts)}
    else:
        if isinstance(body.get("people"), list):
            body = {**body, "people": [{**x, "person_id": _acct(request, plane, x.get("person_id"))} if isinstance(x, dict) else x for x in body["people"]]}
        body = {**body, **{k: _acct(request, plane, body[k]) for k in ("decider", "owner") if body.get(k)}}
        _invite(plane, request, intent_id, body)
    return _show(request, intent_id)


async def _body(request: Request) -> dict:
    try:
        b = await request.json()
    except ValueError:
        return {}
    return b if isinstance(b, dict) else {}


@router.post("/api/intents/{intent_id}/people")
async def post_intents_by_intent_id_people(request: Request, intent_id: str):
    body = await _body(request)
    return _go(lambda: _post(request, intent_id, body))


@router.put("/api/intents/{intent_id}/people")
async def put_intents_by_intent_id_people(request: Request, intent_id: str):
    body = await _body(request)
    return _go(lambda: _post(request, intent_id, body))


@router.post("/api/intents/{intent_id}/people/{person_id}/answer")
async def post_intents_by_intent_id_people_by_person_id_answer(request: Request, intent_id: str, person_id: str):
    body = await _body(request)

    def run():
        plane = _plane(request)
        status = _answer(plane, request, intent_id, _acct(request, plane, person_id), body)
        try:
            return {**_show(request, intent_id), "answered": status}
        except Refuse:  # a decliner may no longer see the intent; the card still thanks them
            return {"answered": status}
    return _go(run)


@router.post("/api/intents/{intent_id}/people/{person_id}/role")
async def post_intents_by_intent_id_people_by_person_id_role(request: Request, intent_id: str, person_id: str):
    body = await _body(request)
    return _go(lambda: (_role(_plane(request), request, intent_id, _acct(request, _plane(request), person_id), body), _show(request, intent_id))[1])


@router.post("/api/intents/{intent_id}/people/{person_id}/remove")
async def post_intents_by_intent_id_people_by_person_id_remove(request: Request, intent_id: str, person_id: str):
    body = await _body(request)
    return _go(lambda: (_remove(_plane(request), request, intent_id, _acct(request, _plane(request), person_id), body), _show(request, intent_id))[1])


@router.post("/api/intents/{intent_id}/people/{person_id}/remind")
def post_intents_by_intent_id_people_by_person_id_remind(request: Request, intent_id: str, person_id: str):
    """Needs its permission line in route_permissions.yaml; the screen uses POST .../people with {remind: [ids]} meanwhile."""
    return _go(lambda: {"reminders": _masked(request, _plane(request), _remind(_plane(request), request, intent_id, [_acct(request, _plane(request), person_id)]))})
