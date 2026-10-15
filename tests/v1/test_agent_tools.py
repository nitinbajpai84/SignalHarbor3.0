"""LOOP0: the shared read-only agent tools (strict arguments, access filtered by the signed-in person, aggregate rule, nothing written)
and the per-step trace the loop leaves for GET /api/v1/agent-runs/trace/{id}."""
import json

import pytest

from sh_platform.agents.loop import run_agent
from sh_platform.agents.protocols import ModelReply, ToolCall
from sh_platform.agents.registry import ToolRefused
from sh_platform.agents.runs import RunRegistry
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import agent_tools as AT
from sh_platform.v1 import e0a_catalogue as cat
from sh_platform.v1 import e6_trace, mem_agent as M, p1_project as P, router, wh

ADMIN = Viewer("Nitin", frozenset({"company_admin"}), False, "acc-admin")
ANA = Viewer("Ana", frozenset({"analyst"}), False, "acc-ana")
BOB = Viewer("Bob", frozenset({"participant"}), False, "acc-bob")
POLICY = "# Policy\n\nThe issuer limit is ten percent of net worth.\n"
PRIVATE = "# Private\n\nThe issuer limit secret belongs to Ana only.\n"


def item(i, name, path, **kw):
    return {"id": i, "name": name, "kind": "document", "note": "", "uploaded_by": "Seeded", "uploaded_by_id": "", "at": "", "sha256": "",
            "size": 1, "visibility": "company", "path": path, "tags": [], **kw}


@pytest.fixture()
def world(tmp_path, monkeypatch):
    wh.reset_cache()
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    plane = PlaneStore(tmp_path / "data").create("acme")
    (plane.root / "documents").mkdir(parents=True, exist_ok=True)
    (plane.root / "documents" / "policy.md").write_text(POLICY, encoding="utf-8")
    (plane.root / "documents" / "private.md").write_text(PRIVATE, encoding="utf-8")
    write_json_atomic(plane.path("library", "index.json"), [
        item("lib_1", "policy.md", "documents/policy.md"),
        item("lib_2", "private.md", "documents/private.md", visibility="private", uploaded_by_id="acc-ana")])
    open_p = P.create_project(plane, "int-1", "Open report", "Nitin")["id"]
    locked = P.create_project(plane, "int-2", "Locked report", "Nitin")["id"]
    P._update(plane, locked, lambda r: r.update(sensitivity="restricted", team=[]))
    cat.register_gold(plane, open_p, "open_report", "holdings", [{"name": "day", "type": "date"}])
    cat.register_gold(plane, locked, "locked_report", "holdings", [{"name": "day", "type": "date"}])
    return plane, open_p, locked


def reg(world, viewer, agent="lumen"):
    return AT.tools_for(world[0], viewer, agent)


def _name(line: str) -> str:
    """The table name of a list_tables line ("name: x; layer: y; purpose: z")."""
    return line.split(";")[0].removeprefix("name: ")


def call(r, name, module="consume", **a):
    return r.call("acme", module, name, a)


# ---- the registry ------------------------------------------------------------------------------------------------------------------

def test_eight_tools_all_read_only_documents_are_outside(world):
    r = reg(world, ADMIN)
    names = [t["name"] for t in r.tools_for("acme", "consume")]
    assert names == ["search_documents", "recall_memory", "get_definition", "explain_figure_source", "list_tables", "describe_layers", "describe_table",
                     "whoami_and_access"]
    assert r.is_outside("consume", "search_documents") and not r.is_outside("consume", "list_tables")
    assert not any(r.is_proposal("consume", n) for n in names)


def test_a_tool_the_agent_already_holds_is_kept(world):
    r = AT.tools_for(world[0], ADMIN, "north")
    again = AT.tools_for(world[0], ADMIN, "north", registry=r)  # no "already registered" error
    assert again is r and len(r.tools_for("acme", "m1_intent")) == 8


# ---- strict arguments --------------------------------------------------------------------------------------------------------------

BAD = [
    ("search_documents", {"query": "", "max": 3}), ("search_documents", {"query": "x" * 201, "max": 3}),
    ("search_documents", {"query": 5, "max": 3}), ("search_documents", {"query": "limit", "max": 0}),
    ("search_documents", {"query": "limit", "max": 9}), ("search_documents", {"query": "limit", "max": "many"}),
    ("search_documents", {"query": "limit", "max": 2.5}), ("search_documents", {"query": "a\x00b", "max": 2}),
    ("recall_memory", {"topic": ""}), ("recall_memory", {"topic": "y" * 201}), ("recall_memory", {"topic": ["a"]}),
    ("get_definition", {"term": "z" * 121}), ("get_definition", {"term": None}),
    ("explain_figure_source", {"kind": "salary", "item_id": "abc"}), ("explain_figure_source", {"kind": "nav", "item_id": "a b;drop"}),
    ("explain_figure_source", {"kind": "nav", "item_id": "9" * 65}),
    ("list_tables", {"layer": "platinum", "starts_with": ""}), ("list_tables", {"layer": "all", "starts_with": "q" * 41}),
    ("describe_table", {"table": ""}), ("describe_table", {"table": "t" * 101}),
]


