"""AQ1 package S (cycle 1 fixes): egress names and vault, master data in the vault, router prices and attempts, trace helpers, the shared
agent tools and memory. Stub models only; the live proof is in docs/test-evidence/agents/cycle-1/aqf10/."""
import json

import pytest

from sh_platform.agents.loop import run_agent
from sh_platform.agents.protocols import ModelReply, ToolCall
from sh_platform.agents.registry import ToolRefused
from sh_platform.agents.runs import RunRegistry
from sh_platform.egress.names import names_in_text, protected_names
from sh_platform.egress.vault import NameVault
from sh_platform.jsonfile import read_json_strict, write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import agent_tools as AT
from sh_platform.v1 import e0a_catalogue as cat
from sh_platform.v1 import e6_trace, mem_agent as M, mem_summary as S, p1_project as P, router, wh

ADMIN = Viewer("Grace Ong", frozenset({"company_admin"}), False, "acc-grace")
SOFIA = Viewer("Sofia Reyes", frozenset({"participant"}), False, "acc-sofia")


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    wh.reset_cache()
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    return PlaneStore(tmp_path / "data").create("evergreen")


# ---- ER-01: never a single everyday word; tokenise and the final check agree ---------------------------------------------------------

def test_case_words_passed_as_people_never_put_an_everyday_word_in_the_vault():
    got = protected_names("", ["Entity B", "September investment report", "Evergreen Growth I", "portfolio", "Daniel Foo"])
    singles = {n.casefold() for _, n in got if " " not in n}
    assert not singles & {"entity", "september", "report", "portfolio", "growth", "investment"}
    assert ("company", "Entity B") in got and ("person", "Daniel") in got and ("person", "Foo") in got


def test_the_vault_refuses_an_everyday_word_and_heals_a_poisoned_file(plane):
    v = NameVault(plane)
    with pytest.raises(ValueError):
        v.register("person", "portfolio")
    path = plane.area("context") / "name_vault.json"
    write_json_atomic(path, {"entries": {"PERSON_001": {"kind": "person", "name": "portfolio"},
                                         "PERSON_002": {"kind": "person", "name": "Daniel Foo"}}})  # left by the old Tally code
    v = NameVault(plane)
    text = "select portfolio_id, cash_by_entity from gold_investment_report_cash_daily -- the portfolio of Daniel Foo"
    out = v.tokenise(text)
    assert "portfolio_id" in out and "the portfolio of PERSON_002" in out and not v.contains_name(out)


@pytest.mark.parametrize("text", ["see DanielFoo today", "Daniel_Foo signed", "report for Daniel Foo2", "Daniel-Foo agreed",
                                  "evergreen_holdings_note mentions Evergreen Holdings", "path data/Evergreen Holdings/x"])
def test_tokenise_and_contains_name_agree_on_glued_forms(plane, text):
    v = NameVault(plane)
    for kind, name in protected_names("Evergreen Holdings", ["Daniel Foo"]):
        v.register(kind, name)
    assert not v.contains_name(v.tokenise(text)), v.tokenise(text)


# ---- ER-02 / NAV-3: master data and document names are in the vault before a call -------------------------------------------------

def test_master_data_is_registered_as_organisations_and_people(plane):
    from sh_platform.build.agents import runtime as RT
    from sh_platform.v1.e1_write import org_id
    with wh.connect(plane) as con:
        con.execute("insert into organizations (id, name, created_at) values (?, ?, now())", [org_id(plane), "Evergreen Office"])
    RT._master_seen.clear()
    assert RT.register_company_names(plane) is True
    assert RT.register_company_names(plane) is False  # once per warehouse change
    names = {e["name"] for e in NameVault(plane)._parse(NameVault(plane)._read_raw()).values()}
    assert "Evergreen Office" in names and "Evergreen" in names
    found = RT.register_document_names(plane, "Kestrel Ridge Advisors Q3 newsletter, written by Thomas Lindqvist and Priya Nair.")
    assert {"Kestrel Ridge Advisors", "Thomas Lindqvist", "Priya Nair"} <= set(found)
    out = NameVault(plane).tokenise("Thomas Lindqvist of Kestrel Ridge Advisors met Evergreen Office")
    assert "Lindqvist" not in out and "Kestrel" not in out and "Evergreen" not in out


