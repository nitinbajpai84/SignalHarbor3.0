"""M2-E3 routes: the governance view of a baseline. Declared in manifest.yaml and route_permissions.yaml (default deny).

The company and the person always come from the server session. The view is derived from where governance is stored (the work list's
measures, the catalogue's sources and fields), filtered for the person asking; changing who may see a measure stays on the work list
route (rank rules unchanged). A signed baseline refuses every write (SignedGuard)."""
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool

from modules.m2_baseline.api.catalogue import _body, _plane, _viewer, guarded
from modules.m2_baseline.api.signed_guard import SignedGuard
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import governance_view as GV
from modules.m2_baseline.store import governance as S
from modules.m2_baseline.store.baseline import read_baseline

router = APIRouter(route_class=SignedGuard)
BASE = "/baselines/{baseline_id}/governance"


def _parts(request: Request) -> dict:
    company = request.app.state.entitlements.company(request.state.company_id) or {}
    return GV.pack_parts(request.app.state.packs, str(company.get("industry", "")))


@router.get(BASE)
@guarded
async def read(request: Request, baseline_id: str):
    plane, parts = _plane(request), _parts(request)
    shown = await run_in_threadpool(S.view, plane, baseline_id, _viewer(request), parts)
    base = read_baseline(plane, baseline_id) or {}
    return {"baseline_id": baseline_id, "signed": base.get("state") == "signed", "pack_label": parts["label"], **shown}


@router.put(BASE + "/fields/{field_id}")
@guarded
async def restrict_field(request: Request, baseline_id: str, field_id: str):
    """body: {may_see: [names]}. Only the organiser or sponsor (the route's roles). An empty list makes the field follow its measures again."""
    body = await _body(request)
    await run_in_threadpool(S.set_field, _plane(request), baseline_id, field_id, body.get("may_see"), _viewer(request))
    return {"status": "saved"}


@router.post(BASE + "/proposals/confirm")
@guarded
async def confirm_proposals(request: Request, baseline_id: str):
    """body: {field_ids: [..]} or {only_not_personal: true}. Turns Lens's proposals into the person's own decision; never replaces one."""
    body = await _body(request)
    if "field_ids" not in body and body.get("only_not_personal") is not True:
        raise C.CatalogueError("invalid", "Choose which proposals to confirm.")
    return await run_in_threadpool(S.confirm, _plane(request), baseline_id, _viewer(request), _parts(request), body.get("field_ids"), body.get("only_not_personal") is True)
