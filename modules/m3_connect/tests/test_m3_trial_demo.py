"""The demo answer key end to end (fixture rows from demo_module3), compile with a stubbed model, the pack-hint fallback, and the egress rule:
no row value reaches the model."""
import json

import pytest

from m3_trial_kit import DEMO, Gate, Stub, demo_files, demo_inputs, pack_kpis, plane
from modules.m3_connect.agent import compile as C
from modules.m3_connect.domain import findings as F
from modules.m3_connect.domain import inputs as I
from modules.m3_connect.domain import rules as R
from modules.m3_connect.domain import trial as T


def compile_demo(tmp_path, model=None, kpis=None, skip=()):
    adir = tmp_path / "a"
    demo_files(adir, skip)
    inputs, pl = demo_inputs(), plane(tmp_path)
    C.compile_all(model, Gate(), "co-test", pl, adir, inputs["measures"], T.columns_by_source(adir), lambda m: T.feeders(adir, m),
                  pack_kpis() if kpis is None else kpis, F.technical_of)
    return adir, inputs


def test_demo_answer_key_from_the_pack_hints(tmp_path):
    adir, inputs = compile_demo(tmp_path)  # no model: every rule comes from the pack's hints
    trial = T.run_trial(adir, inputs["measures"])
    for k in ("K04", "K09", "K10"):
        assert trial[k]["result"] == "matches", (k, trial[k])
    assert trial["K04"]["our_figure"] == 2610000 and trial["K10"]["our_figure"] == pytest.approx(20.86, abs=0.005)
    k12 = trial["K12"]
    assert k12["result"] == "gap" and k12["our_figure"] == pytest.approx(21.43, abs=0.005) and k12["their_figure"] == 28.57
    assert "ends on 22 Sep" in k12["likely_reason"] and "30 Sep" in k12["likely_reason"]
    k15 = trial["K15"]
    assert k15["result"] == "gap" and k15["our_figure"] == pytest.approx(0.63, abs=0.005) and k15["skipped"]["fees"] == 20
    assert "leaves out fees" in k15["likely_reason"] and k15["reasons"][0].startswith("Your figure leaves out fees")
    assert any("Fees is empty in 20 of 40 rows" in r for r in k15["reasons"])
    k16 = trial["K16"]
    assert k16["result"] == "cannot" and k16["our_figure"] is None and "index levels missing after 22 sep" in k16["missing"].lower()
    k18 = trial["K18"]
    assert k18["result"] == "cannot" and k18["our_figure"] is None and k18["their_figure"] is None  # never zero


def test_demo_findings_ready_unclear_unknown_and_risks(tmp_path):
    adir, inputs = compile_demo(tmp_path)
    T.run_trial(adir, inputs["measures"])
    f = F.build(adir, inputs, set())
    groups = {k: v["group"] for k, v in f["measures"].items()}
    assert groups == {"K04": "ready", "K09": "ready", "K10": "ready", "K12": "unclear", "K15": "unclear", "K16": "unknown", "K18": "unknown"}
    assert [p["id"] for p in f["measures"]["K12"]["pain_points"]] == ["p1"] and [x["id"] for x in f["measures"]["K15"]["levers"]] == ["l1"]
    risks = {r["id"]: r for r in f["risks"]}
    assert set(risks) == {"risk-measure-K12", "risk-measure-K15", "risk-measure-K16", "risk-measure-K18"}
    assert risks["risk-measure-K16"]["kind"] == "unknown" and risks["risk-measure-K12"]["kind"] == "risk"
    assert all(r["decision"] is None and r["text"] for r in risks.values())
    risks["risk-measure-K12"]["decision"] = {"decision": "accepted"}
    R.write_file(adir, "findings.json", {**f, "risks": list(risks.values())})
    again = F.build(adir, inputs, set())  # a rebuild keeps what a person decided
    assert next(r for r in again["risks"] if r["id"] == "risk-measure-K12")["decision"] == {"decision": "accepted"}


