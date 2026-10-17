"""W6 live figures: a call question is answered from the office's verified figures, and North's figure names bind to the pack's recipes.

The live uc-004 build answered "No capital calls are due in the next 30 days": the ask route read the older liquidity forecast first, and North's
"Shortfall" and "SGD conversion amount" got no ready table (one was left unbound, the other's recipe table was dropped by the rate guard).

Real: the recipes, the binding rules, the plan guard, the office6m loader and warehouse, the recipe SQL, the call answer. The project's pack and gold
table list are stand-ins (no build runs here). Synthetic data only."""
from __future__ import annotations

from pathlib import Path

import pytest

from sh_platform.v1 import v3_consume as C
from sh_platform.v1 import v3_figures as F
from sh_platform.v1 import v3_plan_guard as PG
from sh_platform.v1 import v3_recipes as R

QUESTION = ("A Cedarpoint call is due on the 23rd. I want to know in one answer whether Holdings can pay it from its own cash after the 250,000 buffer, "
            "what is short if not, and how much SGD to convert. Anything over 500,000 needs my name on it.")


# ---- binding: North's names reach the recipes ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name, definition, want", [
    ("Shortfall", "Amount by which cash after buffer falls short of the call amount.", "cash_after_calls"),  # the live brief's own words
    ("SGD conversion amount", "USD shortfall (if any) converted to SGD using the approved FX rate.", "fx_required"),  # the live brief's own words
    ("Cash short after the buffer", "", "cash_after_calls"),
    ("SGD to convert", "How much SGD to convert to cover the shortfall.", "fx_required"),
    ("Shortage", "Holdings cash less the 250,000 buffer less the call due, when negative.", "cash_after_calls"),
    ("Amount to convert", "", "fx_required"),
    ("Calls due in 30 days", "", "calls_due"),
])
def test_north_names_bind_to_recipes(name, definition, want):
    kpis = [{"name": name, "definition": definition}]
    R.bind(None, None, kpis, QUESTION)  # no model: the rules alone
    assert kpis[0]["built_from"] == want, kpis[0]


def test_question_suggests_the_recipes_no_figure_is_built_from():
    kpis = [{"name": "Cedarpoint call amount", "definition": "The amount of the call due on the 23rd."}]
    R.bind(None, None, kpis, QUESTION)
    assert {"cash_after_calls", "fx_required"} <= {k.get("built_from") for k in kpis}


def test_shortlist_stays_small_and_holds_the_recipe():
    for k, want in (({"name": "Shortfall", "definition": "Amount by which cash after buffer falls short of the call amount."}, "cash_after_calls"),
                    ({"name": "SGD conversion amount", "definition": "USD shortfall converted to SGD."}, "fx_required")):
        got = [r["id"] for r in R.shortlist(k)]
        assert want in got and len(got) <= R.SHORT


def test_unbound_figure_says_no_recipe_yet():
    assert R.shown({"name": "Weather", "built_from": ""}).startswith("No recipe yet")


# ---- cover: a bound recipe's table passes the plan guard --------------------------------------------------------------------------------------

@pytest.mark.parametrize("rid", ["fx_required", "cash_after_calls", "calls_due"])
def test_recipe_tables_pass_the_rate_guard(rid):
    r = R.recipe(rid)
    t = R._table("w6", r, {"name": "x"})
    assert PG.rate_without_division(t) is None


def test_rate_guard_still_catches_a_summed_rate():
    assert PG.rate_without_division({"kpis": ["Match rate"], "sql": "create table g as select sum(matched) as match_rate from t"})


# ---- answer order: verified figures before the liquidity tool ----------------------------------------------------------------------------------

def _stub(monkeypatch, fig, liq):
    monkeypatch.setattr(F, "figure_answer", lambda *a, **k: fig)
    monkeypatch.setattr(C, "liquidity_answer", lambda *a, **k: liq)


ZERO = {"answer": "No capital calls are due in the next 30 days (as at 13 Oct 2026).", "figure": {"label": "Calls due in 30 days · USD", "value": "None"}}
TH = {"id": "t-1", "pid": "prj-1"}


def test_verified_figure_wins_over_the_forecast(monkeypatch):
    fig = {"answer": "Evergreen Holdings is short USD 270,000 for the 1,250,000 of calls due 23 Oct 2026.", "figure": {"label": "Shortfall", "value": "270,000.00"}}
    _stub(monkeypatch, fig, ZERO)
    assert C.verified_answer(None, None, "Can Holdings pay the Cedarpoint call on the 23rd?", None, TH) is fig


def test_no_zero_calls_over_a_calls_figure(monkeypatch):
    fig = {"answer": "Not available yet: Shortfall has no figure in the ready tables.", "figure": None}
    _stub(monkeypatch, fig, ZERO)
    assert C.verified_answer(None, None, "Which calls are due?", None, TH) is fig


def test_forecast_answers_when_no_figure_does(monkeypatch):
    _stub(monkeypatch, None, ZERO)
    assert C.verified_answer(None, None, "Which calls are due?", None, TH) is ZERO


