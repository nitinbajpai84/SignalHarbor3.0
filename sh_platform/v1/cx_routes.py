"""C1 routes: Consume over a project's gold tables. Logic: cx_dash (dashboards, SQL checks, tiles), cx_lumen (the agent).

- `GET  /api/v1/consume/p/{pid}/tables` -> the project's gold tables with columns and row counts
- `GET|POST /api/v1/consume/p/{pid}/dashboards` (POST {title, refresh?}) ; `GET /dashboards/{id}`
- `POST /dashboards/{id}/ask` {text} -> {reply, proposals: [], dashboard_id, link?}: Lumen answers a question about what is shown; a request to build or change gets
  "Dashboards are built in Build > Dashboard studio" (OP1). `POST /dashboards` and `POST .../tiles/{tid}/accept|reject` refuse with 409 and the same pointer.
- `GET .../tiles/{tid}/data` ; `GET .../tiles/{tid}/why` (-> {answer, evidence, ..., trace_id})
- `GET|PUT /dashboards/{id}/audience` {audience: [user or group ids, names or emails], refresh?} -> {audience, refresh}; a share also makes the C3 cards
- `GET /api/v1/consume/p/{pid}/people` -> {people: [{id, name, role}]} for the audience picker
- `GET /api/v1/consume/shared` -> {dashboards: [shared with the person, not their own], brief: latest issued report or null, company: [published and marked company-wide]} (SW1, DS1)

DS1: Consume reads the published version of a dashboard only (cx_dash.get_published); drafts are made and approved in the Build studio (b7_routes).
- `GET /api/v1/consume/dashboards/{did}/view` -> the dashboard without a project id (the read-only link)

OP1: Consume shows published dashboards and answers questions; dashboards are made and changed in the studio (b7_routes), where Lumen's conversation lives."""
import logging
import time

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import cx_lumen as L
from sh_platform.v1 import b7_studio as S
from sh_platform.v1 import cx_share, e6_trace
from sh_platform.v1 import talk as T
from sh_platform.v1.p1_project import Refused
from sh_platform.v1.seats import viewer_of

log = logging.getLogger(__name__)
router = APIRouter()
BASE = "/api/v1/consume/p/{pid}"
DASH = BASE + "/dashboards/{did}"
CODES = {400: "invalid", 403: "not_allowed", 404: "not_found", 409: "conflict"}


def pointer(viewer, pid: str | None) -> dict:
    """What Lumen says in Consume to a request to build or change a dashboard: where that is done, and a link for people who may build there."""
    if pid and S.is_maker(viewer):
        return {"reply": S.POINTER + " Open the studio for this project to build or change it.", "link": f"/centre/build/p/{pid}/studio"}
    return {"reply": S.POINTER + " Ask the project's analyst to build or change it.", "link": None}


def _refuse(request: Request, pid: str):
    """A Consume route that used to build: it now says where building is done (409)."""
    p = pointer(viewer_of(request), pid)
    return JSONResponse({"error": "conflict", "message": p["reply"], "link": p["link"]}, status_code=409)


def _run(request: Request, fn):
    viewer, plane = viewer_of(request), _plane(request)
    try:
        return JSONResponse(D.jsonable(fn(plane, viewer)))
    except Refused as e:
        return JSONResponse({"error": CODES.get(e.status, "failed"), "message": e.message}, status_code=e.status)
    except PermissionError:
        return JSONResponse({"error": "not_allowed", "message": "You do not have access to this."}, status_code=403)


@router.post("/api/v1/consume/chat")
def company_chat(request: Request, body: dict = Body(default_factory=dict)):
    """Talk to Lumen outside any project: the tables and dashboards of the projects the person may read, in words, through Lumen's tool loop; the short rules reply when the model is off."""
    text = str(body.get("text") or "").strip()[:2000]
    if not text:
        return JSONResponse({"error": "invalid", "message": "Write something to Lumen."}, status_code=400)
    pid = body.get("project_id") if isinstance(body.get("project_id"), str) else None
    if L._wants_tile(text, {}) and not L.is_question(text):  # EVT-T14: the pointer has a trace like any answer
        return _run(request, lambda p, v: L.rules_turn(p, v, None, None, text, pointer(v, pid) | {"rules_only": True}, "build_pointer"))
    return _run(request, lambda p, v: T.ask(p, v, "lumen", text, pid))


@router.get("/api/v1/consume/shared")
def shared(request: Request):
    return _run(request, lambda p, v: {"dashboards": D.shared_with(p, v), "brief": D.latest_brief(p, v), "company": D.company_reports(p, v)})


@router.get(BASE + "/tables")
def tables(request: Request, pid: str):
    return _run(request, lambda p, v: {"tables": D.gold_tables(p, pid)})


@router.get(BASE + "/people")
def people(request: Request, pid: str):
    return _run(request, lambda p, v: {"people": D.people(p, v)})


@router.get("/api/v1/consume/dashboards/{did}/view")
def dashboard_by_id(request: Request, did: str):
    return _run(request, lambda p, v: (lambda r: r | {"audience_people": D.audience_view(p, r)})(D.get_published(p, v, _adopted(p, D.find_pid(p, did)), did)))


