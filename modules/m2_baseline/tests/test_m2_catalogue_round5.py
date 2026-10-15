"""CRITIC-M2 round 4, defects 1-3, N-C and N-I: KPI rows carry tracking and review, a personal-data answer is never overwritten by a
safer-looking one, nothing is marked stated that nobody said, and a measure with no steps is not given another measure's path.
Synthetic family-office content only."""
import json

from story_answers import MAILBOX, answers, kpis
from test_m2_catalogue import BID, seed

from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import handoff as H
from modules.m2_baseline.domain import process_map as D
from modules.m2_baseline.domain.catalogue import text_of as t
from modules.m2_baseline.store import catalogue as S


def _say(ans, who, value, at):
    for r in ans["sources"]["value"]:
        if r["name"]["value"] == MAILBOX:
            r["personal"] = {"value": value, "mark": "stated", "by": who, "from": "the answer link", "at": at}


def _mailbox(cat):
    return next(s for s in cat["sources"] if t(s["Source name"]) == MAILBOX)


def _personal(cat, conflicts):
    sid = C.row_id("sources", _mailbox(cat))
    return [c for c in conflicts if c["column"] == "Contains personal data?" and c["row_id"] == sid]


def _two_owners(sara="not_sure", tom="no"):
    a = answers()
    _say(a[2], "Sara Lim", sara, "2026-10-02T00:00:00+00:00")
    _say(a[3], "Tom Ng", tom, "2026-10-03T00:00:00+00:00")
    return a


# ---- defect 2: a personal-data answer is not overwritten ------------------------------------------------------------------------

def test_not_sure_beats_no_when_owners_differ_and_the_cell_is_a_conflict_between_named_owners():
    cat, conflicts = C.build(None, kpis(), _two_owners())
    cell = _mailbox(cat)["Contains personal data?"]
    assert t(cell) == "Not sure" and cell["by"] == "Sara Lim"
    rec = _personal(cat, conflicts)[0]
    assert {v["by"] for v in rec["versions"]} == {"Sara Lim", "Tom Ng"} and rec["state"] == "open"


def test_a_not_sure_given_under_a_restricted_measure_still_counts():
    ks = kpis()
    ks[2] = {**ks[2], "governance": {"personal": "not_sure", "sensitive": False, "may_see": ["Mei Tan"]}}  # K04 is restricted: Sara's answer sits under it
    cat, _ = C.build(None, ks, _two_owners())
    assert t(_mailbox(cat)["Contains personal data?"]) == "Not sure"


def test_yes_beats_both_and_agreement_is_no_conflict():
    cat, _ = C.build(None, kpis(), _two_owners(sara="yes", tom="not_sure"))
    assert t(_mailbox(cat)["Contains personal data?"]) == "Yes"
    cat, conflicts = C.build(None, kpis(), _two_owners(sara="no", tom="no"))
    assert t(_mailbox(cat)["Contains personal data?"]) == "No"
    assert not _personal(cat, conflicts)


def test_a_persons_settlement_wins_over_the_draft_on_a_rebuild():
    cat, conflicts = C.build(None, kpis(), _two_owners())
    C.settle(cat, conflicts, _personal(cat, conflicts)[0]["id"], "No", "Mei Tan")
    cat, conflicts = C.build(cat, kpis(), _two_owners(), conflicts)
    assert t(_mailbox(cat)["Contains personal data?"]) == "No" and _mailbox(cat)["Contains personal data?"]["by"] == "Mei Tan"


def test_a_persons_own_edit_wins_over_the_draft():
    cat, conflicts = C.build(None, kpis(), _two_owners())
    C.edit_cells(cat, [], "sources", C.row_id("sources", _mailbox(cat)), {"Contains personal data?": "No"}, "Mei Tan")
    cat, _ = C.build(cat, kpis(), _two_owners(), conflicts)
    assert t(_mailbox(cat)["Contains personal data?"]) == "No"


def test_the_personal_data_undecided_gap_fires_for_the_merged_not_sure():
    cat, _ = C.build(None, kpis(), _two_owners())
    gaps = H.build_gaps(H.load_outcome_contract(), [], cat)
    assert any(g["type"] == "personal_undecided" and C.row_id("sources", _mailbox(cat)) in g["where"] for g in gaps)


# ---- defect 3: nothing is "stated" that nobody said ------------------------------------------------------------------------------

