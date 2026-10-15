"""LI-M3: module 3 lean. Samples and reported figures come from the company profile, uploads are filed by Lens, rules that match are checked
automatically, plan teams come from owners, and the human inputs are counted. Synthetic data only; the demo-workspace check is skipped when
the local files are absent."""
import json
from pathlib import Path

import pytest
import yaml

from m3_kit import BASE, person
from m3_trial_kit import Gate, demo_files, demo_inputs, pack_kpis, plane as kit_plane
from modules.m3_connect.agent import compile as C
from modules.m3_connect.domain import counters as K
from modules.m3_connect.domain import findings as F
from modules.m3_connect.domain import from_profile as FP
from modules.m3_connect.domain import inputs as I
from modules.m3_connect.domain import plan as P
from modules.m3_connect.domain import profile as PR
from modules.m3_connect.domain import rules as R
from modules.m3_connect.domain import trial as T
from sh_platform import profile
from sh_platform.profile import reader
from test_m3_intake import DEMO, demo_world, payload, upload, url

LENS = {"mark": "stated", "by": "Lens", "agent": "lens"}


def put_sample(world, name="performance_workbook.xlsx", system="", data=None):
    return reader.add_upload(world.plane("m3-a"), 8, "Pia Profile", name, (DEMO / name).read_bytes() if data is None else data, system=system)


def put_figure(world, key, measure, figure, label="Monthly pack Sep, page 3", unit="%", period="2026-09-30"):
    pl = world.plane("m3-a")
    prov = {**LENS, "from": label, "ref": {"kind": "document", "id": "abc123"}}
    for f, v in (("measure", measure), ("figure", figure), ("unit", unit), ("period_end", period)):
        profile.record(pl, f"reported_figures.{key}.{f}", v, prov)


def restrict(world, area, may_see=("Test Somebody Else",)):
    pl = world.plane("m3-a")
    prov = {"mark": "stated", "by": "Head of data"}
    profile.record(pl, f"governance.restricted_areas.{area.replace(' ', '-').lower()}.area", area, {**prov, "from": "Governance list"})
    profile.record(pl, f"governance.restricted_areas.{area.replace(' ', '-').lower()}.may_see", list(may_see), {**prov, "from": "Governance list"})


# ---- 1. samples from the profile ----------------------------------------------------------------------------------------------------
def test_a_profile_sample_is_used_and_not_requested_again(world):
    c, aid = demo_world(world)
    put_sample(world)
    listed = c.get(url(aid, "/requests")).json()
    assert [f["source_id"] for f in listed["from_profile"]] == ["S01"]
    assert listed["from_profile"][0]["from"].startswith("Sample file performance_workbook.xlsx")
    assert "S01" not in {s["source_id"] for s in listed["not_yet_asked"]}
    made = c.post(url(aid, "/requests")).json()
    assert made["new"] == 4 and "S01" not in {s["source_id"] for s in made["sent"]}
    prof = c.get(url(aid, "/sources/S01/profile")).json()["profile"]
    assert prof["tables"] and prof["tables"][0]["row_count"] == 40
    steps = {s["id"]: s["state"] for s in c.get(f"{BASE}/assessments/{aid}").json()["steps"]}
    assert steps["request"] == "in_progress"


def test_all_sources_with_samples_make_the_data_request_done(world):
    c, aid = demo_world(world)
    adir = world.plane("m3-a").path("intents", "m3_connect", "assessments", aid)  # the source map (P01's file): every demo source is in priority 1
    (adir / "sources.json").write_text(json.dumps({"sources": [{"id": f"S0{i}", "name": f"S0{i}", "zone": "p1", "measures": ["K10"]} for i in range(1, 6)]}))
    assert len(c.get(url(aid, "/requests")).json()["not_yet_asked"]) == 5
    steps = {s["id"]: s["state"] for s in c.get(f"{BASE}/assessments/{aid}").json()["steps"]}
    assert steps["request"] == "not_started"
    for name in ("performance_workbook.xlsx", "custody_daily_positions.csv", "capital_calls_export.json", "index_levels.csv", "exposure_workbook.csv"):
        put_sample(world, name)
    got = c.get(url(aid, "/requests")).json()
    assert got["not_yet_asked"] == [] and len(got["from_profile"]) == 5 and got["requests"] == []
    steps = {s["id"]: s["state"] for s in c.get(f"{BASE}/assessments/{aid}").json()["steps"]}
    assert steps["request"] == "done" and steps["scan"] == "done"


