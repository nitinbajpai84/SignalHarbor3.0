"""Routes for the company profile and "Bring what you have" (LI-PROFILE). Mounted by sh_platform/app.py; each route is declared in
route_permissions.yaml for the company admin, the sponsor and the analyst. The company and the person come from the session only."""
import base64
import binascii
import logging

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.context_docs import reader as docreader
from sh_platform.context_docs.api import MAX_BODY, _json_body, _plain
from sh_platform.egress.providers import ProviderError, build_model_client
from sh_platform.plane import CrossCompanyError, PlaneStore
from sh_platform.profile import asks, links, reader, store, view
from sh_platform.settings import load_model_env

log = logging.getLogger(__name__)
router = APIRouter()
NOT_FOUND = "We could not find that."


def _plane(request: Request):
    try:
        plane = PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()
        from sh_platform.v1 import wh
        wh.use(plane)  # this request works in this company's cycle date
        return plane
    except (LookupError, CrossCompanyError, ValueError):
        raise PermissionError("no company space") from None


def _name(request: Request) -> str:
    st = request.app.state
    return str((st.account_store.get(request.state.account_id) or {}).get("display_name") or "")


def _viewer(request: Request) -> view.Viewer:
    st, name = request.app.state, _name(request)
    twins = [a for a in st.account_store.in_company(request.state.company_id) if view.norm(a.get("display_name")) == view.norm(name)]
    return view.Viewer(name, frozenset(request.state.roles or []), len(twins) > 1, request.state.account_id)


def _lookup(request: Request):
    """Suggestions by email are made only when a company admin did the read or upload."""
    if "company_admin" not in (request.state.roles or []):
        return None
    return links.lookup_for(request.app.state.account_store, request.state.company_id)


def _model(request: Request, plane):
    factory = getattr(request.app.state, "lens_model_factory", None)  # tests plug a stub in here
    override = getattr(request.app.state, "model_env", None)
    try:
        return factory(plane) if factory else build_model_client(plane, dict(override) if override is not None else load_model_env())
    except ProviderError:
        log.warning("the model settings are not valid")
        return None


def _answer(fn):
    try:
        return fn()
    except docreader.Refusal as e:
        return _plain(e.status, "refused", str(e))
    except FileNotFoundError:
        return _plain(404, "not_found", NOT_FOUND)
    except links.LinkRefusal as e:
        return _plain(e.status, "refused", str(e))
    except (PermissionError, CrossCompanyError):
        return _plain(403, "forbidden", "Your company space could not be opened. Please ask your administrator.")


@router.get("/api/profile")
def get_profile(request: Request):
    return _answer(lambda: view.read(_plane(request), _viewer(request)))


@router.get("/api/profile/readiness")
def get_readiness(request: Request):
    def work():
        plane = _plane(request)
        return {**reader.readiness(plane), "asks": asks.missing(plane, _name(request) or "your organiser")}
    return _answer(work)


@router.post("/api/profile/read")
async def read_again(request: Request):
    def work():
        plane = _plane(request)
        return {"results": reader.read_all(plane, _model(request, plane), lookup=_lookup(request)), **reader.readiness(plane)}
    return await run_in_threadpool(_answer, work)


@router.post("/api/profile/inputs/{group}/upload")
async def upload(request: Request, group: int):
    body = await _json_body(request, MAX_BODY)
    if isinstance(body, JSONResponse):
        return body
    try:
        data = base64.b64decode(str(body.get("data", "")), validate=True)
    except (binascii.Error, ValueError):
        return _plain(400, "bad_request", "That file could not be read. Please try again.")

    def work():
        plane = _plane(request)
        reader.group(group)
        out = reader.add_upload(plane, group, _name(request) or "A team member", str(body.get("filename") or ""), data,
                                _model(request, plane), restricted=body.get("restricted") is True, system=str(body.get("system") or ""), lookup=_lookup(request))
        return {**out, **reader.readiness(plane)}
    return await run_in_threadpool(_answer, work)


@router.post("/api/profile/inputs/{group}/ask")
def ask(request: Request, group: int):
    """Nira's request for one missing group, with a fresh upload link. Nothing is sent: the text is for the organiser to copy."""
    def work():
        plane = _plane(request)
        g = reader.group(group)
        who = asks.holder(store.load(plane), g)
        text = asks.email_text(who and who["name"], _name(request) or "your organiser", g["title"])
        return {"group": group, "holder": who, "email": asks.with_link(text, asks.mint(plane, group, person=(who or {}).get("name") or ""))}
    return _answer(work)


@router.get("/api/profile/links")
def get_links(request: Request):
    """The admin's picker: each person with the account they are linked to, and the company's enabled accounts by name."""
    return _answer(lambda: links.listing(_plane(request), request.app.state.account_store, request.state.company_id))


@router.put("/api/profile/people/{pid}/account")
async def put_link(request: Request, pid: str):
    body = await _json_body(request, 4096)
    if isinstance(body, JSONResponse):
        return body
    account = body.get("account_id", "")
    if "account_id" not in body or not (account is None or isinstance(account, str) and account.strip()):
        return _plain(400, "bad_request", "Pick an account from the list, or choose none.")

    def work():
        links.set_link(_plane(request), request.app.state.account_store, request.state.company_id, pid, account, _name(request))
        return {"ok": True}
    return _answer(work)
