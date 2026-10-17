"""W1 cash builder: the recipes, signals and persona builds of the cash and treasury cards of the top 50 (docs/v3/w1/build-cash.md).

Real: the recipe SQL (packs/family_office/1/recipes/cash.yaml) run through sh_platform.v1.v3_recipes (render, tie-out, tables rule) on a DuckDB made from the
model's own DDL; the signal engine's own parser, resolver, calculator and checker; the office6m files and their answer keys (numbers are read from
answer_keys.yaml, never typed here). Stubbed: the loader. The files are read by the small readers below (csv, xlsx with openpyxl, pdf text with pypdf) and
written into the model's tables; the platform loader (e0c_load, v3_pdf) is not called (docs/v3/w1/build-cash.md, Needs).
"""
from __future__ import annotations

import csv
import glob
import json
import re
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import duckdb
import openpyxl
import pypdf
import pytest
import yaml

from sh_platform.v1 import v3_recipes as R
from sh_platform.v1 import v3_signals as SG

REPO = Path(__file__).resolve().parents[2]
OFFICE = REPO / "tests" / "v1" / "fixtures" / "office6m"
PACK = REPO / "packs" / "family_office" / "1"
DDL = REPO / "docs" / "v2" / "evidence-to-action-mvp.duckdb.sql"
KEYS = yaml.safe_load((OFFICE / "answer_keys.yaml").read_text(encoding="utf-8"))["keys"]
ORG, TS = "org-1", "2026-10-13 09:00:00+00"
ENTITIES = {"EG-HOLD": "Evergreen Holdings", "EG-TRUST": "Evergreen Family Trust", "EG-B": "Entity B"}
CARDS = ["uc-002-callrecord", "uc6-liquidity", "uc-004-callcheck", "uc-005-benefcheck", "uc-006-fxneed", "uc-008-payrun", "uc-010-bankexp", "uc-018-fundplan",
         "uc-028-interco", "uc6-uncalled", "uc-037-distrack"]
BUILT = ["called_to_date", "call_fee_check", "calls_due", "cash_after_calls", "bank_details_changed", "fx_required", "payment_batch", "cash_by_bank",
         "funding_plan", "intercompany_balance", "distribution_gap"]


def key(card: str, n: int = 0) -> dict:
    """The expected values of the card's n-th question, from the answer keys."""
    return list(KEYS[card]["questions"].values())[n]["expected"]


# ---- readers ---------------------------------------------------------------------------------------------------------------------------

def files(pattern: str) -> list[Path]:
    return [Path(p) for p in sorted(glob.glob(str(OFFICE / pattern)))]


def csv_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@lru_cache(maxsize=None)
def pdf_text(path: str) -> str:
    return "\n".join(p.extract_text() for p in pypdf.PdfReader(path).pages)


def day(text: str) -> date:
    for fmt in ("%d %B %Y", "%m/%d/%Y", "%Y-%m-%d"):  # M11b: one notice writes mm/dd/yyyy
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError(text)


def money(text: str) -> Decimal:
    return Decimal(text.replace(",", ""))


def sheet(path: Path, name: str) -> list[dict]:
    rows = list(openpyxl.load_workbook(path, data_only=True, read_only=True)[name].iter_rows(values_only=True))
    return [dict(zip(rows[0], r)) for r in rows[1:] if any(v is not None for v in r)]


# ---- the office in the model's tables ----------------------------------------------------------------------------------------------------

