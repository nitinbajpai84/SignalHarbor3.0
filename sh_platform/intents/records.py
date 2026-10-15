"""Spec 01: the intent record and its routes. Handlers hold the signed-in plane and viewer (`_plane`, `_viewer`), check the person's part in
the intent, and write through store.update_intent (lock, version check, index row). The transition rules live in lifecycle.py.

The spec spells edit and state as PATCH and close as POST; the stub and the permission file spell edit and state as PUT. Both answer."""
import json
import logging

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from sh_platform.intents import events as E
from sh_platform.intents import lifecycle as L
from sh_platform.intents import store as S
from sh_platform.intents import _plane, _viewer
from sh_platform.intents.search import query_index
from sh_platform.plane import CrossCompanyError

log = logging.getLogger(__name__)
router = APIRouter()
TITLE_MAX, PURPOSE_MAX, AREA_MAX, NAME_MAX = 200, 500, 60, 120
EDITABLE = ("title", "purpose", "areas", "people", "affected_may_read")


def _run(request: Request, fn, status: int = 200):
    """Run `fn(plane, viewer, now)`, mapping the plain-words refusals to JSON answers."""
    try:
        plane, viewer = _plane(request), _viewer(request)
        return JSONResponse(fn(plane, viewer, S.now_iso()), status_code=status)
    except L.Refused as e:
        return JSONResponse({"detail": e.message}, status_code=e.status)
    except S.VersionConflict:
        return JSONResponse({"detail": S.CONFLICT}, status_code=409)
    except (PermissionError, CrossCompanyError):
        return JSONResponse({"detail": "You cannot do that."}, status_code=403)
    except (LookupError, ValueError) as e:
        if isinstance(e, LookupError):
            return JSONResponse({"detail": S.NOT_FOUND}, status_code=404)
        return JSONResponse({"detail": str(e) or "That is not valid."}, status_code=400)
    except S.Unreadable:
        return JSONResponse({"detail": S.UNREADABLE}, status_code=500)


def _body(body) -> dict:
    if not isinstance(body, dict):
        raise ValueError("Please send the details as a JSON object.")
    return body


def _version(body: dict) -> int:
    v = body.get("version")
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError("Please reload and try again: the version is missing.")
    return v


def _seen(plane, viewer, intent_id: str) -> tuple[dict, str, frozenset]:
    """The record, the viewer's tier by file 05's matrix, and the viewer's areas (carrying the matrix context); no tier answers 404."""
    rec = S.read_intent(plane, intent_id)
    areas = S.areas_of(plane, viewer)
    tier = S.tier_of(rec, viewer, areas) if rec else None
    if tier is None:
        raise LookupError(intent_id)
    return rec, tier, areas


def _act(request: Request, intent_id: str, body, change):
    """One organiser-style write: 404 unless seen, version check, `change(rec, viewer, now)`, answer at the viewer's tier."""
    def go(plane, viewer, now):
        b = _body(body)
        areas = _seen(plane, viewer, intent_id)[2]
        by = viewer.account_id
        before: dict = {}

        def edit(r):
            before.update(state=r["state"], stages={s["key"]: s["state"] for s in r.get("stages") or []})
            return change(r, by, b, now, plane, request)
        rec = S.update_intent(plane, intent_id, _version(b), edit)
        _trail(plane, viewer, rec, before, b)
        return S.cut(rec, S.tier_of(rec, viewer, areas) or "exists", viewer, areas.ctx)
    return _run(request, go)


def _trail(plane, viewer, rec: dict, before: dict, b: dict) -> None:
    """The lines a state or stage move leaves in events.jsonl (spec 16): opened, stage opened or closed, closed, cancelled, any other move."""
    who = {"account": viewer.account_id, "name": viewer.name, "role": "organiser"}
    put = lambda kind, detail, **kw: E.try_append(plane, rec["id"], kind, who, None, detail, "act", **kw)  # noqa: E731
    old, new = before.get("state"), rec["state"]
    if old != new:
        if (old, new) == ("draft", "open"):
            if not any(e["kind"] == "opened" for e in E.read_events(plane, rec["id"])):
                put("opened", {"type": rec["type"]})
        elif new == "closed":
            put("closed", {})
        elif new == "cancelled":
            put("cancelled", {"cancel_reason": "given"} if b.get("cancel_reason") else {})
        else:
            put("state_changed", {"from": old, "to": new})
    for s in rec.get("stages") or []:
        was = (before.get("stages") or {}).get(s["key"])
        if s["state"] == "open" and was != "open":
            put("stage_opened", {"stage": s["key"]}, stage=s["key"])
        elif s["state"] == "closed" and was == "open":
            put("stage_closed", {"stage": s["key"], "closed_by": "person"}, stage=s["key"])


# ---- people and fields ------------------------------------------------------------------------------------------------------

