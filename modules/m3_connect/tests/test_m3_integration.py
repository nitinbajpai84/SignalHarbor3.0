"""M3-INT: module 2's new outcome keys read with defaults, the shapes P02 writes read by P03, P03's files read by P04, the re-check of a sent-back risk."""
import json
from pathlib import Path

from m3_kit import restrict, signed_baseline
from modules.m3_connect.domain import accept as X
from modules.m3_connect.domain import findings as F
from modules.m3_connect.domain import inputs as I
from modules.m3_connect.domain import plan as P
from modules.m3_connect.domain import trial as T

ADMIN = I.SYSTEM  # the full read that shared records are built from (A-069: the admin is not "everyone")
OUTSIDER = I.Viewer("Other Olly", frozenset({"analyst"}))


def cell(v, mark="stated"):
    return {"value": v, "mark": mark, "by": "Test Data Dan", "at": "2026-10-01T10:00:00+00:00"}


def outcome_path(world, company="m3-a") -> Path:
    return next(world.plane(company).path("intents", "m2_baseline", "outcomes").glob("*.json"))


def add_keys(world, **keys) -> dict:
    p = outcome_path(world)
    doc = json.loads(p.read_text())
    doc.update(keys)
    p.write_text(json.dumps(doc))
    return doc


def read(world, viewer):
    plane = world.plane("m3-a")
    doc = json.loads(outcome_path(world).read_text())
    return I.read_inputs(plane, doc, doc["charter_outcome_id"], viewer)


def test_an_older_record_without_the_new_keys_reads_with_defaults(world):
    signed_baseline(world)
    p = outcome_path(world)
    doc = {k: v for k, v in json.loads(p.read_text()).items() if k not in ("glossary", "technical", "ambiguities", "left_out", "documents")}
    p.write_text(json.dumps(doc))
    got = read(world, ADMIN)
    assert got["left_out"] == [] and got["glossary"] == [] and len(got["measures"]) == 3
    assert all(m["technical"] is None and m["ambiguities"] == [] for m in got["measures"])


def test_technical_ambiguities_and_left_out_are_read_and_a_restricted_measure_gets_none_of_them(world):
    signed_baseline(world)
    add_keys(world,
             technical={"K1": {"sources": cell(["S01"]), "tables": cell(["T01"]), "fields": cell(["F001"]), "calculation": cell("Sum of amount, open notices"),
                               "filters": cell("unknown", "unknown"), "grain": cell("per notice"), "period": cell(None, "unknown"), "currency_basis": cell("SGD"),
                               "notes": cell(""), "confirmed": {"by": "Test Data Dan", "at": "2026-10-02"}},
                        "K2": {"calculation": cell("Concentration of the largest issuer")}},
             ambiguities=[{"kpi_id": "K1", "id": "a1", "kind": "definition", "text": "Which notice date counts", "question": "?", "where": "K1", "status": "accepted",
                           "reason": "Close enough", "by": "Test Business Bea", "at": "2026-10-02"},
                          {"kpi_id": "K2", "id": "a2", "kind": "definition", "text": "Secret wording", "status": "accepted", "by": "Test Business Bea"}],
             left_out=[{"kpi_id": "K3", "name": "Manager fee reconciliation", "reason": "No data this year", "by": "Test Sponsor Sam", "at": "2026-10-02"}],
             glossary=[{"kpi_id": "K1", "term": "Capital calls"}, {"kpi_id": "K2", "term": "Concentration"}])
    restrict(world, "m3-a", "K2", ["Test Reader Rae"])
    full = read(world, ADMIN)
    k1 = next(m for m in full["measures"] if m["id"] == "K1")
    assert k1["technical"]["calculation"] == "Sum of amount, open notices" and k1["technical"]["filters"] is None and k1["technical"]["period"] is None
    assert k1["technical"]["confirmed"]["by"] == "Test Data Dan"
    assert F.technical_of(k1)[0] == "Sum of amount, open notices per notice SGD"  # unknown parts are left out of the text the model sees
    assert [a["id"] for a in k1["ambiguities"]] == ["a1"]
    assert {m["id"] for m in full["measures"]} == {"K1", "K2"} and [r["kpi_id"] for r in full["left_out"]] == ["K3"]  # left out: not scored, not tried
    assert {e["kpi_id"] for e in full["glossary"]} == {"K1", "K2"}
    out = read(world, OUTSIDER)
    k2 = next(m for m in out["measures"] if m["id"] == "K2")
    assert k2 == {"id": "K2", "name": "A restricted measure", "restricted": True}
    assert "Secret wording" not in json.dumps(out) and "Concentration" not in json.dumps(out) and [e["kpi_id"] for e in out["glossary"]] == ["K1"]
    restrict(world, "m3-a", "K3", [])  # a restricted measure that was left out stays a placeholder: nothing about it, not even its reason
    assert "No data this year" not in json.dumps(read(world, OUTSIDER)) and [r["kpi_id"] for r in read(world, ADMIN)["left_out"]] == ["K3"]


