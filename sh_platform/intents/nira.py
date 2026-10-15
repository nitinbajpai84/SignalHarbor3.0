"""Nira: what is waiting for you (spec 45). The whole list is built on every read from the intent records and never stored; the organiser's
"Who has not acted" panel names the quiet people; Nudge drafts one message through sh_platform/pulse/messages.py and sends nothing."""
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from sh_platform.intents import _plane, _viewer
from sh_platform.intents.clock import DAY, parse, working_seconds
from sh_platform.intents.store import ID_RE
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile import view
import importlib

import sh_platform.pulse as pulse
from sh_platform.pulse import intent_lines as L, messages, templates

router = APIRouter()
COOLDOWN = DAY  # one working day between nudges for one intent (spec 45 open question 4)
CHAT_MAX = 240


# ---- the message: words and dates only, signed North (spec 13). Registered here because templates.py is a shared file.
def intent_nudge(r: dict) -> dict:
    title, what, link = str(r.get("title") or "your intent"), str(r.get("what") or "Open it"), str(r.get("link") or "the Intent Centre")
    due = f" The stage closes {r['due']}." if r.get("due") else ""
    return {"subject": f"A reminder: {title} is waiting for you", "link": link,
            "body": f"Hello, {title} is waiting for you. {what}.{due} Open it here: {link}\n\nThank you,\nNorth",
            "chat": f"{title} is waiting for you. {what}. {link}"[:CHAT_MAX]}


templates.WRITERS["intent_nudge"] = intent_nudge
if "intent_nudge" not in templates.KINDS:
    templates.KINDS = messages.KINDS = (*templates.KINDS, "intent_nudge")
# app.py imports the router as `sh_platform.pulse.__init__`, a second module object, so both are patched
for _m in (pulse, importlib.import_module("sh_platform.pulse.__init__")):
    L.install(_m)  # until pulse/__init__.py calls intent_lines itself


# ---- helpers
def _load(request: Request, intent_id: str):
    """(plane, record, path); the record is None for an intent that does not exist or is still a draft."""
    plane = _plane(request)
    if not ID_RE.fullmatch(intent_id):  # ids are "<prefix>-<hex>", so isalnum() refused every real intent
        return plane, None, None
    path = plane.path("intents", intent_id, "intent.json")
    rec = read_json_strict(path, dict)
    if rec and rec.get("state") != "draft":
        from sh_platform.intents import store as S  # lazy, as elsewhere; hidden answers exactly like missing (file 05)
        v = _viewer(request)
        if S.tier_of(rec, v, S.areas_of(plane, v)) is not None:
            return plane, rec, path
    return plane, None, path


def _is_organiser(request: Request, rec: dict) -> bool:
    v = _viewer(request)
    return "company_admin" in v.roles or L._me((rec.get("people") or {}).get("organiser"), v)


def _name(request: Request, ref) -> str:
    if isinstance(ref, dict) and ref.get("name"):
        return str(ref["name"])
    key = ref.get("account_id") if isinstance(ref, dict) else ref
    return str((request.app.state.account_store.get(key) or {}).get("display_name") or key or "")


def _account(ref) -> str:
    return str(ref.get("account_id") or ref.get("name") or "") if isinstance(ref, dict) else str(ref or "")


def _nudged_at(rec: dict):
    return max((n["at"] for n in rec.get("nudges") or [] if n.get("kind") == "who_has_not_acted" and n.get("at")), default=None)


def _cooling(rec: dict, now: datetime) -> bool:
    at = _nudged_at(rec)
    return bool(at) and working_seconds(parse(at), now) < COOLDOWN


# ---- routes
@router.get("/api/intents/waiting")
def get_intents_waiting(request: Request):
    try:
        plane = _plane(request)
    except PermissionError:
        return JSONResponse({"error": "forbidden", "message": "Your company space could not be opened. Please ask your administrator."}, status_code=403)
    lines = L.waiting(plane, _viewer(request), datetime.now(timezone.utc))
    return {"lines": lines, "count": len(lines)}


