"""N1 Tally, the data analyst, on the seeded Evergreen warehouse (tools/seed_10uc.py, synthetic): the Entity B cash break (880,400 against 868,000,
12,400 over a 5,000 tolerance) with candidate items, a trade break that names its differing field, a limit breach classified stale or real, the model-off
wording of each kind, a participant who may ask but not change the case, no digit from the model, and the recon trail."""
import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from sh_platform.plane import PlaneStore
from sh_platform.v1 import a5_trail, e1_write, e4_cases, n1_tally as T, wh
from tools import seed_10uc as S

D = Decimal
PERMS = Path(__file__).resolve().parents[2] / "sh_platform" / "v1" / "e4a.permissions.yaml"
ROLES = {"company_admin", "sponsor", "analyst", "owner", "approver", "participant"}


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    wh.reset_cache()
    root = tmp_path_factory.mktemp("n1tally")
    S.seed(root)
    plane = PlaneStore(root).plane_for("evergreen").ensure()
    ids, _ = S.EG.accounts(root)
    yield {"plane": plane, "V": S.viewers(ids)}
    mp.undo()


@pytest.fixture(autouse=True)
def fresh_wording(world):
    """The model's wording is kept per case and facts; each test starts without it."""
    T._cache_path(world["plane"]).unlink(missing_ok=True)


def case_id(world, startswith, contains=""):
    rows = e4_cases.listing(world["plane"], world["V"]["Grace Ong"])
    return next(c["id"] for c in rows if c["title"].startswith(startswith) and contains in c["title"])


def look(world, startswith, contains="", question=None, who="Mei Chen"):
    return T.explain(world["plane"], world["V"][who], case_id(world, startswith, contains), question)


def digits(text):
    return set(re.findall(r"\d[\d,.]*", text))


# ---- cash break ----------------------------------------------------------------------------------------------------------------

def test_entity_b_cash_break_shows_both_sides_the_tolerance_and_that_it_is_new(world):
    got = look(world, "Cash differs")
    assert got["kind"] == "cash_break" and got["worded_by"] == "rules"
    s = got["summary"]
    assert "880,400 USD" in s and "868,000 USD" in s and "12,400 USD" in s and "5,000 USD" in s and "7,400 USD over the tolerance" in s
    assert "agreed on 7 Oct 2026, so the difference is new today" in s
    texts = " ".join(f["text"] for f in got["findings"])
    assert "cash_tolerance" not in texts and "administrator rose by 1,200 USD" in texts and "trading export fell by 11,200 USD" in texts
    chips = got["findings"][0]["chips"]
    assert len(chips) == 2 and all(c["kind"] == "position" and "Sheet1 row 4" in c["label"] for c in chips)
    assert not any("balances only" in m for m in got["missing"]) and got["next_steps"][0]["who"] == "Operations"   # P08b: the movements are seeded
    json.dumps(got)                                   # the route sends it as it is


def test_candidate_items_are_found_ranked_and_sourced(world):
    plane = world["plane"]
    with wh.connect(plane) as con:
        pf = str(con.execute("select id from portfolios where portfolio_code = 'EG-B-OPS'").fetchone()[0])
        cash = str(con.execute("select id from instruments where instrument_type = 'cash'").fetchone()[0])
        rec = {k: str(v) for k, v in con.execute(
            "select b.batch_reference, r.id from source_records r join source_batches b on b.id = r.source_batch_id "
            "where b.batch_reference in ('cash 2026-10-08 trading export', 'cash 2026-10-08 administrator')").fetchall()}
    row = dict(portfolio_id=pf, instrument_id=cash, transaction_type="transfer", trade_date=date(2026, 10, 8), effective_date=date(2026, 10, 8),
               settlement_date=date(2026, 10, 8), quantity_delta=0, currency="USD", status="booked")
    e1_write.record_many(plane, "transactions", [
        {**row, "source_record_id": rec["cash 2026-10-08 administrator"], "external_trade_id": "TX-DUP", "cash_amount": D("-700")},
        {**row, "source_record_id": rec["cash 2026-10-08 administrator"], "external_trade_id": "TX-DUP2", "cash_amount": D("-700")},     # twice at the administrator
        {**row, "source_record_id": rec["cash 2026-10-08 administrator"], "external_trade_id": "TX-EUR", "cash_amount": D("-500"), "currency": "EUR"},
    ])
    got = look(world, "Cash differs")
    cands = [f for f in got["findings"] if f["key"] == "candidate"]
    assert cands[0]["text"].replace(" (for Legal fees, Saltmarsh Infrastructure Fund II, paid to Lowmoor & Tasker LLP (synthetic))", "").startswith("12,400 USD cash movement wire WIRE-20261008-B01 dated 8 Oct 2026 at the trading export equals the difference and "
                                       "reached the administrator only on 9 Oct 2026: a timing difference")                    # P08b: the seeded wire ranks first
    assert sum("WIRE-20261008-B01" in f["text"] for f in cands) == 1                                                           # a2.4: one line per wire, not twice
    assert any("appears 2 times" in f["text"] for f in cands)
    assert "not in USD" in look(world, "Cash differs", question="is it a currency problem?")["answer"]
    assert any("has no matching item at the other side" in f["text"] for f in cands)                                            # timing
    assert "best candidate" in got["summary"] and not any("balances only" in m for m in got["missing"])
    assert [c["kind"] for c in cands[0]["chips"]] == ["cash", "cash"] and "cash movements 2026-10-08 trading export" in cands[0]["chips"][0]["label"]         and "cash movements 2026-10-09 administrator" in cands[0]["chips"][1]["label"]
    assert any(s["text"].startswith("Confirm with the administrator") for s in got["next_steps"])