@router.get("/api/v1/consume/dashboards/{did}/refresh")
def dashboard_refresh(request: Request, did: str):
    """The header line of a published dashboard: when its project's pipeline last refreshed it and runs next, with a warning when a run failed or a source is late (DS1)."""
    from sh_platform.v1 import b7_studio
    def go(p, v):
        pid = D.find_pid(p, did)
        D.get_published(p, v, pid, did)
        return b7_studio.refresh_status(p, pid)
    return _run(request, go)


def _adopted(plane, pid: str) -> str:
    S.adopt(plane, pid)  # dashboards started in Consume before OP1 are studio drafts now, so they are not listed here
    return pid


@router.get(BASE + "/dashboards")
def dashboards(request: Request, pid: str):
    return _run(request, lambda p, v: {"dashboards": D.list_for(p, v, _adopted(p, pid))})


@router.post(BASE + "/dashboards")
def post_dashboard(request: Request, pid: str, body: dict = Body(default_factory=dict)):
    return _refuse(request, pid)


@router.get(DASH)
def dashboard(request: Request, pid: str, did: str):
    # NU-22: the person's own talk with Lumen on this dashboard comes with it, so a reload shows the conversation
    return _run(request, lambda p, v: (lambda r: r | {"audience_people": D.audience_view(p, r), "talk": L.talk(p, v, pid, did)})(D.get_published(p, v, _adopted(p, pid), did)))


@router.post(DASH + "/ask")
def ask(request: Request, pid: str, did: str, body: dict = Body(default_factory=dict)):
    """{text}: a question about what this dashboard shows is answered by Lumen; anything else (build, change, a picture) is pointed to the studio.
    {new_talk: true} starts a fresh talk (H1-07) and needs no text."""
    def go(p, v):
        row = T.G1.shown(p, v, T.P1.read(p, pid))
        if row.get("locked"):  # a project the person cannot open: say what can be said and who owns it
            return {"reply": T.locked_words(row), "proposals": []}
        D.get_published(p, v, _adopted(p, pid), did)  # only a published dashboard the person may open
        if body.get("new_talk") is True:
            return L.new_talk(p, v, pid, did)
        text = str(body.get("text") or "").strip()[:2000]
        if not text:
            raise Refused(400, "Ask Lumen about the figures you see.")
        # lumen-memory-c1-02: only a request to build or change (or a picture) gets the studio pointer; a statement or a decision is talk,
        # answered by Lumen's loop and kept in memory. EVT-T14, lumen-memory-c1-07: the pointer turn has a trace and is kept too.
        if body.get("picture") or (not L.is_question(text) and L._wants_tile(text, L.M.parse_style(text))):
            return L.rules_turn(p, v, pid, did, text, pointer(v, pid) | {"proposals": [], "dashboard_id": did}, "build_pointer")
        return L.ask(p, v, pid, did, text, talk_only=True)
    return _run(request, go)


@router.post(DASH + "/tiles/{tid}/accept")
def accept(request: Request, pid: str, did: str, tid: str):
    return _refuse(request, pid)


@router.post(DASH + "/tiles/{tid}/reject")
def reject(request: Request, pid: str, did: str, tid: str):
    return _refuse(request, pid)


@router.get(DASH + "/tiles/{tid}/data")
def tile_data(request: Request, pid: str, did: str, tid: str):
    return _run(request, lambda p, v: D.tile_data(p, v, pid, did, tid, published=True))


@router.get(DASH + "/tiles/{tid}/why")
def why(request: Request, pid: str, did: str, tid: str):
    def go(p, v):
        D._tile(D.get_published(p, v, pid, did), tid)  # only a published tile can be explained to a reader
        if not L.model_off():  # LQ-9: worded by Lumen's loop with context, on the program's figures
            return L.why_tile(p, v, pid, did, tid)
        t0 = time.monotonic()
        with e6_trace.trace(e6_trace.turn_trace_id(p, v, "lumen")) as trace_id:  # A14: the Why answer has a trace like a chat turn
            out = L.explain(p, v, pid, did, tid)
            L._rules_trace(p, trace_id, None, "why_tile", int((time.monotonic() - t0) * 1000))
        return out | {"trace_id": trace_id}
    return _run(request, go)


@router.get(DASH + "/audience")
def get_audience(request: Request, pid: str, did: str):
    return _run(request, lambda p, v: (lambda r: {"audience": D.audience_view(p, r), "refresh": r["refresh"]})(D.get(p, v, pid, did)))


@router.put(DASH + "/audience")
def put_audience(request: Request, pid: str, did: str, body: dict = Body(default_factory=dict)):
    def go(p, v):
        r = D.set_audience(p, v, pid, did, body.get("audience") or [], body.get("refresh"))
        try:  # a card failure never undoes a share
            cx_share.notify(p, pid, did, "shared", token="audience")
        except Exception:  # noqa: BLE001
            log.warning("the share cards could not be made", exc_info=True)
        return {"audience": D.audience_view(p, r), "refresh": r["refresh"]}
    return _run(request, go)
