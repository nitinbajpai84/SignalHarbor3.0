"""K2 routes: the company map's concepts and definitions, merge proposals a person confirms, the collision fact, the person's choice,
and "Suggest a change" (a comment of kind `suggestion` to the definition's owner, accepted or declined by the owner).

GET  /api/v1/map/concepts                       every concept the viewer may see, with variants and the one-line difference
GET  /api/v1/map/concepts/{concept_id}          one concept
GET  /api/v1/map/proposals                      open merge proposals
POST /api/v1/map/proposals/{pid}                {confirm: bool, note}: a person settles a merge
GET  /api/v1/map/collision?kpi=&iid=            the existing definitions for a KPI name, or {"fact": null}
POST /api/v1/map/choice                         {iid, kpi, choice, concept?, variant_of?, reason?}: concept | variant_of | new
POST /api/v1/map/suggestions                    {node, kind, text, value?, field?, other?}
GET  /api/v1/map/suggestions                    the ones addressed to the viewer or made by them
POST /api/v1/map/suggestions/{cid}/accept       the owner accepts: a new version of the definition
POST /api/v1/map/suggestions/{cid}/decline      {reason}: the owner declines
GET /api/v1/map/ask?q= is M1's route; it also returns `concepts` from K2.
Data stays in the signed-in company's plane: every path comes from the request's plane."""
from fastapi import APIRouter, Body, HTTPException, Request

from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import k2_map as K
from sh_platform.v1.m1_routes import _open

router = APIRouter()


def _run(fn):
    try:
        return fn()
    except K.K2Refused as e:
        raise HTTPException(e.status, e.message) from None
    except K.P.Refused as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/api/v1/map/concepts")
def get_concepts(request: Request) -> dict:
    plane, viewer = _open(request)
    return {"concepts": K.concepts(plane, viewer)}


@router.get("/api/v1/map/concepts/{concept_id}")
def get_concept(request: Request, concept_id: str) -> dict:
    plane, viewer = _open(request)
    return _run(lambda: K.concept(plane, viewer, concept_id))


@router.get("/api/v1/map/proposals")
def get_proposals(request: Request) -> dict:
    plane, viewer = _open(request)
    return {"proposals": K.proposals(plane, viewer)}


@router.post("/api/v1/map/proposals/{pid}")
def post_proposal(request: Request, pid: str, body: dict = Body(...)) -> dict:
    plane, viewer = _open(request)
    return _run(lambda: K.decide_proposal(plane, viewer, pid, bool(body.get("confirm")), str(body.get("note") or "")))


@router.get("/api/v1/map/collision")
def get_collision(request: Request, kpi: str = "", iid: str = "") -> dict:
    plane, viewer = _open(request)
    return {"fact": K.collision_fact(plane, viewer, kpi[:200], iid or None)}


@router.post("/api/v1/map/choice")
def post_choice(request: Request, body: dict = Body(...)) -> dict:
    plane, viewer = _open(request)
    iid = str(body.get("iid") or "")

    def allowed() -> None:  # a real intent of work, and only the team of its project says what its KPI is
        rec = K.P.project_of(plane, iid)
        if rec is None:
            raise K.K2Refused(404, "There is no such intent of work.")
        G1.require(plane, viewer, rec["id"], "full")
    _run(allowed)
    return _run(lambda: K.record_choice(plane, iid, str(body.get("kpi") or ""), {**body, "choice": body.get("choice"), "by": viewer.name}))


@router.post("/api/v1/map/suggestions")
def post_suggestion(request: Request, body: dict = Body(...)) -> dict:
    plane, viewer = _open(request)
    return _run(lambda: K.suggest(plane, viewer, str(body.get("node") or ""), str(body.get("kind") or "other"), str(body.get("text") or ""),
                                  str(body.get("value") or ""), str(body.get("field") or "definition"), str(body.get("other") or "")))


@router.get("/api/v1/map/suggestions")
def get_suggestions(request: Request) -> dict:
    plane, viewer = _open(request)
    return {"suggestions": K.suggestions(plane, viewer)}


@router.post("/api/v1/map/suggestions/{cid}/accept")
def post_accept(request: Request, cid: str) -> dict:
    plane, viewer = _open(request)
    return _run(lambda: K.answer_suggestion(plane, viewer, cid, True))


@router.post("/api/v1/map/suggestions/{cid}/decline")
def post_decline(request: Request, cid: str, body: dict = Body(default={})) -> dict:
    plane, viewer = _open(request)
    return _run(lambda: K.answer_suggestion(plane, viewer, cid, False, str(body.get("reason") or "")))
