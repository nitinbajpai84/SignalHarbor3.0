"""SF09: Span's model draft, sandbox repair and file for signature. Stub model only (G3); every file under tmp_path; synthetic data."""
import copy
import json
import time

import pytest

from sh_platform import warehouse as wh
from sh_platform.agents.protocols import ModelReply
from sh_platform.build import blueprint_draft as D
from sh_platform.build.agents import span_model as S
from sh_platform.build.agents.runtime import Runtime
from sh_platform.plane import CompanyPlane
from sh_platform.profile.view import Viewer

BID = "b" * 32
VALUATIONS = "fund_id,period_end,nav,manager\nF1,2026-07-31,100,Ann\nF2,2026-07-31,200,Ben\nF3,2026-08-31,50,Cat\nF1,2026-08-31,110,Dee\nF2,2026-08-31,210,Ben\n"
FUNDS = "fund_id,fund_name,manager\nF1,Alpha,Ann\nF2,Beta,Ben\nF3,Gamma,Cat\nF4,Delta,Eve\nF5,Epsilon,Fay\n"
PLAN = {"silver_model": {"dimensions": [{"name": "dim_fund", "type": "scd2", "business_key": ["fund_id"], "source": ["funds"],
                                         "tracked_attributes": ["manager"]}],
                         "facts": [{"name": "fact_valuation", "grain": ["fund_id", "period_end"], "source": ["valuations"],
                                    "foreign_keys": [{"dimension": "dim_fund", "on": "fund_id"}]}]},
        "gold_contract": {"marts": [{"name": "nav_total", "source_fact": "fact_valuation", "field": "nav", "op": "sum",
                                     "date": "period_end", "measure": "K12"}]},
        "rationale": {"entities": {"dim_fund": {"because": "managers change", "from": ["funds"]}}}}
BAD = {**PLAN, "silver_model": {**PLAN["silver_model"], "facts": [{**PLAN["silver_model"]["facts"][0], "grain": ["fund_id"]}]}}  # not unique


def _w(plane, obj, *parts):
    p = plane.path(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj), encoding="utf-8")


def _land(plane, source, name, text):
    plane.area("landing").mkdir(parents=True, exist_ok=True)
    plane.path("landing", name).write_text(text, encoding="utf-8")
    wh.load_bronze(plane, source, name)


def _blueprint(stated: str | None = None) -> dict:
    doc = {"version": 1, "state": "draft", "signed_by": [], "band": "now",
           "model": {"facts": [{"name": "fact_fund_month", "grain": "one row per fund per month", "keys": ["fund_key"], "measures": ["K12"]}],
                     "dimensions": [{"name": "dim_fund", "keys": ["fund_key"], "attributes": ["manager"], "scd": 1}]},
           "lineage": [{"measure": "K12", "source": "Valuations", "fields": ["nav"], "transform": "sum of nav", "mart": "gold.k12.nav"},
                       {"measure": "K12", "source": "Funds", "fields": ["manager"], "transform": "Not stated", "mart": "gold.k12.nav"}],
           "rules": [], "access": [{"mart": "gold.k12", "may_see": None}], "schedule": [], "infra": {"warehouse": "plane", "runner": "builtin"}}
    doc["provenance"] = D.marks(doc, "2026-10-01T00:00:00+00:00", {})
    if stated:
        doc["provenance"][stated] = {"mark": "stated", "from": "Edited in the blueprint", "by": "Aaron Lyle", "at": "2026-10-02T00:00:00+00:00"}
    return doc


@pytest.fixture
def plane(tmp_path):
    p = CompanyPlane("lakeside-family-office", tmp_path)
    _land(p, "valuations", "valuations_2026_08.csv", VALUATIONS)
    _land(p, "funds", "funds_2026_08.csv", FUNDS)
    wh.refresh_readonly_copy(p)
    _w(p, {"state": "signed", "created_at": "2026-09-01"}, "intents", "m2_baseline", BID, "baseline.json")
    _w(p, [{"id": "K12", "name": {"value": "Net asset value", "mark": "stated"},
            "technical": {"grain": {"value": "one row per fund per month", "mark": "stated"},
                          "calculation": {"value": "sum of nav over the funds", "mark": "stated"}}}],
       "intents", "m2_baseline", BID, "kpis.json")
    _w(p, _blueprint(), "build", "blueprint.json")
    return p


