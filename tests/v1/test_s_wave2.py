"""W2-S shared runtime: billing message, TAQ-S1, TAQ-S2, H1-01, H1-02, H1-08, AQF10-03/-06/-07, SP-C1-03/-05, L-AQ1-05, NU-12.
Stub models only: the replay provider (tests/evals/replay.py) answers with the recorded statuses through the real gateway and adapters."""
import json
import sys
from pathlib import Path

import pytest

from sh_platform.agents.loop import run_agent
from sh_platform.agents.registry import ToolRefused, ToolRegistry
from sh_platform.agents.runs import RunRegistry
from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.names import names_in_text, protected_names
from sh_platform.egress.providers import build_model_client
from sh_platform.egress.providers.gemini import GeminiAdapter
from sh_platform.egress.vault import NameVault
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import agent_tools as AT
from sh_platform.v1 import e6_trace, mem_graph as G, router, wh

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
import replay  # noqa: E402

ADMIN = Viewer("Grace Ong", frozenset({"company_admin"}), False, "acc-grace")
SOFIA = Viewer("Sofia Reyes", frozenset({"participant"}), False, "acc-sofia")


class _Open:
    def is_enabled(self, company_id, module_id):
        return True


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    wh.reset_cache()
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    return PlaneStore(tmp_path / "data").create("evergreen")


def _log_lines(plane):
    return [json.loads(x) for x in (plane.area("context") / "egress_log.jsonl").read_text(encoding="utf-8").splitlines()]


# ---- TAQ-S2, H1-01, billing message ---------------------------------------------------------------------------------------------------

def test_402_on_the_upper_tiers_falls_down_to_a_model_that_answers(plane, two_provider_testing_mode):  # H1-01 (manager on OpenRouter, specialist and fast on Google)
    # CB1/NM1: a 402 opens that provider's breaker and ends its part of the walk, so the answer comes from the other provider's tier below
    env = {}
    with replay.install([{"http": 402}, {"say": "Two gold tables hold it."}], env=env) as r:
        base = build_model_client(plane, dict(env), "specialist")
        model = router.route(base, "span", "redraft", "", plane)  # a manager task
        reply = model.complete("m4_build", [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}],
                               [{"name": "list_tables", "description": "", "parameters": {}}])  # a chat step offers tools (not a side call)
    assert reply.text == "Two gold tables hold it."
    assert [(a["tier"], a["ok"]) for a in model.attempts] == [("manager", "no_credit"), ("specialist", "ok")]
    assert [s["provider"] for s in r.seen] == ["openrouter", "gemini"]
    # Google answered last, OpenRouter is still out of credit: the banner names only OpenRouter
    t = e6_trace.model_trouble(plane)
    assert t["code"] == "no_credit" and t["providers"] == ["OpenRouter"] and "OpenRouter" in t["words"] and "top it up" in t["words"]


def test_out_of_credit_everywhere_says_no_credit_on_the_trace_and_tells_only_the_admin(plane, two_provider_testing_mode):  # TAQ-S2, billing message
    env = {}
    with replay.install("no_credit", env=env):
        base = build_model_client(plane, dict(env), "specialist")
        with e6_trace.trace("tr-w2-bill"):
            res = run_agent(router.route(base, "span", "answer", "", plane), ToolRegistry(_Open()), plane.company_id, "m4_build", "Span",
                            "s", {}, "hello", recorder=RunRegistry(plane), fast={"off": True})
    step = next(s for s in res.trace if s["kind"] == "model")
    assert res.status == "error" and step["reason"] == "no_credit"  # was transport_failed: the router's last raise lost the code
    assert {ln["reason_code"] for ln in _log_lines(plane) if ln["decision"] == "failed"} == {"no_credit"}
    t = e6_trace.model_trouble(plane)
    assert t["providers"] == ["Google", "OpenRouter"] and t["words"].startswith("The model account is out of credit (Google / OpenRouter)")
    note = e6_trace.model_trouble_note(plane, ADMIN)
    assert note and "Google and OpenRouter" in note and "out of credit" in note
    assert e6_trace.model_trouble_note(plane, SOFIA) is None  # a participant is not told about billing


def test_the_router_names_the_most_telling_failure_and_a_404_or_400_is_named_too():  # TAQ-S2, H1-01
    import httpx
    from sh_platform.egress.gateway import _provider_code
    req = httpx.Request("POST", "https://x.test")
    assert _provider_code(httpx.HTTPStatusError("x", request=req, response=httpx.Response(404, request=req))) == "model_unknown"
    assert _provider_code(httpx.HTTPStatusError("x", request=req, response=httpx.Response(400, request=req))) == "provider_bad_request"
    m = router.RoutedModel(type("B", (), {"route_env": {}})(), None, "span", "", "specialist")
    m.attempts = [{"ok": "transport_failed"}, {"ok": "no_credit"}, {"ok": "no_key"}]
    assert m._why_none() == "no_credit"
    m.attempts = [{"ok": "no_key"}]
    assert m._why_none() == "no_credential"


