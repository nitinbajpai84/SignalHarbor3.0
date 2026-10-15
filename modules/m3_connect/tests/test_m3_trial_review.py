"""Review round for M3-P03: bad model rules, fields and sources a viewer may not see, a small largest group."""
import json

import pytest

from modules.m3_connect.domain import engine as E
from modules.m3_connect.domain import findings as F
from modules.m3_connect.domain import inputs as I
from modules.m3_connect.domain import rules as R
from modules.m3_connect.domain import trial as T
from test_m3_trial_demo import compile_demo


@pytest.mark.parametrize("bad", [{"scale": "abc"}, {"scale": "nan"}, {"scale": 7}, {"scale": True}])
def test_a_bad_scale_is_refused_at_compile_and_never_crashes_a_run(bad):
    rule = {"op": "ratio", "numerator": {"op": "sum", "column": "fees"}, "denominator": {"op": "sum", "column": "fees"}, **bad}
    assert R.shape_problems(rule) and R.resolve(rule, {"s": {"fees": "number"}})[1]
    assert E.run({**rule, "source": "s"}, lambda s: [{"fees": "1"}])["value"] is None  # the run itself must not raise


def test_a_bad_having_is_refused_and_one_bad_rule_spares_the_other_measures(tmp_path):
    leaf = {"op": "count", "group_by": "a", "having": {"column": "d", "older_than_business_days": "x"}}
    assert R.shape_problems(leaf) and R.shape_problems({**leaf, "having": {"column": "d", "older_than_business_days": -1}})
    assert E.run({**leaf, "source": "s"}, lambda s: [{"a": "p", "d": "2026-09-22"}])["cannot"]  # caught, not raised
    adir, inputs = compile_demo(tmp_path)
    rules = R.read_rules(adir)
    rules["K12"]["rule"]["numerator"]["having"]["older_than_business_days"] = "x"
    rules["K09"]["rule"]["scale"] = "nan"
    R.write_file(adir, "rules.json", rules)
    trial = T.run_trial(adir, inputs["measures"])
    assert trial["K12"]["result"] == "cannot" and trial["K09"]["result"] == "cannot" and trial["K10"]["result"] == "matches"


def test_a_field_the_viewer_may_not_see_hides_the_measures_that_read_it(tmp_path):
    adir, inputs = compile_demo(tmp_path)
    rules = R.read_rules(adir)
    cell = lambda v: {"value": v, "mark": "stated"}  # noqa: E731
    fields = [{"Field ID": cell("F1"), "Field name as in the source": cell("Fees")}, {"Field ID": cell("F2"), "Field name as in the source": cell("Amount")}]
    full = {**inputs, "fields": fields}
    seen = {**inputs, "fields": [fields[1]]}  # module 2's guards (field class, source personal data, source list) withheld Fees from this viewer
    analyst = I.Viewer("Ana Analyst", frozenset({"analyst"}))
    assert T.hidden_measures(seen, rules, analyst, full) == {"K15", "K16"}
    assert T.hidden_measures(full, rules, analyst, full) == set()


def test_source_risks_of_a_source_the_viewer_may_not_see_are_masked(tmp_path):
    adir, inputs = compile_demo(tmp_path)
    T.run_trial(adir, inputs["measures"])
    marks = R.read_file(adir, "sources.json", [])
    marks[0]["licence"] = True  # s-perf
    R.write_file(adir, "sources.json", marks)
    inputs["sources"] = [{"Source ID": {"value": m["id"], "mark": "stated"}} for m in marks]
    data = F.build(adir, inputs, set())
    risk = next(r for r in data["risks"] if r["id"].startswith("risk-source-s-perf"))
    assert risk["source"] == "s-perf" and "Performance workbook" in risk["text"]
    masked = next(r for r in F.for_viewer(data, set(), {"s-custody"}, adir)["risks"] if r["id"] == F.opaque_id(adir, risk["id"]))
    assert masked["text"] == "A restricted source has something open." and masked["measures"] == [] and "Performance" not in json.dumps(masked)
    assert next(r for r in F.for_viewer(data, set(), {"s-perf"}, adir)["risks"] if r["id"] == risk["id"])["text"] == risk["text"]


