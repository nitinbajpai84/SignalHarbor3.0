"""Build room 0 (the gap analysis, the Moment of truth) when no hand-over is named in the address.

`GET /api/company/build/gap-analysis`: the Initiatives Build may start from: build-ready (or handed over), or closed with `links.build`; each with
its organiser, the check's n of 7 and whether this viewer may start it. `POST /api/company/build/gap-analysis/{intent_id}/start`: starts (or
reuses) module 3's assessment for the newest signed baseline and names it on the Initiative (`refs.assessment_ids`). Records read by path;
a title the viewer may not open reads "An Initiative you may not open" (05)."""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.intents import store as S
from sh_platform.profile.api import _plane, _viewer
from sh_platform.profile.view import norm

log = logging.getLogger(__name__)
router = APIRouter()
BUILD_ROLES = frozenset({"company_admin", "analyst"})
CHAIN_ROLES = ("architect", "developer", "head_of_department")
HIDDEN = "An Initiative you may not open"


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": code, "message": message}, status_code=status)


def _eligible(rec: dict) -> bool:
    if rec.get("type") != "initiative" or rec.get("state") == "draft":
        return False
    br = (rec.get("build_ready") or {}).get("state")
    return bool(rec.get("build_handoff")) or br in ("ready", "handed_over") or (rec.get("state") == "closed" and bool((rec.get("links") or {}).get("build")))


def _n_ok(plane, rec: dict, viewer) -> int:
    lines = (rec.get("build_ready") or {}).get("lines")
    if lines:
        return sum(1 for ln in lines if ln.get("ok"))
    from sh_platform.intents.build_ready import compute  # never stored (a seeded or closed Initiative): computed now, read only
    try:
        return sum(1 for ln in compute(plane, rec, viewer)["lines"] if ln["ok"])
    except (OSError, ValueError, KeyError, TypeError):
        log.warning("the build-ready check could not be computed for room 0", exc_info=True)
        return 0


def may_start(plane, rec: dict, viewer) -> bool:
    """Build roles (company admin, analyst, the chain's architect, data engineer or head of department) or the Initiative's organiser."""
    if BUILD_ROLES & set(viewer.roles):
        return True
    org = (rec.get("people") or {}).get("organiser") or {}
    if (org.get("account_id") and org["account_id"] == viewer.account_id) or (org.get("name") and norm(org["name"]) == norm(viewer.name) and not viewer.shared_name):
        return True
    from sh_platform.build import chain
    try:
        ppl = chain.people_of(plane, rec)
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return any(chain._is(viewer, (ppl.get(r) or {}).get("name")) for r in CHAIN_ROLES)


def candidates(plane, viewer) -> list[dict]:
    areas = S.areas_of(plane, viewer)
    out = []
    for r in S.read_index(plane):
        if r.get("type") != "initiative":
            continue
        try:
            rec = S.read_intent(plane, r["id"]) or {}
        except S.Unreadable:
            continue
        if not _eligible(rec):
            continue
        tier = S.tier_of(rec, viewer, areas)
        if tier is None:
            continue
        open_ = tier != "exists"
        aid = ((rec.get("refs") or {}).get("assessment_ids") or [None])[-1]
        out.append({"id": rec["id"] if open_ else None, "title": rec.get("title") if open_ else HIDDEN,
                    "organiser": ((rec.get("people") or {}).get("organiser") or {}).get("name") if open_ else None,
                    "state": rec.get("state"), "handed_over": bool(rec.get("build_handoff")), "n_ok": _n_ok(plane, rec, viewer) if open_ else None, "of": 7,
                    "assessment_id": aid if open_ else None, "may_start": open_ and not aid and may_start(plane, rec, viewer),
                    "href": f"/centre/build/gap-analysis?from={rec['id']}" if open_ else None, "updated_at": rec.get("updated_at")})
    return sorted(out, key=lambda x: str(x.get("updated_at") or ""), reverse=True)


@router.get("/api/company/build/gap-analysis")
def get_gap_analysis(request: Request):
    try:
        plane, viewer = _plane(request), _viewer(request)
    except PermissionError:
        return _err(403, "forbidden", "This company space cannot be opened.")
    if "super_admin" in viewer.roles:  # R6
        return _err(403, "forbidden", "The Build centre is not open to you.")
    return {"initiatives": [{k: v for k, v in c.items() if k != "updated_at"} for c in candidates(plane, viewer)],
            "build_ready_href": "/centre/intent?type=initiative"}


@router.post("/api/company/build/gap-analysis/{intent_id}/start")
def post_gap_analysis_start(request: Request, intent_id: str):
    from modules.m3_connect.domain import inputs as I
    from modules.m3_connect.store import assessment as A
    try:
        plane, viewer = _plane(request), _viewer(request)
    except PermissionError:
        return _err(403, "forbidden", "This company space cannot be opened.")
    try:
        rec = S.read_intent(plane, intent_id)
    except S.Unreadable:
        rec = None
    if not rec or "super_admin" in viewer.roles or S.tier_of(rec, viewer, S.areas_of(plane, viewer)) in (None, "exists"):
        return _err(404, "intent_not_found", "We could not find that Initiative.")
    if not _eligible(rec):
        return _err(409, "not_build_ready", "This Initiative is not build-ready yet.")
    if not may_start(plane, rec, viewer):
        return _err(403, "forbidden", "Only the organiser or the Build team can start the gap analysis.")
    try:
        made, _ = A.create(plane, I.latest_signed_baseline(plane), viewer.name)
    except A.NoSignedBaseline as e:
        return _err(409, "no_baseline", str(e))
    aid = made["id"]

    def change(r: dict) -> None:
        refs = r.setdefault("refs", {})
        if aid not in (refs.get("assessment_ids") or []):
            refs["assessment_ids"] = [*(refs.get("assessment_ids") or []), aid]
    try:
        S.update_intent(plane, intent_id, rec["version"], change)
    except S.VersionConflict:
        return _err(409, "intent_conflict", "Someone changed this Initiative just now. Try again.")
    return {"assessment_id": aid, "href": f"/centre/build/gap-analysis?from={intent_id}"}
