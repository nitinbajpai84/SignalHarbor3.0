"""M3-FIX-A: the logic defects of the live module 3 run (docs/guides/e2e-m3/run-report.md, D3 and D5 to D10). Synthetic data only; model calls are stubs."""
import json
from pathlib import Path

import pytest
import yaml

from m3_kit import BASE, person, restrict, signed_baseline
from modules.m3_connect.domain import accept as X
from modules.m3_connect.domain import findings as F
from modules.m3_connect.domain import inputs as I
from modules.m3_connect.domain import intake as N
from modules.m3_connect.domain import intake_match as M
from modules.m3_connect.domain import plan as P
from modules.m3_connect.domain import profile as PR
from modules.m3_connect.domain import rules as R
from modules.m3_connect.domain import sources as S
from modules.m3_connect.domain import steps as ST
from modules.m3_connect.domain import trial as T
from test_m3_integration import add_keys, read, ADMIN
from test_m3_plan_api import FINDINGS, SOURCES, Stub, start, url
from test_m3_sources import EXTRAS, c as cell, hand_inputs, src, table

PACK = Path(__file__).resolve().parents[3] / "packs" / "family_office" / "1"


@pytest.fixture(autouse=True)
def registry():
    saved = dict(ST._registry)
    ST._registry.clear()
    ST.register("plan", X.step_state)
    yield
    ST._registry.clear()
    ST._registry.update(saved)  # leave the other tests' steps as they were


# ---- D5: findings ---------------------------------------------------------------------------------------------------------------------------
RULE = {"state": "draft", "rule": {"op": "sum", "column": "a"}}
MATCH = {"our_figure": 1.0, "result": "matches"}


def amb(status, text="what is unclear"):
    return {"id": "a1", "status": status, "text": text, "by": "Mei Tan"}


def test_a_matching_measure_is_ready_even_with_accepted_module_2_notes_but_not_with_an_open_one():
    accepted = {"id": "K4", "name": "Obligations", "definition": "d", "ambiguities": [amb("accepted")]}
    assert F._classify(accepted, MATCH, RULE, [])[0] == "ready"
    assert F._classify({**accepted, "ambiguities": [amb("open")]}, MATCH, RULE, [])[0] == "unclear"


@pytest.mark.parametrize("rec", [None, {"state": R.COULD_NOT, "reason_kind": "invalid", "reason": "inputs unknown"}, {"state": R.COULD_NOT, "reason_kind": "data", "reason": "x"}])
def test_a_measure_with_no_rule_is_never_ready_it_is_unknown_no_rule_yet(rec):
    group, why = F._classify({"id": "K1", "name": "Cash", "definition": "d", "ambiguities": []}, {}, rec, [{"id": "S1", "measures": ["K1"]}])
    assert group == "unknown" and why[0].startswith("No rule yet")


def test_the_plan_never_words_a_measure_outside_now_as_ready(world):
    signed_baseline(world)
    stub = Stub("I1 = Custodian reporting is ready to build.\nI2 = Exposure concentration is ready because the figures match.")
    world.app.state.lens_model_factory = lambda plane: stub
    c, aid, _ = start(world)
    plan = c.get(url(aid, "/plan")).json()["bands"]
    assert "ready to build" in plan["now"][0]["summary"]
    assert "ready" not in plan["next"][0]["summary"].lower().replace("already", "")


# ---- D7: text -------------------------------------------------------------------------------------------------------------------------------
def test_markdown_goes_and_catalogue_ids_become_the_field_name_or_are_dropped():
    names = {"F001": "cash_balance", "T01": "Statement table", "F002": None}
    assert I.plain_text("F001 `cash_balance` *is* not in **T01**", names) == "cash_balance is not in Statement table"
    assert I.plain_text("Check F002 first, and the Q3 plan", names) == "Check first, and the Q3 plan"
    assert I.plain_text(None, names) is None


def test_module_2_text_is_plain_in_module_3(world):
    signed_baseline(world)
    add_keys(world, ambiguities=[{"kpi_id": "K1", "id": "a1", "text": "The *date* `due_date` is unclear", "question": "Which `one`?", "status": "accepted", "by": "Mei Tan"}],
             left_out=[{"kpi_id": "K3", "name": "Fees", "reason": "**Not ready**: no `file`", "by": "Mei Tan", "at": "2026-10-02"}])
    got = read(world, ADMIN)
    assert got["measures"][0]["ambiguities"][0]["text"] == "The date due_date is unclear" and got["left_out"][0]["reason"] == "Not ready: no file"


