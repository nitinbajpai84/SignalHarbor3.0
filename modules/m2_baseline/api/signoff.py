"""M2-P05 routes: the review screen, owner confirmations, sponsor acceptance, countersign, new versions, the audit trail and the
hand-off record (M2-23, M2-25, M2-26, M2-28, X-08). Declared in manifest.yaml. The company and the person always come from the
server session; nothing here reads them from a request."""
import copy
import logging
from datetime import date
from functools import wraps

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse, Response

from modules.m2_baseline.api.catalogue import _viewer
from modules.m2_baseline.api.signed_guard import SignedGuard
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import handoff as H
from modules.m2_baseline.domain import worklist as W
from modules.m2_baseline.domain.readiness import ContractError
from modules.m2_baseline.domain.signoff import SignoffError, slot_for
from modules.m2_baseline.store import bundle as BUNDLE
from modules.m2_baseline.store import documents as DOC
from modules.m2_baseline.store import gate as GATE
from modules.m2_baseline.store.signoff import SignoffStore, StoreError, latest_baseline_outcome, read_kpis
from sh_platform.perf import cached
from sh_platform.plane import CrossCompanyError, PlaneStore

log = logging.getLogger(__name__)
router = APIRouter(route_class=SignedGuard)
BASE = "/baselines/{baseline_id}"
_STATUS = {"invalid": 422, "no_account": 403, "restricted": 403, "locked": 409, "not_your_part": 409, "no_owner": 409}  # every other code is a 409 too
NOT_FOUND = {"error": "not_found", "message": "We could not find that baseline or measure."}


def _plain(status: int, error: str, message: str) -> JSONResponse:
    return JSONResponse({"error": error, "message": message}, status_code=status)