class Stub:
    """Answers each round from a list (the last answer repeats); records every message list it was sent."""

    def __init__(self, *answers):
        self.answers, self.sent = list(answers), []

    def complete(self, module_id, messages, tools):
        self.sent.append(copy.deepcopy(messages))
        a = self.answers[min(len(self.sent), len(self.answers)) - 1]
        if isinstance(a, Exception):
            raise a
        return ModelReply(text=a if isinstance(a, str) else json.dumps(a))


def _rt(model):
    return Runtime(model, company_id="lakeside-family-office", viewer=Viewer("Aaron Lyle", frozenset({"analyst"})))


def _bp(plane):
    return json.loads(plane.path("build", "blueprint.json").read_text(encoding="utf-8"))


def test_a_valid_model_is_filed_and_its_paths_are_guessed_by_span(plane):
    rec = S.start(plane, _rt(Stub(PLAN)), "Aaron Lyle", background=False)
    assert rec["state"] == "ready", json.dumps(rec)
    assert rec["state"] == "ready" and rec["rounds"] == 1 and rec["built"]["gold"] == ["nav_total"]
    assert all("value" not in c or c["group_size"] >= 5 for c in rec["counts"])
    assert S.latest(plane)["id"] == rec["id"]
    out = S.file(plane, rec["id"], "Aaron Lyle")
    assert out["state"] == "filed" and out["filed"]["version"] == 1
    bp = _bp(plane)
    assert [f["name"] for f in bp["model"]["facts"]] == ["fact_valuation"]
    assert bp["model"]["dimensions"][0] == {"name": "dim_fund", "keys": ["fund_id"], "attributes": ["manager"], "scd": 2}
    assert bp["lineage"] == [{"measure": "K12", "source": "Valuations", "fields": ["nav", "period_end"],
                              "transform": "sum of nav by month of period_end", "mart": "gold.k12.nav_total"},
                             {"measure": "K12", "source": "Funds", "fields": ["fund_id", "manager"],  # SF09b: the dimension keeps its source
                              "transform": "looked up on fund_id", "mart": "gold.k12.nav_total"}]
    assert bp["model"]["facts"][0]["keys"] == PLAN["silver_model"]["facts"][0]["grain"]  # SF09b: real columns, never the surrogate key
    for p, m in bp["provenance"].items():
        if p.startswith(("model", "lineage")):
            assert m["mark"] == "guessed" and m["by"] == "Span" and rec["id"] in m["from"], p
    with pytest.raises(S.DraftRefused) as e:
        S.file(plane, rec["id"], "Aaron Lyle")
    assert e.value.status == 409


def test_a_stated_path_is_unchanged_after_filing(plane):
    _w(plane, _blueprint(stated="model.dimensions.0.scd"), "build", "blueprint.json")
    rec = S.start(plane, _rt(Stub(PLAN)), "Aaron Lyle", background=False)
    out = S.file(plane, rec["id"], "Aaron Lyle")
    bp = _bp(plane)
    dims = bp["model"]["dimensions"]
    assert dims == [{"name": "dim_fund", "keys": ["fund_key"], "attributes": ["manager"], "scd": 1}]  # the stated item stays whole
    assert bp["provenance"]["model.dimensions.0.scd"]["mark"] == "stated"
    assert out["filed"]["skipped"] == ["model.dimensions: dim_fund"]


def test_a_signed_blueprint_is_kept_and_the_next_version_opens(plane):
    _w(plane, {**_blueprint(), "state": "signed", "signed_by": [{"name": "Grace Ward"}]}, "build", "blueprint.json")
    rec = S.start(plane, _rt(Stub(PLAN)), "Aaron Lyle", background=False)
    S.file(plane, rec["id"], "Aaron Lyle")
    bp, v1 = _bp(plane), json.loads(plane.path("build", "blueprint.v1.json").read_text(encoding="utf-8"))
    assert bp["version"] == 2 and bp["state"] == "draft" and v1["state"] == "signed"
    assert v1["model"]["facts"][0]["name"] == "fact_fund_month"