class Office:
    """A small company model (the model's own DDL) filled from the office6m files by the loaders below."""

    def __init__(self):
        self.con = duckdb.connect()
        self.con.execute(DDL.read_text(encoding="utf-8"))
        self.n, self.cols = 0, {}
        self.ent, self.port, self.fund, self.cashi, self.commit, self.office_acct, self.payee = {}, {}, {}, {}, {}, {}, {}
        for code, name in ENTITIES.items():
            self.ent[code] = self.ins("legal_entities", entity_code=code, entity_name=name, base_currency="USD")
            self.port[code] = self.ins("portfolios", legal_entity_id=self.ent[code], portfolio_code=f"CASH-{code}", portfolio_name=f"Cash {name}", base_currency="USD")
        self.user = {n: self.ins("users", external_identity_id=n, display_name=n, email=f"{n.split()[0].lower()}@example.test", is_active=True)
                     for n in ("Daniel Foo", "Helen Foo", "Grace Ong", "Sam Lee")}

    def ins(self, table: str, **kw) -> str:
        if table not in self.cols:
            self.cols[table] = [r[0] for r in self.con.execute(f"select column_name from information_schema.columns where table_name = '{table}'").fetchall()]
        self.n += 1
        row = {"id": f"{table}-{self.n}", "organization_id": ORG, "source_record_id": "sr-1", "received_at": TS, "recorded_at": TS, "as_of_at": TS, "created_at": TS,
               "view_type": "operational", "data_status": "official", "source_system_id": "ss-1", "access_group_id": "ag-1", **kw}
        row = {c: v for c, v in row.items() if c in self.cols[table]}
        self.con.execute(f"insert into {table} ({', '.join(row)}) values ({', '.join('?' * len(row))})", list(row.values()))
        return row["id"]

    def instrument(self, name: str, kind: str, **kw) -> str:
        return self.ins("instruments", canonical_name=name, instrument_type=kind, currency=kw.pop("currency", "USD"), **kw)

    def fund_of(self, text: str) -> str | None:
        return next((i for n, i in sorted(self.fund.items(), key=lambda t: -len(t[0])) if n in text), None)

    # administrator cash -> position snapshots of the cash instrument
    def admin_cash(self, pattern: str = "*/administrator_cash/administrator_cash_2026-10_mtd.csv") -> "Office":
        for p in files(pattern):
            for r in csv_rows(p):
                ccy = r["currency"]
                self.cashi.setdefault(ccy, self.instrument(f"Cash {ccy}", "cash", currency=ccy))
                self.ins("position_snapshots", portfolio_id=self.port[r["entity_code"]], instrument_id=self.cashi[ccy], position_date=r["date"], source_market_value=r["administrator_cash"],
                         currency=ccy, quantity=r["administrator_cash"])
        return self

    # reference/office_rules.csv -> signed rules (A20)
    def rules(self) -> "Office":
        by = {r["rule"]: r for r in csv_rows(OFFICE / "reference" / "office_rules.csv")}
        spec = {"cash_buffer": ("policy", "cash_buffer_usd", lambda v: {"amount": float(v), "currency": "USD"}),
                "payment_approval": ("policy", "approval_over_usd", lambda v: {"amount": float(v), "currency": "USD"}),
                "changed_bank_details": ("policy", "bank_detail_change", lambda v: {"rule": v}),
                "cash_tolerance": ("tolerance", "cash_tolerance_usd", lambda v: {"amount": float(v), "currency": "USD"})}
        for code, (kind, src, params) in spec.items():
            rid = self.ins("business_rules", rule_code=code, rule_type=kind, owner_user_id=self.user["Daniel Foo"])
            self.ins("rule_versions", business_rule_id=rid, version_number=1, definition_text=by[src]["text"], parameters=json.dumps(params(by[src]["value"])),
                     effective_from="2026-04-01", approval_status="approved", approved_by=self.user["Daniel Foo"])
        return self

    # commitments register -> funds and commitments (the register states called to date at 13 Oct)
    def commitments(self, pattern: str = "*/commitments/commitments_register_2026-10-13.xlsx") -> "Office":
        terms = {r["fund"]: r for r in csv_rows(OFFICE / "reference" / "fund_terms.csv")}
        for r in sheet(files(pattern)[0], "Register"):
            if r["Fund"] is None:
                continue
            f = self.fund[r["Fund"]] = self.instrument(r["Fund"], "private_fund", manager_name=r["Manager"])
            self.commit[r["Fund"]] = self.ins("commitments", legal_entity_id=self.ent[r["Entity code"]], instrument_id=f, commitment_amount=r["Commitment"], currency=r["Currency"],
                                              committed_on=terms[r["Fund"]]["committed_on"], called_to_date=r["Called to date"], called_as_at="2026-10-13",
                                              source_record_id=None)
        return self

    # fund terms (reference/fund_terms.csv) -> extracted fields (A21): management_fee_rate is a fraction of the commitment per billing
    def fund_terms(self) -> "Office":
        for r in csv_rows(OFFICE / "reference" / "fund_terms.csv"):
            d = self.ins("documents", document_type="fund_terms", title=f"Fund terms {r['fund']}", original_uri="reference/fund_terms.csv", content_hash="h", instrument_id=self.fund[r["fund"]],
                         document_status="policy", processing_status="done", document_date="2026-04-01")
            self.ins("extracted_fields", document_id=d, field_name="management_fee_rate", value_numeric=Decimal(r["fee_pct_of_commitment_per_billing"]) / 100, page_number=1,
                     confidence="high", review_status="confirmed")
        return self

    # notices (pdf text) -> documents, extracted fields and the call or distribution as a cash movement (A22)
    def notices(self, pattern: str = "*/notices/*.pdf") -> "Office":
        last = {}
        for p in files(pattern):
            t = pdf_text(str(p))
            fund = re.search(r"Fund:\s*(.+)", t)[1].strip()
            last[fund] = p
        for p in files(pattern):
            t = pdf_text(str(p))
            fund = re.search(r"Fund:\s*(.+)", t)[1].strip()
            call = "CAPITAL CALL NOTICE" in t
            entity = next(c for c, n in ENTITIES.items() if n in re.search(r"To:\s*(.+)", t)[1])
            amount = money(re.search(r"Amount to be paid (?:by|to) the investor\s+USD ([\d,\.]+)", t)[1])
            noticed = day(re.search(r"Date of notice:\s*(.+)", t)[1])
            due = day(re.search(r"Payment (?:due|value) date:\s*(.+)", t)[1])
            ref = re.search(r"Notice ref:\s*(\S+)", t)
            doc = self.ins("documents", document_type="capital_call_notice" if call else "distribution_notice", title=ref[1] if ref else p.stem, original_filename=p.name,
                           original_uri=str(p.relative_to(OFFICE)), content_hash=p.stem, document_date=noticed, instrument_id=self.fund[fund], document_status="final",
                           processing_status="done")
            fields = {"call_amount" if call else "distribution_amount": amount, "due_date" if call else "pay_date": due}
            for name, v in fields.items():
                self.ins("extracted_fields", document_id=doc, field_name=name, value_numeric=v if isinstance(v, Decimal) else None, value_text=None if isinstance(v, Decimal) else str(v),
                         page_number=1, confidence="high", review_status="confirmed")
            if call:
                fee = re.search(r"Management fee \([\d.]+% of commitment\)\s+USD ([\d,\.]+)", t)
                acct = re.search(r"Account:\s*(\S+)", t)[1]
                if fee:  # "none in this call" has no fee line
                    self.ins("extracted_fields", document_id=doc, field_name="management_fee", value_numeric=money(fee[1]), page_number=1, confidence="high", review_status="confirmed")
                self.ins("extracted_fields", document_id=doc, field_name="bank_account", value_text=acct, page_number=1, confidence="high", review_status="confirmed")
            registered = last[fund] == p and call and self.registered_noticed(fund)
            self.ins("cash_movements", portfolio_id=self.port[entity], instrument_id=self.fund[fund], movement_type="call" if call else "distribution", effective_date=noticed,
                     due_date=due, notice_kind="call" if call else "distribution", commitment_id=self.commit[fund], amount=-amount if call else amount, currency="USD",
                     confirmation_status="noticed" if (registered or not call) else "confirmed")
        return self

    def registered_noticed(self, fund: str) -> bool:
        """The commitments register shows a call as noticed and not yet recorded."""
        return any(r["Fund"] == fund and (r["Noticed, not yet recorded"] or 0) > 0 for r in sheet(files("*/commitments/commitments_register_2026-10-13.xlsx")[0], "Register"))

    # the planned conversions and rates (fx_rates csv) -> market observations
    def fx_rates(self, pattern: str = "*/fx_rates/fx_usdsgd_*.csv") -> "Office":
        for p in files(pattern):
            r = csv_rows(p)[0]
            self.ins("market_observations", series_key="USD/SGD", observation_type="fx", observed_at=f"{r['Date']} 16:00:00+00", value=r["Rate (SGD per 1 USD)"], base_currency="USD",
                     quote_currency="SGD", quality_status="ok")
        return self

    # reference/standing_instructions.csv -> the payee account on file for each fund; reference/accounts.csv -> the office's own accounts
    def payee_accounts(self) -> "Office":
        for r in csv_rows(OFFICE / "reference" / "standing_instructions.csv"):
            self.payee[(r["fund"], r["account_last4"])] = self.ins("bank_accounts", holder_kind="payee", instrument_id=self.fund[r["fund"]], holder_name=r["fund"], account_purpose="payee",
                                                                    bank_name=r["bank"], account_ref=r["account_last4"], currency="USD", status="active", verified_on=r["confirmed_on"],
                                                                    verified_by=self.user[r["confirmed_by"]])
        return self

    def office_accounts(self) -> "Office":
        for r in csv_rows(OFFICE / "reference" / "accounts.csv"):
            ci = self.instrument(f"Bank balance {r['account_id']}", "bank_balance", currency=r["currency"])
            code = next(c for c, n in ENTITIES.items() if n == r["entity"])
            self.office_acct[r["account_id"]] = (self.ins("bank_accounts", holder_kind="office", legal_entity_id=self.ent[code], account_purpose="operating", bank_name=r["bank"],
                                                          account_ref=r["account_number"][-4:], currency=r["currency"], cash_instrument_id=ci, status="active"), ci, code)
        return self

    def bank_balances(self, pattern: str = "*/bank_statements/*_2026-10_mtd.xlsx") -> "Office":
        for p in files(pattern):
            for r in sheet(p, "Daily balances"):
                acct = next(a for a, (_, _, _) in self.office_acct.items() if self.account_number(a) == r["Account number"])
                _, ci, code = self.office_acct[acct]
                self.ins("position_snapshots", portfolio_id=self.port[code], instrument_id=ci, position_date=r["Value date"], source_market_value=r["Closing ledger balance"],
                         currency=r["Currency"])
        return self

    def account_number(self, account_id: str) -> str:
        return next(r["account_number"] for r in csv_rows(OFFICE / "reference" / "accounts.csv") if r["account_id"] == account_id)

    # bank statement lines -> payments of calls, distribution credits and transfers between entities
    def bank_lines(self, pattern: str) -> "Office":
        for p in files(pattern):
            acct = next(a for a in self.office_acct if self.account_number(a)[-4:] and p.name.startswith(a.replace("-", "_") + "_"))
            aid, _, code = self.office_acct[acct]
            for r in sheet(p, "Transactions"):
                typ, desc, amt = r["Type"], r["Description"], r["Amount"]
                if typ == "capital_call":
                    ending = re.search(r"ACCT (\d{4})", desc)[1]
                    fund = self.fund_of(desc)
                    name = next(n for n, i in self.fund.items() if i == fund)
                    self.ins("cash_movements", portfolio_id=self.port[code], instrument_id=fund, movement_type="payment", effective_date=r["Value date"], amount=amt, currency=r["Currency"],
                             confirmation_status="confirmed", bank_account_id=self.payee[(name, ending)])
                elif typ == "distribution":
                    self.ins("cash_movements", portfolio_id=self.port[code], instrument_id=self.fund_of(desc), movement_type="distribution", effective_date=r["Value date"], amount=amt,
                             currency=r["Currency"], confirmation_status="confirmed", bank_account_id=aid)
                elif typ == "intercompany_transfer":
                    other = next(c for c, n in ENTITIES.items() if n == r["Counterparty"])
                    self.ins("cash_movements", portfolio_id=self.port[code], movement_type="transfer", effective_date=r["Value date"], amount=amt, currency=r["Currency"],
                             confirmation_status="confirmed", bank_account_id=aid, counterparty_portfolio_id=self.port[other])
        return self

    # the payments waiting to be released on 13 Oct: three invoices and call 7 (the pdf text), with their approvals and holds
    def payments(self) -> "Office":
        rate = float(re.search(r"Custody \(Anchorage Custody\): ([\d.]+)%", pdf_text(str(OFFICE / "reference" / "fee_schedule.pdf")))[1])
        daniel = self.user["Daniel Foo"]
        todo = []
        for p in files("*/invoices/*FEE-*.pdf") + files("*/invoices/2026-09-14_summit_STA-2609.pdf"):
            t = pdf_text(str(p))
            payee = t.splitlines()[0].title().replace("(Synthetic)", "(synthetic)")
            ccy, amount = re.search(r"Amount due: ([A-Z]{3}) ([\d,\.]+)", t).groups()
            due = day(re.search(r"Due(?: date)?: (\d+ \w+ \d{4})", t)[1])
            end = re.search(r"account ending (\d{4})", t)
            acct = self.ins("bank_accounts", holder_kind="payee", holder_name=payee, account_purpose="payee", bank_name="Harbour Bank (synthetic)", account_ref=end[1] if end else "",
                            currency=ccy, status="active", verified_on="2026-01-15")  # an invoice that states no account leaves the reference empty
            hold = None
            if "FEE-" in p.name and (base := re.search(r"Fee base \(USD\): ([\d,\.]+)", t)):
                over = money(amount) - money(base[1]) * Decimal(str(rate)) / 100 / 4 if "CUST" in p.name else 0
                hold = f"invoice above fee schedule, {over:,.0f} over" if over > 0 else None
            todo.append((payee, ccy, money(amount), due, acct, hold, False))  # an invoice due before 13 Oct is already paid: it is not in the batch
        call = pdf_text(str(files("*/notices/2026-10-13_C_call7.pdf")[0]))
        new = self.ins("bank_accounts", holder_kind="payee", instrument_id=self.fund["Cedarpoint Ventures III"], holder_name="Cedarpoint Ventures III", account_purpose="payee",
                       bank_name="Harbour Bank (synthetic)", account_ref=re.search(r"Account:\s*\S+(\d{4})", call)[1], currency="USD", status="active",
                       supersedes_bank_account_id=self.payee[("Cedarpoint Ventures III", "2209")])
        todo.append(("Cedarpoint Ventures III", "USD", money(re.search(r"Amount to be paid by the investor\s+USD ([\d,\.]+)", call)[1]),
                     day(re.search(r"Payment due date:\s*(.+)", call)[1]), new, None, True))
        for payee, ccy, amount, due, acct, hold, needs in todo:
            m = self.ins("cash_movements", portfolio_id=self.port["EG-HOLD" if "Cedar" in payee or "Summit" in payee else "EG-TRUST"], movement_type="payment", effective_date="2026-10-13",
                         due_date=due, amount=-amount, currency=ccy, confirmation_status="expected" if due >= date(2026, 10, 13) else "confirmed", bank_account_id=acct)
            if needs:
                self.ins("approvals", cash_movement_id=m, approval_type="payment_approval", requested_from_user_id=daniel, status="requested", requested_at=TS)
            if hold:
                self.ins("approvals", cash_movement_id=m, approval_type="payment_hold", requested_from_user_id=daniel, status="requested", rationale=hold, requested_at=TS)
        return self

    def run(self, rid: str) -> list[dict]:
        """Build the recipe's table with its own SQL and return the rows as dicts."""
        r = R.recipe(rid)
        assert r is not None, f"{rid} is still a stub"
        self.con.execute(f"drop table if exists t_{rid}")
        self.con.execute(R.render(r, f"t_{rid}"))
        cur = self.con.execute(f"select * from t_{rid}")
        names = [d[0] for d in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]


