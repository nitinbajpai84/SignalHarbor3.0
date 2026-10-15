"""SF10: Span's suggestions to the data team. Synthetic family-office plane under tmp_path, a stub model (no live call, no server)."""
import json

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.agents.protocols import ModelReply, ToolCall
from sh_platform.build import chain as C, proposals as P
from sh_platform.build.agents import modelling, span_suggest as S
from sh_platform.build.agents.runtime import Runtime
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer

BID = "b" * 32
GRACE = Viewer("Grace Ward", frozenset({"approver"}))
ADMIN = Viewer("Janet Shaw", frozenset({"company_admin"}))
TYPE2 = "Slowly changing dimension, type 2 (add a row per change)"


def _w(plane, obj, *parts):
    p = plane.path(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj), encoding="utf-8")


def _bp(scd=1):
    return {"version": 2, "state": "signed", "signed_by": [{"name": "Grace Ward", "role": "Head of department"}],
            "model": {"facts": [{"name": "fact_fund_month", "grain": "one row per fund per month", "keys": ["fund_key"], "measures": ["K12"]}],
                      "dimensions": [{"name": "dim_fund", "keys": ["fund_key"], "attributes": ["fund_id", "fund_manager"], "scd": scd}]},
            "lineage": [{"measure": "K12", "source": "Fund register", "fields": ["manager", "nav"], "transform": "latest nav", "mart": "gold.k12.nav"}],
            "rules": [], "access": [{"mart": "gold.k12", "may_see": None}], "schedule": [], "provenance": {}}


def _plane(tmp_path, scd=1, valid_from="2026-01-01"):
    pl = PlaneStore(tmp_path / "data").create("acme")
    _w(pl, _bp(scd), "build", "blueprint.json")
    _w(pl, {"state": "signed", "created_at": "2026-09-01"}, "intents", "m2_baseline", BID, "baseline.json")
    _w(pl, {"fields": [{"Field name as in the source": {"value": "fund_manager", "mark": "stated"},
                        "Valid from": {"value": valid_from, "mark": "stated" if valid_from else "unknown"}}]},
       "intents", "m2_baseline", BID, "catalogue.json")
    pl.area("warehouse").mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(pl.path("warehouse", "company.readonly.duckdb")))
    con.execute("create schema bronze")
    # 590 funds over two loads; 12 funds change manager in the second load; nav empty on a third of the rows
    con.execute("create table bronze.fund_register as select 'F' || i fund_id, case when l = 'L2' and i < 12 then 'SECRET-MGR' else 'Manager A' end "
                "manager, case when i % 3 = 0 then null else cast(i as varchar) end nav, l _load_id, "
                "case when l = 'L1' then timestamp '2026-09-01' else timestamp '2026-09-02' end _loaded_at "
                "from range(590) t(i), (values ('L1'), ('L2')) v(l)")
    con.close()
    return pl


@pytest.fixture(autouse=True)
def no_owner(monkeypatch):
    from sh_platform.consume import cards
    monkeypatch.setattr(cards, "data_owner", lambda p, code: None)  # suggestions go to the blueprint signer


class Stub:
    """Proposes the given args on the first step, then ends with text. Keeps every payload it was sent."""

    def __init__(self, *args):
        self.args, self.sent = args, []

    def complete(self, module_id, messages, tools):
        self.sent.append(json.dumps(messages))
        if len(self.sent) == 1:
            return ModelReply(tool_calls=[ToolCall("propose", {"kind": "model_change", "args": a}) for a in self.args])
        return ModelReply(text="I filed my suggestions.")


def _sugg(target="fact_fund_month", **kw):
    return {"subject": target, "technique": "Periodic snapshot fact", "title": "Snapshot the fund month", "what": "Keep one snapshot row per fund per month.",
            "why": "590 funds are read at month end.", "evidence": {"counts": [{"label": "keys", "value": 590, "group_size": 590}], "fields": ["fund_id"]},
            "impact": {"contracts": ["fund_register"], "marts": ["gold.k12"]}, "alternatives": [{"option": "Transaction fact", "why_not": "no events"}],
            "effort": "medium", **kw}