def test_new_provider_codes_have_plain_words():  # AQF10-06
    for code, word in (("no_credit", "out of credit"), ("rate_limited", "too many requests"), ("provider_key_refused", "access key"),
                       ("model_unknown", "model settings")):
        assert word in EgressBlocked(code).message


def test_no_trouble_when_the_log_is_empty_or_the_latest_call_went_through(plane):
    assert e6_trace.model_trouble(plane) is None and e6_trace.model_trouble_note(plane, ADMIN) is None
    path = plane.area("context") / "egress_log.jsonl"
    rows = [{"kind": "model", "host": "openrouter.ai", "decision": "sent", "reason_code": ""},
            {"kind": "model", "host": "openrouter.ai", "decision": "failed", "reason_code": "no_credit"},
            {"kind": "model", "host": "openrouter.ai", "decision": "sent", "reason_code": ""}]  # topped up: the next call went out
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    assert e6_trace.model_trouble(plane) is None


# ---- H1-02: one turn, one trace ------------------------------------------------------------------------------------------------------

def test_the_rules_answer_after_a_failed_loop_is_on_the_loops_trace(plane):
    class Down:
        def complete(self, *a, **k):
            raise EgressBlocked("no_credit")
    with e6_trace.trace("tr-outer"):
        with e6_trace.trace("tr-inner-made-up") as inner:  # a nested turn (consume chat -> company talk) keeps the open trace
            res = run_agent(Down(), ToolRegistry(_Open()), plane.company_id, "consume", "Lumen", "s", {}, "q", recorder=RunRegistry(plane))
        tid = e6_trace.record_rules_answer(plane, "Lumen", "model_error", e6_trace.new_trace_id())  # a caller that makes up a new id
    assert inner == "tr-outer" and res.trace_id == "tr-outer" and tid == "tr-outer"
    kinds = [s["kind"] for r in e6_trace.steps_for(plane, "tr-outer") for s in r["steps"]]
    assert "model" in kinds and "rules" in kinds
    # used once: a later rules answer in the same request after an answered run is its own
    assert e6_trace.record_rules_answer(plane, "Lumen", "tile_rule", "tr-later") == "tr-later"


# ---- TAQ-S1: the vault holds full names, never an everyday word or a split organisation ---------------------------------------------------

def test_organisations_are_never_split_into_person_parts_and_imperatives_are_dropped():
    got = protected_names("", ["Evergreen Administrator", "Cedarpoint Custody", "Mei Chen"], ["Kestrel Ridge Advisors", "Sam Lee"])
    people = {n for k, n in got if k == "person"}
    assert not people & {"Ridge", "Kestrel", "Evergreen", "Cedarpoint", "Administrator", "Custody"}
    assert {"Mei Chen", "Mei", "Chen", "Sam", "Lee"} <= people and ("company", "Kestrel Ridge Advisors") in got
    assert names_in_text("Operations: Ask the administrator. Please Chase Thomas Lindqvist.") == ["Thomas Lindqvist"]


def test_the_vault_never_holds_ask_or_the_companys_own_id_word(plane):
    v = NameVault(plane)
    with pytest.raises(ValueError):
        v.register("person", "Ask")
    v.register("company", "Evergreen")  # the company's own id word: kept (the token maps back) but never matched
    assert v.tokenise("evergreen_holdings for Evergreen") == "evergreen_holdings for Evergreen"
    write_json_atomic(plane.area("context") / "name_vault.json", {"entries": {  # left by the old registration (T run 1)
        "PERSON_011": {"kind": "person", "name": "Ask"}, "PERSON_001": {"kind": "person", "name": "Evergreen"},
        "PERSON_003": {"kind": "person", "name": "Daniel Foo"}}})
    v = NameVault(plane)
    out = v.tokenise("Operations: Ask the administrator about evergreen_holdings for Daniel Foo.")
    assert "Ask the administrator" in out and "evergreen_holdings" in out and "PERSON_003" in out and not v.contains_name(out)


# ---- AQF10-03: Gemini 2.5 keeps room for the answer ------------------------------------------------------------------------------------

def test_gemini_25_thinking_is_capped_below_the_output_cap():
    _, body = GeminiAdapter().format_request("gemini-2.5-flash", [{"role": "user", "content": "q"}], None)
    cfg = body["generationConfig"]
    assert cfg["thinkingConfig"]["thinkingBudget"] <= cfg["maxOutputTokens"] // 4
    _, later = GeminiAdapter().format_request("gemini-3.1-pro-preview", [{"role": "user", "content": "q"}], None)
    assert "thinkingConfig" not in later["generationConfig"]  # later models keep their own default


# ---- NU-12: multi-line SQL ---------------------------------------------------------------------------------------------------------

def test_sql_may_span_lines_other_control_characters_are_refused():
    sql = replay.multiline_sql()
    assert "\n" in sql and AT._text({"sql": sql}, "sql", 4000) == sql.strip()
    assert AT._text({"sql": "select 1\r\n\tfrom t"}, "sql", 4000)
    for bad in ("select 1\x00", "select\x1b[2J 1", "select 1\x7f"):
        with pytest.raises(ToolRefused):
            AT._text({"sql": bad}, "sql", 4000)
    with pytest.raises(ToolRefused):
        AT._text({"table": "gold_x\nsilver_y"}, "table", 100)  # a name is still one line


