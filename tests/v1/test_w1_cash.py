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
BUILT = ["called_to_date", "call_fee_check", "calls_due", "cash_after_calls", "bank_details_changed", "fx_required", "fx_rate_check", "call_payment_status", "payment_batch", "cash_by_bank",
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
        self.n, self.cols, self.names = 0, {}, {}
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
            entity_name = ENTITIES[entity]
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
                self.ins("extracted_fields", document_id=doc, field_name="investor", value_text=entity_name, page_number=1, confidence="high", review_status="confirmed")
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

    # the bank's fx confirmations (pdf text) -> fx_confirmations; the trade reference is the one in the file name (the key's refs)
    def fx_confirmations(self, pattern: str = "*/fx_confirmations/FXS-*_confirmation.pdf") -> "Office":
        for p in files(pattern):
            t = pdf_text(str(p))
            sold, bought = re.search(r"Client sells:\s*([A-Z]{3}) ([\d,\.]+)", t), re.search(r"Client buys:\s*([A-Z]{3}) ([\d,\.]+)", t)
            self.ins("fx_confirmations", trade_reference=p.name.split("_confirmation")[0], trade_date=re.search(r"Trade date:\s*(\S+)", t)[1], value_date=re.search(r"Value date:\s*(\S+)", t)[1],
                     currency_bought=bought[1], amount_bought=money(bought[2]), currency_sold=sold[1], amount_sold=money(sold[2]), rate=re.search(r"Rate \(\w+ per \w+\):\s*([\d.]+)", t)[1],
                     counterparty=t.splitlines()[0].title())
        return self

    # the trading export's spot conversions (fx_spot rows) -> transactions on the pair's instrument; the reference is the trade id without the FX- prefix (the key's refs)
    def fx_trades(self, pattern: str = "*/trading_export/trading_export_*.csv") -> "Office":
        pairs = {}
        for p in files(pattern):
            for r in csv_rows(p):
                if r["instrument_type"] != "fx_spot":
                    continue
                if r["instrument_name"] not in pairs:
                    pairs[r["instrument_name"]] = self.instrument(r["instrument_name"], "fx_spot", currency=r["currency"])
                sign = 1 if r["side"] == "buy" else -1  # buying the base currency: quantity in, cash out
                self.ins("transactions", portfolio_id=self.port["EG-HOLD"], instrument_id=pairs[r["instrument_name"]], external_trade_id=r["external_trade_id"].removeprefix("FX-"),
                         transaction_type="fx_spot", trade_date=r["trade_date"], effective_date=r["trade_date"], settlement_date=r["settle_date"],
                         quantity_delta=sign * Decimal(r["quantity"]), cash_amount=-sign * Decimal(r["amount"]), currency=r["currency"], status=r["status"])
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
                sr = self.ins("source_records", source_batch_id="sb-1", external_record_id=r["Reference"], record_type="bank_line", raw_payload_uri=p.name, content_hash=r["Reference"],
                              quality_status="ok")
                if typ == "capital_call":
                    ending = re.search(r"ACCT (\d{4})", desc)[1]
                    fund = self.fund_of(desc)
                    name = next(n for n, i in self.fund.items() if i == fund)
                    self.ins("cash_movements", portfolio_id=self.port[code], instrument_id=fund, movement_type="payment", effective_date=r["Value date"], amount=amt, currency=r["Currency"],
                             confirmation_status="confirmed", bank_account_id=self.payee[(name, ending)], source_record_id=sr)
                elif typ == "distribution":
                    self.ins("cash_movements", portfolio_id=self.port[code], instrument_id=self.fund_of(desc), movement_type="distribution", effective_date=r["Value date"], amount=amt,
                             currency=r["Currency"], confirmation_status="confirmed", bank_account_id=aid, source_record_id=sr)
                elif typ == "intercompany_transfer":
                    other = next(c for c, n in ENTITIES.items() if n == r["Counterparty"])
                    self.ins("cash_movements", portfolio_id=self.port[code], movement_type="transfer", effective_date=r["Value date"], amount=amt, currency=r["Currency"],
                             confirmation_status="confirmed", bank_account_id=aid, counterparty_portfolio_id=self.port[other], source_record_id=sr)
        return self

    # the approvals file -> an approved approval on the sending side of the transfer whose bank reference it names
    def approvals(self, pattern: str = "*/approvals/approvals_2026-08.csv") -> "Office":
        for p in files(pattern):
            for r in csv_rows(p):
                if not r["approved_by"]:
                    continue
                hit = self.con.execute("select m.id from cash_movements as m join source_records as s on s.id = m.source_record_id where s.external_record_id = ? and m.amount < 0",
                                       [r["payment_ref"]]).fetchone()
                if hit:
                    self.ins("approvals", cash_movement_id=hit[0], approval_type="payment_approval", requested_from_user_id=self.user[r["approved_by"]], decision_by_user_id=self.user[r["approved_by"]],
                             status="approved", requested_at=TS, decided_at=f"{r['approved_on']} 09:00:00+00")
        return self

    # the payments waiting to be released on 13 Oct: three invoices and call 7 (the pdf text), with their approvals and holds
    def payments(self) -> "Office":
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
                # no hold is written for an invoice above its fee schedule: no signed rule holds it (BLOCKED, docs/v3/w1/build-cash.md)
            todo.append((payee, ccy, money(amount), due, acct, None, False))  # an invoice due before 13 Oct is already paid: it is not in the batch
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
        names = self.names[rid] = [d[0] for d in cur.description]
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
    g = one(rows, fund="Evergreen Credit III", call_no=3)  # M08 (the manifest): the notice charges more than the terms; both numbers are read from the files, not typed
    notice = pdf_text(str(files("*/notices/2026-06-10_G_call3.pdf")[0]))
    charged = money(re.search(r"Management fee \([\d.]+% of commitment\)\s+USD ([\d,\.]+)", notice)[1])
    pct = Decimal(next(r["fee_pct_of_commitment_per_billing"] for r in csv_rows(OFFICE / "reference" / "fund_terms.csv") if r["fund"] == "Evergreen Credit III"))
    commitment = Decimal(str(next(r["Commitment"] for r in sheet(files("*/commitments/commitments_register_2026-10-13.xlsx")[0], "Register") if r["Fund"] == "Evergreen Credit III")))
    per_terms = commitment * pct / 100
    assert (f2(g["fee_on_notice"]), f2(g["fee_per_terms"]), f2(g["fee_difference"]), g["fee_matches"]) == (f2(charged), f2(per_terms), f2(charged - per_terms), False) and charged > per_terms
    assert [r["call_no"] for r in rows if r["fee_matches"] is False] == [3] and all(r["fee_basis"] == "rate times commitment" for r in rows)


def test_card_36_how_much_is_uncalled_across_the_commitments(liquid):
    k, rows = key("uc6-uncalled"), liquid.run("called_to_date")
    assert round(sum(float(r["unfunded_after_notice"]) for r in rows), 2) == k["uncalled_after_call_7"]
    assert round(sum(float(r["unfunded_before_notice"]) for r in rows), 2) == k["uncalled_register_13_oct_before_call_7_recorded"]
    assert {r["fund"]: f2(r["unfunded_after_notice"]) for r in rows} == k["by_fund"]
    for r in sheet(files("*/commitments/commitments_register_2026-10-13.xlsx")[0], "Register"):  # the register's own columns, fund by fund
        if r["Fund"] is None:
            continue
        c = one(rows, fund=r["Fund"])
        assert f2(c["unfunded_before_notice"]) == f2(Decimal(str(r["Commitment"])) - Decimal(str(r["Called to date"]))) and f2(c["noticed_not_recorded"]) == f2(r["Noticed, not yet recorded"] or 0)


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

def test_card_8_the_payments_that_are_ready_or_waiting_are_right_and_the_changed_account_is_held():
    o = Office().commitments().notices().payee_accounts().payments()
    rows, k = o.run("payment_batch"), key("uc-008-payrun")
    got = {(r["payee"], f2(r["amount"]), r["currency"], str(r["due_date"])): r for r in rows}
    for item in k["items"]:
        if item["state"].startswith("hold"):  # BLOCKED: see test_card_8_the_invoice_above_its_fee_schedule_is_held
            continue
        r = got[(item["payee"], float(item["amount"]), item["ccy"], item["due"])]
        assert r["state"] == item["state"], (item, r["state"])
    call = one(rows, payee="Cedarpoint Ventures III")
    assert call["account_changed_unverified"] is True and call["release_blocked"] is True and call["approval_state"] == "requested" and call["requested_from"] == "Daniel Foo"
    assert one(rows, payee="Summit Tax Advisory")["release_blocked"] is False  # a vendor with its account unchanged is not blocked


@pytest.mark.xfail(strict=True, reason="BLOCKED: no signed rule holds an invoice above its fee schedule (reference/office_rules.csv has none), and payment_batch cannot read "
                   "invoice_variance; the hold stays unwritten until the rule is signed (docs/v3/w1/build-cash.md)")
def test_card_8_the_invoice_above_its_fee_schedule_is_held():
    o = Office().commitments().notices().payee_accounts().payments()
    rows, k = o.run("payment_batch"), key("uc-008-payrun")
    want = next(i for i in k["items"] if i["payee"] == "Anchorage Custody (synthetic)")["state"]
    assert [r["state"] for r in rows if r["payee"] == "Anchorage Custody (synthetic)"] == [want]
    states = {}
    for r in rows:
        key_ = "hold: invoice above fee schedule" if r["state"].startswith("hold") else r["state"]
        states[key_] = states.get(key_, 0) + 1
    assert states == k["states"]


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
    assert k["amount"] == f2(r["balance_outstanding"])


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


def test_the_columns_a_signal_reads_are_columns_of_the_recipe_it_names():
    empty = Office()
    cols = {}
    for rid in BUILT:
        empty.run(rid)
        cols[rid] = set(empty.names[rid])
    for sid, sig in SIGNALS.items():
        alias = {i["as"]: i["id"] for i in sig["inputs"] if i["kind"] == "figure"}
        text = " ".join([sig["condition"], sig["message"], *(sig.get("let") or {}).values(), *(str(i.get("by", "")) for i in sig["inputs"])])
        by = {i["as"]: set(i.get("by") or {}) for i in sig["inputs"] if i["kind"] == "figure"}
        for a, rid in alias.items():
            if rid in cols:
                for col in re.findall(rf"{a}\.(\w+)", text):
                    assert col in cols[rid], (sid, a, col)
                assert by[a] <= cols[rid], (sid, a, by[a] - cols[rid])  # the columns a signal picks its row by exist too


CALL7 = {"fund": "Cedarpoint Ventures III", "investor": "Evergreen Holdings", "amount": 1250000, "currency": "USD", "call_no": 7, "due_date": "2026-10-23"}


def test_signals_fire_on_call_7_with_the_numbers_of_the_answer_keys(liquid):
    doc = CALL7
    calls, fee = liquid.run("called_to_date"), liquid.run("call_fee_check")
    cac, plan, fx = liquid.run("cash_after_calls"), liquid.run("funding_plan"), liquid.run("fx_required")
    k2 = key("uc-002-callrecord")
    ok, msg = fire("uc-002-callrecord-recorded", doc, {"called_to_date": calls})
    assert ok and f"{k2['unfunded_after_call_7']:,}" in msg and f"{k2['called_after_call_7']:,}" in msg
    assert fire("uc-002-callrecord-blocked", doc, {"called_to_date": calls})[0] is False  # it fits: nothing is blocked
    assert fire("uc-002-callrecord-fee-off", doc, {"call_fee_check": fee})[0] is False  # and the fee matches the terms
    ok, msg = fire("uc-002-callrecord-blocked", {**doc, "amount": 4000001}, {"called_to_date": calls})
    assert ok and "1,250,000" not in msg and "4,000,000" in msg
    ok, _ = fire("uc-002-callrecord-blocked", {**doc, "currency": "SGD"}, {"called_to_date": calls})
    assert ok  # a call in another currency than the commitment cannot be compared: it is not recorded without a decision
    c3 = {**doc, "fund": "Evergreen Credit III", "investor": "Entity B", "call_no": 3, "amount": 100000}
    g = one(fee, fund="Evergreen Credit III", call_no=3)
    ok, msg = fire("uc-002-callrecord-fee-off", c3, {"call_fee_check": fee})  # M08: the fee part is off the fund terms
    assert ok and f"{g['fee_on_notice']:,.0f}" in msg and f"{g['fee_per_terms']:,.0f}" in msg
    assert fire("uc-002-callrecord-blocked", c3, {"called_to_date": calls})[0] is False  # the call itself fits; only the fee is off
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
    assert fire("uc6-uncalled-adds-up", doc, {"called_to_date": calls})[0] is False
    over = [{**r, "called_before_notice": r["commitment"] + 1} if r["fund"] == doc["fund"] else r for r in calls]  # the register and the recorded calls say more is called than committed
    assert fire("uc6-uncalled-adds-up", doc, {"called_to_date": over})[0] is True


def test_the_funding_signals_pick_their_call_by_fund_due_date_and_amount_so_a_second_open_call_of_the_fund_is_not_mixed_in(liquid):
    plan = liquid.run("funding_plan")
    twin = [{**r, "due_date": "2026-11-20", "call_amount": Decimal("300000.00"), "cover_after_calls": Decimal("1")} for r in plan if r["fund"] == CALL7["fund"]]
    ok, msg = fire("uc-018-fundplan-plan", CALL7, {"funding_plan": plan + twin})
    assert ok and "-270,000" in msg  # the 23 Oct call, not the 20 Nov one
    with pytest.raises(SG.Missing):  # two rows that fit the same call cannot be told apart: skipped, never guessed
        fire("uc-018-fundplan-plan", CALL7, {"funding_plan": plan + [r for r in plan if r["is_named"]]})


def test_signals_that_say_no_source_or_partial_lender_fire_when_the_other_entities_cannot_cover(liquid):
    doc = CALL7
    plan = liquid.run("funding_plan")
    none = [{**r, "best_other_spare": Decimal("0")} if r["is_named"] else r for r in plan]
    part = [{**r, "best_other_spare": Decimal("100000")} if r["is_named"] else r for r in plan]
    assert fire("uc-004-callcheck-no-source", doc, {"funding_plan": none})[0] is True and fire("uc-004-callcheck-no-source", doc, {"funding_plan": part})[0] is False
    assert fire("uc-028-interco-lender-short", doc, {"funding_plan": part})[0] is True and fire("uc-028-interco-lender-short", doc, {"funding_plan": none})[0] is False
    assert fire("uc-028-interco-offer", doc, {"funding_plan": part})[0] is False


def test_the_approval_signal_reads_the_signed_rule_and_never_compares_two_currencies(liquid):
    doc = CALL7
    rule = {"amount": 500000, "currency": "USD", "text": "Payments over 500,000 need the Head of Finance's approval"}
    ok, msg = fire("uc-004-callcheck-approval", doc, {}, {"payment_approval": rule})
    assert ok and "500,000" in msg and fire("uc-004-callcheck-approval", {**doc, "amount": 400000}, {}, {"payment_approval": rule})[0] is False
    ok, msg = fire("uc-004-callcheck-approval", {**doc, "amount": 400000, "currency": "SGD"}, {}, {"payment_approval": rule})
    assert ok and "another currency" in msg  # a small SGD call is not waved through against a USD limit


@pytest.fixture()
def confs() -> Office:
    return Office().fx_rates().fx_confirmations().fx_trades()


def test_card_6_every_conversion_is_checked_against_the_fixing_of_its_day_and_the_one_without_a_confirmation_is_found(confs):
    k = key("uc-006-fxneed", 0)["conversions"]
    rows = confs.run("fx_rate_check")
    want = {c["ref"]: c for c in k}
    assert {r["trade_reference"] for r in rows} == set(want)
    for r in rows:
        c = want[r["trade_reference"]]
        assert (f2(r["amount_bought"]), float(r["bank_rate"]), float(r["fixing"]), round(float(r["difference_pct"]), 4)) == (float(c["usd"]), c["rate"], c["fixing"], c["diff_pct"])
        assert abs(r["difference_pct"]) < Decimal("0.1") and c["within_0_1_pct"]
        assert (r["confirmation"] == "bank confirmation") == c["confirmation"]
    bank = {line["Reference"] for p in files("*/bank_statements/*.xlsx") for line in sheet(p, "Transactions") if line["Type"] == "fx_conversion"}  # conversions the banks booked (the data)
    assert bank <= {r["trade_reference"] for r in rows}  # every bank conversion is in the figure, confirmed or not
    assert [r["trade_reference"] for r in rows if r["confirmation"] == "none on record"] == key("uc-006-fxneed", 2)["refs"]  # M09


def test_card_6_a_conversion_with_no_confirmation_fires_its_signal_and_the_confirmed_ones_do_not(confs):
    rows = confs.run("fx_rate_check")
    cols = ("trade_reference", "trade_date", "currency_bought", "amount_bought", "currency_sold", "bank_rate", "confirmation")
    fired = [r["trade_reference"] for r in rows if fire("uc-006-fxneed-no-confirmation", {c: r[c] for c in cols}, {"fx_rate_check": rows})[0]]
    assert fired == key("uc-006-fxneed", 2)["refs"]


def test_card_6_the_rate_signal_needs_a_signed_tolerance_and_fires_on_a_rate_away_from_the_fixing(confs):
    tol = {"pct": 0.1}
    rows = confs.run("fx_rate_check")
    first = rows[0]
    doc = {"trade_reference": first["trade_reference"], "rate": first["bank_rate"]}
    assert fire("uc-006-fxneed-confirmation-off", doc, {"fx_rate_check": rows}, {"fx_plan_tolerance": tol})[0] is False  # 0.037 percent: inside 0.1
    confs.ins("fx_confirmations", trade_reference="FXS-TEST-OFF", trade_date="2026-04-16", currency_bought="USD", amount_bought=1000000, currency_sold="SGD", amount_sold=1342400, rate="1.3424",
              counterparty="Harbour Bank (synthetic)")
    rows = confs.run("fx_rate_check")
    off = one(rows, trade_reference="FXS-TEST-OFF")
    assert float(off["fixing"]) == 1.3369 and round(float(off["difference_pct"]), 3) == 0.411
    ok, msg = fire("uc-006-fxneed-confirmation-off", {"trade_reference": "FXS-TEST-OFF", "rate": off["bank_rate"]}, {"fx_rate_check": rows}, {"fx_plan_tolerance": tol})
    assert ok and "0.4114" in msg and "1.3369" in msg
    with pytest.raises(SG.Missing):  # no signed tolerance: skipped, never guessed
        fire("uc-006-fxneed-confirmation-off", {"trade_reference": "FXS-TEST-OFF", "rate": off["bank_rate"]}, {"fx_rate_check": rows}, {})
    confs.ins("fx_confirmations", trade_reference="FXS-TEST-NOFIX", trade_date="2025-01-02", currency_bought="USD", amount_bought=1, currency_sold="SGD", amount_sold=1, rate="1.3", counterparty="x")
    nofix = one(confs.run("fx_rate_check"), trade_reference="FXS-TEST-NOFIX")
    assert nofix["fixing"] is None and nofix["difference_pct"] is None  # no fixing on that day: nothing is guessed from another day


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


# ---- wave 2: the cases the verifier named, built from the same office files with one thing changed each ----------------------------------------------

def october() -> Office:
    return Office().admin_cash().rules().commitments().fund_terms().notices().fx_rates()


def add_call(o: Office, entity: str, fund: str, amount: float, due: str, status: str, currency: str = "USD") -> str:
    return o.ins("cash_movements", portfolio_id=o.port[entity], instrument_id=o.fund[fund], movement_type="call", effective_date="2026-09-20", due_date=due, notice_kind="call",
                 commitment_id=o.commit[fund], amount=-amount, currency=currency, confirmation_status=status)


def test_a_noticed_call_already_past_its_due_date_is_still_unpaid_cash_and_a_recorded_one_past_due_is_paid():
    o = october()
    add_call(o, "EG-B", "Evergreen Credit III", 50000, "2026-09-30", "noticed")  # past due, never paid
    add_call(o, "EG-B", "Evergreen Credit III", 70000, "2026-10-01", "confirmed")  # recorded and due before the cash date: the cash already shows it paid
    due = one(o.run("calls_due"), entity="Entity B", currency="USD", window_days=30)
    assert f2(due["calls_due"]) == 50000.0 and f2(due["overdue_amount"]) == 50000.0 and due["calls"] == 1
    cac = one(o.run("cash_after_calls"), entity="Entity B", currency="USD")
    k = key("uc-018-fundplan")["usd_cover_after_buffer_and_call"]["Entity B"]
    assert f2(cac["calls_due"]) == 50000.0 and f2(cac["overdue_calls"]) == 50000.0 and f2(cac["cash_after_calls"]) == round(k - 50000, 2)
    plan = o.run("funding_plan")
    late = [r for r in plan if f2(r["call_amount"]) == 50000.0]
    assert len(late) == 3 and one(late, entity="Entity B")["is_named"] is True and f2(one(late, entity="Entity B")["cover_after_calls"]) == round(k - 50000, 2)
    assert R.tie_out(o.con, R.recipe("funding_plan"), "t_funding_plan")["ok"] and R.tie_out(o.con, R.recipe("calls_due"), "t_calls_due")["ok"]


def test_an_entity_that_reports_cash_on_an_earlier_date_keeps_the_calls_due_between_its_date_and_the_latest_date():
    o = october()
    o.con.execute("delete from position_snapshots where position_date > '2026-10-09' and portfolio_id = ?", [o.port["EG-TRUST"]])
    add_call(o, "EG-TRUST", "Evergreen Income II", 40000, "2026-10-10", "confirmed")  # after the Trust's last cash date, before the other entities'
    cac = one(o.run("cash_after_calls"), entity="Evergreen Family Trust", currency="USD")
    assert str(cac["as_of"]) == "2026-10-09" and f2(cac["calls_due"]) == 40000.0
    due = one(o.run("calls_due"), entity="Evergreen Family Trust", currency="USD", window_days=30)
    assert str(due["as_of"]) == "2026-10-09" and f2(due["calls_due"]) == 40000.0
    assert str(one(o.run("calls_due"), entity="Entity B", currency="USD", window_days=30)["as_of"]) == "2026-10-13"
    assert R.tie_out(o.con, R.recipe("calls_due"), "t_calls_due")["ok"]


def test_a_signed_buffer_is_in_force_on_the_entitys_date_and_an_unsigned_one_leaves_the_figure_empty():
    o = october()
    o.con.execute("update rule_versions set effective_from = '2026-11-01' where business_rule_id in (select id from business_rules where rule_code = 'cash_buffer')")
    rows = o.run("cash_after_calls")
    assert all(r["buffer"] is None and r["cash_after_calls"] is None and r["shortfall"] is None for r in rows)  # not on record: never zero
    assert o.run("fx_required") == [] and all(r["cover_after_calls"] is None for r in o.run("funding_plan")) and one(o.run("funding_plan"), is_named=True)["transfer_needed"] is None
    sgd = one(october().run("cash_after_calls"), entity="Evergreen Holdings", currency="SGD")
    assert sgd["buffer"] is None and sgd["cash_after_calls"] is None  # the signed buffer is in USD: no SGD buffer is invented


def test_the_cash_of_an_entity_is_not_counted_twice_when_the_bank_balances_are_typed_as_cash():
    o = Office().admin_cash().rules().commitments().notices().office_accounts().bank_balances().fx_rates()
    k = key("uc6-liquidity", 0)
    o.con.execute("update instruments set instrument_type = 'cash' where instrument_type = 'bank_balance'")  # a loader that types the bank balances as cash
    day13 = [r for r in o.run("cash_by_entity") if str(r["position_date"]) == "2026-10-13"]
    for name, v in k.items():
        assert f2(one(day13, entity=name, currency="USD")["cash"]) == v["usd"] and f2(one(day13, entity=name, currency="SGD")["cash"]) == v["sgd"]
    assert f2(one(o.run("cash_after_calls"), entity="Evergreen Holdings", currency="USD")["cash"]) == key("uc-004-callcheck")["holdings_usd"]
    for rid in ("cash_by_entity", "cash_after_calls"):
        assert R.tie_out(o.con, R.recipe(rid), f"t_{rid}")["ok"]


def test_a_call_in_another_currency_than_the_commitment_is_counted_and_never_added():
    o = october()
    add_call(o, "EG-HOLD", "Evergreen Growth I", 9000, "2026-11-01", "noticed", currency="SGD")
    g = one(o.run("called_to_date"), fund="Evergreen Growth I")
    assert g["calls_in_other_currency"] == 1 and g["notice_fits"] is False and f2(g["noticed_not_recorded"]) == 0.0
    assert R.tie_out(o.con, R.recipe("called_to_date"), "t_called_to_date")["ok"]


def test_the_fee_is_checked_against_the_investor_the_notice_names_and_not_at_all_when_two_investors_hold_the_fund():
    o = Office().commitments().fund_terms().notices()
    o.ins("commitments", legal_entity_id=o.ent["EG-B"], instrument_id=o.fund["Cedarpoint Ventures III"], commitment_amount=5000000, currency="USD", committed_on="2026-01-01",
          called_to_date=0, called_as_at="2026-10-13", source_record_id=None)
    c7 = one(o.run("call_fee_check"), fund="Cedarpoint Ventures III", call_no=7)
    assert c7["fee_matches"] is True and c7["investor"] == "Evergreen Holdings" and f2(c7["commitment"]) == key("uc-002-callrecord")["commitment"]  # the notice names the Holdings
    o.con.execute("delete from extracted_fields where field_name = 'investor'")
    c7 = one(o.run("call_fee_check"), fund="Cedarpoint Ventures III", call_no=7)
    assert c7["fee_matches"] is None and c7["fee_per_terms"] is None and c7["fee_basis"] == "investor not named on the notice"
    o.con.execute("delete from documents where document_type = 'fund_terms'")
    assert one(o.run("call_fee_check"), fund="Cedarpoint Ventures III", call_no=7)["fee_basis"] == "fee rate not on record"
    with pytest.raises(SG.Missing):  # a fee that cannot be checked is skipped with the reason, never called a match or a miss
        fire("uc-002-callrecord-fee-off", CALL7, {"call_fee_check": o.run("call_fee_check")})


# ---- card 8 ---------------------------------------------------------------------------------------------------------------------------------

def test_a_payment_to_a_changed_unverified_account_is_not_ready_even_when_no_approval_is_open():
    o = Office().commitments().notices().payee_accounts().payments()
    o.con.execute("delete from approvals where approval_type = 'payment_approval'")
    c = one(o.run("payment_batch"), payee="Cedarpoint Ventures III")
    assert c["state"] == "hold: account changed, no call-back" and c["release_blocked"] is True and c["blocked_by"] == "account changed, no call-back"
    rows = o.run("payment_batch")
    usd = [r for r in rows if r["currency"] == "USD"]
    assert {f2(r["batch_total_in_currency"]) for r in usd} == {f2(sum(r["amount"] for r in usd))}
    # held and changed-account payments are not in the releasable total; the 6,180 to Anchorage is in it only because no hold rule for an invoice above its schedule is on record (BLOCKED)
    assert {f2(r["releasable_total_in_currency"]) for r in usd} == {16234.5 + 6180}
    assert [r["blocked_by"] for r in rows if r["payee"] == "Anchorage Custody (synthetic)"] == [None]  # no payment_hold on record: nothing is invented


def test_the_payment_window_is_the_signed_rule_and_without_one_every_expected_payment_is_listed_unwindowed():
    o = Office().commitments().notices().payee_accounts().payments()
    assert all(r["in_window"] is None and r["window_days"] is None for r in o.run("payment_batch"))
    rid = o.ins("business_rules", rule_code="payment_run_window_days", rule_type="policy", owner_user_id=o.user["Daniel Foo"])
    o.ins("rule_versions", business_rule_id=rid, version_number=1, definition_text="Payment run covers the next 5 days", parameters=json.dumps({"days": 5}), effective_from="2026-04-01",
          approval_status="approved")
    rows = o.run("payment_batch")
    assert {r["payee"]: r["in_window"] for r in rows} == {"Summit Tax Advisory": True, "Harbourline Fund Services (synthetic)": False, "Anchorage Custody (synthetic)": False,
                                                          "Cedarpoint Ventures III": False}  # 13 Oct + 5 days = 18 Oct: only the Summit invoice (due 14 Oct)


# ---- card 10 ---------------------------------------------------------------------------------------------------------------------------------

def test_an_account_with_no_rate_to_usd_makes_the_bank_figure_empty_and_holds_it_instead_of_leaving_the_account_out():
    o = Office().office_accounts().bank_balances()  # no fx rates at all
    rows = o.run("cash_by_bank")
    assert all(r["usd_equivalent"] is None and r["share_pct"] is None and r["unconverted_accounts"] > 0 for r in rows)
    assert "no rate to USD" in R.needs(o.con, R.recipe("cash_by_bank"))
    assert R.needs(Office().office_accounts().bank_balances().fx_rates().con, R.recipe("cash_by_bank")) is None


def test_two_banks_over_their_signed_limits_are_both_ranked_and_counted():
    o = Office().office_accounts().bank_balances().fx_rates()
    for bank in ("harbour_bank_synthetic", "tidewater_commercial_bank_synthetic"):
        rid = o.ins("business_rules", rule_code=f"bank_limit_{bank}", rule_type="policy", owner_user_id=o.user["Daniel Foo"])
        o.ins("rule_versions", business_rule_id=rid, version_number=1, definition_text="limit", parameters=json.dumps({"max_pct": 10}), effective_from="2026-10-01", approval_status="approved")
    rows = o.run("cash_by_bank")
    assert sorted(r["worst"] for r in rows) == [1, 2] and {r["banks_over_limit"] for r in rows} == {2} and one(rows, worst=1)["bank"].startswith("Harbour")
    ok, msg = fire("uc-010-bankexp-over-limit", {}, {"cash_by_bank": rows})
    assert ok and "Banks over their limit: 2" in msg


# ---- card 28 -----------------------------------------------------------------------------------------------------------------------------------

def test_card_28_the_reference_and_the_approval_come_from_the_rows_and_the_approvals_file():
    k = key("uc-028-interco")
    o = Office().commitments().payee_accounts().office_accounts().bank_lines("*/bank_statements/HB_[HT]*_USD_2026-08.xlsx").approvals()
    r = o.run("intercompany_balance")[0]
    row = next(x for x in csv_rows(files("*/approvals/approvals_2026-08.csv")[0]) if x["payment_ref"] == k["reference"])
    assert r["reference"] == k["reference"] and r["approvals_recorded"] == 1 and r["approved_by"] == row["approved_by"] and f2(row["amount_usd"]) == f2(r["balance_outstanding"])


def test_card_28_a_repayment_recorded_by_the_borrower_only_still_reduces_the_balance_and_is_flagged():
    o = Office().commitments().payee_accounts().office_accounts().bank_lines("*/bank_statements/HB_[HT]*_USD_2026-08.xlsx")
    o.ins("cash_movements", portfolio_id=o.port["EG-HOLD"], movement_type="transfer", effective_date="2026-09-01", amount=-100000, currency="USD", confirmation_status="confirmed",
          counterparty_portfolio_id=o.port["EG-TRUST"])
    r = o.run("intercompany_balance")[0]
    assert (r["lender"], f2(r["balance_outstanding"]), r["sides_agree"], r["unmatched_rows"]) == ("Evergreen Family Trust", 500000.0, False, 1)
    o.ins("cash_movements", portfolio_id=o.port["EG-TRUST"], movement_type="transfer", effective_date="2026-09-02", amount=100000, currency="USD", confirmation_status="confirmed",
          counterparty_portfolio_id=o.port["EG-HOLD"])  # the Trust books it a day later: one repayment, not two
    r = o.run("intercompany_balance")[0]
    assert f2(r["balance_outstanding"]) == 500000.0 and r["unmatched_rows"] == 0 and r["date_differs"] == 1 and r["sides_agree"] is False
    ok, msg = fire("uc-028-interco-one-sided", {}, {"intercompany_balance": [r]})
    assert ok and "on another date" in msg


# ---- card 37 -----------------------------------------------------------------------------------------------------------------------------------

def distributions() -> Office:
    return Office().commitments().notices().office_accounts().payee_accounts().bank_lines("*/bank_statements/HB_*_USD_2026-0[4-9].xlsx")


def test_card_37_a_credit_a_day_late_is_still_the_credit_of_the_notice_and_a_reversal_takes_money_back():
    o = distributions()
    base = {r["fund"]: r for r in o.run("distribution_gap")}
    o.con.execute("update cash_movements set effective_date = effective_date + 1 where movement_type = 'distribution' and confirmation_status = 'confirmed' and instrument_id = ?",
                  [o.fund["Evergreen Growth I"]])
    late = one(o.run("distribution_gap"), fund="Evergreen Growth I")
    assert (f2(late["received"]), f2(late["gap"]), late["status"]) == (f2(base["Evergreen Growth I"]["received"]), f2(base["Evergreen Growth I"]["gap"]), "short")
    o.ins("cash_movements", portfolio_id=o.port["EG-HOLD"], instrument_id=o.fund["Evergreen Income II"], movement_type="distribution", effective_date="2026-07-16", amount=-20000, currency="USD",
          confirmation_status="confirmed", bank_account_id=next(iter(o.office_acct.values()))[0])  # a reversal of part of the July distribution
    rev = one(o.run("distribution_gap"), fund="Evergreen Income II", pay_date="2026-07-15")
    assert (f2(rev["received"]), f2(rev["gap"]), rev["status"]) == (100000.0, 20000.0, "short")


def test_card_37_more_money_than_the_notice_is_over_not_short_and_a_notice_with_no_recorded_movement_is_still_tracked():
    o = distributions()
    o.ins("cash_movements", portfolio_id=o.port["EG-HOLD"], instrument_id=o.fund["Evergreen Income II"], movement_type="distribution", effective_date="2026-04-15", amount=5000, currency="USD",
          confirmation_status="confirmed", bank_account_id=next(iter(o.office_acct.values()))[0])
    over = one(o.run("distribution_gap"), fund="Evergreen Income II", pay_date="2026-04-15")
    assert (f2(over["received"]), f2(over["gap"]), over["status"]) == (125000.0, -5000.0, "over")
    n = len(o.run("distribution_gap"))
    o.con.execute("delete from cash_movements where movement_type = 'distribution' and confirmation_status = 'noticed' and instrument_id = ?", [o.fund["Evergreen Credit III"]])
    rows = o.run("distribution_gap")
    c = one(rows, fund="Evergreen Credit III")
    assert len(rows) == n and c["recorded"] is False and f2(c["notice_amount"]) == 55000.0 and c["status"] == "received"  # the notice document alone keeps the row
    assert R.tie_out(o.con, R.recipe("distribution_gap"), "t_distribution_gap")["ok"]
    o.con.execute("delete from cash_movements where movement_type = 'distribution' and confirmation_status = 'confirmed' and instrument_id = ?", [o.fund["Evergreen Credit III"]])
    c = one(o.run("distribution_gap"), fund="Evergreen Credit III")
    assert (c["status"], f2(c["gap"])) == ("no credit", 55000.0)  # and with no credit either the whole amount is the gap


def test_card_6_a_call_is_paid_when_the_bank_shows_the_exact_amount_on_its_due_date_and_call_7_is_not_due():
    k = key("uc-006-fxneed", 1)["calls_due_to_date"]
    o = Office().commitments().notices().office_accounts().payee_accounts().bank_lines("*/bank_statements/*_USD_2026-0[4-9].xlsx")
    rows = o.run("call_payment_status")
    keyed = {r["Fund key"]: r["Fund"] for r in sheet(files("*/commitments/commitments_register_2026-10-13.xlsx")[0], "Register") if r["Fund"]}
    for c in k:
        letter = c["call"].split("-")[1]
        hit = [r for r in rows if r["fund"] == keyed[letter] and r["due_date"] == c["due"] and f2(r["amount"]) == float(c["amount"])]
        assert len(hit) == 1 and (hit[0]["status"] == "paid") is c["paid"], c
    seven = one(rows, fund="Cedarpoint Ventures III", due_date="2026-10-23")
    assert seven["status"] == "not due" and seven["payments_found"] == 0
    assert [r for r in rows if r["status"] == "not paid"] == []
    o.con.execute("delete from cash_movements where movement_type = 'payment' and instrument_id = ?", [o.fund["Cedarpoint Ventures III"]])  # the bank shows nothing for Cedarpoint III
    assert sorted(r["due_date"] for r in o.run("call_payment_status") if r["status"] == "not paid" and r["fund"] == "Cedarpoint Ventures III") == ["2026-04-21", "2026-07-21"]
    assert R.tie_out(o.con, R.recipe("call_payment_status"), "t_call_payment_status")["ok"]


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


# ---- live r1 fixes: shadow commitment rows and the daily cash break ----------------------------------------------------------------------

def test_shadow_commitment_rows_are_not_counted_as_unfunded():
    """r1 uc-007: placeholder rows (no register source, no called figure, no call) for commitments the register already holds added their whole amount (58.6M, not 14.6M)."""
    o = Office().commitments().fund_terms().notices()
    k = key("uc6-uncalled")["uncalled_after_call_7"]
    live = o.con.execute("select legal_entity_id, instrument_id, commitment_amount, committed_on from commitments where called_to_date is not null").fetchall()
    for ent, ins, amt, on in live:  # one placeholder per register line, and one for an investor the register does not list in that fund
        o.ins("commitments", legal_entity_id=ent, instrument_id=ins, commitment_amount=amt, currency="USD", committed_on=on, called_to_date=None, called_as_at=None, source_record_id=None)
    o.ins("commitments", legal_entity_id=o.ent["EG-B"], instrument_id=live[0][1], commitment_amount=6000000, currency="USD", committed_on="2023-09-20", called_to_date=None, called_as_at=None, source_record_id=None)
    rows = o.run("called_to_date")
    assert round(sum(float(r["unfunded_after_notice"]) for r in rows), 2) == k and len(rows) == len(live)
    assert R.tie_out(o.con, R.recipe("called_to_date"), "t_called_to_date")["ok"]


def test_cash_break_is_the_break_of_the_day_and_not_the_sum_since_the_period_start():
    """r1 uc2: Entity B, 8 Oct: the administrator's cash is flat, the 12,400 wire left the bank that day, so the break is 12,400 on the 8th and -12,400 on the 9th, 0 on the others."""
    o = Office()
    cash = o.instrument("Cash USD", "cash")
    desk = o.instrument("Desk cash EG-B USD", "cash")  # the desk's own derived line must not be read as the administrator's cash
    bank = o.instrument("HB-B-USD", "cash")
    o.ins("bank_accounts", holder_kind="office", legal_entity_id=o.ent["EG-B"], cash_instrument_id=bank, currency="USD", status="active", holder_name="Entity B", account_purpose="operating", bank_name="HB", account_ref="B")
    k = key("uc2-recon-break-desk")
    wire, day8 = Decimal(str(k["difference"])), str(k["date"])
    for d, admin, derived in (("2026-10-06", 880400, 880400), ("2026-10-07", 880400, 880400), ("2026-10-08", 880400, 868000), ("2026-10-09", 868000, 868000), ("2026-10-12", 868000, 868000)):
        o.ins("position_snapshots", portfolio_id=o.port["EG-B"], instrument_id=cash, position_date=d, source_market_value=admin, currency="USD", quantity=admin)
        o.ins("position_snapshots", portfolio_id=o.port["EG-B"], instrument_id=desk, position_date=d, source_market_value=derived, currency="USD", quantity=derived, data_status="Derived")
        o.ins("position_snapshots", portfolio_id=o.port["EG-B"], instrument_id=bank, position_date=d, source_market_value=derived - 200000, currency="USD", quantity=derived - 200000)
    o.ins("cash_movements", portfolio_id=o.port["EG-B"], movement_type="payment", amount=-wire, currency="USD", effective_date=day8, confirmation_status="confirmed")
    by = {str(r["day"]): r["cash_break"] for r in o.run("cash_break")}
    assert by == {"2026-10-07": 0, "2026-10-08": wire, "2026-10-09": -wire, "2026-10-12": 0}  # the first day has no day before it
    assert R.tie_out(o.con, R.recipe("cash_break"), "t_cash_break")["ok"]


def test_net_worth_counts_the_cash_of_a_portfolio_once():
    """r1 morning note: the administrator's cash, the office's bank-account lines and the desk's derived cash all sat in the snapshots; net worth counted the cash three times."""
    o = Office()
    cash, desk, bank1, bank2 = o.instrument("Cash USD", "cash"), o.instrument("Desk cash EG-B USD", "cash"), o.instrument("HB-B-USD", "cash"), o.instrument("TCB-B-USD", "cash")
    for b, ref in ((bank1, "B1"), (bank2, "B2")):
        o.ins("bank_accounts", holder_kind="office", legal_entity_id=o.ent["EG-B"], cash_instrument_id=b, currency="USD", status="active", holder_name="Entity B", account_purpose="operating", bank_name="HB", account_ref=ref)
    snap = lambda ins, v, st="Final", d="2026-09-30": o.ins("position_snapshots", portfolio_id=o.port["EG-B"], instrument_id=ins, position_date=d, source_market_value=v, currency="USD", quantity=v, data_status=st)  # noqa: E731
    snap(cash, 880400), snap(desk, 880400, "Derived"), snap(bank1, 680400), snap(bank2, 200000)
    snap(desk, 870000, "Derived", "2026-10-01"), snap(bank1, 670000, "Final", "2026-10-01"), snap(bank2, 200000, "Final", "2026-10-01")  # no administrator line: the bank lines count
    by = {str(r["position_date"]): r["net_worth"] for r in o.run("net_worth")}
    assert by == {"2026-09-30": 880400, "2026-10-01": 870000}
    assert R.tie_out(o.con, R.recipe("net_worth"), "t_net_worth")["ok"]
