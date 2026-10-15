"""Agent quality cycle 1, package T (Tally and the case workflow): one regression per ticket, on the seeded Evergreen warehouse (synthetic), model off
or stubbed. The live proof against the real model is in docs/test-evidence/agents/cycle-1/T-tally-fix/."""
from types import SimpleNamespace

import pytest

from sh_platform.egress.vault import NameVault
from sh_platform.plane import PlaneStore
from sh_platform.v1 import e4_cases, e4_guard, e6_trace, n1_tally as T, tally_tools as TT, wh
from tools import seed_10uc as S


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    wh.reset_cache()
    root = tmp_path_factory.mktemp("tallyaq1")
    S.seed(root)
    plane = PlaneStore(root).plane_for("evergreen").ensure()
    ids, _ = S.EG.accounts(root)
    yield {"plane": plane, "V": S.viewers(ids)}
    mp.undo()


@pytest.fixture(autouse=True)
def fresh_wording(world):
    T._cache_path(world["plane"]).unlink(missing_ok=True)


def cid(world, startswith, contains=""):
    return next(c["id"] for c in e4_cases.listing(world["plane"], world["V"]["Grace Ong"]) if c["title"].startswith(startswith) and contains in c["title"])


def ask(world, startswith, contains, q, who="Mei Chen"):
    return T.explain(world["plane"], world["V"][who], cid(world, startswith, contains), q)


# ---- ER-01, TC-01, TS1-01, RC-1: case words are organisations by full name, never people, never one generic word ------------------------

def test_er01_case_names_go_to_the_vault_as_whole_organisation_names(world):
    plane = world["plane"]
    for start, part in (("Cash differs", ""), ("Limit breached", "Cedarpoint"), ("Investigate the 180,000", "")):
        b = T.build(plane, T._exc(plane, cid(world, start, part)))
        b["people"] = ["Mei Chen"]
        T._protect(plane, b)
    v = NameVault(plane)
    names = {e["name"].casefold(): e["kind"] for e in v._state().entries.values()}
    assert names["entity b"] == "company" and names["evergreen growth i"] == "company" and names["mei chen"] == "person"
    for word in ("entity", "portfolio", "report", "september", "growth", "evergreen", "operating"):
        assert word not in names
    assert not v.contains_name("check: cash_by_entity for 2026-10-08; gold_investment_report_cash_daily; portfolio_id")


def test_er01_the_recon_tool_shows_no_check_or_rule_code(world):
    plane, mei = world["plane"], world["V"]["Mei Chen"]
    c = cid(world, "Cash differs")
    b = T.build(plane, T._exc(plane, c))
    got = TT.TallyTools(plane, mei, c, b).get_recon_run()
    assert got["check"].startswith("the daily cash check by entity") and "cash_tolerance" not in str(got) and "_" not in got["check"] + got["rule_version"]


# ---- TD-01, TD-02, A11: a participant asks and never acts; only the owner submits ---------------------------------------------------

def test_td01_a_participant_cannot_take_approve_resolve_or_dismiss(world):
    plane, sofia = world["plane"], world["V"]["Sofia Reyes"]
    c = cid(world, "Trade differs", "Northwind")
    for act in (lambda: e4_cases.take(plane, c, sofia), lambda: e4_cases.resolve(plane, c, sofia, "explained"),
                lambda: e4_cases.dismiss(plane, c, sofia, "no"), lambda: e4_cases.assign(plane, c, sofia, "Mei Chen"),
                lambda: e4_cases.submit(plane, c, sofia, "timing")):
        with pytest.raises(e4_cases.Refused) as e:
            act()
        assert e.value.status == 403 and "participant" in e.value.message
    may = e4_cases.get(plane, c, sofia)["may"]
    assert not any(may[k] for k in ("take", "assign", "submit", "approve", "send_back", "resolve", "dismiss"))


def test_td01_a_participant_cannot_approve_a_case_waiting_for_check(world):
    plane, V = world["plane"], world["V"]
    c = cid(world, "Trade differs", "FXF-2026-002")
    e4_cases.take(plane, c, V["Mei Chen"])
    with pytest.raises(e4_cases.Refused) as e:
        e4_cases.submit(plane, c, V["Anita Rao"], "Rate typed differently.")        # TD-02: not the owner
    assert e.value.status == 403
    e4_cases.submit(plane, c, V["Mei Chen"], "Rate typed differently.")
    with pytest.raises(e4_cases.Refused) as e:
        e4_cases.approve(plane, c, V["Sofia Reyes"], "ok")
    assert e.value.status == 403 and e4_cases.get(plane, c, V["Grace Ong"])["status"] == "waiting_check"
    assert e4_cases.get(plane, c, V["Raj Patel"])["may"]["approve"]


