"""IC-3c routes: the governed state of each measure. Declared in manifest.yaml and route_permissions.yaml (default deny). The person and
company come from the session; the filtering and the who-may-confirm rule are the store's. A signed baseline refuses writes (SignedGuard)."""
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool

from modules.m2_baseline.api.catalogue import _body, _plain, _plane, _viewer, guarded
from modules.m2_baseline.api.signed_guard import SignedGuard
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.store import governed as S

import logging

from modules.m2_baseline.agent import pack_text as P
from modules.m2_baseline.store import baseline as B
from modules.m2_baseline.store import catalogue as SC

log = logging.getLogger(__name__)
LENS = C.Viewer("Lens", frozenset({"company_admin"}))  # the draft covers every measure; what a person reads back is filtered for them
router = APIRouter(route_class=SignedGuard)
BASE = "/baselines/{baseline_id}/governed"


def ensure_draft(request: Request, baseline_id: str) -> None:
    """Lens's governed draft for the baseline, from the stored governance, the profile and the pack's measures. Idempotent: a stated cell stays.
    Never stops the caller: a baseline that cannot take a draft (signed, unreadable) is simply left as it is."""
    company = request.app.state.entitlements.company(request.state.company_id) or {}
    try:
        S.draft_all(_plane(request), baseline_id, LENS, P.load_guidance(request.app.state.packs, company.get("industry")).kpis)
    except (C.CatalogueError, B.Locked, B.StoreError, SC.StoreError, OSError, ValueError) as e:
        log.warning("the governed draft was skipped for baseline %s: %s", baseline_id, type(e).__name__)


@router.get(BASE)
@guarded
async def read(request: Request, baseline_id: str):
    if not await run_in_threadpool(S.exists, _plane(request), baseline_id):  # the first look drafts it
        await run_in_threadpool(ensure_draft, request, baseline_id)
    return await run_in_threadpool(S.governed_for, _plane(request), baseline_id, _viewer(request))


@router.post(BASE + "/{measure_id}/confirm")
@guarded
async def confirm(request: Request, baseline_id: str, measure_id: str):
    """body: {field, value}. Only the person named for that field (store.confirm_field); one plain sentence otherwise."""
    body = await _body(request)
    if not isinstance(body.get("field"), str):
        raise C.CatalogueError("invalid", "Choose which part to confirm.")
    try:
        entry = await run_in_threadpool(S.confirm_field, _plane(request), baseline_id, measure_id, body["field"], body.get("value"), _viewer(request))
    except C.CatalogueError as e:
        if e.code != "forbidden":
            raise
        return _plain(403, e.code, e.message)
    return {"measure_id": measure_id, "complete": S.G.is_complete(entry), "state": entry}
