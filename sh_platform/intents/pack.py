"""Pack suggestions for the Intent Centre (spec 49): first intents, start hints and check-in questions, read as written.

Every function takes the company's resolved pack (`request.app.state.packs.load(industry)`: the industry comes from the company
record, never from the request). A missing pack, file or version gives the honest empty answer, never another industry's content.
Reading writes nothing: a suggestion becomes the company's own only when a person picks it up (the create press).
"""
import logging
import re

import yaml
from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from sh_platform.intents import _plane, _viewer
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.packs import SUGGESTION_LABEL
from sh_platform.profile import areas as areas_store, store as profile_store
from sh_platform.profile.view import _v

log = logging.getLogger(__name__)
router = APIRouter()
SECTIONS = ("first_intents", "start_hints", "checkin_questions")
TYPES = ("initiative", "brainstorm", "pulse", "problem", "decision")


def intents_section(pack, name: str):
    """Parsed `intents/<name>.yaml` of this pack, or None when there is no pack, no file, or the file cannot be read."""
    if getattr(pack, "empty", True) or name not in SECTIONS:
        return None
    try:
        return pack.intents_section(name)
    except (KeyError, TypeError, AttributeError, OSError, ValueError, yaml.YAMLError):
        log.warning("pack file intents/%s could not be read", name)
        return None


def _head(pack) -> dict:
    if getattr(pack, "empty", True):
        return {"label": SUGGESTION_LABEL, "pack": None, "empty_message": getattr(pack, "message", None)}
    meta = {"industry": pack.industry, "version": pack.version, "label": pack.label, "status": pack.status}
    return {"label": SUGGESTION_LABEL, "pack": meta, "empty_message": None}


def _rows(doc, key: str) -> list[dict]:
    rows = doc.get(key) if isinstance(doc, dict) else None
    return [r for r in rows if isinstance(r, dict) and r.get("id")] if isinstance(rows, list) else []


def first_intents(pack, marks: list[dict] | None = None) -> dict:
    """The strip: `{label, pack, items, empty_message}`. `marks` are this person's rows ({suggestion_id, mark}); a picked up or
    dismissed card is left out for them only. Types the record does not know are dropped."""
    out = _head(pack)
    hidden = {m.get("suggestion_id") for m in marks or [] if m.get("mark") in ("picked_up", "dismissed")}
    source = f"{pack.industry}@{pack.version}" if out["pack"] else None
    out["items"] = [
        {"suggestion_id": r["id"], "type": r.get("type"), "title": r.get("title", ""), "purpose": r.get("purpose", ""),
         "areas": list(r.get("areas") or []), "why": r.get("why", ""), "start_answers": dict(r.get("start_answers") or {}),
         "label": SUGGESTION_LABEL, "source": source}
        for r in _rows(intents_section(pack, "first_intents"), "suggestions")
        if r.get("type") in TYPES and r["id"] not in hidden]
    return out


def start_hints(pack, type_: str) -> dict:
    """`{label, pack, hints: {order: text}}` for one type; an empty `hints` when the pack has none. A hint never fills a field."""
    out = _head(pack)
    doc = intents_section(pack, "start_hints")
    rows = ((doc or {}).get("hints") or {}).get(type_) if isinstance(doc, dict) else None
    out["hints"] = {str(k): str(v) for k, v in rows.items()} if isinstance(rows, dict) else {}
    return out


def checkin_questions(pack, area: str | None = None, marks: list[dict] | None = None) -> dict:
    """`{label, pack, questions: [{suggestion_id, area, text, label}]}` for an area (and `any`); all areas when `area` is None."""
    out = _head(pack)
    hidden = {m.get("suggestion_id") for m in marks or [] if m.get("mark") in ("picked_up", "dismissed")}
    out["questions"] = [
        {"suggestion_id": r["id"], "area": r.get("area", "any"), "text": r.get("text", ""), "label": SUGGESTION_LABEL}
        for r in _rows(intents_section(pack, "checkin_questions"), "questions")
        if r["id"] not in hidden and (area is None or r.get("area") in (area, "any"))]
    return out


# ---- routes: this person's marks, in `intents/_suggestion_marks/<person>.json` (spec 49); the pack files are never written ----------

_WHO = re.compile(r"[^a-z0-9_.-]")


