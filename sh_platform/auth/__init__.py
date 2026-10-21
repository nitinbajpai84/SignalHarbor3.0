"""Sign-in and access: sessions, CSRF, roles, default-deny route permissions.

One pure ASGI middleware covers HTTP and WebSocket. A request is allowed through only if it matches a
route that is declared in route_permissions.yaml; a route we cannot classify (for example app.frontend)
is refused. Keys in the yaml: "GET /path", "WEBSOCKET /path", "MOUNT /prefix/{path}".
"""
import hmac
import logging
import secrets
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.requests import HTTPConnection
from starlette.routing import Match, Mount

from sh_platform import demo_limits
from sh_platform.auth.accounts import AccountStore
from sh_platform.auth.guest import guest_for
from sh_platform.auth.permissions import Permissions, is_unsafe, load_permissions
from sh_platform.auth.routes import router
from sh_platform.auth.sessions import ABSOLUTE_SECONDS, IDLE_SECONDS, LoginThrottle, SessionManager
from sh_platform.settings import Settings

log = logging.getLogger(__name__)
_EXPIRED = {"error": "session_expired", "message": "Your session has ended. Please sign in again.",
            "login_url": "/login"}
_FORBIDDEN = {"error": "forbidden", "message": "You do not have access to this."}
_RATE = {"error": "rate_limited", "message": "That is a lot of questions in an hour for a public demo. Please wait a little and try again."}
_CSRF = {"error": "csrf", "message": "Please reload the page and try again."}
# SP-C1-03: a signed-in person refused for their role is told who can act, in the product's words, never just "no access"
ROLE_WORDS = {"company_admin": "the company administrator", "analyst": "the data team", "head_of_data": "the head of data", "sponsor": "the sponsor", "owner": "a data owner",
              "approver": "an approver", "participant": "a participant"}
MAX_NAMED = 3


def who_can_act(accounts, company_id: str | None, roles) -> dict:
    """The refusal for a person whose role may not use a route: the roles that may, and up to three colleagues who hold them."""
    words = [w for r, w in ROLE_WORDS.items() if r in roles]
    if not words:
        return _FORBIDDEN
    try:
        people = [a["display_name"] for a in (accounts.in_company(company_id) if company_id else [])
                  if not a["disabled"] and set(a["roles"]) & set(roles) and a.get("display_name")][:MAX_NAMED]
    except Exception:  # noqa: BLE001 - the refusal never fails for want of names
        people = []
    msg = f"Only {' or '.join(words)} can do this" + (f"; {' or '.join(people)} can." if people else ".")
    return {"error": "forbidden", "message": msg}


def iter_routes(routes):
    """Flat route objects, looking inside include_router() groups.

    ponytail: leans on FastAPI's internal effective_candidates(); test_fastapi_version_is_the_tested_one
    tells the next builder to re-check this when FastAPI is upgraded.
    """
    for r in routes:
        if hasattr(r, "effective_candidates"):
            yield from iter_routes(r.effective_candidates())
            yield from iter_routes(r.effective_low_priority_routes())
        elif getattr(r, "starlette_route", None) is not None:
            yield r.starlette_route
        else:
            yield r


def all_routes(app: FastAPI) -> list:
    """Every route object the app can serve, including low-priority ones (app.frontend)."""
    # ponytail: _low_priority_routes is a FastAPI private list
    return [*iter_routes(app.routes), *iter_routes(getattr(app.router, "_low_priority_routes", []))]


def route_keys(route) -> list[str]:
    """Permission keys a route needs declared. Raises ValueError for a route we cannot classify."""
    pf = getattr(route, "path_format", None)
    if "Frontend" in type(getattr(route, "original_route", route)).__name__ or pf is None:
        raise ValueError(f"cannot classify route object {type(route).__name__}; it would bypass default deny")
    if isinstance(route, Mount):
        return [f"MOUNT {pf}"]
    if getattr(route, "methods", None) is None:
        return [f"WEBSOCKET {pf}"]
    return [f"{m} {pf}" for m in sorted(route.methods) if m not in {"HEAD", "OPTIONS"}]


def _key_for(app: FastAPI, scope) -> str | None | bool:
    """Key of the route that will serve this scope; None if nothing will (404); False if unclassifiable."""
    for route in all_routes(app):
        if route.matches(scope)[0] != Match.FULL:
            continue
        try:
            route_keys(route)
        except ValueError:
            return False
        if isinstance(route, Mount):
            return f"MOUNT {route.path_format}"
        if scope["type"] == "websocket":
            return f"WEBSOCKET {route.path_format}"
        return f"{'GET' if scope['method'] == 'HEAD' else scope['method']} {route.path_format}"
    return None