def test_accepted_in_module_2_is_not_repeated_on_every_risk_and_the_risk_list_says_it_once(world):
    signed_baseline(world)
    risks = [{"id": f"M{i}", "kind": "ambiguity", "text": f"Ambiguity {i}", "measures": ["K2"], "pain_points": [], "decision": None,
              "accepted_in_module_2": {"by": "Mei Tan", "at": "2026-10-02T09:00:00+00:00", "reason": "ok"}} for i in (1, 2)]
    c, aid, _ = start(world, findings={**FINDINGS, "risks": risks + FINDINGS["risks"][1:]})
    got = c.get(url(aid, "/risks")).json()
    assert got["notes"] == [{"kind": "accepted_in_module_2", "by": "Mei Tan", "at": "2026-10-02", "count": 2,
                             "text": "2 risks were accepted in module 2 by Mei Tan on 2026-10-02. They are known risks and need no new decision."}]
    assert all("accepted in module 2 by" not in r["text"] for r in got["risks"])
    # decided already: only module 3's own risks are open, and the plan can be signed once those are decided
    assert got["counts"] == {"open": 2, "sent_back": 0, "accepted": 2, "rechecked": 0}
    m1 = next(r for r in got["risks"] if r["id"] == "M1")
    assert m1["state"] == "accepted" and m1["decision"]["by"] == "Mei Tan" and m1["accepted_in_module_2"]["at"].startswith("2026-10-02")
    assert c.post(url(aid, "/risks/accept-all"), json={}).json()["accepted"] == 2  # not the module 2 ones
    sponsor = person(world, "m3-a", "Sam Sponsor", ("sponsor",))
    assert sponsor.post(url(aid, "/plan/sign")).status_code == 200


def test_a_person_may_send_back_a_risk_module_2_accepted(world):
    signed_baseline(world)
    risk = {"id": "M1", "kind": "ambiguity", "text": "Ambiguity", "measures": ["K2"], "pain_points": [], "decision": None,
            "accepted_in_module_2": {"by": "Mei Tan", "at": "2026-10-02T09:00:00+00:00", "reason": "ok"}}
    c, aid, _ = start(world, findings={**FINDINGS, "risks": [risk]})
    back = c.post(url(aid, "/risks/M1/decision"), json={"decision": "sent_back", "reason": "Not settled"}).json()
    assert next(r for r in back["risks"] if r["id"] == "M1")["state"] == "sent_back" and back["counts"]["sent_back"] == 1


def test_a_risk_text_from_findings_carries_no_accepted_by_suffix(tmp_path):
    inputs = {"measures": [{"id": "K1", "name": "Cash", "definition": "d", "ambiguities": [amb("accepted", "t1"), amb("accepted", "t2")]}],
              "sources": [], "pain_points": [], "levers": [], "gaps": []}
    inputs["measures"][0]["ambiguities"][1]["id"] = "a2"
    data = F.build(tmp_path, inputs, set())
    texts = [r["text"] for r in data["risks"] if r["kind"] == "ambiguity"]
    assert len(texts) == 2 and all("module 2" not in t for t in texts)
    assert all(r["accepted_in_module_2"]["by"] == "Mei Tan" for r in data["risks"] if r["kind"] == "ambiguity")


def test_no_date_is_null_not_a_placeholder(world):
    signed_baseline(world)
    c, aid, _ = start(world)
    item = c.get(url(aid, "/plan")).json()["bands"]["next"][0]
    assert item["date"] is None and item["date_text"] is None


