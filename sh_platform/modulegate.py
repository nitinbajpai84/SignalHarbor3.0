"""Module gate: who may reach which module, plus the menu and the module switch routes.

The gate is a pure ASGI middleware placed OUTSIDE the auth middleware, so a request under
/api/modules/<module_id>/... is judged on one question first: does the signed-in company own that module?
Switched off, never owned, not in the catalogue, signed in as a super admin: all get the same 403, with the
same body and headers, before the route table, the roles or the CSRF check can say anything about whether
the path exists. Signed out gets one 401 for every such path. Anything it does not recognise as clean
(dot segments, empty segments, backslashes, NUL) is refused too. Applies to HTTP, WebSocket, mounts and
routers alike because it works on the path, not on the route table.

A route the table marks `guest` (module 1's join link and lobby, auth/guest.py) is the one exception to "signed
in": see _guest_verdict. A guest of a company that does not own the module gets the same 403 as anyone.

The tool registry (P1-07) calls the same decision through may_use_module().
"""
import logging

from fastapi import APIRouter, FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response
from starlette._utils import get_route_path  # ponytail: private, same function routing uses
from starlette.requests import HTTPConnection

from sh_platform.auth import AuthMiddleware, _EXPIRED, _FORBIDDEN, _key_for
from sh_platform.auth.guest import guest_for
from sh_platform.entitlements import LOGO_NAME, EntitlementStore
from sh_platform.plane import CrossCompanyError, PlaneStore
from sh_platform.settings import Settings

log = logging.getLogger(__name__)
PREFIX = "/api/modules/"
NOT_AVAILABLE = {"error": "module_not_available", "message": "This module is not part of your plan."}
router = APIRouter()


def may_use_module(store: EntitlementStore, company_id, module_id) -> bool:
    """The one decision: does this company own this module right now? Never raises."""
    return store.is_enabled(company_id, module_id)


def _clean(segments: list[str]) -> bool:
    return not any(s in (".", "..") or "\\" in s or "\x00" in s for s in segments) and "" not in segments[:-1]


ALIASES = {"/api/intents": "m1_intent"}  # spec 14 rule 11: Intent Centre v2 routes belong to module 1


def _module_segments(path: str) -> list[str] | None:
    """[module_id, ...rest] for a path the gate judges, else None."""
    if path.startswith(PREFIX):
        return path[len(PREFIX):].split("/")
    for prefix, module_id in ALIASES.items():
        if path == prefix or path.startswith(prefix + "/"):
            return [module_id, *path[len(prefix):].split("/")[1:]]
    return None


class ModuleGate:
    def __init__(self, app, owner: FastAPI):
        self.app, self.owner = app, owner
        # ponytail: reuses auth's session check so "signed in" has one definition; costs a second small
        # file read per module request.
        self._auth = AuthMiddleware(None, owner, None)  # only its _session() is used here

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        segments = _module_segments(get_route_path(scope))
        if segments is None:
            return await self.app(scope, receive, send)
        verdict = self._verdict(scope, segments)
        if verdict is None:
            return await self.app(scope, receive, send)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        body, status = {"expired": (_EXPIRED, 401), "forbidden": (_FORBIDDEN, 403)}.get(verdict, (NOT_AVAILABLE, 403))
        await JSONResponse(body, status_code=status)(scope, receive, send)

    def _verdict(self, scope, segments: list[str]) -> str | None:
        rec = self._auth._session(HTTPConnection(scope).cookies.get("sh_session"))
        if rec is None:
            return self._guest_verdict(scope, segments)
        if _clean(segments) and may_use_module(self.owner.state.entitlements, rec["company_id"], segments[0]):
            return None
        return "refused"

    def _guest_verdict(self, scope, segments: list[str]) -> str | None:
        """No signed-in session. A route the table marks `guest` also admits a holder of a valid session token
        (the module must be owned by the token's company, exactly as for a signed-in user) and, if it is an
        `entry` route, a caller with neither (its handler checks the join code). Everything else is signed out."""
        key = _key_for(self.owner, scope) if scope["type"] == "http" and _clean(segments) else None
        rule = self.owner.state.route_permissions.routes.get(key) if key else None
        if rule is None or not rule.guest:
            # a live guest on a route that is not theirs is refused, not told their session ended
            return "forbidden" if scope["type"] == "http" and guest_for(self.owner, scope) is not None else "expired"
        g = guest_for(self.owner, scope)
        if g is None:
            return None if rule.entry else "expired"
        return None if may_use_module(self.owner.state.entitlements, g.company_id, segments[0]) else "refused"


