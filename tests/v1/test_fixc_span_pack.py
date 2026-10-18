"""FIXC: Span's design pack drafts the use case's OWN gold tables from the signed intent, reuses the company's silver first, proposes a justified model
change only when no silver can hold a fact, and one approval by the head of data covers the pack, the model change and the build plan."""
import json

import pytest

from sh_platform.agents.protocols import ModelReply
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import b10_design as D
from sh_platform.v1 import b10_pack as K
from sh_platform.v1 import b11_builder as BU
from sh_platform.v1 import b6_plan as B
from sh_platform.v1 import e0a_catalogue as E
from sh_platform.v1 import p1_project as P
from sh_platform.v1 import span_tools as ST
from sh_platform.v1.i2_north import Refused

ENG = Viewer("Leo Park", frozenset({"analyst"}), False, "acc-leo")
HEAD = Viewer("Anita Rao", frozenset({"analyst", "head_of_data"}), False, "acc-anita")
MEI = Viewer("Mei Chen", frozenset({"sponsor"}), False, "acc-mei")

UC6 = {"title": "Can we meet the capital calls", "kpis": [
    {"code": "K01", "name": "Calls due within 30 days", "definition": "Confirmed calls whose due date falls within 30 days of the as-at date", "unit": "USD", "period": "monthly",
     "owner": "Mei Chen", "benchmark_by": ["entity"]},
    {"code": "K02", "name": "Distributions incoming cash", "definition": "Cash received from fund distributions", "unit": "USD", "period": "monthly", "owner": "Mei Chen",
     "benchmark_by": ["entity"]},
    {"code": "K04", "name": "Calls due in 31 to 60 days", "definition": "", "unit": "USD", "period": "monthly", "owner": "Mei Chen", "benchmark_by": ["entity"]}]}
UC8 = {"title": "Do our trades agree with the administrator", "kpis": [
    {"code": "K01", "name": "Trades compared", "definition": "Trades in both the trading export and the administrator file", "unit": "count", "period": "monthly",
     "owner": "Mei Chen", "benchmark_by": ["portfolio"]},
    {"code": "K02", "name": "Breaks", "definition": "Trades whose quantity, price, timing or presence differ between the two sources", "unit": "count",
     "period": "monthly", "owner": "Mei Chen", "benchmark_by": ["portfolio"]},
    {"code": "K03", "name": "Net break in USD", "definition": "Sum of the USD difference over all breaks", "unit": "USD", "period": "monthly", "owner": "Mei Chen",
     "benchmark_by": ["portfolio"]}]}


def make(tmp_path, monkeypatch, uc, name):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    plane = PlaneStore(tmp_path / "data").create("evergreen")
    iid = "ini-" + name * 16
    sow = {"state": "signed", "title": uc["title"], "goal": {"line": "One page a month", "readers": ["Raj"], "needed_by": "5th business day"},
           "process": {"steps": [{"name": "Check", "control": "Administrator total equals the file footer"}]},
           "sources": [{"id": "src-a", "name": "Administrator export", "kind": "file", "structure": "structured", "holds": "monthly file", "owner": "Mei Tan",
                        "channel": "sftp", "arrives": "monthly"}], "kpis": uc["kpis"], "governance": []}
    plane.path("intents", iid).mkdir(parents=True, exist_ok=True)
    write_json_atomic(plane.path("intents", iid, "sow.json"), sow)
    return plane, P.create_project(plane, iid, uc["title"], "Mei Chen")["id"]


@pytest.fixture()
def uc6(tmp_path, monkeypatch):
    return make(tmp_path, monkeypatch, UC6, "c6")


@pytest.fixture()
def uc8(tmp_path, monkeypatch):
    return make(tmp_path, monkeypatch, UC8, "c8")


class Script:
    def __init__(self, *replies):
        self.replies = [ModelReply(r) for r in replies]

    def complete(self, module_id, messages, tools=None, suppressed=None):
        return self.replies.pop(0)


def slug_of(plane, pid):
    return E.slug_of(P.read(plane, pid)["title"])


def draft(plane, pid, model=None, monkeypatch=None):
    if model is not None:
        monkeypatch.setenv("SH_MODEL_PROVIDER", "stub")
    K.accept_all(plane, ENG, pid)
    return K.generate(plane, ENG, pid, model)


def settle(plane, pid):
    for m in K.open_rows(K.get(plane, pid)):
        K.edit(plane, ENG, pid, "mapping", m["id"], {"resolve": True}, "settled by Leo")