@pytest.fixture(scope="module")
def liquid() -> Office:
    """Cash, commitments, notices, rules and rates as at 13 October."""
    return Office().admin_cash().rules().commitments().fund_terms().notices().fx_rates()


def one(rows: list[dict], **want) -> dict:
    hit = [r for r in rows if all(r[k] == v for k, v in want.items())]
    assert len(hit) == 1, (want, hit)
    return hit[0]


def f2(v) -> float:
    return round(float(v), 2)


# ---- the recipes are built and obey their own tables rule -------------------------------------------------------------------------------

def test_every_recipe_of_the_cash_cards_is_built_and_reads_only_the_tables_it_names(liquid):
    ids = {r["id"] for r in R.recipes()}
    assert set(BUILT) <= ids and not [s["id"] for s in R.stubs() if s["id"] in BUILT]
    for rid in BUILT:
        r = R.recipe(rid)
        assert r["may_read"] and r["never_read"] is not None and r["formula"] and r["grain"] and r["measure"] and r["columns"] and r["tie_out"], rid
        sql = R.render(r, f"t_{rid}")
        assert R.refusal(r, sql) is None, R.refusal(r, sql)
        assert not set(R.tables_read(sql)) & set(r["never_read"]), rid
        assert "{" not in sql and sql.startswith(f"create table t_{rid} as "), rid


