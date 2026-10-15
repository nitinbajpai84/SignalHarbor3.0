"""The catalogue's files in the company plane (SHARED.md):

intents/m2_baseline/<baseline_id>/catalogue.json            {sources, tables, fields, extractions, kpis}, each cell a provenance value
intents/m2_baseline/<baseline_id>/catalogue_conflicts.json  {conflicts: [...]}: both versions of a cell and who said each, M2-24

Reads `baseline.json` (state), `kpis.json` and `answers.json` of the same folder. Those belong to M2-P01 and M2-P02: the three readers below
are STAND-INS with exactly the SHARED.md shapes, to be replaced by those packages' store read functions when they land. A damaged file is
refused and never overwritten. Locks cover threads in one process only (A-015).
"""
import re
from pathlib import Path

from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import readiness as R
from modules.m2_baseline.domain import worklist as W
from modules.m2_baseline.domain.provenance import prov
from modules.m2_baseline.domain.xlsx_export import build_xlsx
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CompanyPlane

UNREADABLE = "These records could not be read, so nothing was changed. Please ask your administrator."
NOT_SAVED = "That could not be saved. Please try again."
ACCEPTED, COVERED = "Unknown accepted by (sponsor)", "Covered by its named owners"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


class StoreError(Exception):
    """A plain-words failure; never contains a path or an id."""


from modules.m2_baseline.store.answers import read_answers  # noqa: E402  (M2-P02, integration A-043)
from modules.m2_baseline.store.kpis import read_kpis  # noqa: E402  (M2-P01)

def _folder(plane: CompanyPlane, baseline_id: str) -> Path:
    if not isinstance(baseline_id, str) or not _ID.fullmatch(baseline_id):
        raise C.CatalogueError("not_found", "We could not find that baseline.")
    return plane.path("intents", "m2_baseline", baseline_id)


def _read(path: Path, kind: type):
    try:
        return read_json_strict(path, kind)
    except (OSError, ValueError):
        raise StoreError(UNREADABLE) from None


def _write(path: Path, data: object) -> None:
    try:
        write_json_atomic(path, data)
    except OSError:
        raise StoreError(NOT_SAVED) from None


def _baseline(plane: CompanyPlane, baseline_id: str) -> dict:
    base = _read(_folder(plane, baseline_id) / "baseline.json", dict)  # STAND-IN for M2-P01's reader
    if base is None:
        raise C.CatalogueError("not_found", "We could not find that baseline.")
    return base






def _raw(plane: CompanyPlane, baseline_id: str) -> tuple[dict, list[dict]]:
    folder = _folder(plane, baseline_id)
    cat = _read(folder / "catalogue.json", dict) or {}
    conflicts = (_read(folder / "catalogue_conflicts.json", dict) or {}).get("conflicts", [])
    return {t: cat.get(t, []) for t in C.TABS}, conflicts


def _save(plane: CompanyPlane, baseline_id: str, cat: dict, conflicts: list[dict]) -> None:
    folder = _folder(plane, baseline_id)
    _write(folder / "catalogue.json", {t: cat[t] for t in C.TABS})
    _write(folder / "catalogue_conflicts.json", {"conflicts": conflicts})


def _changeable(plane: CompanyPlane, baseline_id: str) -> dict:
    base = _baseline(plane, baseline_id)
    if base.get("state") == "signed":  # signed content is read-only
        raise C.CatalogueError("read_only", "This baseline is signed, so the catalogue can no longer be changed.")
    return base


