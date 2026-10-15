"""B2: Span proposes a build plan for the Evergreen investment report intent; an invented column and a DROP are refused; the proposer cannot
approve; approving the plan also approves its linked model change and registers its gold tables; a chat request becomes a pending change."""
import copy
import os

import pytest

from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import b6_plan as B
from sh_platform.v1 import b6_span as S
from sh_platform.v1 import e0a_catalogue as E
from sh_platform.v1 import e0b_mappings as M
from sh_platform.v1 import p1_project as P
from sh_platform.v1.i2_north import Refused

ENG = Viewer("Leela Raman", frozenset({"analyst"}), False, "acc-leela")
HEAD = Viewer("Ravi Head", frozenset({"analyst", "head_of_data"}), False, "acc-ravi")
READER = Viewer("Priya Nair", frozenset({"sponsor"}), False, "acc-priya")
IID = "evergreen-report"


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    plane = PlaneStore(tmp_path / "data").create("evergreen")
    sow = {"state": "signed", "title": "Monthly investment report",
           "sources": [{"name": "Administrator export", "kind": "file", "holds": "valuations by month", "owner": "Mei Tan"},
                       {"name": "Trading export", "kind": "file", "holds": "trades and cash", "owner": "Arjun Mehta"},
                       {"name": "Manager statements", "kind": "document", "holds": "manager statements", "owner": "Mei Tan"}],
           "kpis": [{"code": "K1", "name": "Net worth by month", "definition": "Sum of valuations", "formula": "", "unit": "USD", "period": "monthly",
                     "owner": "Priya Nair", "sources": [], "benchmark_by": ["month"]},
                    {"code": "K2", "name": "Valuation by currency", "definition": "Valuations by currency", "formula": "", "unit": "USD", "period": "monthly",
                     "owner": "Priya Nair", "sources": [], "benchmark_by": ["month", "currency"]},
                    {"code": "K3", "name": "Customer happiness", "definition": "How pleased clients are", "formula": "", "unit": "", "period": "", "owner": "x",
                     "sources": [], "benchmark_by": []}]}
    plane.path("intents", IID).mkdir(parents=True, exist_ok=True)
    write_json_atomic(plane.path("intents", IID, "sow.json"), sow)
    prj = P.create_project(plane, IID, "Monthly investment report", "Priya Nair")
    mid = M.save_proposal(plane, {"file_name": "administrator_export_2026_09.xlsx", "sheet": "Valuations", "purpose": "valuations", "owner": "Mei Tan", "columns": [
        {"source": "Valuation date", "target_table": "valuation_observations", "target_field": "valuation_date", "transform": None},
        {"source": "Value", "target_table": "valuation_observations", "target_field": "value_amount", "transform": None},
        {"source": "Currency", "target_table": "valuation_observations", "target_field": "currency", "transform": None}]})
    M.approve(plane, mid, ENG)
    return plane, prj["id"]


def table(plan, name_part):
    return next(t for t in plan["tables"] if name_part in t["name"])


def test_plan_proposed_for_the_intent(world):
    plane, pid = world
    plan = S.propose_plan(plane, ENG, pid)
    assert plan["version"] == 1 and plan["state"] == "proposed" and plan["proposed_by"] == "Leela Raman"
    layers = {t["name"]: t["layer"] for t in plan["tables"]}
    assert layers["bronze_administrator_export_valuations"] == "bronze" and layers["valuation_observations"] == "silver"
    assert layers["bronze_manager_statements_documents"] == "bronze"
    golds = [t for t in plan["tables"] if t["layer"] == "gold"]
    assert {g["name"] for g in golds} == {"gold_monthly_investment_report_valuation_monthly",
                                          "gold_monthly_investment_report_valuation_monthly_by_currency"}
    by_cur = table(plan, "_by_currency")
    assert [c["name"] for c in by_cur["columns"]][:2] == ["month", "currency"] and by_cur["depends_on"] == ["valuation_observations"]
    assert {"from": "bronze_administrator_export_valuations", "to": "valuation_observations"} in plan["lineage"]
    assert any("Customer happiness" in n for n in plan["notes"])  # a KPI the rules cannot place is named, not guessed
    assert plan["sources"][0] == {"code": "administrator_export", "kind": "structured", "files": ["administrator_export_2026_09.xlsx"], "owner": "Mei Tan"}
    assert B.get(plane, pid)["version"] == 1 and plane.path("build", pid, "plan-v1.json").exists()


def test_source_codes_follow_the_intent_code_not_the_name(world):
    plane, pid = world
    sow = S.signed_sow(plane, P.read(plane, pid))
    sow["sources"][0]["code"] = "administrator"
    write_json_atomic(plane.path("intents", IID, "sow.json"), sow)
    plan = S.propose_plan(plane, ENG, pid)
    assert plan["sources"][0]["code"] == "administrator" and "bronze_administrator_valuations" in {t["name"] for t in plan["tables"]}


def test_invented_column_and_drop_are_refused(world):
    plane, pid = world
    plan = S.propose_plan(plane, ENG, pid)
    bad = copy.deepcopy(plan)
    table(bad, "valuation_monthly")["sql"] = table(bad, "valuation_monthly")["sql"].replace("value_amount", "invented_amount")
    with pytest.raises(Refused) as e:
        B.validate(plane, bad)
    assert "not in the data model" in e.value.message
    for sql in ("drop table valuation_observations", "delete from valuation_observations", "update valuation_observations set currency = 'x'",
                "create table gold_x_y as select 1; drop table instruments"):
        evil = copy.deepcopy(plan)
        g = table(evil, "valuation_monthly")
        g["sql"] = sql
        with pytest.raises(Refused):
            B.validate(plane, evil)
    unlisted = copy.deepcopy(plan)
    table(unlisted, "valuation_monthly")["depends_on"] = []
    with pytest.raises(Refused):
        B.validate(plane, unlisted)