def test_a_file_the_organiser_uploaded_is_not_replaced_by_a_profile_sample(world):
    c, aid = demo_world(world)
    assert upload(c, aid, "S01", "performance_workbook.xlsx").status_code == 200
    put_sample(world)
    listed = c.get(url(aid, "/requests")).json()
    assert listed["from_profile"] == []


def test_a_signed_assessment_is_not_written_to_by_opening_the_screen(world, monkeypatch):
    c, aid = demo_world(world)
    put_sample(world)
    monkeypatch.setattr("modules.m3_connect.api.intake.is_signed", lambda plane, assessment_id: True)
    assert c.get(url(aid, "/requests")).json()["from_profile"] == []
    assert not world.plane("m3-a").path("intents", "m3_connect", "assessments", aid, "intake").exists()


# ---- 2. benchmarks from the profile -------------------------------------------------------------------------------------------------
def test_profile_figures_become_benchmarks_with_their_label(world):
    c, aid = demo_world(world)
    put_figure(world, "private-market-allocation-2026-09-30", "Private-market allocation", 29.0)
    put_figure(world, "something-odd-2026-09-30", "Something we never defined", 7.5, label="Monthly pack Sep, page 9")
    got = c.get(url(aid, "/benchmarks")).json()
    k10 = next(m for m in got["measures"] if m["measure_id"] == "K10")
    assert k10["figure"] == 29.0 and k10["came_from"] == "Monthly pack Sep, page 3" and k10["from_profile"] is True
    assert [u["line"] for u in got["unmatched"]] == ["Something we never defined"]  # still mapped by hand
    assert got["unmatched"][0]["came_from"] == "Monthly pack Sep, page 9"
    again = c.get(url(aid, "/benchmarks")).json()
    assert len(again["measures"]) == 1 and len(again["unmatched"]) == 1  # reading twice adds nothing


def test_a_figure_from_the_profile_never_overwrites_a_hand_mapping(world):
    c, aid = demo_world(world)
    put_figure(world, "odd-2026-09-30", "Something we never defined", 7.5)
    first = c.get(url(aid, "/benchmarks")).json()
    done = c.post(url(aid, "/benchmarks/map"), json={"index": first["unmatched"][0]["index"], "measure_id": "K12"}).json()
    assert next(m for m in done["measures"] if m["measure_id"] == "K12")["figure"] == 7.5
    again = c.get(url(aid, "/benchmarks")).json()
    assert again["unmatched"] == [] and len(again["measures"]) == 1


# ---- 3. uploads filed by Lens ---------------------------------------------------------------------------------------------------------
def test_an_unassigned_upload_is_filed_to_its_source(world):
    c, aid = demo_world(world)
    r = upload(c, aid, "_auto", "performance_workbook.xlsx")
    assert r.status_code == 200 and r.json()["filed"] == {"source_id": "S01", "source_name": "Performance workbook"}
    assert c.get(url(aid, "/sources/S01/profile")).json()["profile"]["tables"]


def test_an_uncertain_upload_asks_and_stores_nothing_until_confirmed(world):
    c, aid = demo_world(world)
    odd = b"Date,Thing\n2026-09-01,1\n2026-09-02,2\n"
    r = upload(c, aid, "_auto", "notes.csv", odd)
    body = r.json()
    assert r.status_code == 200 and body["filed"] is None and body["needs_confirm"]["candidates"]
    assert c.get(url(aid, "/sources/S04/profile")).json()["profile"] is None
    assert upload(c, aid, "S04", "notes.csv", odd).status_code == 200  # the organiser chose
    assert c.get(url(aid, "/sources/S04/profile")).json()["profile"]["tables"]


def test_a_profile_sample_that_matches_no_source_for_certain_waits_for_confirmation(world):
    c, aid = demo_world(world)
    put_sample(world, "notes.csv", data=b"Date,Thing\n2026-09-01,1\n2026-09-02,2\n")
    listed = c.get(url(aid, "/requests")).json()
    assert listed["from_profile"] == [] and listed["to_confirm"][0]["file"] == "notes.csv" and listed["to_confirm"][0]["candidates"]
    key = listed["to_confirm"][0]["key"]
    assert c.post(url(aid, "/sources/_auto/upload"), json={"profile_sample": key, "source_id": "S04"}).status_code == 200
    again = c.get(url(aid, "/requests")).json()
    assert [f["source_id"] for f in again["from_profile"]] == ["S04"] and again["to_confirm"] == []