# ---- the call answer reads the recipe tables -------------------------------------------------------------------------------------------------

RIDS = ("cash_after_calls", "fx_required", "bank_details_changed", "call_payment_status", "payment_batch", "commitments_by_fund", "called_to_date",
        "call_notice_fields", "net_worth", "fx_rate_check")


@pytest.fixture(scope="module")
def office(tmp_path_factory):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    import score50
    plane, con, _ = score50.load(tmp_path_factory.mktemp("w6"))
    tables = []
    for rid in RIDS:
        r = R.recipe(rid)
        name = f"gold_w6_{rid}"
        con.execute(R.render(r, name, R.dims_for(r, {})))
        cols = con.execute("select column_name, data_type from information_schema.columns where table_name = ? order by ordinal_position", [name]).fetchall()
        tables.append({"name": name, "columns": [{"name": c, "type": t} for c, t in cols], "rows": con.execute(f"select count(*) from {name}").fetchone()[0],
                       "purpose": f"{R.MARK}{rid}: {r['label']}"})
    con.close()
    return plane, tables


def test_call_question_states_every_figure(office, monkeypatch):
    from sh_platform.v1 import b10_pack as P, cx_dash as CD
    plane, tables = office
    monkeypatch.setattr(P, "latest_approved", lambda *a: {"target": {"gold": [{"name": t["name"], "purpose": t["purpose"]} for t in tables]}})
    monkeypatch.setattr(CD, "gold_tables", lambda *a: tables)
    kpis = [{"name": "Shortfall", "built_from": "cash_after_calls"}, {"name": "SGD conversion amount", "built_from": "fx_required"}]
    got = F.recipe_rows(plane, "Can Holdings pay the Cedarpoint call on the 23rd?", "prj-1", {}, kpis)
    print(got["answer"])
    said = got["answer"].replace(",", "")
    for want in ("1230000", "1600000", "1194029.85", "1250000", "250000", "270000", "361800", "1.34"):
        assert want in said, (want, got["answer"])
    assert got["answer"].startswith("Evergreen Holdings is short USD 270,000")


@pytest.mark.parametrize("ask, bound, want", [
    ("Cedarpoint now says to wire to an account ending 4471. Is that really them?",  # uc-005: the account endings, not a payment amount
     {"Account number match": "call_payment_status", "Payment hold flag": "payment_batch", "Bank details changed": "bank_details_changed"}, ["2209", "4471"]),
    ("What's our unfunded commitment across all funds?", {"Unfunded commitments": "commitments_by_fund", "Net worth": "net_worth"}, ["14600000"]),  # uc-007
    ("Which payments to release", {"Payments ready": "payment_batch", "Net worth": "net_worth"}, ["5400", "16234.5", "6180", "1030"]),  # uc-008
    ("Does call 7 fit what we committed to Cedarpoint Ventures III, and what is left after it?",  # uc-002
     {"Unfunded commitment after call": "called_to_date", "Net worth": "net_worth"}, ["10000000", "6000000", "7250000", "2750000"]),
    ("A Cedarpoint call notice just came in by email. Which fund, how much and by when?",  # uc-001
     {"Capital call payment status": "call_payment_status", "Call notice fields": "call_notice_fields", "Net worth": "net_worth"}, ["1250000", "900000", "350000", "4471"]),
])
def test_question_reads_the_recipe_it_means(office, monkeypatch, ask, bound, want):
    from sh_platform.v1 import b10_pack as P, cx_dash as CD
    plane, tables = office
    monkeypatch.setattr(P, "latest_approved", lambda *a: {"target": {"gold": [{"name": t["name"], "purpose": t["purpose"]} for t in tables]}})
    monkeypatch.setattr(CD, "gold_tables", lambda *a: tables)
    kpis = [{"name": n, "built_from": r} for n, r in bound.items()]
    got = F.recipe_rows(plane, ask, "prj-1", {}, kpis, floor=2 if not C.CALLS.search(ask) else 1)
    said = got["answer"].replace(",", "")
    for w in want:
        assert w in said, (w, got["answer"][:1500])
    assert "net worth" not in said.lower()


def test_tied_name_is_bound_by_the_question():
    q = ("After Cedarpoint's call came in I want to see where we stand on pacing. For every private fund, what we committed, what has been called "
         "including the call that just arrived, and what is still unfunded, and the total across all funds.")
    kpis = [{"name": "Unfunded commitments", "definition": "Opening unfunded + approved commitment changes + recallable adjustments - reductions from funded calls."}]
    R.bind(None, None, kpis, q)
    assert kpis[0]["built_from"] == "commitments_by_fund"


