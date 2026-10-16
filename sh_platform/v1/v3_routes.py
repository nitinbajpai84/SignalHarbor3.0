"""Harbor 3.0 routes (spec: docs/v3/HARBOR-SPEC.md). Logic in v3_harbor; every failure answers a plain message, never a trace."""
import base64
import binascii

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from sh_platform.profile.api import _plane
from sh_platform.v1 import v3_harbor as H, v3_signoff as SO
from sh_platform.v1.e0c_routes import _multipart

router = APIRouter()


def _ctx(request: Request):
    plane = _plane(request)
    H.start_scanner(request.app)
    return request.app, plane, request.state.account_id


def _thread(plane, tid):
    try:
        return H.load(plane, tid)
    except KeyError:
        raise HTTPException(404, "I cannot find that thread.") from None


async def _json(request: Request) -> dict:
    try:
        body = await request.json()
    except ValueError:
        body = None
    return body if isinstance(body, dict) else {}


@router.get("/api/v3/desk")
def get_desk(request: Request):
    app, plane, acct = _ctx(request)
    H.scan(app, plane)
    return SO.desk_for(app, plane, acct)


@router.get("/api/v3/threads")
def list_threads(request: Request):
    _, plane, _ = _ctx(request)
    return {"threads": [H.summary(t) for t in H.all_threads(plane)]}


@router.post("/api/v3/threads")
async def new_thread(request: Request):
    app, plane, acct = _ctx(request)
    text = str((await _json(request)).get("text") or "").strip()
    if not text:
        raise HTTPException(400, "Say what you want to know first.")
    return SO.decorate(app, plane, H.view(await run_in_threadpool(H.create, app, plane, text, acct)), acct)


@router.get("/api/v3/threads/{tid}")
def get_thread(tid: str, request: Request):
    app, plane, acct = _ctx(request)
    return SO.decorate(app, plane, H.view(_thread(plane, tid)), acct)


@router.post("/api/v3/threads/{tid}/say")
async def say(tid: str, request: Request):
    app, plane, acct = _ctx(request)
    _thread(plane, tid)
    text = str((await _json(request)).get("text") or "").strip()
    if not text:
        raise HTTPException(400, "Say something first.")
    return SO.decorate(app, plane, H.view(await run_in_threadpool(H.say, app, plane, tid, text, acct)), acct)


@router.post("/api/v3/threads/{tid}/decide")
async def decide(tid: str, request: Request):
    app, plane, acct = _ctx(request)
    _thread(plane, tid)
    b = await _json(request)
    if b.get("n") not in (1, 2, 3) or b.get("answer") not in ("confirm", "carry_on", "go_live", "not_yet", "retry", "send_for_signature"):
        raise HTTPException(400, "Choose one of the answers on the card.")
    answers = dict(b["answers"]) if isinstance(b.get("answers"), dict) else {}
    if isinstance(b.get("to"), str):
        answers["to"] = b["to"]
    if isinstance(b.get("reuse"), dict):
        answers["reuse"] = b["reuse"]  # per brief figure: the figure to reuse, or null
    try:
        th = await run_in_threadpool(H.decide, app, plane, tid, b["n"], b["answer"], answers, acct)
    except ValueError as e:
        raise HTTPException(409, str(e)) from None
    return SO.decorate(app, plane, H.view(th), acct)


@router.post("/api/v3/threads/{tid}/discard")
async def discard(tid: str, request: Request):
    app, plane, acct = _ctx(request)
    _thread(plane, tid)
    reason = str((await _json(request)).get("reason") or "")
    try:
        return H.view(await run_in_threadpool(H.discard, app, plane, tid, reason, acct))
    except ValueError as e:
        raise HTTPException(409, str(e)) from None


@router.post("/api/v3/threads/{tid}/brief")
async def edit_brief(tid: str, request: Request):
    app, plane, acct = _ctx(request)
    _thread(plane, tid)
    b = await _json(request)
    if not isinstance(b.get("section"), str) or not isinstance(b.get("field"), str) or not str(b.get("value") or "").strip():
        raise HTTPException(400, "Write the new wording first.")
    try:
        return H.view(await run_in_threadpool(H.edit_brief, app, plane, tid, b, acct))
    except ValueError as e:
        raise HTTPException(409, str(e)) from None
    except H.Q as e:
        raise HTTPException(422, e.text) from None


@router.get("/api/v3/threads/{tid}/workbench")
def get_workbench(tid: str, request: Request):
    return H.workbench(_thread(_ctx(request)[1], tid))


@router.get("/api/v3/files")
def list_files(request: Request):
    app, plane, _ = _ctx(request)
    return {"files": H.scan(app, plane)}


@router.post("/api/v3/files")
async def post_file(request: Request):
    app, plane, _ = _ctx(request)
    if request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
        form = await _multipart(request)
        got = form.get("files") if isinstance(form, dict) else None
        if not got:
            raise HTTPException(400, "Please choose a file.")
    else:
        b = await _json(request)
        try:
            got = [(str(b["name"]), base64.b64decode(b["data"], validate=True))]
        except (KeyError, binascii.Error, ValueError):
            raise HTTPException(400, "Send the file as a name and its data.") from None
    for name, data in got:
        H.drop(plane, name, data)
    return {"files": H.scan(app, plane)}