def _current(plane: CompanyPlane, baseline_id: str, cat: dict) -> dict:
    """The catalogue with the KPI rows' tracking, review, acceptance and owner confirmations as they stand now (r4-1). Read only: what
    is saved in catalogue.json stays what the build and the people wrote."""
    folder = _folder(plane, baseline_id)
    version = ((_read(folder / "signoff.json", dict) or {}).get("versions") or [{}])[-1]
    c = R.load_contract()
    answers, mapped = read_answers(plane, baseline_id), _read(folder / "process_map_tracking.json", dict) or {}
    kpis = R.with_tracking(read_kpis(plane, baseline_id), answers, version, c, mapped)
    out = C.with_review(cat, kpis, version, c["parts"])
    # a restricted measure whose three owners confirmed it cannot get the sponsor's acceptance: the cell says so, as the sign-off page does
    # ponytail: "restricted" is read from the measure's own governance; a sponsor who is named on the measure could still accept it
    hidden = frozenset(k["id"] for k in kpis if isinstance(k, dict) and isinstance(k.get("governance"), dict)
                       and (W.treated_as_personal(k["governance"]) or k["governance"].get("sensitive")))
    covered = {r["id"] for r in R.compute(kpis, answers, version, c, mapped, hidden)["kpis"] if r.get("covered")} if hidden and "named" in version else set()  # no sign-off version yet: nothing is confirmed
    for row in out["kpis"]:
        if C.row_id("kpis", row) in covered and C.is_blank(row.get(ACCEPTED)):
            row[ACCEPTED] = prov(COVERED, "stated", "its named owners", "the sign-off review")
    # IC-0d: module 3's proposed quality rules, written by path beside the catalogue (never into it); the view and the export filter them per reader
    rules = (_read(folder / C.contract()["quality_rules"]["file"], dict) or {}).get("rules")
    return C.with_quality_rules(out, rules) if isinstance(rules, dict) else out


def read_catalogue(plane: CompanyPlane, baseline_id: str) -> dict:
    """What module 3 reads: the five tabs, every column of the template (the counts, Complete? and Ready? worked out), each cell a
    provenance value. Not limited to anyone's view; the screens and the Excel file use view() and export() instead."""
    return C.with_derived(_current(plane, baseline_id, _raw(plane, baseline_id)[0]))


def _governance(plane: CompanyPlane, baseline_id: str) -> dict[str, dict]:
    return {str(k["id"]): k.get("governance") or {} for k in read_kpis(plane, baseline_id)}


def view(plane: CompanyPlane, baseline_id: str, viewer: C.Viewer) -> dict:
    """The catalogue as this person may see it: rows they are not named for are {id, hidden}; their conflicts and findings are left out."""
    _baseline(plane, baseline_id)
    cat, conflicts = _raw(plane, baseline_id)
    cat = _current(plane, baseline_id, cat)
    gov = _governance(plane, baseline_id)
    shown, findings = C.view_of(cat, C.guards(cat, gov), viewer)
    visible = {(t, C.row_id(t, r)) for t in C.TABS for r in shown[t] if not r.get(C.HIDDEN)}
    out_of_sight = {C.row_id("kpis", r) for r in shown["kpis"] if r.get(C.HIDDEN)}  # no version said under a measure the caller may not see
    seen = [{**c, "versions": [v for v in c["versions"] if str(v.get("kpi_id")) not in out_of_sight]}
            for c in conflicts if (c["tab"], c["row_id"]) in visible]  # a conflict about a row the caller may not see is not mentioned
    return {**shown, "conflicts": seen, "findings": findings, "hidden_note": C.hidden_note(shown, cat, gov)}


def _problem_names(plane: CompanyPlane, baseline: dict) -> dict[str, str]:
    """Problem id -> title, from module 1's signed outcome record (its output; this module never imports module 1)."""
    oid = baseline.get("charter_outcome_id")
    if not isinstance(oid, str) or not _ID.fullmatch(oid):
        return {}
    outcome = _read(plane.path("intents", "m1_intent", "outcomes", f"{oid}.json"), dict) or {}
    return {str(p["id"]): str(p["title"]) for p in outcome.get("problems") or [] if isinstance(p, dict) and p.get("id") and p.get("title")}


def refresh(plane: CompanyPlane, baseline_id: str) -> dict:
    """Fill the catalogue from kpis.json and answers.json. Cells a person edited or settled are kept."""
    with lock_for(_folder(plane, baseline_id) / "catalogue.json"):
        base = _changeable(plane, baseline_id)
        cat, conflicts = _raw(plane, baseline_id)
        cat, conflicts = C.build(cat, read_kpis(plane, baseline_id), read_answers(plane, baseline_id), conflicts, _problem_names(plane, base))
        _save(plane, baseline_id, cat, conflicts)
    return {"status": "ok"}  # counts would tell a caller about rows they may not see


