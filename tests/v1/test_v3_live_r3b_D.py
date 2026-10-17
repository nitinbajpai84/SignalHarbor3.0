"""Live run 3, part B, fixer D (docs/v3/LIVE-R3B-ANALYSIS.md): the answer logic, the readers and intake, and the stuck causes.

Each case is the office6m files (tests/v1/fixtures/office6m), loaded the way the case needs: the whole office through the real readers (tools/score50.py's
`load`), or a flat drop read batch by batch the way Harbor's intake reads a live dropbox (test_w3_intake.py's `flat_thread`). The figures are North's own
names and definitions from the run 3 threads, bound to the recipes those threads bound them to; the question is the case's live check ask, answered
through figures._answer; the numbers are the persona check's (v3_persona.py), read from the sentence and the figures behind it. Synthetic data only."""
from __future__ import annotations

import importlib.util
import json
import re
import threading
import time
from datetime import date
from pathlib import Path

import pytest

from sh_platform.v1 import v3_figures as F
from sh_platform.v1 import v3_harbor as H
from sh_platform.v1 import v3_pack_readers as PK
from sh_platform.v1 import v3_recipes as R
from sh_platform.v1 import wh

REPO = Path(__file__).resolve().parents[2]
OFFICE = REPO / "tests" / "v1" / "fixtures" / "office6m"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


W2 = _load("w2_loader_tests_r3b_d", Path(__file__).with_name("test_w2_loader.py"))
W3 = _load("w3_intake_tests_r3b_d", Path(__file__).with_name("test_w3_intake.py"))
VP = _load("v3_persona_r3b_d", REPO / "docs" / "test" / "uc-live" / "uc6-scripts" / "v3_persona.py")


def _missing(card: str, got: dict) -> list[str]:
    """The persona check of the card: the expected values not in the sentence or the figures behind it."""
    _, build = VP.load_uc(card)
    return VP.missing(VP.said(got), build["check"]["expect"])


# ---- the answer logic: the whole office, the recipes' ready tables, the live figures and question ----------------------------------------------

CASES = [  # card, the live ask, North's figures (name, definition, recipe or "" when the thread left it unbound)
    ("uc-073-runway", "Whether spending is sustainable",  # was the "Rules-only reply": the question named no figure and shared one word with cash_runway
     [("Cash coverage (cash only)", "Months of cash runway based on current cash balance divided by average monthly spend.", "cash_runway"),
      ("Cash coverage (liquid book)", "Months of runway using cash plus liquid book assets.", "")]),
    ("uc-055-corpact", "Which actions need a decision or a booking?",  # was 10 of 12 rows: "booking" named the bucket "book", so the tender offer was cut
     [("Timeliness of election decisions", "Proportion of elections acted on before deadline.", ""),
      ("Corporate actions in the next 14 days", "One row for each corporate action as it stands.", "actions_next_14d")]),
    ("uc-065-realassets", "What real assets we own, their values and who holds them?",  # was RA-04 only: the register was cut to its latest appraisal date
     [("Reported‑value evidence coverage", "Sum of asset values with approved appraisal evidence / total asset value", ""),
      ("Real assets register", "One row for each real asset: its latest appraisal on or before the as-of date.", "real_asset_value")]),
    ("uc-066-propreval", "Whether to order a new appraisal?",  # was RA-04 only (125 days)
     [("Days since last appraisal", "Current date minus the last appraisal date for each real asset", "appraisal_age"),
      ("Real assets register", "One row per real asset with latest appraisal and USD value", "real_asset_value")]),
    ("uc-080-vintage", "Are our private commitments too bunched in one year?",  # was names and amounts only, the year said "2,021"
     [("Private fund commitments by vintage year", "Sum of commitment amounts for each vintage year, expressed as a share of total commitments", "vintage_split")]),
    ("uc-100-famaccess", "What each family member may see",  # was "pairs 1, one of 4 rows": "family" named Evergreen Family Trust
     [("Over‑access count", "Number of family members who have report access beyond what the policy permits", "member_access")]),
    ("uc-083-taxcal", "Which filings and payments are due and who prepares them",  # was "items 1, one of 3 rows": "filings and payments" kept 3 of 6, and TX-01 sat in id
     [("Filing due date", "Date a filing must be submitted for each entity", "tax_due"), ("Payment due date", "Date a tax payment must be made for each entity", ""),
      ("Overdue filing count", "Number of filings past due that have not been filed", "tax_due"),
      ("Overdue payment amount", "Total amount of tax payments past due and not yet made", "")]),
    ("uc-056-custrecon", "Which holdings differ between the custodian and the administrator, and why?",
     [("Quantity discrepancy value", "Monetary value of the difference between custodian and administrator quantities for a holding", "position_break")]),
    ("uc-071-expdist", "How much money should we expect back from the funds over the next year?",
     [("Projected fund payout", "Sum of the quarterly payout amounts calculated from the latest fund statement value multiplied by the manager’s distribution outlook rates.",
       "expected_distributions"), ("Old‑statement flag count", "Number of funds where the latest statement date is older than the standard month‑end cut‑off.", "")]),
    ("uc-078-redemption", "By when must we send the redemption notice and when do we get the cash?",
     [("First dealing date reachable", "Earliest date you can still trade given the lock‑up (suggested)", "redemption_dates"),
      ("Last notice date", "Final day to send redemption notice (suggested)", ""), ("Cash amount to be received", "Redemption cash expected from the fund (suggested)", ""),
      ("Audit hold‑back amount", "Cash retained until audit clearance (suggested)", "")]),
]


