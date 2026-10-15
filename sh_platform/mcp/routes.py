"""MCP routes. POST /mcp is token-authenticated (Authorization: Bearer shmcp...), not by cookie; the Settings routes use the normal session.

POST   /mcp                         JSON-RPC, one message per request (streamable HTTP, JSON replies)
GET    /api/v1/mcp/tokens           this person's tokens (no secrets)
POST   /api/v1/mcp/tokens           {label, scopes, days}: issue one; the token text is in the reply once
DELETE /api/v1/mcp/tokens/{id}      revoke (own token; a company admin may revoke any of the company)
GET    /api/v1/mcp/drafts           the drafts this person's assistants proposed, waiting for a yes
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from sh_platform.jsonfile import read_json_strict
from sh_platform.mcp import server, tokens
from sh_platform.plane import PlaneStore

router = APIRouter()
MAX_BODY = 256_000


def _plane(request: Request):
    try:
        return PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()
    except (LookupError, PermissionError, ValueError):
        raise HTTPException(403, {"error": "forbidden", "message": "Your company space could not be opened. Please ask your administrator."}) from None


@router.post("/mcp")
async def rpc(request: Request):
    raw = await request.body()
    auth = request.headers.get("authorization", "")
    bearer = auth[7:].strip() if auth[:7].lower() == "bearer " else ""
    try:
        if len(raw) > MAX_BODY:
            return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Too large."}}, 413)
        msg = json.loads(raw)
    except ValueError:
        msg = None
    status, out = await run_in_threadpool(server.handle, request.app.state.settings.data_root, bearer, msg)
    if status == 401:
        return JSONResponse({"error": "unauthorized"}, 401, headers={"WWW-Authenticate": 'Bearer realm="signal-harbor"'})
    return Response(status_code=status) if out is None else JSONResponse(out, status)


@router.get("/mcp")
async def no_stream():
    return Response(status_code=405, headers={"Allow": "POST"})


@router.get("/api/v1/mcp/tokens")
async def list_tokens(request: Request):
    return {"tokens": tokens.listing(_plane(request), request.state.account_id), "scopes": list(tokens.SCOPES)}


@router.post("/api/v1/mcp/tokens")
async def issue_token(request: Request):
    body = await request.json()
    body = body if isinstance(body, dict) else {}
    try:
        return tokens.issue(_plane(request), request.state.account_id, body.get("label"), body.get("scopes") or ["read"], body.get("days", tokens.DEFAULT_DAYS))
    except tokens.TokenError as e:
        raise HTTPException(400, {"error": "bad_request", "message": str(e)}) from None


@router.delete("/api/v1/mcp/tokens/{token_id}")
async def revoke_token(request: Request, token_id: str):
    if not tokens.revoke(_plane(request), token_id, request.state.account_id, "company_admin" in (request.state.roles or [])):
        raise HTTPException(404, {"error": "not_found", "message": "We could not find that token."})
    return {"revoked": True}


@router.get("/api/v1/mcp/drafts")
async def list_drafts(request: Request):
    plane = _plane(request)
    rows = read_json_strict(plane.area("context") / "mcp_drafts.json", list) or []
    return {"drafts": [{k: r[k] for k in ("id", "kind", "item", "at", "status")} for r in rows if r["account_id"] == request.state.account_id]}
