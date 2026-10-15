"""Routes for the one interview (LI-INTERVIEW). Mounted by sh_platform/app.py; every route is declared in route_permissions.yaml.

Signed in: the organiser lists everyone with their status, starts or resumes anyone's interview and mints an invite link; a person starts,
answers and finishes only their own (their display name is the person's name). The company and the person come from the session.
Guest: /api/modules/interview/guest/* are `entry` routes with no session. The X-Interview-Token header names the company and the one
person; nothing in the request body can name another. A bad, expired or withdrawn link gets one plain answer."""
import logging
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.context_docs.api import _json_body, _plain
from sh_platform.egress.providers import ProviderError, build_model_client
from sh_platform.interview import engine, links
from sh_platform.memory.summarise import summarise_and_remember
from sh_platform.plane import CrossCompanyError, PlaneStore
from sh_platform.profile import view
from sh_platform.settings import load_model_env

log = logging.getLogger(__name__)
router = APIRouter()
ORGANISER = frozenset({"company_admin", "sponsor", "analyst"})
HEADER = "X-Session-Token"  # the header the UI client already sends for a guest; no module resolver is registered for "interview", so the kernel ignores it
BODY_LIMIT = 20_000
BAD_LINK = "This link is not valid any more. Please ask the person who sent it for a new one."
NOT_YOURS = "This interview is not yours."
NOT_FOUND = "We could not find that person."