@pytest.mark.parametrize("say, rid", [
    ("A Cedarpoint call notice just came in by email. Tell me which fund it is for, how much, by when.", "call_notice_fields"),
    ("The notice says to wire to an account ending 4471 but we have always paid 2209.", "bank_details_changed"),
    ("Tell me whether it fits what we committed to Cedarpoint Ventures III and what is left after it.", "called_to_date"),
])
def test_question_suggests_the_recipe(say, rid):
    kpis = [{"name": "Weather", "definition": "Rain in mm."}]
    R.bind(None, None, kpis, say)
    assert rid in {k.get("built_from") for k in kpis}


# ---- the answer reads like a colleague: one sentence with the key numbers, the rows behind it ---------------------------------------------------

def _persona():
    import importlib.util
    path = Path(__file__).resolve().parents[2] / "docs" / "test" / "uc-live" / "uc6-scripts" / "v3_persona.py"
    spec = importlib.util.spec_from_file_location("v3_persona_w6", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CARDS = [  # (card, question, North's figures and the recipes they are bound to, the numbers the sentence itself must hold)
    ("uc-001-noticelog", "A Cedarpoint call notice just came in by email. Which fund, how much and by when?",
     {"Capital call payment status": "call_payment_status", "Call notice fields": "call_notice_fields", "Net worth": "net_worth"}, ["1,250,000", "900,000", "350,000", "4471"]),
    ("uc-002-callrecord", "Does call 7 fit what we committed to Cedarpoint Ventures III, and what is left after it?",
     {"Unfunded commitment after call": "called_to_date", "Net worth": "net_worth"}, ["10,000,000", "6,000,000", "7,250,000", "2,750,000"]),
    ("uc-004-callcheck", "Can Holdings pay the Cedarpoint call on the 23rd?", {"Shortfall": "cash_after_calls", "SGD conversion amount": "fx_required"},
     ["1,230,000", "1,600,000", "1,194,029.85", "1,250,000", "250,000", "270,000", "361,800", "1.34"]),
    ("uc-005-benefcheck", "Cedarpoint now says to wire to an account ending 4471. Is that really them?",
     {"Account number match": "call_payment_status", "Payment hold flag": "payment_batch", "Bank details changed": "bank_details_changed"}, ["2209", "4471"]),
    ("uc-006-fxneed", "We hold SGD and need USD for the call. How much do we convert, and did the bank trade at the right rate?",
     {"SGD to convert": "fx_required", "Bank rate check": "fx_rate_check"}, ["361,800", "1.34"]),
    ("uc-007-pacing", "What's our unfunded commitment across all funds?", {"Unfunded commitments": "commitments_by_fund", "Net worth": "net_worth"}, ["14,600,000"]),
    ("uc-008-payrun", "Which payments to release", {"Payments ready": "payment_batch", "Net worth": "net_worth"}, ["5,400", "16,234.50", "6,180", "1,030", "1,250,000"]),
]


@pytest.mark.parametrize("card, ask, bound, key", CARDS, ids=[c[0] for c in CARDS])
def test_answer_is_one_sentence_with_the_key_numbers(office, monkeypatch, card, ask, bound, key):
    import re
    from sh_platform.v1 import b10_pack as P, cx_dash as CD
    plane, tables = office
    monkeypatch.setattr(P, "latest_approved", lambda *a: {"target": {"gold": [{"name": t["name"], "purpose": t["purpose"]} for t in tables]}})
    monkeypatch.setattr(CD, "gold_tables", lambda *a: tables)
    kpis = [{"name": n, "built_from": r} for n, r in bound.items()]
    got = F.recipe_rows(plane, ask, "prj-1", {}, kpis, floor=2 if not C.CALLS.search(ask) else 1)
    said = got["answer"]
    print(card, len(said.split()), said)
    for k in key:
        assert k in said, (k, said)
    assert len(said.split()) <= 42, said
    assert not re.search(r"run|gold_|_id|[0-9a-f]{8}-[0-9a-f]{4}", said, re.I), said
    assert got["rows"] and all(r["label"] and r["value"] for r in got["rows"])
    assert got["kpi"]  # "Where this number comes from" links the figure record the answer was read through
    vp = _persona()  # the persona check reads the sentence and the figures behind it: every number of the card's check is there
    _, build = vp.load_uc(card)
    assert vp.missing(vp.said(got), build["check"]["expect"]) == []


def test_say_formats_like_a_person():
    r = {"answer": [{"if": "shortfall", "say": "{entity} is short {currency} {shortfall} due {due}"}, {"once": True, "say": "{n} rows, {sum:cash} in all"}]}
    from datetime import date
    from decimal import Decimal
    rows = [{"entity": "A", "currency": "USD", "shortfall": Decimal("270000.00"), "due": date(2026, 10, 23), "cash": Decimal("16234.50")},
            {"entity": "B", "currency": "USD", "shortfall": Decimal("0.00"), "due": None, "cash": Decimal("1.00")}]
    assert F.say(r, rows) == "A is short USD 270,000 due 23 Oct 2026. 2 rows, 16,235.50 in all."
    assert F.say({"answer": [{"say": "{rate}"}]}, [{"rate": Decimal("1.3400000000")}]) == "1.34."
    assert F.say({}, rows) is None