@pytest.fixture(scope="module")
def office(tmp_path_factory):
    import sys
    sys.path.insert(0, str(REPO / "tools"))
    import score50
    plane, con, _ = score50.load(tmp_path_factory.mktemp("r3b_d"))
    tables = []
    for rid in sorted({rid for _, _, figs in CASES for *_, rid in figs if rid}):
        r = R.recipe(rid)
        name = f"gold_r3b_{rid}"
        con.execute(R.render(r, name, R.dims_for(r, {})))
        cols = con.execute("select column_name, data_type from information_schema.columns where table_name = ? order by ordinal_position", [name]).fetchall()
        tables.append({"name": name, "columns": [{"name": c, "type": t} for c, t in cols], "rows": con.execute(f"select count(*) from {name}").fetchone()[0],
                       "purpose": f"{R.MARK}{rid}: {r['label']}", "kpis": []})
    con.close()
    return plane, tables


def _answer(monkeypatch, office, card, ask, figs):
    from sh_platform.v1 import b10_pack as P, cx_dash as CD, talk
    plane, tables = office
    kpis = [{"name": n, "definition": d, "built_from": rid} for n, d, rid in figs]
    monkeypatch.setattr(F, "kpis_of", lambda plane_, iid: [dict(k) for k in kpis])
    monkeypatch.setattr(P, "latest_approved", lambda *a, **k: {"target": {"gold": [{"name": t["name"], "purpose": t["purpose"], "kpis": t["kpis"]} for t in tables]}})
    monkeypatch.setattr(CD, "gold_tables", lambda *a, **k: tables)
    monkeypatch.setattr(talk, "reachable", lambda *a, **k: ([{"id": "prj-1"}], []))
    th = {"id": f"t-{card}", "pid": "prj-1", "iid": f"ini-{card}", "figures": [], "steps": []}
    return F._answer(plane, None, ask, "prj-1", th)