def test_an_accepted_ambiguity_is_a_risk_that_says_who_accepted_it_in_module_2_and_a_left_out_measure_goes_to_later(world, tmp_path):
    signed_baseline(world)
    add_keys(world, ambiguities=[{"kpi_id": "K1", "id": "a1", "text": "Which notice date counts", "status": "accepted", "by": "Test Business Bea", "at": "2026-10-02"}],
             left_out=[{"kpi_id": "K3", "name": "Manager fee reconciliation", "reason": "No data this year", "by": "Test Sponsor Sam", "at": "2026-10-02"}])
    inputs = read(world, ADMIN)
    adir = tmp_path / "assessments" / ("a" * 32)
    adir.mkdir(parents=True)
    (adir / "sources.json").write_text(json.dumps({"sources": [{"id": "S01", "name": "Source", "measures": ["K1", "K2"], "impact": {"score": 0.5}, "marks": {"effort": "small"}}]}))
    data = F.build(adir, inputs, set())
    risk = next(r for r in data["risks"] if r["id"] == "risk-ambiguity-K1-a1")
    assert risk["kind"] == "ambiguity" and "module 2" not in risk["text"] and risk["accepted_in_module_2"]["by"] == "Test Business Bea"  # said once, not in every text
    assert any("Known risk, accepted in module 2: Which notice date counts" in r for r in data["measures"]["K1"]["reasons"])
    assert "K3" not in data["measures"] and data["left_out"][0]["measure"] == "K3"
    got = P.inputs_for_plan(adir)  # P04 reads P03's real file: measures keyed by id, sources from P01's real sources.json
    assert {f["measure_id"]: f["sources"] for f in got["findings"]} == {"K1": ["S01"], "K2": ["S01"]} and got["left_out"][0]["measure_id"] == "K3"
    assert not any("K3" in i["measures"] for i in P.draft(got, set(), {}))  # left out in module 2: not a plan item (D10)


def test_p02s_files_are_read_by_the_trial_and_a_sent_back_risk_is_decided_only_after_a_recheck(tmp_path):
    adir = tmp_path / "assessments" / ("a" * 32)
    (adir / "intake" / "S01").mkdir(parents=True)
    (adir / "intake" / "S01" / "rows.json").write_text(json.dumps({"source_id": "S01", "tables": [
        {"file": "x_perf.csv", "table_id": "T01", "name": "Perf", "columns": [{"name": "Closing Value (SGD)", "type": "decimal", "field_id": "F1", "personal": False},
                                                                             {"name": "Extra", "type": "string", "field_id": None, "personal": False}],
         "rows": [{"Closing Value (SGD)": 10.5, "Extra": "a"}, {"Closing Value (SGD)": None, "Extra": "b"}]}]}))
    (adir / "intake" / "S01" / "profile.json").write_text(json.dumps({"expected": [{"field_id": "F1", "name": "closing_value", "found_as": "Closing Value (SGD)"}]}))
    (adir / "benchmarks.json").write_text(json.dumps({"file": None, "measures": {"K1": {"figure": 3.5, "unit": "%", "period_end": "2026-09-30", "came_from": "pack p1",
                                                                                         "given_by": "Test", "matched": "auto"}}, "unmatched": []}))
    assert T.rows_for(adir, "S01") == [{"closing_value": 10.5, "Extra": "a"}, {"closing_value": None, "Extra": "b"}]
    assert T.benchmarks(adir) == [{"measure_id": "K1", "figure": 3.5, "unit": "%", "period_end": "2026-09-30", "source_note": "pack p1"}]
    # a sent-back risk: not decided until P03 has re-run
    (adir / "findings.json").write_text(json.dumps({"measures": {}, "risks": [{"id": "risk-measure-K1", "kind": "risk", "text": "t", "measures": ["K1"], "pain_points": [], "decision": None}]}))
    (adir / "decisions.json").write_text(json.dumps({"risks": {"risk-measure-K1": {"decision": "sent_back", "reason": "Count them", "at": "2026-01-04T09:00:00.500000+00:00"}}}))
    state = lambda: P.risk_state(P.inputs_for_plan(adir)["risks"][0], X.read_decisions(adir)["risk-measure-K1"])  # noqa: E731
    assert state() == "sent_back"
    F.build(adir, {"measures": [{"id": "K1", "name": "K one", "definition": "d"}], "sources": [], "pain_points": [], "levers": [], "gaps": []}, set())
    risks = json.loads((adir / "findings.json").read_text())["risks"]
    assert risks[0]["rechecked_at"] > "2026-01-04T09:00:00.500000+00:00" and state() == "rechecked" and P.is_decided(state())