def test_the_stubs_of_the_cash_domain_that_belong_to_cards_after_the_top_50_stay_stubs():
    assert {s["id"] for s in R.stubs()} >= {"liquidity_ladder", "cash_forecast"}


# ---- card 2 and 36: called to date and unfunded ---------------------------------------------------------------------------------------------

def test_card_2_call_7_fits_the_commitment_and_leaves_the_unfunded_amount(liquid):
    k, rows = key("uc-002-callrecord"), liquid.run("called_to_date")
    c = one(rows, fund="Cedarpoint Ventures III")
    assert f2(c["commitment"]) == k["commitment"]
    assert f2(c["called_before_notice"]) == k["called_before_call_7"] and f2(c["called_after_notice"]) == k["called_after_call_7"]
    assert f2(c["unfunded_after_notice"]) == k["unfunded_after_call_7"] and c["notice_fits"] is k["within_commitment"]


def test_card_2_the_fee_part_of_call_7_matches_the_fund_terms_and_call_3_of_credit_iii_does_not(liquid):
    k, rows = key("uc-002-callrecord", 1), liquid.run("call_fee_check")
    c = one(rows, fund="Cedarpoint Ventures III", call_no=7)
    assert f2(c["fee_on_notice"]) == k["fee_on_notice"] and f2(c["fee_per_terms"]) == k["fee_per_terms"] and c["fee_matches"] is k["matches"]
    g = one(rows, fund="Evergreen Credit III", call_no=3)  # M08: 28,125.00 charged, 18,750.00 per the terms
    assert (f2(g["fee_on_notice"]), f2(g["fee_per_terms"]), f2(g["fee_difference"]), g["fee_matches"]) == (28125.0, 18750.0, 9375.0, False)
    assert [r["call_no"] for r in rows if not r["fee_matches"]] == [3]


def test_card_36_how_much_is_uncalled_across_the_commitments(liquid):
    k, rows = key("uc6-uncalled"), liquid.run("called_to_date")
    assert round(sum(float(r["unfunded_after_notice"]) for r in rows), 2) == k["uncalled_after_call_7"]
    assert round(sum(float(r["unfunded_before_notice"]) for r in rows), 2) == k["uncalled_register_13_oct_before_call_7_recorded"]
    assert {r["fund"]: f2(r["unfunded_after_notice"]) for r in rows} == k["by_fund"]
    assert all(f2(r["called_after_notice"]) + f2(r["unfunded_after_notice"]) == f2(r["commitment"]) for r in rows)


# ---- card 3: cash by entity (the existing recipe) and the calls due in 30 and 60 days ----------------------------------------------------

def test_card_3_cash_by_entity_and_calls_due_in_30_and_60_days(liquid):
    k = key("uc6-liquidity", 0)
    cash = liquid.run("cash_by_entity")
    day13 = [r for r in cash if str(r["position_date"]) == "2026-10-13"]
    for name, v in k.items():
        assert f2(one(day13, entity=name, currency="USD")["cash"]) == v["usd"] and f2(one(day13, entity=name, currency="SGD")["cash"]) == v["sgd"]
    due, calls = key("uc6-liquidity", 1), liquid.run("calls_due")
    for name, w in due.items():
        for days, amount in w.items():
            assert f2(one(calls, entity=name, currency="USD", window_days=int(days))["calls_due"]) == amount


# ---- card 4: cash after calls ---------------------------------------------------------------------------------------------------------------

def test_card_4_holdings_is_short_after_the_call_and_the_buffer(liquid):
    k, rows = key("uc-004-callcheck"), liquid.run("cash_after_calls")
    h = one(rows, entity="Evergreen Holdings", currency="USD")
    assert f2(h["cash"]) == k["holdings_usd"] and f2(h["calls_due"]) == k["call"] and f2(h["buffer"]) == k["buffer"]
    assert f2(h["shortfall"]) == k["shortfall_usd"] and f2(h["cash_after_calls"]) == -k["shortfall_usd"]
    assert f2(one(rows, entity="Evergreen Holdings", currency="SGD")["cash"]) == k["holdings_sgd"]
    assert round(k["holdings_sgd"] / float(one(liquid.run("fx_required"), entity="Evergreen Holdings")["rate"]), 2) == k["sgd_in_usd"]
    fits = key("uc-004-callcheck", 1)
    assert one(liquid.run("called_to_date"), fund="Cedarpoint Ventures III")["notice_fits"] is fits["fits"]
    assert f2(one(liquid.run("called_to_date"), fund="Cedarpoint Ventures III")["unfunded_before_notice"]) == fits["unfunded_before"]
    rule = liquid.con.execute("select v.definition_text from business_rules r join rule_versions v on v.business_rule_id = r.id where r.rule_code = 'payment_approval'").fetchone()[0]
    assert "500,000" in rule and k["needs_approval_over_500000"]


def test_card_4_without_a_signed_buffer_rule_the_figure_is_held():
    o = Office().admin_cash().commitments().fund_terms().notices().fx_rates()  # no rules
    con, r = o.con, R.recipe("cash_after_calls")
    assert R.needs(con, r) and "buffer" in R.needs(con, r)
    assert R.needs(con, R.recipe("fx_required")) and R.needs(con, R.recipe("funding_plan"))


# ---- card 6: the FX needed ----------------------------------------------------------------------------------------------------------------

def test_card_6_holdings_converts_sgd_361800_at_the_planning_rate(liquid):
    k, rows = key("uc-006-fxneed"), liquid.run("fx_required")
    assert [r["entity"] for r in rows] == ["Evergreen Holdings"]  # only an entity with a call due that it cannot cover
    r = rows[0]
    assert f2(r["convert_amount"]) == k["sgd_to_convert_for_call_7"] and f2(r["rate"]) == k["planning_rate"] and str(r["rate_date"]) == "2026-10-13"
    assert r["convert_currency"] == "SGD" and r["other_cash_covers"] is True and f2(r["shortfall"]) == 270000.0
    assert R.needs(liquid.con, R.recipe("fx_required")) is None


# ---- card 5: the bank details changed -------------------------------------------------------------------------------------------------------

@pytest.fixture()
def payees() -> Office:
    return Office().commitments().notices().payee_accounts().office_accounts().bank_lines("*/bank_statements/HB_HOLD_USD_2026-0[47].xlsx")