def test_proposer_cannot_approve_and_approval_registers_gold(world):
    plane, pid = world
    S.propose_plan(plane, ENG, pid)
    with pytest.raises(Refused) as e:
        B.approve(plane, ENG, pid)
    assert e.value.status == 403
    with pytest.raises(Refused):
        B.approve(plane, READER, pid)
    other = Viewer("Dev Analyst", frozenset({"analyst"}), False, "acc-dev")   # V6: an analyst who is not the head of data cannot approve
    with pytest.raises(Refused) as e2:
        B.approve(plane, other, pid)
    assert e2.value.status == 403 and "head of data" in e2.value.message
    with pytest.raises(Refused):
        B.reject(plane, other, pid, "no")
    done = B.approve(plane, HEAD, pid, None, "  Keep the raw copies  shared. ")   # V6 (C2): the note stays with the approval and in the log
    assert done["state"] == "approved" and done["approved_by"] == "Ravi Head" and done["approval_note"] == "Keep the raw copies shared."
    assert any(r["note"] == "Keep the raw copies shared." for r in B.read_log(plane, pid) if r["what"].startswith("approved the build plan"))
    gold = table(done, "valuation_monthly")["name"]
    assert E.layer_of(plane, gold) == "gold" and gold in E.tables_for_project(plane, pid)["gold"]
    assert any("approved the build plan" in r["what"] for r in B.read_log(plane, pid))
    with pytest.raises(Refused):
        B.approve(plane, HEAD, pid)  # already approved


def test_approval_also_approves_the_model_change(world):
    plane, pid = world
    plan = S.propose_plan(plane, ENG, pid, model_change={"add_column": {"table": "instruments", "name": "risk_class", "type": "text"}})
    n = plan["model_changes"]
    assert E.proposal(plane, n)["state"] == "proposed" and not E.has_field(plane, "instruments", "risk_class")
    B.approve(plane, HEAD, pid)
    assert E.proposal(plane, n)["state"] == "approved" and E.has_field(plane, "instruments", "risk_class")


def test_sending_back_needs_a_reason_and_turns_the_model_change_down(world):
    plane, pid = world
    plan = S.propose_plan(plane, ENG, pid, model_change={"add_column": {"table": "instruments", "name": "risk_class", "type": "text"}})
    with pytest.raises(Refused):
        B.reject(plane, HEAD, pid, "")
    assert B.reject(plane, HEAD, pid, "Too early")["state"] == "rejected"
    assert E.proposal(plane, plan["model_changes"])["state"] == "rejected"


def test_unsigned_intent_and_wrong_seat_are_refused(world):
    plane, pid = world
    with pytest.raises(Refused):
        S.propose_plan(plane, READER, pid)
    sow = plane.path("intents", IID, "sow.json")
    from sh_platform.jsonfile import read_json_strict
    write_json_atomic(sow, {**read_json_strict(sow, dict), "state": "draft"})
    with pytest.raises(Refused) as e:
        S.propose_plan(plane, ENG, pid)
    assert "Sign the intent" in e.value.message


def test_chat_request_becomes_a_pending_change_then_a_new_version(world):
    plane, pid = world
    S.propose_plan(plane, ENG, pid)
    got = S.chat(plane, ENG, pid, "add a weekly gold table by currency")
    assert len(got["pending"]) == 1 and "valuation_weekly_by_currency" in got["pending"][0]["summary"]
    assert B.get(plane, pid)["version"] == 1  # nothing applied yet
    again = S.chat(plane, ENG, pid, "yes")
    assert again["pending"] == [] and "version 2" in again["turns"][-1]["text"]
    v2 = B.get(plane, pid)
    assert v2["version"] == 2 and v2["state"] == "proposed" and any(t["name"].endswith("weekly_by_currency") for t in v2["tables"])
    S.chat(plane, ENG, pid, "add a monthly gold table by currency")  # already in the plan: nothing to add
    assert S.conversation(plane, pid)["changes"][-1]["status"] == "accepted"
    S.chat(plane, ENG, pid, "add a quarterly gold table by currency")
    S.chat(plane, ENG, pid, "no, not this")
    assert S.conversation(plane, pid)["changes"][-1]["status"] == "rejected" and B.get(plane, pid)["version"] == 2


def test_runner_hooks(world):
    plane, pid = world
    S.propose_plan(plane, ENG, pid)
    with pytest.raises(Refused):
        B.set_state(plane, pid, "built", "runner")  # not approved yet
    B.approve(plane, HEAD, pid)
    assert B.set_state(plane, pid, "built", "runner")["state"] == "built"
    assert B.set_schedule(plane, pid, {"freq": "weekly", "day": "mon"}, "Leela Raman")["schedule"] == {"freq": "weekly", "at": "06:00", "day": "mon"}
    with pytest.raises(Refused):
        B.set_schedule(plane, pid, {"freq": "hourly"}, "x")


def test_a_share_or_a_conditional_count_is_never_a_plain_total():
    """UC5: the rules once showed SUM(market value) under 'Harborview as a % of EG-LIQUID'; such KPIs are left for Span to define."""
    from sh_platform.v1 import b6_span as S
    assert S._not_a_plain_total({"unit": "percent"}, "EG-LIQUID single-name exposure")
    assert S._not_a_plain_total({}, "Share of Cedarpoint versus the EG-B-OPS portfolio")
    assert S._not_a_plain_total({}, "Count of instruments that lack an asset class")
    assert not S._not_a_plain_total({"unit": "money"}, "Total holdings value at month end")