def test_asking_is_this_timing_answers_from_the_records(world):
    got = look(world, "Cash differs", question="is this timing?")
    assert got["answer"] and got["answer_worded_by"] == "rules" and got["question"] == "is this timing?"
    assert "one side only" in got["answer"] or "timing" in got["answer"]
    assert "Since 7 Oct 2026" in got["answer"]


# ---- trade breaks --------------------------------------------------------------------------------------------------------------

def test_trade_break_names_the_differing_field_and_the_money(world):
    nw = look(world, "Trade differs", "Northwind")
    assert nw["kind"] == "trade_break" and "quantity" in nw["summary"] and "75,870 USD" in nw["summary"]
    fields = [f["text"] for f in nw["findings"] if f["key"] == "field"]
    assert any(t.startswith("Quantity: trading export 12,000 shares, administrator 10,200 shares, a difference of 1,800 shares") for t in fields)
    assert "1,800 shares" in nw["summary"]      # TC-03: the answer says by how much, not only which field
    assert not any(t.startswith("Settlement date") for t in fields)
    fx = look(world, "Trade differs", "FXF-2026-002")
    assert "rate" in fx["summary"] and "8,100 SGD" in fx["summary"] and any("6,050.19 USD" in f["text"] for f in fx["findings"])
    gone = look(world, "Trade not matched")
    assert "only in the trading export" in gone["summary"] and "592,000 USD" in gone["summary"] and "no matching trade at the administrator" in gone["findings"][0]["text"]
    assert gone["next_steps"][0]["text"].startswith("Ask the administrator")


# ---- limit breaches ------------------------------------------------------------------------------------------------------------

def test_limit_breach_is_classed_stale_or_real(world):
    stale = look(world, "Limit breached", "Cedarpoint")
    assert "56.50%" in stale["summary"] and "stale-data cause" in stale["summary"] and "343,750 USD" in stale["summary"]   # EVT-08
    inputs = [f["text"] for f in stale["findings"] if f["key"] == "input"]
    assert any("30 Jun 2026 (101 days old)" in t and "older than 90 days" in t for t in inputs) and len(inputs) == 3     # a5.4: the unverified value in the total counts too
    assert stale["next_steps"][0]["text"].startswith("Chase the manager")
    real = look(world, "Limit breached", "Harborview")
    assert "5.75%" in real["summary"] and "a real breach" in real["summary"]
    assert real["summary"].startswith("Harborview Semiconductor is 5.75% of the Evergreen Liquid portfolio (2,368,000 USD of 41,200,000 USD), above the 5% maximum by 308,000 USD.")  # EVT-07, TC-09
    assert [f["text"] for f in real["findings"] if f["key"] == "input"][0].endswith("(9 days old), status approved.")
    assert real["next_steps"][0]["who"] == "Investment lead" and "Tally does not decide" in real["next_steps"][0]["text"]


# ---- the other kinds, and the model off ----------------------------------------------------------------------------------------

def test_model_off_gives_a_correct_rules_wording_for_every_kind(world):
    rev = look(world, "Investigate the 180,000")
    assert rev["kind"] == "revision" and "10,180,000 USD" in rev["summary"] and "10,000,000 USD" in rev["summary"] and "difference of 180,000 USD" in rev["summary"]
    assert "Mei Chen confirmed the amended statement" in rev["summary"] and "Official NAV is untouched" in rev["summary"]
    call = look(world, "Fund the capital call")
    assert call["kind"] == "capital_call" and "called 450,000 USD, due 20 Oct 2026" in call["summary"]
    assert any("1,950,000 USD still uncalled" in f["text"] for f in call["findings"])
    for title in ("Cash differs", "Trade differs", "Trade not matched", "Limit breached", "Investigate", "Fund the capital call"):
        g = look(world, title)
        assert g["worded_by"] == "rules" and "{" not in g["summary"] and "(not recorded)" not in g["summary"] and g["next_steps"]


