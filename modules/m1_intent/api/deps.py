"""Shared helpers for the module's routes. The company and the person always come from the server session
(request.state, set by the sign-in middleware); nothing here reads them from a request."""
import functools
import logging
from collections.abc import Callable

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from modules.m1_intent.domain import contracts as C
from modules.m1_intent.domain.preparation import Offers
from modules.m1_intent.store.files import StoreError, WrongState
from modules.m1_intent.store.sessions import SessionStore
from sh_platform.plane import CrossCompanyError, PlaneStore

log = logging.getLogger(__name__)
NOT_FOUND = {"error": "not_found", "message": "We could not find that session."}
BAD_BODY = "Those details could not be read. Please try again."
BAD_READ = "That could not be read. Please try again."


def plain(status: int, error: str, message: str, **extra) -> JSONResponse:
    return JSONResponse({"error": error, "message": message, **extra}, status_code=status)


def _contract_broken(e: C.ContractError) -> JSONResponse:
    log.exception("a module 1 contract file is not valid")
    return plain(500, "settings_unreadable", "Session settings could not be read. Please ask your administrator.")


# The one table from the module's plain failures to plain answers. A route file passes only its own extras.
_ANSWERS: tuple[tuple[type | tuple, Callable], ...] = (
    (WrongState, lambda e: plain(409, "wrong_state", str(e))),
    (StoreError, lambda e: plain(500, "unreadable", str(e))),
    (C.ContractError, _contract_broken),
    ((PermissionError, CrossCompanyError), lambda e: plain(
        403, "forbidden", "Your company space could not be opened. Please ask your administrator.")),
)


def typed(request: Request, n: int = 1) -> None:
    """A route that took n free-text entries from a person says so here; `guarded` adds them to the session's counters."""
    request.state.m1_free_text = getattr(request.state, "m1_free_text", 0) + n


def _count(request, kwargs: dict, res) -> None:
    """LI-M1: every successful change a person makes inside a session is one action; the entries they typed are counted by
    `typed`. Counters only (domain: store/sessions.py `count`), never the content. A failed count never fails the request."""
    sid = kwargs.get("session_id")
    if not isinstance(request, Request) or not isinstance(sid, str) or request.method == "GET" or getattr(res, "status_code", 200) >= 400:
        return
    try:
        store(request).count(sid, 1, getattr(request.state, "m1_free_text", 0))
    except (StoreError, PermissionError, OSError):
        log.warning("the input counters could not be updated")


def guarded(*extra: tuple[type | tuple, Callable]):
    """Route decorator: turns the module's failures into plain answers; nothing technical reaches the screen.
    `extra` is (exception type, answer function) pairs, tried before the shared table."""
    table = (*extra, *_ANSWERS)

    def decorate(fn):
        @functools.wraps(fn)
        async def inner(*args, **kwargs):
            try:
                res = await fn(*args, **kwargs)
                await run_in_threadpool(_count, kwargs.get("request"), kwargs, res)
                return res
            except Exception as e:
                for kinds, answer in table:
                    if isinstance(e, kinds):
                        return answer(e)
                raise
        return inner
    return decorate


def not_found() -> JSONResponse:
    return JSONResponse(NOT_FOUND, status_code=404)


def contracts(request: Request) -> tuple[C.SessionSettings, C.CharterTemplates]:
    folder = getattr(request.app.state, "m1_contracts_dir", None)  # tests point this at a temporary copy
    return C.load_session_settings(folder), C.load_charter_templates(folder)


def store(request: Request) -> SessionStore:
    """The store of the signed-in company's own plane."""
    try:
        plane = PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()
    except (LookupError, CrossCompanyError, ValueError):
        raise PermissionError("no company space") from None
    return SessionStore(plane)


def north_offers(request: Request) -> tuple[Offers, dict]:
    """What North can offer this company, from its own industry's pack only. Counts and a label, never content."""
    company = request.app.state.entitlements.company(request.state.company_id) or {}
    pack = None
    try:
        pack = request.app.state.packs.load(str(company.get("industry", "")))
    except ValueError:
        pass  # an industry that cannot be a pack name has no pack
    problems: list = []
    if pack is not None and not pack.empty:
        try:
            raw = pack.section("problems")
            problems = [p for p in (raw or {}).get("problems", []) if isinstance(p, dict)] if isinstance(raw, dict) else []
        except (KeyError, OSError, ValueError):
            problems = []
    practice = any(isinstance(p.get("typical_actions"), dict) and p["typical_actions"].get("items") for p in problems)
    info = {"problem_library_available": bool(problems), "industry_practice_available": practice,
            "problem_count": len(problems), "suggestion_label": pack.suggestion_label if pack else None,
            "message": None if problems else (pack.message if pack is not None and pack.empty else
                                              "No industry knowledge is available yet for this industry. "
                                              "You can still work from your own company's information.")}
    return Offers(practice=practice, problem_library=bool(problems)), info


async def body_object(request: Request) -> dict | None:
    """The JSON body when it is an object, else None."""
    try:
        body = await request.json()
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


async def blocking(fn, *args):
    return await run_in_threadpool(fn, *args)
