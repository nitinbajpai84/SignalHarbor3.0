"""P1 routes: projects, their artefacts as documents of numbered lines, comments, export. Every seat may read and comment; the
addressee answers; the author or the signer resolves (checked in p1_project).

Who may read what is G1's `may_see_project` (full | read | preview | none); a locked project answers with its lock row.
- `GET /api/v1/projects` → {projects}
- `GET /api/v1/intents/{iid}/project` → the intent's project (made on first ask for an older intent)
- `GET /api/v1/projects/{pid}` → the project
- `GET /api/v1/projects/{pid}/artefacts/{kind}` → the document: sections, numbered lines, comments
- `GET /api/v1/projects/{pid}/artefacts/{kind}/export?format=docx|xlsx|md`
- `GET /api/v1/projects/{pid}/comments` → {comments};  `POST` {artefact, line_ref?, to, text} → the comment
- `POST /api/v1/projects/{pid}/comments/{cid}/answer` {text};  `POST …/resolve`
"""
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response

from sh_platform.profile.api import _plane
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import p1_project as P
from sh_platform.v1.seats import CONSUMER, require_seat

router = APIRouter()
BASE = "/api/v1/projects/{pid}"
CODES = {400: "invalid", 403: "not_allowed", 404: "not_found", 409: "conflict"}


async def _run(request: Request, fn, *args):
    viewer = require_seat(request, CONSUMER)
    try:
        plane = _plane(request)
        return await run_in_threadpool(fn, plane, viewer, *args)
    except P.Refused as e:
        return JSONResponse({"error": CODES.get(e.status, "invalid"), "message": e.message}, status_code=e.status)
    except PermissionError:
        return JSONResponse({"error": "forbidden", "message": "Your company space could not be opened. Please ask your administrator."}, status_code=403)


async def _body(request: Request) -> dict:
    try:
        got = await request.json()
    except ValueError:
        got = None
    return got if isinstance(got, dict) else {}


@router.get("/api/v1/projects")
async def list_projects(request: Request):
    def go(plane, v):  # a locked project shows as its preview (Internal) or not at all (Restricted)
        rows = [G1.shown(plane, v, p) for p in P.all_projects(plane)]
        return {"projects": [r for r in rows if not r.get("locked") or r["access"] == "preview"]}
    return await _run(request, go)


@router.get("/api/v1/intents/{iid}/project")
async def of_intent(request: Request, iid: str):
    def go(plane, v):
        got = P.project_of(plane, iid)
        if got is None:
            raise P.Refused(404, "This intent has no project yet.")
        return G1.shown(plane, v, got)
    return await _run(request, go)


@router.get(BASE)
async def get_project(request: Request, pid: str):
    return await _run(request, lambda plane, v: G1.shown(plane, v, P.read(plane, pid)))


@router.get(BASE + "/artefacts/{kind}")
async def get_artefact(request: Request, pid: str, kind: str):
    def go(plane, v):
        G1.require(plane, v, pid, "read")
        return {**P.document(plane, pid, kind), "me": v.name}
    return await _run(request, go)


@router.get(BASE + "/artefacts/{kind}/export")
async def export(request: Request, pid: str, kind: str, format: str = "md"):
    def go(plane, v):
        _, lvl = G1.require(plane, v, pid, "read")
        if not G1.export_allowed(lvl, kind, v.roles):
            raise P.Refused(403, "Your role does not export this document. You can read it here.")  # a1 and b3 refuse the same roles
        data, mime, name = P.export(plane, pid, kind, format)
        if lvl == "full":
            try:
                G1.add_file(plane, v, pid, name, data, "export")  # the project folder keeps what was exported
            except Exception:  # noqa: BLE001 - the download never waits on the folder
                pass
        return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})
    return await _run(request, go)


@router.get(BASE + "/comments")
async def list_comments(request: Request, pid: str):
    def go(plane, v):
        G1.require(plane, v, pid, "read")
        return {"comments": P.comments(plane, P.read(plane, pid)["id"])}
    return await _run(request, go)


@router.post(BASE + "/comments")
async def add_comment(request: Request, pid: str):
    b = await _body(request)

    def go(plane, v):
        G1.require(plane, v, pid, "read")  # 404 before anything is written
        return P.comment(plane, pid, b.get("artefact"), b.get("line_ref"), v.name, b.get("to"), b.get("text"))
    return await _run(request, go)


@router.post(BASE + "/comments/{cid}/answer")
async def answer(request: Request, pid: str, cid: str):
    b = await _body(request)
    def go(plane, v):
        G1.require(plane, v, pid, "read")  # S10: the person a comment is addressed to reads it, whatever their role
        return P.answer(plane, pid, cid, v.name, b.get("text"))
    return await _run(request, go)


@router.post(BASE + "/comments/{cid}/resolve")
async def resolve(request: Request, pid: str, cid: str):
    def go(plane, v):
        G1.require(plane, v, pid, "read")
        return P.resolve(plane, pid, cid, v.name)
    return await _run(request, go)