def test_names_in_text_skips_everyday_capitalised_phrases(plane):
    assert names_in_text("The Monthly Investment Report and Net Asset Value were sent.") == []
    # live 10 Oct: a manager note "Ask Cedarpoint for the notice" put "Ask" in the vault, and "Kestrel Ridge Advisors" put "Ridge"
    from sh_platform.build.agents import runtime as RT
    RT.register_document_names(plane, "Ask Cedarpoint Ventures for the notice. Kestrel Ridge Advisors wrote.")
    names = {e["name"] for e in NameVault(plane)._parse(NameVault(plane)._read_raw()).values()}
    assert "Cedarpoint Ventures" in names and "Kestrel Ridge Advisors" in names and not {"Ask", "Ridge", "Ventures", "Advisors"} & names


# ---- RC-5 / RC-7 / EVT-05: every model priced; attempts carry model, mode and the refusal ------------------------------------------

def test_every_model_of_both_modes_has_a_price_and_an_unknown_one_its_tier_default():
    for m in ("anthropic/claude-haiku-5.5", "anthropic/claude-sonnet-5.5", "anthropic/claude-opus-5.5", "openai/gpt-6-luna",
              "openai/gpt-6.1-sol", "openai/gpt-6.1-sol-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"):
        assert router.price_usd(m, 1000, 1000) is not None, m
    assert router.price_usd("vendor/new-model", 1_000_000, 0, "fast") == 1.0 and router.price_of("vendor/new-model", "fast")[1] is True
    assert router.price_usd("anthropic/claude-sonnet-5.5", 1_000_000, 1_000_000) == 12.0


def test_a_gateway_refusal_is_logged_as_an_attempt_before_it_is_raised(plane):
    from sh_platform.egress.errors import EgressBlocked

    class Refusing:
        model_id = "anthropic/claude-haiku-5.5"

        def complete(self, *a, **k):
            raise EgressBlocked("vault_name")
    rm = router.RoutedModel(type("B", (), {"route_env": {}})(), plane, "span", "", "fast", build=lambda mode, tier, alt: Refusing())
    with pytest.raises(EgressBlocked):
        rm.complete("m4_build", [{"role": "user", "content": "x"}])
    a = rm.attempts[-1]
    assert a["ok"] == "vault_name" and a["tier"] == "fast" and a["model"] == "anthropic/claude-haiku-5.5" and a["mode"] in ("testing", "real")


# ---- ER-09 / NM-7 / RC-9 / RC-10: one trace per answer, returned to the route, listed with cost ------------------------------------

def test_trace_id_reaches_the_route_and_a_memory_call_joins_the_answer(plane):
    reg_ = AT.tools_for(plane, ADMIN, "span")
    m = _Script(ModelReply("Hello.", []))
    res = run_agent(m, reg_, "evergreen", "m4_build", "Span", "s", {}, "Say hello to the team", recorder=RunRegistry(plane))
    assert e6_trace.response_trace_id() == res.trace_id and e6_trace.with_trace({"reply": "x"})["trace_id"] == res.trace_id
    with e6_trace.joined():
        side = run_agent(_Script(ModelReply('{"items": []}', [])), reg_, "evergreen", "m4_build", "Span memory", "s", {}, "remember?",
                         recorder=RunRegistry(plane))
    assert side.trace_id == res.trace_id and e6_trace.response_trace_id() == res.trace_id
    rows = e6_trace.by_trace(plane, res.trace_id)
    assert len(rows) == 2 and {r["agent_type"] for r in rows} == {"Span", "Span memory"} and all(r["kind"] == "loop" for r in rows)
    loops = e6_trace.loop_traces(plane, agent="span")
    assert len(loops) == 1 and loops[0]["runs"] == 2 and loops[0]["cost_usd"] == pytest.approx(0.002)
    assert e6_trace.loop_traces(plane, agent="lumen") == []


def test_a_rules_answer_leaves_a_trace_saying_so(plane):
    tid = e6_trace.record_rules_answer(plane, "Lumen", "model_off")
    assert e6_trace.loop_traces(plane)[0]["worded_by"] == "rules" and e6_trace.steps_for(plane, tid)[0]["steps"] == [{"kind": "rules", "reason": "model_off"}]


class _Script:
    def __init__(self, *replies):
        self.replies, self.attempts = list(replies), []

    def complete(self, module_id, messages, tools=None, suppressed=None):
        self.attempts = [{"tier": "fast", "model": "anthropic/claude-haiku-5.5", "mode": "real", "tokens_in": 10, "tokens_out": 2, "ok": "ok",
                          "cost_usd": 0.001}]
        return self.replies.pop(0)


