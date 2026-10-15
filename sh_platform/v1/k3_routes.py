"""K3 routes: the Map centre's four tabs, read-only.

GET /api/v1/centre-map/flow         sources -> files -> bronze -> silver -> gold -> dashboards -> people, as nodes and edges
GET /api/v1/centre-map/processes    every signed intent's swim lane the person may open
GET /api/v1/centre-map/definitions  the agreed KPI meanings and their variants (K2)
GET /api/v1/centre-map/model        the data model by layer: tables, columns, row counts, what feeds what (k3_model)
GET /api/v1/centre-map/health       per source: late, stale, rejected loads, unverified values, open breaks (data team)
Data stays in the signed-in company's plane."""
from fastapi import APIRouter, Request

from sh_platform.v1 import k3_map as K
from sh_platform.v1 import k3_model as M
from sh_platform.v1.m1_routes import _open

router = APIRouter()


@router.get("/api/v1/centre-map/flow")
def get_flow(request: Request) -> dict:
    return K.flow(*_open(request))


@router.get("/api/v1/centre-map/processes")
def get_processes(request: Request) -> dict:
    return {"processes": K.processes(*_open(request))}


@router.get("/api/v1/centre-map/definitions")
def get_definitions(request: Request) -> dict:
    return {"concepts": K.definitions(*_open(request))}


@router.get("/api/v1/centre-map/health")
def get_health(request: Request) -> dict:
    return K.health(*_open(request))


@router.get("/api/v1/centre-map/model")
def get_model(request: Request) -> dict:
    return M.model(*_open(request))


# ---- v5: the company map as one living ontology (k3_onto) -----------------------------------------------------------------------------
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from sh_platform.v1 import k3_onto as O  # noqa: E402


class _Approve(BaseModel):
    ids: list[str] = Field(default_factory=list, max_length=200)


class _Reject(BaseModel):
    id: str
    reason: str = ""


def _refused(e: O.Refused) -> JSONResponse:
    code = {400: "invalid", 403: "not_allowed", 409: "conflict"}.get(e.status, "invalid")
    return JSONResponse({"error": code, "message": e.message}, status_code=e.status)


@router.get("/api/v1/centre-map/ontology")
def get_ontology(request: Request) -> dict:
    return O.build(*_open(request))


@router.get("/api/v1/centre-map/review")
def get_review(request: Request) -> dict:
    return O.review(*_open(request))


@router.post("/api/v1/centre-map/review/approve")
def post_approve(body: _Approve, request: Request):
    try:
        return O.approve(*_open(request), body.ids)
    except O.Refused as e:
        return _refused(e)


@router.post("/api/v1/centre-map/review/reject")
def post_reject(body: _Reject, request: Request):
    try:
        return O.reject(*_open(request), body.id, body.reason)
    except O.Refused as e:
        return _refused(e)