@pytest.mark.parametrize("card, ask, figs", CASES, ids=[c[0] for c in CASES])
def test_live_question_is_answered_from_the_bound_tables_rows(office, monkeypatch, card, ask, figs):
    got = _answer(monkeypatch, office, card, ask, figs)
    assert got and got["answer"] and not got["answer"].startswith("Not available yet"), (card, got)
    assert not re.search(r"\bone of \d+ rows|\band \d+ more\b", got["answer"]), got["answer"]  # a set is said whole, never "one of N rows" or "and N more"
    assert _missing(card, got) == [], (_missing(card, got), got["answer"][:1500])


def test_one_figure_repeated_on_every_row_is_said_once_never_added_up():
    rows = [{"category": c, "months_of_cash": F.Decimal("25.23")} for c in ("Staff", "Grants", "Premises")]
    said = F._plain_sentence("Cash coverage", {"measure": "months_of_cash"}, rows, lambda x: x["category"], {}, {"months_of_cash"})
    assert said == "Cash coverage: months of cash 25.23." and "75.69" not in said
    rows[0]["months_of_cash"] = F.Decimal("3")
    assert F._plain_sentence("Cash coverage", {"measure": "months_of_cash"}, rows, lambda x: x["category"], {}, set()) == \
        "Cash coverage, months of cash: Staff 3; Grants 25.23; Premises 25.23."


def test_uc080_a_year_is_said_as_a_year():
    assert F._said(2021, {}, col="vintage_year") == "2021" and F._said(F.Decimal("2021"), {}, col="year") == "2021"
    assert F._said(2021, {}) == "2,021"  # an amount is still an amount


# ---- readers and intake: a flat drop, read in batches the way a live dropbox is ------------------------------------------------------------

def _drop(plane, rels: list[str], thread: str = "t-w3") -> None:
    """More office files arrive in the drop folder for the thread (a later batch)."""
    reg = json.loads(H._fp(plane).read_text(encoding="utf-8"))
    for rel in rels:
        H.drop(plane, Path(rel).name, (OFFICE / rel).read_bytes())
        reg.append({"name": Path(rel).name, "arrived_at": "2026-10-13T09:00:00Z", "status": "recognised", "source": "office files", "thread": thread})
    H._fp(plane).write_text(json.dumps(reg), encoding="utf-8")


def _read(x) -> tuple[int, list]:
    PK.intake(x)
    return PK.load(x)


DESK_OCT = [f"2026-10/trading_export/trading_export_202610{d}.csv" for d in ("01", "02", "05", "06", "07")]


def test_uc8_the_administrators_october_trades_are_read_and_the_breaks_found(tmp_path):
    """"How much does the FX forward confirmation differ from our record, and which October trades does the administrator not match?" Run 3 said every
    October trade was "awaiting administrator file": a flat drop staged administrator_trades_2026-10.csv a month on (November), after the clock."""
    assert PK.folder_month("administrator_trades_2026-10.csv", "administrator_trades", date(2026, 10, 13)) == "2026-10"
    assert PK.folder_month("administrator_trades_2026-09.csv", "administrator_trades", date(2026, 10, 13)) == "2026-10"  # still the month after
    plane, x = W3.flat_thread(tmp_path, [*DESK_OCT, "2026-10/administrator_trades/administrator_trades_2026-10.csv"])
    n, aside = _read(x)
    assert (n, aside) == (6, [])
    o = W2.Loaded(plane, None)
    rows = {r["trade"]: r for r in o.run("trade_breaks")}
    assert (rows["T-20261002-003"]["break_kind"], float(rows["T-20261002-003"]["difference_amount"])) == ("quantity differs", 75870)
    assert (rows["T-20261006-005"]["break_kind"], float(rows["T-20261006-005"]["difference_amount"])) == ("missing at administrator", 592000)
    said = F.say(R.recipe("trade_breaks"), list(rows.values()))
    assert "75,870" in said and "592,000" in said
    o.con.close()


