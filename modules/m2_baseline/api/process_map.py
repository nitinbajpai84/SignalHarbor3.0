"""The process map, per KPI (M2-12, M2-21, M2-22). The company and the person come from the server session.

Routes are declared in manifest.yaml under M2-P03. Lens draws from the owners' answers; people validate, edit,
remove and add steps; a human edit is never overwritten by a redraw; a signed baseline is never redrawn over.
"""
import logging
from datetime import date

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from modules.m2_baseline.agent.lens import run_in_order, sort_names
from modules.m2_baseline.api.catalogue import _viewer
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.api.signed_guard import SignedGuard
from modules.m2_baseline.domain import process_map as D
from modules.m2_baseline.domain import technical as TD
from modules.m2_baseline.store import technical as ST
from modules.m2_baseline.domain import readiness as R
from modules.m2_baseline.domain import worklist as W
from modules.m2_baseline.domain.provenance import prov, unknown
from modules.m2_baseline.domain.readiness import ContractError
from modules.m2_baseline.store.process_map import BadId, MapUnreadable, ProcessMapStore
from modules.m2_baseline.store.signoff import SignoffStore, StoreError
from sh_platform.egress.names import protected_names
from sh_platform.egress.providers import ProviderError, build_model_client
from sh_platform.egress.vault import NameVault, VaultUnavailable
from sh_platform.plane import CrossCompanyError, PlaneStore
from sh_platform.settings import load_model_env

log = logging.getLogger(__name__)
router = APIRouter(route_class=SignedGuard)
P = "/baselines/{baseline_id}/process-map"
SIGNED = "This baseline is signed; it can no longer be changed."
NOT_FOUND = "We could not find that measure or step."


class Refuse(Exception):
    def __init__(self, status: int, error: str, message: str):
        self.status, self.error, self.message = status, error, message


def _run(fn):
    try:
        return fn()
    except Refuse as e:
        return JSONResponse({"error": e.error, "message": e.message}, status_code=e.status)
    except ValueError as e:  # BadId is one too: a bad id is not found
        if isinstance(e, BadId):
            return JSONResponse({"error": "not_found", "message": NOT_FOUND}, status_code=404)
        return JSONResponse({"error": "bad_request", "message": str(e)}, status_code=400)
    except D.StepRemoved as e:
        return JSONResponse({"error": "removed", "message": str(e)}, status_code=409)
    except KeyError:
        return JSONResponse({"error": "not_found", "message": NOT_FOUND}, status_code=404)
    except MapUnreadable as e:
        return JSONResponse({"error": "unreadable", "message": str(e)}, status_code=500)
    except (LookupError, CrossCompanyError):
        return JSONResponse({"error": "forbidden", "message": "Your company space could not be opened. Please ask your administrator."},
                            status_code=403)


def _open(request: Request, baseline_id: str):
    plane = PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()
    return plane, ProcessMapStore(plane, baseline_id)


def _name(request: Request) -> str:
    acct = request.app.state.account_store.get(request.state.account_id) or {}
    return str(acct.get("display_name") or "").strip() or "A reviewer"


def _seen(request: Request, store: ProcessMapStore) -> set[str]:
    """The measures this person may see, by the work list's rule (domain/worklist.py). The others are dropped from the
    map entirely: no steps, no definition, no owner names."""
    acct = request.app.state.account_store.get(request.state.account_id) or {}
    organiser = "company_admin" in (request.state.roles or [])
    return W.visible_ids([k for k in store.kpis() if isinstance(k, dict) and k.get("id")], str(acct.get("display_name") or ""),
                         request.state.account_id, organiser)


def _editable(store: ProcessMapStore) -> None:
    if store.baseline().get("state") == "signed":
        raise Refuse(409, "signed", SIGNED)


def _model(request: Request, plane, people: list[str], organisations: list[str] = ()) -> tuple[object, frozenset[str]]:
    """Lens's model client (or None when none is set up) and the lowercased names the vault now holds (D-007)."""
    known: set[str] = set()
    factory = getattr(request.app.state, "lens_model_factory", None)  # tests plug a stub in here
    override = getattr(request.app.state, "model_env", None)
    try:
        model = factory(plane) if factory else build_model_client(plane, dict(override) if override is not None else load_model_env())
    except ProviderError:
        log.warning("the model settings are not valid")
        return None, frozenset()
    if model is not None:
        vault = NameVault(plane)
        company = (request.app.state.entitlements.company(request.state.company_id) or {}).get("name")
        for kind, name in protected_names(str(company or ""), *sort_names(str(company or ""), people, organisations)):
            try:
                vault.register(kind, name)
                known.update(w.lower() for w in name.split())
            except (ValueError, VaultUnavailable):
                log.warning("a name could not be registered with the egress vault")  # the gateway then refuses to send
    return model, frozenset(known)