# ---- 4. rules checked automatically when they match ---------------------------------------------------------------------------------
def test_a_rule_is_checked_automatically_on_a_match_only(tmp_path):
    adir = tmp_path / "a"
    demo_files(adir)
    inputs = demo_inputs()
    C.compile_all(None, Gate(), "co-test", kit_plane(tmp_path), adir, inputs["measures"], T.columns_by_source(adir), lambda m: T.feeders(adir, m),
                  pack_kpis(), F.technical_of)
    trial = T.run_trial(adir, inputs["measures"])
    rules = R.read_rules(adir)
    for k in ("K04", "K09", "K10"):
        assert trial[k]["result"] == "matches" and rules[k]["state"] == "checked" and rules[k]["auto_checked"] is True, k
        assert trial[k]["auto_checked"] is True and trial[k]["rule_state"] == "checked"
    for k in ("K12", "K15"):
        assert trial[k]["result"] == "gap" and rules[k]["state"] == "draft" and not rules[k].get("auto_checked"), k
    assert rules["K16"]["state"] != "checked" and trial["K16"]["result"] == "cannot"
    left = [k for k, r in rules.items() if r.get("rule") and r["state"] != "checked"]
    assert set(left) >= {"K12", "K15"} and not {"K04", "K09", "K10"} & set(left)  # the analyst waits on the gaps and the unknowns only
    assert f"check {len(left)} rule" in T.state(adir)["waiting_on"]


def test_an_auto_checked_rule_is_unchecked_when_it_stops_matching(tmp_path):
    adir = tmp_path / "a"
    demo_files(adir)
    inputs = demo_inputs()
    C.compile_all(None, Gate(), "co-test", kit_plane(tmp_path), adir, inputs["measures"], T.columns_by_source(adir), lambda m: T.feeders(adir, m),
                  pack_kpis(), F.technical_of)
    T.run_trial(adir, inputs["measures"])
    bench = json.loads((adir / "benchmarks.json").read_text())
    for b in bench:
        if b["measure_id"] == "K04":
            b["figure"] = 1.0
    (adir / "benchmarks.json").write_text(json.dumps(bench))
    T.run_trial(adir, inputs["measures"])
    assert R.read_rules(adir)["K04"]["state"] == "draft" and "auto_checked" not in R.read_rules(adir)["K04"]


def test_a_rule_a_person_checked_stays_theirs(tmp_path):
    adir = tmp_path / "a"
    demo_files(adir)
    inputs = demo_inputs()
    C.compile_all(None, Gate(), "co-test", kit_plane(tmp_path), adir, inputs["measures"], T.columns_by_source(adir), lambda m: T.feeders(adir, m),
                  pack_kpis(), F.technical_of)
    rules = R.read_rules(adir)
    rules["K04"].update(state="checked", checked_by="Ana Analyst")
    R.write_file(adir, "rules.json", rules)
    T.run_trial(adir, inputs["measures"])
    assert R.read_rules(adir)["K04"]["checked_by"] == "Ana Analyst" and not R.read_rules(adir)["K04"].get("auto_checked")


# ---- 5. teams from owners ----------------------------------------------------------------------------------------------------------------
def test_teams_come_from_the_profile_people_and_module_2_owners():
    people = {"owen owner": "Fund Operations", "hana head": "Risk"}
    inputs = {"sources": [{"Source ID": {"value": "S1", "mark": "stated"}, "Data owner": {"value": "Owen Owner", "mark": "stated"}}],
              "measures": [{"id": "K1", "restricted": False, "owners": {"business": "Hana Head", "data": "Hana Head", "process": None}}],
              "tables": [], "fields": []}
    owners = FP.source_owners(inputs, "S1", ["K1"], people)
    assert {(o["name"], o["team"]) for o in owners} == {("Owen Owner", "Fund Operations"), ("Hana Head", "Risk")}
    only_name = FP.source_owners(inputs, "S1", [], {})
    assert [o["name"] for o in only_name] == ["Owen Owner"] and only_name[0]["team"] == ""
    src = {"id": "S1", "name": "S one", "effort": "small", "owners": owners, "marks": [], "impact": 0.5}
    found = {"measure_id": "K1", "group": "ready", "reasons": [], "pain_points": [], "levers": [], "sources": ["S1"]}
    items = P.draft({"sources": {"S1": src}, "findings": [found], "risks": []}, set(), {})
    assert items[0]["team"] == ["Fund Operations", "Risk"] and "Team not named yet" not in items[0]["team"]
    nobody = P.draft({"sources": {"S1": {**src, "owners": FP.source_owners({"sources": [], "measures": [], "tables": [], "fields": []}, "S1", [], {})}}, "findings": [found], "risks": []}, set(), {})
    assert nobody[0]["team"] == ["Team not named yet"]


