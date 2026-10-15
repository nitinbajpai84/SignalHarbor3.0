"""Spec 11: the visitor routes of an intent share. A SIGNED-IN person of the company opens what the organiser shared with them.

Same defences as api/approver.py, in the same order: sign-in, the failure lock, the token's shape, then the match. The token of a
link travels in the X-Session-Token header only; a named or area share sends the intent id in the body. The logic is in
sh_platform/intents/share.py (the one link mechanism); these two routes only read the request and hand it over.
"""
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool

from modules.m1_intent.api import deps
from modules.m1_intent.api.approver import HEADER, _decision_body
from sh_platform.intents import share

router = APIRouter()


async def _read(request: Request):
    body = await _decision_body(request)
    if body is None or set(body) - {"intent_id", "text"}:
        return None
    return body, request.headers.get(HEADER) or None


@router.post("/shared/view")
async def view(request: Request):
    got = await _read(request)
    if got is None:
        return deps.plain(400, "bad_request", deps.BAD_BODY)
    body, token = got
    return await run_in_threadpool(share.visitor_open, request, body.get("intent_id"), token)


@router.post("/shared/note")
async def note(request: Request):
    got = await _read(request)
    if got is None:
        return deps.plain(400, "bad_request", deps.BAD_BODY)
    body, token = got
    return await run_in_threadpool(share.visitor_note, request, body.get("intent_id"), token, body.get("text"))
