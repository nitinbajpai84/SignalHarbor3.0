"""W2-H: the offline replay stubs (tests/evals/replay.py) and the runner's offline mode, Ctrl-C summary and loop fallback.
Every recorded shape is played through the product's real gateway and provider adapters; no network, no key."""
import json
import sys
from pathlib import Path

import duckdb
import pytest
import sqlglot

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "tools"))

import replay as R  # noqa: E402
from sh_platform.egress.errors import EgressBlocked  # noqa: E402
from sh_platform.egress.gateway import MODEL_TRIES  # noqa: E402
from sh_platform.egress.providers import build_model_client  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402

TOOLS = [{"name": n, "description": "", "parameters": {}} for n in ("propose_intent_section", "dry_run_sql", "propose_plan_change")]
ASK = [{"role": "system", "content": "be brief"}, {"role": "user", "content": "go"}]


@pytest.fixture
def plane(tmp_path):
    return PlaneStore(tmp_path / "data").create("acme-co")


def model(plane, env, provider="openrouter"):
    return build_model_client(plane, {**env, "SH_MODEL_PROVIDER": provider}, "specialist")


def log(plane) -> str:
    return (plane.area("context") / "egress_log.jsonl").read_text(encoding="utf-8")


@pytest.mark.parametrize("provider", ["openrouter", "gemini"])
def test_no_credit_is_a_402_the_gateway_names_no_credit(plane, provider):  # NU-28, AQF10-01, TAQ-S2
    env = {}
    with R.install("no_credit", env=env) as r:
        with pytest.raises(EgressBlocked) as e:
            model(plane, env, provider).complete("m", ASK, tools=TOOLS)
    assert e.value.reason_code == "no_credit" and '"no_credit"' in log(plane)
    assert len(r.seen) == 1 and r.seen[0]["provider"] == provider  # a 402 is not retried
    assert env == {}  # the dummy keys are taken away again


def test_a_dropped_connection_is_retried_then_transport_failed(plane):  # H1-01
    env = {}
    with R.install("transport_failed", env=env) as r:
        with pytest.raises(EgressBlocked) as e:
            model(plane, env).complete("m", ASK, tools=TOOLS)
    assert e.value.reason_code == "transport_failed" and len(r.seen) == MODEL_TRIES


def test_the_refused_argument_shapes_are_the_recorded_24(plane):  # NU-06: whether the product now takes them is package N's test
    env, calls = {}, []
    with R.install("refused_args_24", env=env):
        m = model(plane, env, "gemini")
        for _ in range(13):
            rep = m.complete("m", ASK, tools=TOOLS)
            if not rep.tool_calls:
                break
            calls += rep.tool_calls
    assert len(calls) == 24 and {c.name for c in calls} == {"propose_intent_section"} and "drafted" in rep.text
    # the two shapes the refusal codes name (argument_check:section / content): the intent's key as the section, content as a JSON string
    assert {(c.arguments["section"], type(c.arguments["content"]).__name__) for c in calls} == {("kpis", "dict"), ("kpi", "str")}


def test_multiline_sql_arrives_with_its_line_breaks_and_is_valid_sql(plane):  # NU-12
    env = {}
    with R.install("multiline_sql", env=env):
        rep = model(plane, env).complete("m", ASK, tools=TOOLS)
    sql = rep.tool_calls[0].arguments["sql"]
    assert rep.tool_calls[0].name == "dry_run_sql" and "\nFROM" in sql and "QUALIFY" not in sql
    sqlglot.parse_one(sql, dialect="duckdb")  # a normal select: only the line breaks are on trial


def test_qualify_sql_is_the_recorded_draft_and_duckdb_cannot_parse_it(plane):  # NU-14 (ch-eb7c061c)
    env = {}
    with R.install("qualify_sql", env=env):
        rep = model(plane, env).complete("m", ASK, tools=TOOLS)
    a = rep.tool_calls[0].arguments
    assert rep.tool_calls[0].name == "propose_plan_change" and a["name"] == "gold_exposure_by_manager_across_ent_summary"
    assert a["sql"].upper().index("QUALIFY") < a["sql"].upper().index("GROUP BY") and not a["sql"].lower().startswith("create")
    with pytest.raises(duckdb.ParserException):
        duckdb.connect().extract_statements(a["sql"])


def test_words_not_tool_claims_a_draft_with_no_call(plane):  # NU-25, H1-06
    env = {}
    with R.install("words_not_tool", env=env):
        rep = model(plane, env).complete("m", ASK, tools=TOOLS)
    assert not rep.tool_calls and "drafted" in rep.text


def test_side_calls_do_not_use_up_the_loop_script_but_failures_hit_them(plane):
    env = {}
    with R.install([{"call": "dry_run_sql", "args": {"sql": "select 1"}}, {"say": "done"}], env=env) as r:
        m = model(plane, env)
        assert json.loads(m.complete("m", ASK).text) == {"items": []}  # a memory learner's call, no tools
        assert m.complete("m", ASK, tools=TOOLS).tool_calls[0].name == "dry_run_sql"
        assert m.complete("m", ASK, tools=TOOLS).text == "done" == m.complete("m", ASK, tools=TOOLS).text  # the last step repeats
        r.load("no_credit")
        with pytest.raises(EgressBlocked):
            m.complete("m", ASK)
    assert [s["step"] for s in r.seen] == ["http"]