def test_card_5_the_account_on_call_7_is_not_the_one_on_file_and_the_payment_stays_on_hold(payees):
    k = key("uc-005-benefcheck")
    rows = payees.run("bank_details_changed")
    c = one(rows, fund="Cedarpoint Ventures III", call_no=7)
    assert c["changed"] is k["changed"] and c["old_ending"] == k["old_ending"] and c["new_ending"] == k["new_ending"] and c["on_hold"] is k["callback_required"]
    assert c["paid_to"].split(",") == k["earlier_calls_paid_to"] and c["paid_before"] == 2
    hold = key("uc-005-benefcheck", 1)
    assert [(r["fund"], r["call_no"]) for r in rows if r["on_hold"]] == [("Cedarpoint Ventures III", 7)] and len([r for r in rows if r["on_hold"]]) == hold["count"]
    assert hold["payment"] == "CALL-C-7" and not any(r["changed"] for r in rows if r["call_no"] != 7)  # the earlier notices all went to the account on file


def test_card_5_the_hold_lifts_only_when_a_call_back_is_recorded_for_the_new_account(payees):
    c = payees.con
    new = payees.ins("bank_accounts", holder_kind="payee", instrument_id=payees.fund["Cedarpoint Ventures III"], holder_name="Cedarpoint Ventures III", account_purpose="payee",
                     bank_name="Harbour Bank (synthetic)", account_ref="4471", currency="USD", status="active", supersedes_bank_account_id=payees.payee[("Cedarpoint Ventures III", "2209")])
    assert one(payees.run("bank_details_changed"), call_no=7, fund="Cedarpoint Ventures III")["on_hold"] is True  # the new account is on file but nobody called back
    c.execute("update bank_accounts set verified_on = '2026-10-14' where id = ?", [new])
    r = one(payees.run("bank_details_changed"), call_no=7, fund="Cedarpoint Ventures III")
    assert r["changed"] is True and r["on_hold"] is False and str(r["callback_verified_on"]) == "2026-10-14"


# ---- card 8: the payment batch -------------------------------------------------------------------------------------------------------------

def test_card_8_the_weekly_payment_run_has_two_ready_one_held_and_one_waiting_for_approval():
    o = Office().commitments().notices().payee_accounts().payments()
    rows, k = o.run("payment_batch"), key("uc-008-payrun")
    got = {(r["payee"], f2(r["amount"]), r["currency"], str(r["due_date"])): r for r in rows}
    for item in k["items"]:
        r = got[(item["payee"], float(item["amount"]), item["ccy"], item["due"])]
        want = item["state"] if not item["state"].startswith("hold") else "hold"
        assert r["state"].startswith(want if want != "hold" else "hold"), (item, r["state"])
        if want == "hold":
            assert item["state"].split(": ")[1] in r["state"] and f"{item['variance']:,}" in r["state"]
    states = {}
    for r in rows:
        key_ = "hold: invoice above fee schedule" if r["state"].startswith("hold") else r["state"]
        states[key_] = states.get(key_, 0) + 1
    assert states == k["states"]
    call = one(rows, payee="Cedarpoint Ventures III")
    assert call["account_changed_unverified"] is True and call["release_blocked"] is True and call["approval_state"] == "requested" and call["requested_from"] == "Daniel Foo"
    assert one(rows, payee="Summit Tax Advisory")["release_blocked"] is False  # a vendor with its account unchanged is not blocked


# ---- card 10: cash by bank -------------------------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def banks() -> Office:
    return Office().office_accounts().bank_balances().fx_rates("*/fx_rates/fx_usdsgd_*.csv")


def test_card_10_cash_at_each_bank_in_usd_and_its_share(banks):
    k, rows = key("uc-010-bankexp"), banks.run("cash_by_bank")
    assert {r["bank"]: f2(r["usd_equivalent"]) for r in rows} == k["usd_equivalent_by_bank"]
    assert {r["bank"]: f2(r["share_pct"]) for r in rows} == k["share_pct"]
    assert round(sum(float(r["usd_equivalent"]) for r in rows), 2) == k["total_usd_eq"] and all(r["accounts"] == 6 for r in rows)
    assert all(r["limit_pct"] is None and r["over_limit"] is None and r["worst"] is None for r in rows)  # the policy sets no bank limit: nothing is over it


def test_card_10_a_signed_bank_limit_marks_the_bank_over_it(banks):
    rid = banks.ins("business_rules", rule_code="bank_limit_harbour_bank_synthetic", rule_type="policy", owner_user_id=banks.user["Daniel Foo"])
    banks.ins("rule_versions", business_rule_id=rid, version_number=1, definition_text="No bank above 50 percent of cash", parameters=json.dumps({"max_pct": 50}),
              effective_from="2026-10-01", approval_status="approved")
    try:
        h = one(banks.run("cash_by_bank"), bank="Harbour Bank (synthetic)")
        assert (f2(h["limit_pct"]), f2(h["excess_pct"]), h["over_limit"], h["worst"]) == (50.0, 34.03, True, 1)
        assert one(banks.run("cash_by_bank"), bank="Tidewater Commercial Bank (synthetic)")["worst"] is None
    finally:
        banks.con.execute("delete from rule_versions where business_rule_id = ?", [rid])
        banks.con.execute("delete from business_rules where id = ?", [rid])


# ---- card 18: which entity pays ------------------------------------------------------------------------------------------------------------

def test_card_18_holdings_pays_call_7_and_needs_a_transfer_first_and_entity_b_has_spare_cash(liquid):
    k, rows = key("uc-018-fundplan"), liquid.run("funding_plan")
    assert {r["entity"]: f2(r["cover_after_calls"]) for r in rows} == k["usd_cover_after_buffer_and_call"]
    paying = one(rows, is_named=True)
    assert paying["entity"] == k["paying_entity"] and paying["transfer_needed"] is k["transfer_needed"] and f2(paying["shortfall"]) == k["shortfall"]
    assert [r["entity"] for r in rows if r["spare_cover"] > 0] == k["entities_with_spare_usd"]
    assert paying["best_other_entity"] == "Entity B" and f2(paying["best_other_spare"]) == 618343.96


# ---- card 28: the intercompany loan ---------------------------------------------------------------------------------------------------------

def test_card_28_the_trust_lent_holdings_600000_on_5_august_and_both_sides_agree():
    k = key("uc-028-interco")
    o = Office().commitments().payee_accounts().office_accounts().bank_lines("*/bank_statements/HB_[HT]*_USD_2026-08.xlsx")
    rows = o.run("intercompany_balance")
    assert len(rows) == 1
    r = rows[0]
    assert (r["lender"], r["borrower"], f2(r["balance_outstanding"])) == (k["lender"], k["borrower"], k["balance_outstanding"] * 1.0)
    assert str(r["first_transfer_date"]) == k["date"] == str(r["last_transfer_date"]) and r["sides_agree"] is True and r["unmatched_rows"] == 0
    assert k["approval_recorded"] and k["amount"] == f2(r["balance_outstanding"])