def _pack_default(request: Request) -> tuple[dict | None, str]:
    company = request.app.state.entitlements.company(request.state.company_id) or {}
    try:
        pack = request.app.state.packs.load(str(company.get("industry", "")))
        return (pack.section("process_map_default") if "process_map_default" in pack.sections() else None), f"pack: {getattr(pack, 'label', '')}"
    except (ValueError, KeyError, OSError):
        return None, "pack"


def _names(answers: list[dict], kpis: list[dict]) -> tuple[list[str], list[str]]:
    """(people, organisations) named in this baseline. Nominated owners and the answering person are people; a `who`
    in an answer is a system, team or organisation ("Market data vendor API"), unless it is one of those people
    (a `who` that looks like a person's name still gets the person rule in protected_names). What the vault then holds is decided by sh_platform.egress.names.protected_names."""
    people = [D._text(v) for k in kpis for v in ((k.get("owners") or {}).get(r) for r in ("business", "data", "process"))]
    orgs = []
    for a in answers:
        people.append(str(a.get("owner_name") or "").strip())
        for f in ("upstream", "in_between", "downstream"):
            items = D._val(a.get(f))
            orgs += [D._text(e.get("who")) for e in items if isinstance(e, dict)] if isinstance(items, list) else []
    mine = {p.casefold() for p in people}
    return people, [o for o in orgs if o.casefold() not in mine]


def _tracking_view(kpi: dict, record: dict, kpi_map: dict) -> dict:
    status = record.get("status") or kpi.get("tracking") or unknown()
    return {"status": status, "tentative_date": record.get("tentative_date") or unknown(),
            "next_step": record.get("next_step") or unknown(), "steps": record.get("steps", {}), "_kpi": status["value"]}


def _kpi_view(kpi: dict, maps: dict, tracking: dict, answers: list[dict], hidden: list[str] = ()) -> dict:
    mine = [a for a in answers if a.get("kpi_id") == kpi["id"]]
    kmap = maps.get(kpi["id"]) or {"lanes": [], "steps": []}
    v = D.view({**kmap, "steps": D.without_hidden(kmap["steps"], list(hidden))}, mine)  # steps from the technical definition, filtered for this person
    t = _tracking_view(kpi, tracking.get(kpi["id"]) or {}, v)
    steps = [{**s, "tracking": t["steps"].get(s["id"]) or t["_kpi"]} for s in v["steps"]]
    return {"id": kpi["id"], "name": kpi.get("name"), "definition": kpi.get("definition") or unknown(), **v, "steps": steps, "drawn": kpi["id"] in maps,
            "tracking": {k: t[k] for k in ("status", "tentative_date", "next_step")}}


def _reviewed(request: Request, store: ProcessMapStore) -> list[dict]:
    """The measures with the one tracking status the review shows (what someone set here, else the owners' answers): the map's
    control and the review read it from the same place (R4 defect 7)."""
    try:
        so = SignoffStore(store._plane, contracts_dir=getattr(request.app.state, "m2_contracts_dir", None))
        doc = so.read(store._bid)
        return R.with_tracking(store.kpis(), store.answers(), doc["versions"][-1] if doc else {}, so.contract, store.tracking())
    except (StoreError, ContractError):
        return store.kpis()


def _everything(request: Request, store: ProcessMapStore, seen: set[str]) -> dict:
    maps, tracking, answers = store.maps(), store.tracking(), store.answers()
    try:
        hidden = ST.hidden_terms(store._plane, store._bid, _viewer(request), lambda k: k.get("id") in seen)
    except (LookupError, C.CatalogueError, BadId, MapUnreadable):
        hidden = []  # no baseline or catalogue to read yet: there are no technical steps either
    return {"baseline_id": store._bid, "signed": store.baseline().get("state") == "signed",
            "statuses": D.CONTRACT["statuses"],
            "kpis": [_kpi_view(k, maps, tracking, answers, hidden) for k in _reviewed(request, store) if isinstance(k, dict) and k.get("id") in seen]}


def _one(request: Request, store: ProcessMapStore, kpi_id: str, seen: set[str]) -> dict:
    return next(k for k in _everything(request, store, seen)["kpis"] if k["id"] == kpi_id)  # StopIteration is a bug, not a user error


def _known(store: ProcessMapStore, kpi_id: str, seen: set[str]) -> None:
    if kpi_id not in seen:  # P3: hidden but real is refused plainly; one that does not exist is "not found"
        if any(isinstance(k, dict) and k.get("id") == kpi_id for k in store.kpis()):
            raise Refuse(403, "restricted", W.RESTRICTED_REFUSAL)
        raise KeyError(kpi_id)


@router.get(P)
def get_map(request: Request, baseline_id: str):
    def work():
        store = _open(request, baseline_id)[1]
        return _everything(request, store, _seen(request, store))
    return _run(work)


