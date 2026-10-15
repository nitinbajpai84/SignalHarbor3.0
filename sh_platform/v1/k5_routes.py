"""K3 routes: the manager inbox (Action) and manager research (Consume).

GET  /api/v1/managers/inbox?as_of=            per manager and fund: due, received, late, revised, last value and status
POST /api/v1/managers/{id}/followup           {fund_id?, as_of?} -> a plain-text email draft; nothing is sent
GET  /api/v1/managers/{id}                    profile: funds, commitments, statements timeline, notes, documents, open questions
GET  /api/v1/managers/{id}/changes?since=     what changed since the last meeting (or a date), every line dated and sourced
POST /api/v1/managers/{id}/notes              {text, kind: note|meeting|question, on?}
POST /api/v1/managers/{id}/notes/{nid}/answered
Funds a person may not see (E1d) are not listed, and their manager is a 404 to that person."""
import logging

import duckdb
from fastapi import APIRouter, Body, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import k5_managers as K
from sh_platform.v1 import wh
from sh_platform.v1.i2_north import Refused
from sh_platform.v1.seats import CONSUMER, require_seat

log = logging.getLogger(__name__)
router = APIRouter()
BUSY = "The company records are busy for a moment. Please try again in a few seconds."
CODES = {400: "invalid", 403: "not_allowed", 404: "not_found"}


async def _run(request: Request, fn):
    viewer = require_seat(request, CONSUMER)
    for attempt in (1, 2):
        try:
            return await run_in_threadpool(fn, _plane(request), viewer)
        except (wh.Busy, duckdb.Error):
            # AUC3-01: a warehouse read that collides with another request is tried once more, then a plain answer, never a bare 500.
            # Every route here reads the warehouse before it writes a note, so a second try never writes twice.
            log.warning("manager route: warehouse error (try %s of 2)", attempt, exc_info=True)
        except Refused as e:
            return JSONResponse({"error": CODES.get(e.status, "invalid"), "message": e.message}, status_code=e.status)
        except PermissionError:
            return JSONResponse({"error": "forbidden", "message": "Your company space could not be opened. Please ask your administrator."}, status_code=403)
    return JSONResponse({"error": "busy", "message": BUSY}, status_code=503)


@router.get("/api/v1/managers/inbox")
async def get_inbox(request: Request, as_of: str = ""):
    return await _run(request, lambda p, v: K.inbox(p, v, as_of or None))


@router.post("/api/v1/managers/{manager_id}/followup")
async def post_followup(request: Request, manager_id: str, body: dict = Body(default={})):
    return await _run(request, lambda p, v: K.draft_followup(p, v, manager_id, body.get("fund_id"), body.get("as_of")))


@router.get("/api/v1/managers/{manager_id}")
async def get_profile(request: Request, manager_id: str):
    return await _run(request, lambda p, v: K.profile(p, v, manager_id))


@router.get("/api/v1/managers/{manager_id}/changes")
async def get_changes(request: Request, manager_id: str, since: str = ""):
    return await _run(request, lambda p, v: K.changes(p, v, manager_id, since or None))


@router.post("/api/v1/managers/{manager_id}/notes")
async def post_note(request: Request, manager_id: str, body: dict = Body(default={})):
    return await _run(request, lambda p, v: K.add_note(p, v, manager_id, body.get("text"), body.get("kind") or "note", body.get("on")))


@router.post("/api/v1/managers/{manager_id}/notes/{note_id}/answered")
async def post_answered(request: Request, manager_id: str, note_id: str):
    return await _run(request, lambda p, v: K.resolve_question(p, v, manager_id, note_id))
