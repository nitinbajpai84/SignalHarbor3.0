"""C2 Offer card routes. Every working seat reads the offers; only the decision maker answers "We have it" (checked again here
through the seat helper so a widened yaml never lets anyone else write). Company and industry come from the session only."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from sh_platform.context_docs.api import _plain
from sh_platform.profile.api import _answer, _name, _plane
from sh_platform.v1 import c2_offers, seats
from sh_platform.v1 import g1_access as G1

router = APIRouter()


def _pack(request: Request):
    rec = request.app.state.entitlements.company(request.state.company_id) or {}
    industry = rec.get("industry")
    return request.app.state.packs.load(industry) if industry else None


def _refused(fn):
    try:
        return _answer(fn)
    except c2_offers.Refusal as e:
        return _plain(e.status, "refused", str(e))


def _gate(request: Request, iid) -> None:
    """G1: the offers read the intent's SoW; the intent is keyed `intent` here (or `intent_id` in a body), so the router-wide gate misses it."""
    from sh_platform.build import runner
    plane, viewer = runner._company(request)
    try:
        iid = c2_offers.pick_intent(plane, iid)  # no intent named: the newest one is the one that would be read
    except c2_offers.Refusal:
        return  # the handler gives its own 404
    if iid:
        G1.http_gate(plane, viewer, iid, "read")


@router.get("/api/v1/consume/offers")
def get_offers(request: Request, intent: str | None = None):
    _gate(request, intent)
    may = seats.DECISION_MAKER in seats.seat_of(request.state.roles or [])
    return _refused(lambda: {**c2_offers.offers(_plane(request), _pack(request), intent), "can_answer": may})


@router.post("/api/v1/consume/offers/{offer_id}/have")
async def post_have(request: Request, offer_id: str):
    try:
        seats.require_seat(request, seats.DECISION_MAKER)
    except HTTPException as e:
        return _plain(e.status_code, "not_allowed", e.detail["message"])
    try:
        body = await request.json()
    except ValueError:  # an empty body means the newest intent of work
        body = {}
    iid = body.get("intent_id") if isinstance(body, dict) else None
    if iid is not None and not isinstance(iid, str):
        return _plain(422, "refused", "Send the intent as text, or leave it out.")
    _gate(request, iid)
    plane, pack, name = _plane(request), _pack(request), _name(request)
    return await run_in_threadpool(_refused, lambda: c2_offers.have(plane, pack, iid, offer_id, name))
