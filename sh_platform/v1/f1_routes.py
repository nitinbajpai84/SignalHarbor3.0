"""F1 routes: the data engineer's conversation with Flow (f1_chat.py). Reads for the build seats and the decision maker; answering and
flagging for the data engineer (analyst, company admin), checked again here through sh_platform.v1.seats. A switched-off Build centre is
refused as B3 does.

- `GET /api/v1/build/{iid}/engineer` → {turns, opening, points, current, context, handed_over}
- `POST /api/v1/build/{iid}/engineer` {text, point?} → the same, after Flow's reply
- `POST /api/v1/build/{iid}/engineer/flag` {point, note} → the same, the point flagged for a human data engineer
- `GET /api/v1/build/{iid}/engineer/flagged.md` → the flagged points as Markdown"""
import json

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from sh_platform.build.agents import runtime as R
from sh_platform.build import runner
from sh_platform.v1 import f1_chat as C
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import p1_project as P1
from sh_platform.v1 import t2_tickets as T2
from sh_platform.v1 import i2_north as N
from sh_platform.v1.i2_routes import MAX_TURN_BODY, _decode
from sh_platform.v1.b3_routes import _answer, _err, _plane_or_err
from sh_platform.v1.seats import DATA_ENGINEER, require_seat, seat_of

router = APIRouter()
BASE = "/api/v1/build/{iid}/engineer"


async def _body(request: Request):
    try:
        raw = await request.body()
        body = json.loads(raw) if len(raw) <= MAX_TURN_BODY else None
    except ValueError:
        body = None
    return body if isinstance(body, dict) else None


def _gate(request: Request, iid: str, need: str = "read") -> None:
    """G1: the engineer screen is the project's. An engineer holding a ticket on it joins the team as engineer here, then the gate applies."""
    plane, viewer = runner._company(request)
    prj = P1.for_intent(plane, iid)
    if prj and DATA_ENGINEER in seat_of(viewer) and G1.level(plane, viewer, prj) != "full" and T2.assigned_on(plane, viewer, prj["id"]):
        G1.join(plane, prj["id"], viewer.name, "data engineer", viewer.account_id)
    G1.http_gate(plane, viewer, iid, need)


@router.get(BASE)
def get_engineer(request: Request, iid: str):
    _gate(request, iid)
    plane, err = _plane_or_err(request)
    return err or _answer(lambda: C.view(plane, iid))


@router.post(BASE)
async def post_engineer(request: Request, iid: str):
    viewer = require_seat(request, DATA_ENGINEER)
    _gate(request, iid, "full")
    plane, err = _plane_or_err(request)
    if err:
        return err
    body = await _body(request)
    if body is None or not isinstance(body.get("text"), str):
        return _err(422, "refused", "Send your answer as text.")
    point = body.get("point") if isinstance(body.get("point"), str) else None
    rt = R.runtime_for_request(request, plane, viewer)
    raw_files = body.get("files")
    try:  # V1: files dropped into Flow's conversation, saved as I2 saves them
        files = [N.save_file(plane, iid, str(f.get("name") or ""), _decode(f.get("data")), f.get("kind"))
                 for f in raw_files or [] if isinstance(f, dict)] if isinstance(raw_files, list) else []
    except N.Refused as e:
        return _err(e.status, "refused", e.message)
    return await run_in_threadpool(_answer, lambda: C.chat(plane, iid, viewer, body["text"], point, rt=rt, files=files))


@router.post(BASE + "/flag")
async def post_flag(request: Request, iid: str):
    viewer = require_seat(request, DATA_ENGINEER)
    _gate(request, iid, "full")
    plane, err = _plane_or_err(request)
    if err:
        return err
    body = await _body(request)
    if body is None or not isinstance(body.get("point"), str):
        return _err(422, "refused", "Name the point to flag.")
    return _answer(lambda: C.flag(plane, iid, viewer, body["point"], str(body.get("note") or "")))


@router.get(BASE + "/flagged.md")
def get_flagged(request: Request, iid: str):
    _gate(request, iid)
    plane, err = _plane_or_err(request)
    if err:
        return err
    return _answer(lambda: Response(C.flagged_markdown(plane, iid), media_type="text/markdown; charset=utf-8",
                                    headers={"Content-Disposition": f'attachment; filename="open-points-{iid}.md"'}))