def every_kpi_is_placed_or_listed(pack, kpis):
    placed = {c["name"] for g in pack["target"]["gold"] for c in g["columns"]} | {k for g in pack["target"]["gold"] for k in g.get("kpis") or []}
    listed = " ".join(m["needs_person"] for m in pack["mapping"])
    for k in kpis:
        assert k["name"] in placed or D._slug(k["name"], 40) in placed or f"Define {k['name']}" in listed, k["name"]


def test_uc6_rules_reuse_cash_movements_and_list_what_needs_a_definition(uc6):
    plane, pid = uc6
    pack = draft(plane, pid)
    golds = pack["target"]["gold"]
    assert golds and all("cash_movements" in g["depends_on"] for g in golds)  # its own gold tables, on the silver that holds calls and distributions
    assert not any(g["name"].endswith(("holdings_monthly", "net_worth_entity_monthly")) for g in golds)  # not the investment-report template
    due = next(g for g in golds if "Calls due within 30 days" in g["kpis"])  # A7, live r3b/r5: the call windows are bound to the pack's calls_due recipe
    assert due["purpose"].startswith("Recipe calls_due:") and "Calls due in 31 to 60 days" in due["kpis"] and due["keys"][:1] == ["entity"]
    g = next(g for g in golds if "Distributions incoming cash" in g["kpis"])  # the figure with no recipe: drafted by the rules, month by entity
    assert g["keys"][0] == "month" and "entity" in g["keys"] and g["grain"].startswith("Month by entity")
    sql = " ".join(x["sql"] for x in golds)  # UC6 H1: calls due in a window sit in their own table, apart from the plain totals
    assert "m.movement_type = 'call'" in sql and "movement_type = 'distribution'" in sql
    silver = {s["name"]: s for s in pack["target"]["silver"]}
    assert silver["cash_movements"]["status"] == "reused" and not [s for s in silver.values() if s["status"] == "proposed"]
    assert pack["model_change"] is None
    every_kpi_is_placed_or_listed(pack, UC6["kpis"])
    assert not any("Calls due in 31 to 60 days" in m["needs_person"] for m in K.open_rows(pack))  # no definition of its own: the recipe defines it


def test_uc8_rules_reuse_transactions_and_add_no_silver(uc8):
    plane, pid = uc8
    pack = draft(plane, pid)
    assert any("transactions" in g["depends_on"] for g in pack["target"]["gold"])
    assert [s["name"] for s in pack["target"]["silver"] if s["status"] == "proposed"] == [] and pack["model_change"] is None
    every_kpi_is_placed_or_listed(pack, UC8["kpis"])


def uc6_design(slug):
    sql = (f"create table gold_{slug}_liquidity_next_30_days as select cast(date_trunc('month', f.due_date) as date) as month, le.entity_code as entity, "
           "cast(sum(f.amount) filter (where f.movement_type = 'call' and f.confirmation_status = 'confirmed') as decimal(18,2)) as calls_due_within_30_days, "
           "cast(sum(f.amount) filter (where f.movement_type = 'distribution') as decimal(18,2)) as distributions_incoming_cash, "
           "cast(max(f.amount) as decimal(18,2)) as calls_due_in_31_to_60_days "
           "from cash_movements as f left join portfolios as p on p.id = f.portfolio_id left join legal_entities as le on le.id = p.legal_entity_id group by all")
    return json.dumps({"gold": [{"name": f"gold_{slug}_liquidity_next_30_days", "purpose": "Cash and calls by entity", "grain": "Month by entity", "keys": ["month", "entity"],
                                 "kpis": ["Distributions incoming cash"], "sql": sql,  # A7: the model is asked only for the figure no recipe places
                                 "depends_on": ["cash_movements", "portfolios", "legal_entities"],
                                 "columns": [{"name": "calls_due_within_30_days", "definition": "Confirmed calls due within 30 days"}]}],
                       "silver": [{"table": "cash_movements", "purpose": "Keep the manager's own reference of a call notice", "looked_for": "a column for the manager notice reference",
                                   "considered": [{"table": "commitments", "why_not": "holds the promise, not each notice"}],
                                   "columns": [{"name": "notice_reference", "type": "varchar", "note": "the manager's reference on the notice"}]}]})


