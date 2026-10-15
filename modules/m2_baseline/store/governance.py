"""M2-E3: the governance view over the files that already hold governance (kpis.json, catalogue.json). Nothing new is stored: the one
thing written here is a field's own "Who may see it" cell, and a person's confirmed class, both in the catalogue's field rows."""
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import governance_view as GV
from modules.m2_baseline.store import catalogue as S
from modules.m2_baseline.store.kpis import read_kpis
from sh_platform.jsonfile import lock_for
from sh_platform.plane import CompanyPlane


def _analysis(plane: CompanyPlane, baseline_id: str, parts: dict | None = None) -> dict:
    S._baseline(plane, baseline_id)  # a baseline that does not exist is a 404
    cat = S._current(plane, baseline_id, S._raw(plane, baseline_id)[0])
    return GV.attach_proposals(GV.analyse(cat, read_kpis(plane, baseline_id)), parts)


def view(plane: CompanyPlane, baseline_id: str, viewer: C.Viewer, parts: dict | None = None) -> dict:
    return GV.view(_analysis(plane, baseline_id, parts), viewer)


def table(plane: CompanyPlane, baseline_id: str, viewer: C.Viewer) -> list[list[str]]:
    return GV.table(view(plane, baseline_id, viewer))


def columns(plane: CompanyPlane, baseline_id: str, viewer: C.Viewer) -> dict:
    return GV.columns(view(plane, baseline_id, viewer))


def governance_ready(plane: CompanyPlane, baseline_id: str, viewer: C.Viewer | None = None) -> tuple[bool, list[str]]:
    """For the sign-off package (M2-E4): (ready, reasons). Reads only; changes nothing. With no viewer (the gate's own call) or for the
    organiser or sponsor the reasons count everything; for anyone else they count only the rows that person may see."""
    S._baseline(plane, baseline_id)
    return GV.governance_ready(S._current(plane, baseline_id, S._raw(plane, baseline_id)[0]), read_kpis(plane, baseline_id), viewer)


def ambiguities(plane: CompanyPlane, baseline_id: str, viewer: C.Viewer) -> dict[str, list[dict]]:
    """Open governance ambiguities by measure id (the shared contract's shape), only those about rows `viewer` may see."""
    S._baseline(plane, baseline_id)
    return GV.ambiguities(S._current(plane, baseline_id, S._raw(plane, baseline_id)[0]), read_kpis(plane, baseline_id), viewer)


def hidden_names(plane: CompanyPlane, baseline_id: str, viewer: C.Viewer) -> set[str]:
    """The lower-case names of the fields this person may not see: a column matcher answer about one of them is left out."""
    an = _analysis(plane, baseline_id)
    return {C.norm(f["name"]) for f in an["fields"].values() if not GV._seen_row(an, f, viewer)}


def set_field(plane: CompanyPlane, baseline_id: str, field_id: str, names: object, viewer: C.Viewer) -> None:
    with lock_for(S._folder(plane, baseline_id) / "catalogue.json"):
        S._changeable(plane, baseline_id)
        cat, conflicts = S._raw(plane, baseline_id)
        kpis = read_kpis(plane, baseline_id)
        an = GV.analyse(cat, kpis)
        field = an["fields"].get(field_id)
        if field is None or not GV._seen_row(an, field, viewer):  # a field a person may not see is, to them, a field that does not exist
            raise C.CatalogueError("not_found", "We could not find that field.")
        GV.set_field_names(cat, kpis, field_id, names, viewer.name)
        S._save(plane, baseline_id, cat, conflicts)


def confirm(plane: CompanyPlane, baseline_id: str, viewer: C.Viewer, parts: dict, field_ids: object, only_not_personal: bool) -> dict:
    with lock_for(S._folder(plane, baseline_id) / "catalogue.json"):
        S._changeable(plane, baseline_id)
        cat, conflicts = S._raw(plane, baseline_id)
        an = GV.attach_proposals(GV.analyse(cat, read_kpis(plane, baseline_id)), parts)
        out = GV.confirm_proposals(cat, an, viewer, viewer.name, field_ids, only_not_personal)
        if out["confirmed"]:
            S._save(plane, baseline_id, cat, conflicts)
    return out
