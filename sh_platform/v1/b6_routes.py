"""B2 routes: Span's build plan for a project (the shapes ui/src/v1/b6/api.ts expects).

- `GET /api/v1/build/projects` -> {projects: [{id, title, owner, stage: intent|build|live, plan_state|null, intent_signed}]}
- `GET /api/v1/build/p/{pid}/plan` -> the plan plus model_diff, per-table is_new, can {propose, approve, reject, run_sandbox, go_live, schedule},
  versions, pending changes, log. With no plan yet: {project_id, plan: null, state: null, can, ...}.
- `POST .../plan/propose` {model_change?} · `POST .../plan/approve` {version?} · `POST .../plan/reject` {reason, version?}
- `GET|POST .../chat` {text} -> {turns, pending} · `POST .../plan/changes/{cid}/accept|reject`
"""
import logging

import duckdb
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, PlainTextResponse

from sh_platform.build.agents.runtime import get_model
from sh_platform.profile.api import _plane
from sh_platform.v1 import b6_plan as B
from sh_platform.v1 import b6_run as R
from sh_platform.v1 import b6_schedule as SCH
from sh_platform.v1 import b6_span as S
from sh_platform.v1 import e0a_catalogue as E
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import p1_project as P1
from sh_platform.v1 import talk as T
from sh_platform.v1 import wh
from sh_platform.v1.i2_north import Refused
from sh_platform.v1.i2_routes import MAX_FILE_BODY, _decode, _json_body
from sh_platform.v1.seats import ARCHITECT, CONSUMER, DATA_ENGINEER, HEAD_OF_DATA, require_seat, seat_of

router = APIRouter()
log = logging.getLogger(__name__)
BUSY = {"error": "busy", "message": "The run could not start because a data file is busy. Try again in a minute."}
CODES = {400: "invalid", 403: "not_allowed", 404: "not_found", 409: "conflict"}
BASE = "/api/v1/build/p/{pid}"


async def _run(request: Request, fn):
    viewer = require_seat(request, CONSUMER)
    try:
        plane = _plane(request)
        return await run_in_threadpool(fn, plane, viewer)
    except (Refused, P1.Refused) as e:
        return JSONResponse({"error": CODES.get(e.status, "invalid"), "message": e.message}, status_code=e.status)
    except R.Refused as e:
        return JSONResponse({"error": CODES.get(e.status, "invalid"), "message": e.message}, status_code=e.status)
    except PermissionError as e:
        if e.errno is None:  # _plane: no company space for this sign-in
            return JSONResponse({"error": "forbidden", "message": "Your company space could not be opened. Please ask your administrator."}, status_code=403)
        log.warning("build call hit a busy file: %r", e)
        return JSONResponse(BUSY, status_code=503)
    except (OSError, wh.Busy, duckdb.IOException) as e:  # a data file in use (sharing violation, DuckDB lock)
        log.warning("build call hit a busy file: %r", e)
        return JSONResponse(BUSY, status_code=503)


async def _body(request: Request) -> dict:
    try:
        got = await request.json()
    except ValueError:
        got = None
    return got if isinstance(got, dict) else {}


def _gate(plane, viewer, pid: str, need: str) -> dict:
    return G1.require(plane, viewer, pid, need)[0]


def _model_diff(plane, plan: dict) -> dict | None:
    n = plan.get("model_changes")
    if not n:
        return None
    m = E.proposal(plane, int(n))
    cat = {t["name"]: t for t in E._cat(plane, int(n))["tables"]}
    d = m.get("diff") or {}
    return {"tables_added": [{"table": a["table"], "columns": [c["name"] for c in cat[a["table"]]["columns"]]} for a in d.get("tables_added", []) if a["table"] in cat],
            "columns_added": [{"table": a["table"], "column": a["column"], "type": a.get("type")} for a in d.get("columns_added", [])],
            "state": m["state"], "words": d.get("words", [])}


def _can(viewer, plan: dict | None, sow_ok: bool) -> dict:
    seats, st = seat_of(viewer), (plan or {}).get("state")
    mine = plan is not None and getattr(viewer, "account_id", None) == plan.get("proposed_by_id")
    return {"propose": DATA_ENGINEER in seats and sow_ok, "approve": HEAD_OF_DATA in seats and st == "proposed" and not mine,   # V6: the head of data approves the plan
            "reject": HEAD_OF_DATA in seats and st == "proposed", "run_sandbox": DATA_ENGINEER in seats and st in ("approved", "built", "live"),
            "go_live": ARCHITECT in seats and st in ("approved", "built"), "schedule": DATA_ENGINEER in seats and st in ("approved", "built", "live")}