def test_uc058_desk_trades_and_their_settlement_read_in_two_batches_are_one_trade_each(tmp_path):
    """"Which trades failed to settle and whom do I chase?" Run 3: the desk export and the custodian's lines came in different batches, so every trade was
    written twice (executed by the desk, settled by the custodian) and 23 trades read as unsettled."""
    plane, x = W3.flat_thread(tmp_path, DESK_OCT)
    assert _read(x)[1] == []
    _drop(plane, ["2026-10/custodian_transactions/transactions_2026-10_mtd.csv", "2026-10/settlement_status/settlement_report_2026-10-13.csv",
                  "2026-10/custodian_positions/positions_20261002.csv", "2026-10/custodian_positions/positions_20261007.csv"])  # the price of a trade with no cash
    assert _read(x)[1] == []
    o = W2.Loaded(plane, None)
    live = o.rows("select external_trade_id, status from transactions as t where t.transaction_type in ('buy', 'sell') "
                  "and not exists (select 1 from transactions as x where x.supersedes_transaction_id = t.id)")
    ids = [r["external_trade_id"] for r in live]
    assert len(ids) == len(set(ids)), sorted(ids)  # one row per trade that counts
    assert {r["status"] for r in live if r["external_trade_id"] == "T-20261006-005"} == {"settled"}
    unsettled = o.run("unsettled_trades")
    assert {r["trade"] for r in unsettled} == {"BR2-20261002-001", "BR2-20261007-002"}, [(r["trade"], r["status"]) for r in unsettled]
    said = F.say(R.recipe("unsettled_trades"), unsettled)
    for k in ("BR2-20261002-001", "281,150", "Synthetic Broker Two"):
        assert k in said, (k, said)
    before = o.one("select count(*) from transactions")
    assert PK.load(x)[1] == [] and o.one("select count(*) from transactions") == before  # the same files again: nothing written twice
    o.con.close()


def test_uc060_a_notice_and_a_bank_statement_with_no_name_to_place_them_are_inbox_files(tmp_path):
    """"Where does each unrecognised file belong, or should I refuse it?" Run 3: scan_0412.pdf (a copy of a distribution notice) and account_extract.xlsx
    (a bank statement) went to the notices and bank readers, which take the fund and the month from the name, and failed with a TypeError."""
    inbox = ["2026-10/inbox/scan_0412.pdf", "2026-10/inbox/account_extract.xlsx"]
    plane, x = W3.flat_thread(tmp_path, inbox)
    assert [PK.recognise(plane, Path(r).name) for r in inbox] == [("inbox", "scan_0412.pdf"), ("inbox", "account_extract.xlsx")]
    assert PK.recognise(plane, "EG_security_master_20261008.xlsx")[0] == "reference"  # a file whose name its reader needs nothing from is as before
    n, aside = _read(x)
    assert (n, aside) == (2, [])
    o = W2.Loaded(plane, None)
    rows = {r["file"]: r for r in o.run("unrecognised_files")}
    assert (rows["scan_0412.pdf"]["belongs_in"], rows["account_extract.xlsx"]["belongs_in"]) == ("notices", "bank_statements")
    assert o.one("select count(*) from cash_movements") == 0  # the copy of the notice is not a second distribution
    o.con.close()


def test_uc052_the_insurance_schedule_is_read_from_a_flat_name_and_holds_the_renewals(office):
    """"Which policies expire in the next 60 days and what is each worth?" The schedule reader works (the stuck cause was the plan: Span read 0 systems,
    "The plan has no tables."). The flat name is recognised and the renewals are on record."""
    p = OFFICE / "2026-10/insurance_schedule/insurance_schedule_2026-10-01.pdf"
    assert PK.kind_of(p.name, p.read_bytes()) == ("insurance_schedule", p.name)
    plane, _ = office
    with wh.connect(plane) as con:
        con.execute(R.render(R.recipe("renewals_due"), "t_r3b_renewals", R.dims_for(R.recipe("renewals_due"), {})))
        due = sorted(r[0] for r in con.execute("select policy from t_r3b_renewals where due_in_60_days = 1").fetchall())
    want = W2.KEYS["uc-052-insurance"]["questions"]
    assert due == sorted(p["policy"] for p in next(iter(want.values()))["expected"]["expiring_in_60_days"])


