"""DS1 routes: the dashboard studio in Build. Logic: b7_studio (grid, widgets, Lumen, refresh facts) and cx_dash (lifecycle).

- `GET|POST /api/v1/build/p/{pid}/studio` (POST {title}) ; `GET .../studio/{did}` -> the dashboard, its status, what the person can do, the library, the refresh facts
- `PUT .../studio/{did}/layout` {rows, items:[{id,row,col,size,title?,text?}], title?, company_wide?} ; `POST .../widgets` {kind, table?, row, col, size?}
- `POST .../studio/{did}/ask` {text, picture?, widget?} or {new_talk: true} -> {reply, proposals, ...}: the Consume conversation, moved here (OP1); nothing is placed
- `POST .../studio/{did}/tiles/{tid}/accept` {row?, col?, size?} -> {placed, dashboard} (the chosen slot, else the first free one; a new version replaces its tile in place) ; `.../reject` (Not this)
- `GET .../tiles/{tid}/data` (a preview with live data)
- `POST .../studio/starter` (Lumen's starter draft, H10) ; `POST .../studio/{did}/starter/accept` (Accept as it is)
- `POST .../studio/{did}/submit|approve` ; `POST .../send-back` {reason}"""
import base64
import binascii

from fastapi import APIRouter, Body, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import b7_studio as S
from sh_platform.v1 import b7h_history as H
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import ocr_local
from sh_platform.v1.p1_project import Refused
from sh_platform.v1.seats import viewer_of

router = APIRouter()
BASE = "/api/v1/build/p/{pid}/studio"
DASH = BASE + "/{did}"
PICTURE_MAX = 5 * 1024 * 1024
CODES = {400: "invalid", 403: "not_allowed", 404: "not_found", 409: "conflict"}


async def _run(request: Request, fn):
    viewer, plane = viewer_of(request), _plane(request)
    try:
        return JSONResponse(D.jsonable(await run_in_threadpool(fn, plane, viewer)))
    except Refused as e:
        return JSONResponse({"error": CODES.get(e.status, "failed"), "message": e.message}, status_code=e.status)
    except PermissionError:
        return JSONResponse({"error": "not_allowed", "message": "You do not have access to this."}, status_code=403)


def _maker(viewer) -> None:
    if not S.is_maker(viewer):
        raise Refused(403, "Only the data team can build dashboards.")


@router.get(BASE)
async def studio_list(request: Request, pid: str):
    return await _run(request, lambda p, v: {"dashboards": S.listing(p, v, pid), "can_make": S.is_maker(v)})


@router.post(BASE)
async def studio_create(request: Request, pid: str, body: dict = Body(default_factory=dict)):
    def go(p, v):
        _maker(v)
        return S.view(p, v, pid, S.create(p, v, pid, body.get("title"))["id"])
    return await _run(request, go)


@router.post(BASE + "/starter")
async def studio_starter(request: Request, pid: str):
    """H10: Lumen's starter draft (made when the pipeline went live; made now if it was not)."""
    def go(p, v):
        _maker(v)
        rec = S.start_starter(p, pid)
        if rec is None:
            raise Refused(409, "There are no figures to build a starter dashboard from yet. It appears when the pipeline has run.")
        return S.view(p, v, pid, rec["id"])
    return await _run(request, go)


@router.post(DASH + "/starter/accept")
async def studio_starter_accept(request: Request, pid: str, did: str):
    def go(p, v):
        _maker(v)
        return S.accept_starter(p, v, pid, did)
    return await _run(request, go)


@router.get(DASH)
async def studio_view(request: Request, pid: str, did: str):
    return await _run(request, lambda p, v: S.view(p, v, pid, did))


@router.delete(DASH)
async def studio_delete(request: Request, pid: str, did: str):
    def go(p, v):
        _maker(v)
        S.delete_draft(p, v, pid, did)
        return {"deleted": did}
    return await _run(request, go)