@pytest.mark.parametrize("name,args", BAD)
def test_bad_arguments_are_refused_in_plain_words(world, name, args):
    with pytest.raises(ToolRefused) as e:
        call(reg(world, ADMIN), name, **args)
    assert str(e.value).split()[0] in args or str(e.value).startswith(("item_id", "kind"))


@pytest.mark.parametrize("name,args", [("search_documents", {"query": "limit"}), ("recall_memory", {}), ("list_tables", {"layer": "all"}),
                                       ("describe_table", {"table": "x", "extra": "y"}), ("whoami_and_access", {"x": "1"})])
def test_missing_or_extra_arguments_are_refused(world, name, args):
    with pytest.raises(ToolRefused):
        call(reg(world, ADMIN), name, **args)


def test_unknown_figure_and_table_are_refused(world):
    r = reg(world, ADMIN)
    with pytest.raises(ToolRefused):
        call(r, "describe_table", table="no_such_table")
    got = call(r, "explain_figure_source", kind="nav", item_id="not-there")  # LQ-6/NI2-01: not a dead end: where it is not, and what next
    assert got["found"] == "not on a dashboard you can open" and "never guess" in got["next"]
    with pytest.raises(ToolRefused, match="file path"):  # NA-6
        call(r, "explain_figure_source", kind="nav", item_id="../../_control/accounts")


# ---- access: a person sees only their projects and documents -------------------------------------------------------------------------

def test_search_documents_returns_only_what_the_person_may_read(world):
    seen = {}
    for who in (ANA, BOB):
        out = call(reg(world, who), "search_documents", query="issuer limit", max=5)
        seen[who.name] = json.dumps(out)
        assert out["note"] == AT.NOTE
    assert "policy.md" in seen["Ana"] and "private.md" in seen["Ana"]
    assert "policy.md" in seen["Bob"] and "private.md" not in seen["Bob"] and "secret" not in seen["Bob"]


def test_search_scope_is_the_ticked_files_when_a_conversation_is_given(world):
    plane = world[0]
    plane.path("intents", "ini-" + "a" * 32).mkdir(parents=True)
    write_json_atomic(plane.path("intents", "ini-" + "a" * 32, "context.json"), {"library_ids": ["lib_1"]})
    r = AT.tools_for(plane, ANA, "north", iid="ini-" + "a" * 32)
    out = json.dumps(call(r, "search_documents", module="m1_intent", query="issuer limit", max=5))
    assert "policy.md" in out and "private.md" not in out


def test_tables_of_a_restricted_project_are_hidden_from_people_off_it(world):
    open_t, locked_t = "gold_open_report_holdings", "gold_locked_report_holdings"
    for who, sees in ((ADMIN, True), (ANA, False), (BOB, False)):
        r = reg(world, who)
        names = {_name(t) for t in call(r, "list_tables", layer="gold", starts_with="")["tables"]}
        assert open_t in names and (locked_t in names) is sees
        if not sees:
            with pytest.raises(ToolRefused):
                call(r, "describe_table", table=locked_t)
    assert call(reg(world, ADMIN), "describe_table", table=locked_t)["columns"][0] == "name: day; type: date"


def test_whoami_lists_only_the_projects_the_person_may_see(world):
    admin = call(reg(world, ADMIN), "whoami_and_access")
    bob = call(reg(world, BOB), "whoami_and_access")
    assert admin["roles"] == ["company_admin"] and admin["centres"] == ["intent", "action", "build", "consume"]
    assert {p.split("title: ")[1].split(";")[0] for p in admin["projects"]} == {"Open report", "Locked report"}
    assert {p.split("title: ")[1].split(";")[0] for p in bob["projects"]} == {"Open report"} and bob["centres"] == ["intent", "action"]


def test_memory_is_this_persons_and_this_agents(world):
    plane = world[0]
    M.remember(plane, ANA, "lumen", "preference", "Ana likes blue charts.", key="lumen.colour", value="blue")
    M.remember(plane, ANA, "north", "fact", "Ana works on the policy review.")
    mine = json.dumps(call(reg(world, ANA), "recall_memory", topic="charts policy"))
    other = json.dumps(call(reg(world, BOB), "recall_memory", topic="charts policy"))
    assert "blue" in mine and "blue" not in other and "policy review" not in other