def test_card_28_a_transfer_with_no_row_on_the_other_side_is_flagged():
    o = Office().commitments().payee_accounts().office_accounts().bank_lines("*/bank_statements/HB_TRUST_USD_2026-08.xlsx")  # only the Trust's side
    r = o.run("intercompany_balance")[0]
    assert r["sides_agree"] is False and r["unmatched_rows"] == 1 and r["lender"] == "Evergreen Family Trust"
    assert R.tie_out(o.con, R.recipe("intercompany_balance"), "t_intercompany_balance")["ok"] is False  # the transfers do not net to zero


# ---- card 37: distributions expected against received ----------------------------------------------------------------------------------------

def test_card_37_one_distribution_arrived_short_and_the_rest_in_full():
    k = key("uc-037-distrack")
    o = Office().commitments().notices().office_accounts().payee_accounts().bank_lines("*/bank_statements/HB_*_USD_2026-0[4-9].xlsx")
    rows = o.run("distribution_gap")
    want = {(r["fund"], r["pay"]): (r["notice"], r["received"], r["gap"]) for r in k["rows"]}
    got = {(r["fund"], r["pay_date"]): (f2(r["notice_amount"]), f2(r["received"]), f2(r["gap"])) for r in rows}
    assert got == {kk: tuple(map(float, v)) for kk, v in want.items()}
    assert [(r["fund"], r["pay_date"], f2(r["gap"])) for r in rows if r["gap"] > 0] == [(g["fund"], g["pay"], float(g["gap"])) for g in k["gaps"]]
    assert one(rows, fund="Evergreen Growth I")["status"] == "short" and all(r["status"] == "received" for r in rows if r["gap"] == 0)


def test_card_37_a_notice_with_no_credit_shows_its_whole_amount_and_a_future_pay_date_is_not_due():
    o = Office().commitments().notices().office_accounts().payee_accounts()  # no bank lines at all
    rows = o.run("distribution_gap")
    assert all(r["status"] == "no credit" and r["gap"] == r["notice_amount"] for r in rows)
    o.ins("cash_movements", portfolio_id=o.port["EG-HOLD"], instrument_id=o.fund["Evergreen Growth I"], movement_type="distribution", effective_date="2026-10-13",
          due_date="2026-12-01", notice_kind="distribution", commitment_id=o.commit["Evergreen Growth I"], amount=50000, currency="USD", confirmation_status="noticed")
    future = one(o.run("distribution_gap"), pay_date="2026-12-01")
    assert future["status"] == "not due" and f2(future["gap"]) == 0.0 and f2(future["notice_amount"]) == 50000.0


# ---- every recipe ties out ------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("rid", [r for r in BUILT if r not in ("payment_batch", "cash_by_bank", "intercompany_balance", "distribution_gap", "bank_details_changed")])
def test_the_tie_out_of_a_recipe_holds_on_the_october_office(liquid, rid):
    liquid.run(rid)
    t = R.tie_out(liquid.con, R.recipe(rid), f"t_{rid}")
    assert t and t["ok"], t


def test_the_tie_out_of_the_recipes_that_need_other_files_holds(payees, banks):
    for o, rid in ((payees, "bank_details_changed"), (banks, "cash_by_bank")):
        o.run(rid)
        t = R.tie_out(o.con, R.recipe(rid), f"t_{rid}")
        assert t and t["ok"], (rid, t)
    p = Office().commitments().notices().payee_accounts().payments()
    p.run("payment_batch")
    assert R.tie_out(p.con, R.recipe("payment_batch"), "t_payment_batch")["ok"]
    t = Office().commitments().payee_accounts().office_accounts().bank_lines("*/bank_statements/HB_[HT]*_USD_2026-08.xlsx")
    t.run("intercompany_balance")
    assert R.tie_out(t.con, R.recipe("intercompany_balance"), "t_intercompany_balance")["ok"]
    d = Office().commitments().notices().office_accounts().payee_accounts().bank_lines("*/bank_statements/HB_*_USD_2026-0[4-9].xlsx")
    d.run("distribution_gap")
    assert R.tie_out(d.con, R.recipe("distribution_gap"), "t_distribution_gap")["ok"]


def test_a_recipe_tie_out_fails_when_its_table_is_wrong(liquid):
    liquid.run("cash_after_calls")
    liquid.con.execute("update t_cash_after_calls set cash = cash + 1000 where currency = 'USD' and entity = 'Entity B'")
    assert R.tie_out(liquid.con, R.recipe("cash_after_calls"), "t_cash_after_calls")["ok"] is False


# ---- signals --------------------------------------------------------------------------------------------------------------------------------

ROLES = {r["id"]: r["title"] for r in yaml.safe_load((PACK / "role_builds.yaml").read_text(encoding="utf-8"))["roles"]}
SIGNALS = {p.stem: yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted((PACK / "signals").glob("*.yaml")) if any(p.name.startswith(c + "-") for c in CARDS)}


def fire(sid: str, doc: dict, figures: dict, rules: dict | None = None) -> tuple[bool, str]:
    """The engine's own resolve, calc and render over facts we hand it (what evaluate() does for one signal)."""
    sig = SIGNALS[sid]
    funcs = {"abs": abs, "min": min, "max": max, "round": round, "last4": SG.last4, "num": SG.num, "same_fund": lambda a, b: str(a) == str(b)}
    old, SG.PROVIDER, old_v, SG._fig_v = SG.PROVIDER, None, SG._fig_v, lambda plane, fid: None  # no figure store here: the facts are the rows we hand over
    try:
        ev = {"trigger": sig["trigger"]["on"], "doc": doc, "facts": {"figures": figures, "rules": rules or {}}}
        ns, _ = SG.resolve(None, sig, ev, funcs, [])
        for name, e in (sig.get("let") or {}).items():
            ns[name] = SG.calc(e, ns, funcs)
        return bool(SG.calc(sig["condition"], ns, funcs)), SG.render(sig["message"], ns)
    finally:
        SG.PROVIDER, SG._fig_v = old, old_v


def test_every_card_has_signal_files_with_at_least_one_exception_row_that_holds_something():
    assert SIGNALS
    for card in CARDS:
        mine = {k: v for k, v in SIGNALS.items() if k.startswith(card + "-")}
        assert mine, card
        assert any(v.get("row") == "exception" and v.get("hold") for v in mine.values()), card


def test_every_signal_is_valid_for_the_engine_and_routes_to_a_role_of_the_team():
    for sid, sig in SIGNALS.items():
        assert sig["id"] == sid and sig["suggestion"] is True, sid
        assert SG.check(sig, ROLES) is None, (sid, SG.check(sig, ROLES))
        assert sig["row"] in ("normal", "exception") and (sig["row"] == "normal" or sig.get("hold")), sid
        for inp in sig["inputs"]:
            if inp["kind"] == "figure":
                assert inp["id"] in {r["id"] for r in R.recipes()}, (sid, inp)  # a figure input is one of the built recipes
        names = {i.get("as") for i in sig["inputs"] if i.get("as")} | set(sig.get("let") or {}) | {"doc"}
        used = set(re.findall(r"\b([a-z_]+)\.[a-z_]", " ".join([sig["condition"], *(sig.get("let") or {}).values()]))) | set(re.findall(r"\{([a-z_]+)\.", sig["message"]))
        assert used <= names, (sid, used - names)