def _person(p, accounts: dict) -> dict | None:
    if p is None:
        return None
    if not isinstance(p, dict) or not isinstance(p.get("name"), str) or not p["name"].strip() or len(p["name"]) > NAME_MAX:
        raise ValueError("Each person needs a name.")
    aid = p.get("account_id")
    if aid is not None and aid not in accounts:
        raise ValueError("That person has no account in this company.")
    return L.person(aid, p["name"].strip())


def _people(patch, rec_people: dict, accounts: dict) -> dict:
    if not isinstance(patch, dict) or set(patch) - set(S.SLOTS) - set(S.LISTS):
        raise ValueError("Those are not places for people.")
    if "organiser" in patch and (patch["organiser"] or {}).get("account_id") != (rec_people.get("organiser") or {}).get("account_id"):
        raise ValueError("The organiser cannot be changed here.")
    out = dict(rec_people)
    for k, v in patch.items():
        if k == "organiser":
            continue
        if k in S.LISTS:
            if not isinstance(v, list):
                raise ValueError("That should be a list of people.")
            out[k] = [_person(x, accounts) for x in v if x]
        else:
            out[k] = _person(v, accounts)
    return out


def _text(v, limit: int, what: str) -> str:
    if not isinstance(v, str) or len(v) > limit:
        raise ValueError(f"The {what} must be text of at most {limit} characters.")
    return v.strip()


def _areas(v) -> list[str]:
    if not isinstance(v, list) or any(not isinstance(a, str) or not a.strip() or len(a) > AREA_MAX for a in v) or len(v) > 20:
        raise ValueError("Areas must be a short list of names.")
    return list(dict.fromkeys(a.strip() for a in v))


def _accounts(request: Request) -> dict:
    return {a["account_id"]: a for a in request.app.state.account_store.in_company(request.state.company_id)}


def _apply(rec: dict, patch: dict, accounts: dict) -> None:
    if set(patch) - set(EDITABLE) - {"version"}:
        raise ValueError("That field cannot be changed here.")
    if "title" in patch:
        rec["title"] = _text(patch["title"], TITLE_MAX, "title")
    if "purpose" in patch:
        rec["purpose"] = _text(patch["purpose"], PURPOSE_MAX, "purpose")
    if "areas" in patch:
        rec["areas"] = _areas(patch["areas"])
    if "people" in patch:
        rec["people"] = _people(patch["people"], rec["people"], accounts)
    if "affected_may_read" in patch:
        if not isinstance(patch["affected_may_read"], bool):
            raise ValueError("That should be on or off.")
        rec["affected_may_read"] = patch["affected_may_read"]


# ---- references -------------------------------------------------------------------------------------------------------------

def _json(plane, *parts) -> dict | None:
    try:
        d = json.loads(plane.path(*parts).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError, CrossCompanyError):
        return None


def _refs_resolved(plane, refs: dict) -> list[dict]:
    """One line per id, read from the owning module's files at the moment of reading; nothing is copied into the intent."""
    out = []
    for sid in refs.get("wall_session_ids") or []:
        d = _json(plane, "intents", "m1_intent", "sessions", f"{sid}.json")
        out.append({"ref": sid, "kind": "wall", "state": d.get("state")} if d else _gone(sid, "wall session not found"))
    if refs.get("charter_outcome_id"):
        cid = refs["charter_outcome_id"]
        d = _json(plane, "intents", "m1_intent", "outcomes", f"{cid}.json")
        out.append({"ref": cid, "kind": "charter", "signed": bool(d.get("signed_at"))} if d else _gone(cid, "charter not found"))
    for bid in refs.get("baseline_ids") or []:
        out.append({"ref": bid, "kind": "baseline", "state": "found"} if plane.path("intents", "m2_baseline", bid).is_dir()
                   else _gone(bid, "baseline not found"))
    for aid in refs.get("assessment_ids") or []:
        out.append({"ref": aid, "kind": "assessment", "state": "found"} if plane.path("intents", "m3_connect", "assessments", aid).exists()
                   else _gone(aid, "assessment not found"))
    return out


def _gone(ref: str, missing: str) -> dict:
    return {"ref": ref, "status": "Not available yet", "missing": missing}


# ---- routes -----------------------------------------------------------------------------------------------------------------

SEARCH_KEYS = ("q", "cursor", "limit", "sort", "role", "timebox", "outcome", "rated")


@router.get("/api/intents")
def get_intents(request: Request):
    """The plain list; with any search key (spec 15) the search answer {items, total, facets, ...} from search.query_index."""
    q = request.query_params
    if any(k in q for k in SEARCH_KEYS):
        return _run(request, lambda plane, viewer, now: query_index(plane, viewer, dict(q)))
    return _run(request, lambda plane, viewer, now: S.list_for_viewer(
        plane, viewer, type=q.get("type"), state=q.get("state"), area=q.get("area"), mine=q.get("mine") == "1", view=q.get("view")))


# GET /api/intents/control is gone (ruling R6): the super admin reads existence and counts through /api/control (B31).