def guarded(fn):
    """Turns the module's failures into plain answers; nothing technical reaches the screen."""
    @wraps(fn)
    def inner(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except SignoffError as e:
            return _plain(_STATUS.get(e.code, 409), e.code, e.message)
        except LookupError:
            return JSONResponse(NOT_FOUND, status_code=404)
        except StoreError as e:
            return _plain(500, "unreadable", str(e))
        except C.CatalogueError as e:  # the catalogue could not be read for the gate: nothing is signed or changed
            return _plain(500, "unreadable", e.message)
        except ContractError:
            log.exception("a module 2 sign-off contract file is not valid")
            return _plain(500, "settings_unreadable", "Sign-off settings could not be read. Please ask your administrator.")
        except (PermissionError, CrossCompanyError):
            return _plain(403, "forbidden", "Your company space could not be opened. Please ask your administrator.")
    return inner


def _plane(request: Request):
    try:
        return PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()
    except (LookupError, CrossCompanyError, ValueError):
        raise PermissionError("no company space") from None


def _store(request: Request) -> SignoffStore:
    sponsors = [(a["display_name"], a["account_id"]) for a in request.app.state.account_store.in_company(request.state.company_id)
                if "sponsor" in a["roles"] and not a["disabled"]]
    return SignoffStore(_plane(request), contracts_dir=getattr(request.app.state, "m2_contracts_dir", None), sponsors=sponsors)


def _who(request: Request) -> str:
    """The signed-in person's display name, for showing. Identity is the account id (see _me)."""
    return _me(request)[1]


def _me(request: Request) -> tuple[str, str]:
    """(account id, display name) of this company's signed-in account; refuses when it cannot be found."""
    acct = request.app.state.account_store.get(request.state.account_id)
    if not acct or acct.get("company_id") != request.state.company_id or not str(acct.get("display_name") or "").strip():
        raise SignoffError("no_account", "We could not confirm who you are. Please sign in again.")
    return acct["account_id"], str(acct["display_name"])


def _people(request: Request) -> list[dict]:
    return [{"account_id": a["account_id"], "display_name": a["display_name"]}
            for a in request.app.state.account_store.in_company(request.state.company_id)]


def _is_sponsor(request: Request, store: SignoffStore) -> bool:
    return bool(set(request.state.roles) & set(store.contract["sponsor_roles"]))


def _seen(request: Request, store: SignoffStore, baseline_id: str) -> set[str]:
    """The measures the signed-in person may see (the work list's rule, as requests and the process map use it). Everything
    about any other measure is left out of every answer here, and an action on one is "not found"."""
    acct = request.app.state.account_store.get(request.state.account_id) or {}
    return W.visible_ids([k for k in read_kpis(_plane(request), baseline_id) if isinstance(k, dict) and k.get("id")],
                         str(acct.get("display_name") or ""), request.state.account_id, "company_admin" in (request.state.roles or []))


def _known(request: Request, store: SignoffStore, baseline_id: str, kpi_id) -> None:
    """P3: a measure that exists but is hidden from the asker is refused plainly (403, no name); one that does not exist is not found.
    Existence was already public (the work list lists every restricted measure as a stub), so this tells nobody more."""
    if not isinstance(kpi_id, str) or kpi_id not in _seen(request, store, baseline_id):
        if isinstance(kpi_id, str) and any(isinstance(k, dict) and k.get("id") == kpi_id for k in read_kpis(_plane(request), baseline_id)):
            raise SignoffError("restricted", W.RESTRICTED_REFUSAL)
        raise LookupError("no measure")


def _full(request: Request, store: SignoffStore, baseline_id: str) -> dict:
    """The review view, plus who is looking: what they may sign (the screen shows only buttons that can work)."""
    view = store.view(baseline_id, _seen(request, store, baseline_id))
    if not view["all_visible"]:
        n = view["restricted_count"]
        view = {**view, "note": f"{n} measure{'s are' if n != 1 else ' is'} restricted from you. You can sign for what you can see; "
                f"your signature will say it covers {'them' if n != 1 else 'it'}, confirmed by the named owners."}
    acct_id, who = _me(request)
    doc = store.read(baseline_id)
    view = {**view, **_gate_and_documents(request, store, baseline_id, view)}
    signed_by_me = any(s.get("account_id") == acct_id for s in doc["versions"][-1]["countersign"]) if doc else False
    slot = None if signed_by_me or view["status"] == "signed" else slot_for(
        store.contract, set(request.state.roles), {s["slot"] for s in view["signatures"]})
    return {**view, "viewer": {"name": who, "sponsor": _is_sponsor(request, store),
                        "can_settle": bool(set(request.state.roles) & {*store.contract["sponsor_roles"], "company_admin"}), "slot": slot}}


def _sees(request: Request, store: SignoffStore, baseline_id: str):
    seen = _seen(request, store, baseline_id)
    return lambda k: k["id"] in seen


def _left_out(store: SignoffStore, baseline_id: str) -> dict:
    doc = store.read(baseline_id)
    return (doc["versions"][-1].get("left_out") or {}) if doc else {}


def _gate_and_documents(request: Request, store: SignoffStore, baseline_id: str, view: dict) -> dict:
    """M2-E4: the ready-to-build checklist as this person may see it, and the two documents (with the fingerprints once signed)."""
    left = _left_out(store, baseline_id)
    recorded = view.get("documents")
    return {"gate": GATE.for_viewer(_plane(request), baseline_id, left, _viewer(request), _sees(request, store, baseline_id)),
            "documents": DOC.status(_plane(request), baseline_id, left, recorded)}


@router.get(BASE + "/review")
@guarded
def review(request: Request, baseline_id: str) -> dict:
    plane = _plane(request)  # the GET only: a write route reads straight after its own write, so it calls _full uncached
    return copy.deepcopy(cached(plane, "m2-review", [plane.root], lambda: _full(request, _store(request), baseline_id),
                                viewer=(_viewer(request), tuple(sorted(request.state.roles or [])), request.state.account_id, baseline_id, date.today())))


@router.get(BASE + "/my-parts")
@guarded
def my_parts(request: Request, baseline_id: str) -> dict:
    """Every role: a named owner reads exactly their own parts (no other measure, no restricted one they are not on), to confirm them."""
    store = _store(request)
    return store.my_parts_signed_in(baseline_id, _me(request)[0], _people(request), _seen(request, store, baseline_id))


@router.put(BASE + "/review/{kpi_id}")
@guarded
def update_review(request: Request, baseline_id: str, kpi_id: str, body: dict = Body(...)) -> dict:
    store = _store(request)
    _known(request, store, baseline_id, kpi_id)
    store.set_review(baseline_id, _who(request), kpi_id, {k: body[k] for k in ("tentative_date", "next_step", "project") if k in body})
    return _full(request, store, baseline_id)


@router.post(BASE + "/review/{kpi_id}/accept")
@guarded
def accept(request: Request, baseline_id: str, kpi_id: str) -> dict:
    store = _store(request)
    _known(request, store, baseline_id, kpi_id)
    store.accept(baseline_id, _who(request), kpi_id, _is_sponsor(request, store))
    return _full(request, store, baseline_id)


@router.post(BASE + "/review/{kpi_id}/owner")
@guarded
def name_owner(request: Request, baseline_id: str, kpi_id: str, body: dict = Body(...)) -> dict:
    store = _store(request)
    _known(request, store, baseline_id, kpi_id)
    store.name_owner(baseline_id, _who(request), kpi_id, body.get("part"), body.get("name"), _is_sponsor(request, store), _people(request))
    return _full(request, store, baseline_id)


@router.post(BASE + "/review/{kpi_id}/leave-out")
@guarded
def leave_out(request: Request, baseline_id: str, kpi_id: str, body: dict = Body(...)) -> dict:
    """The organiser or a sponsor leaves a measure out of this baseline, with a reason (M2-E4)."""
    store = _store(request)
    _known(request, store, baseline_id, kpi_id)
    store.leave_out(baseline_id, _who(request), kpi_id, body.get("reason"), request.state.roles)
    return _full(request, store, baseline_id)


@router.post(BASE + "/review/{kpi_id}/bring-back")
@guarded
def bring_back(request: Request, baseline_id: str, kpi_id: str) -> dict:
    store = _store(request)
    _known(request, store, baseline_id, kpi_id)
    store.bring_back(baseline_id, _who(request), kpi_id, request.state.roles)
    return _full(request, store, baseline_id)


@router.get(BASE + "/signoff/bundle")
@guarded
def bundle(request: Request, baseline_id: str):
    """One zip: the business glossary, the data catalogue and a read-me page, built for this person. A draft until the baseline is signed."""
    store = _store(request)
    view = _full(request, store, baseline_id)
    company = str((request.app.state.entitlements.company(request.state.company_id) or {}).get("name") or "company")
    data = BUNDLE.build(_plane(request), baseline_id, _viewer(request), _sees(request, store, baseline_id), company, view, view["gate"],
                        "company_admin" in (request.state.roles or []))
    name = BUNDLE.FILE if view["status"] == "signed" else BUNDLE.DRAFT_FILE
    return Response(data, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post(BASE + "/signoff/settle")
@guarded
def settle(request: Request, baseline_id: str, body: dict = Body(...)) -> dict:
    """The sponsor or company admin settles a real conflict between two choices. Both answers are kept."""
    store = _store(request)
    _known(request, store, baseline_id, body.get("kpi_id"))
    ok = bool(set(request.state.roles) & {*store.contract["sponsor_roles"], "company_admin"})
    store.settle(baseline_id, _who(request), body.get("kpi_id"), body.get("field"), body.get("value"), ok)
    return _full(request, store, baseline_id)


@router.post(BASE + "/confirm")
@guarded
def confirm(request: Request, baseline_id: str, body: dict = Body(...)) -> dict:
    store = _store(request)
    _known(request, store, baseline_id, body.get("kpi_id"))
    acct_id, who = _me(request)
    store.confirm(baseline_id, who, body.get("kpi_id"), body.get("part"), acct_id, _people(request))
    if not set(request.state.roles) & {"company_admin", "sponsor", "analyst", "owner"}:  # approver, participant: their own parts, not the review
        return store.my_parts_signed_in(baseline_id, acct_id, _people(request), _seen(request, store, baseline_id))
    return _full(request, store, baseline_id)


@router.post(BASE + "/countersign")
@guarded
def countersign(request: Request, baseline_id: str) -> dict:
    store = _store(request)
    acct_id, who = _me(request)
    every = {k["id"] for k in read_kpis(_plane(request), baseline_id) if isinstance(k, dict) and k.get("id")}
    store.countersign(baseline_id, who, acct_id, request.state.roles, len(every - _seen(request, store, baseline_id)),  # A-044
                      _viewer(request), _sees(request, store, baseline_id))
    return _full(request, store, baseline_id)


@router.post(BASE + "/versions")
@guarded
def new_version(request: Request, baseline_id: str) -> dict:
    store = _store(request)
    store.new_version(baseline_id, _who(request))
    return _full(request, store, baseline_id)


@router.get(BASE + "/audit")
@guarded
def audit(request: Request, baseline_id: str) -> dict:
    store = _store(request)
    return store.audit(baseline_id, _seen(request, store, baseline_id))


@router.get(BASE + "/handoff")
@guarded
def handoff(request: Request, baseline_id: str) -> dict:
    """The record module 3 reads, for the newest signed version. 404 until the baseline is signed."""
    plane = _plane(request)
    record = latest_baseline_outcome(plane, baseline_id)
    if record is None:
        raise LookupError("not signed")
    return H.for_viewer(record, read_kpis(plane, baseline_id), _seen(request, _store(request), baseline_id), _viewer(request))  # N1