@router.get("/api/intents/{intent_id}/who-has-not-acted")
def get_intents_by_intent_id_who_has_not_acted(request: Request, intent_id: str):
    plane, rec, _ = _load(request, intent_id)
    if rec is None:
        return JSONResponse({"detail": "Not found."}, status_code=404)
    if not _is_organiser(request, rec):
        return JSONResponse({"detail": "Only the organiser of this intent can see who has not acted."}, status_code=403)
    q = L.not_acted(plane, rec)
    stage = q["stage"] or {}
    owes = L.OWES.get(rec.get("type"), ("Open it",))[0]
    people = [{"person_id": _account(r), "name": _name(request, r), "owes": owes, "since": q["since"]} for r in q["people"]]
    now = datetime.now(timezone.utc)
    from sh_platform.intents import store as S  # account ids never leave (SEC0 #4): person ids; the nudge route maps them back
    return S.mask_accounts({"intent_id": rec["id"], "active": bool(q["stage"]), "stage": stage.get("key"), "people": people,
                            "count_stage": f"{len(people)} of {q['total']} in this stage", "total": q["total"], "anonymous": q["anonymous"],
                            "nudged_at": _nudged_at(rec), "cooling": _cooling(rec, now),
                            "nudges": len([n for n in rec.get("nudges") or [] if n.get("kind") == "who_has_not_acted"])}, _viewer(request), S.refs_of(plane))


class Nudge(BaseModel):
    to: list[str]


@router.post("/api/intents/{intent_id}/nudge/{person_id}")
def post_intents_by_intent_id_nudge_by_person_id(request: Request, intent_id: str, person_id: str, body: Nudge):
    """One draft for the ticked people. `person_id` is the one person ticked, or `all` with the ticked ids in `to`."""
    plane, rec, path = _load(request, intent_id)
    if rec is None:
        return JSONResponse({"detail": "Not found."}, status_code=404)
    if not _is_organiser(request, rec):
        return JSONResponse({"detail": "Only the organiser of this intent can nudge."}, status_code=403)
    now = datetime.now(timezone.utc)
    ids = body.to if person_id == "all" else [person_id]
    with lock_for(path):
        rec = read_json_strict(path, dict)
        q = L.not_acted(plane, rec)
        quiet = {_account(r): r for r in q["people"]}
        from sh_platform.intents import store as S
        refs = S.refs_of(plane)
        back = {S.public_ref(a, refs): a for a in quiet}
        ids = [back.get(i, i) for i in ids]  # the screen sends person ids (or the viewer's own account id)
        if not ids or any(i not in quiet for i in ids):
            return JSONResponse({"detail": "Tick at least one person who has not acted."}, status_code=422)
        if _cooling(rec, now):
            return JSONResponse({"detail": "You nudged this intent recently. Nudge again after a working day."}, status_code=409)
        s = q["stage"] or {}
        organiser = _viewer(request)
        record = {"to": [{"account_id": i, "name": _name(request, quiet[i])} for i in ids], "title": L._title(rec),
                  "what": L.OWES[rec["type"]][0], "due": (lambda d: L._date(d) if d else None)(L._stage_due(rec, s)),
                  "link": f"/centre/intent/{rec['id']}", "organiser_account_id": organiser.account_id,
                  "from_record": f"intents/{rec['id']}#nudge:{s.get('key')}:{now.date().isoformat()}"}
        msg = messages.draft(plane, "intent_nudge", record)
        rec["nudges"] = [*(rec.get("nudges") or []), {"kind": "who_has_not_acted", "at": now.isoformat(), "message_id": msg["id"], "to": ids}]
        write_json_atomic(path, rec)
    return S.mask_accounts({"message": msg, "nudged_at": now.isoformat()}, _viewer(request), refs)
