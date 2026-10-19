"""Answer quality, as a person reads it (r7 review: docs/v3/LIVE-R7-ANSWERS.md). Synthetic data only.

1. Say only what was asked: the figure the question binds to, never other live figures appended (uc-005: net worth after the call notice).
2. What the question asks for: outside, not inside (uc-032); a verdict first on a yes/no question (uc-005, uc-004); steps from the process map (uc9-sop).
3. Plain words: no internal names, no underscores, a currency on every amount, no "1 portfolios", "due 0" or "USD 0" for unknowns, no answer-key wording.
4. The strict live checker (v3_persona.strict) and the build checks it reads (expect, must_not, must_have_verdict).
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

from sh_platform.v1 import v3_consume as C
from sh_platform.v1 import v3_figures as F
from sh_platform.v1 import v3_recipes as R

REPO = Path(__file__).resolve().parents[2]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(mod)
    return mod


VP = _load("v3_persona_quality", REPO / "docs" / "test" / "uc-live" / "uc6-scripts" / "v3_persona.py")


# ---- 1. say only what was asked ---------------------------------------------------------------------------------------------------------

RIDS = ("call_notice_fields", "net_worth", "bank_details_changed", "call_payment_status", "fx_required", "fx_rate_check", "cash_after_calls")


@pytest.fixture(scope="module")
def office(tmp_path_factory):
    sys.path.insert(0, str(REPO / "tools"))
    import score50
    plane, con, _ = score50.load(tmp_path_factory.mktemp("quality"))
    tables = []
    for rid in RIDS:
        r = R.recipe(rid)
        name = f"gold_q_{rid}"
        con.execute(R.render(r, name, R.dims_for(r, {})))
        cols = con.execute("select column_name, data_type from information_schema.columns where table_name = ? order by ordinal_position", [name]).fetchall()
        tables.append({"name": name, "columns": [{"name": c, "type": t} for c, t in cols], "rows": con.execute(f"select count(*) from {name}").fetchone()[0],
                       "purpose": f"{R.MARK}{rid}: {r['label']}"})
    con.close()
    return plane, tables


@pytest.fixture
def rows_of(office, monkeypatch):
    from sh_platform.v1 import b10_pack as P, cx_dash as CD
    plane, tables = office
    monkeypatch.setattr(P, "latest_approved", lambda *a: {"target": {"gold": [{"name": t["name"], "purpose": t["purpose"]} for t in tables]}})
    monkeypatch.setattr(CD, "gold_tables", lambda *a: tables)
    return lambda ask, bound, **kw: F.recipe_rows(plane, ask, "prj-1", {}, [{"name": n, "built_from": r} for n, r in bound.items()], **kw)


UC005 = "Cedarpoint now says to wire to an account ending 4471. Is that really them?"
UC005_FIGS = {"Capital call notice, as read": "call_notice_fields", "Net worth": "net_worth", "Payee bank details changed": "bank_details_changed"}


def test_the_figure_the_question_binds_to_is_said_and_nothing_else(rows_of):
    got = rows_of(UC005, UC005_FIGS, floor=2, lead="Payee bank details changed")
    assert "4471" in got["answer"] and "2209" in got["answer"], got["answer"]
    assert "Net worth" not in got["answer"] and "42,273,700" not in got["answer"], got["answer"]  # r7: net worth was appended after the notice
    assert any(r["label"].startswith("Net worth") for r in got["rows"])  # the other figures stay behind "Show the figures"


def test_without_a_bound_figure_only_the_best_fitting_figure_is_said(rows_of):
    got = rows_of(UC005, UC005_FIGS, floor=2)
    assert "Net worth" not in got["answer"], got["answer"]


def test_a_two_part_question_keeps_both_parts(rows_of):
    got = rows_of("We hold SGD and need USD for the call. How much do we convert, and did the bank trade at the right rate?",
                  {"SGD to convert": "fx_required", "Bank rate check": "fx_rate_check"}, lead="SGD to convert")
    assert "361,800" in got["answer"] and "fixing" in got["answer"], got["answer"]


# ---- 2. what the question asks for ------------------------------------------------------------------------------------------------------

def _p(q: str, a: str, rows=None) -> str:
    return C.polish(q, {"answer": a, "rows": rows or []})["answer"]


def test_asked_outside_never_answered_inside():
    got = _p("Which asset classes are outside their policy band?",
             "Inside the band: Cedarpoint Ventures 26.73% (0% to 55%); hedge_fund 54.55% (20% to 60%); listed_equity 80.61% (60% to 90%).")
    assert got.startswith("None is outside its band") and "Inside the band" not in got and "listed equity 80.61%" in got, got
    assert VP.strict(got, {"expect": ["80.61", "54.55", "26.73"], "must_not": ["Inside the band"]})["pass"]


@pytest.mark.parametrize("q, a, opens", [
    ("Can Holdings pay the Cedarpoint call on the 23rd?", "Evergreen Holdings is short USD 270,000 for the USD 1,250,000 call.", "No. "),
    ("Does call 7 fit what we committed to Cedarpoint Ventures III, and what is left after it?", "The USD 1,250,000 call fits Cedarpoint Ventures III.", "Yes. "),
    ("Is the September close complete and can the report start?", "2026-09 close: 4 of 6 steps done. Open: Read the report.", "No. "),
    ("Whether the office costs more than planned", "Office costs: USD 1,463,862.76 against a budget. Over budget for the period: grants.", "Yes. "),
    ("Whether every document and feed is in place before the first call", "3 of 5 items complete. Outstanding: call-back (missing).", "No. "),
])
def test_a_yes_no_question_gets_its_verdict_first(q, a, opens):
    got = _p(q, a)
    assert got.startswith(opens) and got.endswith(a), got
    assert VP.VERDICT.match(got)


def test_a_decision_question_reads_as_a_decision():
    assert _p("Whether to add a word to the language list", "To add to the language list: side letter.") == "Add to the language list: side letter."
    assert _p("Whether to sign off and issue the report: which sections are ready?", "40% is ready to sign. Not ready: Total.").startswith("Not yet. 40%")
    assert _p("Whether to sign off and issue the report?", "All 5 sections are ready to sign.") == "All 5 sections are ready to sign."


@pytest.mark.parametrize("q, a", [
    ("Whether to hedge a currency exposure?", "SGD exposure is 7.62% of the family; the bank confirms the forwards 8,100 apart."),  # a decision: never guessed
    ("Should we accept the administrator value or ask the administrator to correct it?", "Differs from the administrator: Evergreen Growth II."),  # a choice
    ("Whether spending is sustainable", "Spent on, largest first: Staff USD 580,620.95."),  # nothing says either way
    ("Cedarpoint now says to wire to an account ending 4471. Is that really them?", "Not confirmed: account 4471 differs from 2209 on file."),  # already one
])
def test_no_verdict_is_guessed(q, a):
    assert _p(q, a) == a


def test_steps_question_answers_from_the_process_map_or_says_there_is_none(monkeypatch):
    from sh_platform.v1 import v3_board_routes as B, v3_process as P
    monkeypatch.setattr(P, "answer", lambda plane, text: None)
    monkeypatch.setattr(C, "verified_answer", lambda *a, **k: {"answer": "Inside the band: listed_equity 80.61% (60% to 90%)."})
    monkeypatch.setattr(B, "_live", lambda plane, text="": None)
    got = B.fast(object(), None, "What are the steps of the month-end report process and who does each one?", None)
    assert got["answer"].startswith("Not available yet: no process map is live") and "80.61" not in got["answer"]
    assert B.fast(object(), None, "Which asset classes are outside their policy band?", None)["answer"].startswith("None is outside")  # other questions: the figures


# ---- 3. plain words ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("a, want, gone", [
    ("Over budget: listed_equity -5,811,695 (sell).", "listed equity", "listed_equity"),
    ("Columns renamed for Positions · position_snapshots.source_market_value · Market Value.", "source market value", "position_snapshots"),
    ("The run stopped at gold_every_morning_i_want_the_corpo_upcoming_actions.", "a ready table", "gold_"),
    ("Release Harbourline Fund Services (synthetic) USD 16,234.50.", "Harbourline Fund Services USD 16,234.50", "(synthetic)"),
    ("Assumed called within 24 months (no signed pacing rule is on record; the assumption of the answer key) · short.", "(no signed pacing rule is on record)", "answer key"),
    ("Daily P&L across the 1 portfolios loaded (of 8).", "1 portfolio loaded", "1 portfolios"),
    ("2021 USD 15,000,000 (1 fund(s)); 2022 USD 13,000,000 (2 fund(s)).", "(1 fund); 2022 USD 13,000,000 (2 funds)", "(s)"),
    ("Procedures overdue: Quarterly access review · Priya Nair: due 0.", "due date not stated", "due 0"),
    ("Policies expiring: POL-ART-02 · Fine art collection · USD 0; POL-CYB-04 · Family office cyber · SGD 1.", "Fine art collection · value not stated", "USD 0"),
])
def test_plain_words(a, want, gone):
    got = _p("Which ones?", a)
    assert want in got and gone not in got, got
    assert not VP.SNAKE.search(got) and "gold_" not in got


def test_every_amount_carries_its_currency():
    got = _p("Can Holdings pay?", "Evergreen Holdings is short USD 270,000 for the 1,250,000 of calls, after the 250,000 buffer. "
                                   "Converting SGD 361,800 of its 1,600,000 (worth USD 1,194,029.85) at 1.34 covers it.")
    assert "the USD 1,250,000 of calls" in got and "USD 250,000 buffer" in got and "of its SGD 1,600,000" in got and "at 1.34" in got, got
    assert "USD USD" not in got and "SGD SGD" not in got
    assert _p("How much?", "Entity B has 618,343.96 spare. Others: Evergreen Family Trust -36,104.48.", [{"label": "Cash · Entity B · USD", "value": "1"}]) \
        == "Entity B has USD 618,343.96 spare. Others: Evergreen Family Trust USD -36,104.48."  # the rows' one currency
    units = "The administrator holds 40,000 and the custodian 41,250, a difference of -1,250 units worth -60,062.50 USD."
    assert _p("Which holdings differ?", units) == units  # units and counts are not money
    assert _p("Which first?", "Collect manager statements: score 1,935.") == "Collect manager statements: score 1,935."
    assert _p("How much?", "Office costs 1,463,862.76 against 1,455,850.") == "Office costs 1,463,862.76 against 1,455,850."  # no currency on record: none guessed


# ---- 4. the strict live checker and the build checks ------------------------------------------------------------------------------------

def test_an_empty_expect_fails():
    assert not VP.strict("The steps are below.", {"ask": "What are the steps?", "expect": []})["pass"]


def test_expected_values_must_be_in_the_answer_text_itself():
    assert not VP.strict("Inside the band: see the figures.", {"expect": ["80.61"]})["pass"]  # a value only in the rows behind it does not count
    assert VP.strict("Listed equity 80.61%.", {"expect": ["80.61"]})["pass"]
    assert VP.strict("Lent on 5 Aug 2026; fix administrator cash first.", {"expect": ["2026-08-05", "administrator_cash"]})["pass"]  # said in plain words


def test_must_not_and_verdict():
    chk = {"expect": ["4471", "2209"], "must_not": ["Net worth"], "must_have_verdict": ["Not confirmed", "No"]}
    assert not VP.strict("Call 7 to account 4471, 2209 before. Net worth USD 1.", chk)["pass"]
    assert not VP.strict("Call 7 asks for 4471; earlier calls went to 2209.", chk)["pass"]
    assert VP.strict("Not confirmed: call 7 asks for 4471; earlier calls went to 2209.", chk)["pass"]
    assert not VP.strict("Short USD 270,000.", {"expect": ["270,000"], "must_have_verdict": True})["pass"]
    assert VP.strict("No. Short USD 270,000.", {"expect": ["270,000"], "must_have_verdict": True})["pass"]


@pytest.mark.parametrize("bad", ["hedge_fund 54.55", "built gold_x_y", "the assumption of the answer key", "Harbour Bank (synthetic)", "due 0."])
def test_plain_word_bans_apply_to_every_build(bad):
    got = VP.strict(f"Listed equity 80.61. {bad}", {"expect": ["80.61"]})
    assert not got["pass"] and got["banned"], got


def _builds():
    return {b["id"]: b for r in VP.all_roles().values() for b in r["builds"]}


def test_every_build_has_a_real_expect_and_the_named_ones_their_extra_checks():
    b = _builds()
    assert not [i for i, x in b.items() if not x["check"].get("expect")]
    assert "Inside the band" in b["uc-032-driftrep"]["check"]["must_not"]
    assert b["uc-005-benefcheck"]["check"]["must_have_verdict"] and "Net worth" in b["uc-005-benefcheck"]["check"]["must_not"]
    for i, x in b.items():  # a verdict is asked only of a yes/no or whether question
        if x["check"].get("must_have_verdict") and i != "uc-005-benefcheck":
            assert re.match(r"\s*(is|are|can|could|does|do|did|should|will|whether)\b", x["check"]["ask"], re.I), i


def test_uc9_sop_expect_comes_from_the_answer_key():
    keys = yaml.safe_load((REPO / "tests" / "v1" / "fixtures" / "office6m" / "answer_keys.yaml").read_text(encoding="utf-8"))["keys"]
    owners = keys["uc9-sop"]["questions"]["What are the steps of the month-end report process and who does each one?"]["expected"]["owners"]
    expect = _builds()["uc9-sop"]["check"]["expect"]
    assert set(expect) == set(owners) | set(owners.values())


def test_rescore_counts_old_and_strict(tmp_path, capsys, monkeypatch):
    rs = _load("rescore_live_quality", REPO / "tools" / "rescore_live.py")
    (tmp_path / "uc-032-driftrep.json").write_text(json.dumps({"build": "uc-032-driftrep", "person": "Tom Hale", "answer": "Inside the band: hedge_fund 54.55%; listed_equity 80.61%; Cedarpoint Ventures 26.73%.",
                                                               "check": {"ask": "Which asset classes are outside their policy band?", "expect": ["80.61"], "pass": True}}), encoding="utf-8")
    (tmp_path / "uc-055-corpact.json").write_text(json.dumps({"build": "uc-055-corpact", "person": "Sam Lee", "answer": None, "check": None}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["rescore_live.py", str(tmp_path)])
    rs.main()
    out = capsys.readouterr().out
    assert "2 builds | old checker pass 1 | strict on saved answers pass 0" in out, out
