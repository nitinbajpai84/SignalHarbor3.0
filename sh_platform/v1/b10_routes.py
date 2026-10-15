"""V6 b10 routes: the Architecture step (read before asking, the few questions, samples, the design pack, its approval, the plan drawn from it).

All under `/api/v1/build/p/{pid}/architecture/`. Reads: anyone who may see the project. Writes: the data team seat (engineer); approval: the head of
data seat, never the person who made the version (checked again in b10_pack)."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.build.agents.runtime import get_model
from sh_platform.v1 import b10_pack as K
from sh_platform.v1 import p1_project as P1
from sh_platform.v1.b6_routes import _body, _gate, _run
from sh_platform.v1.i2_north import Refused
from sh_platform.v1.i2_routes import MAX_FILE_BODY, _decode, _json_body

router = APIRouter()
BASE = "/api/v1/build/p/{pid}/architecture"


def _strs(body: dict) -> dict:
    return {k: x for k, x in body.items() if isinstance(x, str) and k != "note"}


@router.get(BASE + "/summary")
async def summary(request: Request, pid: str):
    return await _run(request, lambda plane, v: (_gate(plane, v, pid, "read"), K.summary(plane, v, pid))[1])


@router.get(BASE + "/questions")
async def questions(request: Request, pid: str):
    return await _run(request, lambda plane, v: (_gate(plane, v, pid, "read"), K.questions(plane, v, pid))[1])


@router.post(BASE + "/questions/accept-all")
async def accept_all(request: Request, pid: str):
    return await _run(request, lambda plane, v: (_gate(plane, v, pid, "full"), K.accept_all(plane, v, pid))[1])


@router.post(BASE + "/questions/{qid}")
async def answer(request: Request, pid: str, qid: str):
    body = await _body(request)
    return await _run(request, lambda plane, v: (_gate(plane, v, pid, "full"), K.answer(plane, v, pid, qid, body.get("value")))[1])


@router.post(BASE + "/systems/confirm")
async def confirm(request: Request, pid: str):
    body = await _body(request)
    ids = [x for x in body.get("ids") or [] if isinstance(x, str)] if isinstance(body.get("ids"), list) else []
    return await _run(request, lambda plane, v: (_gate(plane, v, pid, "full"), K.confirm_systems(plane, v, pid, ids))[1])


@router.put(BASE + "/systems/{sid}")
async def correct(request: Request, pid: str, sid: str):
    """A value that differs from the intent's: the intent's system map and the pack change together."""
    body = await _body(request)

    def go(plane, v):
        _gate(plane, v, pid, "full")
        if K.get(plane, pid) is not None:
            K.edit(plane, v, pid, "system", sid, _strs(body), str(body.get("note") or ""))
        else:
            K.correct_system(plane, v, P1.read(plane, pid)["intent_id"], sid, _strs(body))
        return K.summary(plane, v, pid)
    return await _run(request, go)


@router.post(BASE + "/samples/{sid}/table")
async def sample_table(request: Request, pid: str, sid: str):
    body = await _json_body(request, MAX_FILE_BODY)
    if isinstance(body, JSONResponse):
        return body
    return await _run(request, lambda plane, v: (_gate(plane, v, pid, "full"), K.sample_table(plane, v, pid, sid, str(body.get("name") or ""), _decode(body.get("data"))))[1])


@router.post(BASE + "/samples/{sid}/pdf")
async def sample_pdf(request: Request, pid: str, sid: str):
    body = await _json_body(request, MAX_FILE_BODY)
    if isinstance(body, JSONResponse):
        return body
    return await _run(request, lambda plane, v: (_gate(plane, v, pid, "full"), K.sample_pdf(plane, v, pid, sid, str(body.get("name") or ""), _decode(body.get("data"))))[1])


@router.get(BASE + "/samples/{sid}/lines")
async def lines(request: Request, pid: str, sid: str):
    return await _run(request, lambda plane, v: (_gate(plane, v, pid, "read"), {"lines": K.sample_lines(plane, v, pid, sid)})[1])


@router.post(BASE + "/samples/{sid}/mark")
async def mark(request: Request, pid: str, sid: str):
    body = await _body(request)
    return await _run(request, lambda plane, v: (_gate(plane, v, pid, "full"),
                                                 K.mark_field(plane, v, pid, sid, body.get("line"), str(body.get("name") or ""), str(body.get("format") or "text")))[1])


@router.get(BASE + "/pack")
async def get_pack(request: Request, pid: str, version: int | None = None):
    return await _run(request, lambda plane, v: (_gate(plane, v, pid, "read"), K.view(plane, v, pid, version))[1])


@router.post(BASE + "/pack/generate")
async def generate(request: Request, pid: str):
    def go(plane, v):
        _gate(plane, v, pid, "full")
        K.generate(plane, v, pid, get_model(request.app.state, plane))
        return K.view(plane, v, pid)
    return await _run(request, go)


@router.put(BASE + "/pack/edit")
async def edit(request: Request, pid: str):
    body = await _body(request)

    def go(plane, v):
        _gate(plane, v, pid, "full")
        if not isinstance(body.get("changes"), dict):
            raise Refused(400, "Say what to change.")
        K.edit(plane, v, pid, str(body.get("section") or ""), str(body.get("key") or ""), body["changes"], str(body.get("note") or ""),
               body.get("version") if isinstance(body.get("version"), int) else None)
        return K.view(plane, v, pid)
    return await _run(request, go)


@router.post(BASE + "/pack/submit")
async def submit(request: Request, pid: str):
    def go(plane, v):
        _gate(plane, v, pid, "full")
        K.submit(plane, v, pid)
        return K.view(plane, v, pid)
    return await _run(request, go)


@router.post(BASE + "/pack/approve")
async def approve(request: Request, pid: str):
    body = await _body(request)

    def go(plane, v):
        _gate(plane, v, pid, "read")
        K.approve(plane, v, pid, body.get("version") if isinstance(body.get("version"), int) else None, str(body.get("note") or ""))
        return K.view(plane, v, pid)
    return await _run(request, go)


@router.post(BASE + "/pack/reject")
async def reject(request: Request, pid: str):
    body = await _body(request)

    def go(plane, v):
        _gate(plane, v, pid, "read")
        K.reject(plane, v, pid, str(body.get("reason") or ""))
        return K.view(plane, v, pid)
    return await _run(request, go)


@router.get(BASE + "/pack/diff")
async def diff(request: Request, pid: str, a: int, b: int):
    return await _run(request, lambda plane, v: (_gate(plane, v, pid, "read"), K.diff(plane, pid, a, b))[1])


@router.post(BASE + "/pack/plan")
async def to_plan(request: Request, pid: str):
    def go(plane, v):
        _gate(plane, v, pid, "full")
        plan = K.apply_to_plan(plane, v, pid, get_model(request.app.state, plane))
        return {**K.view(plane, v, pid), "plan_version": plan["version"]}
    return await _run(request, go)


@router.post(BASE + "/pack/plan/approve")
async def approve_plan(request: Request, pid: str):
    """FIXC: the head of data approves the build plan drawn from the approved pack when the one-step approval could not (a retry)."""
    def go(plane, v):
        _gate(plane, v, pid, "read")
        K.approve_plan(plane, v, pid)
        return K.view(plane, v, pid)
    return await _run(request, go)