class AuthMiddleware:
    def __init__(self, app, owner: FastAPI, perms: Permissions):
        self.app, self.owner, self.perms = app, owner, perms

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        state = scope.setdefault("state", {})
        state.update(sid=None, account_id=None, company_id=None, roles=[], guest_id=None, m1_session_id=None)
        verdict = "forbidden" if self._bad_origin(scope) else self._check(scope, state)
        if verdict is None:
            return await self.app(scope, receive, send)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})  # policy violation
        if verdict == "redirect":
            resp = RedirectResponse("/login", status_code=302)
        else:
            resp = JSONResponse(*{"expired": (_EXPIRED, 401), "csrf": (_CSRF, 403), "rate": (_RATE, 429)}.get(verdict, (state.get("refusal") or _FORBIDDEN, 403)),
                                headers={"x-refused-by": "access"})  # the guard's refusal, told apart from a handler's own 403
        await resp(scope, receive, send)

    @staticmethod
    def _bad_origin(scope) -> bool:
        """A WebSocket handshake from a page on another host:port is refused (cross-site hijacking)."""
        if scope["type"] != "websocket":
            return False
        headers = HTTPConnection(scope).headers
        origin = headers.get("origin")
        return origin is not None and urlsplit(origin).netloc.lower() != headers.get("host", "").lower()

    def _check(self, scope, state) -> str | None:
        """None to let the request through, else why it is refused."""
        key = _key_for(self.owner, scope)
        if key is None:  # nothing serves this: the framework answers 404/405
            return None
        rule = self.perms.routes.get(key) if key else None
        if rule is None:
            return "forbidden"
        if rule.roles == {"super_admin"} and not rule.authenticated and not demo_limits.superadmin_open():
            return "forbidden"  # public demo: the control area is off unless SH_ENABLE_SUPERADMIN=1
        if rule.public:
            return None
        conn = HTTPConnection(scope)
        rec = self._session(conn.cookies.get("sh_session"))
        if rec is None and rule.guest and scope["type"] == "http":
            return self._guest(scope, state, rule)
        if rec is None and scope["type"] == "http" and guest_for(self.owner, scope) is not None:
            return "forbidden"  # a live guest on a route guests may not use: refused, not "your session has ended"
        if rec is None:
            html = "text/html" in conn.headers.get("accept", "") and not scope["path"].startswith("/api/")
            return "redirect" if scope["type"] == "http" and html else "expired"
        if scope["type"] == "http" and is_unsafe(scope["method"]) and not hmac.compare_digest(
                conn.headers.get("x-csrf-token", "").encode(), self.owner.state.sessions.csrf_for(rec["sid"]).encode()):
            return "csrf"
        if not (rule.authenticated and rec["company_id"] is not None or rule.roles & set(rec["roles"])):
            if rec["company_id"] is not None and rule.roles:
                state["refusal"] = who_can_act(self.owner.state.account_store, rec["company_id"], rule.roles)
            return "forbidden"
        state.update(sid=rec["sid"], account_id=rec["account_id"], company_id=rec["company_id"],
                     roles=rec["roles"])
        if scope["type"] == "http" and scope["method"] == "POST" and demo_limits.CHAT_ROUTE.match(scope["path"]):
            if not self.owner.state.turn_limiter.allow(rec["account_id"]):
                return "rate"
        if scope["type"] == "http":
            from sh_platform.v1 import v3_audit  # W7: reads, exports, changes, signed decisions
            v3_audit.record_request(self.owner, state, scope["method"], scope["path"])
        return None

    def _guest(self, scope, state, rule) -> str | None:
        """No signed-in session on a guest route: a valid X-Session-Token makes the caller a participant of that
        token's company and session, nothing more. An `entry` route also lets a caller with neither through (the
        handler checks the join code). The module gate has already checked the module is owned.
        A guest has no cookie, so there is nothing for a cross-site page to ride on: no CSRF check applies."""
        g = guest_for(self.owner, scope)
        if g is not None and "participant" in rule.roles:  # the loader checks this too
            state.update(company_id=g.company_id, roles=["participant"], guest_id=g.guest_id,
                         m1_session_id=g.session_id)
            return None
        if rule.entry:
            return None
        return "forbidden" if g is not None else "expired"  # a live guest on a route not theirs is refused, not signed out

    def _session(self, cookie: str | None) -> dict | None:
        """Live session whose account is still enabled with the same company and roles."""
        sessions = self.owner.state.sessions
        rec = sessions.resolve(cookie)
        if rec is None:
            return None
        acct = self.owner.state.account_store.get(rec["account_id"])  # one small file read per request
        if not acct or acct["disabled"]:
            sessions.destroy(rec["sid"])
            return None
        return {**rec, "roles": acct["roles"], "company_id": acct["company_id"]}  # the account is the truth


def install_auth(app: FastAPI, settings: Settings, *, idle_seconds: int = IDLE_SECONDS,
                 absolute_seconds: int = ABSOLUTE_SECONDS, clock: Callable[[], float] = time.time,
                 route_permissions: Path | str | None = None) -> None:
    secret = settings.session_secret.strip()
    if not secret:
        if settings.mode != "dev":
            raise RuntimeError("SH_SESSION_SECRET is empty; set it before starting outside dev mode.")
        secret = secrets.token_hex(32)
        log.warning("SH_SESSION_SECRET is empty; generated a per-process secret (dev mode only).")
    elif settings.mode != "dev" and (len(secret) < 32 or len(set(secret)) < 8):
        raise RuntimeError("SH_SESSION_SECRET is too weak: use at least 32 characters with at least 8 "
                           "different ones (a random value).")
    app.state.settings = settings
    app.state.account_store = AccountStore(settings.data_root)
    app.state.sessions = SessionManager(secret, idle_seconds, absolute_seconds, clock)
    app.state.login_throttle = LoginThrottle(clock)
    app.state.turn_limiter = demo_limits.TurnLimiter(clock)
    app.include_router(router)
    app.state.route_permissions = perms = load_permissions(route_permissions)  # the module gate reads it too
    app.add_middleware(AuthMiddleware, owner=app, perms=perms)
