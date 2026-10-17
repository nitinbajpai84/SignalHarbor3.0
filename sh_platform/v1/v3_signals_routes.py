"""Harbor 3.0 signals (logic in v3_signals; docs/v3/SIGNAL-ENGINE.md). Failures answer a plain message.
GET /api/v3/signals -> [{id, title, pain_points, trigger, severity, route_to, role_title, action, hold, source, suggestion, error, stats}]
GET /api/v3/signals/fired?status=open|acted|dismissed -> the cards, newest first, each with its receipts (evidence)
POST /api/v3/signals/{fired_id}/act {choice?, note?, dismiss?} -> the card; `next` lists the cards it started"""
from fastapi import APIRouter, HTTPException, Request

from sh_platform.profile.api import _plane
from sh_platform.v1 import v3_roles as R, v3_signals as SG

router = APIRouter()
KEEP = ("id", "title", "pain_points", "trigger", "severity", "route_to", "role_title", "action", "hold", "source", "suggestion", "error", "disabled")


@router.get("/api/v3/signals")
def library(request: Request):
    plane, st = _plane(request), None
    st = SG.stats(plane)
    return [{**{k: s.get(k) for k in KEEP}, "stats": st.get(s["id"]) or {"fired": 0, "acted": 0, "dismissed": 0, "open": 0, "hit_rate": None, "last_fired": None}}
            for s in SG.library(plane)]


@router.get("/api/v3/signals/fired")
def fired(request: Request, status: str | None = None):
    rows = [{k: v for k, v in r.items() if k != "event"} for r in SG.fired(_plane(request)) if not status or r["status"] == status]
    return list(reversed(rows))


@router.post("/api/v3/signals/{fired_id}/act")
async def act(fired_id: str, request: Request):
    plane = _plane(request)
    try:
        body = await request.json()
    except ValueError:
        body = None
    body = body if isinstance(body, dict) else {}
    me = request.app.state.account_store.get(request.state.account_id) or {}
    me = me if isinstance(me, dict) else vars(me)
    email = str(me.get("email") or "").casefold()
    card = next((r for r in SG.fired(plane) if r["id"] == fired_id), None)
    if card is None:
        raise HTTPException(404, "I cannot find that card.")
    jobs = R._jobs(plane)
    if jobs and "company_admin" not in (request.state.roles or []) and jobs.get(email) != card["route_to"]:
        raise HTTPException(403, f"This card is for the {card.get('role_title') or card['route_to']}.")
    try:
        got = SG.act(plane, fired_id, me.get("display_name") or email, body.get("choice"), str(body.get("note") or ""), bool(body.get("dismiss")))
    except ValueError as e:
        raise HTTPException(409, str(e)) from None
    return {k: v for k, v in got.items() if k != "event"}