def test_plan_reads_teams_from_the_profile_end_to_end(world):
    c, aid = demo_world(world)
    pl = world.plane("m3-a")
    prov = {"mark": "stated", "by": "Lens", "agent": "lens", "from": "People list, sheet 1"}
    profile.record(pl, "people.owen-owner-illustrative.name", "Owen Owner (illustrative)", prov)
    profile.record(pl, "people.owen-owner-illustrative.team", "Fund Operations", prov)
    d = pl.path("intents", "m3_connect", "assessments", aid)
    (d / "sources.json").write_text(json.dumps({"sources": [{"id": "S01", "name": "Performance workbook", "kind": "spreadsheet", "effort": "small",
                                                              "impact": {"score": 0.6, "reasons": []}, "marks": [], "owners": []}]}))
    (d / "findings.json").write_text(json.dumps({"findings": [{"measure_id": "K10", "group": "ready", "reasons": ["Matches."], "pain_points": [],
                                                              "levers": [], "sources": ["S01"]}], "risks": []}))
    got = c.get(f"{BASE}/assessments/{aid}/plan").json()
    assert got["bands"]["now"][0]["team"] == ["Fund Operations"]


# ---- 6. counters --------------------------------------------------------------------------------------------------------------------------
def test_counters_count_actions_and_free_text(tmp_path):
    K.bump(tmp_path, "upload_source")
    K.bump(tmp_path, "check_rule")
    K.bump(tmp_path, "override", free_text=True)
    K.bump(tmp_path, "override", free_text=False)
    assert K.read(tmp_path) == {"actions": {"upload_source": 1, "check_rule": 1, "override": 2}, "actions_total": 4, "free_text": 1}
    assert K.read(tmp_path / "none") == {"actions": {}, "actions_total": 0, "free_text": 0}


def test_an_upload_through_the_route_is_counted(world):
    c, aid = demo_world(world)
    upload(c, aid, "S01", "performance_workbook.xlsx")
    adir = world.plane("m3-a").path("intents", "m3_connect", "assessments", aid)
    assert K.read(adir)["actions"]["upload_source"] == 1
    upload(c, aid, "_auto", "custody_daily_positions.csv")
    assert K.read(adir)["actions"]["upload_source"] == 2
    assert K.read(adir)["free_text"] == 0


# ---- restricted data stays hidden ---------------------------------------------------------------------------------------------------------
def test_a_restricted_profile_sample_and_figure_never_reach_an_outsider(world):
    c, aid = demo_world(world)  # Lens Lee is not on the list
    put_sample(world, system="Performance workbook")
    put_figure(world, "private-market-allocation-2026-09-30", "Private-market allocation", 29.0)
    restrict(world, "Performance workbook")
    restrict(world, "Private-market allocation")
    listed = c.get(url(aid, "/requests")).json()
    assert listed["from_profile"] == [] and listed["to_confirm"] == []
    got = c.get(url(aid, "/benchmarks")).json()
    assert got["measures"] == [] and got["unmatched"] == []
    assert "Private-market" not in json.dumps(got["unmatched"])
    assert c.get(url(aid, "/sources/S01/profile")).json()["profile"] is None


def _restricted_world(world):
    c, aid = demo_world(world)  # Lens Lee is not on the list
    put_sample(world, system="Performance workbook")
    put_figure(world, "private-market-allocation-2026-09-30", "Private-market allocation", 29.0)
    restrict(world, "Performance workbook")
    restrict(world, "Private-market allocation")
    return c, aid, person(world, "m3-a", "Somebody Else")