def add_row(plane: CompanyPlane, baseline_id: str, tab: str, cells: dict, by: str, mark: str = "stated") -> str:
    with lock_for(_folder(plane, baseline_id) / "catalogue.json"):
        _changeable(plane, baseline_id)
        cat, conflicts = _raw(plane, baseline_id)
        row = C.add_row(cat, conflicts, tab, cells, by, mark)
        _save(plane, baseline_id, cat, conflicts)
    return C.row_id(tab, row)


def propose_rows(plane: CompanyPlane, baseline_id: str, proposals: dict, kpi_id: str, title: str, restricted: bool, may_see: list[str] | None = None) -> dict[str, list[str]]:
    """Lens's guessed rows from the technical notes (domain/catalogue.py `propose_rows`); the ids of the rows made or found. Nothing is saved when
    there is nothing to add."""
    with lock_for(_folder(plane, baseline_id) / "catalogue.json"):
        _changeable(plane, baseline_id)
        cat, conflicts = _raw(plane, baseline_id)
        ids = C.propose_rows(cat, proposals, kpi_id, title, restricted, may_see)
        _save(plane, baseline_id, cat, conflicts)
    return ids


def edit_row(plane: CompanyPlane, baseline_id: str, tab: str, row_id: str, changes: dict, by: str, mark: str, viewer: C.Viewer) -> None:
    with lock_for(_folder(plane, baseline_id) / "catalogue.json"):
        _changeable(plane, baseline_id)
        cat, conflicts = _raw(plane, baseline_id)
        _may_open(cat, plane, baseline_id, tab, row_id, viewer)
        C.edit_cells(cat, conflicts, tab, row_id, changes, by, mark)
        _save(plane, baseline_id, cat, conflicts)


def settle(plane: CompanyPlane, baseline_id: str, conflict_id: str, value: object, by: str, note: str, viewer: C.Viewer) -> dict:
    with lock_for(_folder(plane, baseline_id) / "catalogue.json"):
        _changeable(plane, baseline_id)
        cat, conflicts = _raw(plane, baseline_id)
        rec = next((c for c in conflicts if c["id"] == conflict_id), None)
        if rec is not None:
            _may_open(cat, plane, baseline_id, rec["tab"], rec["row_id"], viewer)
        out = C.settle(cat, conflicts, conflict_id, value, by, note)
        _save(plane, baseline_id, cat, conflicts)
    return out


def _may_open(cat: dict, plane: CompanyPlane, baseline_id: str, tab: str, row_id: str, viewer: C.Viewer) -> None:
    """A row a person may not see cannot be changed by them either: the answer is the same as for a row that does not exist."""
    row_guards = C.guards(cat, _governance(plane, baseline_id)).get((tab, row_id), [])
    if C.find(cat, tab, row_id) is not None and not all(C.allows(g, viewer) for g in row_guards):
        raise C.CatalogueError("not_found", "We could not find that row.")


def _governance_rows(plane: CompanyPlane, baseline_id: str, viewer: C.Viewer) -> list[list[str]]:
    from modules.m2_baseline.store import governance as G  # M2-E3 (imported here: that file reads this one)
    return G.table(plane, baseline_id, viewer)


def export(plane: CompanyPlane, baseline_id: str, viewer: C.Viewer, stamp: str = "") -> bytes:
    """The Excel workbook of the rows this person may see (M2-18, M2-05): the others are not in the file."""
    _baseline(plane, baseline_id)
    cat = _current(plane, baseline_id, _raw(plane, baseline_id)[0])
    shown, _ = C.view_of(cat, C.guards(cat, _governance(plane, baseline_id)), viewer, drop=True)
    from modules.m2_baseline.store import technical as ST  # M2-E1 (imported here: that file reads this one)
    return build_xlsx(shown, _governance_rows(plane, baseline_id, viewer), ST.table(plane, baseline_id, viewer), stamp)
