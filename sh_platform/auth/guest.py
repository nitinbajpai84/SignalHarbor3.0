"""The guest principal: a person with no account who holds a session token (module 1, M1-P02).

A module registers ONE resolver with register_guest_resolver(module_id, fn). fn(app, token) returns
(company_id, guest_id, session_id) for a token that is valid right now, else None. The kernel never decides
what a token is; it only asks, and it believes the answer only if it is exactly three good strings.

Where a guest can go is set by the route table, never here: only a route marked `guest: true` (module routes,
roles that include participant). The token is read from the X-Session-Token header only: never a query string,
never a cookie. The company comes from the resolver's answer, never from the request. Never raises, never logs
the token.
"""
import logging
from dataclasses import dataclass
from typing import Callable

from starlette._utils import get_route_path  # ponytail: private, same function routing uses
from starlette.requests import HTTPConnection

from sh_platform.plane import InvalidCompanyId, valid_company_id, valid_module_id

log = logging.getLogger(__name__)
PREFIX = "/api/modules/"
HEADER = "x-session-token"
MAX_TOKEN = 200
_RESOLVERS: dict[str, Callable] = {}


@dataclass(frozen=True)
class Guest:
    company_id: str
    guest_id: str
    session_id: str


def register_guest_resolver(module_id: str, fn: Callable) -> None:
    if not valid_module_id(module_id):
        raise ValueError("module id must be lowercase letters, digits and underscores")
    _RESOLVERS[module_id] = fn


def unregister_guest_resolver(module_id: str) -> None:
    _RESOLVERS.pop(module_id, None)


def module_of(path: str) -> str | None:
    if not path.startswith(PREFIX):
        return None
    first = path[len(PREFIX):].split("/", 1)[0]
    return first if valid_module_id(first) else None


def guest_for(app, scope) -> Guest | None:
    """The guest behind this HTTP request's X-Session-Token header, or None. Cookies and the query string are
    never looked at. The module is the one in the path."""
    if scope["type"] != "http":
        return None
    module_id = module_of(get_route_path(scope))
    fn = _RESOLVERS.get(module_id) if module_id else None
    token = HTTPConnection(scope).headers.get(HEADER)
    if fn is None or not token or len(token) > MAX_TOKEN:
        return None
    try:
        got = fn(app, token)
    except Exception:  # noqa: BLE001 - a broken resolver means "no guest", never an error page
        log.warning("The guest resolver of module %s failed; the request is treated as signed out.", module_id)
        return None
    if not (isinstance(got, tuple) and len(got) == 3 and all(isinstance(v, str) and v for v in got)):
        return None
    try:
        return Guest(valid_company_id(got[0]), got[1], got[2])
    except InvalidCompanyId:
        return None