# ---- D8: scan -------------------------------------------------------------------------------------------------------------------------------
def test_the_gap_list_names_low_fill_and_partly_empty_columns_even_when_they_match_no_catalogue_field():
    col = lambda n, fill, nulls, personal=False: {"name": n, "fill": fill, "nulls": nulls, "non_empty": 40 - nulls, "field_id": None, "personal": personal}  # noqa: E731
    tables = [{"table_id": None, "name": None, "series": False, "date_range": None,
               "columns": [col("Asset Cls", 0.9, 4), col("Fees Charged", 0.5, 20), col("Salary", 0.5, 20, True), col("Fund", 1.0, 0)]}]
    gaps = {g["column"]: g for g in PR.gaps_for("S1", tables, [], {"to": "2026-09-30"})}
    assert set(gaps) == {"Asset Cls", "Fees Charged"}
    assert gaps["Asset Cls"]["kind"] == "some_empty" and "4 of 40 rows" in gaps["Asset Cls"]["text"]
    assert gaps["Fees Charged"]["kind"] == "half_empty" and "50%" in gaps["Fees Charged"]["text"] and "20 empty of 40 rows" in gaps["Fees Charged"]["text"]


def test_the_packs_demo_spellings_reach_the_profile_matcher():
    syn = yaml.safe_load((PACK / "column_synonyms.yaml").read_text(encoding="utf-8"))["feeds"]
    fields = [{"field_id": "F1", "name": "period_return"}, {"field_id": "F2", "name": "valuation_date"}, {"field_id": "F3", "name": "value_sgd"}]
    got = M.match_columns([{"name": "Period Return %"}, {"name": "Val Date"}, {"name": "Exposure Value (SGD)"}], fields, syn)
    assert {c: m["field"] for c, m in got.items()} == {"Period Return %": "period_return", "Val Date": "valuation_date", "Exposure Value (SGD)": "value_sgd"}


# ---- D9: risks and roles --------------------------------------------------------------------------------------------------------------------
def restricted_findings():
    risks = [dict(r, restricted=r["id"] == "R1") for r in FINDINGS["risks"]]
    return {**FINDINGS, "risks": risks}


def test_nira_names_who_decides_the_open_risks_and_who_signs_next():
    risk = lambda i, state, restricted=False: {"id": i, "state": state, "restricted": restricted}  # noqa: E731
    assert X.next_sentence(None, [risk("a", "open"), risk("b", "open")]) == "2 risks need a decision from the sponsor."
    assert X.next_sentence(None, [risk("a", "open", True), risk("b", "open", True)]) == "2 risks about measures only some people can see need a decision from the people who can see them."
    assert X.next_sentence(None, [risk("a", "open"), risk("b", "open", True)]) == \
        "1 risk needs a decision from the sponsor, and 1 risk about a measure only some people can see from those people."
    assert X.next_sentence(None, []) == "The plan is ready to sign. The sponsor signs next."
    assert X.next_sentence({"signed_at": None, "signatures": [{"slot": "sponsor"}]}, []) == "Waiting for the head of data to sign."
    assert X.next_sentence({"signed_at": "x", "signatures": []}, []) == "The plan is signed. Module 4 starts from it."


def test_restricted_risks_are_decided_by_the_head_of_data_and_the_list_says_so(world):
    signed_baseline(world)
    restrict(world, "m3-a", "K2", ["Test Reader Rae"])
    c, aid, _ = start(world, findings=restricted_findings())
    outsider = person(world, "m3-a", "Other Olly")
    got = outsider.get(url(aid, "/risks")).json()
    assert got["restricted_note"] == "1 risk is about a measure only some people can see; it is decided by those people."
    named = person(world, "m3-a", "Reader Rae")
    assert named.get(url(aid, "/risks")).json()["restricted_note"] is None
    left = outsider.post(url(aid, "/risks/accept-all"), json={}).json()
    assert left["accepted"] == 2 and left["left_hidden"] == 1 and left["left"] == 1
    assert left["message"] == "Accepted 2 risks. Left 1: it is about a measure only some people can see, which those people decide."
    assert outsider.get(f"{BASE}/assessments/{aid}/next").json()["sentence"] == "1 risk about a measure only some people can see needs a decision from the people who can see it."


# ---- D3: Nira's next step ----------------------------------------------------------------------------------------------------------------
def write(d, name, doc):
    (d / name).write_text(json.dumps(doc), encoding="utf-8")


def req(sid, state="sent", **more):
    return {"id": sid.lower(), "source_id": sid, "source_name": f"Source {sid}", "state": state, "revoked_at": None, **more}


