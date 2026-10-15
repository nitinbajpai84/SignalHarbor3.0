"""B2 Scan and agree: `POST /api/v1/build/{iid}/scan` (Span reads the landing files against the signed SOW),
`GET …/scan`, `POST …/scan/agree` (decision maker names the scope), `POST …/scan/send-back` (decision maker, with a reason).
Room posts go through `sh_platform.v1.room.post` when it is there; a missing room never breaks the scan."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.jsonfile import read_json_strict
from sh_platform.profile.api import _name, _plane
from sh_platform.v1 import b2_scan as B

log = logging.getLogger(__name__)
router = APIRouter()


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": code, "message": message}, status_code=status)


def _room(plane, iid: str, by: str, kind: str, text: str, to: list[str]) -> None:
    try:
        from sh_platform.v1.room import post
    except ImportError:
        return
    try:
        post(plane, iid, by, kind, text, to=to, refs=[{"kind": "scan", "id": iid}])
    except Exception:  # the room is a side channel: its failure must never undo a written scan
        log.warning("room post for the scan of %s failed", iid, exc_info=True)


def _shown(plane, iid: str, rec: dict | None) -> dict:
    """The record plus what the screen needs beside it: KPI names and the landing files read."""
    sow = read_json_strict(plane.path("intents", iid, "sow.json"), dict) or {}
    names = {k.get("code"): k.get("name") for k in sow.get("kpis") or []}
    return {"scan": rec, "names": names, "files": [{k: f[k] for k in ("path", "columns", "rows")} for f in B.landing_files(plane)]}


async def _body(request: Request) -> dict:
    try:
        body = await request.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


@router.get("/api/v1/build/{iid}/scan")
def get_scan(iid: str, request: Request):
    try:
        plane = _plane(request)
        return _shown(plane, iid, B.read_scan(plane, iid))
    except PermissionError:
        return _err(403, "forbidden", "This company space cannot be opened.")
    except B.ScanError as e:
        return _err(e.status, e.code, e.message)


@router.post("/api/v1/build/{iid}/scan")
def post_scan(iid: str, request: Request):
    try:
        plane = _plane(request)
        rec = B.run_scan(plane, iid)
    except PermissionError:
        return _err(403, "forbidden", "This company space cannot be opened.")
    except B.ScanError as e:
        return _err(e.status, e.code, e.message)
    n = sum(1 for k in rec["kpis"] if k["status"] == "available")
    _room(plane, iid, "span", "handover",
          f"I scanned the landing files against the signed intent of work: {n} of {len(rec['kpis'])} KPIs can be built now. "
          "Please read the scan and agree the scope.", ["people"])
    return _shown(plane, iid, rec)


@router.post("/api/v1/build/{iid}/scan/agree")
async def post_agree(iid: str, request: Request):
    body = await _body(request)
    try:
        plane = _plane(request)
        who = _name(request) or "The decision maker"
        rec = B.agree(plane, iid, body.get("scope"), who)
    except PermissionError:
        return _err(403, "forbidden", "This company space cannot be opened.")
    except B.ScanError as e:
        return _err(e.status, e.code, e.message)
    scope = rec["agreed"]["scope"]
    _room(plane, iid, "span", "handover",
          f"{who} agreed the scope: {', '.join(scope)}. Flow, these can be loaded once the mapping sheet is written.", ["flow", "people"])
    return _shown(plane, iid, rec)


@router.post("/api/v1/build/{iid}/scan/send-back")
async def post_send_back(iid: str, request: Request):
    reason = str((await _body(request)).get("reason") or "").strip()
    if not reason:
        return _err(422, "invalid", "Say in a line what should change before you agree.")
    try:
        plane = _plane(request)
        who = _name(request) or "The decision maker"
        rec = B.send_back(plane, iid)
    except PermissionError:
        return _err(403, "forbidden", "This company space cannot be opened.")
    except B.ScanError as e:
        return _err(e.status, e.code, e.message)
    _room(plane, iid, "person", "question", f"{who} sent the scan back: {reason[:500]}", ["span"])
    return _shown(plane, iid, rec)