def _rt(model=None):
    return Runtime(model, company_id="acme", company_name="Acme Family Office", viewer=ADMIN)


def test_type1_dimension_with_changing_keys_gets_type2_without_a_model(tmp_path):
    out = S.review(_plane(tmp_path), _rt())
    assert out["fallback"] is True and out["message"] == "Span could not review the model just now. Try again later."
    t2 = next(p for p in out["proposals"] if p["subject"] == "dim_fund")
    assert t2["technique"] == TYPE2 and t2["by_agent"] == "Span" and t2["to"] == "Grace Ward" and t2["state"] == "proposed"
    assert {"label": "keys changed in the newest loads", "value": 12, "group_size": 590} in t2["evidence"]["counts"]
    assert "12 of 590" in t2["why"] and t2["impact"]["contracts"] == ["fund_register"]
    assert any(p["subject"] == "gold.k12.nav" for p in out["proposals"])  # the empty nav values (a third of the rows)


@pytest.mark.parametrize("scd, valid_from", [(2, "2026-01-01"), (1, None)])
def test_no_type2_when_already_type2_or_the_catalogue_does_not_say_it_changes(tmp_path, scd, valid_from):
    out = S.review(_plane(tmp_path, scd, valid_from), _rt())
    assert not any(p["subject"] == "dim_fund" for p in out["proposals"])


def test_model_suggestion_without_all_parts_is_dropped(tmp_path):
    plane = _plane(tmp_path)
    partial = {k: v for k, v in _sugg(target="fact_a").items() if k != "alternatives"}
    no_impact = _sugg(target="fact_b", impact={})
    out = S.review(plane, _rt(Stub(partial, no_impact, _sugg(target="fact_c"))))
    subjects = [p["subject"] for p in out["proposals"]]
    assert out["fallback"] is False and "fact_c" in subjects and not {"fact_a", "fact_b"} & set(subjects)
    kept = next(p for p in out["proposals"] if p["subject"] == "fact_c")
    assert kept["technique"] and kept["alternatives"] and kept["effort"] == "medium" and kept["impact"]["marts"] == ["gold.k12"]


def test_evidence_numbers_must_trace_to_tool_facts(tmp_path):
    invented = _sugg(target="fact_x", evidence={"counts": [{"label": "funds", "value": 777, "group_size": 777}]}, why="777 funds.")
    words = _sugg(target="fact_y", why="4321 funds are read at month end.")
    out = S.review(_plane(tmp_path), _rt(Stub(invented, words, _sugg(target="fact_z"))))
    subjects = [p["subject"] for p in out["proposals"]]
    assert "fact_z" in subjects and "fact_x" not in subjects and "fact_y" not in subjects


def test_against_an_earlier_decision_it_must_name_the_fact_that_changed(tmp_path):
    plane = _plane(tmp_path)
    assert modelling.remember_decision(plane, "Chose Dimensional model (star) for fact_fund_month because one consumer reads it")
    silent = _sugg(technique="Data Vault (hubs, links, satellites)")
    assert not any(p["subject"] == "fact_fund_month" for p in S.review(plane, _rt(Stub(silent)))["proposals"])
    named = _sugg(technique="Data Vault (hubs, links, satellites)", why="Since then 12 fund keys changed another field, so history matters.",
                  evidence={"counts": [{"label": "keys changed", "value": 12, "group_size": 590}]})
    assert any(p["subject"] == "fact_fund_month" for p in S.review(plane, _rt(Stub(named)))["proposals"])
    same = _sugg(target="fact_fund_month", technique="Dimensional model (star)")
    assert S.against_decision(plane, {"subject": same["subject"], "technique": same["technique"]}) is False  # agreeing is never "against"


