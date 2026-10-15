"""K11 attribution read path (Consume analytics tab).

GET /api/v1/attribution?portfolio=&code=&start=YYYY-MM&end=YYYY-MM   Brinson-Fachler per sleeve, contribution by fund, active weights, splits.
Nothing is calculated here; k11_attrib does it from records. Read only: asking never opens a case."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.v1 import k11_attrib
from sh_platform.v1.i2_north import Refused
from sh_platform.v1.k7_routes import _end, _month, _portfolio, _run

router = APIRouter()


def build(plane, viewer, portfolio: str, code: str, start: str, end: str) -> dict:
    pid, pcode = _portfolio(plane, viewer, portfolio)
    first, last = _month(start or end), _month(end or start)
    if last < first or (last.year - first.year) * 12 + last.month - first.month > 35:
        raise Refused(400, "Choose a period of up to 36 months, ending after it starts.")
    return k11_attrib.attribute(plane, viewer, pid, pcode, code, first, _end(last))


@router.get("/api/v1/attribution")
async def get_attribution(request: Request, portfolio: str = "", code: str = "", start: str = "", end: str = ""):
    if not portfolio or not code or not (start or end):
        return JSONResponse({"error": "invalid", "message": "Choose a portfolio, a benchmark and a month."}, status_code=400)
    return await _run(request, lambda p, v: build(p, v, portfolio, code, start, end))