def test_two_failures_then_a_success_stops_at_round_three(plane):
    stub = Stub(BAD, "not json at all", PLAN)
    rec = S.start(plane, _rt(stub), "Aaron Lyle", background=False)
    assert rec["state"] == "ready" and rec["rounds"] == 3 and len(stub.sent) == 3
    second = json.loads(stub.sent[1][1]["content"])
    assert "grain fund_id is not unique" in " ".join(second["context"]["errors"])


def test_always_failing_leaves_the_draft_failed_with_scrubbed_errors_and_the_blueprint_untouched(plane):
    before = plane.path("build", "blueprint.json").read_bytes()
    rec = S.start(plane, _rt(Stub(BAD)), "Aaron Lyle", background=False)
    assert rec["state"] == "failed" and rec["rounds"] == S.MAX_ROUNDS and rec["message"] == S.MSG_FAILED
    assert rec["errors"] == ["silver fact_valuation: grain fund_id is not unique (duplicates exist)"]
    assert "F1" not in json.dumps(rec["errors"])
    assert plane.path("build", "blueprint.json").read_bytes() == before
    with pytest.raises(S.DraftRefused):
        S.file(plane, rec["id"], "Aaron Lyle")


def test_the_payload_has_no_sample_value_and_no_landed_file_name(plane):
    stub = Stub(BAD, PLAN)
    S.start(plane, _rt(stub), "Aaron Lyle", background=False)
    sent = json.dumps(stub.sent)
    for value in ("valuations_2026_08", "funds_2026_08", ".csv", "Alpha", "Gamma", "Epsilon", "2026-07-31"):
        assert value not in sent, value
    ctx = json.loads(stub.sent[0][1]["content"])["context"]
    assert "(name: nav; type: varchar)" in ctx["sources"][1]  # SF14b: a list of objects goes as text lines
    assert all(f["group_size"] >= 5 for f in ctx["facts"])
    assert ctx["measures"][0]["technical_definition"] == "sum of nav over the funds"


def test_a_figure_the_guard_replaces_makes_the_round_invalid(plane):
    stub = Stub({**PLAN, "open_questions": ["Are 4321 funds expected?"]}, PLAN)
    rec = S.start(plane, _rt(stub), "Aaron Lyle", background=False)
    assert rec["state"] == "ready" and rec["rounds"] == 2
    assert "figure" in json.loads(stub.sent[1][1]["content"])["context"]["errors"][0]


def test_no_model_or_a_failing_call_falls_back_and_says_so(plane):
    before = plane.path("build", "blueprint.json").read_bytes()
    for model in (None, Stub(RuntimeError("down"))):
        rec = S.start(plane, _rt(model), "Aaron Lyle", background=False)
        assert rec["state"] == "fallback" and rec["fallback"] is True and rec["message"] == S.MSG_FALLBACK
    assert plane.path("build", "blueprint.json").read_bytes() == before


def test_a_stale_claim_reads_as_failed(plane):
    _w(plane, {"id": "Dold", "state": "drafting", "claimed_at": time.time() - S.STALE_AFTER - 1}, "build", "span", "model_draft.json")
    assert S.latest(plane)["state"] == "failed"
    rec = S.start(plane, _rt(Stub(PLAN)), "Aaron Lyle", background=False)  # a stale claim does not block a new draft
    assert rec["state"] == "ready" and rec["id"] != "Dold"


def test_an_empty_company_has_nothing_to_draft(tmp_path):
    p = CompanyPlane("empty-co", tmp_path)
    assert S.latest(p)["message"] == S.MSG_NOTHING
    with pytest.raises(S.DraftRefused) as e:  # SF09b: a plain refusal, never a failed draft
        S.start(p, _rt(Stub(PLAN)), "Aaron Lyle", background=False)
    assert e.value.status == 409 and e.value.message == S.MSG_NOTHING and S.latest(p)["state"] == "none"


def test_no_draft_yet_with_a_signed_blueprint_says_ask_span_not_wait_for_the_baseline(plane):
    """SF18b D6: the reason is read from the records: nothing to draft from, or a draft that has not been asked for yet."""
    assert S.latest(plane) == {"state": "none", "message": S.MSG_NO_DATA}
    assert "Ask Span" in S.MSG_NO_DATA and "baseline" not in S.MSG_NO_DATA