def test_accept_writes_a_decision_and_decline_writes_the_reason(tmp_path, monkeypatch):
    plane = _plane(tmp_path)
    filed = {p["subject"]: p["id"] for p in S.review(plane, _rt())["proposals"]}
    monkeypatch.setattr(C, "open_note", lambda pl, title, sections, people, source, by: {"id": "C-0001"}, raising=False)
    app = FastAPI()
    app.include_router(P.router)
    monkeypatch.setattr(P, "_plane", lambda r: plane)
    monkeypatch.setattr(P, "_viewer", lambda r: GRACE)
    client = TestClient(app)
    assert client.post(f"/api/company/build/proposals/{filed['dim_fund']}/accept").status_code == 200
    assert client.post(f"/api/company/build/proposals/{filed['gold.k12.nav']}/decline", json={"reason": "the custodian fills nav later"}).status_code == 200
    texts = [d["text"] for d in modelling.decisions(plane)]
    assert any(t.startswith(f"Chose {TYPE2} for dim_fund") for t in texts)
    assert any(t.startswith("Declined") and "gold.k12.nav" in t and "the custodian fills nav later" in t for t in texts)
    assert json.loads(plane.path("build", "blueprint.json").read_text())["model"]["dimensions"][0]["scd"] == 1  # never applied by Span


def test_at_most_three_per_run_and_no_duplicate_of_an_open_one(tmp_path):
    plane = _plane(tmp_path)
    many = [_sugg(target=f"fact_{c}") for c in "pqrs"]
    first = S.review(plane, _rt(Stub(*many)))["proposals"]
    assert len(first) == 3 and [p["subject"] for p in first][:2] == ["dim_fund", "gold.k12.nav"]  # deterministic findings first
    again = S.review(plane, _rt(Stub(*many[:2])))["proposals"]
    assert {p["subject"] for p in again}.isdisjoint({p["subject"] for p in first}) and len(again) == 1  # only fact_q is new


def test_no_row_value_reaches_the_model(tmp_path):
    stub = Stub(_sugg())
    S.review(_plane(tmp_path), _rt(stub))
    payload = " ".join(stub.sent)
    assert "SECRET-MGR" not in payload and "Manager A" not in payload and '"F1"' not in payload
    assert "keys_changed_last_n_loads" in payload and "dim_fund" in payload


def test_an_empty_company_gets_no_suggestions_and_no_error(tmp_path):
    plane = PlaneStore(tmp_path / "data").create("empty")
    assert S.review(plane, _rt())["proposals"] == []
    assert S.review(plane, _rt(Stub(_sugg())))["proposals"] == []  # no blueprint signer, no architect: nobody to address it to
    stub = Stub(_sugg())
    assert S.review(plane, _rt(stub)) == {"proposals": [], "fallback": False, "message": None} and stub.sent == []  # SF09b: no model call


def test_a_refused_proposal_is_echoed_as_one_line_without_its_arguments(tmp_path):
    """SF09b: a malformed propose comes back to the model as a short line (tool, reason, expected shape), never its list of objects."""
    bad = _sugg(alternatives=[{"choice": "SECRET-ALT-1", "because": "x"}, {"choice": "SECRET-ALT-2", "because": "y"}])
    stub = Stub(bad, _sugg())
    S.review(_plane(tmp_path), _rt(stub))
    second = json.loads(stub.sent[1])
    assert "SECRET-ALT" not in stub.sent[1]
    assert "Your call to propose was refused (argument_check:alternatives): alternatives must be a list of {option, why_not}." in second[-1]["content"]
    assert second[-1]["role"] == "user" and len(second[-3]["tool_calls"]) == 1  # the accepted call and its answer stay paired


def test_sink_items_in_the_store_shape_pass():
    store = {"kind": "model_change", "args": {"subject": "dim_fund", "measure": "K12", "title": "t", "cites": []}}
    assert S._from_sink(store) == {"kind": "model_change", "args": {"subject": "dim_fund", "measure": "K12", "title": "t"}}
    assert S._from_sink({"kind": "model_change", "args": {"title": "t"}}) is None
    assert S._from_sink({"kind": "incident_note", "args": {"alert_id": "a"}}) is None
    P.validate("model_change", {**S._from_sink(store)["args"], "what": "w", "why": "y", "technique": "grain statement"})  # the store's own schema accepts it