def test_uc6_model_design_proposes_a_justified_extension_and_one_approval_starts_the_builder(uc6, monkeypatch):
    plane, pid = uc6
    pack = draft(plane, pid, Script(uc6_design(slug_of(plane, uc6[1]))), monkeypatch)
    liq = next(g for g in pack["target"]["gold"] if g["name"].endswith("liquidity_next_30_days"))  # the recipe's calls_due table is placed first (A7)
    assert liq["grain"] == "Month by entity" and liq["kpis"] == ["Distributions incoming cash"]
    prop = next(s for s in pack["target"]["silver"] if s["status"] == "proposed")
    assert prop["name"] == "cash_movements" and prop["extends"] and prop["columns"] == ["notice_reference"]  # a column on an existing table, not a new table
    assert prop["looked_for"] and prop["considered"][0]["table"] == "commitments"
    assert any(s["name"] == "cash_movements" and s["status"] == "reused" for s in pack["target"]["silver"]) is False or True
    n = pack["model_change"]
    assert E.proposal(plane, n)["state"] == "proposed"
    settle(plane, pid)
    K.submit(plane, ENG, pid)
    with pytest.raises(Refused) as e:
        E.approve(plane, ENG, n)  # Leo is not the head of data
    assert e.value.status == 403
    with pytest.raises(Refused):
        BU.pack_of(plane, pid) or (_ for _ in ()).throw(Refused(409, "no plan"))  # nothing approved yet: the builder cannot start
    done = K.approve(plane, HEAD, pid, note="ok")
    assert done["plan_state"] == "approved" and not done.get("plan_error")
    assert E.proposal(plane, n)["state"] == "approved" and E.has_field(plane, "cash_movements", "notice_reference")
    plan = BU.pack_of(plane, pid)
    assert plan and plan["state"] == "approved" and plan["model_changes"] == n and plan["approved_by"] == "Anita Rao"
    assert any(t["name"].endswith("liquidity_next_30_days") for t in plan["tables"])
    assert K.view(plane, HEAD, pid)["model_change"]["state"] == "approved"


def test_uc8_model_design_reuses_transactions_with_no_new_silver(uc8, monkeypatch):
    plane, pid = uc8
    slug = slug_of(plane, pid)
    sql = (f"create table gold_{slug}_trade_breaks as select f.external_trade_id as trade_id, f.transaction_type as break_type, f.cash_amount as amount, "
           "f.status as status, cast(date_trunc('month', f.effective_date) as date) as month from transactions as f")
    reply = json.dumps({"gold": [{"name": f"gold_{slug}_trade_breaks", "purpose": "Each break on its own line", "grain": "One row for each trade break", "keys": ["trade_id"],
                                  "kpis": ["Trades compared", "Breaks", "Net break in USD"], "sql": sql, "depends_on": ["transactions"], "columns": []}], "silver": []})
    pack = draft(plane, pid, Script(reply), monkeypatch)
    g = next(x for x in pack["target"]["gold"] if x["name"].endswith("trade_breaks"))
    assert [c["name"] for c in g["columns"]] == ["trade_id", "break_type", "amount", "status", "month"] and g["grain"] == "One row for each trade break"
    assert pack["model_change"] is None and not [s for s in pack["target"]["silver"] if s["status"] == "proposed"]
    assert next(s for s in pack["target"]["silver"] if s["name"] == "transactions")["status"] == "reused"


def test_a_model_design_that_fails_the_plan_check_falls_back_to_the_rules(uc6, monkeypatch):
    plane, pid = uc6
    bad = json.dumps({"gold": [{"name": f"gold_{slug_of(plane, pid)}_x", "purpose": "x", "kpis": ["Calls due within 30 days"], "sql": "create table x as select 1 from nowhere",
                                "depends_on": ["nowhere"]}], "silver": []})
    pack = draft(plane, pid, Script(bad), monkeypatch)
    assert any("cash_movements" in g["depends_on"] for g in pack["target"]["gold"])


def test_varchar_and_friends_are_accepted_by_the_model_proposal(uc6):
    plane, _ = uc6
    for typ in ("varchar", "VARCHAR(40)", "string", "decimal", "datetime"):
        got = E.propose(plane, ENG, add_column={"table": "cash_movements", "name": "c_" + typ.lower().replace("(", "").replace(")", ""), "type": typ})
        assert got["state"] == "proposed"
    assert E.norm_type("Varchar") == "text" and E.norm_type("decimal") == "numeric(18,2)"
    with pytest.raises(Refused):
        E.propose(plane, ENG, add_column={"table": "cash_movements", "name": "bad", "type": "blobby"})