def test_a_listed_person_opening_first_leaves_nothing_restricted_for_an_outsider(world):
    outsider, aid, listed = _restricted_world(world)
    for path in ("/requests", "/benchmarks", "/sources/S01/profile"):
        assert listed.get(url(aid, path)).status_code == 200
    adir = world.plane("m3-a").path("intents", "m3_connect", "assessments", aid)
    shared = " ".join(p.read_text(errors="ignore") for p in adir.rglob("*.json"))
    for word in ("performance_workbook", "Private-market", "Monthly pack Sep", "Sample file"):
        assert word not in shared
    got = [outsider.get(url(aid, p)).text for p in ("/requests", "/benchmarks", "/sources/S01/profile")]
    assert [w for w in ("performance_workbook", "Monthly pack Sep", "Sample file", "29.0") if w in " ".join(got)] == []
    bench = outsider.get(url(aid, "/benchmarks")).json()  # (the measure's own name stays in the catalogue's choices; no figure is behind it)
    assert bench["measures"] == [] and bench["unmatched"] == []
    assert outsider.get(url(aid, "/requests")).json()["from_profile"] == []


def test_a_listed_person_gets_no_auto_adopted_restricted_items_but_can_place_them(world):
    _, aid, listed = _restricted_world(world)
    got = listed.get(url(aid, "/requests")).json()
    assert got["from_profile"] == [], got
    assert [x["file"] for x in got["to_confirm"]] == ["performance_workbook.xlsx"]
    bench = listed.get(url(aid, "/benchmarks")).json()
    assert "Private-market" not in json.dumps(bench["measures"]) and bench["unmatched"] == []
    key = got["to_confirm"][0]["key"]
    placed = listed.post(url(aid, "/sources/S01/upload"), json={"profile_sample": key})
    assert placed.status_code == 200 and placed.json()["profile"]["tables"]


def test_opening_the_screens_again_changes_no_file_and_writes_nothing_restricted(world):
    outsider, aid, listed = _restricted_world(world)
    put_figure(world, "open-measure-2026-09-30", "Open measure", 11.0)
    adir = world.plane("m3-a").path("intents", "m3_connect", "assessments", aid)
    snap = lambda: {str(p.relative_to(adir)): p.read_bytes() for p in adir.rglob("*") if p.is_file()}  # noqa: E731
    for c in (listed, outsider):
        c.get(url(aid, "/requests")), c.get(url(aid, "/benchmarks"))
    first = snap()
    for c in (outsider, listed, outsider):
        c.get(url(aid, "/requests")), c.get(url(aid, "/benchmarks"))
    assert snap() == first
    assert b"Private-market" not in b"".join(first.values()) and b"performance_workbook" not in b"".join(first.values())


def test_the_profile_is_read_for_the_viewer_not_raw(world):
    demo_world(world)
    put_sample(world, system="Performance workbook")
    restrict(world, "Performance workbook")
    pl = world.plane("m3-a")
    outsider = profile.Viewer("Lee", frozenset({"analyst"}))
    assert FP.samples(pl, outsider) == []
    listed = FP.samples(pl, profile.Viewer("Test Somebody Else", frozenset({"analyst"})))
    assert len(listed) == 1 and listed[0]["file"] == "performance_workbook.xlsx" and listed[0]["data"]


# ---- round 2: the same leak class on other paths ------------------------------------------------------------------------------------------
def _plan_world(world):
    c, aid = demo_world(world)  # Lens Lee, an analyst, is not on any list
    pl = world.plane("m3-a")
    prov = {"mark": "stated", "by": "Lens", "agent": "lens", "from": "People list, sheet 1"}
    profile.record(pl, "people.owen-owner-illustrative.name", "Owen Owner (illustrative)", prov)
    profile.record(pl, "people.owen-owner-illustrative.team", "Secret Desk", prov)
    restrict(world, "Secret Desk")
    d = pl.path("intents", "m3_connect", "assessments", aid)
    (d / "sources.json").write_text(json.dumps({"sources": [{"id": "S01", "name": "Performance workbook", "kind": "spreadsheet", "effort": "small",
                                                              "impact": {"score": 0.6, "reasons": []}, "marks": [], "owners": [], "measures": ["K10"]}]}))
    (d / "findings.json").write_text(json.dumps({"findings": [{"measure_id": "K10", "group": "ready", "reasons": ["Matches."], "pain_points": [],
                                                              "levers": [], "sources": ["S01"]}], "risks": []}))
    return c, aid, d


