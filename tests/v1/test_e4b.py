"""E4b: the explanation event is written with sources; the bridge is program arithmetic; no figure appears that is not in the facts;
model wording with a digit or an unknown placeholder is dropped for the rules text; the skill loads under the cap."""
import importlib
import re
import sys
import types
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import e4_investigate as E
from sh_platform.v1 import wh
from sh_platform.v1.skill_loader import load_skill

INST, EXC, DOC = wh.new_id(), wh.new_id(), wh.new_id()
FLD, V1, V2 = wh.new_id(), wh.new_id(), wh.new_id()
T = lambda d: datetime(2026, 10, d, tzinfo=timezone.utc)  # noqa: E731


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    wh.reset_cache()
    plane = PlaneStore(tmp_path / "data").create("acme")
    oid = wh.new_id()
    with wh.connect(plane) as con:
        ins = lambda t, **r: con.execute(f"insert into {t} ({','.join(r)}) values ({','.join('?' * len(r))})", list(r.values()))  # noqa: E731
        ins("instruments", id=INST, organization_id=oid, canonical_name="Evergreen Growth I", instrument_type="fund", created_at=T(1))
        ins("exceptions", id=EXC, organization_id=oid, exception_type="revision", title="Fund A revised", detected_at=T(5),
            instrument_id=INST, materiality_status="material", status="new")
        ins("exception_events", id=wh.new_id(), organization_id=oid, exception_id=EXC, event_type="opened", occurred_at=T(5))
    real = lambda n: dict(vars(importlib.import_module(f"sh_platform.v1.{n}")))  # noqa: E731 - the real module, with only the calls below stubbed
    stub = {"e4_cases": real("e4_cases") | {"get": lambda plane, eid, viewer: {"id": eid}}, "e1_asof": real("e1_asof"), "e6_trace": real("e6_trace")}
    events = []
    stub["e4_cases"]["add_event"] = lambda plane, eid, actor, et, note, agent_run_id=None, **k: events.append((et, note, agent_run_id)) or "ev-new"
    stub["e1_asof"]["chain"] = lambda plane, table, rid: VALS
    from contextlib import contextmanager

    @contextmanager
    def agent_run(plane, viewer, agent_type, model_id, pv, tp, exception_id=None, decision_intent_id=None):
        yield SimpleNamespace(id="run-1")
    stub["e6_trace"]["agent_run"] = agent_run
    for name, attrs in stub.items():
        m = types.ModuleType(f"sh_platform.v1.{name}")
        m.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, f"sh_platform.v1.{name}", m)
    return plane, events


VALS = [{"id": V1, "recorded_at": T(2), "valuation_date": "2026-09-30", "value_amount": 10000000, "currency": "USD", "evidence_document_id": None},
        {"id": V2, "recorded_at": T(5), "valuation_date": "2026-09-30", "value_amount": 10180000, "currency": "USD", "evidence_document_id": DOC}]


