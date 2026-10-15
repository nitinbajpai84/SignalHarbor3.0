"""Card I4 routes: the intent of work page. Reading is for every seat; editing, settling, signing and sending back are the
decision maker's (sh_platform/v1/seats.py). Logic in i4_sow.py."""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from sh_platform.profile.api import _plane
from sh_platform.v1 import i4_sow as S
from sh_platform.v1.seats import CONSUMER, DECISION_MAKER, require_seat, seat_of

router = APIRouter()
BASE = "/api/v1/intents/{iid}/sow"


def _fail(e: S.SowError):
    return HTTPException(e.status, {"error": e.code, "message": e.message})


def _space(request: Request):
    try:
        return _plane(request)
    except PermissionError:
        raise HTTPException(403, {"error": "forbidden", "message": "Your company space could not be opened."}) from None


def _signer(request: Request, iid: str):
    """The viewer if they raised this intent or are its sponsor (or the company admin); else 403. Anyone may raise one."""
    viewer = require_seat(request, CONSUMER)
    if not _may_sign(_space(request), viewer, iid):
        raise HTTPException(403, {"error": "not_allowed", "message": "Only the person who raised this, or the sponsor, can do this."})
    return viewer


def _may_sign(plane, viewer, iid: str) -> bool:
    from sh_platform.v1 import g1_access as G1, p1_project as P1
    if DECISION_MAKER in seat_of(viewer):
        return True
    if not set(getattr(viewer, "roles", ()) or ()) - {"participant"}:
        return False  # NAV-4 (A11): a participant may raise and talk to an intent, never sign it or send it to Build
    rec = P1.for_intent(plane, iid) or {}
    return G1._me(rec.get("raiser_id"), viewer) or G1._me((rec.get("people") or {}).get("raiser") or rec.get("started_by"), viewer)         or G1._me((rec.get("people") or {}).get("sponsor"), viewer)


def _before(plane, iid: str) -> dict | None:
    """Design B3 "Before this": who finished the intent with North, when, and after how many minutes (from the thread's own turns)."""
    from datetime import datetime
    from sh_platform.jsonfile import read_json_strict
    try:
        turns = [t for t in (read_json_strict(plane.path("intents", iid, "thread.json"), dict) or {}).get("turns") or [] if isinstance(t, dict) and t.get("at")]
        times = [datetime.fromisoformat(str(t["at"]).replace("Z", "+00:00")) for t in turns]
    except (OSError, ValueError):
        return None
    if not times:
        return None
    who = next((t.get("name") for t in turns if t.get("by") == "person" and t.get("name")), None)
    return {"by": who, "at": max(times).isoformat(), "minutes": max(1, round((max(times) - min(times)).total_seconds() / 60))}


def _view(sow: dict, viewer, plane) -> dict:
    """The record as stored, plus what this person may do with it (screen only, never saved)."""
    dm = _may_sign(plane, viewer, sow.get("intent_id") or "")
    draft = sow.get("state") != "signed"
    block = S.sign_block(sow) or (S.t1_block(plane, sow.get("intent_id") or "") if draft else None)
    return {**sow, "may": {"edit": dm and draft, "sign": dm and draft and block is None, "send_back": dm and draft},
            "sign_block": block, "docx": S.docx_available(), "before": _before(plane, sow.get("intent_id") or "")}


def _body(body) -> dict:
    if not isinstance(body, dict):
        raise HTTPException(400, {"error": "bad_request", "message": "That could not be read. Please try again."})
    return body


@router.get(BASE)
async def get_sow(request: Request, iid: str):
    viewer = require_seat(request, CONSUMER)
    plane = _space(request)
    try:
        return _view(await run_in_threadpool(S.read, plane, iid), viewer, plane)
    except S.SowError as e:
        raise _fail(e) from None


@router.put(BASE)
async def put_sow(request: Request, iid: str, body: dict | None = Body(None)):
    viewer = _signer(request, iid)
    plane = _space(request)
    try:
        return _view(await run_in_threadpool(S.edit, plane, iid, _body(body), viewer.name), viewer, plane)
    except S.SowError as e:
        raise _fail(e) from None


@router.post(BASE + "/sign")
async def sign_sow(request: Request, iid: str, body: dict | None = Body(None)):
    """{"confirm": true, "version": n}: one click and the confirm sentence on the screen, as the charter's "Are you the sponsor?"."""
    viewer = _signer(request, iid)
    raw = _body(body)
    if raw.get("confirm") is not True:
        raise HTTPException(422, {"error": "unconfirmed", "message": "Please confirm that you sign this intent of work."})
    plane = _space(request)
    role = "sponsor" if "sponsor" in viewer.roles else "company_admin" if "company_admin" in viewer.roles else "raiser"
    try:
        sow, written = await run_in_threadpool(S.sign, plane, iid, viewer.name or "The decision maker", role, raw.get("version"), raw.get("note") or "")
    except S.SowError as e:
        raise _fail(e) from None
    return {**_view(sow, viewer, plane), "written": written}


@router.post(BASE + "/send-back")
async def send_back(request: Request, iid: str, body: dict | None = Body(None)):
    viewer = _signer(request, iid)
    plane = _space(request)
    try:
        return _view(await run_in_threadpool(S.send_back, plane, iid, _body(body).get("reason"), viewer.name or "The decision maker"), viewer, plane)
    except S.SowError as e:
        raise _fail(e) from None


@router.get(BASE + "/download")
async def download(request: Request, iid: str, format: str = "md"):
    require_seat(request, CONSUMER)
    plane = _space(request)
    try:
        sow = await run_in_threadpool(S.read, plane, iid)
    except S.SowError as e:
        raise _fail(e) from None
    lay = await run_in_threadpool(S.layout_of, plane, iid)  # T1b: the template's layout and headings
    if format == "docx":
        if not S.docx_available():
            raise HTTPException(404, {"error": "not_found", "message": "A Word file cannot be made on this server. Download the Markdown file instead."})
        data, mime, ext = await run_in_threadpool(S.to_docx, sow, lay), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"
    elif format == "md":
        data, mime, ext = S.to_markdown(sow, lay).encode("utf-8"), "text/markdown; charset=utf-8", "md"
    elif format == "xlsx" and lay:
        from sh_platform.v1 import t1_layout
        data, mime, ext = (await run_in_threadpool(t1_layout.to_xlsx, lay, f"Intent of work: {sow.get('title') or ''}"),
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx")
    else:
        raise HTTPException(400, {"error": "bad_request", "message": "Choose Markdown, Word or a spreadsheet."})
    return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{S.filename(sow, ext)}"'})