def test_every_shape_loads():
    assert {n: len(R.script_of(n)) for n in R.SHAPES}["refused_args_24"] == 13
    with pytest.raises(ValueError):
        R.script_of([])


# ---- the runner ----------------------------------------------------------------------------------------------------------------

import run_evals as RE  # noqa: E402


def test_the_item_loop_is_never_a_talk_summary():  # H residual 2
    new = [{"trace_id": "tr-sum", "agent": "North summary"}, {"trace_id": "tr-mem", "agent": "Memory"}, {"trace_id": "tr-n", "agent": "North"}]
    assert RE.item_loop(new, "north") == "tr-n"
    assert RE.item_loop(new[:2], "north") == "tr-mem"  # not the item's agent, but a real loop
    assert RE.item_loop(new[:1], "north") is None  # only a summary: no trace rather than the wrong one


class _Ctx:
    def client(self, role):
        raise LookupError("no admin")


def _args(tmp_path, **kw):
    return type("A", (), {"mode": "testing", "keep_mode": False, "base": "b", "replay": None, **kw})()


def test_ctrl_c_writes_the_summary_of_the_items_already_run(monkeypatch, tmp_path):  # H residual 1
    def two_then_stop(ctx, items, mode, out, rows, drafts, *a):
        rows.append({"id": "X-1", "agent": "span", "role": "analyst", "desc": "d", "status": "pass", "scores": [], "error": None})
        raise KeyboardInterrupt
    monkeypatch.setattr(RE, "run_all", two_then_stop)
    restored = []
    monkeypatch.setattr(RE, "restore_mode", lambda *a: restored.append(a) or "")
    code = RE.run_and_report(_args(tmp_path), _Ctx(), [{}, {}], tmp_path)
    js = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert code == 130 and restored and js["stopped"] is True and [r["id"] for r in js["items"]] == ["X-1"]
    assert "Stopped by Ctrl-C after 1 of 2" in (tmp_path / "REPORT.md").read_text(encoding="utf-8")


def test_offline_items_with_no_script_are_owed_to_the_live_run(tmp_path):
    rows, rp = [], R.Replay("no_credit")
    RE.run_all(None, [{"id": "L-1", "agent": "lumen", "role": "analyst", "desc": "d", "route": {}}], "testing", tmp_path, rows, [], rp, None)
    assert rows[0]["status"] == "live"
    md = RE.report_md(rows, {"mode": "testing"})
    assert "live 1" in md and "Owed to the live run" in md and "| lumen | 1 | 0 | 0 | 0 | 0 | - |" in md


def test_offline_items_name_known_shapes():
    import yaml
    for it in yaml.safe_load((HERE / "offline.yaml").read_text(encoding="utf-8")):
        R.script_of(it["replay"])  # a shape name or a step list that loads
        assert set(it["scorers"]) <= set(RE.S.SCORERS), it["id"]


def test_offline_refuses_the_real_data_root(tmp_path):
    a = _args(tmp_path, data_root=str(RE.ROOT / "data" / "x"))
    import contextlib
    with contextlib.ExitStack() as st, pytest.raises(SystemExit, match="never data"):
        RE.offline_ctx(a, st)


def _res(*steps, agent="Span"):
    return {"traces": [{"steps": [{"agent": agent, "status": "error", "elapsed_ms": 5, "steps": list(steps)}]}]}


def test_model_failure_reads_the_attempts_on_the_trace():  # TAQ-S2: the reason by name, from the trace
    S = RE.S
    r = _res({"kind": "model", "ok": False, "attempts": [{"ok": "no_credit"}, {"ok": "transport_failed"}]})
    assert S.model_failure({"expected": {"model_failure": "no_credit"}}, r)["passed"] is True
    assert S.model_failure({"expected": {"model_failure": "rate_limited"}}, r)["passed"] is False
    assert S.model_failure({"expected": {"model_failure": "no_credit"}}, _res({"kind": "model", "ok": "no_credit"}, agent="North summary"))["passed"] is False
    assert S.model_failure({"expected": {}}, {"traces": None})["passed"] is None


def test_tool_outcome_reads_refused_flags_not_words():
    S = RE.S
    r = _res({"kind": "tool", "tool": "dry_run_sql", "refused": True, "reason": "argument_check:sql"},
             {"kind": "tool", "tool": "describe_table", "refused": False})
    assert S.tool_outcome({"expected": {"tools_ok": ["describe_table"], "tools_refused": ["dry_run_sql"]}}, r)["passed"] is True
    out = S.tool_outcome({"expected": {"tools_ok": ["dry_run_sql"]}}, r)
    assert out["passed"] is False and "argument_check:sql" in out["detail"]
