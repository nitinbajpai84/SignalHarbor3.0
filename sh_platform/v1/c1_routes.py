"""C1 KPI cards. GET /api/v1/consume: every signed SOW's KPIs with value, period and trend for loaded periods only.
GET /api/v1/consume/{iid}/{code}?period=YYYY-MM: the figure's run and rows. Read-only; every company role may read (the Consumer seat)."""
from fastapi import APIRouter, HTTPException, Request

from sh_platform.profile.api import _plane
from sh_platform.v1 import c1_cards
from sh_platform.v1 import g1_access as G1

router = APIRouter()


@router.get("/api/v1/consume")
def get_consume(request: Request) -> dict:
    from sh_platform.build import runner
    plane, viewer = runner._company(request)
    got = c1_cards.build(plane)
    return {**got, "intents": [i for i in got["intents"] if G1.can_read_intent(plane, viewer, i["intent_id"])]}  # G1: only projects the viewer may read


@router.get("/api/v1/consume/{iid}/{code}")
def get_figure(iid: str, code: str, period: str, request: Request) -> dict:
    out = c1_cards.figure(_plane(request), iid, code, period)
    if out is None:
        raise HTTPException(404, c1_cards.NA)
    return out