def test_the_columns_a_signal_reads_are_columns_of_the_recipe_it_names(liquid):
    cols = {rid: set(R.recipe(rid)["columns"]) | set(liquid.run(rid)[0]) if liquid.run(rid) else set() for rid in ("called_to_date", "call_fee_check", "cash_after_calls", "funding_plan",
                                                                                                              "fx_required", "calls_due")}
    for sid, sig in SIGNALS.items():
        alias = {i["as"]: i["id"] for i in sig["inputs"] if i["kind"] == "figure"}
        text = " ".join([sig["condition"], sig["message"], *(sig.get("let") or {}).values(), *(str(i.get("by", "")) for i in sig["inputs"])])
        for a, rid in alias.items():
            if rid in cols:
                for col in re.findall(rf"\b{a}\.(\w+)", text):
                    assert col in cols[rid], (sid, a, col)


def test_signals_fire_on_call_7_with_the_numbers_of_the_answer_keys(liquid):
    doc = {"fund": "Cedarpoint Ventures III", "investor": "Evergreen Holdings", "amount": 1250000, "currency": "USD", "call_no": 7, "due_date": "2026-10-23"}
    calls, fee = liquid.run("called_to_date"), liquid.run("call_fee_check")
    cac, plan, fx = liquid.run("cash_after_calls"), liquid.run("funding_plan"), liquid.run("fx_required")
    k2 = key("uc-002-callrecord")
    ok, msg = fire("uc-002-callrecord-recorded", doc, {"called_to_date": calls})
    assert ok and f"{k2['unfunded_after_call_7']:,}" in msg and f"{k2['called_after_call_7']:,}" in msg
    ok, _ = fire("uc-002-callrecord-blocked", doc, {"called_to_date": calls, "call_fee_check": fee})
    assert ok is False  # it fits and the fee matches: nothing is blocked
    ok, msg = fire("uc-002-callrecord-blocked", {**doc, "amount": 4000001}, {"called_to_date": calls, "call_fee_check": fee})
    assert ok and "1,250,000" not in msg and "4,000,001" in msg and "4,000,000" in msg
    ok, msg = fire("uc-002-callrecord-blocked", {**doc, "fund": "Evergreen Credit III", "investor": "Entity B", "call_no": 3, "amount": 400000}, {"called_to_date": calls, "call_fee_check": fee})
    assert ok and "28,125" in msg and "18,750" in msg  # M08: the fee part is off the fund terms
    ok, msg = fire("uc6-liquidity-call-vs-cash", doc, {"cash_after_calls": cac})
    assert ok and "1,230,000" in msg and "1,250,000" in msg
    ok, msg = fire("uc-006-fxneed-release", doc, {"fx_required": fx})
    assert ok and "361,800" in msg and "1.3400" in msg.replace("1.34000", "1.3400")
    ok, msg = fire("uc-018-fundplan-plan", doc, {"funding_plan": plan})
    assert ok and "Evergreen Holdings pays" in msg and "-270,000" in msg
    ok, msg = fire("uc-018-fundplan-under-buffer", doc, {"funding_plan": plan})
    assert ok and "270,000" in msg and f"{key('uc-018-fundplan')['usd_cover_after_buffer_and_call']['Entity B']:,.0f}" in msg
    ok, msg = fire("uc-028-interco-offer", doc, {"funding_plan": plan})
    assert ok and "Entity B can lend 270,000" in msg
    assert fire("uc-028-interco-lender-short", doc, {"funding_plan": plan})[0] is False  # Entity B can cover the whole shortfall
    assert fire("uc-004-callcheck-no-source", doc, {"funding_plan": plan})[0] is False
    ok, msg = fire("uc6-uncalled-adds-up", doc, {"called_to_date": calls})
    assert ok is False
    over = [{**r, "unfunded_after_notice": Decimal("-1000")} if r["fund"] == doc["fund"] else r for r in calls]
    assert fire("uc6-uncalled-adds-up", doc, {"called_to_date": over})[0] is True


def test_signals_that_say_no_source_or_partial_lender_fire_when_the_other_entities_cannot_cover(liquid):
    doc = {"fund": "Cedarpoint Ventures III", "investor": "Evergreen Holdings", "amount": 1250000, "currency": "USD", "call_no": 7}
    plan = liquid.run("funding_plan")
    none = [{**r, "best_other_spare": Decimal("0")} if r["is_named"] else r for r in plan]
    part = [{**r, "best_other_spare": Decimal("100000")} if r["is_named"] else r for r in plan]
    assert fire("uc-004-callcheck-no-source", doc, {"funding_plan": none})[0] is True and fire("uc-004-callcheck-no-source", doc, {"funding_plan": part})[0] is False
    assert fire("uc-028-interco-lender-short", doc, {"funding_plan": part})[0] is True and fire("uc-028-interco-lender-short", doc, {"funding_plan": none})[0] is False
    assert fire("uc-028-interco-offer", doc, {"funding_plan": part})[0] is False


def test_the_approval_signal_reads_the_signed_rule_and_the_fx_signal_needs_a_signed_tolerance(liquid):
    doc = {"fund": "Cedarpoint Ventures III", "investor": "Evergreen Holdings", "amount": 1250000, "currency": "USD", "call_no": 7}
    rule = {"amount": 500000, "currency": "USD", "text": "Payments over 500,000 need the Head of Finance's approval"}
    ok, msg = fire("uc-004-callcheck-approval", doc, {}, {"payment_approval": rule})
    assert ok and "500,000" in msg and fire("uc-004-callcheck-approval", {**doc, "amount": 400000}, {}, {"payment_approval": rule})[0] is False
    fx = liquid.run("fx_required")
    conf = {"trade_reference": "FXS-20261022-HOLD", "currency_bought": "USD", "currency_sold": "SGD", "amount_sold": 361935, "rate": 1.3405}
    tol = {"pct": 0.1}
    ok, _ = fire("uc-006-fxneed-confirmation-off", conf, {"fx_required": fx}, {"fx_plan_tolerance": tol})
    assert ok is False  # 361,935 against 361,800 is 0.037 percent: inside the tolerance
    ok, msg = fire("uc-006-fxneed-confirmation-off", {**conf, "amount_sold": 363000}, {"fx_required": fx}, {"fx_plan_tolerance": tol})
    assert ok and "1,200" in msg
    with pytest.raises(SG.Missing):  # no signed tolerance: skipped, never guessed
        fire("uc-006-fxneed-confirmation-off", {**conf, "amount_sold": 363000}, {"fx_required": fx}, {})