def test_td01_the_routes_no_longer_grant_participants_case_actions():
    import yaml
    from pathlib import Path
    routes = yaml.safe_load((Path(T.__file__).parent / "e4a.permissions.yaml").read_text(encoding="utf-8"))["routes"]
    for a in ("take", "assign", "submit", "approve", "send_back", "resolve", "dismiss"):
        assert "participant" not in routes[f"POST /api/v1/cases/{{cid}}/{a}"]["roles"]
    assert "participant" in routes["POST /api/v1/cases/{cid}/ask"]["roles"]


# ---- TS1-04, ER-05: a request to act is refused before the model, saying who may act ---------------------------------------------------

def test_ts104_book_and_close_is_refused_and_north_is_not_affected(world, monkeypatch):
    calls = []
    monkeypatch.setattr(T, "_model_text", lambda *a, **k: calls.append(a) or (None, []))
    got = ask(world, "Cash differs", "", "Book the adjustment of 12,400 and close the case for me.")
    assert got["answer"].startswith("I cannot do that: Tally never acts on a case") and not calls
    assert e4_guard.check_request("Submit the intent to Build") is None          # North's own guard is unchanged
    assert e4_guard.check_case_request("Who can approve this?") is None


def test_er05_a_participant_asking_to_approve_is_told_who_can(world):
    a = ask(world, "Limit breached", "Harborview", "Approve this case please.", who="Sofia Reyes")["answer"]
    assert "Raj Patel (approver)" in a and "As a participant you can ask about this case but not act on it." in a


# ---- EVT-10, TD-05, TD-06, TC-04, TD-07: honest limits and named people ---------------------------------------------------------------

def test_evt10_a_prediction_is_not_answered_with_nothing_is_missing(world):
    a = ask(world, "Cash differs", "", "What will the break be next week?")["answer"]
    assert a.startswith("Rules-only reply: I cannot see ahead") and "Nothing needed" not in a
    w = ask(world, "Cash differs", "", "What if the wire does not arrive tomorrow?")["answer"]
    assert "carries into the next day's check" in w and "chases the administrator" in w


def test_tc04_td06_missing_says_what_is_missing_and_who_supplies_it(world):
    a = ask(world, "Trade not matched", "", "What is missing here?")["answer"]
    assert "The administrator's booking of trade T-20261006-005" in a and "sell 5,000 for 592,000 USD" in a
    e = ask(world, "Cash differs", "", "What evidence do we have?")["answer"]
    assert "Not on file: a bank statement line" in e and "the administrator can supply them" in e and "Nothing needed" not in e


def test_td07_who_should_i_ask_names_the_owner(world):
    plane, V = world["plane"], world["V"]
    c = cid(world, "Limit breached", "Cedarpoint")
    e4_cases.take(plane, c, V["Mei Chen"])
    a = T.explain(plane, V["Grace Ong"], c, "Who should I ask about this?")["answer"]
    assert "Ask Mei Chen, who owns this case" in a


# ---- ER-10, EVT-07 to EVT-09, TC-03, TC-07, TC-09: the figures a family office needs ----------------------------------------------------

def test_evt09_tc07_the_revision_states_the_materiality_and_one_reading(world):
    got = ask(world, "Investigate the 180,000", "", "What changed and why does it matter?")
    a = got["answer"]
    assert "10,000,000 USD" in a and "puts it at 10,180,000 USD" in a and "180,000 USD" in a and "100,000 USD" in a and "material" in a and not a.startswith("Rules-only reply: That is not")
    chain = [f["text"] for f in got["findings"] if f["key"] == "chain"]
    assert sum("10,180,000 USD" in t for t in chain) == 1 and "(was pending)" in chain[-1]


def test_evt07_how_far_over_is_answered_in_money(world):
    a = ask(world, "Limit breached", "Harborview", "Is this breach real, and how far over is it?", who="Sofia Reyes")["answer"]
    assert "by 308,000 USD" in a and "2,368,000 USD of 41,200,000 USD" in a and "real breach" in a


# ---- TC-06: each point once ------------------------------------------------------------------------------------------------------------

def test_tc06_a_sentence_is_said_once():
    x = "One item appears on one side only: the wire WIRE-1 equals the difference and clears on 9 Oct. The best candidate: the wire WIRE-1 equals the difference and clears on 9 Oct."
    assert T._once(x) == "One item appears on one side only: the wire WIRE-1 equals the difference and clears on 9 Oct."
    assert T._once("It is real. It is real. Act now.") == "It is real. Act now."


