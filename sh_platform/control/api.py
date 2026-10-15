"""Control panel routes (IC-5a). Every route is declared in route_permissions.yaml (default deny):
/api/control/* is super_admin only and returns directory facts, never plane content; /api/company/settings*
and /api/company/egress-log are company_admin only and always act on the session's own company.
Nothing is cached: each request reads the files again, so a switch shows on the next request."""
import json
import logging
import re
from pathlib import Path

import yaml
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.egress.policy import EgressPolicy
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CrossCompanyError, PlaneStore, valid_company_id

log = logging.getLogger(__name__)
router = APIRouter()
PROVIDERS_PATH = Path(__file__).resolve().parent / "providers.yaml"
LOG_CAP = 200
# a whitelist: the payload and its hash never leave the plane
LOG_FIELDS = ("time", "module", "kind", "host", "decision", "reason_code", "bytes", "trace_id", "masked")  # AQF10-05: the run's id; TS1c-05: names masked (a count)
EGRESS_KEYS = ("internet", "connectors", "cloud_push")
_DOMAIN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+")


def _plain(status: int, error: str, message: str) -> JSONResponse:
    return JSONResponse({"error": error, "message": message}, status_code=status)


def _bad(message: str = "That value is not valid.") -> JSONResponse:
    return _plain(400, "bad_request", message)


def _unknown_company() -> JSONResponse:
    return _plain(404, "unknown_company", "That company does not exist.")


async def _body(request: Request) -> dict | JSONResponse | None:
    """The JSON object; a 415 response for a wrong content type (as the login route); None when unreadable."""
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        return _plain(415, "unsupported_media_type", "Send JSON.")
    try:
        raw = await request.body()
        data = json.loads(raw) if len(raw) <= 8192 else None
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def allowed_providers() -> dict[str, list[str]]:
    data = yaml.safe_load(PROVIDERS_PATH.read_text(encoding="utf-8")) or {}
    return {p["id"]: list(p["models"]) for p in data.get("providers", [])}


def _provider_file(request: Request) -> Path:
    return Path(request.app.state.settings.data_root) / "_control" / "providers.json"


def _provider_rows(request: Request) -> dict:
    return read_json_strict(_provider_file(request), dict) or {}


def _plane(request: Request):
    try:
        return PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()
    except (LookupError, CrossCompanyError, ValueError):
        return None


def _own(request: Request) -> bool:
    """A company admin may only name their own company; any other id is a 404."""
    asked = request.query_params.get("company_id")
    return asked is None or asked == request.state.company_id


# -- super admin
@router.get("/api/control/catalogue")
def catalogue(request: Request):
    cat = request.app.state.entitlements.catalogue
    return {"modules": [m.public() for m in cat.modules], "centres": [c.public() for c in cat.centres]}


def _domains_of(request: Request, cid: str) -> list[str]:
    """The email allowlist (a setting, not plane content) for the directory view; empty when none is set."""
    try:
        plane = PlaneStore(request.app.state.settings.data_root).plane_for(cid).ensure()
        d = _policy(request, plane)._read().get("email_domains")
    except (LookupError, CrossCompanyError, ValueError, OSError):
        return []
    return [x for x in d if isinstance(x, str)] if isinstance(d, list) else []


@router.get("/api/control/companies")
def companies(request: Request):
    es, accounts = request.app.state.entitlements, request.app.state.account_store
    out = []
    for row in es.list_companies():
        cid, sw = row["company_id"], es.switches(row["company_id"])
        people = accounts.in_company(cid)
        out.append({"id": cid, "display": row.get("name"), "industry": row.get("industry"),
                    "centres_on": [c for c, on in sw["centres"].items() if on],
                    "modules_on": [m for m, on in sw["modules"].items() if on],
                    "email_domains": _domains_of(request, cid),
                    "accounts": {"total": len(people), "active": sum(1 for a in people if not a["disabled"])}})
    return {"companies": out}


@router.post("/api/control/companies")
async def create_company(request: Request):
    body = await _body(request)
    if isinstance(body, JSONResponse):
        return body
    if body is None or not all(isinstance(body.get(k), str) for k in ("id", "display", "industry")):
        return _bad('Send {"id", "display", "industry"} as text.')
    try:
        rec = await run_in_threadpool(request.app.state.entitlements.create_company,
                                      body["id"], body["display"], body["industry"])
    except FileExistsError:
        return _plain(409, "exists", "That company already exists.")
    except (ValueError, TypeError):
        return _bad("The id, display name or industry is not valid.")
    return JSONResponse({"id": rec["company_id"], "display": rec["name"], "industry": rec["industry"]}, status_code=201)


async def _switch(request: Request, company_id: str, setter, thing: str):
    body = await _body(request)
    if isinstance(body, JSONResponse):
        return body
    if body is None or not isinstance(body.get("on"), bool):
        return _bad('Send {"on": true} or {"on": false}.')
    try:
        await run_in_threadpool(setter, company_id, thing, body["on"])
    except LookupError:
        return _unknown_company()
    except ValueError as e:  # an invalid company id, or an unknown centre or module
        return _plain(404, "unknown_item", "That does not exist.") if "unknown" in str(e) else _unknown_company()
    return {"company_id": company_id, "id": thing, "on": body["on"]}


