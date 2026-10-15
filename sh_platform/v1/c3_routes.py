"""C3 routes: Lumen's conversation and the consumption brief. Body reading, refusals, the model and the pack come from I2's routes.

- `GET /api/v1/consume/brief?iid=` → the conversation, the brief, the signed KPIs and the feeds by kind (latest intent when no iid).
- `POST /api/v1/consume/brief/{iid}/chat` {text, files?: [{name, data (base64)}]} → the same after Lumen's reply (the designer: analyst,
  company_admin, sponsor).
- `POST /api/v1/consume/brief/{iid}/input` {text} → an end user's answer to the short version, appended to `end_user_inputs` (any seat).
Paths sit under `/consume/brief` so they never meet C1's `/api/v1/consume/{iid}/{code}`.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import c3_chat as L
from sh_platform.v1.i2_routes import MAX_TURN_BODY, _answer, _decode, _json_body, _model, _pack
from sh_platform.v1.seats import CONSUMER, require_seat

router = APIRouter()
DESIGNER = frozenset({"analyst", "company_admin", "sponsor"})


def _designer(request: Request):
    viewer = require_seat(request, CONSUMER)
    if not DESIGNER & set(viewer.roles or ()):
        raise HTTPException(403, {"error": "not_allowed", "message": "Only the analyst or the decision maker can shape the page. "
                                                                     "Use the short questions to give your view."})
    return viewer


@router.get("/api/v1/consume/brief")
def get_brief(request: Request, iid: str | None = None):
    viewer = require_seat(request, CONSUMER)

    def work():
        plane = _plane(request)
        return L.view(plane, L.pick(plane, iid), viewer, _pack(request))
    return _answer(work)


@router.post("/api/v1/consume/brief/{iid}/chat")
async def post_chat(iid: str, request: Request):
    viewer = require_seat(request, CONSUMER)  # anyone may talk to Lumen; the logic leaves the brief to the designers
    body = await _json_body(request, MAX_TURN_BODY)
    if isinstance(body, JSONResponse):
        return body

    def work():
        plane = _plane(request)
        iid_ = L.pick(plane, iid)
        raw = body.get("files") or []
        if not isinstance(raw, list) or not all(isinstance(f, dict) and f.get("data") for f in raw):
            raise L.N.Refused(400, "That file could not be read. Please try again.")
        files = [L.save_file(plane, iid_, str(f.get("name") or ""), _decode(f["data"])) for f in raw]
        return L.chat(plane, iid_, viewer, str(body.get("text") or ""), files, model=_model(request, plane), pack=_pack(request))
    return await run_in_threadpool(_answer, work)


@router.post("/api/v1/consume/brief/{iid}/input")
async def post_input(iid: str, request: Request):
    viewer = require_seat(request, CONSUMER)
    body = await _json_body(request, MAX_TURN_BODY)
    if isinstance(body, JSONResponse):
        return body

    def work():
        plane = _plane(request)
        return L.end_user_input(plane, L.pick(plane, iid), viewer, str(body.get("text") or ""), _pack(request))
    return await run_in_threadpool(_answer, work)
