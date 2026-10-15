"""IC-3c: governed_state.json beside the baseline's catalogue, {measure id: {field: cell}}. Two writers: Lens's guess and a person's
confirmation, both through `_put`, which keeps a stated value from a guess (domain/governed.keep_old)."""
from datetime import date

from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import governed as G
from modules.m2_baseline.domain import worklist as W
from modules.m2_baseline.store import baseline as B
from modules.m2_baseline.store import governance as GS
from modules.m2_baseline.store.kpis import read_kpis
from sh_platform.jsonfile import lock_for
from sh_platform.plane import CompanyPlane
from sh_platform.profile import store as profile_store

FILE = "governed_state.json"


def _file(plane: CompanyPlane, baseline_id: str):
    return B.root(plane) / baseline_id / FILE


def _read(plane: CompanyPlane, baseline_id: str) -> dict:
    return B.read_file(_file(plane, baseline_id), dict) or {}


def exists(plane: CompanyPlane, baseline_id: str) -> bool:
    return _file(plane, baseline_id).exists()


def _editable(plane: CompanyPlane, baseline_id: str) -> None:
    base = B.read_baseline(plane, baseline_id)
    if base is None:
        raise C.CatalogueError("not_found", "We could not find that baseline.")
    if base["state"] == "signed":
        raise B.Locked(B.LOCKED)


def _kpi(plane: CompanyPlane, baseline_id: str, measure_id: str) -> dict:
    kpi = next((k for k in read_kpis(plane, baseline_id) if k.get("id") == measure_id), None)
    if kpi is None:
        raise C.CatalogueError("not_found", "We could not find that measure.")
    return kpi


def _put(entry: dict, field: str, new: dict) -> bool:
    if G.keep_old(entry.get(field), new):
        return False
    entry[field] = new
    return True


def draft_governed(plane: CompanyPlane, baseline_id: str, measure_id: str, drafts: dict) -> dict:
    """Lens's guesses: {field: (value, plain source label)}. A stated field is kept. Returns the entry."""
    if set(drafts) - set(G.FIELDS):
        raise C.CatalogueError("invalid", "That part of a measure's governance does not exist.")
    with lock_for(_file(plane, baseline_id)):
        _editable(plane, baseline_id)
        _kpi(plane, baseline_id, measure_id)
        doc = _read(plane, baseline_id)
        entry = {**G.blank(), **doc.get(measure_id, {})}
        for field, (value, source) in drafts.items():
            _put(entry, field, G.draft_cell(G.clean(field, value) if value is not None else None, source))
        doc[measure_id] = entry
        B.write_file(_file(plane, baseline_id), doc)
        return entry


def sync_owners(plane: CompanyPlane, baseline_id: str, measure_id: str, value: dict, by: str) -> None:
    """One place for owners: a confirmed owners cell also becomes the measure's own owners, for the slots named in `value` only
    (a slot left out keeps its name; an empty name withdraws it)."""
    from modules.m2_baseline.store.kpis import change

    def edit(k: dict) -> dict:
        own = {**(k.get("owners") or {})}
        for role, who in value.items():
            if role in G.ROLES:
                same = isinstance(own.get(role), dict) and C.norm(C.value_of(own[role])) == C.norm(who)
                if not same:
                    own[role] = W.nominee({"name": who or ""}, by)
        return {**k, "owners": own}
    change(plane, baseline_id, measure_id, edit)


def confirm_field(plane: CompanyPlane, baseline_id: str, measure_id: str, field: str, value, by_account: C.Viewer) -> dict:
    """A person states one field. Refused in one plain sentence unless they are the person named for it (domain/governed.check_confirm)."""
    with lock_for(_file(plane, baseline_id)):
        _editable(plane, baseline_id)
        kpi = _kpi(plane, baseline_id, measure_id)
        if kpi not in _seen(plane, baseline_id, by_account):  # a measure a person may not see does not exist for them
            raise C.CatalogueError("not_found", "We could not find that measure.")
        doc = _read(plane, baseline_id)
        G.check_confirm(field, kpi, profile_store.raw(plane), by_account, value, doc.get(measure_id, {}).get("owners"))
        entry = {**G.blank(), **doc.get(measure_id, {})}
        got = G.clean(field, value, stated=True)
        if field == "owners":  # a slot left out of the confirmation keeps its current name instead of being wiped
            now = (entry.get("owners") or {}).get("value") or {}
            got = {r: (got.get(r) if r in value else now.get(r)) for r in got}
        _put(entry, field, G.person_cell(got, by_account.name))
        doc[measure_id] = entry
        B.write_file(_file(plane, baseline_id), doc)
        if field == "owners":
            sync_owners(plane, baseline_id, measure_id, {r: got[r] for r in got if r in value}, by_account.name)
        return entry


def _seen(plane: CompanyPlane, baseline_id: str, viewer: C.Viewer) -> list[dict]:
    organiser = "company_admin" in viewer.roles
    return [k for k in read_kpis(plane, baseline_id) if W.may_see(k, viewer.name, viewer.account_id, organiser)]


def draft_all(plane: CompanyPlane, baseline_id: str, viewer: C.Viewer, pack_kpis: list[dict] | None = None, today: date | None = None) -> int:
    """Lens's draft for every measure the viewer may see, from the stored governance, the profile and the pack. No model call.
    Returns how many measures were drafted."""
    an = GS._analysis(plane, baseline_id)
    profile, mine = profile_store.raw(plane), _seen(plane, baseline_id, viewer)
    for k in mine:
        names = [f["name"] for f in an["fields"].values() if k["id"] in f["feeds"]]
        got = G.draft(k, names, profile, pack_kpis or [], today or date.today())
        draft_governed(plane, baseline_id, k["id"], {f: (c["value"], c["from"]) for f, c in got.items()})
    return len(mine)


def governed_for(plane: CompanyPlane, baseline_id: str, viewer: C.Viewer) -> dict:
    """The state of the measures this viewer may see (a restricted measure's state only to its list), `complete` each, four percentages."""
    if B.read_baseline(plane, baseline_id) is None:
        raise C.CatalogueError("not_found", "We could not find that baseline.")
    doc = _read(plane, baseline_id)
    rows = [{"id": k["id"], "name": k.get("name"), "state": {**G.blank(), **doc.get(k["id"], {})}} for k in _seen(plane, baseline_id, viewer)]
    for r in rows:
        r["complete"] = r["governed"] = G.is_complete(r["state"])
        r["missing"] = [f for f in G.FIELDS if r["state"][f].get("mark") != "stated"]
    return {"measures": rows, "percentages": G.percentages([r["state"] for r in rows])}