# ---- stuck causes --------------------------------------------------------------------------------------------------------------------------

UC094_SQL = ("create table gold_no_account_opens_until_its_sig_signatory_metrics as select organization_id, date_trunc('month', opened_on) as month, "
             "avg(signatory_compliance) * 100 as signatory_compliance_rate, sum(missing_signatory_count) as missing_signatory_count from bank_accounts "
             "where opened_on is not null group by organization_id, date_trunc('month', opened_on);")  # the live design, word for word


def test_uc094_an_avg_over_a_yes_no_column_is_built():
    import duckdb
    con = duckdb.connect()
    con.execute("create table bank_accounts (organization_id varchar, opened_on date, signatory_compliance boolean, missing_signatory_count integer)")
    con.execute("insert into bank_accounts values ('o', date '2026-10-02', true, 0), ('o', date '2026-10-05', false, 2)")
    with pytest.raises(duckdb.BinderException, match=r"avg\(BOOLEAN\)"):
        con.execute(UC094_SQL)
    con.execute(F.avg_numbers(UC094_SQL))
    assert con.execute("select signatory_compliance_rate, missing_signatory_count from gold_no_account_opens_until_its_sig_signatory_metrics").fetchall() == [(50.0, 2)]
    plain = "create table t as select avg(x) as a from s"
    assert F.avg_numbers("create table t as select avg(cast(x as double)) as a from s") == "create table t as select avg(cast(x as double)) as a from s"
    assert "CAST(x AS DOUBLE)" in F.avg_numbers(plain) and F.avg_numbers("not sql at all (") == "not sql at all ("


def test_uc043_a_slow_file_judgement_never_holds_a_save(tmp_path, monkeypatch):
    """Run 3 uc-043: Decision 1's confirm timed out after 300 s. The scanner judged 822 waiting files, two model calls each, while it held LOCK, and
    the confirm's save waited on LOCK."""
    from sh_platform.plane import PlaneStore
    plane = PlaneStore(tmp_path / "data").create("r3b")
    H.drop(plane, "slow.csv", b"a,b\n1,2\n")
    gate, inside = threading.Event(), threading.Event()

    def judge(plane_, name, threads):
        inside.set()
        gate.wait(10)
        return "waiting", "", None
    monkeypatch.setattr(H, "recognise", judge)
    t = threading.Thread(target=H.scan, args=(None, plane))
    t.start()
    try:
        assert inside.wait(10)
        t0 = time.monotonic()
        H.save(plane, {"id": "t-r3b", "created": "2026-10-13T00:00:00Z", "stage": "decision1", "events": [], "steps": []})  # the confirm's save
        assert time.monotonic() - t0 < 2
        assert [f["name"] for f in H.scan(None, plane)] == ["slow.csv"]  # a read during the scan sees the list as it stands, at once
    finally:
        gate.set()
        t.join(10)
    assert {f["name"]: f["status"] for f in H.read_files(plane)} == {"slow.csv": "waiting"}


@pytest.mark.xfail(reason="v3_recipes.py is fixer A's: _match counts a words_all tie but picks `top` by names only, so `near` has one entry", strict=False)
def test_uc059_a_figure_two_recipes_tie_on_by_their_word_sets_does_not_crash_the_pack():
    """Run 3 uc-059: POST .../pack/generate answered 500. Cause (reproduced on a copy of the office): b10_pack.generate -> b10_design.design ->
    v3_recipes.place -> bound -> _match raised IndexError for North's "Cash breaks >5 days"."""
    k = {"name": "Cash breaks >5 days", "definition": "Number of cash‑type breaks that have been open for more than five business days",
         "formula": "Count(rows where type = 'cash' and days_open > 5)", "unit": "count"}
    R._match(k)
