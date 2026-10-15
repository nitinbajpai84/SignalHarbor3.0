"""P3 the Build Centre entry. The builder is recorded on the P1 project record (`people.builder`, via p1_project).

- `GET /api/v1/build/waiting` -> {waiting: [{intent_id, title, signed_by, signed_at, pid}], in_build: [{intent_id, title, builder, stage, pid}]}:
  signed intents of work nobody has picked up, and the work already in build.
- `POST /api/v1/build/pickup/{iid}` -> {intent_id, builder, pid}. Architect seat only; a second pick-up is refused (409).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from sh_platform.jsonfile import lock_for
from sh_platform.profile.api import _plane
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import p1_project as P
from sh_platform.v1.c1_cards import IID, signed_sows
from sh_platform.v1.seats import ARCHITECT, require_seat, viewer_of

router = APIRouter()


def _held(plane, iid: str) -> tuple[str | None, dict]:
    """(builder, project) for a signed intent; P1 makes the project for an intent started before projects existed."""
    prj = P.project_of(plane, iid) or {}
    return (prj.get("people") or {}).get("builder"), prj


def waiting(plane, viewer=None) -> dict:
    """G1: with a viewer, a Restricted project the person may not see is left out, and an Internal one shows its title only."""
    out = {"waiting": [], "in_build": []}
    for sow in signed_sows(plane):
        iid = sow["intent_id"]
        builder, prj = _held(plane, iid)
        if viewer is not None and prj and G1.level(plane, viewer, prj) == "none":
            continue
        line = {"intent_id": iid, "title": sow.get("title") or prj.get("title") or iid, "pid": prj.get("id")}
        if builder:
            out["in_build"].append({**line, "builder": builder, "stage": prj.get("stage") or "signed"})
        else:
            sig = sow.get("signature") or {}
            out["waiting"].append({**line, "signed_by": sig.get("name"), "signed_at": sig.get("at")})
    return out


def pickup(plane, iid: str, name: str) -> dict:
    if not IID.fullmatch(iid) or not any(s["intent_id"] == iid for s in signed_sows(plane)):
        raise HTTPException(404, {"error": "not_found", "message": "There is no signed intent of work with that name."})
    with lock_for(plane.path("build", "pickup", iid)):  # ponytail: per-intent lock around read-then-write; P1's lock covers the file
        held, prj = _held(plane, iid)
        if held:
            raise HTTPException(409, {"error": "taken", "message": f"{held} has already picked this up."})
        P.set_person(plane, prj["id"], "builder", name)
    return {"intent_id": iid, "builder": name, "pid": prj["id"]}


@router.get("/api/v1/build/waiting")
def get_waiting(request: Request) -> dict:
    return waiting(_plane(request), viewer_of(request))


@router.post("/api/v1/build/pickup/{iid}")
def post_pickup(iid: str, request: Request) -> dict:
    viewer = require_seat(request, ARCHITECT)
    plane = _plane(request)
    prj = P.for_intent(plane, iid)
    if prj and G1.level(plane, viewer, prj) == "none":
        raise HTTPException(404, {"error": "not_found", "message": "There is no signed intent of work with that name."})
    return pickup(plane, iid, viewer.name)