@router.get("/api/modules")
def my_modules(request: Request) -> list[dict]:
    store: EntitlementStore = request.app.state.entitlements
    owned = set(store.enabled_modules(request.state.company_id))
    centres = {c.id: c.public() for c in store.centres_for(request.state.company_id)}
    out = []
    for m in store.catalogue.modules:
        if m.id in owned:
            cid = store.centre_for(m.id)
            out.append({**m.public(), "centre": cid, **({"centre_name": centres[cid]["name"],
                        "centre_description": centres[cid]["description"]} if cid in centres else {})})
    return out


@router.get("/api/company")
def my_company(request: Request):
    rec = request.app.state.entitlements.company(request.state.company_id)
    if rec is None:
        return JSONResponse({"error": "company_not_found",
                             "message": "Your company is not set up yet. Please ask your administrator."},
                            status_code=404)
    out = {"company_id": rec["company_id"], "name": rec["name"], "industry": rec["industry"]}
    if rec.get("brand"):  # only a company with a brand record gets the key; the logo itself is GET /api/company/logo
        out["brand"] = rec["brand"]
    return out


LOGO_MAX_BYTES = 512 * 1024
_LOGO_TYPES = {"png": "image/png", "svg": "image/svg+xml"}


@router.get("/api/company/logo")
def my_company_logo(request: Request):
    """The signed-in company's logo from its own plane (brand/). The file name comes from the company record, never from
    the request; the size is capped; an svg is served with a policy that lets it show but run nothing."""
    gone = JSONResponse({"error": "no_logo", "message": "This company has no logo."}, status_code=404)
    rec = request.app.state.entitlements.company(request.state.company_id)
    name = ((rec or {}).get("brand") or {}).get("logo")
    if not isinstance(name, str) or not LOGO_NAME.fullmatch(name):
        return gone
    try:
        path = PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).path("brand", name)
        if not path.is_file() or path.stat().st_size > LOGO_MAX_BYTES:
            return gone
        data = path.read_bytes()
    except (CrossCompanyError, LookupError, OSError):
        return gone
    ext = name.rsplit(".", 1)[1]
    if ext == "png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return gone
    if ext == "svg" and b"<svg" not in data[:2048]:
        return gone
    return Response(data, media_type=_LOGO_TYPES[ext], headers={
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=300",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox"})


def _plain(status: int, error: str, message: str) -> JSONResponse:
    return JSONResponse({"error": error, "message": message}, status_code=status)


@router.put("/api/admin/companies/{company_id}/modules/{module_id}")
async def switch_module(company_id: str, module_id: str, request: Request):
    store: EntitlementStore = request.app.state.entitlements
    try:
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            raise ValueError
        enabled = (await request.json())["enabled"]
        if not isinstance(enabled, bool):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        return _plain(400, "bad_request", 'Send {"enabled": true} or {"enabled": false}.')
    if module_id not in store.catalogue.ids:
        return _plain(404, "unknown_module", "That module does not exist.")
    try:
        await run_in_threadpool(store.set_module, company_id, module_id, enabled)
    except (LookupError, ValueError):  # unknown company, or an id that is not a valid company id
        return _plain(404, "unknown_company", "That company does not exist.")
    return {"company_id": company_id, "module_id": module_id, "enabled": enabled}


def install_modulegate(app: FastAPI, settings: Settings) -> None:
    """Call after install_auth. The gate must wrap auth, which add_middleware does for the later call."""
    if not hasattr(app.state, "sessions"):
        raise RuntimeError("install_auth must run before install_modulegate")
    app.state.entitlements = EntitlementStore(settings.data_root)
    app.include_router(router)
    app.add_middleware(ModuleGate, owner=app)