def seed_doc(plane):
    with wh.connect(plane) as con:
        con.execute("insert into documents (id, organization_id, source_system_id, access_group_id, document_type, title, original_uri, content_hash, document_status, processing_status, valuation_date, received_at, recorded_at) values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [DOC, wh.new_id(), wh.new_id(), wh.new_id(), "manager_statement", "Amended statement", "x", "h", "revised_estimate", "done", "2026-09-30", T(5), T(5)])
        con.execute("insert into valuation_observations (id, organization_id, instrument_id, valuation_date, received_at, recorded_at, value_amount, currency, "
                    "valuation_type, approval_status) values (?,?,?,?,?,?,?,?,?,?)", [V2, wh.new_id(), INST, "2026-09-30", T(5), T(5), 10180000, "USD", "manager_estimate", "pending"])
        con.execute("insert into extracted_fields (id, organization_id, document_id, field_name, value_numeric, currency, confidence, review_status) "
                    "values (?, ?, ?, 'nav', 10180000, 'USD', 'high', 'confirmed')", [FLD, wh.new_id(), DOC])


def test_bridge_is_program_arithmetic(world):
    plane, events = world
    seed_doc(plane)
    b = E.bridge(E.gather(plane, EXC))
    assert [x["label"] for x in b] == ["Value used in the issued report", "Manager-reported valuation now", "Manager-reported valuation difference"] and str(b[2]["amount"]) == "180000"


def test_rules_only_event_has_sources_and_only_known_figures(world):
    plane, events = world
    seed_doc(plane)
    assert E.propose_explanation(plane, EXC, object()) == "ev-new"
    et, note, run = events[0]
    assert et == "explanation_proposed" and run == "run-1" and "rules only" in note
    assert f"document {DOC}" in note and f"extracted field {FLD}" in note and f"valuation {V2}" in note
    facts = E.gather(plane, EXC)
    allowed = set(re.findall(r"\d[\d,.]*", " ".join(E.values(facts, E.bridge(facts)).values()))) | set(re.findall(r"\d[\d,.]*", note.split("Sources:")[1]))
    assert set(re.findall(r"\d[\d,.]*", note)) <= allowed
    assert "10,180,000 USD" in note and "180,000 USD" in note


def model_says(monkeypatch, text):
    import sh_platform.agents.loop as loop
    import sh_platform.build.agents.runtime as rt
    monkeypatch.setattr(rt, "runtime_for_plane", lambda plane: SimpleNamespace(model=object()))
    monkeypatch.setattr(loop, "run_agent", lambda *a, **k: SimpleNamespace(status="done", text=text))


def test_model_wording_is_filled_by_the_program(world, monkeypatch):
    plane, events = world
    seed_doc(plane)
    model_says(monkeypatch, '{"explanation": "A revised estimate for {instrument} is {new_value}, {difference} more than {old_value}."}')
    E.propose_explanation(plane, EXC, object())
    note = events[0][1]
    assert "Evergreen Growth I is 10,180,000 USD, 180,000 USD more than 10,000,000 USD." in note and "rules only" not in note


@pytest.mark.parametrize("said", ['{"explanation": "It rose by 190,000."}', '{"explanation": "See {made_up}."}', "no json"])
def test_bad_model_wording_falls_back(world, monkeypatch, said):
    plane, events = world
    seed_doc(plane)
    model_says(monkeypatch, said)
    E.propose_explanation(plane, EXC, object())
    assert "rules only" in events[0][1] and "made_up" not in events[0][1]


def test_unknown_case_and_skill_cap(world):
    plane, _ = world
    with pytest.raises(LookupError):
        E.propose_explanation(plane, wh.new_id(), object())
    s = load_skill("investigation")
    assert s and len(s) < 6000 and "never write a digit" in s.lower()


def test_wording_is_a_manager_reported_valuation_difference_never_pnl(world):
    plane, events = world
    seed_doc(plane)
    E.propose_explanation(plane, EXC, object())
    note = events[0][1]
    assert "manager-reported valuation difference of 180,000 USD" in note and "unverified until Operations confirms" in note and "Official NAV is untouched" in note
    assert not re.search(r"P&L|moved by|rose by|profit", note, re.I)
    assert "manager-reported valuation difference" in load_skill("investigation").lower()


def test_the_bridge_uses_the_date_of_the_case_not_the_newest_arrival(world, monkeypatch):
    plane, _ = world
    seed_doc(plane)
    oct_id, rid, vid = wh.new_id(), wh.new_id(), wh.new_id()
    with wh.connect(plane) as con:  # an October valuation arrives later; the September report is what the case is about
        con.execute("insert into valuation_observations (id, organization_id, instrument_id, valuation_date, received_at, recorded_at, value_amount, currency, "
                    "valuation_type, approval_status) values (?,?,?,?,?,?,?,?,?,?)", [oct_id, wh.new_id(), INST, "2026-10-31", T(9), T(9), 11000000, "USD", "manager_estimate", "pending"])
        con.execute("insert into reports (id, organization_id, report_code, report_name) values (?,?,?,?)", [rid, wh.new_id(), "inv", "September investment report"])
        con.execute("insert into report_versions (id, organization_id, report_id, calculation_run_id, period_end, cutoff_at, status, issued_at) values (?,?,?,?,?,?,?,?)",
                    [vid, wh.new_id(), rid, wh.new_id(), "2026-09-30", T(6), "issued", T(3)])
        con.execute("insert into exception_impacts (id, organization_id, exception_id, report_version_id, issued_value, draft_value, currency) values (?,?,?,?,?,?,?)",
                    [wh.new_id(), wh.new_id(), EXC, vid, 10000000, 10180000, "USD"])
    asked = []
    monkeypatch.setattr(sys.modules["sh_platform.v1.e1_asof"], "chain", lambda plane, table, row_id: asked.append(row_id) or VALS)
    E.gather(plane, EXC)
    assert [str(a) for a in asked] == [V2]
