"""Reviewer round on L1: no restricted owner leaks through the personal-data conflict or cell; a review field names the person who set it;
a guessed edit stays guessed. Synthetic family-office content only."""
import io
import json
import zipfile

from story_answers import MAILBOX, answers, kpis
from test_m2_catalogue import BID, seed

from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import readiness as R
from modules.m2_baseline.domain import signoff as SO
from modules.m2_baseline.domain.catalogue import text_of as t
from modules.m2_baseline.domain.xlsx_export import build_xlsx
from modules.m2_baseline.store import catalogue as S

SECRET = "Tomas Restricted"


def _mailbox(cat):
    return next(s for s in cat["sources"] if t(s["Source name"]) == MAILBOX)


def _say(ans, who, value):
    for r in ans["sources"]["value"]:
        if r["name"]["value"] == MAILBOX:
            r["personal"] = {"value": value, "mark": "stated", "by": who, "from": "the answer link", "at": "2026-10-03T00:00:00+00:00"}


def _k15_restricted(sara_says, k15_says):
    ks = kpis()
    ks[3] = {**ks[3], "governance": {"personal": "yes", "sensitive": True, "may_see": ["Mei Tan"]}}  # K15 is restricted
    a = answers()
    _say(a[2], "Sara Lim", sara_says)  # K04's owner
    _say(a[3], SECRET, k15_says)  # K15's owner
    a[3]["owner_name"] = SECRET
    return ks, a


def _whole(shown):
    return str(shown) + "".join(zipfile.ZipFile(io.BytesIO(build_xlsx(shown))).read(n).decode("utf8", "ignore")
                                for n in zipfile.ZipFile(io.BytesIO(build_xlsx(shown))).namelist())


def test_a_restricted_owners_no_is_not_in_a_conflict_or_anything_the_analyst_sees():
    ks, a = _k15_restricted("not_sure", "no")
    cat, conflicts = C.build(None, ks, a)
    assert not [c for c in conflicts if c["row_id"] == C.row_id("sources", _mailbox(cat)) and c["column"] == "Contains personal data?"]
    for tb in cat["tables"]:  # the mailbox's tables are tied to K04 only, so the source row is visible to the analyst
        tb["Related KPIs"] = C.prov("K04", "stated", "x", "x")
    shown, _ = C.view_of(cat, C.guards(cat, {k["id"]: k["governance"] for k in ks}), C.Viewer("Tom Ng", frozenset({"analyst"})), drop=True)
    assert t(_mailbox(shown)["Contains personal data?"]) == "Not sure"  # the source row is visible
    assert SECRET not in _whole(shown) and "K15" not in str(shown["sources"])


def test_a_restricted_owners_not_sure_counts_but_names_nobody():
    ks, a = _k15_restricted("no", "not_sure")
    cat, conflicts = C.build(None, ks, a)
    cell = _mailbox(cat)["Contains personal data?"]
    assert t(cell) == "Not sure" and SECRET not in str(cell) and SECRET not in str(conflicts)


def test_the_store_view_drops_conflict_versions_said_under_a_measure_the_viewer_cannot_see(world):
    plane = seed(world)
    S.refresh(plane, BID)
    folder = plane.path("intents", "m2_baseline", BID)
    sid = C.row_id("sources", json.loads((folder / "catalogue.json").read_text())["sources"][0])
    (folder / "catalogue_conflicts.json").write_text(json.dumps({"conflicts": [{
        "id": "c-x", "tab": "sources", "row_id": sid, "column": "Contains personal data?", "state": "open",
        "versions": [{"value": "No", "by": "Hidden Owner", "kpi_id": "K03"}, {"value": "Yes", "by": "Sara", "kpi_id": "K01"}]}]}))
    out = S.view(plane, BID, C.Viewer("Someone", frozenset({"analyst"})))
    assert out["conflicts"] and "Hidden Owner" not in str(out["conflicts"]) and "Sara" in str(out["conflicts"])


def test_a_review_field_names_the_person_who_set_it_not_the_last_editor():
    c = R.load_contract()
    kp = [{"id": "K02", "tracking": {"value": "partly", "mark": "stated", "by": "x", "from": "x", "at": None}}]
    v = {"version": 1, "status": "open", "review": {}, "parts": {}, "named": {}, "settled": {}, "countersign": []}
    v, _ = SO.set_review(v, c, kp, "K02", {"tentative_date": "2027-03-31"}, "Mei", "2026-10-03T10:00:00+00:00")
    v, _ = SO.set_review(v, c, kp, "K02", {"next_step": "Ask the custodian"}, "Tom", "2026-10-04T10:00:00+00:00")
    cat = {tab: [] for tab in C.TABS}
    cat["kpis"] = [C.new_row("kpis", "K02")]
    row = C.with_review(cat, kp, v, c["parts"])["kpis"][0]
    assert (row["Tentative date"]["by"], row["Next steps or project"]["by"]) == ("Mei", "Tom")
    old = {**v, "review": {"K02": {k: x for k, x in v["review"]["K02"].items() if k != "set"}}}  # a record from before: no person is named
    row = C.with_review(cat, kp, old, c["parts"])["kpis"][0]
    assert not row["Tentative date"]["by"] and row["Tentative date"]["mark"] == "stated"


def test_a_guessed_edit_to_the_personal_data_cell_stays_guessed_and_does_not_settle():
    a = answers()
    _say(a[2], "Sara Lim", "not_sure")
    _say(a[3], "Tom Ng", "no")
    cat, conflicts = C.build(None, kpis(), a)
    C.edit_cells(cat, conflicts, "sources", C.row_id("sources", _mailbox(cat)), {"Contains personal data?": "No"}, "Mei Tan", mark="guessed")
    mine = [c for c in conflicts if c["row_id"] == C.row_id("sources", _mailbox(cat)) and c["column"] == "Contains personal data?"]
    assert _mailbox(cat)["Contains personal data?"]["mark"] == "guessed" and mine[0]["state"] == "open"