def test_definitions_and_catalogue_answer_in_text(world):
    assert call(reg(world, ADMIN), "get_definition", term="net worth")["found"] == []
    out = call(reg(world, ADMIN), "list_tables", layer="silver", starts_with="")
    assert out["tables"] and all("; layer: silver;" in t for t in out["tables"])
    d = call(reg(world, ADMIN), "describe_table", table=_name(out["tables"][0]))
    assert d["columns"] and d["columns"][0].startswith("name: ") and "; type: " in d["columns"][0]


# ---- the aggregate rule ------------------------------------------------------------------------------------------------------------

def test_no_result_holds_a_bare_number_or_rows(world):
    r = reg(world, ADMIN)
    results = [call(r, "whoami_and_access"), call(r, "list_tables", layer="all", starts_with=""),
               call(r, "search_documents", query="issuer", max=3), call(r, "describe_table", table="gold_open_report_holdings")]

    def walk(n):
        if isinstance(n, dict):
            assert "available" not in n and not {"rows", "records"} & {k.lower() for k in n}
            for k, v in n.items():
                assert k.endswith("id") or not isinstance(v, (int, float)) or isinstance(v, bool), (k, v)
                walk(v)
        elif isinstance(n, list):
            assert len(n) <= 50
            for x in n:
                walk(x)
    for res in results:
        walk(res)


def test_plain_turns_a_number_into_a_sentence():
    out = AT._plain({"figure": {"amount": 12000, "label": "NAV", "run_id": 7}, "steps": [{"count": "1,200"}, {"count": 3}]})
    assert out == {"figure": {"amount": "amount: 12000", "label": "NAV", "run_id": "7"}, "steps": ["count: 1,200", "count: 3"]}


# ---- the trace ---------------------------------------------------------------------------------------------------------------------

class Script:
    def __init__(self, *replies):
        self.replies, self.attempts = list(replies), []

    def complete(self, module_id, messages, tools=None, suppressed=None):
        self.attempts = [{"tier": "fast", "tokens_in": 100, "tokens_out": 20, "ok": "ok"}]
        return self.replies.pop(0)


def test_each_step_is_recorded_and_shown_on_the_trace_route(world):
    plane = world[0]
    r = reg(world, ADMIN)
    model = Script(ModelReply("", [ToolCall("list_tables", {"layer": "gold", "starts_with": ""}), ToolCall("describe_table", {"table": "x"})]),
                   ModelReply("The gold tables are open.", []))  # LQ-11: "Two gold tables" is now checked against the tool's count
    with e6_trace.trace("tr-fixed"):
        res = run_agent(model, r, "acme", "consume", "Lumen", "You help.", {"facts": []}, "which tables?", recorder=RunRegistry(plane))
    assert res.trace_id == "tr-fixed" and res.status == "done"
    kinds = [s["kind"] for s in res.trace]
    assert kinds == ["model", "tool", "tool", "model", "guard"]
    model_step, ok_tool, bad_tool = res.trace[0], res.trace[1], res.trace[2]
    assert (model_step["tier"], model_step["tokens_in"], model_step["tokens_out"], model_step["tool_calls"]) == ("fast", 100, 20, 2)
    assert ok_tool["tool"] == "list_tables" and ok_tool["arg_keys"] == ["layer", "starts_with"] and ok_tool["result_chars"] > 0 and not ok_tool["refused"]
    assert bad_tool["tool"] == "describe_table" and bad_tool["refused"] and bad_tool["reason"].startswith("argument_check")
    assert all("ms" in s for s in res.trace if s["kind"] != "guard") and res.trace[-1]["numbers_replaced"] == 0
    stored = e6_trace.steps_for(plane, "tr-fixed")
    assert len(stored) == 1 and stored[0]["steps"] == res.trace and stored[0]["run_id"] == res.run_id and stored[0]["elapsed_ms"] >= 0
    assert "x" not in json.dumps(stored[0]["steps"]).replace('"tool"', "")  # argument values are never kept, only their names


def test_a_routed_model_keeps_its_attempts_for_the_trace(world):
    plane = world[0]

    class Client:
        model_id = "m"

        def complete(self, module_id, messages, tools=None, suppressed=None):
            return ModelReply("fine", [])

    rm = router.RoutedModel(type("B", (), {"route_env": {}})(), plane, "lumen", "t", "fast", build=lambda mode, tier, alt: Client())
    rm.complete("consume", [{"role": "system", "content": "s"}, {"role": "user", "content": "{}"}])
    assert [a["tier"] for a in rm.attempts] == ["fast"] and rm.attempts[0]["ok"] == "ok"


def test_a_recorder_without_steps_and_no_recorder_still_work(world):
    r = reg(world, ADMIN)
    res = run_agent(Script(ModelReply("Hello.", [])), r, "acme", "consume", "Lumen", "s", {"facts": []}, "Say hello to the team")
    assert res.status == "done" and res.trace_id and res.trace[0]["kind"] == "model"