@router.post("/api/intents")
def post_intents(request: Request, body: dict = Body(default={})):
    def go(plane, viewer, now):
        b = _body(body)
        if b.get("type") not in S.PREFIX:
            raise ValueError("Please choose a type of intent.")
        if not viewer.account_id:
            raise PermissionError
        origin = (b.get("links") or {}).get("from")
        if origin is not None and (not isinstance(origin, str) or S.read_intent(plane, origin) is None):
            raise ValueError("The intent this follows could not be found.")
        rec = L.new_record(b["type"], request.state.company_id, L.person(viewer.account_id, viewer.name), now, link_from=origin)
        _apply(rec, {k: b[k] for k in EDITABLE if k in b}, _accounts(request))
        for k in ("start_answers", "catalogue_version"):
            if k in b:
                if not isinstance(b[k], (dict if k == "start_answers" else str)):
                    raise ValueError("That is not valid.")
                rec[k] = b[k]
        made = S.create_intent(plane, rec)
        E.try_append(plane, made["id"], "state_changed", {"account": viewer.account_id, "name": viewer.name, "role": "organiser"}, None, {"to": "draft", "from": ""}, "act")
        return S.cut(made, "content", viewer)
    return _run(request, go, 201)


@router.get("/api/intents/{intent_id}")
def get_intents_by_intent_id(request: Request, intent_id: str):
    def go(plane, viewer, now):
        rec, tier, areas = _seen(plane, viewer, intent_id)
        out = S.cut(rec, tier, viewer, areas.ctx)
        if tier == "content":
            out["refs_resolved"] = _refs_resolved(plane, rec.get("refs") or {})
        return out
    return _run(request, go)


def _edit(rec, by, b, now, plane, request):
    L._organiser(rec, by)
    if rec["state"] not in ("draft", "open"):
        raise L.Refused(409, "This intent can no longer be edited.")
    _apply(rec, b, _accounts(request))


@router.patch("/api/intents/{intent_id}")
@router.put("/api/intents/{intent_id}")
def patch_intents_by_intent_id(request: Request, intent_id: str, body: dict = Body(default={})):
    return _act(request, intent_id, body, _edit)


def _state(rec, by, b, now, plane, request):
    L.move(rec, b.get("to"), by, now, note=str(b.get("note") or ""), tz=L.company_zone(plane), ends=b.get("ends"))


@router.patch("/api/intents/{intent_id}/state")
@router.put("/api/intents/{intent_id}/state")
def put_intents_by_intent_id_state(request: Request, intent_id: str, body: dict = Body(default={})):
    return _act(request, intent_id, body, _state)


@router.post("/api/intents/{intent_id}/open")
def post_intents_by_intent_id_open(request: Request, intent_id: str, body: dict = Body(default={})):
    return _act(request, intent_id, {**_body(body), "to": "open"}, _state)


# Extending the time box is clock.py's POST /api/intents/{id}/time-box/extend (B07: one extension alone, then the sponsor decides).


@router.post("/api/intents/{intent_id}/close")
def post_intents_by_intent_id_close(request: Request, intent_id: str, body: dict = Body(default={})):
    return _act(request, intent_id, body, lambda rec, by, b, now, plane, req: L.close(rec, by, b, now))


@router.post("/api/intents/{intent_id}/cancel")
def post_intents_by_intent_id_cancel(request: Request, intent_id: str, body: dict = Body(default={})):
    out = _act(request, intent_id, body, lambda rec, by, b, now, plane, req: L.cancel(rec, by, b.get("cancel_reason"), now))
    if out.status_code == 200:
        try:  # the link lines are written at cancel time; a failure here never undoes the cancel (the chain read repairs it)
            from sh_platform.intents import links
            links.on_cancel(_plane(request), intent_id, _viewer(request))
        except Exception:  # noqa: BLE001
            log.exception("link events after cancel")
    return out


@router.post("/api/intents/{intent_id}/closure/confirm")
def post_intents_by_intent_id_closure_confirm(request: Request, intent_id: str, body: dict = Body(default={})):
    return _act(request, intent_id, body, lambda rec, by, b, now, plane, req: L.confirm(rec, by, now))


@router.post("/api/intents/{intent_id}/stages/{stage_key}/open")
def post_intents_by_intent_id_stages_by_stage_key_open(request: Request, intent_id: str, stage_key: str, body: dict = Body(default={})):
    return _act(request, intent_id, body, lambda rec, by, b, now, plane, req: L.set_stage(rec, stage_key, "open", by, now))


@router.post("/api/intents/{intent_id}/stages/{stage_key}/close")
def post_intents_by_intent_id_stages_by_stage_key_close(request: Request, intent_id: str, stage_key: str, body: dict = Body(default={})):
    return _act(request, intent_id, body, lambda rec, by, b, now, plane, req: L.set_stage(rec, stage_key, "closed", by, now))