# ---- the shared tools: tables by words, projects by title, dashboards, figures by name, memory across agents -----------------------

@pytest.fixture()
def world(plane):
    pid = P.create_project(plane, "int-1", "Monthly investment report in USD and SGD", "Grace Ong")["id"]
    cat.register_gold(plane, pid, "investment_report", "holdings_monthly", [{"name": "month", "type": "date"}])
    cat.register_gold(plane, pid, "investment_report", "cash_daily", [{"name": "day", "type": "date"}])
    return plane, pid


def call(plane, viewer, name, **a):
    return AT.tools_for(plane, viewer, "lumen").call("evergreen", "consume", name, a)


def test_list_tables_matches_words_and_never_answers_with_a_bare_empty_list(world):
    plane, _ = world
    got = call(plane, ADMIN, "list_tables", layer="gold", starts_with="monthly_investment_report")["tables"]
    assert any("gold_investment_report_holdings_monthly" in t for t in got)
    none = call(plane, ADMIN, "list_tables", layer="gold", starts_with="pension")
    assert none["tables"] == [] and "gold_investment_report_cash_daily" in none["note"]


def test_describe_table_resolves_a_plain_description(world):
    plane, _ = world
    assert call(plane, ADMIN, "describe_table", table="the monthly holdings gold table")["name"] == "gold_investment_report_holdings_monthly"
    with pytest.raises(ToolRefused) as e:
        call(plane, ADMIN, "describe_table", table="investment report gold")
    assert "several tables match" in str(e.value)


def test_whoami_names_projects_by_title_and_says_when_no_dashboard_is_shared(world):
    plane, pid = world
    out = call(plane, ADMIN, "whoami_and_access")
    assert pid not in json.dumps(out) and "Monthly investment report in USD and SGD" in json.dumps(out)
    sofia = call(plane, SOFIA, "whoami_and_access")
    assert sofia["dashboards_shared_with_you"].startswith("none")  # OB-7: never told she sees a dashboard nobody shared
    layers = call(plane, ADMIN, "describe_layers", project="Monthly investment report in USD and SGD")
    assert layers["counts"].startswith("bronze: 0 tables; silver: ") and layers["counts"].endswith("gold: 2 tables") and pid not in json.dumps(layers)
    for empty in ('""', "all", " "):  # live 10 Oct (Real use, Haiku): '""' for "every project" was refused and the answer had no counts
        assert call(plane, ADMIN, "describe_layers", project=empty)["scope"] == "every project you may see"


def test_explain_figure_source_finds_a_tile_by_its_name(world, monkeypatch):
    plane, pid = world
    d = plane.path("consume", pid, "dashboards", "dash-1.json")
    write_json_atomic(d, {"id": "dash-1", "project_id": pid, "title": "Monthly", "created_by": "acc-grace", "audience": [],
                          "tiles": [{"id": "t-net", "title": "Net worth by month", "kpi": "net worth", "sql": "select 1", "state": "accepted"}]})
    from sh_platform.v1 import a5_trail
    seen = {}
    monkeypatch.setattr(a5_trail, "trail", lambda p, v, kind, rid: seen.update(kind=kind, rid=rid) or {"kind": kind, "id": rid, "steps": []})
    call(plane, ADMIN, "explain_figure_source", kind="nav", item_id="net worth")
    assert seen == {"kind": "tile", "rid": "t-net"}


def test_recall_memory_shares_preferences_told_to_another_agent(world):
    plane, _ = world
    M.remember(plane, ADMIN, "lumen", "preference", "Prefers: blue for chart lines", key="lumen.color", value="blue")
    out = AT.tools_for(plane, ADMIN, "span").call("evergreen", "m4_build", "recall_memory", {"topic": "chart preferences"})
    assert any("blue" in p and "Lumen" in p for p in out["preferences"]) and "true" in out["note"]


# ---- memory: facts about the person, SGD, three lines, decisions only from the person ----------------------------------------------

def test_a_fact_about_the_person_is_kept_and_said_back_in_the_second_person(plane):
    shown = M.learn(plane, ADMIN, "north", "I look after the Singapore entities and sign off every report.")
    assert shown == ["You look after the Singapore entities and sign off every report"]
    assert any(i["kind"] == "fact" for i in M.mine(plane, ADMIN))


