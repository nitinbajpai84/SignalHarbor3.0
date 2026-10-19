"""Live run 7, operations group: eleven check questions of run 7 (D:/Temp/sh3-live/r7/<id>.json) answered from the recipe that computes them.

Root causes, one per case (each replayed against a copy of its r7 office with verified_answer before it was pinned here):
- uc-015: the question names cash ("and do we have the cash") and the allowances fit it better, so the answer said the allowances alone; a figure whose
  recipe the question's own words name is now said with the better fit (v3_figures.recipe_rows `also`).
- uc-072: "whether the family needs to raise cash" and "cash month by month" named no recipe, so the twelve month forecast was never built; they are
  the forecast's names now (it is added to the brief and answers the question).
- uc-078: the redemption recipe reads range(0, 37), a table function sqlglot lists as a table with no name, and the plan check refused it ("reads , which
  is not in the data model"); a nameless table is no table read (b6_plan).
- uc-085: "Whether to approve more grants this year" took the grant request check (grants + approve); it is the budget recipe's name now.
- uc-094: the policy's Head of Finance is found in the users table only, where the demo office calls Daniel Foo the CIO; the latest payroll title counts too.
- uc-095, uc-096: seven of the eight SOP files never reached the build: "Procedures register" and "Procedure logs" share no word with the reader's kind
  "sops"; the kind serves a source named in full (v3_pack_readers.KIND_WORDS). uc-095's ages were a day long: a file stamped late on the office's day
  (23:00 UTC, wh.now) is the next day in the server's zone, so the as-at is read as a UTC day. uc-096's recipe had no answer lines (one row read plainly).
- uc-097: the person's "ask the owner for a new one" with "bank" and "account" added the payee-bank-change recipe, whose figure took the question;
  "new" is no longer a word of that recipe.
- uc-052, uc-062: no answer lines, so the answer was a plain read of a 0/1 flag ("USD 0") or of the marks alone; each now says its key figures.
- uc-053: the 90-day window started a day late for the same as-at cause as uc-095, in watch_flags (invest.yaml).
  The as-at is read as a UTC day (cast(received_at at time zone 'UTC' as date)), so the window starts on the office's day.

Expected values come from tests/v1/fixtures/office6m/answer_keys.yaml and the builds' check.expect (packs/family_office/1/builds), never typed here.
The office tests load the six-month office (tools/score50.load), build the bound recipes' tables, and ask through verified_answer; the pack and the
gold-table list are stand-ins (no build runs here). Synthetic data only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

from sh_platform.v1 import v3_figures as F
from sh_platform.v1 import v3_recipes as R

REPO = Path(__file__).resolve().parents[2]
KEYS = yaml.safe_load((REPO / "tests" / "v1" / "fixtures" / "office6m" / "answer_keys.yaml").read_text(encoding="utf-8"))["keys"]
BUILDS = {b["id"]: b for p in sorted((REPO / "packs" / "family_office" / "1" / "builds").glob("*.yaml"))
          for r in yaml.safe_load(p.read_text(encoding="utf-8"))["roles"] for b in r["builds"]}

# The run 7 briefs as North wrote them: the goal line, the person's words, the check question and the figures (a figure the binding itself added, named
# after its recipe, is left out: the binding adds it back).
R7 = json.loads(r"""{
    "uc-015-allowances": {"goal": "At the start of each month I need to know what we owe each of the family: Lin, Maya, Ethan and Wen. I approve, Daniel pays.", "said": "At the start of each month I need to know what we owe each of the family: Lin, Maya, Ethan and Wen. Show me what is scheduled, what has actually been paid, and whether the Trust has the cash for it. I approve, Daniel pays. use the usual practice", "ask": "What do we owe each family member this month, and do we have the cash?", "figs": [{"name": "Scheduled amount", "definition": "Total amount that each family member is scheduled to receive for the month."}, {"name": "Paid amount", "definition": "Total amount actually paid to each family member during the month."}, {"name": "Cash availability", "definition": "Cash on hand after accounting for scheduled payments and known obligations."}]},
    "uc-072-cashfc": {"goal": "At each quarter start I want cash month by month to 30 Sep 2027, with the capital calls at the signed monthly average from the month after the noticed call, the scheduled payments left out when held, the expected distributions and the income, against the signed floor.", "said": "At each quarter start I want cash month by month to 30 Sep 2027, with the capital calls at the signed monthly average from the month after the noticed call, the scheduled payments left out when held, the expected distributions and the income, against the signed floor. Tell me whether the family needs to raise cash, how much and from which month.", "ask": "Whether the family needs to raise cash", "figs": [{"name": "Minimum six\u2011month funding headroom", "definition": "Opening cash + approved inflows \u2013 known obligations \u2013 scenario\u2011only calls \u2013 proposed funding \u2013 reserve; take the minimum across the six closing\u2011month headrooms."}, {"name": "Reported\u2011value evidence coverage", "definition": "Sum of non\u2011negative asset values supported by approved source evidence divided by sum of all non\u2011negative included asset values."}, {"name": "Known obligations due", "definition": "Sum of current, unpaid approved obligations within each monthly bucket after notice supersession, converted using approved FX rates."}, {"name": "Unfunded commitments", "definition": "Opening unfunded + approved commitment changes + recallable adjustments \u2013 reductions from funded calls. Fees are excluded."}]},
    "uc-078-redemption": {"goal": "The CIO wants to reduce the Kestrel hedge funds.", "said": "The CIO wants to reduce the Kestrel hedge funds. From their redemption terms and latest statements, tell me for each fund the first dealing date we can still reach given the lock-up, the last day to send the notice, how many days that leaves, the day the cash comes and how much, and what is held back until the audit. I draft the notice; the CIO signs it.", "ask": "By when must we send the redemption notice and when do we get the cash?", "figs": [{"name": "First dealing date", "definition": "Earliest date a redemption can be dealt given the lock\u2011up"}, {"name": "Notice deadline", "definition": "Latest date to send the redemption notice"}, {"name": "Days left to notice", "definition": "Days between today and the notice deadline"}, {"name": "Cash receipt date", "definition": "Date the cash from the redemption will be received"}, {"name": "Cash amount", "definition": "Amount of cash to be received on the cash receipt date"}, {"name": "Audit hold\u2011back amount", "definition": "Cash retained until audit completion"}]},
    "uc-085-grants": {"goal": "We set a grants budget for the year.", "said": "We set a grants budget for the year. Show me what is paid and pledged against it, what is left, and whether the paid grants agree with the bank.", "ask": "Whether to approve more grants this year", "figs": [{"name": "Paid grants total", "definition": "Total amount of grants that have been paid during the year"}, {"name": "Pledged grants total", "definition": "Total amount of grants that have been pledged for the year"}, {"name": "Remaining budget", "definition": "Grants budget minus paid and pledged amounts"}, {"name": "Paid\u2011grant\u2011bank reconciliation", "definition": "Whether the paid grants total matches the amount recorded by the bank"}]},
    "uc-094-onbbank": {"goal": "No account opens until its signatories meet our signing policy.", "said": "No account opens until its signatories meet our signing policy. Check the opening form's signatories against the policy and tell me who is missing.", "ask": "Whether the account and its signatories are approved", "figs": []},
    "uc-095-sopreview": {"goal": "Each quarter I check our written procedures.", "said": "Each quarter I check our written procedures. Show me each one with its owner and when it was last reviewed, and which are more than a year old, so I can assign the reviews. use the usual practice", "ask": "Which procedures to review", "figs": [{"name": "Procedures overdue", "definition": "Count of procedures whose last review date is more than six months ago."}, {"name": "Review effort", "definition": "Total person\u2011hours spent compiling the quarterly review pack."}]},
    "uc-096-automation": {"goal": "Each quarter I rank our written procedures by the time they take and how often they fail. Put every procedure's manual minutes a month, its runs, and the failures of the last six months (at 45 minutes of rework each) side by side, and tell me which to automate next.", "said": "Each quarter I rank our written procedures by the time they take and how often they fail. Put every procedure's manual minutes a month, its runs, and the failures of the last six months (at 45 minutes of rework each) side by side, and tell me which to automate next. use the usual practice", "ask": "Which process to automate", "figs": [{"name": "Manual minutes per month", "definition": "Total logged person\u2011hours spent manually on the procedure each month"}, {"name": "Run count", "definition": "Number of times the procedure is executed in the month"}, {"name": "Failures (rework minutes)", "definition": "Minutes of rework required for failures, assuming 45 minutes per failure"}]},
    "uc-097-kycrefresh": {"goal": "Banks and managers freeze an account when a KYC document lapses.", "said": "Banks and managers freeze an account when a KYC document lapses. Show me every KYC document with its expiry, the ones that expire in the next 90 days and the ones already expired, so I can ask the owner for a new one. use the usual practice", "ask": "Which documents to refresh before the bank or manager freezes the account", "figs": [{"name": "Expired KYC count", "definition": "Number of KYC documents whose expiry date is before today."}, {"name": "KYC expiring in next 90 days", "definition": "Number of KYC documents that will expire within the next 90\u202fdays."}, {"name": "KYC compliance coverage", "definition": "Sum of assets backed by a current (non\u2011expired) KYC document divided by total assets."}]},
    "uc-052-insurance": {"goal": "Our policies renew once a year and the broker's schedule is the list.", "said": "Our policies renew once a year and the broker's schedule is the list. Show me which policies renew in the next 60 days, what each insures and costs, and whether the insurer's renewal notice has come, so I can draft the renewal request for the Principal.", "ask": "Which policies expire in the next 60 days and what is each worth?", "figs": [{"name": "Time\u2011weighted return net of fees", "definition": "Chained monthly return after fees, compared to blended benchmark"}, {"name": "Allocation drift", "definition": "Difference between current asset allocation and policy ranges"}, {"name": "Single\u2011issuer concentration", "definition": "Issuer exposure divided by total included asset value"}, {"name": "Cash drag", "definition": "Cash holding as a proportion of total assets"}]},
    "uc-062-fxlife": {"goal": "Provide a monthly performance pack for the family office", "said": "Show me the FX forwards we have open: when each one settles, what it is worth at today's rate, whether the bank confirmed it as we booked it, and how much USD we deliver. Tell me which ones need settlement cash or a roll. use the usual practice", "ask": "Which forwards need settlement cash or a roll, and what are they worth now?", "figs": [{"name": "Net\u2011worth", "definition": "Total assets minus liabilities, from custodian positions, bank balances and private\u2011fund valuations"}, {"name": "Time\u2011weighted return net of fees", "definition": "Chained monthly return, net of fees, compared to blended benchmark"}, {"name": "Allocation drift", "definition": "Difference between actual asset allocation and policy target ranges"}, {"name": "Single\u2011issuer concentration", "definition": "Issuer exposure divided by total asset value"}, {"name": "FX forward open positions", "definition": "Settlement date, value at today\u2019s rate, bank confirmation status, USD delivery amount"}]},
    "uc-053-watchlist": {"goal": "At each month end, once the statements are logged, I need to know which managers gave us trouble in the last 90 days: statements that came late, statements they restated, statements still missing, and mails telling us someone left or joined the team.", "said": "At each month end, once the statements are logged, I need to know which managers gave us trouble in the last 90 days: statements that came late, statements they restated, statements still missing, and mails telling us someone left or joined the team. Count each per manager, total them, and list the managers with at least one flag. I propose the watch list; the CIO decides. use the usual practice", "ask": "Which managers have given us a late, restated or changed statement this quarter?", "figs": [{"name": "Manager trouble flags", "definition": "Count of late, restated, missing statements and staff\u2011change emails per manager in the last 90 days"}]}
}""")


def _q(ask: str) -> str | None:
    return (R.match({"name": ask}, strict=False) or {}).get("id")


def _bind(c: dict) -> tuple[dict, list]:
    ks = [{"name": f["name"], "definition": f["definition"], "formula": "", "unit": "", "period": "monthly", "owner": "x", "status": "defined"} for f in c["figs"]]
    R.bind(None, None, ks, c["goal"], None, c["said"])
    names = {f["name"] for f in c["figs"]}
    return {k["name"]: k["built_from"] for k in ks if k["name"] in names}, sorted(k["built_from"] for k in ks if k["name"] not in names)


def _expect(uc: str) -> list[str]:
    return BUILDS[uc]["check"]["expect"]


def _missing(got: dict, expect: list[str]) -> list[str]:
    """The live check (docs/test/uc-live/uc6-scripts/v3_persona.py): each value in the sentence or the figures behind it, commas ignored."""
    said = " ".join([str(got.get("answer") or ""), *(f"{r.get('label', '')} {r.get('value', '')}" for r in got.get("rows") or [] if isinstance(r, dict))]).replace(",", "").lower()
    return [e for e in expect if e.replace(",", "").lower() not in said and e.replace(",", "").lower().removesuffix(".00") not in said]


# ---- the check question reads as its recipe; the builds ask what the answer keys hold ---------------------------------------------------------

WANT = {"uc-015-allowances": "cash_by_entity", "uc-072-cashfc": "cash_forecast", "uc-078-redemption": "redemption_dates", "uc-085-grants": "grants_used",
        "uc-094-onbbank": "account_setup", "uc-095-sopreview": "sop_age", "uc-096-automation": "automation_score", "uc-097-kycrefresh": "kyc_expiry",
        "uc-052-insurance": "renewals_due", "uc-062-fxlife": "fx_mtm", "uc-053-watchlist": "watch_flags"}


@pytest.mark.parametrize("uc", sorted(WANT))
def test_r7_the_check_question_is_its_recipe_and_the_build_asks_it(uc):
    assert R7[uc]["ask"] == BUILDS[uc]["check"]["ask"]
    assert _q(R7[uc]["ask"]) == WANT[uc], uc


def test_r7_uc072_raising_cash_month_by_month_adds_the_twelve_month_forecast():
    want, added = _bind(R7["uc-072-cashfc"])
    assert "cash_forecast" in added
    assert R.asks("Tell me whether the family needs to raise cash, how much and from which month.", R.recipe("cash_forecast"))
    assert _q("What is our cash by entity today?") == "cash_by_entity"  # one word "cash" keeps its recipe


def test_r7_uc097_a_new_kyc_document_is_not_a_changed_payee_account():
    want, added = _bind(R7["uc-097-kycrefresh"])
    assert "bank_details_changed" not in added and "bank_details_changed" not in want.values()
    assert want["KYC expiring in next 90 days"] == "kyc_expiry"
    for goal in ("The Cedarpoint call 7 notice says to wire to an account ending 4471 but we have always paid 2209.",  # uc-005 keeps its recipe
                 "The fund changed its bank account for the call."):
        assert R.asks(goal, R.recipe("bank_details_changed")), goal


def test_r7_uc085_more_grants_this_year_is_the_budget_and_paying_a_grant_is_still_the_request_check():
    want, _ = _bind(R7["uc-085-grants"])
    assert set(want.values()) == {"grants_used"}
    ask86 = next(iter(KEYS["uc-086-grantappr"]["questions"]))
    assert _q(ask86) == "grant_check", ask86


def test_r7_uc078_a_table_function_is_no_table_the_plan_check_refuses():
    from sh_platform.v1 import b6_plan as B
    sql = "create table gold_r7_x as with t as (select id from documents) select t.id, g.n from t cross join range(0, 3) as g(n)"
    cols, reads = B._check_sql({"name": "gold_r7_x", "sql": sql, "depends_on": ["documents"]}, {"documents": {"id": "varchar"}}, set())
    assert reads == {"documents"}
    assert "range(0, 37)" in R.recipe("redemption_dates")["sql"]  # the recipe that the check refused in run 7 ("reads , which is not in the data model")


def test_r7_uc095_uc096_the_sop_files_serve_a_source_named_procedures():
    from sh_platform.v1 import v3_pack_readers as PK
    assert PK._kind_serves("sops", ["Procedures register"]) and PK._kind_serves("sops", ["Procedure logs"])
    assert not PK._kind_serves("sops", ["KYC documents", "Grants ledger"])
    assert PK._kind_serves("manager_statements", ["Manager statements"]) and not PK._kind_serves("manager_statements", ["Capital call notices"])


def test_r7_the_new_answer_lines_say_the_figures_of_the_answer_keys():
    k62 = next(iter(KEYS["uc-062-fxlife"]["questions"].values()))["expected"]
    rows = [{"trade": f["id"], "value_date": f["value_date"], "days_to_value": f["days_to_value"], "sell_amount": f["sell_usd"], "buy_currency": "SGD",
             "buy_amount": f["buy_sgd"], "mtm_usd": f["mtm_usd"], "confirmation_status": f["confirmation_status"], "usd_to_deliver": f["sell_usd"]} for f in k62["forwards"]]
    said = F.say(R.recipe("fx_mtm"), rows, money={"sell_amount", "buy_amount", "mtm_usd", "usd_to_deliver"})
    assert not _missing({"answer": said}, _expect("uc-062-fxlife")), said
    k52 = next(iter(KEYS["uc-052-insurance"]["questions"].values()))["expected"]
    rows = [{"policy": p["policy"], "policy_name": p["name"], "next_renewal_date": p["next_renewal"], "days_left": p["days_left"], "currency": p["currency"],
             "sum_insured": p["sum_insured"], "premium": p["premium"], "due_in_60_days": int(p in k52["expiring_in_60_days"])} for p in k52["all_policies"]]
    said = F.say(R.recipe("renewals_due"), rows, money={"sum_insured", "premium"})
    assert all(p["policy"] in said for p in k52["expiring_in_60_days"]) and "USD 0" not in said, said
    k96 = next(iter(KEYS["uc-096-automation"]["questions"].values()))["expected"]
    rows = [{**x, "automate_next": i == 0} for i, x in enumerate(k96["ranking"])]
    said = F.say(R.recipe("automation_score"), rows, money={"score", "manual_minutes_per_month"})
    assert said.startswith(f"Automate {k96['ranking'][0]['sop']} next") and not _missing({"answer": said}, _expect("uc-096-automation")), said


# ---- the six-month office: each check question asked through verified_answer -------------------------------------------------------------------
# The live server runs in the machine's zone (UTC+7 here) and stamps a file received in a build at 23:00 UTC on the office's day (wh.now): the tables
# are built in that zone with one such file on record, as run 7 had them.

BOUND = {  # each case's figures and the recipe each is bound to in run 7 (with the fixes: uc-072's forecast added, uc-097's payee figure not added)
    "uc-015-allowances": {"Scheduled amount": "allowance_due", "Paid amount": "allowance_due", "Cash availability": "cash_by_entity",
                          "Trust distribution room per beneficiary": "trust_distribution_room"},
    "uc-072-cashfc": {"Known obligations due": "allowance_due", "Unfunded commitments": "commitments_by_fund", "Distributions expected in the next year": "expected_distributions",
                      "Twelve month cash forecast": "cash_forecast"},
    "uc-078-redemption": {"First dealing date": "redemption_dates", "Notice deadline": "redemption_dates", "Cash receipt date": "redemption_dates",
                          "Audit hold\u2011back amount": "redemption_dates"},
    "uc-085-grants": {"Paid grants total": "grants_used", "Pledged grants total": "grants_used", "Remaining budget": "grants_used",
                      "Paid\u2011grant\u2011bank reconciliation": "grants_used", "Grant request against budget, charity age and cash": "grant_check"},
    "uc-094-onbbank": {"Account set-up signatories against the signing policy": "account_setup"},
    "uc-095-sopreview": {"Procedures overdue": "sop_age"},
    "uc-096-automation": {"Manual minutes per month": "automation_score", "Failures (rework minutes)": "automation_score"},
    "uc-097-kycrefresh": {"Expired KYC count": "kyc_expiry", "KYC expiring in next 90 days": "kyc_expiry", "KYC compliance coverage": "kyc_expiry"},
    "uc-052-insurance": {"Insurance policies expiring": "renewals_due"},
    "uc-062-fxlife": {"FX forward open positions": "fx_mtm"},
    "uc-053-watchlist": {"Manager watchlist flags": "watch_flags", "Missing statements": "missing_statements"},
}


@pytest.fixture(scope="module")
def office(tmp_path_factory):
    sys.path.insert(0, str(REPO / "tools"))
    import score50
    plane, con, _ = score50.load(tmp_path_factory.mktemp("r7ops"))
    con.execute("set TimeZone = 'Asia/Bangkok'")
    con.execute("insert into documents select * replace (uuid() as id, 'other' as document_type, 'handover_email.txt' as original_filename, "
                "timestamptz '2026-10-13 23:07:53+00' as received_at, timestamptz '2026-10-13 23:07:53+00' as recorded_at) from documents limit 1")
    # the demo office's users: Daniel Foo is the CIO there, nobody the Head of Finance (the payroll and the access register say Head of Finance)
    con.execute("update users set business_role = 'Chief Investment Officer' where display_name = 'Daniel Foo'")
    con.execute("update users set business_role = 'Finance' where business_role = 'Head of Finance'")
    tables = {}
    for rid in sorted({r for b in BOUND.values() for r in b.values()}):
        r, name = R.recipe(rid), f"gold_r7_{rid}"
        con.execute(R.render(r, name, R.dims_for(r, {})))
        cols = con.execute("select column_name, data_type from information_schema.columns where table_name = ? order by ordinal_position", [name]).fetchall()
        tables[rid] = {"name": name, "columns": [{"name": c, "type": t} for c, t in cols], "rows": con.execute(f"select count(*) from {name}").fetchone()[0],
                       "purpose": f"{R.MARK}{rid}: {r['label']}"}
    con.close()
    return plane, tables


def _ask(office, monkeypatch, uc: str) -> dict:
    from sh_platform.profile.view import Viewer
    from sh_platform.v1 import b10_pack as P, cx_dash as CD, talk, v3_consume as C
    plane, tables = office
    figs = BOUND[uc]
    mine = [tables[r] for r in dict.fromkeys(figs.values())]
    monkeypatch.setattr(P, "latest_approved", lambda *a: {"target": {"gold": [{"name": t["name"], "purpose": t["purpose"],
                                                                                "kpis": [n for n, r in figs.items() if tables[r] is t]} for t in mine]}})
    monkeypatch.setattr(CD, "gold_tables", lambda *a: mine)
    monkeypatch.setattr(F, "kpis_of", lambda *a: [{"name": n, "built_from": r} for n, r in figs.items()])
    monkeypatch.setattr(talk, "reachable", lambda *a: ([{"id": "prj-r7"}], []))
    th = {"id": "t-r7", "pid": "prj-r7", "iid": "ini-r7"}
    return C.verified_answer(plane, Viewer("Daniel Foo", frozenset({"company_admin"}), False, None), BUILDS[uc]["check"]["ask"], None, th) or {}


@pytest.mark.parametrize("uc", [uc for uc in sorted(BOUND) if uc != "uc-053-watchlist"])
def test_r7_the_check_question_says_every_value_of_the_build(office, monkeypatch, uc):
    got = _ask(office, monkeypatch, uc)
    assert not _missing(got, _expect(uc)), (uc, got.get("answer"))


def test_r7_uc015_the_allowances_are_said_with_the_trusts_cash(office, monkeypatch):
    got = _ask(office, monkeypatch, "uc-015-allowances")
    cash = next(iter(KEYS["uc-015-allowances"]["questions"].values()))["expected"]["trust_usd_cash"]
    assert "Owed for" in got["answer"] and f"Evergreen Family Trust USD {cash:,.2f}" in got["answer"], got["answer"]  # the allowances and the Trust's cash, both said


def test_r7_uc095_the_age_of_a_procedure_runs_to_the_offices_day_not_the_next(office, monkeypatch):
    k = next(iter(KEYS["uc-095-sopreview"]["questions"].values()))["expected"]
    got = _ask(office, monkeypatch, "uc-095-sopreview")
    for s in k["sops"]:
        if s["due"]:
            assert f"{s['sop']} ({s['owner']}), last reviewed" in got["answer"] and f"{s['age_days']} days ago" in got["answer"], got["answer"]


def test_r7_uc053_the_window_starts_90_days_before_the_offices_day(office, monkeypatch):
    got = _ask(office, monkeypatch, "uc-053-watchlist")
    assert not _missing(got, _expect("uc-053-watchlist")), got.get("answer")