def _who(plane, viewer) -> tuple[str, dict]:
    """The marks file name (profile person, else account) and the viewer's profile row."""
    people = profile_store.load(plane).get("people") or {}
    pid, me = next(((k, p) for k, p in people.items() if isinstance(p, dict) and _v(p, "account_id") == viewer.account_id), (None, {}))
    return _WHO.sub("-", str(pid or viewer.account_id or "").lower()) or "unknown", me


def _marks_file(plane, who: str):
    return plane.path("intents", "_suggestion_marks", f"{who}.json")


def read_marks(plane, who: str) -> list[dict]:
    try:
        doc = read_json_strict(_marks_file(plane, who), dict)
    except (OSError, ValueError):
        log.warning("a suggestion marks file could not be read")
        return []
    rows = (doc or {}).get("marks")
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def _mark(plane, who: str, sid: str, mark: str | None, intent_id: str | None = None) -> None:
    """Replace this person's rows for one suggestion: `dismissed` and `picked_up` are written, None (restore) removes a dismissal."""
    path = _marks_file(plane, who)
    with lock_for(path):
        rows = [r for r in read_marks(plane, who) if r.get("suggestion_id") != sid or (mark is None and r.get("mark") == "picked_up")]
        if mark:
            rows.append({"suggestion_id": sid, "mark": mark, "intent_id": intent_id, "at": _now()})
        write_json_atomic(path, {"marks": rows})


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _pack(request: Request, plane):
    rec = request.app.state.entitlements.company(request.state.company_id) or {}
    return request.app.state.packs.load(rec["industry"]) if rec.get("industry") else request.app.state.packs.load("no_industry")


def _prefill(plane, rows: list[dict]) -> list[dict]:
    """The company's own area ids for the pack's area words (by id or name, any case); words the company has no area for are left out."""
    listing = areas_store.listing(profile_store.load(plane))
    by = {k: a["id"] for a in listing if a["status"] == "active" for k in (str(a["id"]).lower(), str(a["name"] or "").strip().lower())}
    return [{**r, "company_areas": list(dict.fromkeys(by[x.lower()] for x in r["areas"] if x.lower() in by))} for r in rows]


@router.get("/api/intents/suggestions")
def get_intents_suggestions(request: Request):
    """The first-intents strip for this person: only an admin or an organiser sees cards; picked up or dismissed ones are left out."""
    try:
        plane, viewer = _plane(request), _viewer(request)
    except PermissionError:
        return JSONResponse({"error": "forbidden", "message": "You do not have access to this."}, status_code=403)
    who, me = _who(plane, viewer)
    may = "company_admin" in viewer.roles or _v(me, "is_organiser") is True
    marks = read_marks(plane, who)
    out = first_intents(_pack(request, plane), marks)
    out["items"] = _prefill(plane, out["items"]) if may else []
    out["dismissed_ids"] = [m["suggestion_id"] for m in marks if m.get("mark") == "dismissed" and m.get("suggestion_id")] if may else []
    out["dismissed_count"] = len(out["dismissed_ids"])
    out["may_start"] = may
    return out


def _change(request: Request, sid: str, mark: str | None, intent_id: str | None = None):
    try:
        plane, viewer = _plane(request), _viewer(request)
    except PermissionError:
        return JSONResponse({"error": "forbidden", "message": "You do not have access to this."}, status_code=403)
    if not viewer.account_id:
        return JSONResponse({"error": "forbidden", "message": "You do not have access to this."}, status_code=403)
    _mark(plane, _who(plane, viewer)[0], sid[:80], mark, intent_id)
    return {"ok": True}


@router.post("/api/intents/suggestions/{suggestion_id}/dismiss")
def post_intents_suggestions_dismiss(request: Request, suggestion_id: str):
    return _change(request, suggestion_id, "dismissed")


@router.post("/api/intents/suggestions/{suggestion_id}/restore")
def post_intents_suggestions_restore(request: Request, suggestion_id: str):
    return _change(request, suggestion_id, None)


@router.post("/api/intents/suggestions/{suggestion_id}/picked-up")
def post_intents_suggestions_picked_up(request: Request, suggestion_id: str, body: dict = Body(default={})):
    iid = body.get("intent_id") if isinstance(body, dict) else None
    return _change(request, suggestion_id, "picked_up", iid if isinstance(iid, str) else None)


@router.get("/api/intents/hints/{type_}")
def get_intents_hints(request: Request, type_: str):
    try:
        plane = _plane(request)
    except PermissionError:
        return JSONResponse({"error": "forbidden", "message": "You do not have access to this."}, status_code=403)
    return start_hints(_pack(request, plane), type_)