def test_lasting_answer_style_is_a_preference_and_sgd_is_caught(plane):
    assert M.learn(plane, ADMIN, "north", "From now on keep answers to three lines.") == ["you like answers of at most three lines"]
    shown = M.learn(plane, ADMIN, "lumen", "Please remember: I prefer SGD and blue lines")
    assert set(shown) == {"you like figures in SGD", "you like blue for chart lines"}  # no "lines for charts" read from "blue lines"
    assert M.remember_line(["They want x..", "You look after y."]).count("..") == 0


def test_a_model_summary_keeps_only_decisions_the_person_said(plane, monkeypatch):
    turns = [{"by": "person", "text": "We agreed the report goes out on the first Monday, SGD only.", "at": "2026-10-09T10:00:00+00:00"},
             {"by": "lumen", "text": "I proposed a Net worth per month tile.", "at": "2026-10-09T10:00:05+00:00"}]
    reply = json.dumps({"about": "monthly report", "decisions": ["Report goes out on the first Monday, SGD only",
                                                                  "Net worth per month tile was proposed and accepted", "Prefers blue lines"],
                        "open": [], "preferences": [], "topics": ["report"]})
    import sh_platform.agents.loop as loop
    monkeypatch.setattr(loop, "run_agent", lambda *a, **k: type("R", (), {"status": "done", "numbers_replaced": 0, "text": reply})())
    monkeypatch.setattr(router, "route", lambda m, *a, **k: m)
    monkeypatch.setattr(S, "model_is_off", lambda: False)
    got = S.by_model(plane, "lumen", "c1", turns, object())
    assert got["decisions"] == ["Report goes out on the first Monday, SGD only"] and "accepted" not in json.dumps(got)
    assert S.decided("We agreed: first Monday, SGD only.") and not S.decided("Did we agree on that?")


def _routed(plane, start, scripts):
    class C:
        def __init__(self, tier, script):
            self.model_id, self.script = tier, script

        def complete(self, *a, **k):
            r = self.script.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
    clients = {t: C(t, s) for t, s in scripts.items()}
    return router.RoutedModel(type("B", (), {"route_env": {}})(), plane, "north", "", start,
                              build=lambda mode, tier, alt: None if alt else clients.get(tier))


def test_an_unreachable_escalation_retries_the_first_tier_and_a_dead_manager_falls_down_once(plane):
    """AQ1 RC-6/EVT-05 (live, 10 Oct: OpenRouter out of credit): an empty first reply escalates; when the manager cannot be reached the
    first tier is asked once more instead of the person getting a rules reply; a manager-first call tries the specialist once."""
    from sh_platform.egress.errors import EgressBlocked
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}]
    rm = _routed(plane, "specialist", {"specialist": [ModelReply("", []), ModelReply("second try", [])],
                                       "manager": [EgressBlocked("transport_failed")]})
    assert rm.complete("m", msgs).text == "second try"
    assert [(a["tier"], a["step"], a["ok"]) for a in rm.attempts] == [
        ("specialist", "first", "empty"), ("manager", "retry_up", "transport_failed"), ("specialist", "retry_same", "ok")]
    rm = _routed(plane, "manager", {"manager": [EgressBlocked("transport_failed")], "specialist": [ModelReply("from specialist", [])]})
    assert rm.complete("m", msgs).text == "from specialist" and rm.attempts[-1]["step"] == "fallback_down"
    # live 10 Oct: the specialist and manager accounts out of credit, the fast model still answers
    rm = _routed(plane, "specialist", {"specialist": [EgressBlocked("no_credit")], "manager": [EgressBlocked("no_credit")],
                                       "fast": [ModelReply("from fast", [])]})
    assert rm.complete("m", msgs).text == "from fast" and [a["ok"] for a in rm.attempts] == ["no_credit", "no_credit", "ok"]
    # the same model empty twice: one try on the fast model rather than no answer
    rm = _routed(plane, "specialist", {"specialist": [ModelReply("", []), ModelReply("", [])], "manager": [EgressBlocked("no_credit")],
                                       "fast": [ModelReply("short answer", [])]})
    assert rm.complete("m", msgs).text == "short answer"


def test_a_provider_status_becomes_a_reason_code_never_its_body():
    import httpx
    from sh_platform.egress.gateway import _provider_code
    req = httpx.Request("POST", "https://x.test")
    for status, code in ((402, "no_credit"), (429, "rate_limited"), (401, "provider_key_refused"), (500, "transport_failed")):
        assert _provider_code(httpx.HTTPStatusError("x", request=req, response=httpx.Response(status, request=req))) == code
    assert _provider_code(RuntimeError("boom")) == "transport_failed"