@router.post(P + "/draw")
def draw_map(request: Request, baseline_id: str):
    """Lens draws every KPI's map from the answers. Steps a person has touched stay as they are."""
    def work():
        plane, store = _open(request, baseline_id)
        with store.lock():
            _editable(store)
            answers, maps = store.answers(), store.maps()
            default, source = _pack_default(request)
            seen = _seen(request, store)
            kpis = [k for k in store.kpis() if isinstance(k, dict) and k.get("id") in seen]
            model, known = _model(request, plane, *_names(answers, kpis))
            people = [D._text(v) for k in store.kpis() if isinstance(k, dict) for v in (k.get("owners") or {}).values()]  # a hop may name any of them

            # the stored map is shown to everyone who sees the measure, so technical steps are drawn for the least-privileged view: a person with no
            # role and no name, who sees only what is open to all (and filtered again for each person when the map is read)
            nobody = C.Viewer("", frozenset())
            names = TD.row_names(ST.catalogue_for(plane, baseline_id, nobody)[0])
            hidden = ST.hidden_terms(plane, baseline_id, nobody, lambda k: W.may_see(k, "", None, False))

            def one(k):
                mine = [a for a in answers if a.get("kpi_id") == k["id"]]
                tech = D.without_hidden(D.from_technical(k, names), hidden)
                return D.draw(mine, default, source, maps.get(k["id"]), model, known, D.waiting_owners(k, mine, people), D.waiting_owners(k, mine), k["id"], tech)
            for k, drawn in zip(kpis, run_in_order(one, kpis)):  # the model calls run two at a time; the files are written in order
                store.save_map(k["id"], drawn)
        return _everything(request, store, seen)
    return _run(work)


def _change(request: Request, baseline_id: str, kpi_id: str, fn):
    def work():
        _, store = _open(request, baseline_id)
        with store.lock():
            _editable(store)
            seen = _seen(request, store)
            _known(store, kpi_id, seen)
            store.save_map(kpi_id, fn(store.maps().get(kpi_id) or {"lanes": [], "steps": []}, _name(request)))
        return _one(request, store, kpi_id, seen)
    return _run(work)


@router.post(P + "/{kpi_id}/steps")
def add_step(request: Request, baseline_id: str, kpi_id: str, body: dict = Body(...)):
    return _change(request, baseline_id, kpi_id, lambda m, by: D.add_step(
        m, body.get("lane"), body.get("text"), body.get("manual") is True, by, body.get("order")))


@router.post(P + "/{kpi_id}/steps/{step_id}/validate")
def validate(request: Request, baseline_id: str, kpi_id: str, step_id: str):
    return _change(request, baseline_id, kpi_id, lambda m, by: D.validate_step(m, step_id, by))


@router.put(P + "/{kpi_id}/steps/{step_id}")
def edit(request: Request, baseline_id: str, kpi_id: str, step_id: str, body: dict = Body(...)):
    manual = body.get("manual")
    return _change(request, baseline_id, kpi_id, lambda m, by: D.edit_step(
        m, step_id, by, body.get("lane"), body.get("text"), manual if isinstance(manual, bool) else None))


@router.delete(P + "/{kpi_id}/steps/{step_id}")
def remove(request: Request, baseline_id: str, kpi_id: str, step_id: str):
    return _change(request, baseline_id, kpi_id, lambda m, by: D.remove_step(m, step_id, by))


@router.put(P + "/{kpi_id}/tracking")
def set_tracking(request: Request, baseline_id: str, kpi_id: str, body: dict = Body(...)):
    """The KPI's tracking status with an optional tentative date and next step, or one step's own status."""
    def work():
        _, store = _open(request, baseline_id)
        by = _name(request)
        status = body.get("status")
        if status not in D.STATUS_IDS:
            raise ValueError("Choose one of: " + ", ".join(s["label"] for s in D.CONTRACT["statuses"]) + ".")
        with store.lock():
            _editable(store)
            seen = _seen(request, store)
            _known(store, kpi_id, seen)
            rec = dict(store.tracking().get(kpi_id) or {})
            if body.get("step_id") is not None:
                if body["step_id"] not in {s["id"] for s in (store.maps().get(kpi_id) or {}).get("steps", [])}:
                    raise KeyError(body["step_id"])
                rec["steps"] = {**rec.get("steps", {}), body["step_id"]: status}
            else:
                rec["status"] = prov(status, "stated", by, "process map")
                for key, limit in (("tentative_date", 10), ("next_step", D.LIM["next_step_chars"])):
                    v = body.get(key)
                    if v is not None:
                        v = str(v).strip()[:limit + 1]
                        if len(v) > limit:
                            raise ValueError("That is too long. Please shorten it.")
                        if key == "tentative_date" and v:
                            try:
                                date.fromisoformat(v)
                            except ValueError:
                                raise ValueError("Please give the date as year-month-day, for example 2027-03-31.") from None
                        rec[key] = prov(v, "stated", by, "process map") if v else unknown(by, "process map")
            store.save_tracking(kpi_id, rec)
        return _one(request, store, kpi_id, seen)
    return _run(work)