class _Stop(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def _answer(fn):
    try:
        return fn()
    except _Stop as e:
        return _plain(e.status, e.code, e.message)
    except engine.Refused as e:
        return _plain(409, "refused", str(e))
    except (PermissionError, CrossCompanyError, LookupError):
        return _plain(403, "forbidden", "Your company space could not be opened. Please ask your administrator.")


def _plane(request: Request):
    try:
        return PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()
    except (LookupError, CrossCompanyError, ValueError):
        raise PermissionError("no company space") from None


def _model(request: Request, plane):
    """The gateway-backed model client of this company (copied from sh_platform/profile/api.py); tests plug a stub in as
    app.state.interview_model_factory."""
    factory = getattr(request.app.state, "interview_model_factory", None)
    override = getattr(request.app.state, "model_env", None)
    try:
        return factory(plane) if factory else build_model_client(plane, dict(override) if override is not None else load_model_env())
    except ProviderError:
        log.warning("the model settings are not valid")
        return None


def _company_name(request: Request, company_id: str) -> str:
    return str((request.app.state.entitlements.company(company_id) or {}).get("name") or "")


def _accounts(request: Request) -> list[dict]:
    return [a for a in request.app.state.account_store.in_company(request.state.company_id) if not a["disabled"]]


def _me(request: Request) -> tuple[str, bool]:
    """(the signed-in person's name, whether it is theirs alone: no other account of the company has the same name)."""
    name = str((request.app.state.account_store.get(request.state.account_id) or {}).get("display_name") or "")
    twins = [a for a in _accounts(request) if view.norm(a["display_name"]) == view.norm(name)]
    return name, bool(name) and len(twins) <= 1


def _person(request: Request, plane, pid: str, *, own_only: bool) -> dict:
    organiser = bool(ORGANISER & set(request.state.roles or []))
    name, mine = _me(request)
    person = engine.find(plane, pid, [a["display_name"] for a in _accounts(request)])
    if person is None:
        raise _Stop(404, "not_found", NOT_FOUND)
    me = mine and view.norm(person["name"]) == view.norm(name)
    if not (me or (organiser and not own_only)):
        raise _Stop(403, "forbidden", NOT_YOURS)
    return {**person, "self": bool(me)}


def _guest(request: Request) -> tuple:
    """(plane, person) for a live link token, else a plain refusal. The company and the person come from the token alone."""
    token = request.headers.get(HEADER, "")
    cid = links.company_of(token)
    if cid is None:
        raise _Stop(404, "bad_link", BAD_LINK)
    try:
        plane = PlaneStore(request.app.state.settings.data_root).plane_for(cid).ensure()
        pid = links.check(plane, token)
    except (LookupError, CrossCompanyError, ValueError, OSError):
        raise _Stop(404, "bad_link", BAD_LINK) from None
    person = engine.find(plane, pid, []) if pid else None
    if person is None:
        st = engine.load_state(plane, pid) if pid else None  # a person who is only an account name has a state but no profile row
        person = {"id": pid, "name": st["name"], "role": ""} if st else None
    if person is None:
        raise _Stop(404, "bad_link", BAD_LINK)
    return plane, person


def _remember(request: Request, plane, person: dict, was_done: bool, company_id: str) -> None:
    """MEM-2: a finished interview is summarised into North's memory of this profile person (the person is known: it is the interview's own).
    Only on the move to done; never raises."""
    st = engine.load_state(plane, person["id"])
    if was_done or not st or st["status"] != "done":
        return
    try:
        model = _model(request, plane)
        if model is not None:
            summarise_and_remember(plane, "north", person["id"], [f"{'North' if t['who'] == 'north' else 'Person'}: {t['text']}" for t in st["log"]],
                                   model=model, gate=request.app.state.entitlements, company_id=company_id,
                                   module_id="m1_intent", conversation="Interview")  # ponytail: entitled as M1; the interview has no module of its own
    except Exception:  # noqa: BLE001 - memory must never fail the interview
        log.warning("the memory of an interview could not be written", exc_info=True)


def _was_done(plane, person: dict) -> bool:
    return (engine.load_state(plane, person["id"]) or {}).get("status") == "done"


def _turn(plane, person: dict, body: dict, model, company: str) -> dict:
    if model is not None:
        engine.register_names(plane, company, [p["name"] for p in engine.people(plane)])
    engine.start(plane, person)
    return engine.answer(plane, person["id"], body, model, company)


def _row(plane, p: dict) -> dict:
    return {**p, "kind": (engine.load_state(plane, p["id"]) or {}).get("kind") or engine.kind_of(plane, p["name"]), **engine.status_of(plane, p["id"])}


async def _body(request: Request) -> dict:
    b = await _json_body(request, BODY_LIMIT)
    if isinstance(b, JSONResponse):
        raise _Stop(400, "bad_request", "That could not be read. Please try again.")
    return b


# ---- signed in -------------------------------------------------------------------------------------------------------------


@router.get("/api/interview")
def listing(request: Request):
    def work():
        plane = _plane(request)
        name, mine = _me(request)
        rows = engine.people(plane, [a["display_name"] for a in _accounts(request)])
        if not ORGANISER & set(request.state.roles or []):
            rows = [p for p in rows if mine and view.norm(p["name"]) == view.norm(name)]
        return {"people": [{**_row(plane, p), "self": mine and view.norm(p["name"]) == view.norm(name)} for p in rows], "organiser": bool(ORGANISER & set(request.state.roles or []))}
    return _answer(work)


@router.get("/api/interview/{person_id}")
def one(request: Request, person_id: str):
    def work():
        plane = _plane(request)
        p = _person(request, plane, person_id, own_only=False)
        st = engine.load_state(plane, p["id"])
        return engine.public(plane, st, own=p["self"]) if st else {"person": {"id": p["id"], "name": p["name"]}, "status": "not_started", "log": [], "card": None}
    return _answer(work)


@router.post("/api/interview/{person_id}/start")
async def start(request: Request, person_id: str):
    def work():
        plane = _plane(request)
        p = _person(request, plane, person_id, own_only=False)
        return engine.public(plane, engine.start(plane, p), own=p["self"])
    return await run_in_threadpool(_answer, work)


@router.post("/api/interview/{person_id}/answer")
async def post_answer(request: Request, person_id: str):
    try:
        body = await _body(request)
    except _Stop as e:
        return _plain(e.status, e.code, e.message)

    def work():
        plane = _plane(request)
        p = _person(request, plane, person_id, own_only=True)
        was = _was_done(plane, p)
        out = _turn(plane, p, body, _model(request, plane), _company_name(request, request.state.company_id))
        _remember(request, plane, p, was, request.state.company_id)
        return out
    return await run_in_threadpool(_answer, work)


@router.post("/api/interview/{person_id}/finish")
async def finish(request: Request, person_id: str):
    def work():
        plane = _plane(request)
        p = _person(request, plane, person_id, own_only=True)
        was = _was_done(plane, p)
        engine.finish(plane, p["id"])
        _remember(request, plane, p, was, request.state.company_id)
        return engine.public(plane, engine.load_state(plane, p["id"]), own=True)
    return await run_in_threadpool(_answer, work)


@router.post("/api/interview/{person_id}/link")
def invite(request: Request, person_id: str):
    """The organiser's invite link for one person. Shown once: only its hash is kept. Nothing is sent."""
    def work():
        if not ORGANISER & set(request.state.roles or []):
            raise _Stop(403, "forbidden", NOT_YOURS)
        plane = _plane(request)
        p = engine.find(plane, person_id, [a["display_name"] for a in _accounts(request)])
        if p is None:
            raise _Stop(404, "not_found", NOT_FOUND)
        engine.start(plane, p)  # keeps the person's name on file for a guest who is only an account name
        token = links.mint(plane, request.state.company_id, p["id"])
        return {"person": p["id"], "link": links.LINK.format(token=token) + "?for=" + quote(p["name"].split()[0] if p["name"].split() else "")}
    return _answer(work)


# ---- guest: one person's own interview, by link ------------------------------------------------------------------------------


@router.post("/api/modules/interview/guest/start")
async def guest_start(request: Request):
    def work():
        plane, p = _guest(request)
        return engine.public(plane, engine.start(plane, p), own=True)
    return await run_in_threadpool(_answer, work)


@router.post("/api/modules/interview/guest/answer")
async def guest_answer(request: Request):
    try:
        body = await _body(request)
    except _Stop as e:
        return _plain(e.status, e.code, e.message)

    def work():
        plane, p = _guest(request)
        cid = links.company_of(request.headers.get(HEADER, "")) or ""
        was = _was_done(plane, p)
        out = _turn(plane, p, body, _model(request, plane), _company_name(request, cid))
        _remember(request, plane, p, was, cid)
        return out
    return await run_in_threadpool(_answer, work)


@router.post("/api/modules/interview/guest/finish")
async def guest_finish(request: Request):
    def work():
        plane, p = _guest(request)
        was = _was_done(plane, p)
        engine.finish(plane, p["id"])
        _remember(request, plane, p, was, links.company_of(request.headers.get(HEADER, "")) or "")
        return engine.public(plane, engine.load_state(plane, p["id"]), own=True)
    return await run_in_threadpool(_answer, work)
