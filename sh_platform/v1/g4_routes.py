"""G4 Deviations: GET /api/v1/build/{iid}/deviations lists them; POST asks the approver for one (Flow, or the engineer on its behalf) with
{summary, about, before, after, why, effect, effect_labels, change, mapping_row, drop_sheet_row, sheet_row, sheet_change, business_definition};
POST …/{did}/make re-runs an approved change that is not yet made (engineer); POST …/{did}/decide {decision: "approved"|"not approved", reason} is the approver's answer (the same as answering the approval comment).
A change that keeps the signed design is refused with the sentence "Flow runs the load again without asking". Logic: g4_deviations."""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Request

from sh_platform.build import runner
from sh_platform.v1 import g4_deviations as G4
from sh_platform.v1 import p1_project as P1
from sh_platform.v1.b4_load import IID
from sh_platform.v1.seats import DATA_ENGINEER, require_seat

router = APIRouter()
BASE = "/api/v1/build/{iid}/deviations"
FIELDS = ("summary", "about", "before", "after", "why", "effect", "effect_labels", "change", "mapping_row", "drop_sheet_row", "sheet_row",
          "sheet_change", "business_definition")


def _iid(iid: str) -> str:
    if not IID.fullmatch(iid):
        raise HTTPException(404, "There is no such intent.")
    return iid


def _run(fn, *a, **k):
    try:
        return fn(*a, **k)
    except P1.Refused as e:
        raise HTTPException(e.status, {"error": "not_allowed", "message": e.message} if e.status == 403 else e.message) from None


@router.get(BASE)
def get_deviations(request: Request, iid: str):
    plane, _ = runner._company(request)
    return G4.view(plane, _iid(iid))


@router.post(BASE)
def post_deviation(request: Request, iid: str, body: dict = Body(default_factory=dict)):
    plane, viewer = runner._company(request)
    got = {k: body.get(k) for k in FIELDS if k in body}
    for k in ("summary", "about", "before", "after", "why"):
        got[k] = str(got.get(k) or "").strip()
    if not (got["summary"] and got["after"] and got["why"]):
        raise HTTPException(400, "Say what would change, to what, and why.")
    got["effect"] = [str(x) for x in got.get("effect") or []]
    return {"deviation": _run(G4.propose, plane, _iid(iid), **got, by=viewer.name)}


@router.post(BASE + "/{did}/decide")
def post_decide(request: Request, iid: str, did: str, body: dict = Body(default_factory=dict)):
    plane, viewer = runner._company(request)
    dev = next((d for d in G4.read(plane, _iid(iid)) if d["id"] == did), None)
    ask = next((a for a in (dev or {}).get("asks") or [] if a["name"] == viewer.name), None)
    if dev is None:
        raise HTTPException(404, "There is no such request.")
    if ask is None:
        raise HTTPException(403, {"error": "not_allowed", "message": f"Only {' and '.join(a['name'] for a in dev['asks'])} can answer this request."})
    _run(G4.check_answerer, plane, iid, did, viewer.name)
    text = str(body.get("decision") or "").strip()
    if str(body.get("reason") or "").strip():
        text += f": {str(body['reason']).strip()}"
    pid = P1.project_of(plane, iid)["id"]
    _run(P1.answer, plane, pid, ask["cid"], viewer.name, text)
    return G4.view(plane, iid)


@router.post(BASE + "/{did}/make")
def post_make(request: Request, iid: str, did: str):
    """"Make it now": the engineer re-runs the implementation of an approved change that could not be made."""
    require_seat(request, DATA_ENGINEER)
    plane, viewer = runner._company(request)
    _run(G4.make_now, plane, _iid(iid), did, viewer.name)
    return G4.view(plane, iid)
