"""Spec 28: data sources and technical areas, the intent-side spelling: /api/intents/{id}/data-sources.

The work is done in modules/m2_baseline/api/data_sources.py (one operation table, two spellings; the module's own spelling is under
/baselines/{baseline_id}/data-sources). This file resolves the intent to its baseline (`refs.baseline_ids[0]`), checks the person's part in
the intent, and adds the substage: closing `data_sources` on **Done**. The kernel already reads the module's stores elsewhere (consume,
graph); nothing is copied here.

Other cards read through `list_sources(plane, intent_id, viewer=None)` (the strategic source map) and `intake_owners(plane, baseline_id)`
(module 3's intake plan asks the source owner first). The substage's own state lives in `data_sources.json` until `data_sources` is added to
the intent record's key set (store.KEYS); the record is never given a key the store would refuse.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Request

from modules.m2_baseline.api import data_sources as DS
from modules.m2_baseline.domain import catalogue as C
from sh_platform.intents import _plane, _viewer
from sh_platform.intents import clock as K
from sh_platform.intents import store as S
from sh_platform.profile import view as PV

router = APIRouter()
STAGE = "data_sources"
NO_BASELINE = "Not available yet. This intent has no baseline to hold its data sources."
intake_owners = DS.intake_owners


def _cviewer(v: PV.Viewer) -> C.Viewer:
    return C.Viewer(v.name, v.roles, v.shared_name, v.account_id)


def _intent(plane, viewer: PV.Viewer, intent_id: str) -> tuple[dict, str | None]:
    """The record and the viewer's tier. A person with no part in it, who is not the company admin, a source owner or the governance lead, gets 404."""
    rec = S.read_intent(plane, intent_id)
    tier = S.tier_of(rec, viewer, S.areas_of(plane, viewer)) if rec else None
    if rec is None or not (tier == "content" or {"company_admin", "owner", "approver"} & viewer.roles):
        raise DS.Refusal("not_found", "We could not find that intent.")
    return rec, tier


def baseline_of(rec: dict) -> str:
    ids = (rec.get("refs") or {}).get("baseline_ids") or []
    if not ids:
        raise DS.Refusal("not_found", NO_BASELINE)
    return str(ids[0])


def resolve(request: Request):
    plane, viewer = _plane(request), _viewer(request)
    rec, _tier = _intent(plane, viewer, request.path_params["intent_id"])
    if request.method != "GET" and rec.get("state") in ("closed", "cancelled"):
        raise DS.Refusal("read_only", "This intent is closed, so its data sources can no longer change.")
    organiser = PV.ADMIN in viewer.roles or S._named((rec.get("people") or {}).get("organiser"), viewer)
    return plane, baseline_of(rec), _cviewer(viewer), bool(organiser)


def _days(state: dict | None) -> int | None:
    """Working days from the substage's opening to Done, from data_sources.json's own stamps (`opened_at`, else `drafted_at`; `done_at`)."""
    opened = (state or {}).get("opened_at") or (state or {}).get("drafted_at")
    if not opened or not (state or {}).get("done_at"):
        return None  # shown as "Not available yet"
    return round(K.working_days_between(K.parse(opened), K.parse(state["done_at"])))


def _with_stage(op):
    """Wrap a table operation so its answer carries the days from open to done."""
    async def endpoint(req: Request):
        iid = req.path_params["intent_id"]

        def run_op(plane, bid, viewer, body=None, org=False, **kw):
            out = op(plane, bid, viewer, body=body, org=org, **kw)
            if op is DS.done:
                close_stage(plane, iid)
            state = DS.load(plane, bid)["state"]
            return {**out, "intent_id": iid, "stage": state, "days_to_done": _days(state)}
        return await DS.run(run_op, resolve)(req)
    return endpoint


def close_stage(plane, intent_id: str) -> None:
    """The organiser's Done writes `closed` and `closed_at` on the `data_sources` stage; an Initiative made before the stage was listed gets it added (R9)."""
    rec = S.read_intent(plane, intent_id)
    if rec is None or any(s.get("key") == STAGE and s.get("state") == "closed" for s in rec.get("stages") or []):
        return
    at = datetime.now(timezone.utc).isoformat()

    def change(r: dict) -> None:
        for s in r.setdefault("stages", []):
            if s.get("key") == STAGE:
                s.update(state="closed", closed_at=at)
                return
        r["stages"].append({"key": STAGE, "state": "closed", "closed_at": at})
    S.update_intent(plane, intent_id, rec["version"], change)


def list_sources(plane, intent_id: str, viewer: PV.Viewer | None = None) -> list[dict]:
    """The intent's sources, one dict each (id, name, system, format, frequency, personal, who_may_see, owners {business, data, source},
    state, fields, used_in). With a viewer: at that viewer's tier, a closed source as {id, restricted: true, label}. Without: every source
    (the kernel's own read, for the map; the caller masks per viewer with profile.view.sees_source). [] when there is no baseline yet."""
    rec = S.read_intent(plane, intent_id)
    ids = ((rec or {}).get("refs") or {}).get("baseline_ids") or []
    if not ids:
        return []
    bid = str(ids[0])
    if viewer is None:
        return DS.rows(plane, bid, C.Viewer("", frozenset(), False, None), everything=True)["rows"]
    got = DS.rows(plane, bid, _cviewer(viewer))
    return got["rows"] + [{"id": f"restricted-{n}", "restricted": True, "label": DS.RESTRICTED} for n in range(1, got["restricted"] + 1)]


def _register() -> None:
    base = "/api/intents/{intent_id}/data-sources"
    for method, suffix, name, op in DS.OPS:
        router.add_api_route(base + suffix, _with_stage(op) if name in ("read", "done") else DS.run(op, resolve),
                             methods=[method], name=f"intent_data_sources_{name}")


_register()