def test_a_restricted_teams_name_never_reaches_the_shared_plan(world):
    outsider, aid, d = _plan_world(world)
    admin = person(world, "m3-a", "Head Honcho", ("company_admin",))
    assert admin.get(f"{BASE}/assessments/{aid}/plan").status_code == 200  # the head of data drafts the plan first
    got = outsider.get(f"{BASE}/assessments/{aid}/plan").json()
    assert "Secret Desk" not in json.dumps(got)
    assert "Secret Desk" not in (d / "plan.json").read_text()


def _placed_world(world):
    """A restricted sample the listed person placed by hand on S01; the trial and findings hold a figure computed from it."""
    outsider, aid, listed = _restricted_world(world)
    key = listed.get(url(aid, "/requests")).json()["to_confirm"][0]["key"]
    assert listed.post(url(aid, "/sources/S01/upload"), json={"profile_sample": key}).status_code == 200
    return outsider, aid, listed, world.plane("m3-a").path("intents", "m3_connect", "assessments", aid)


def test_a_restricted_sample_placed_by_hand_is_served_only_to_people_who_may_see_it(world):
    outsider, aid, listed, adir = _placed_world(world)
    mark = (adir / "intake" / "S01" / "from_profile.json").read_text()
    assert "performance_workbook" not in mark and "Sample file" not in mark  # the shared mark holds no name and no label
    got = [outsider.get(url(aid, p)).text for p in ("/requests", "/sources/S01/profile")]
    assert [w for w in ("performance_workbook", "Sample file", "sheet 1", '"row_count"') if w in " ".join(got)] == []
    assert outsider.get(url(aid, "/sources/S01/profile")).json()["profile"] is None
    shown = outsider.get(url(aid, "/requests")).json()
    assert [(f["source_id"], f["from"], f["files"], f["profile"]) for f in shown["from_profile"]] == [("S01", "A restricted sample", [], None)]
    assert all(r["profile"] is None for r in shown["requests"] if r["source_id"] == "S01")
    mine = listed.get(url(aid, "/requests")).json()["from_profile"]
    assert [f["files"] for f in mine] == [["performance_workbook.xlsx"]] and mine[0]["profile"]["tables"]
    assert listed.get(url(aid, "/sources/S01/profile")).json()["profile"]["tables"]


def test_figures_computed_from_a_restricted_sample_are_masked_per_viewer(world):
    outsider, aid, listed, adir = _placed_world(world)
    (adir / "sources.json").write_text(json.dumps({"sources": [{"id": "S01", "name": "Performance workbook", "kind": "spreadsheet", "effort": "small",
                                                                 "impact": {"score": 0.6, "reasons": []}, "marks": [], "owners": [], "measures": ["K10"]}]}))
    (adir / "trial.json").write_text(json.dumps({"K10": {"ours": 12.5, "theirs": 12.5, "result": "match", "reasons": ["Our figure 12.5"]}}))
    (adir / "findings.json").write_text(json.dumps({"measures": {"K10": {"measure": "K10", "group": "ready", "reasons": ["Our figure 12.5"], "pain_points": [],
                                                                         "levers": [], "sources": ["S01"]}}, "risks": [], "left_out": []}))
    seen = outsider.get(f"{BASE}/assessments/{aid}/trial").json()["measures"]
    row = next(m for m in seen if m["measure"] == "K10")
    assert row["restricted"] is True and "12.5" not in json.dumps(row)
    assert "12.5" not in outsider.get(f"{BASE}/assessments/{aid}/findings").text
    own = next(m for m in listed.get(f"{BASE}/assessments/{aid}/trial").json()["measures"] if m["measure"] == "K10")
    assert own["restricted"] is False and own.get("ours") == 12.5