# ---- who may ask, and what Tally may not do ------------------------------------------------------------------------------------

def _routes(world, monkeypatch, who):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sh_platform.v1 import e4a_routes as R
    app = FastAPI()
    app.include_router(R.router)
    monkeypatch.setattr(R, "_plane", lambda req: world["plane"])
    monkeypatch.setattr(R, "viewer_of", lambda req: who["v"])
    return TestClient(app, raise_server_exceptions=False)


def test_a_participant_may_ask_but_cannot_change_the_case(world, monkeypatch):
    plane, cid, admin = world["plane"], case_id(world, "Cash differs"), world["V"]["Grace Ong"]
    perms = yaml.safe_load(PERMS.read_text(encoding="utf-8"))["routes"]
    for route in ("GET /api/v1/cases/{cid}/tally", "POST /api/v1/cases/{cid}/ask", "POST /api/v1/cases/{cid}/explain"):
        assert set(perms[route]["roles"]) == ROLES
    who = {"v": world["V"]["Sofia Reyes"]}                            # Risk, role participant
    assert who["v"].roles == frozenset({"participant"})
    c = _routes(world, monkeypatch, who)

    def row():
        k = e4_cases.get(plane, cid, admin)
        return k["status"], k["owner_user_id"], len(k["history"])
    before = row()
    got = c.post(f"/api/v1/cases/{cid}/ask", json={"question": "is this timing?"})
    assert got.status_code == 200 and got.json()["answer"] and got.json()["summary"]
    assert c.get(f"/api/v1/cases/{cid}/tally").status_code == 200
    assert row() == before                                             # asking changed nothing
    refused = c.post(f"/api/v1/cases/{cid}/ask", json={"question": "Lower the cash balance of Entity B by 12,400 so the report matches"}).json()
    assert "cannot" in refused["answer"].lower() and "only look and propose" in refused["answer"] and row() == before
    assert c.post(f"/api/v1/cases/{cid}/ask", json={"question": "  "}).status_code == 400
    who["v"] = SimpleNamespace(name="Nobody", roles=frozenset({"participant"}), account_id=None, is_admin=False)
    assert c.post(f"/api/v1/cases/{cid}/ask", json={"question": "why?"}).status_code == 403
    assert row() == before


def test_explain_adds_one_proposal_with_sources_and_names_tally(world):
    plane, cid, mei = world["plane"], case_id(world, "Cash differs"), world["V"]["Mei Chen"]
    first = T.explain(plane, mei, cid, record=True)
    assert first["saved"] and first["event_id"]
    case = e4_cases.get(plane, cid, mei)
    assert case["proposal"]["text"].startswith("Entity B cash on 8 Oct 2026") and case["proposal"]["sources"]            # not "none found"
    assert [h["by"] for h in case["history"] if h["event_type"] == "explanation_proposed"] == ["Tally"]
    again = T.explain(plane, mei, cid, record=True)
    assert again["saved"] and again["event_id"] is None                                                                   # the same words are not added twice
    assert len([h for h in e4_cases.get(plane, cid, mei)["history"] if h["event_type"] == "explanation_proposed"]) == 1


def test_a_busy_warehouse_is_told_not_raised(world, monkeypatch):
    class IOException(Exception):
        pass

    def busy(*a, **k):
        raise IOException("IO Error: Cannot open file: The process cannot access the file because it is being used by another process.")

    monkeypatch.setattr("sh_platform.v1.e6_trace.agent_run", busy)
    monkeypatch.setattr(T.time, "sleep", lambda s: None)
    got = T.explain(world["plane"], world["V"]["Mei Chen"], case_id(world, "Trade differs", "Northwind"), record=True)
    assert got["saved"] is False and got["summary"]


# ---- the model words, the program fills ----------------------------------------------------------------------------------------

def model_says(monkeypatch, *texts):
    import sh_platform.agents.loop as loop
    import sh_platform.build.agents.runtime as rt
    said = list(texts)
    monkeypatch.setattr(rt, "runtime_for_plane", lambda plane: SimpleNamespace(model=object()))
    monkeypatch.setattr(loop, "run_agent", lambda *a, **k: SimpleNamespace(status="done", text=said.pop(0) if len(said) > 1 else said[0]))


