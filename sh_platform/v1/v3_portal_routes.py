"""G5 family portal, Web Push and the morning email (logic in g5_portal and g5_push; docs/v3/PROGRAM-GAPS.md W5). Failures answer a plain message.
GET  /api/v3/portal[?member=] -> {member, share:{basis, total, lines, note}, note:{headline, lines, text}, documents, approvals}; a family member sees only their own
                                 (?member= is for the company admin to preview a member)
POST /api/v3/portal/ask {text} -> {answer, used}                       from the member's own data only
POST /api/v3/portal/approvals {member, title, detail?, amount?, currency?} -> the approval   staff raise it for a member
POST /api/v3/portal/approvals/{id}/decide {approve, note?} -> the approval    only the member it is addressed to
POST /api/v3/portal/morning-email {force?} -> {day, sent:[{to, result}]}   company admin: write today's notes now (outbox, or SMTP when SH_SMTP_URL is set)
GET  /api/v3/push/config -> {enabled, public_key, subscribed};  POST /api/v3/push/subscribe {subscription};  POST /api/v3/push/unsubscribe {endpoint?}
GET  /api/v3/push/inbox -> [{title, body, url}]   what a wake-up from the push service is about (the service worker reads it, then it is empty)
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from sh_platform.profile.api import _plane
from sh_platform.v1 import g5_portal as G, g5_push as P

router = APIRouter()
STAFF = {"company_admin", "sponsor", "analyst", "approver"}


def _me(request: Request) -> dict:
    a = request.app.state.account_store.get(request.state.account_id)
    if not a:
        raise HTTPException(401, "Please sign in again.")
    return a if isinstance(a, dict) else vars(a)


def _member(request: Request, plane, preview: str | None = None) -> str:
    me = _me(request)
    if preview and "company_admin" in (request.state.roles or []):
        if preview not in G.members(plane):
            raise HTTPException(404, "That is not a family member of this office.")
        return preview
    m = G.member_of(plane, me)
    if m is None:
        raise HTTPException(403, "This page is for the family members of the office.")
    return m


async def _body(request: Request) -> dict:
    try:
        b = await request.json()
    except ValueError:
        b = None
    return b if isinstance(b, dict) else {}


@router.get("/api/v3/portal")
async def portal(request: Request, member: str | None = None):
    plane = _plane(request)
    return await run_in_threadpool(lambda: G.portal(plane, _member(request, plane, member)))


@router.post("/api/v3/portal/ask")
async def ask(request: Request):
    plane, b = _plane(request), await _body(request)
    text = str(b.get("text") or "").strip()[:500]
    if not text:
        raise HTTPException(400, "Type your question first.")
    return await run_in_threadpool(lambda: G.ask(plane, _member(request, plane, b.get("member")), text))


@router.post("/api/v3/portal/approvals")
async def raise_approval(request: Request):
    plane, b = _plane(request), await _body(request)
    if not STAFF & set(request.state.roles or []):
        raise HTTPException(403, "Only the office team can ask a family member to approve something.")
    try:
        return G.raise_approval(plane, _me(request).get("display_name") or "the office", str(b.get("member") or ""), b.get("title") or "", b.get("detail") or "",
                                b.get("amount"), b.get("currency") or "USD")
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@router.post("/api/v3/portal/approvals/{aid}/decide")
async def decide(aid: str, request: Request):
    plane, b = _plane(request), await _body(request)
    member = _member(request, plane)  # the preview is for looking, not deciding: no `member` argument here
    try:
        return G.decide(plane, member, aid, b.get("approve") is True, str(b.get("note") or ""))
    except LookupError as e:
        raise HTTPException(404, str(e)) from None
    except ValueError as e:
        raise HTTPException(409, str(e)) from None


@router.post("/api/v3/portal/morning-email")
async def morning_email(request: Request):
    plane, b = _plane(request), await _body(request)
    return await run_in_threadpool(lambda: G.send_morning(plane, G.accounts_of(plane), force=b.get("force") is True))


@router.get("/api/v3/push/config")
def push_config(request: Request):
    plane, keys = _plane(request), None
    keys = P.vapid(plane)
    return {"enabled": keys is not None, "public_key": keys["public"] if keys else None, "subscribed": P.is_on(plane, request.state.account_id)}


@router.post("/api/v3/push/subscribe")
async def push_subscribe(request: Request):
    plane, b = _plane(request), await _body(request)
    if P.vapid(plane) is None:
        raise HTTPException(503, "Notifications are not switched on for this office yet.")
    sub = b.get("subscription") if isinstance(b.get("subscription"), dict) else {}
    if not P.subscribe(plane, request.state.account_id, sub):
        raise HTTPException(400, "That browser's notification address is not one I can use.")
    return {"subscribed": True}


@router.post("/api/v3/push/unsubscribe")
async def push_unsubscribe(request: Request):
    plane, b = _plane(request), await _body(request)
    P.unsubscribe(plane, request.state.account_id, str(b.get("endpoint") or "") or None)
    return {"subscribed": P.is_on(plane, request.state.account_id)}


@router.get("/api/v3/push/inbox")
def push_inbox(request: Request):
    return P.inbox_take(_plane(request), request.state.account_id)
