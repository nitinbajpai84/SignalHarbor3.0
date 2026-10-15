"""FIXE2: the company's cycle date, the business "today" every screen and check of this company reads (wh.today).

- `GET /api/v1/cycle-date` -> {cycle_date: pinned day or null, today: the company's day, real_today, pinned, can_set}
- `PUT /api/v1/cycle-date` {cycle_date: "YYYY-MM-DD" | null}: the administrator or the head of data sets it; null returns the company to the real day.
Stored in the company's data plane (settings/demo_today.json, the existing demo-day setting), so two companies never share a day."""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import wh
from sh_platform.v1.seats import viewer_of

router = APIRouter()


def _may_set(viewer) -> bool:
    return bool({"company_admin", "head_of_data"} & set(getattr(viewer, "roles", ()) or ()))


def _view(plane, viewer) -> dict:
    pinned = wh.demo_today(plane)
    return {"cycle_date": pinned.isoformat() if pinned else None, "today": wh.today(plane).isoformat(),
            "real_today": datetime.now(timezone.utc).date().isoformat(), "pinned": pinned is not None, "can_set": _may_set(viewer)}


@router.get("/api/v1/cycle-date")
async def cycle_get(request: Request):
    viewer, plane = viewer_of(request), _plane(request)
    return _view(plane, viewer)


@router.put("/api/v1/cycle-date")
async def cycle_put(request: Request, body: dict = Body(default_factory=dict)):
    viewer, plane = viewer_of(request), _plane(request)
    if not _may_set(viewer):
        return JSONResponse({"error": "not_allowed", "message": "Only the administrator or the head of data can set the cycle date."}, status_code=403)
    raw = body.get("cycle_date")
    day = None
    if raw not in (None, ""):
        try:
            day = date.fromisoformat(str(raw))
        except ValueError:
            return JSONResponse({"error": "invalid", "message": "Write the cycle date like 2026-07-31."}, status_code=400)
        if not 2000 <= day.year <= 2100:
            return JSONResponse({"error": "invalid", "message": "Choose a date between 2000 and 2100."}, status_code=400)
    wh.set_demo_today(plane, day)
    return _view(plane, viewer)