def _leaves(x):
    if isinstance(x, dict):
        for v in x.values():
            yield from _leaves(v)
    elif isinstance(x, list):
        for v in x:
            yield from _leaves(v)
    elif isinstance(x, str):
        yield C.norm(x)


def test_every_cell_marked_stated_by_a_person_traces_to_an_answer():
    ans = _two_owners()
    cat, _ = C.build(None, kpis(), ans)
    words = {C.norm(w) for table in C.contract()["mapping"].values() if isinstance(table, dict) for w in table.values()}
    words |= {C.norm(o) for tab in C.TABS for h in C.headers(tab) for o in C.options(tab, h)}
    words |= {C.norm(c["label"]) for f in C._questionnaire().fields.values() for r in f.get("row", []) for c in r.get("choices") or []}
    said = {}
    for a in ans:
        said.setdefault(a["owner_name"], set()).update(_leaves({k: v for k, v in a.items() if isinstance(v, dict) and v.get("mark") == "stated"}))
    for tab in C.TABS:
        for row in cat[tab]:
            for header, cell in row.items():
                if not (isinstance(cell, dict) and cell.get("mark") == "stated") or C.norm(cell["by"]) in C.NOT_A_PERSON or cell["by"] == C.DERIVED_BY:
                    continue
                if header in ("Related KPIs", "Feeds KPI") or cell["by"] == "the organiser":  # ids worked out from the rows; the organiser's settings
                    continue
                assert cell["by"] in said, (tab, header, cell)
                text = C.norm(t(cell))
                assert any(text in leaf or text in words for leaf in said[cell["by"]] | {""}) or text in words, (tab, header, cell)


def test_availability_is_never_stated_by_a_person_who_did_not_say_it():
    a = answers()
    a[0]["could_track"] = {"value": "yes", "mark": "stated", "by": "Arjun Rao", "from": "the answer link", "at": "2026-10-02T00:00:00+00:00"}
    cat, _ = C.build(None, kpis(), a)
    for s in cat["sources"]:
        assert s["Availability"]["mark"] == "unknown"


def test_a_source_with_no_personal_answer_and_no_organiser_setting_is_not_marked_stated():
    ks = [{**k, "governance": {}} for k in kpis()]
    a = answers()
    for ans in a:
        for r in (ans.get("sources") or {}).get("value") or []:
            r["personal"] = {"value": None, "mark": "unknown", "by": ans["owner_name"], "from": "not answered yet", "at": "2026-10-02T00:00:00+00:00"}
    cat, _ = C.build(None, ks, a)
    assert all(s["Contains personal data?"]["mark"] == "unknown" for s in cat["sources"])


# ---- N-C: fields and extractions ------------------------------------------------------------------------------------------------

def test_a_field_never_takes_the_definition_as_its_meaning_and_no_extraction_is_blank():
    ks = kpis()
    ks[3] = {**ks[3], "definition": {**ks[3]["definition"], "value": "Net return minus the benchmark. Over the same period and currency."}}
    cat, _ = C.build(None, ks, answers())
    fields = [f for f in cat["fields"] if "K15" in t(f["Feeds KPI"])]
    assert fields and all(f["Business meaning"]["mark"] == "unknown" and f["Business meaning"]["from"] == C.NOT_YET for f in fields)  # not the definition, not its first sentence
    assert cat["extractions"] and all(t(x["What to extract"]) for x in cat["extractions"])


def test_a_document_type_with_nothing_to_read_out_gets_no_blank_extraction_row():
    rows = [r for r in answers() if r["id"] != "a3"]
    cat, _ = C.build(None, kpis(), rows)
    assert all(t(x["What to extract"]) for x in cat["extractions"])
    old = {**cat, "extractions": [*cat["extractions"], C.new_row("extractions", "X99")]}  # a blank row an earlier build left
    cat, _ = C.build(old, kpis(), rows)
    assert all(t(x["What to extract"]) for x in cat["extractions"])


# ---- N-I: a default path only for the measures that list it -----------------------------------------------------------------------

PACK = {"for_kpis": ["K01"], "steps": [{"step_id": "p1", "lane": "Operations", "name": "Register the document"}]}


def test_the_pack_default_applies_only_to_the_measures_it_lists():
    assert [s["text"] for s in D.draw([], PACK, "pack", None, kpi_id="K01")["steps"]] == ["Register the document"]
    assert D.draw([], PACK, "pack", None, kpi_id="K19")["steps"] == []