def _view(plane, viewer, pid: str) -> dict:
    prj = P1.read(plane, pid)
    try:
        sow_ok = S.signed_sow(plane, prj) is not None
    except Refused:
        sow_ok = False
    plan = B.get(plane, pid)
    conv = S.conversation(plane, pid)
    base = {"project_id": pid, "title": prj.get("title"), "intent_id": prj.get("intent_id"), "intent_signed": sow_ok, "versions": B.versions(plane, pid), "can": _can(viewer, plan, sow_ok),
            "changes": [c for c in conv["changes"] if c["status"] == "pending"], "log": B.read_log(plane, pid)[-20:]}
    if plan is None:
        return {**base, "plan": None, "state": None}
    new = lambda t: t["layer"] != "silver" or E.layer_of(plane, t["name"]) is None
    return {**plan, **base, "tables": [{**t, "is_new": new(t)} for t in plan["tables"]], "model_diff": _model_diff(plane, plan)}


@router.get("/api/v1/build/projects")
async def projects(request: Request):
    def go(plane, v):
        rows = []
        for p in P1.all_projects(plane):
            s = G1.shown(plane, v, p)
            if s.get("locked") and s.get("access") != "preview":
                continue
            plan = B.get(plane, p["id"])
            stage = "live" if p["stage"] == "live" else "build" if p["stage"] in ("signed", "designed", "built") else "intent"
            rows.append({"id": p["id"], "intent_id": p.get("intent_id"), "title": s.get("title"), "owner": (p.get("people") or {}).get("raiser") or p.get("started_by"), "builder": (p.get("people") or {}).get("builder"), "stage": stage,
                         "plan_state": plan["state"] if plan else None, "updated_at": (plan or {}).get("proposed_at") or p.get("started_at"),
                         "intent_signed": any(a["kind"] == "intent" and a.get("state") == "signed" for a in p.get("artefacts") or [])})
        return {"projects": rows}
    return await _run(request, go)


@router.get(BASE + "/plan")
async def plan(request: Request, pid: str):
    return await _run(request, lambda plane, v: (_gate(plane, v, pid, "read"), _view(plane, v, pid))[1])


@router.post(BASE + "/plan/propose")
async def propose(request: Request, pid: str):
    body = await _body(request)

    def go(plane, v):
        _gate(plane, v, pid, "full")
        S.propose_plan(plane, v, pid, get_model(request.app.state, plane), body.get("model_change") if isinstance(body.get("model_change"), dict) else None)
        return _view(plane, v, pid)
    return await _run(request, go)


@router.post(BASE + "/plan/approve")
async def approve(request: Request, pid: str):
    body = await _body(request)

    def go(plane, v):
        _gate(plane, v, pid, "read")
        B.approve(plane, v, pid, body.get("version"), body.get("note") or "")
        from . import b11_builder  # V6: the builder starts at the approval, nobody has to open the page (never raises)
        b11_builder.on_approved(plane, pid)
        return _view(plane, v, pid)
    return await _run(request, go)


@router.post(BASE + "/plan/reject")
async def reject(request: Request, pid: str):
    body = await _body(request)

    def go(plane, v):
        _gate(plane, v, pid, "read")
        B.reject(plane, v, pid, body.get("reason"), body.get("version"))
        return _view(plane, v, pid)
    return await _run(request, go)


@router.get(BASE + "/chat")
async def get_chat(request: Request, pid: str):
    def go(plane, v):
        _gate(plane, v, pid, "read")
        c = S.conversation(plane, pid)
        return {"turns": c["turns"], "pending": [x for x in c["changes"] if x["status"] == "pending"]}
    return await _run(request, go)


@router.post(BASE + "/chat")
async def post_chat(request: Request, pid: str):
    body = await _body(request)

    def go(plane, v):
        try:
            _gate(plane, v, pid, "read")  # anyone who may see the project may ask; changes wait for the data team
        except P1.Refused:  # a project the person cannot open: say what can be said and who owns it, in words
            reply = T.span_company(plane, v, "", pid)
            tid = S.rules_trace(plane, v, "Span", "locked_project")
            return {"turns": [S._turn("person", v.name, str(body.get("text") or "")[:2000]), {**S._turn("span", "Span", reply), "trace_id": tid}],
                    "pending": [], "reply": reply, "trace_id": tid}
        return S.chat(plane, v, pid, body.get("text"), get_model(request.app.state, plane), body.get("files"))
    return await _run(request, go)


