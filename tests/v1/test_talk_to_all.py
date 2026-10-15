"""Everyone can talk to every agent (Span, Lumen); acting stays with the role that owns the action. Also: every /api/v1 route has a permission line."""
import json
import uuid

import pytest

from sh_platform.auth import all_routes
from sh_platform.agents.protocols import ModelReply, ToolCall
from sh_platform.app import create_app
from sh_platform.auth.permissions import load_permissions
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.settings import Settings
from sh_platform.v1 import b6_plan as B
from sh_platform.v1 import b6_span as S
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import cx_lumen as L
from sh_platform.v1 import e0a_catalogue as cat
from sh_platform.v1 import e0b_mappings as M
from sh_platform.v1 import p1_project as P
from sh_platform.v1 import talk as T
from sh_platform.v1 import wh

ENG = Viewer("Leela Raman", frozenset({"analyst"}), False, "acc-leela")
SOFIA = Viewer("Sofia Reyes", frozenset({"participant"}), False, "acc-sofia")
IID = "evergreen-report"
ALL = {"company_admin", "sponsor", "analyst", "owner", "approver", "participant"}


@pytest.fixture()
def world(tmp_path, monkeypatch):
    wh.reset_cache()
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    plane = PlaneStore(tmp_path / "data").create("evergreen")
    sow = {"state": "signed", "title": "Monthly investment report",
           "sources": [{"name": "Administrator export", "kind": "file", "holds": "valuations by month", "owner": "Mei Tan"}],
           "kpis": [{"code": "K1", "name": "Net worth by month", "definition": "Sum of valuations", "formula": "", "unit": "USD", "period": "monthly",
                     "owner": "Priya Nair", "sources": [], "benchmark_by": ["month"]}]}
    plane.path("intents", IID).mkdir(parents=True, exist_ok=True)
    write_json_atomic(plane.path("intents", IID, "sow.json"), sow)
    pid = P.create_project(plane, IID, "Monthly investment report", "Priya Nair")["id"]
    mid = M.save_proposal(plane, {"file_name": "administrator_export_2026_09.xlsx", "sheet": "Valuations", "purpose": "valuations", "owner": "Mei Tan", "columns": [
        {"source": "Valuation date", "target_table": "valuation_observations", "target_field": "valuation_date", "transform": None},
        {"source": "Value", "target_table": "valuation_observations", "target_field": "value_amount", "transform": None},
        {"source": "Currency", "target_table": "valuation_observations", "target_field": "currency", "transform": None}]})
    M.approve(plane, mid, ENG)
    S.propose_plan(plane, ENG, pid)
    return plane, pid


def test_participant_talks_to_span_and_gets_the_data_model(world):
    plane, pid = world
    got = S.chat(plane, SOFIA, pid, "Can you please tell me the current data model of performance reporting?")
    reply = got["turns"][-1]["text"]
    assert "silver" in reply and "bronze" in reply and "gold" in reply and got["pending"] == []
    assert "Columns:" in S.chat(plane, SOFIA, pid, "what columns does valuation_observations have?")["turns"][-1]["text"]


def test_participant_change_request_waits_for_the_data_team(world):
    plane, pid = world
    got = S.chat(plane, SOFIA, pid, "add a weekly gold table by currency")
    assert len(got["pending"]) == 1 and got["pending"][0]["suggestion"] is True and "head of data will see" in got["turns"][-1]["text"]
    got = S.chat(plane, SOFIA, pid, "yes")  # her own yes does not accept
    assert len(got["pending"]) == 1 and B.get(plane, pid)["version"] == 1
    with pytest.raises(Exception) as e:
        S.accept_change(plane, SOFIA, pid, got["pending"][0]["id"])
    assert getattr(e.value, "status", 403) == 403
    with pytest.raises(Exception):
        B.approve(plane, SOFIA, pid, None)
    done = S.chat(plane, ENG, pid, "yes")  # the data team accepts
    assert done["pending"] == [] and B.get(plane, pid)["version"] == 2


