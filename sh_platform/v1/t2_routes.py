"""T2 routes: the ticket centre.

- `GET /api/v1/tickets?project=&stage=&assignee=&raised_by=&state=&priority=` (assignee and raised_by accept "me"; state accepts "active") → {tickets, stages}
- `POST /api/v1/tickets` {title, body?, project?, stage?, priority?, assigned_to?, due?, links?} → the ticket
- `GET /api/v1/tickets/people` → names a ticket can go to
- `GET /api/v1/tickets/{id}` → the ticket with its links (locked ones show the preview) and its audit log in words
- `POST /api/v1/tickets/{id}/delegate` {to, note?} · `/comment` {text} · `/state` {state, note?} · `/link` {kind, ref} · `/work` (an agent's ticket)
- `GET /api/v1/tickets/{id}/log.csv` → the audit log as a spreadsheet file
Logic and visibility: t2_tickets."""
from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import Response

from sh_platform.profile.api import _plane
from sh_platform.v1 import t2_tickets as T
from sh_platform.v1.seats import NO_SPACE, viewer_of

router = APIRouter()
BASE = "/api/v1/tickets"


def _run(request: Request, fn, *args, **kw):
    viewer = viewer_of(request)
    try:
        plane = _plane(request)
        return fn(plane, viewer, *args, **kw)
    except PermissionError:
        raise HTTPException(403, {"error": "forbidden", "message": NO_SPACE}) from None
    except T.Refused as e:
        raise HTTPException(e.status, {"error": "not_allowed", "message": e.message} if e.status == 403 else e.message) from None


@router.get(BASE)
def list_tickets(request: Request, project: str = "", stage: str = "", assignee: str = "", raised_by: str = "", state: str = "", priority: str = ""):
    return _run(request, lambda p, v: T.listing(p, v, project=project or None, stage=stage or None, assignee=assignee or None,
                                               raised_by=raised_by or None, state=state or None, priority=priority or None))


@router.post(BASE)
def post_ticket(request: Request, body: dict = Body(default_factory=dict)):
    return _run(request, lambda p, v: T.detail(p, v, T.start(p, v, body)["id"]))


@router.get(BASE + "/people")
def get_people(request: Request):
    return _run(request, lambda p, v: {"people": T.people(p), "agents": T.AGENTS})


@router.get(BASE + "/{tid}")
def get_ticket(request: Request, tid: str):
    return _run(request, lambda p, v: T.detail(p, v, tid))


def _do(request: Request, tid: str, fn):
    return _run(request, lambda p, v: (fn(p, v), T.detail(p, v, tid))[1])


@router.post(BASE + "/{tid}/delegate")
def post_delegate(request: Request, tid: str, body: dict = Body(default_factory=dict)):
    return _do(request, tid, lambda p, v: T.reassign(p, v, tid, body.get("to"), body.get("note") or ""))


@router.post(BASE + "/{tid}/comment")
def post_comment(request: Request, tid: str, body: dict = Body(default_factory=dict)):
    return _do(request, tid, lambda p, v: T.say(p, v, tid, body.get("text")))


@router.post(BASE + "/{tid}/state")
def post_state(request: Request, tid: str, body: dict = Body(default_factory=dict)):
    return _do(request, tid, lambda p, v: T.set_state(p, v, tid, str(body.get("state")), body.get("note") or ""))


@router.post(BASE + "/{tid}/link")
def post_link(request: Request, tid: str, body: dict = Body(default_factory=dict)):
    return _do(request, tid, lambda p, v: T.link(p, v, tid, str(body.get("kind")), str(body.get("ref") or "")))


@router.post(BASE + "/{tid}/work")
def post_work(request: Request, tid: str):
    return _do(request, tid, lambda p, v: T.work(p, v, tid))


@router.get(BASE + "/{tid}/log.csv")
def get_log(request: Request, tid: str):
    csv_text = _run(request, lambda p, v: (T._checked(p, v, tid), T.log_csv(T.get(p, tid)))[1])
    return Response(csv_text, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{tid}-audit-log.csv"'})