def test_data_request_and_scan_count_only_needed_priority_1_and_2_sources_that_were_not_withdrawn(tmp_path):
    write(tmp_path, "sources.json", {"sources": [{"id": "S1", "zone": "p1", "measures": ["K1"]}, {"id": "S2", "zone": "identify", "measures": ["K1"]},
                                                  {"id": "S3", "zone": "p2", "measures": ["K1"]}, {"id": "S4", "zone": "p1", "measures": ["K1"]},
                                                  {"id": "S5", "zone": "p1", "measures": []}, {"id": "S6", "zone": "p1", "measures": ["K1"]}]})
    write(tmp_path, "requests.json", [req("S1", "arrived"), req("S2"), req("S3", revoked_at="2026-10-01"), req("S4", "will_not_send"), req("S5"), req("S6")])
    assert N.request_state(tmp_path) == {"state": "in_progress", "waiting_on": "Waiting for the owners of Source S6 to send their files."}
    write(tmp_path, "requests.json", [req("S1", "arrived"), req("S2"), req("S3", revoked_at="2026-10-01"), req("S4", "will_not_send"), req("S5"), req("S6", "arrived")])
    assert N.request_state(tmp_path) == {"state": "done"}
    for sid in ("S1", "S6"):
        (tmp_path / "intake" / sid).mkdir(parents=True)
        write(tmp_path / "intake" / sid, "profile.json", {})
    assert N.scan_state(tmp_path) == {"state": "done"}


def test_a_request_can_be_marked_will_not_send_through_revoke(world):
    from test_m3_intake import demo_world, url as iurl
    c, aid = demo_world(world)
    c.post(iurl(aid, "/requests"))
    listed = c.get(iurl(aid, "/requests")).json()["requests"]
    rid = next(r["id"] for r in listed if r["source_id"] == "S01")
    got = c.post(iurl(aid, f"/requests/{rid}/revoke"), json={"will_not_send": True}).json()["request"]
    assert got["state"] == "will_not_send"
    assert c.post(iurl(aid, f"/requests/{rid}/relink")).json()["request"]["state"] == "sent"  # asking again reopens it


def test_only_the_organiser_may_mark_will_not_send_it_is_recorded_and_a_file_reopens_it(world):
    from test_m3_intake import demo_world, intake_dir, upload, url as iurl
    c, aid = demo_world(world)  # Lens Lee started the assessment
    c.post(iurl(aid, "/requests"))
    rid = next(r["id"] for r in c.get(iurl(aid, "/requests")).json()["requests"] if r["source_id"] == "S01")
    other = person(world, "m3-a", "Other Olly")
    refused = other.post(iurl(aid, f"/requests/{rid}/revoke"), json={"will_not_send": True})
    assert refused.status_code == 403 and refused.json()["message"] and "/" not in refused.json()["message"]
    stored = lambda: next(r for r in json.loads((intake_dir(world, aid).parents[1] / "requests.json").read_text()) if r["id"] == rid)  # noqa: E731
    assert stored()["state"] == "sent" and stored().get("revoked_at") is None  # a refusal changes nothing
    admin = person(world, "m3-a", "Head Henry", ("company_admin",))
    assert admin.post(iurl(aid, f"/requests/{rid}/revoke"), json={"will_not_send": True}).status_code == 200
    row = stored()
    assert row["state"] == "will_not_send" and row["will_not_send_by"]["name"] == "Test Head Henry" and row["will_not_send_by"]["account_id"] and row["will_not_send_at"]
    assert upload(c, aid, "S01", "performance_workbook.xlsx").status_code == 200  # the organiser uploads: it reopens
    row = stored()
    assert row["state"] == "arrived" and row["reopened_by"]["name"] == "Test Lens Lee" and row["reopened_at"] and row["will_not_send_by"]["name"] == "Test Head Henry"


def test_the_trial_waits_for_the_analyst_while_a_rule_is_not_checked(tmp_path):
    (tmp_path / "intake" / "S1").mkdir(parents=True)
    write(tmp_path / "intake" / "S1", "rows.json", {"source_id": "S1", "tables": []})
    write(tmp_path, "trial.json", {"K1": {"result": "matches"}})
    write(tmp_path, "rules.json", {"K1": RULE, "K2": {"state": R.COULD_NOT}, "K3": {"state": "checked", "rule": {}}})
    assert T.state(tmp_path) == {"state": "in_progress", "waiting_on": "Waiting for the data analyst to check 1 rule Lens wrote."}
    write(tmp_path, "rules.json", {"K1": {**RULE, "state": "checked"}})
    assert T.state(tmp_path)["state"] == "done"