def test_span_without_a_plan_still_answers(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    plane = PlaneStore(tmp_path / "data").create("empty")
    pid = P.create_project(plane, "int-x", "Quiet project", "Priya Nair")["id"]
    assert "no build plan yet" in S.chat(plane, SOFIA, pid, "what is the data model?")["turns"][-1]["text"]


@pytest.fixture()
def dash(tmp_path, monkeypatch):
    wh.reset_cache()
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    plane = PlaneStore(tmp_path / "data").create("acme")
    pid = P.create_project(plane, "int-1", "Monthly report", "Nitin")["id"]
    admin = Viewer(name="Nitin", roles=frozenset({"company_admin"}), account_id="acc-admin")
    uid = str(uuid.uuid4())
    with wh.connect(plane) as con:
        con.execute("create table gold_monthly_report_holdings (month date, entity varchar, net_worth decimal(18,2))")
        con.execute("insert into gold_monthly_report_holdings values ('2026-08-31','Fund A',100),('2026-09-30','Fund A',130)")
    cat.register_gold(plane, pid, "monthly_report", "holdings", [{"name": "month", "type": "date"}])
    with wh.connect(plane) as con:
        org = con.execute("select organization_id from users limit 1").fetchone()
        org = org[0] if org else str(uuid.uuid4())
        con.execute("insert into users (id, organization_id, external_identity_id, display_name, email, is_active, created_at) values (?,?,?,?,?,true,?)",
                    [uid, org, "acc-sofia", "Sofia Reyes", "s@x.test", wh.now()])
        gid, ent = str(uuid.uuid4()), str(uuid.uuid4())
        con.execute("insert into access_groups (id, organization_id, group_name) values (?,?,?)", [gid, org, "GS"])
        con.execute("insert into access_group_memberships (id, organization_id, access_group_id, user_id, granted_at) values (?,?,?,?,?)", [str(uuid.uuid4()), org, gid, uid, wh.now()])
        con.execute("insert into access_group_scopes (id, organization_id, access_group_id, scope_type, scope_value, access_level) values (?,?,?,?,?,'read')", [str(uuid.uuid4()), org, gid, "legal_entity", ent])
    d = D.create(plane, admin, pid, "Board")
    D.set_audience(plane, admin, pid, d["id"], [uid])
    return plane, pid, d["id"], admin


def test_participant_asks_lumen_a_question_and_a_tile(dash):
    plane, pid, did, admin = dash
    q = L.ask(plane, SOFIA, pid, did, "Can you please tell me the current data model of performance reporting?")
    assert q["proposals"] == [] and "gold_monthly_report_holdings" in q["reply"] and "Span" in q["reply"] and "130" not in q["reply"]
    assert "could not match" not in L.ask(plane, SOFIA, pid, did, "how many reports are there?")["reply"]
    t = L.ask(plane, SOFIA, pid, did, "net worth by entity per month")
    own = t["dashboard_id"]
    assert t["proposals"] and own != did  # made on her own dashboard, not the admin's
    assert D.get(plane, SOFIA, pid, own)["created_by"] == D.who(SOFIA) and D.get(plane, admin, pid, did)["tiles"] == []
    with pytest.raises(Exception) as e:  # she cannot decide tiles on a dashboard that is not hers
        D.decide(plane, SOFIA, pid, did, t["proposals"][0]["id"], True)
    assert e.value.status in (403, 404)


def test_company_wide_talk_and_a_locked_project(world):
    plane, pid = world
    assert "core model" in T.span_company(plane, SOFIA, "what tables do we have?")
    told = T.lumen_company(plane, SOFIA, "how many dashboards?")
    assert "1 more project you cannot open" in told and "Monthly investment report" not in told  # AQF10-04: a locked project is not named
    P._update(plane, pid, lambda r: r.update(sensitivity="restricted", team=[{"name": "Priya Nair", "role": "owner"}]))
    out = T.span_company(plane, SOFIA, "tell me about Monthly investment report", pid)
    assert "Restricted" in out and "administrator" in out


# ---- routes ------------------------------------------------------------------------------------------------------------

def test_route_lines_open_talk_but_not_action():
    perms = load_permissions()
    talk = ["POST /api/v1/build/p/{pid}/chat", "POST /api/v1/build/chat", "POST /api/v1/consume/chat", "POST /api/v1/consume/p/{pid}/dashboards",
            "POST /api/v1/consume/p/{pid}/dashboards/{did}/ask", "POST /api/v1/consume/brief/{iid}/chat", "POST /api/v1/build/{iid}/blueprint/chat"]
    for k in talk:
        assert perms.routes[k].roles == ALL, k
    for k in ("POST /api/v1/build/p/{pid}/plan/approve", "POST /api/v1/build/p/{pid}/plan/changes/{cid}/accept", "POST /api/v1/build/p/{pid}/run",
              "POST /api/v1/consume/p/{pid}/dashboards/{did}/tiles/{tid}/accept", "PUT /api/v1/consume/p/{pid}/dashboards/{did}/audience"):
        assert perms.routes[k].roles != ALL, k


def test_every_v1_route_has_a_permission_line(tmp_path):
    app = create_app(Settings(mode="dev", data_root=str(tmp_path / "data"), session_secret="fake-test-secret-not-real"))
    perms = load_permissions()
    missing = []
    for r in all_routes(app):  # FastAPI 0.142 wraps included routers
        path = getattr(r, "path", "")
        if path.startswith("/api/v1/"):
            for m in getattr(r, "methods", None) or ():
                if m not in ("HEAD", "OPTIONS") and perms.rule_for(m, path) is None:
                    missing.append(f"{m} {path}")
    assert not missing, missing


# ---- TB1: the conversation runs the agent's real tool loop ---------------------------------------------------------------------

class Script:
    def __init__(self, *replies):
        self.replies, self.seen, self.attempts = list(replies), [], []

    def complete(self, module_id, messages, tools=None, suppressed=None):
        self.seen.append(json.dumps(messages))
        return self.replies.pop(0)


def test_span_company_chat_runs_the_loop_with_tools_and_keeps_the_talk(world):
    plane, _ = world
    model = Script(ModelReply("", [ToolCall("list_tables", {"layer": "all", "starts_with": "valuation"})]),
                   ModelReply("", [ToolCall("describe_table", {"table": "valuation_observations"})]),
                   ModelReply("The model has groups of tables. Ask about a table for detail.", []),
                   ModelReply("", [ToolCall("describe_table", {"table": "valuation_observations"})]),  # a data follow-up calls a tool too (A2)
                   ModelReply("It holds valuations.", []))
    got = T.ask(plane, SOFIA, "span", "what is the data model?", None, model)
    assert got["reply"].startswith("The model has groups") and not got["rules_only"]
    assert "valuation_observations" in model.seen[1] and "valuation_date" in model.seen[2]  # the model was shown both tool results
    again = T.ask(plane, SOFIA, "span", "and the valuations?", None, model)  # a follow-up: the first turn is in the conversation
    assert again["reply"] == "It holds valuations."
    from sh_platform.v1 import mem_agent as MEM
    turns = MEM.convo(plane, SOFIA, "span", T.CONVO)["turns"]
    assert [t["by"] for t in turns] == ["person", "span", "person", "span"]


def test_rules_reply_is_short_and_labelled_when_the_model_is_off(world):
    plane, _ = world
    got = T.ask(plane, SOFIA, "span", "what is the data model?")
    assert got["rules_only"] and got["reply"].startswith("Rules-only reply:") and "Ask about a table" in got["reply"]
    assert len(got["reply"]) < 600
    lum = T.ask(plane, SOFIA, "lumen", "what dashboards are there?")
    assert lum["reply"].startswith("Rules-only reply:")


def test_a_locked_project_gets_the_lock_words_not_the_loop(world):
    plane, pid = world
    P._update(plane, pid, lambda r: r.update(sensitivity="restricted", team=[{"name": "Priya Nair", "role": "owner"}]))
    boom = Script()  # any model call would raise
    got = T.ask(plane, SOFIA, "span", "tell me about Monthly investment report", pid, boom)
    assert "Restricted" in got["reply"] and not got["rules_only"] and boom.seen == []


def test_change_ask_is_refused_not_described():  # UC10-08
    from sh_platform.v1.talk import CHANGE_ASK
    assert CHANGE_ASK.match("Drop the holdings table") and CHANGE_ASK.match("please rename x")
    assert not CHANGE_ASK.match("What is the holdings table?") and not CHANGE_ASK.match("how does a dropdown work")