def test_the_bank_hold_signal_fires_for_call_7_only_while_no_call_back_is_recorded(payees):
    doc = {"fund": "Cedarpoint Ventures III", "call_no": 7}
    rows = payees.run("bank_details_changed")
    ok, msg = fire("uc-005-benefcheck-hold", doc, {"bank_details_changed": rows})
    assert ok and "4471" in msg and "2209" in msg
    assert fire("uc-005-benefcheck-hold", {"fund": "Cedarpoint Ventures III", "call_no": 6}, {"bank_details_changed": rows})[0] is False


def test_the_payment_run_signals_hold_a_payment_to_a_changed_account_and_ask_for_the_approval():
    o = Office().commitments().notices().payee_accounts().payments()
    rows = o.run("payment_batch")
    d = {"payee": "Cedarpoint Ventures III", "amount": 1250000, "currency": "USD", "due_date": "2026-10-23"}
    ok, msg = fire("uc-008-payrun-changed-account", d, {"payment_batch": rows})
    assert ok and "4471" in msg
    assert fire("uc-008-payrun-changed-account", {"payee": "Summit Tax Advisory", "amount": 5400, "currency": "SGD", "due_date": "2026-10-14"}, {"payment_batch": rows})[0] is False
    assert fire("uc-008-payrun-waiting", d, {"payment_batch": rows})[0] is True
    assert fire("uc-008-payrun-waiting", {"payee": "Summit Tax Advisory", "amount": 5400, "currency": "SGD", "due_date": "2026-10-14"}, {"payment_batch": rows})[0] is False


def test_the_bank_limit_signal_is_skipped_without_a_signed_limit_and_fires_over_it(banks):
    rows = banks.run("cash_by_bank")
    with pytest.raises(SG.Missing):  # the policy sets no bank limit
        fire("uc-010-bankexp-over-limit", {}, {"cash_by_bank": rows})
    over = [{**r, "limit_pct": Decimal("50"), "excess_pct": Decimal("34.03"), "worst": 1} if r["bank"].startswith("Harbour") else r for r in rows]
    ok, msg = fire("uc-010-bankexp-over-limit", {}, {"cash_by_bank": over})
    assert ok and "Harbour Bank (synthetic)" in msg and "84.03" in msg and "34.03" in msg


def test_the_distribution_signals_log_the_notice_and_chase_the_missing_credit():
    k = key("uc-037-distrack")
    o = Office().commitments().notices().office_accounts().payee_accounts().bank_lines("*/bank_statements/HB_*_USD_2026-0[4-9].xlsx")
    rows = o.run("distribution_gap")
    ok, msg = fire("uc-037-distrack-logged", {"fund": "Evergreen Growth I", "amount": 275000, "currency": "USD", "pay_date": "2026-07-16"}, {})
    assert ok and "275,000" in msg
    ok, msg = fire("uc-037-distrack-no-credit", {"fund": "Evergreen Growth I", "pay_date": "2026-07-16", "days_past": 90}, {"distribution_gap": rows})
    assert ok and "12,500" in msg and "262,500" in msg and k["gaps"][0]["gap"] == 12500
    assert fire("uc-037-distrack-no-credit", {"fund": "Evergreen Income II", "pay_date": "2026-07-15", "days_past": 90}, {"distribution_gap": rows})[0] is False


def test_the_late_administrator_file_signal_fires_on_a_date_that_has_passed():
    ok, msg = fire("uc6-liquidity-cash-file-late", {"due_date": "2026-10-13", "days_past": 0}, {})
    assert ok and "2026-10-13" in msg


# ---- persona builds -------------------------------------------------------------------------------------------------------------------------

BUILDS = yaml.safe_load((PACK / "builds" / "cash.yaml").read_text(encoding="utf-8"))["roles"]
OWN = [b for r in BUILDS for b in r["builds"]]
EXISTING = {b["id"] for r in yaml.safe_load((PACK / "role_builds.yaml").read_text(encoding="utf-8"))["roles"] for b in r["builds"]}
CARD_OWNER = {"uc-002-callrecord": "fund_accountant", "uc-004-callcheck": "cfo", "uc-005-benefcheck": "ops_lead", "uc-006-fxneed": "ops_lead", "uc-008-payrun": "ops_lead",
              "uc-010-bankexp": "risk_officer", "uc-018-fundplan": "cfo", "uc-028-interco": "cfo", "uc-037-distrack": "ops_clerk"}


def leaves(v):
    if isinstance(v, dict):
        for x in v.values():
            yield from leaves(x)
    elif isinstance(v, list):
        for x in v:
            yield from leaves(x)
    elif v is not None and not isinstance(v, bool):
        yield v


def forms(v) -> set[str]:
    if isinstance(v, (int, float)):
        return {str(v), str(abs(v)), f"{abs(v):,}"}
    return {str(v)}


def test_each_card_without_a_build_gets_one_under_its_owner_and_the_existing_builds_are_not_duplicated():
    assert {b["id"] for b in OWN} == set(CARD_OWNER) and not {b["id"] for b in OWN} & EXISTING
    assert "uc6-liquidity" in EXISTING and "uc6-uncalled" in EXISTING  # these two keep their builds in role_builds.yaml
    for r in BUILDS:
        assert r["id"] in ROLES
        for b in r["builds"]:
            assert CARD_OWNER[b["id"]] == r["id"], b["id"]


def test_each_build_says_the_cards_question_asks_one_and_expects_exactly_the_numbers_of_the_answer_key():
    cards = {c["id"]: c for c in yaml.safe_load((PACK / "use_cases_100.yaml").read_text(encoding="utf-8"))["use_cases"]}
    for b in OWN:
        assert b["say"] and b["title"] == cards[b["id"]]["title"] and b["skills"] and b["dashboard"] and b["files"], b["id"]
        qs = {q: v["expected"] for q, v in KEYS[b["id"]]["questions"].items()}
        asked = next((e for q, e in qs.items() if q.rstrip("?") == b["check"]["ask"].rstrip("?")), None)
        assert asked is not None, (b["id"], b["check"]["ask"])
        pool = {f for leaf in leaves(asked) for f in forms(leaf)}
        assert b["check"]["expect"], b["id"]
        for e in b["check"]["expect"]:
            assert e.replace(",", "") in {p.replace(",", "") for p in pool}, (b["id"], e, sorted(pool)[:12])


def test_each_builds_files_exist_in_the_office6m_fixtures_and_are_the_answer_keys_input_files():
    for b in OWN:
        for entry in b["files"]:
            assert entry.startswith("office6m:"), entry
            assert glob.glob(str(OFFICE / entry[len("office6m:"):])), (b["id"], entry)
        assert {e[len("office6m:"):] for e in b["files"]} == set(KEYS[b["id"]]["input_files"]), b["id"]