def test_an_outsider_gets_nothing_about_a_restricted_left_out_measure_from_the_findings_or_the_plan_routes(world):
    from m3_kit import BASE, person
    signed_baseline(world)
    add_keys(world,
             ambiguities=[{"kpi_id": "K1", "id": "a1", "text": "Counts what Exposure concentration counts", "status": "accepted", "by": "Test Business Bea"},
                          {"kpi_id": "K2", "id": "a2", "text": "Secret wording", "status": "accepted", "by": "Test Business Bea"}],
             left_out=[{"kpi_id": "K2", "name": "Exposure concentration", "reason": "Secret reason", "by": "Test Sponsor Sam", "at": "2026-10-02"}])
    restrict(world, "m3-a", "K2", ["Test Reader Rae"])
    olly, head = person(world, "m3-a", "Other Olly", ("analyst",)), person(world, "m3-a", "Head Henry", ("company_admin",))
    aid = olly.post(f"{BASE}/assessments").json()["assessment"]["id"]
    a = f"{BASE}/assessments/{aid}"
    assert olly.post(f"{a}/trial/run").status_code == 200  # the analyst runs it: findings must still be built from the whole, then masked per reader
    for path in ("/findings", "/plan", "/risks"):
        got = olly.get(a + path)
        assert got.status_code == 200
        for secret in ("Secret reason", "Secret wording", "Exposure concentration"):
            assert secret not in got.text, (path, secret)
    seen = head.get(f"{a}/findings").json()
    assert [(x["measure"], x["reason"]) for x in seen["left_out"]] == [("K2", None)]  # A-069: named, so the admin outside the list is masked too
    assert olly.get(f"{a}/findings").json()["left_out"] == [{"measure": "K2", "name": "A restricted measure", "reason": None, "restricted": True}]


def test_a_left_out_measure_is_no_plan_item_and_a_restricted_one_is_masked_in_the_outcome():
    got = {"ready": True, "findings": [], "risks": [], "sources": {}, "left_out": [{"measure_id": "K2", "name": "N", "reason": "Secret reason", "restricted": True},
                                                                              {"measure_id": "K3", "name": "M", "reason": "Plain reason"}]}
    items = P.draft(got, set(), {})
    assert items == []  # left out in module 2: listed once beside the plan (api/plan.py `left_out`), never a plan item
    outcome = X.build_outcome("o" * 32, {"assessment_id": "a", "signed_at": "x", "signatures": [], "items": items}, [], got, {"restricted": [], "names": {}})
    text = json.dumps(outcome)
    assert "Plain reason" in text and "Secret reason" not in text and outcome["left_out"][0]["name"] == "A restricted measure"


def test_the_matcher_does_not_link_benchmark_return_to_a_return_field():
    from modules.m3_connect.domain import intake_match as M
    assert M.match_columns([{"name": "Benchmark Return"}], [{"field_id": "F1", "name": "Return"}]) == {}
    assert M.match_columns([{"name": "Acct"}], [{"field_id": "F1", "name": "account"}])["Acct"]["confidence"] == "high"