def test_source_level_risks_and_open_ambiguities(tmp_path):
    adir, inputs = compile_demo(tmp_path)
    T.run_trial(adir, inputs["measures"])
    marks = R.read_file(adir, "sources.json", [])
    marks[0]["blocked_upstream"] = True
    marks[1]["licence"] = True
    R.write_file(adir, "sources.json", marks)
    inputs["sources"] = [{"Source ID": {"value": m["id"], "mark": "stated"}} for m in marks]
    inputs["gaps"] = [{"kind": "personal_undecided", "kpi_id": "K18"}]
    inputs["measures"][0]["technical"] = {"calculation": "x"}
    inputs["measures"][0]["ambiguities"] = [{"id": "a1", "text": "Which notice date counts", "status": "open"}, {"id": "a2", "text": "Done", "status": "settled"},
                                            {"id": "a3", "text": "Know it", "status": "accepted"}]
    ids = {r["id"]: r for r in F.build(adir, inputs, set())["risks"]}
    assert {"risk-source-s-perf-blocked_upstream", "risk-source-s-custody-licence", "risk-personal-K18", "risk-ambiguity-K04-a1", "risk-ambiguity-K04-a3"} <= set(ids)
    assert "risk-ambiguity-K04-a2" not in ids and ids["risk-ambiguity-K04-a1"]["kind"] == "ambiguity"
    assert F.build(adir, inputs, set())["measures"]["K04"]["group"] == "unclear"  # an open ambiguity stops "ready"


def test_a_checked_rule_is_a_persons_and_recompile_keeps_it(tmp_path):
    adir, inputs = compile_demo(tmp_path)
    rules = R.read_rules(adir)
    rules["K04"].update(state="checked", checked_by="Ana Analyst")
    R.write_file(adir, "rules.json", rules)
    C.compile_all(None, Gate(), "co-test", plane(tmp_path), adir, inputs["measures"], T.columns_by_source(adir), lambda m: [], pack_kpis(), F.technical_of)
    assert R.read_rules(adir)["K04"]["checked_by"] == "Ana Analyst"


def test_rule_in_plain_words(tmp_path):
    adir, _ = compile_demo(tmp_path)
    rules = R.read_rules(adir)
    assert rules["K15"]["words"].startswith("The sum of closing value minus opening value minus net flows, less the sum of fees (net of fees)")
    assert "where status is open and notice ref was not replaced" in rules["K04"]["words"]
    assert rules["K15"]["origin"] == "pack hint"


# ---- compile with a stubbed model -----------------------------------------------------------------------------------------------------
GOOD = json.dumps({"op": "sum", "column": "Closing Value", "filters": [{"column": "asset class", "op": "in", "value": ["Private Equity"]}]})
BAD = json.dumps({"op": "sum", "column": "no_such_column"})


def test_stub_model_rule_is_resolved_to_real_columns(tmp_path):
    stub = Stub(GOOD)
    adir, _ = compile_demo(tmp_path, stub, kpis=[])
    r = R.read_rules(adir)["K10"]
    assert r["state"] == "draft" and r["origin"] == "definition" and r["rule"]["column"] == "closing_value" and r["rule"]["source"] == "s-perf"
    assert r["rule"]["filters"][0]["column"] == "asset_class" and len(stub.sent) == 7  # one call per measure, no retry


def test_invalid_rule_is_retried_once_then_good(tmp_path):
    stub = Stub(BAD, GOOD)
    pl = plane(tmp_path)
    adir = tmp_path / "a"
    demo_files(adir)
    rec = C.compile_rule(stub, Gate(), "co-test", pl, name="Private-market allocation", text="Private equity share", columns=T.columns_by_source(adir))
    assert rec["state"] == "draft" and len(stub.sent) == 2
    assert "no_such_column" in stub.payload.split("Your last rule was not usable")[1]  # the retry says what was wrong, by column name


