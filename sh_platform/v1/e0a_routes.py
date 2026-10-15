"""E0a routes: the data model catalogue, its versions and change proposals.

- `GET /api/v1/model/catalogue` → {version, state, groups: [{name, tables: [{name, layer, note, columns}]}]};  `GET /api/v1/model/tables/{name}`
- `GET /api/v1/model/script?version=` → the DBML text;  `GET /api/v1/model/versions`;  `GET /api/v1/model/proposals`;  `GET /api/v1/model/proposals/{n}`
- `POST /api/v1/model/proposals` {dbml? | add_table? {name, group?, note?, columns} | add_column? {table, name, type, null?, note?}, note?}
- `POST /api/v1/model/proposals/{n}/approve` · `POST /api/v1/model/proposals/{n}/reject` {reason}
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import e0a_catalogue as E
from sh_platform.v1.i2_routes import _answer, _json_body
from sh_platform.v1.seats import viewer_of

router = APIRouter()


@router.get("/api/v1/model/catalogue")
def catalogue(request: Request):
    viewer_of(request)
    return _answer(lambda: E.catalogue_view(_plane(request)))


@router.get("/api/v1/model/layers")
def layers(request: Request):
    viewer_of(request)
    return _answer(lambda: E.layers_view(_plane(request)))


@router.get("/api/v1/model/projects/{pid}/tables")
def project_tables(pid: str, request: Request):
    viewer_of(request)
    return _answer(lambda: E.tables_for_project(_plane(request), pid))


@router.get("/api/v1/model/tables/{name}")
def table(name: str, request: Request):
    viewer_of(request)
    plane = _plane(request)
    return _answer(lambda: E.describe(plane, name) or JSONResponse({"error": "not_found", "message": "We could not find that table."}, status_code=404))


@router.get("/api/v1/model/script")
def script(request: Request, version: int = 0):
    viewer_of(request)
    try:
        return PlainTextResponse(E.script(_plane(request), version or None))
    except E.Refused as e:
        return JSONResponse({"error": "not_found", "message": e.message}, status_code=e.status)


@router.get("/api/v1/model/versions")
def versions(request: Request):
    viewer_of(request)
    return _answer(lambda: E.versions(_plane(request)))


@router.get("/api/v1/model/proposals")
def proposals(request: Request):
    viewer_of(request)
    return _answer(lambda: E.proposals(_plane(request)))


@router.get("/api/v1/model/proposals/{n}")
def one_proposal(n: int, request: Request):
    viewer_of(request)
    return _answer(lambda: E.proposal(_plane(request), n))


@router.post("/api/v1/model/proposals")
async def propose(request: Request):
    viewer = viewer_of(request)
    body = await _json_body(request, 512 * 1024)
    if isinstance(body, JSONResponse):
        return body
    return _answer(lambda: E.propose(_plane(request), viewer, dbml=body.get("dbml"), add_table=body.get("add_table"),
                                     add_column=body.get("add_column"), note=body.get("note") or ""))


@router.post("/api/v1/model/proposals/{n}/approve")
def approve(n: int, request: Request):
    viewer = viewer_of(request)
    return _answer(lambda: E.approve(_plane(request), viewer, n))


@router.post("/api/v1/model/proposals/{n}/reject")
async def reject(n: int, request: Request):
    viewer = viewer_of(request)
    body = await _json_body(request, 8192)
    return body if isinstance(body, JSONResponse) else _answer(lambda: E.reject(_plane(request), viewer, n, str(body.get("reason") or "")))