def test_a_restriction_added_after_adoption_takes_effect(world):
    c, aid = demo_world(world)  # Lens Lee, not on any list
    put_sample(world, system="Performance workbook")
    first = c.get(url(aid, "/requests")).json()
    assert [f["files"] for f in first["from_profile"]] == [["performance_workbook.xlsx"]]  # open at the time: adopted
    restrict(world, "Performance workbook")
    adir = world.plane("m3-a").path("intents", "m3_connect", "assessments", aid)
    marks = (adir / "intake" / "S01" / "from_profile.json").read_bytes()
    after = [c.get(url(aid, p)).text for p in ("/requests", "/sources/S01/profile")]
    assert [w for w in ("performance_workbook", "Sample file") if w in " ".join(after)] == []
    assert c.get(url(aid, "/sources/S01/profile")).json()["profile"] is None
    assert [f["from"] for f in c.get(url(aid, "/requests")).json()["from_profile"]] == ["A restricted sample"]
    assert (adir / "intake" / "S01" / "from_profile.json").read_bytes() == marks  # and it is not adopted again
    listed = person(world, "m3-a", "Somebody Else")
    assert [f["files"] for f in listed.get(url(aid, "/requests")).json()["from_profile"]] == [["performance_workbook.xlsx"]]


def test_an_unbound_near_name_does_not_match_a_restricted_list(world):
    demo_world(world)
    put_sample(world, system="Performance workbook")
    restrict(world, "Performance workbook")  # the list holds "Test Somebody Else"
    pl = world.plane("m3-a")
    assert FP.samples(pl, profile.Viewer("Somebody Else", frozenset({"analyst"}))) == []
    assert len(FP.samples(pl, profile.Viewer("Test Somebody Else", frozenset({"analyst"})))) == 1


# ---- the demo workspace's September trial (skipped when the local files are absent) ---------------------------------------------------
def _demo_root():
    here = Path(__file__).resolve()
    for up in here.parents:
        found = next(iter(sorted((up / "local").glob("*/08-samples"))), None) if (up / "local").is_dir() else None
        if found is not None and (found.parent / "EXPECTED-OUTCOMES.md").is_file():
            return found.parent
    return None


DEMO_ROOT = _demo_root()
SOURCE_IDS = ("S01", "S02", "S03", "S07", "S09", "S12", "S16", "S17", "S18")
FEEDS = {"K04": ["S03"], "K05": ["S02"], "K09": ["S07"], "K10": ["S09"], "K12": ["S01"], "K15": ["S09", "S16"], "K16": ["S12", "S09"],
         "K17": ["S17", "S09"], "K19": ["S18"]}


def _sample_file(root: Path, sid: str) -> Path:
    """The September file of a source's folder (the index file covers all three months)."""
    folder = next(d for d in (root / "08-samples").iterdir() if d.name.startswith(sid + "_"))
    return next(f for f in sorted(folder.iterdir()) if "2026-09" in f.name or f.name.startswith("index_levels"))


@pytest.mark.skipif(DEMO_ROOT is None, reason="the demo workspace's local files are not here")
def test_the_demo_september_trial_reproduces_the_answer_key(tmp_path):
    root, adir = DEMO_ROOT, tmp_path / "a"
    pl = kit_plane(tmp_path)
    for sid in SOURCE_IDS[:-1]:  # what the organiser brought on "Bring what you have": the samples, the glossary, then the pack
        f = _sample_file(root, sid)
        reader.add_upload(pl, 8, "Pia Profile", f.name, f.read_bytes(), system=sid)
    gloss = root / "04-definitions" / "business_glossary.xlsx"
    reader.add_upload(pl, 8, "Pia Profile", gloss.name, gloss.read_bytes(), system="S18")
    pack = root / "03-reporting" / "imc_pack_2026-09.xlsx"
    reader.add_upload(pl, 3, "Pia Profile", pack.name, pack.read_bytes())
    viewer = profile.Viewer("Ana Analyst", frozenset({"analyst"}))
    kpis = pack_kpis()
    measures = [{"id": k["id"], "name": k["name"], "restricted": k["id"] == "K18", "definition": k["definition"], "problem_ids": [], "owners": {}} for k in kpis]
    taken = FP.samples(pl, viewer)
    assert len(taken) == len(SOURCE_IDS)
    for s in taken:
        header, rows = FP.T.read_table(s["file"], s["data"])
        (adir / "intake" / s["system"]).mkdir(parents=True, exist_ok=True)
        (adir / "intake" / s["system"] / "rows.json").write_text(json.dumps(PR.rows_of(header, rows)))
    (adir / "sources.json").write_text(json.dumps([{"id": s, "name": s, "measures": [k for k, v in FEEDS.items() if s in v]} for s in SOURCE_IDS]))
    FP.adopt_figures(adir, FP.figures(pl, viewer), measures, {"to": "2026-09-30"}, lambda: 1790000000)
    assert {m["measure_id"] for m in T.benchmarks(adir)} >= {"K04", "K05", "K09", "K10", "K12", "K15", "K16", "K17", "K19"}
    syn = yaml.safe_load((Path(__file__).resolve().parents[3] / "packs" / "family_office" / "1" / "column_synonyms.yaml").read_text(encoding="utf-8"))["feeds"]
    C.compile_all(None, Gate(), "co-test", pl, adir, measures, T.columns_by_source(adir), lambda m: T.feeders(adir, m), kpis, F.technical_of, syn)
    trial = T.run_trial(adir, measures)
    result = {k: v["result"] for k, v in trial.items()}
    match, gap = {"K04", "K09", "K10", "K17", "K19"}, {"K05", "K12", "K15"}
    assert {k for k, r in result.items() if r == "matches"} == match, trial
    assert {k for k, r in result.items() if r == "gap"} == gap, trial
    assert all(r == "cannot" for k, r in result.items() if k not in match | gap)
    rules = R.read_rules(adir)
    assert all(rules[k].get("auto_checked") for k in match) and not any(rules.get(k, {}).get("auto_checked") for k in gap)