def test_invalid_twice_falls_back_to_the_pack_hint_else_could_not_compile(tmp_path):
    adir, _ = compile_demo(tmp_path, Stub(BAD))
    assert all(R.read_rules(adir)[k]["origin"] == "pack hint" for k in ("K04", "K10"))
    adir2 = tmp_path / "b"
    demo_files(adir2)
    stub = Stub(BAD)
    rec = C.compile_rule(stub, Gate(), "co-test", plane(tmp_path), name="X", text="Something", columns=T.columns_by_source(adir2))
    assert len(stub.sent) == 2 and rec["state"] == R.COULD_NOT and "no_such_column" in rec["reason"] and rec["rule"] is None


def test_model_says_it_cannot_and_a_figure_the_guard_replaces(tmp_path):
    adir = tmp_path / "a"
    demo_files(adir)
    cols = T.columns_by_source(adir)
    rec = C.compile_rule(Stub(json.dumps({"error": "the definition does not say what is counted"})), Gate(), "co-test", plane(tmp_path), name="X", text="Odd", columns=cols)
    assert rec["state"] == R.COULD_NOT and "does not say" in rec["reason"]
    rec = C.compile_rule(Stub(json.dumps({"op": "sum", "column": "fees", "scale": 777})), Gate(), "co-test", plane(tmp_path), name="X", text="Sum fees", columns=cols)
    assert rec["state"] == R.COULD_NOT  # a number nobody gave it is replaced by the guard, so the answer is no rule


def test_no_row_value_reaches_the_model(tmp_path):
    stub = Stub(GOOD)
    adir, inputs = compile_demo(tmp_path, stub, kpis=[])
    T.run_trial(adir, inputs["measures"])
    shown = stub.payload.lower()
    values = set()
    for sid in T.source_ids(adir):
        for row in T.rows_for(adir, sid):
            values |= {str(v) for v in row.values() if v not in (None, "") and len(str(v)) >= 5}
    leaked = sorted(v for v in values if v.lower() not in " ".join(m["definition"] for m in inputs["measures"]).lower() and v.lower() in shown)
    assert stub.sent and not leaked, leaked[:5]
    for ctx in (json.loads(m[-1]["content"]) for m in stub.sent):
        assert set(ctx["context"]) == {"measure", "definition", "columns", "facts"} and all(t in ("number", "date", "text") for t in ctx["context"]["columns"].values())


def test_demo_inputs_exist():
    assert DEMO.is_dir() and I.RESTRICTED_NAME


def test_a_measure_reading_a_narrower_field_is_hidden_from_others_not_from_the_head_of_data(tmp_path):
    adir, inputs = compile_demo(tmp_path)
    inputs["fields"] = [{"Field name as in the source": {"value": "Fees", "mark": "stated"}, "Who may see it": {"value": "Pia Pay", "mark": "stated"}}]
    rules = R.read_rules(adir)
    assert T.hidden_measures(inputs, rules, I.Viewer("Ana Analyst", frozenset({"analyst"}))) == {"K15", "K16"}  # K16 reads K15's fees too
    assert T.hidden_measures(inputs, rules, I.Viewer("Pia Pay", frozenset({"analyst"}))) == set()
    assert T.hidden_measures(inputs, rules, I.Viewer("Head", frozenset({"company_admin"}))) == set()
    assert F.for_viewer(F.build(adir, inputs, set()), {"K15"})["measures"]["K15"]["name"] == I.RESTRICTED_NAME


def test_lens_rewords_a_gap_from_reasons_only_and_keeps_ours_if_it_changes_a_number(tmp_path):
    from modules.m3_connect.agent import explain as X
    pl = plane(tmp_path)
    reasons = ["The data ends on 22 Sep, but your figure is as at 30 Sep."]
    stub = Stub("Your figure runs to 30 Sep, ours only to 22 Sep.")
    assert X.reword(stub, Gate(), "co-test", pl, "Stale share", reasons).startswith("Your figure runs")
    assert json.loads(stub.sent[0][-1]["content"])["context"].keys() == {"measure", "reasons", "facts"}
    assert X.reword(Stub("It is 45 days off."), Gate(), "co-test", pl, "Stale share", reasons) is None
    assert X.reword(None, Gate(), "co-test", pl, "x", reasons) is None
