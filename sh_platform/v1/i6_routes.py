"""I6a routes: North's conversation. Body reading, file decoding, refusals, the model and the pack come from I2's routes.

- `GET /api/v1/intents/open` → {id, greeting, recent}: the person's open intent (SOW not signed), or id null, North's greeting, and their latest intents with a state word.
- `POST /api/v1/intents/chat` {text, files?: [{name, data (base64), kind}]} → a new intent, North's first reply by the model.
- `GET /api/v1/intents/{iid}/chat` → thread, sow, process_map. For the decision maker it first answers a person turn North has not
  answered yet (an intent started through I2's `POST /api/v1/intents`: its fixed opening question is replaced by North's own reply).
- `POST /api/v1/intents/{iid}/chat` {text, files?} → the same, after North's reply. Files: base64 or stored records, as I2's.
- `POST /api/v1/intents/{iid}/send-to-build` → {by, at, project_id}: the signed intent is ready for Build (I1).
- `POST /api/v1/intents/{iid}/chat/files` {name, data, kind} → {name, path, kind}, as I2's.
"""
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import i2_north as N
from sh_platform.v1 import i6_chat as C
from sh_platform.v1.i2_routes import MAX_FILE_BODY, MAX_TURN_BODY, _answer, _decode, _json_body, _model, _pack
from sh_platform.v1.seats import CONSUMER, require_seat, viewer_of

router = APIRouter()


def _files(plane, iid: str, raw) -> list[dict]:
    out = []
    for f in raw or []:
        if not isinstance(f, dict):
            raise N.Refused(400, "That file could not be read. Please try again.")
        out.append(N.save_file(plane, iid, str(f.get("name") or ""), _decode(f["data"]), f.get("kind")) if f.get("data")
                   else N.stored_file(plane, f))
    return out


@router.get("/api/v1/intents/open")
def open_intent(request: Request):
    viewer = viewer_of(request)

    def work():
        plane = _plane(request)
        return {"id": C.open_intent(plane, viewer), "greeting": C.greeting(plane, viewer), "recent": C.recent_intents(plane, viewer)}
    return _answer(work)


@router.post("/api/v1/intents/chat")
async def start(request: Request):
    viewer = require_seat(request, CONSUMER)
    body = await _json_body(request, MAX_TURN_BODY)
    if isinstance(body, JSONResponse):
        return body

    def work():
        plane = _plane(request)
        raw = body.get("files") or []
        if not isinstance(raw, list) or not all(isinstance(f, dict) and f.get("data") for f in raw):
            raise N.Refused(400, "That file could not be read. Please try again.")
        files = [{"name": str(f.get("name") or ""), "data": _decode(f["data"]), "kind": f.get("kind")} for f in raw]
        return C.start(plane, viewer, str(body.get("text") or body.get("line") or ""), files,
                       model=_model(request, plane), pack=_pack(request), template_id=str(body.get("template_id") or "") or None)
    return await run_in_threadpool(_answer, work)


@router.get("/api/v1/intents/{iid}/chat")
async def get_chat(iid: str, request: Request):
    viewer = viewer_of(request)
    G1.http_gate(_plane(request), viewer, iid)  # G1

    def work():
        plane = _plane(request)
        if C.pending(N.read_thread(plane, iid)) and G1.for_intent(plane, viewer, iid, "full") == "full":
            return C.answer_pending(plane, iid, viewer, model=_model(request, plane), pack=_pack(request))
        return C.view(plane, iid)
    return await run_in_threadpool(_answer, work)


@router.post("/api/v1/intents/{iid}/chat/files")
async def upload(iid: str, request: Request):
    G1.http_gate(_plane(request), require_seat(request, CONSUMER), iid, "full")  # G1
    body = await _json_body(request, MAX_FILE_BODY)
    if isinstance(body, JSONResponse):
        return body
    return await run_in_threadpool(_answer, lambda: N.save_file(_plane(request), iid, str(body.get("name") or ""),
                                                                _decode(body.get("data")), body.get("kind")))


@router.post("/api/v1/intents/{iid}/chat")
async def post_chat(iid: str, request: Request):
    viewer = require_seat(request, CONSUMER)
    G1.http_gate(_plane(request), viewer, iid, "full")  # G1
    body = await _json_body(request, MAX_TURN_BODY)
    if isinstance(body, JSONResponse):
        return body

    def work():
        plane = _plane(request)
        return C.chat(plane, iid, viewer, str(body.get("text") or ""), _files(plane, iid, body.get("files")),
                      model=_model(request, plane), pack=_pack(request))
    return await run_in_threadpool(_answer, work)


@router.post("/api/v1/intents/{iid}/send-to-build")
async def send_to_build(iid: str, request: Request):
    """I1: the signed intent of work is ready for Build; the head of data gets a card in Action. Only who may sign (I4's rule)."""
    from sh_platform.v1.i4_routes import _signer
    viewer = _signer(request, iid)
    return await run_in_threadpool(_answer, lambda: C.send_to_build(_plane(request), iid, viewer))