# ---- L-AQ1-05: a figure the gateway would suppress never sits in a tool result -----------------------------------------------------------

def test_plain_names_a_small_or_unsized_figure_instead_of_sending_it():
    from sh_platform.egress.rows import json_findings
    trail = {"title": "Net worth by entity", "steps": {"source": {"label": "Net worth", "value": 103405000, "currency": "USD"},
                                                       "group": {"label": "Entity B", "value": 22875000, "group_size": 3},
                                                       "total": {"label": "All entities", "value": 103405000, "group_size": 12}}}
    out = AT._plain(trail)
    assert json_findings(json.dumps(out)) == (None, [])
    assert "22875000" not in json.dumps(out) and out["steps"]["source"].startswith("Net worth: the value is shown on the screen")
    assert out["steps"]["total"]["group_size"] == 12  # an aggregate of five or more still goes


# ---- AQF10-07 and H1-08: the map --------------------------------------------------------------------------------------------------

def test_the_map_shows_the_latest_summary_of_a_talk_only(plane):
    s1 = {"id": "s-1", "agent": "lumen", "convo": "dash-1", "about": "Net worth", "ctx": {}, "topics": ["net worth"], "decisions": ["use USD"],
          "open": [], "replaces": None}
    s2 = {**s1, "id": "s-2", "about": "Net worth in SGD", "decisions": ["use SGD"], "replaces": "s-1"}
    G.add_summary(plane, ADMIN, s1, [])
    G.add_summary(plane, ADMIN, s2, [])
    ids = {n["id"] for n in G.view(plane, ADMIN)["nodes"]}
    assert "summary:s-2" in ids and "summary:s-1" not in ids and "decision:s-1-0" not in ids and "decision:s-2-0" in ids
    G.drop(plane, "s-2")
    G.drop(plane, "s-1")
    assert not [n for n in G.view(plane, ADMIN)["nodes"] if n["type"] == "summary"]


def test_a_turn_that_teaches_a_preference_is_summarised_at_once(plane, monkeypatch):  # H1-08
    from sh_platform.v1 import mem_agent as MEM, mem_context as MC, mem_summary as S
    calls = []
    monkeypatch.setattr(MEM, "after_turn", lambda *a, **k: ["you prefer blue lines"])
    monkeypatch.setattr(S, "maybe", lambda *a, **k: calls.append(k.get("decision")))
    monkeypatch.setattr(S, "sweep", lambda *a, **k: [])
    MC.after_turn(plane, "lumen", ADMIN, "dash-1", "I prefer blue lines", "Noted.")
    assert calls == [True]


# ---- SP-C1-03: the guard's refusal names who can act -------------------------------------------------------------------------------

def test_a_role_refusal_names_the_roles_and_the_people_who_can_act():
    from sh_platform.auth import who_can_act

    class Accounts:
        def in_company(self, cid):
            return [{"display_name": "Anita Rao", "roles": ["analyst"], "disabled": False},
                    {"display_name": "Grace Ong", "roles": ["company_admin"], "disabled": False},
                    {"display_name": "Old Hand", "roles": ["analyst"], "disabled": True},
                    {"display_name": "Sofia Reyes", "roles": ["participant"], "disabled": False}]
    got = who_can_act(Accounts(), "evergreen", frozenset({"company_admin", "analyst"}))
    assert got == {"error": "forbidden", "message": "Only the company administrator or the data team can do this; Anita Rao or Grace Ong can."}
    assert who_can_act(Accounts(), "evergreen", frozenset({"super_admin"}))["message"] == "You do not have access to this."


# ---- SP-C1-05: a project's silver tables are the ones its plan reads ---------------------------------------------------------------------

def test_describe_layers_for_a_project_lists_the_silver_tables_its_plan_reads(plane, monkeypatch):
    from sh_platform.v1 import g1_access
    cat = {**{f"silver_{i}": {"layer": "silver", "purpose": "core", "columns": []} for i in range(42)},
           "gold_p_cash": {"layer": "gold", "purpose": "Gold table of p", "columns": [], "project_ids": ["prj-1"]}}
    t = AT.AgentTools(plane, ADMIN, "span")
    monkeypatch.setattr(t, "_catalogue", lambda: cat)
    monkeypatch.setattr(t, "flows", lambda only=None: ([("silver_3", "gold_p_cash"), ("silver_7", "gold_p_cash")], {}))
    monkeypatch.setattr(t, "_counts", lambda names: {})
    monkeypatch.setattr(t, "_projects", lambda: [{"id": "prj-1", "title": "Monthly report"}])
    monkeypatch.setattr(t, "_project", lambda v: v)
    monkeypatch.setattr(g1_access, "may_see_project", lambda *a: "full")
    out = t.describe_layers(project="prj-1")
    assert [ln.split(":")[0] for ln in out["silver"]] == ["silver_3", "silver_7"]
    assert "silver: 2 tables read by this project's plan, of 42 in the shared model" in out["counts"]