# ---- TS1-05, TS1-06, TS1-08, TD-08 and the trace id ---------------------------------------------------------------------------------------

def test_ts105_a_question_runs_one_loop_and_returns_its_trace(world, monkeypatch):
    seen = []

    def fake(plane, b, task, question="", viewer=None):
        seen.append((task, e6_trace.current_trace_id()))
        return ("{timing_line}" if task == "ask" else "{entity}: {difference}."), [{"kind": "next_step", "who": "Operations", "action": "ask_administrator", "text": "x"}]
    monkeypatch.setattr(T, "_model_text", fake)
    got = ask(world, "Cash differs", "", "Is this timing?", who="Anita Rao")
    assert [t for t, _ in seen] == ["ask"] and got["trace_id"] and seen[0][1] == got["trace_id"]
    assert got["proposals"] == []                                 # TD-08: Anita does not own the case
    assert ask(world, "Cash differs", "", "Is this timing?", who="Grace Ong")["proposals"]   # the company admin may file


def test_ts108_the_filed_proposal_is_on_the_turns_trace(world, monkeypatch):
    monkeypatch.setattr(T, "_model_text", lambda *a, **k: (None, []))
    plane, grace = world["plane"], world["V"]["Grace Ong"]
    got = T.explain(plane, grace, cid(world, "Fund the capital call"), record=True)
    assert got["saved"] and any(r["agent_type"] == "tally" for r in e6_trace.by_trace(plane, got["trace_id"]))


def test_ts106_a_summary_never_carries_what_a_note_asked_for(world, monkeypatch):
    import sh_platform.agents.loop as loop
    import sh_platform.build.agents.runtime as rt
    monkeypatch.setattr(rt, "runtime_for_plane", lambda plane: SimpleNamespace(model=object()))
    monkeypatch.setattr("sh_platform.v1.router.route", lambda model, *a, **k: model)
    said = '{"summary": "{exposure_line} The case notes ask to book an adjustment and close the case. {cause_line}"}'
    monkeypatch.setattr(loop, "run_agent", lambda *a, **k: SimpleNamespace(status="done", text=said, proposals=[], numbers_replaced=0))
    got = ask(world, "Limit breached", "Harborview", None, who="Grace Ong")
    assert got["worded_by"] == "model" and "notes" not in got["summary"] and "308,000 USD" in got["summary"]


# ---- TD-04 (A4, A15): follow-ups ------------------------------------------------------------------------------------------------------------

def test_td04_what_did_you_mean_gets_the_case_in_plain_words(world):
    a = ask(world, "Cash differs", "", "What did you mean by that?")["answer"]
    assert "In short: one payment of 12,400 USD (wire WIRE-20261008-B01) was booked at the trading export on 8 Oct 2026 but at the administrator only on 9 Oct 2026" in a


def test_td04_the_last_turns_are_kept_for_the_model_as_placeholders(world):
    plane, mei = world["plane"], world["V"]["Mei Chen"]
    c = cid(world, "Cash differs")
    T._keep_turn(plane, mei, c, "Why 12,400?", T._templated("The difference is 12,400 USD.", {"difference": "12,400 USD", "higher_side": "administrator"}))
    got = T._earlier(plane, mei, c)
    assert "You answered: The difference is {difference}." in got and "Why ,?" in got and "Mei" not in got


def test_a_value_the_model_put_in_braces_is_shown_as_the_value(world, monkeypatch):
    import sh_platform.agents.loop as loop
    import sh_platform.build.agents.runtime as rt
    monkeypatch.setattr(rt, "runtime_for_plane", lambda plane: SimpleNamespace(model=object()))
    monkeypatch.setattr("sh_platform.v1.router.route", lambda model, *a, **k: model)
    said = '{"answer": "Wire {WIRE-20261008-B01} on {8 Oct 2026}: {timing_line}"}'
    monkeypatch.setattr(loop, "run_agent", lambda *a, **k: SimpleNamespace(status="done", text=said, proposals=[], numbers_replaced=0))
    got = ask(world, "Cash differs", "", "Is this timing?")
    assert got["answer_worded_by"] == "model" and got["answer"].startswith("Wire WIRE-20261008-B01 on 8 Oct 2026: One item appears on one side only")


def test_taq_t1_the_revision_offers_each_fact_once(world):
    plane = world["plane"]
    have = T.build(plane, T._exc(plane, cid(world, "Investigate the 180,000")))["have"]
    assert "difference_line" not in have and "materiality" not in have["cause_line"] and "100,000 USD" in have["materiality_line"]