@router.put(DASH + "/layout")
async def studio_layout(request: Request, pid: str, did: str, body: dict = Body(default_factory=dict)):
    def go(p, v):
        _maker(v)
        S.set_layout(p, v, pid, did, body)
        H.record_step(p, v, pid, did, "", "Rearranged the dashboard")
        return S.view(p, v, pid, did)
    return await _run(request, go)


@router.post(DASH + "/widgets")
async def studio_widget(request: Request, pid: str, did: str, body: dict = Body(default_factory=dict)):
    def go(p, v):
        _maker(v)
        placed = S.add_widget(p, v, pid, did, body)
        H.record_step(p, v, pid, did, "", f"Added {placed['title']}")
        return {"placed": placed, "dashboard": S.view(p, v, pid, did)}
    return await _run(request, go)


@router.post(DASH + "/ask")
async def studio_ask(request: Request, pid: str, did: str, body: dict = Body(default_factory=dict)):
    def go(p, v):
        _maker(v)
        return S.ask_lumen(p, v, pid, did, _with_reading(body)) | {"dashboard": S.view(p, v, pid, did)}
    return await _run(request, go)


def _with_reading(body: dict) -> dict:
    """A picture is read on this machine (ocr_local, 5 MB cap); the words go to Lumen and the image goes nowhere else (as in Consume before OP1)."""
    pic = body.get("picture") if isinstance(body.get("picture"), dict) else {}
    if not pic.get("data"):
        return body
    try:
        raw = base64.b64decode(str(pic["data"]), validate=True)
    except (binascii.Error, ValueError):
        raise Refused(400, "The picture could not be read. Try another image.") from None
    if len(raw) > PICTURE_MAX:
        raise Refused(400, "That picture is over 5 MB. Use a smaller one.")
    return body | {"reading": (ocr_local.ocr(raw) or "") if ocr_local.available() else "", "no_client_figures": pic.get("no_client_figures") is True}


@router.post(DASH + "/tiles/{tid}/accept")
async def studio_accept(request: Request, pid: str, did: str, tid: str, body: dict = Body(default_factory=dict)):
    def go(p, v):
        _maker(v)
        placed = S.accept_tile(p, v, pid, did, tid, body)
        H.record_step(p, v, pid, did, "", f"Placed {placed['title']}")
        return {"placed": placed, "dashboard": S.view(p, v, pid, did)}
    return await _run(request, go)


@router.post(DASH + "/tiles/{tid}/reject")
async def studio_reject(request: Request, pid: str, did: str, tid: str):
    def go(p, v):
        _maker(v)
        S.reject_tile(p, v, pid, did, tid)
        return S.view(p, v, pid, did)
    return await _run(request, go)


@router.get(DASH + "/tiles/{tid}/data")
async def studio_tile(request: Request, pid: str, did: str, tid: str):
    return await _run(request, lambda p, v: S.tile_data(p, v, pid, did, tid))


@router.post(DASH + "/submit")
async def studio_submit(request: Request, pid: str, did: str):
    def go(p, v):
        _maker(v)
        if (S._editor(p, v, pid, did).get("starter") or {}).get("status") == "proposed":  # a starter is accepted before it is sent
            S.accept_starter(p, v, pid, did)
        D.submit(p, v, pid, did)
        return S.view(p, v, pid, did)
    return await _run(request, go)


@router.post(DASH + "/approve")
async def studio_approve(request: Request, pid: str, did: str):
    return await _run(request, lambda p, v: (D.decide_version(p, v, pid, did, True), S.view(p, v, pid, did))[1])


@router.post(DASH + "/send-back")
async def studio_send_back(request: Request, pid: str, did: str, body: dict = Body(default_factory=dict)):
    return await _run(request, lambda p, v: (lambda r: {"id": r["id"], "status": D.status_of(r), "sent_back": r["lifecycle"]["sent_back"]})(D.decide_version(p, v, pid, did, False, body.get("reason"))))
