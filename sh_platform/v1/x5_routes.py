"""X5 routes: the extraction spec per document type, the reading, the review queue and the revised spec after a layout change.

- `GET  /api/v1/intents/{iid}/extract` → {types, documents, queue}: the spec panel.
- `POST /api/v1/intents/{iid}/extract/propose` {file} → the proposed type (North proposes from what it sees).
- `PUT  /api/v1/intents/{iid}/extract/types/{tid}` {name?, fields?, remove_fields?, checks?, confirm?} → the type (the person confirms).
- `POST /api/v1/intents/{iid}/extract/run` {files: [...], type_id?} → {extractions}.
- `POST /api/v1/intents/{iid}/extract/types/{tid}/revision` {accept: bool} → the type (version up on yes).
- `GET  /api/v1/extract/queue` → {count, line, items}: "N documents need a look", for Home and the ops page.
- `GET  /api/v1/extract/{doc_id}` → the extraction and the document lines (review page).
- `POST /api/v1/extract/{doc_id}/accept` {values: {field: value}} → {extraction, revision}.
"""
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.build.runner import _company
from sh_platform.profile.api import _plane
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import x5_extract as X
from sh_platform.v1.i2_routes import _answer, _json_body, _model
from sh_platform.v1.seats import DECISION_MAKER, DATA_ENGINEER, require_seat, viewer_of

router = APIRouter()
BODY = 256 * 1024


async def _body(request: Request):
    return await _json_body(request, BODY)


@router.get("/api/v1/intents/{iid}/extract")
def overview(iid: str, request: Request):
    viewer_of(request)
    return _answer(lambda: X.overview(_plane(request), iid))


@router.post("/api/v1/intents/{iid}/extract/propose")
async def propose(iid: str, request: Request):
    require_seat(request, DECISION_MAKER)
    body = await _body(request)
    if isinstance(body, JSONResponse):
        return body

    def work():
        plane = _plane(request)
        return X.propose(plane, iid, str(body.get("file") or ""), model=_model(request, plane))
    return await run_in_threadpool(_answer, work)


@router.put("/api/v1/intents/{iid}/extract/types/{tid}")
async def edit_type(iid: str, tid: str, request: Request):
    require_seat(request, DECISION_MAKER)
    body = await _body(request)
    if isinstance(body, JSONResponse):
        return body

    def work():
        plane = _plane(request)
        t = X.upsert(plane, iid, body, tid=tid, state="confirmed" if body.get("confirm") is True else None)
        if body.get("confirm") is True:
            for f in t["sample_files"]:
                X._safe_run(plane, iid, f, tid, _model(request, plane))
        return X.overview(plane, iid)
    return await run_in_threadpool(_answer, work)


@router.post("/api/v1/intents/{iid}/extract/run")
async def run(iid: str, request: Request):
    require_seat(request, DATA_ENGINEER)
    body = await _body(request)
    if isinstance(body, JSONResponse):
        return body

    def work():
        plane = _plane(request)
        files = body.get("files") if isinstance(body.get("files"), list) else []
        if not files:
            raise X.Refused(400, "Name the documents to read.")
        tid = str(body.get("type_id") or "") or None
        return {"extractions": [X.run(plane, iid, str(f), tid, model=_model(request, plane)) for f in files[:50]]}
    return await run_in_threadpool(_answer, work)


@router.post("/api/v1/intents/{iid}/extract/types/{tid}/revision")
async def revision(iid: str, tid: str, request: Request):
    require_seat(request, DECISION_MAKER)
    body = await _body(request)
    if isinstance(body, JSONResponse):
        return body

    def work():
        plane = _plane(request)
        return X.decide_revision(plane, iid, tid, body.get("accept") is True, model=_model(request, plane))
    return await run_in_threadpool(_answer, work)


@router.get("/api/v1/extract/queue")
def queue(request: Request):
    viewer_of(request)
    plane, viewer = _company(request)
    def mine():
        got = X.queue(plane)
        items = [i for i in got["items"] if G1.can_read_intent(plane, viewer, i.get("intent_id"))]  # G1: only documents of projects the viewer may read
        return {**got, "count": len(items), "line": X.queue_line(len(items)), "items": items}
    return _answer(mine)


@router.get("/api/v1/extract/{doc_id}")
def detail(doc_id: str, request: Request):
    require_seat(request, DATA_ENGINEER)
    plane, viewer = _company(request)

    def one():
        rec = X.read_extraction(plane, doc_id)
        G1.http_gate(plane, viewer, rec.get("intent_id"), "read") if rec.get("intent_id") else None
        from sh_platform.v1 import c4_library as L
        name = str(rec.get("file") or "").replace("\\", "/")
        item = next((i for i in L._index(plane) if str(i.get("path") or "").replace("\\", "/") == name), None)
        if item and not L.readable(item, viewer):  # K1: project read is not the right to the file; the lock and preview only
            return {k: v for k, v in rec.items() if k != "file"} | {"lines": [], "locked": True, "preview": L.shown(item, viewer, plane)}
        return X.detail(plane, doc_id)
    return _answer(one)


@router.post("/api/v1/extract/{doc_id}/accept")
async def accept(doc_id: str, request: Request):
    viewer = require_seat(request, DATA_ENGINEER)
    body = await _body(request)
    if isinstance(body, JSONResponse):
        return body

    def work():
        plane = _plane(request)
        values = body.get("values") if isinstance(body.get("values"), dict) else {}
        return X.accept(plane, doc_id, values, viewer.name, model=_model(request, plane))
    return await run_in_threadpool(_answer, work)
