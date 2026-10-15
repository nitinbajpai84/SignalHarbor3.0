"""M2-P04 routes: the data catalogue (M2-16, 17, 18, 20, 24, 05). Declared in manifest.yaml and route_permissions.yaml.

The company and the person always come from the server session. Every route that returns rows goes through store.view() or store.export(),
which apply the governance rules on the server: a row the person is not named for comes back as {id, hidden} and is never in the Excel file.
"""
import functools
import logging

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response

from modules.m2_baseline.api.signed_guard import SignedGuard
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.store import catalogue as S
from modules.m2_baseline.store import governance as G
from modules.m2_baseline.store import technical as ST
from modules.m2_baseline.store.baseline import read_baseline
from sh_platform.plane import CrossCompanyError, PlaneStore

log = logging.getLogger(__name__)
router = APIRouter(route_class=SignedGuard)
BASE = "/baselines/{baseline_id}/catalogue"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_STATUS = {"not_found": 404, "invalid": 422, "conflict": 409, "read_only": 409, "contract_unreadable": 500}
BAD_BODY = "Those details could not be read. Please try again."


def _plain(status: int, error: str, message: str) -> JSONResponse:
    return JSONResponse({"error": error, "message": message}, status_code=status)


def guarded(fn):
    """Turns this area's failures into plain answers; nothing technical reaches the screen."""
    @functools.wraps(fn)
    async def inner(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except C.CatalogueError as e:
            return _plain(_STATUS.get(e.code, 409), e.code, e.message)
        except S.StoreError as e:
            return _plain(500, "unreadable", str(e))
        except (PermissionError, CrossCompanyError):
            return _plain(403, "forbidden", "Your company space could not be opened. Please ask your administrator.")
    return inner


def _plane(request: Request):
    try:
        return PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()
    except LookupError:
        raise PermissionError("no company space") from None


def _viewer(request: Request) -> C.Viewer:
    acct = request.app.state.account_store.get(request.state.account_id) or {}
    name = str(acct.get("display_name") or "")
    twins = [a for a in request.app.state.account_store.in_company(request.state.company_id)
             if C.norm(a.get("display_name") or "") == C.norm(name)]
    return C.Viewer(name, frozenset(request.state.roles), len(twins) > 1, request.state.account_id)


async def _body(request: Request) -> dict:
    try:
        body = await request.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        raise C.CatalogueError("invalid", BAD_BODY)
    return body


@router.get(BASE)
@guarded
async def read(request: Request, baseline_id: str):
    shown = await run_in_threadpool(S.view, _plane(request), baseline_id, _viewer(request))
    base = read_baseline(_plane(request), baseline_id) or {}
    gov = await run_in_threadpool(G.columns, _plane(request), baseline_id, _viewer(request))  # M2-E3: personal data, sensitive, who may see it
    tech = await run_in_threadpool(ST.columns, _plane(request), baseline_id, _viewer(request))  # M2-E1: the calculation and the inputs of each measure
    return {"baseline_id": baseline_id, "schema": C.schema(), "signed": base.get("state") == "signed", "governance": gov, "technical": tech, **shown}  # the screen shows its read-only banner


@router.post(BASE + "/refresh")
@guarded
async def refresh(request: Request, baseline_id: str):
    return await run_in_threadpool(S.refresh, _plane(request), baseline_id)


@router.post(BASE + "/{tab}/rows")
@guarded
async def add_row(request: Request, baseline_id: str, tab: str):
    body = await _body(request)
    cells = body.get("cells")
    if not isinstance(cells, dict):
        raise C.CatalogueError("invalid", BAD_BODY)
    who = _viewer(request).name
    new_id = await run_in_threadpool(S.add_row, _plane(request), baseline_id, tab, cells, who, _mark(body))
    return {"id": new_id}


@router.put(BASE + "/{tab}/rows/{row_id}")
@guarded
async def edit_row(request: Request, baseline_id: str, tab: str, row_id: str):
    body = await _body(request)
    cells = body.get("cells")
    if not isinstance(cells, dict):
        raise C.CatalogueError("invalid", BAD_BODY)
    viewer = _viewer(request)
    await run_in_threadpool(S.edit_row, _plane(request), baseline_id, tab, row_id, cells, viewer.name, _mark(body), viewer)
    return {"status": "saved"}


@router.post(BASE + "/conflicts/{conflict_id}/settle")
@guarded
async def settle(request: Request, baseline_id: str, conflict_id: str):
    body = await _body(request)
    viewer = _viewer(request)  # Lens never settles; the person signed in does, and is named in the record
    rec = await run_in_threadpool(S.settle, _plane(request), baseline_id, conflict_id, body.get("value"), viewer.name, str(body.get("note") or ""), viewer)
    return {"id": rec["id"], "state": rec["state"], "settled_by": rec["settled_by"]}


@router.post(BASE + "/suggest-fields")
@guarded
async def suggest_fields(request: Request, baseline_id: str):
    """Which KPIs a table's columns may feed, from the industry pack. Only names and types come in; every answer is a suggestion."""
    body = await _body(request)
    seen = body.get("columns")
    if not isinstance(seen, list) or len(seen) > 500 or not all(isinstance(c, dict) and isinstance(c.get("name"), str) and len(c["name"]) < 200 for c in seen):
        raise C.CatalogueError("invalid", BAD_BODY)
    shown = await run_in_threadpool(S.view, _plane(request), baseline_id, _viewer(request))
    kpi_ids = {C.row_id("kpis", k) for k in shown["kpis"] if not k.get(C.HIDDEN)}
    feeds, synonyms, label = _pack_matching(request)
    cols = [{"name": c["name"], "type": str(c.get("type") or "")[:40]} for c in seen]  # names and types only, never values
    names = {C.row_id("kpis", k): C.text_of(k.get("KPI name")) for k in shown["kpis"] if not k.get(C.HIDDEN)}  # only the measures this person may see
    out = C.match_columns(cols, feeds, synonyms, kpi_ids, names)
    gone = await run_in_threadpool(G.hidden_names, _plane(request), baseline_id, _viewer(request))  # a field this person may not see is not matched either (M2-E3)
    return {"label": label, "suggestions": [s for s in out if C.norm(s.get("column") or "") not in gone and C.norm(s.get("field") or "") not in gone]}


def _pack_matching(request: Request) -> tuple[dict, dict, str]:
    company = request.app.state.entitlements.company(request.state.company_id) or {}
    try:
        pack = request.app.state.packs.load(str(company.get("industry", "")))
    except ValueError:
        return {}, {}, ""
    got = []
    for name in ("feeds", "column_synonyms"):
        try:
            raw = pack.section(name) if name in pack.sections() else None
        except (KeyError, OSError, ValueError):
            raw = None
        inner = raw.get("feeds") if isinstance(raw, dict) else None
        got.append(inner if isinstance(inner, dict) else {})
    return got[0], got[1], pack.suggestion_label


@router.get(BASE + "/export")
@guarded
async def export(request: Request, baseline_id: str):
    data = await run_in_threadpool(S.export, _plane(request), baseline_id, _viewer(request))
    return Response(data, media_type=XLSX, headers={"Content-Disposition": 'attachment; filename="data-catalogue.xlsx"'})


def _mark(body: dict) -> str:
    return "guessed" if body.get("mark") == "guessed" else "stated"