def test_an_unlisted_measure_with_a_silent_owner_shows_the_waiting_marker_and_no_copied_path():
    drawn = D.draw([], PACK, "pack", None, own_waiting=["Wei Chen"], kpi_id="K19")["steps"]
    assert [(s["text"], s.get("waiting")) for s in drawn] == [("Waiting on Wei Chen", True)]


def test_the_real_family_office_default_lists_the_measures_it_fits():
    import yaml
    from pathlib import Path
    default = yaml.safe_load((Path(__file__).resolve().parents[3] / "packs" / "family_office" / "1" / "process_map_default.yaml").read_text(encoding="utf-8"))
    assert default["for_kpis"] and "K19" not in default["for_kpis"] and D.from_pack(default, "pack", "K19") == []


# ---- defect 1: the KPI rows carry tracking, review, acceptance and signatures ----------------------------------------------------

def test_kpi_rows_carry_tracking_review_acceptance_and_each_owners_signature(world):
    plane = seed(world)
    S.refresh(plane, BID)
    stamp = "2026-10-03T10:00:00+00:00"
    version = {"version": 1, "status": "open", "record": None, "named": {}, "settled": {}, "countersign": [], "signed_at": None,
               "parts": {"K02": {"definition": {"by": "Tom", "at": stamp}, "process": {"by": "Sara", "at": "2026-10-04T09:00:00+00:00"}}},
               "review": {"K02": {"tentative_date": "2027-03-31", "next_step": "Ask the custodian for a feed", "project": "Data hub",
                                  "accepted": {"by": "Mei Sponsor", "at": "2026-10-05T08:00:00+00:00"}, "updated_by": "Mei Sponsor", "updated_at": stamp,
                                  "set": {f: {"by": "Mei Sponsor", "at": stamp} for f in ("tentative_date", "next_step", "project")}}}}
    plane.path("intents", "m2_baseline", BID, "signoff.json").write_text(json.dumps({"baseline_id": BID, "versions": [version], "audit": []}))
    rows = {C.row_id("kpis", r): r for r in S.read_catalogue(plane, BID)["kpis"]}
    assert t(rows["K01"]["Tracking status"]) == "Tracked today"  # K01 is tracked now: said so, not only in the gap text
    k2 = rows["K02"]
    assert t(k2["Tracking status"]) == "Will be tracked in future" and t(k2["Tentative date"]) == "2027-03-31"
    assert t(k2["Next steps or project"]) == "Ask the custodian for a feed; project: Data hub" and k2["Next steps or project"]["by"] == "Mei Sponsor"
    assert t(k2["Unknown accepted by (sponsor)"]) == "Mei Sponsor" and t(k2["Date accepted"]) == "2026-10-05"
    assert (t(k2["Business owner signed"]), k2["Business owner signed"]["by"]) == ("2026-10-03", "Tom")
    assert t(k2["Process owner signed"]) == "2026-10-04" and k2["Data owner signed"]["mark"] == "unknown"  # nobody confirmed it: unknown, not invented
    assert rows["K03"]["Business owner signed"]["mark"] == "unknown"
    assert json.loads(plane.path("intents", "m2_baseline", BID, "catalogue.json").read_text())["kpis"][0]["Next steps or project"]["mark"] == "unknown"  # nothing stored


def test_a_persons_edit_to_a_kpi_cell_is_kept_over_the_review(world):
    plane = seed(world)
    S.refresh(plane, BID)
    S.edit_row(plane, BID, "kpis", "K02", {"Tentative date": "2028-01-01"}, "Tom Ng", "stated", C.Viewer("Tom Ng", frozenset({"company_admin"})))
    version = {"version": 1, "status": "open", "record": None, "named": {}, "settled": {}, "countersign": [], "signed_at": None, "parts": {},
               "review": {"K02": {"tentative_date": "2027-03-31", "updated_by": "Mei", "updated_at": "2026-10-03T10:00:00+00:00"}}}
    plane.path("intents", "m2_baseline", BID, "signoff.json").write_text(json.dumps({"baseline_id": BID, "versions": [version], "audit": []}))
    k2 = next(r for r in S.read_catalogue(plane, BID)["kpis"] if C.row_id("kpis", r) == "K02")
    assert t(k2["Tentative date"]) == "2028-01-01"