# ---- the two filters the demo needed (no demo files) --------------------------------------------------------------------------------------
def test_listed_in_reads_another_source_and_not_contains_leaves_shared_owners_out():
    from modules.m3_connect.domain import engine as E
    data = {"a": [{"fund": "F1", "value": 60}, {"fund": "F2", "value": 30}, {"fund": "Cash", "value": 10}],
            "b": [{"fund": "F1", "mark": "X"}, {"fund": "F2", "mark": None}],
            "c": [{"term": "T1", "owner": "Ann"}, {"term": "T2", "owner": "Ann or Bo"}, {"term": "T3", "owner": None}]}
    listed = {"column": "fund", "op": "listed_in", "value": "fund", "source": "b"}
    rule = {"op": "ratio", "scale": 100, "source": "a",
            "numerator": {"op": "sum", "column": "value", "source": "a", "filters": [{**listed, "where": "mark"}]},
            "denominator": {"op": "sum", "column": "value", "source": "a", "filters": [listed]}}
    assert E.run(rule, data.get)["value"] == pytest.approx(60 / 90 * 100)
    assert E.run(rule, {"a": data["a"]}.get)["cannot"].endswith("has not arrived yet.")
    owned = {"op": "count", "column": "term", "source": "c", "filters": [{"column": "owner", "op": "not_contains", "value": " or "}]}
    assert E.run(owned, data.get)["value"] == 1
    assert R.shape_problems(rule) == [] and E.sources_of(rule["numerator"]) == {"a", "b"}
    assert "is in the list of fund that has a mark" in R.words(rule)




def test_the_company_admin_outside_a_restricted_list_gets_the_silhouette_too(world):
    """A-069: once somebody is named, the admin is like anyone else."""
    _, aid, listed, adir = _placed_world(world)
    (adir / "sources.json").write_text(json.dumps({"sources": [{"id": "S01", "name": "Performance workbook", "kind": "spreadsheet", "effort": "small",
                                                                 "impact": {"score": 0.6, "reasons": []}, "marks": [], "owners": [], "measures": ["K10"]}]}))
    (adir / "trial.json").write_text(json.dumps({"K10": {"ours": 12.5, "theirs": 12.5, "result": "match", "reasons": ["Our figure 12.5"]}}))
    (adir / "findings.json").write_text(json.dumps({"measures": {"K10": {"measure": "K10", "group": "ready", "reasons": ["Our figure 12.5"], "pain_points": [],
                                                                         "levers": [], "sources": ["S01"]}}, "risks": [], "left_out": []}))
    admin = person(world, "m3-a", "Head Honcho", ("company_admin",))
    row = next(m for m in admin.get(f"{BASE}/assessments/{aid}/trial").json()["measures"] if m["measure"] == "K10")
    assert row["restricted"] is True and "12.5" not in json.dumps(row)
    assert "12.5" not in admin.get(f"{BASE}/assessments/{aid}/findings").text
    plan = admin.get(f"{BASE}/assessments/{aid}/plan")
    assert plan.status_code == 200 and "12.5" not in plan.text and "Performance workbook" not in plan.text