def test_a_restricted_source_hides_the_measures_that_read_or_are_fed_by_it(tmp_path):
    adir, inputs = compile_demo(tmp_path)
    rules = R.read_rules(adir)
    src = lambda i: {"Source ID": {"value": i, "mark": "stated"}}  # noqa: E731
    full = {**inputs, "sources": [src("s-perf"), src("s-custody"), src("s-calls"), src("s-index"), src("s-expo")]}
    seen = {**inputs, "sources": [src("s-custody"), src("s-calls"), src("s-index"), src("s-expo")]}  # s-perf is not on this analyst's list
    analyst = I.Viewer("Ana Analyst", frozenset({"analyst"}))
    marks = T.source_marks(adir)
    assert T.hidden_measures(seen, rules, analyst, full, marks) == {"K10", "K15", "K16"}  # read it (K10, K15, K16 via its rule)
    assert T.hidden_measures(seen, {}, analyst, full, marks) == {"K10", "K15", "K16"}  # fed by it through sources.json, even with no rule
    assert T.hidden_measures(full, rules, analyst, full, marks) == set()
    assert T.hidden_measures(seen, rules, I.Viewer("Head", frozenset({"company_admin"})), full, marks) == {"K10", "K15", "K16"}  # A-069: outside the list like the analyst
    assert T.hidden_measures(full, rules, I.Viewer("Head", frozenset({"company_admin"})), full, marks) == set()


def test_masked_source_risk_has_an_opaque_id_and_decisions_still_match(tmp_path):
    adir, inputs = compile_demo(tmp_path)
    marks = R.read_file(adir, "sources.json", [])
    marks[0]["licence"] = True
    R.write_file(adir, "sources.json", marks)
    inputs["sources"] = [{"Source ID": {"value": m["id"], "mark": "stated"}} for m in marks]
    data = F.build(adir, inputs, set())
    real = next(r["id"] for r in data["risks"] if r["id"].startswith("risk-source-s-perf"))
    shown = F.for_viewer(data, set(), {"s-custody"}, adir)
    opaque = next(r["id"] for r in shown["risks"] if r["text"] == "A restricted source has something open.")
    assert "s-perf" not in json.dumps(shown) and opaque != real and opaque == F.opaque_id(adir, real)
    assert F.real_id(adir, data, opaque) == real and F.real_id(adir, data, real) == real


def test_the_opaque_id_cannot_be_found_by_hashing_guesses_and_is_stable(tmp_path):
    import hashlib
    adir, _ = compile_demo(tmp_path)
    real = "risk-source-s-perf-licence"
    first = F.opaque_id(adir, real)
    assert first == F.opaque_id(adir, real) and first != F.opaque_id(adir, "risk-source-s-custody-licence")
    for guess in (hashlib.sha256(real.encode()).hexdigest(), "risk-" + hashlib.sha256(real.encode()).hexdigest()[:16]):
        assert first != guess  # not a bare hash of the real id
    assert len(json.loads((adir / "trial_salt.json").read_text())["salt"]) == 32  # created once, kept
    other = tmp_path / "other"
    other.mkdir()
    assert F.opaque_id(other, real) != first  # a different assessment has a different salt


def test_a_largest_group_under_five_rows_is_not_shown_but_the_overall_figure_stays(tmp_path):
    adir, inputs = compile_demo(tmp_path)
    trial = T.run_trial(adir, inputs["measures"])
    k09 = trial["K09"]
    assert k09["result"] == "matches" and k09["our_figure"] == pytest.approx(12.92, abs=0.005) and k09["groups"] == []
    assert k09["group_note"] == "Hidden: fewer than five holdings"
    assert not trial["K10"].get("group_note")