def test_nira_follows_the_real_stage_and_a_signed_plan_ends_it(world):
    signed_baseline(world)
    c, aid, d = start(world)
    done = lambda p: {"state": "done"}  # noqa: E731
    for step in ("map", "request", "scan"):
        ST.register(step, done)
    ST.register("trial", lambda p: {"state": "in_progress", "waiting_on": "Waiting for the data analyst to check 2 rules Lens wrote."})
    ST.register("findings", done)
    assert c.get(url(aid, "/next")).json() == {"step": "trial", "done": False, "sentence": "Waiting for the data analyst to check 2 rules Lens wrote."}
    ST.register("trial", done)
    assert c.get(url(aid, "/next")).json()["step"] == "plan"
    ST.register("request", lambda p: {"state": "in_progress", "waiting_on": "Waiting for the owners of Source S6 to send their files."})
    assert c.get(url(aid, "/next")).json()["step"] == "request"
    ST.register("request", done)
    base = json.loads((d / "assessment.json").read_text())
    write(d, "assessment.json", {**base, "state": "signed"})
    assert c.get(url(aid, "/next")).json() == {"step": None, "done": True, "sentence": "The plan is signed. Module 4 starts from it."}


# ---- D10: scope ---------------------------------------------------------------------------------------------------------------------------
def test_a_measure_left_out_in_module_2_is_not_a_plan_item_it_is_listed_once(world):
    signed_baseline(world)
    restrict(world, "m3-a", "K2", ["Test Reader Rae"])
    c, aid, d = start(world)
    plan = c.get(url(aid, "/plan")).json()
    assert plan["left_out"] == []
    write(d, "findings.json", {**json.loads((d / "findings.json").read_text()),
                               "left_out": [{"measure": "K9", "name": "Old measure", "reason": "Not ready", "restricted": False},
                                            {"measure": "K2", "name": "Secret measure", "reason": "Secret reason", "restricted": True}]})
    c.post(url(aid, "/plan/draft"))
    plan = c.get(url(aid, "/plan")).json()
    assert [(x["measure"], x["name"], x["reason"]) for x in plan["left_out"]] == [("K9", "Old measure", "Not ready"), ("K2", "A restricted measure", None)]
    items = [i for b in plan["bands"].values() for i in b]
    assert not any(m["id"] == "K9" for i in items for m in i["measures"]) and not any(i["key"].startswith("later:left") for i in items)
    named = person(world, "m3-a", "Reader Rae").get(url(aid, "/plan")).json()
    assert [(x["measure"], x["name"], x["reason"]) for x in named["left_out"]][1] == ("K2", "Secret measure", "Secret reason")


def test_sources_that_feed_no_measure_are_off_the_map_and_off_the_request_and_listed_once():
    inputs = hand_inputs()
    inputs["sources"].append(src("E", "Source E"))
    inputs["tables"].append(table("TE", "E", ""))
    scored = S.score_all(inputs, inputs, EXTRAS)
    assert "E" not in {s["id"] for s in scored} and S.unneeded(inputs) == [{"id": "E", "name": "Source E"}]
    plans = N.source_plan(inputs, {"sources": [{"id": s["id"], "zone": "p1", "measures": s["measures"]} for s in scored] + [{"id": "E", "zone": "p1", "measures": []}]})
    assert "E" not in {p["source_id"] for p in plans} and {p["source_id"] for p in plans} == {s["id"] for s in scored}
    assert "E" not in {p["source_id"] for p in N.source_plan(inputs, None)}  # also without the map's file


def test_the_map_answer_lists_the_sources_not_needed_for_any_measure(world):
    signed_baseline(world)
    c = person(world, "m3-a", "Lens Lee")
    aid = c.post(f"{BASE}/assessments").json()["assessment"]["id"]
    got = c.get(f"{BASE}/assessments/{aid}/sources").json()
    assert "not_needed" in got and all(s["measures_fed"] > 0 for s in got["sources"]) and "left_out" in got