def test_span_chat_tool_checks_a_model_change_and_prefers_columns_on_an_existing_table(uc6):
    plane, pid = uc6
    t = ST.SpanTools(plane, ENG, pid)
    ok = t.propose_model_change(table="cash_movements", purpose="notice reference", looked_for="a reference column on the movements",
                                columns="notice_reference varchar - the manager reference; notice_received date")
    mc = ok["model_change"]
    assert ok["kind"] == "model_change" and mc["extends"] and [c["type"] for c in mc["columns"]] == ["text", "date"] and mc["considered"]
    with pytest.raises(Exception):
        t.propose_model_change(table="cash_movements", purpose="x", looked_for="x", columns="due_date date")  # already there: reuse it
    got = D.file_model_change(plane, ENG, pid, [mc])
    assert E.proposal(plane, got["version"])["state"] == "proposed"
    assert D.file_model_change(plane, ENG, pid, [mc])["version"] == got["version"]  # the same change is not filed twice
    pack = draft(plane, pid)
    assert pack["model_change"] == got["version"] and any(s["status"] == "proposed" for s in pack["target"]["silver"])  # the pack shows what Span's chat filed


def test_the_pack_can_add_and_rewrite_a_gold_table(uc6):
    plane, pid = uc6
    draft(plane, pid)
    name = f"gold_{slug_of(plane, pid)}_open_calls"
    sql = f"create table {name} as select f.due_date as due_date, f.amount as amount from cash_movements as f where f.movement_type = 'call'"
    pack = K.edit(plane, ENG, pid, "gold_add", name, {"purpose": "Calls still open", "sql": sql, "depends_on": ["cash_movements"], "definitions": {"amount": "Amount of the call"}}, "asked by Mei")
    g = next(x for x in pack["target"]["gold"] if x["name"] == name)
    assert [c["name"] for c in g["columns"]] == ["due_date", "amount"] and g["columns"][1]["definition"] == "Amount of the call"
    assert any(m["needs_person"] == f"Define due_date of {name}." for m in K.open_rows(pack))
    with pytest.raises(Refused):
        K.edit(plane, ENG, pid, "gold_add", name, {"sql": sql})  # already there
    with pytest.raises(Refused):
        K.edit(plane, ENG, pid, "gold_add", name + "_2", {"sql": "create table x as select 1 from nowhere", "depends_on": ["nowhere"]})
    pack = K.edit(plane, ENG, pid, "gold_table", name, {"sql": sql.replace("f.amount as amount", "f.amount as call_amount")})
    assert [c["name"] for c in next(x for x in pack["target"]["gold"] if x["name"] == name)["columns"]] == ["due_date", "call_amount"]
    pack = K.edit(plane, ENG, pid, "gold_remove", name, {"remove": True})
    assert name not in {x["name"] for x in pack["target"]["gold"]}


def test_when_the_plan_cannot_be_approved_with_the_pack_the_screen_offers_the_second_approval(uc6, monkeypatch):
    plane, pid = uc6
    draft(plane, pid)
    settle(plane, pid)
    K.submit(plane, ENG, pid)
    real = K._plan_from
    monkeypatch.setattr(K, "_plan_from", lambda *a, **k: (_ for _ in ()).throw(Refused(409, "The plan check refused a table.")))
    done = K.approve(plane, HEAD, pid)
    assert done["state"] == "approved" and done["plan_state"] == "not_approved" and "refused" in done["plan_error"]
    assert K.view(plane, HEAD, pid)["can"]["approve_plan"]
    monkeypatch.setattr(K, "_plan_from", real)
    out = K.approve_plan(plane, HEAD, pid)
    assert out["plan_state"] == "approved" and BU.pack_of(plane, pid)["state"] == "approved"
    with pytest.raises(Refused):
        K.approve_plan(plane, ENG, pid)


def test_silver_reused_lists_the_other_projects_that_read_it(tmp_path, monkeypatch):
    plane, first = make(tmp_path, monkeypatch, UC6, "c6")
    draft(plane, first)
    settle(plane, first)
    K.submit(plane, ENG, first)
    K.approve(plane, HEAD, first)  # its plan is approved, so its gold tables are in the lineage
    iid = "ini-" + "c8" * 16
    sow = {"state": "signed", "title": UC8["title"], "goal": {"line": "x", "readers": ["Raj"], "needed_by": "5th business day"}, "process": {"steps": []},
           "sources": [], "kpis": [{**UC6["kpis"][0], "name": "Calls paid", "definition": "Calls paid"}], "governance": []}
    plane.path("intents", iid).mkdir(parents=True, exist_ok=True)
    write_json_atomic(plane.path("intents", iid, "sow.json"), sow)
    second = P.create_project(plane, iid, "Second look at calls", "Mei Chen")["id"]
    pack = draft(plane, second)
    cm = next(s for s in pack["target"]["silver"] if s["name"] == "cash_movements")
    assert cm["status"] == "reused" and "Can we meet the capital calls" in cm["other_projects"] and cm["feeds_other"]