@router.post(BASE + "/chat/files")
async def post_chat_file(request: Request, pid: str):
    """{name, data (base64)} -> {name, path, kind}: a file for Span to read, kept for this project like North's. Anyone who may see the project may add one."""
    body = await _json_body(request, MAX_FILE_BODY)
    if isinstance(body, JSONResponse):
        return body

    def go(plane, v):
        _gate(plane, v, pid, "read")
        return S.attach(plane, v, pid, str(body.get("name") or ""), _decode(body.get("data")))
    return await _run(request, go)


@router.post("/api/v1/build/chat")
async def post_company_chat(request: Request):
    """Talk to Span outside any project: the agent's tool loop, kept as a short-term conversation; the short rules reply when the model is off."""
    body = await _body(request)
    text = str(body.get("text") or "").strip()[:2000]
    if not text:
        return JSONResponse({"error": "invalid", "message": "Write something to Span."}, status_code=400)
    return await _run(request, lambda plane, v: T.ask(plane, v, "span", text, body.get("project_id") if isinstance(body.get("project_id"), str) else None,
                                                      get_model(request.app.state, plane)))


@router.post(BASE + "/plan/changes/{cid}/accept")
async def accept(request: Request, pid: str, cid: str):
    def go(plane, v):
        _gate(plane, v, pid, "full")
        S.accept_change(plane, v, pid, cid)
        return _view(plane, v, pid)
    return await _run(request, go)


@router.post(BASE + "/plan/changes/{cid}/reject")
async def reject_change(request: Request, pid: str, cid: str):
    body = await _body(request)

    def go(plane, v):
        _gate(plane, v, pid, "full")
        S.reject_change(plane, v, pid, cid, body.get("reason") or "")
        return _view(plane, v, pid)
    return await _run(request, go)


# ---- B4: the Pipeline step (run, runs, schedule, Airflow file) ---------------------------------------------------------------------

def _seat(viewer, seat: str) -> None:
    if seat not in seat_of(viewer):
        raise Refused(403, "Only the " + ("head of data" if seat == ARCHITECT else "data engineer") + " can do this.")


def _builder_gate(plane, pid: str) -> None:
    """V6 review: once the builder (b11) holds a round that is not live, only its Go live (with the variance gate) takes the pack live."""
    from . import b11_builder
    rounds = b11_builder.load(plane, pid)["rounds"]
    if rounds and rounds[-1].get("state") != "live":
        raise R.Refused("The builder takes this pack live after its benchmark check. Use Go live in the builder above.", 409)


@router.post(BASE + "/run")
async def run_plan(request: Request, pid: str, mode: str = "sandbox"):
    def go(plane, v):
        _gate(plane, v, pid, "full")
        _seat(v, ARCHITECT if mode == "live" else DATA_ENGINEER)
        if mode == "live":
            _builder_gate(plane, pid)
        from sh_platform.jobs.handlers import run_pipeline  # W3: through the job queue
        run_pipeline(plane, pid, mode, v.name)
        return {**_view(plane, v, pid), "runs": R.runs(plane, pid)}
    return await _run(request, go)


@router.get(BASE + "/runs")
async def list_runs(request: Request, pid: str):
    return await _run(request, lambda plane, v: (_gate(plane, v, pid, "read"), {"runs": R.runs(plane, pid)})[1])


@router.put(BASE + "/schedule")
async def put_schedule(request: Request, pid: str):
    body = await _body(request)

    def go(plane, v):
        _gate(plane, v, pid, "full")
        _seat(v, DATA_ENGINEER)
        B.set_schedule(plane, pid, body, v.name)
        return _view(plane, v, pid)
    return await _run(request, go)


@router.get(BASE + "/airflow")
async def airflow(request: Request, pid: str):
    def go(plane, v):
        _gate(plane, v, pid, "read")
        return PlainTextResponse(SCH.airflow_dag(plane, pid), media_type="text/x-python",
                                 headers={"Content-Disposition": f'attachment; filename="{SCH.slug_of(plane, pid)}.py"'})
    return await _run(request, go)
