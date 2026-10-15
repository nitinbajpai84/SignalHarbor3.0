"""R1 routes: the Testing / Real use mode and the cost panel.

GET  /api/v1/router/mode       {mode, by, at, can_flip} for every company role
POST /api/v1/router/mode       {mode: testing|real}; the decision maker only (company_admin, sponsor); the next message uses it
GET  /api/v1/router/costs?iid= {calls, tokens, by_tier, fast_share, estimated, rows} from context/model_costs.jsonl"""
from fastapi import APIRouter, Body, HTTPException, Request

from sh_platform.profile.api import _plane
from sh_platform.v1 import router as R
from sh_platform.v1.seats import CONSUMER, DECISION_MAKER, NO_SPACE, require_seat, seat_of, viewer_of

router = APIRouter()


def _open(request: Request):
    try:
        return _plane(request)
    except PermissionError:
        raise HTTPException(403, {"error": "forbidden", "message": NO_SPACE}) from None


@router.get("/api/v1/router/mode")
def get_mode(request: Request):
    viewer = viewer_of(request)
    return {**R.mode_of(_open(request)), "can_flip": CONSUMER in seat_of(viewer)}  # Nitin, 8 Oct: everyone may flip while testing; narrow to DECISION_MAKER before real use


@router.post("/api/v1/router/mode")
def post_mode(request: Request, body: dict = Body(...)):
    viewer = require_seat(request, CONSUMER)  # see can_flip
    if body.get("mode") not in R.MODES:
        raise HTTPException(400, {"error": "invalid", "message": "Choose Testing or Real use."})
    return {**R.set_mode(_open(request), body["mode"], viewer.name), "can_flip": True}


@router.get("/api/v1/router/costs")
def get_costs(request: Request, iid: str | None = None):
    viewer_of(request)
    return R.costs(_open(request), iid or None)