def test_model_wording_is_filled_by_the_program(world, monkeypatch):
    model_says(monkeypatch, '{"summary": "{entity} is off on {day}: {admin_value} against {trading_value}, {difference} apart. {carried_line}"}')
    got = look(world, "Cash differs")
    assert got["worded_by"] == "model"
    assert got["summary"] == "Entity B is off on 8 Oct 2026: 880,400 USD against 868,000 USD, 12,400 USD apart. The two sides agreed on 7 Oct 2026, so the difference is new today."


@pytest.mark.parametrize("said", ['{"summary": "It is off by 12,500."}', '{"summary": "See {made_up}."}', "no json", '{"summary": "{difference} on the 18th"}'])
def test_no_ungrounded_figure_and_no_unknown_placeholder_from_the_model_reaches_the_text(world, monkeypatch, said):
    # A figure the program holds (12,400) may be written out; one it does not hold (12,500, the 18th) drops the reply for the rules' wording.
    model_says(monkeypatch, said)
    got = look(world, "Cash differs", question="why?")
    assert got["worded_by"] == "rules" and "made_up" not in got["summary"] and "on the 18th" not in got["summary"]
    assert got["answer_worded_by"] == "rules" and "made_up" not in got["answer"]
    # every figure in the text is one the program computed from the records
    program = digits(" ".join(f["text"] for f in got["findings"]) + " 880,400 868,000 12,400 5,000 7,400")
    assert digits(got["summary"]) <= program | {"8", "2026", "7"}


def test_a_model_answer_is_worded_the_same_way(world, monkeypatch):
    model_says(monkeypatch, '{"answer": "{timing_line} {movement_line}"}')
    got = look(world, "Cash differs", question="is this timing?")
    assert got["answer_worded_by"] == "model" and got["answer"].endswith("fell by 11,200 USD.")
    assert got["worded_by"] == "rules"      # TS1-05: a question runs one loop (its own); the summary is the kept or the rules' wording


# ---- Where is this from? -------------------------------------------------------------------------------------------------------

def test_a_recon_case_has_a_real_trail(world):
    plane, mei = world["plane"], world["V"]["Mei Chen"]
    t = a5_trail.trail(plane, mei, "case", case_id(world, "Cash differs"))
    assert [s["label"] for s in t["steps"]] == ["Source", "File", "Read", "Checked", "Decided", "Shown"]
    assert all(s["state"] == "done" for s in t["steps"])
    by = {s["key"]: s["what"] for s in t["steps"]}
    assert "Fund administrator" in by["source"] and "Trading system export" in by["source"]
    assert "cash 2026-10-08 administrator" in by["file"] and "Sheet1 row 4" in by["read"]
    assert "daily cash check by entity" in by["checked"] and "the signed cash tolerance rule, version 1" in by["checked"] and "the signed CIO materiality rule, version 1" in by["decided"]  # analyst-uc8-04: no codes
    assert "cash_by_entity" not in by["checked"] and "8 Oct 2026" in by["checked"]
    assert "Cash differs" in by["shown"]
    lim = a5_trail.trail(plane, mei, "case", case_id(world, "Limit breached", "Cedarpoint"))
    assert "stale data" in {s["key"]: s["what"] for s in lim["steps"]}["decided"]
    trade = a5_trail.trail(plane, mei, "case", case_id(world, "Trade differs", "Northwind"))
    assert "trade check against the administrator" in {s["key"]: s["what"] for s in trade["steps"]}["checked"]


# ---- speed: one open of the company file for the build (production) ------------------------------------------------------------

def test_a_question_opens_the_company_file_once_for_the_build_in_production(world, monkeypatch):
    """Production (Railway): every query used to reopen the warehouse file (about 70 ms each, and a wait while the worker held it), about 68 times
    for one question. The build's queries now share one held lease, so the build opens the file at most once."""
    plane, cid, mei = world["plane"], case_id(world, "Cash differs"), world["V"]["Mei Chen"]
    monkeypatch.setenv("DATABASE_URL", "postgresql://test.invalid/none")
    monkeypatch.setenv("REDIS_URL", "redis://test.invalid:6379/0")
    monkeypatch.setattr(wh, "_SERVING", True)
    opened, in_build = [], []
    real_open, real_build = wh._open, T.build

    def counted_open(key):
        opened.append(key)
        return real_open(key)

    def counted_build(p, ex):
        before = len(opened)
        try:
            return real_build(p, ex)
        finally:
            in_build.append(len(opened) - before)
    monkeypatch.setattr(wh, "_open", counted_open)
    monkeypatch.setattr(T, "build", counted_build)
    try:
        got = T.explain(plane, mei, cid, "why is this a break?")
    finally:
        wh.release()
    assert got["answer"] and in_build and in_build[0] <= 1