@router.put("/api/control/companies/{company_id}/centres/{centre_id}")
async def put_centre(company_id: str, centre_id: str, request: Request):
    return await _switch(request, company_id, request.app.state.entitlements.set_centre, centre_id)


@router.put("/api/control/companies/{company_id}/modules/{module_id}")
async def put_module(company_id: str, module_id: str, request: Request):
    return await _switch(request, company_id, request.app.state.entitlements.set_module, module_id)


@router.get("/api/control/providers")
def get_providers(request: Request):
    rows, es = _provider_rows(request), request.app.state.entitlements
    return {"allowed": allowed_providers(),
            "companies": {r["company_id"]: rows.get(r["company_id"]) for r in es.list_companies()}}


@router.put("/api/control/providers")
async def put_provider(request: Request):
    body = await _body(request)
    if isinstance(body, JSONResponse):
        return body
    if body is None or not all(isinstance(body.get(k), str) for k in ("company_id", "provider", "model")):
        return _bad('Send {"company_id", "provider", "model"} as text.')
    if body["model"] not in allowed_providers().get(body["provider"], ()):
        return _bad("That provider and model are not in the allowed list.")
    try:
        valid_company_id(body["company_id"])
    except ValueError:
        return _unknown_company()
    if request.app.state.entitlements.company(body["company_id"]) is None:
        return _unknown_company()
    path = _provider_file(request)
    with lock_for(path):
        write_json_atomic(path, {**_provider_rows(request),
                                 body["company_id"]: {"provider": body["provider"], "model": body["model"]}})
    return {"company_id": body["company_id"], "provider": body["provider"], "model": body["model"]}


# -- company admin
def _policy(request: Request, plane) -> EgressPolicy:
    return EgressPolicy(plane, request.app.state.settings.egress_default)


def _settings(request: Request, plane) -> dict:
    es, pol = request.app.state.entitlements, _policy(request, plane)
    on = es.enabled_modules(request.state.company_id)
    # internet reads as on only when every enabled module is allowed (fail closed on a mixed state)
    domains = pol._read().get("email_domains")  # the allowlist the email gateway reads; empty means the company's own domains
    return {"email_domains": [d for d in domains if isinstance(d, str)] if isinstance(domains, list) else [],
            "centres": [c for c, on in es.switches(request.state.company_id)["centres"].items() if on],
            "egress": {"internet": bool(on) and all(pol.is_internet_allowed(m) for m in on),
                       "connectors": pol.flag("connectors"),
                       "cloud_push": False,  # never on from this route: it needs two named approvers (later)
                       "cloud_push_requested": pol.flag("cloud_push_requested")}}


@router.get("/api/company/settings")
def get_settings(request: Request):
    plane = _plane(request) if _own(request) else None
    return _settings(request, plane) if plane else _unknown_company()


@router.put("/api/company/settings/egress")
async def put_egress(request: Request):
    if not _own(request):
        return _unknown_company()
    body = await _body(request)
    if isinstance(body, JSONResponse):
        return body
    domains = body.pop("email_domains", None) if body else None
    if domains is not None:
        domains = [d.strip().lower() for d in domains] if isinstance(domains, list) and all(isinstance(d, str) for d in domains) else None
        if domains is None or not all(_DOMAIN.fullmatch(d) for d in domains):
            return _bad("Email domains must be a list of names such as example.com.")
    if (not body and domains is None) or set(body) - set(EGRESS_KEYS) or not all(isinstance(v, bool) for v in body.values()):
        return _bad('Send any of {"internet", "connectors", "cloud_push"} as true or false, or "email_domains" as a list.')
    plane = _plane(request)
    if plane is None:
        return _unknown_company()
    pol, es = _policy(request, plane), request.app.state.entitlements

    def work():
        if domains is not None:
            pol._update(email_domains=sorted(set(domains)))
        if "internet" in body:
            for m in es.enabled_modules(request.state.company_id):  # a module that is off stays internet-off
                pol.set_internet(m, body["internet"])
        if "connectors" in body:
            pol.set_flag("connectors", body["connectors"])
        if "cloud_push" in body:  # a request only: stored, never on
            pol.set_flag("cloud_push_requested", body["cloud_push"])
    await run_in_threadpool(work)
    return _settings(request, plane)


@router.get("/api/company/egress-log")
def egress_log(request: Request, limit: int = 50):
    plane = _plane(request) if _own(request) else None
    if plane is None:
        return _unknown_company()
    limit = max(1, min(limit, LOG_CAP))
    try:
        lines = (plane.area("context") / "egress_log.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    entries = []
    for line in reversed(lines):  # newest first
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            entries.append({k: rec.get(k) for k in LOG_FIELDS})
        if len(entries) >= limit:
            break
    return {"entries": entries}
