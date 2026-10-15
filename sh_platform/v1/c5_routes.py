"""C5 routes: connectors for the data engineer seat (company_admin, analyst). Secrets never pass through: specs hold variable NAMES.

- `GET /api/v1/connectors` -> {connectors: [spec + health], kinds, egress_note}
- `PUT /api/v1/connectors/{id}` {kind, host, schedule, source_code, credentials, params, file_pattern} -> spec ;  `DELETE` -> {deleted}
- `POST /api/v1/connectors/{id}/test | dry-run | fetch` -> result (test and dry run are read only)
- `GET /api/v1/connectors/health` -> {connectors}
"""
from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Request

from sh_platform.profile.api import _plane
from sh_platform.v1 import e0c_landing as L
from sh_platform.v1.c5_connect import ops, spec as S
from sh_platform.v1.i2_routes import _json_body, _plain
from sh_platform.v1.seats import DATA_ENGINEER, require_seat

router = APIRouter()
BASE = "/api/v1/connectors"
CLIENTS: dict = {}  # tests put stub clients here; empty means the real ones


def _answer(fn):
    try:
        return fn()
    except L.Refused as e:
        return _plain(e.status, {403: "not_allowed", 404: "not_found"}.get(e.status, "invalid"), e.message)
    except PermissionError:
        return _plain(403, "forbidden", "Your company space could not be opened. Please ask your administrator.")


def _both(plane):
    h = {x["id"]: x for x in ops.health(plane)}
    return [{**s, "health": h.get(cid)} for cid, s in sorted(S.all_specs(plane).items())]


@router.get(BASE)
def listing(request: Request):
    require_seat(request, DATA_ENGINEER)
    plane = _plane(request)
    return _answer(lambda: {"connectors": _both(plane), "kinds": list(S.KINDS), "schedules": list(S.SCHEDULES),
                            "egress_note": "A connector can only reach hosts on the company's internet list, with the c5_connect switch on."})


@router.get(BASE + "/health")
def health(request: Request):
    require_seat(request, DATA_ENGINEER)
    plane = _plane(request)
    return _answer(lambda: {"connectors": ops.health(plane)})


@router.put(BASE + "/{cid}")
async def save(cid: str, request: Request):
    require_seat(request, DATA_ENGINEER)
    body = await _json_body(request, 16 * 1024)
    if not isinstance(body, dict):
        return body
    plane = _plane(request)
    return _answer(lambda: S.save(plane, cid, body))


@router.delete(BASE + "/{cid}")
def delete(cid: str, request: Request):
    require_seat(request, DATA_ENGINEER)
    plane = _plane(request)
    return _answer(lambda: (S.remove(plane, cid), {"deleted": cid})[1])


def _op(name):
    def route(cid: str, request: Request):
        require_seat(request, DATA_ENGINEER)
        plane = _plane(request)
        return _answer(lambda: getattr(ops, name)(plane, S.get(plane, cid), CLIENTS))
    return route


for _path, _name in (("test", "test"), ("dry-run", "dry_run"), ("fetch", "fetch")):
    router.post(f"{BASE}/{{cid}}/{_path}")(_op(_name))


# ---- Connect an API (c5_connect/api.py): fixed public providers; the spec itself is saved with PUT /connectors/{id} (kind "api")
API = "/api/v1/connect-api"


@router.get(API + "/providers")
def api_providers(request: Request):
    require_seat(request, DATA_ENGINEER)
    from sh_platform.v1.c5_connect import api
    return {"providers": api.catalogue(), "default_at": api.AT}


@router.post(API + "/test")
async def api_test(request: Request):
    """Test an unsaved choice: {provider, series}. Read only; nothing is written."""
    require_seat(request, DATA_ENGINEER)
    body = await _json_body(request, 4 * 1024)
    if not isinstance(body, dict):
        return body
    plane = _plane(request)
    from sh_platform.v1.c5_connect import api
    return await run_in_threadpool(_answer, lambda: ops.test(plane, api.clean_spec(body, "test"), CLIENTS))  # network waits off the event loop


@router.get(API + "/latest")
def api_latest(request: Request):
    """For Consume: newest value per live series with provider, observed date, outside and live flags."""
    require_seat(request, DATA_ENGINEER)
    plane = _plane(request)
    from sh_platform.v1.c5_connect import api
    return _answer(lambda: {"series": api.markers(plane)})
