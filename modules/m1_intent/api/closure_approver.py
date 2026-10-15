"""IC v2 spec 09: the closure by approver link, for a person with no account. A SECURITY PATH, the same defences as api/approver.py.

The link is "ci.<company>.<intent id>.<secret>"; only its SHA-256 hash is kept (sh_platform/intents/closure.py). It travels in the
X-Session-Token header only. One route: no `decision` in the body reads the one-page closure; `decision` approve or decline decides it,
and the link is used up. The answers hold the closure's own words and nothing else: no ids, no other intent, no account data.
Every failure before the hash matches gives the same answer and counts against the caller (5 failures, then a wait).
"""
import logging

from fastapi import APIRouter, Request

from modules.m1_intent.api import approver as base
from modules.m1_intent.api import deps
from sh_platform.intents import closure as K
from sh_platform.modulegate import may_use_module
from sh_platform.plane import CrossCompanyError, PlaneStore

log = logging.getLogger(__name__)
router = APIRouter()


async def _plane(request: Request):
    throttle, key = base._throttle(request.app), request.client.host if request.client else "unknown"
    if throttle.locked(key):
        raise base._Refuse(deps.plain(429, *base._LOCKED))
    m = K.TOKEN.fullmatch(request.headers.get(base.HEADER, ""))
    try:
        if m and may_use_module(request.app.state.entitlements, m.group(1), base.MODULE):
            return PlaneStore(request.app.state.settings.data_root).plane_for(m.group(1)).ensure(), m.group(0)
    except (LookupError, CrossCompanyError, ValueError, OSError):
        pass
    throttle.failed(key)
    raise base._Refuse(deps.plain(404, *base._INVALID))


@router.post("/approver/closure")
async def closure_by_link(request: Request):
    try:
        plane, token = await _plane(request)
    except base._Refuse as e:
        return e.response
    body = await base._decision_body(request) if request.headers.get("content-length", "0") not in ("", "0") else {}
    if body is None or set(body) - {"decision", "comment"} or body.get("decision") not in (None, "approve", "decline"):
        return deps.plain(400, "bad_request", deps.BAD_BODY)
    try:
        if body.get("decision") is None:
            return await deps.blocking(K.approver_read, plane, token)
        return await deps.blocking(K.approver_decide, plane, token, body["decision"], str(body.get("comment") or ""))
    except K.LinkGone as e:
        if e.status in (404, 409):
            base._failed_link(request)
        return deps.plain(e.status, {404: "link_invalid", 409: "link_gone"}.get(e.status, "comment_needed"), str(e))
