"""W1 invest: the recipes, signals and persona builds of the Invest cards of the top 50 (7, 25, 34, 35, 39, 40, 41, 49), proved on the Evergreen Office data.

Real: the recipes file (sh_platform/v1/v3_recipes.py renders and guards them), the model DDL (docs/v2/evidence-to-action-mvp.duckdb.sql), the office6m files, the signal
checker (sh_platform/v1/v3_signals.py check/calc) and the answer keys (tests/v1/fixtures/office6m/answer_keys.yaml). The files are read by the small loader below (PDF text with
pypdf, xlsx with openpyxl) because the production loaders for call notices, manager statements and questionnaires are not written yet (see docs/v3/w1/build-invest.md, Needs).
A recipe's numbers are asserted against the answer key; nothing is computed here with a rule of its own.
"""
import csv
import datetime as dt
import glob
import re
from decimal import Decimal
from pathlib import Path

import duckdb
import openpyxl
import pytest
import yaml
from pypdf import PdfReader

from sh_platform.v1 import v3_recipes as R
from sh_platform.v1 import v3_signals as S

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "v1" / "fixtures" / "office6m"
PACK = ROOT / "packs" / "family_office" / "1"
DDL = ROOT / "docs" / "v2" / "evidence-to-action-mvp.duckdb.sql"
KEYS = yaml.safe_load((FIX / "answer_keys.yaml").read_text(encoding="utf-8"))["keys"]
CARDS = {"uc-007-pacing": 7, "uc7-manager-diligence": 25, "uc-034-prospect": 34, "uc-035-ddq": 35, "uc-039-irr": 39, "uc-040-icmemo": 40, "uc-041-commitappr": 41, "uc-049-feedrag": 49}
MY_RECIPES = ["commitments_by_fund", "private_markets_budget", "ddq_compare", "fund_irr_tvpi", "fee_drag", "manager_timeline", "mandate_fit", "memo_support", "commit_check"]
ORG, ASOF = "org-1", "2026-10-13"
PORTFOLIO_OF = {"A": "EG-GROWTH", "B": "EG-GROWTH", "C": "EG-PRIVATE", "F": "EG-PRIVATE", "D": "EG-B-OPS", "E": "EG-B-OPS", "G": "EG-B-OPS", "K": "EG-B-OPS", "H1": "EG-FUNDS", "H2": "EG-FUNDS"}
PORTFOLIO_ENTITY = {"EG-GROWTH": "EG-HOLD", "EG-PRIVATE": "EG-HOLD", "EG-B-OPS": "EG-B", "EG-FUNDS": "EG-TRUST"}
ENTITY_NAME = {"EG-HOLD": "Evergreen Holdings", "EG-TRUST": "Evergreen Family Trust", "EG-B": "Entity B"}
KESTREL = "Kestrel Ridge Advisors"


# ---- reading the office6m files -------------------------------------------------------------------------------------------------------------------

def pdf_text(p) -> str:
    return "\n".join(pg.extract_text() for pg in PdfReader(str(p)).pages)


def num(s) -> Decimal:
    return Decimal(re.sub(r"[^\d.\-]", "", s))


def when(s: str) -> dt.date:
    s = s.strip()
    for f in ("%d %B %Y", "%m/%d/%Y", "%Y-%m-%d"):  # M11b: one notice writes mm/dd/yyyy
        try:
            return dt.datetime.strptime(s, f).date()
        except ValueError:
            pass
    raise ValueError(s)


def field(t: str, pat: str, group: int = 1):
    m = re.search(pat, t)
    return m.group(group).strip() if m else None


def read_all() -> dict:
    """Everything the recipes need, read once from the files."""
    d: dict = {"funds": {}, "statements": [], "notices": [], "bank": {}, "cash": [], "fx": [], "ddq": [], "docs": []}
    reg = list(openpyxl.load_workbook(FIX / "2026-10/commitments/commitments_register_2026-10-13.xlsx").active.iter_rows(values_only=True))
    head = reg[0]
    manager = {r[3]: r[4] for r in reg[1:] if r[3]}
    reg_rows = {r[3]: dict(zip(head, r)) for r in reg[1:] if r[3]}
    for r in csv.DictReader(open(FIX / "reference/fund_terms.csv", encoding="utf-8")):
        k = r["fund_key"]
        d["funds"][k] = {"key": k, "name": r["fund"], "entity": r["entity"], "committed_on": r["committed_on"], "fee_pct": Decimal(r["fee_pct_of_commitment_per_billing"]),
                         "commitment": Decimal(reg_rows[k]["Commitment"]), "called": Decimal(reg_rows[k]["Called to date"]), "manager": manager[k]}
    for p in sorted(glob.glob(str(FIX / "*/manager_statements/*.pdf"))):
        m = re.fullmatch(r"(\w+?)_(A|B|C|D|E|F|G|K|H1|H2)_(\d{4}-\d{2}-\d{2})_(final|estimate|amended)\.pdf", Path(p).name)
        if not m:
            continue
        t = pdf_text(p)
        d["statements"].append({"file": Path(p).name, "key": m[2], "fund": field(t, r"Fund: (.*)"), "period": m[3], "kind": m[4], "issued": when(field(t, r"Issued: (.*)")),
                                "value": num(field(t, r"Closing capital account balance\s+([\d,.\-]+)")), "cum_called": num(c) if (c := field(t, r"Cumulative contributions called\s+([\d,.]+)")) else None})
    for p in sorted(glob.glob(str(FIX / "*/bank_statements/*_USD_*.xlsx"))):  # the bank side of the calls and distributions: reference -> (value date, amount)
        ws = openpyxl.load_workbook(p, read_only=True)["Transactions"]
        for row in list(ws.iter_rows(values_only=True))[1:]:
            if row[1] and (str(row[1]).startswith("CC-CALL-") or str(row[1]).startswith("DI-DIST-")):
                d["bank"][row[1]] = (when(str(row[0])[:10]), Decimal(str(row[5])))
    for p in sorted(glob.glob(str(FIX / "*/notices/*.pdf"))):
        n = Path(p).name
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})_(\w)_(call(\d+)|distribution)\.pdf", n)
        t = pdf_text(p)
        o = {"file": n, "key": m[2], "notice": when(field(t, r"Date of notice: (.*)"))}
        if m[3] == "distribution":
            o.update(kind="distribution", value_date=when(field(t, r"Payment value date: (.*)")), amount=num(field(t, r"Amount to be paid to the investor\s+USD ([\d,.]+)")))
        else:
            fee = field(t, r"Management fee(?: \(.*?\))?\s+USD ([\d,.]+)")
            o.update(kind="call", no=int(m[4]), due=when(field(t, r"Payment due date: (.*)")), invest=num(field(t, r"New investments\s+USD ([\d,.]+)")), fee=num(fee) if fee else Decimal(0))
        d["notices"].append(o)
    cashfiles = sorted(glob.glob(str(FIX / "2026-10/bank_statements/*_2026-10_mtd.xlsx")))
    acct_entity = {r["account_id"]: r["entity"] for r in csv.DictReader(open(FIX / "reference/accounts.csv", encoding="utf-8"))}
    ent_code = {v: k for k, v in ENTITY_NAME.items()}
    for p in cashfiles:
        acct = Path(p).name.replace("_2026-10_mtd.xlsx", "").replace("_", "-")
        ws = openpyxl.load_workbook(p, read_only=True)["Daily balances"]
        for row in list(ws.iter_rows(values_only=True))[1:]:
            if str(row[0])[:10] == ASOF:
                d["cash"].append({"account": acct, "entity": ent_code[acct_entity[acct]], "currency": row[2], "balance": Decimal(str(row[5]))})
    for p in sorted(glob.glob(str(FIX / "*/fx_rates/*.csv"))):
        for r in csv.DictReader(open(p, encoding="utf-8")):
            d["fx"].append((r["Date"], Decimal(r["Rate (SGD per 1 USD)"])))
    for p in sorted(glob.glob(str(FIX / "*/ddq/cedarpoint_ddq_*.pdf"))):
        t = pdf_text(p)
        d["ddq"].append({"file": Path(p).name, "month": Path(p).parts[-3], "title": field(t, r"^(.*DUE DILIGENCE QUESTIONNAIRE \d{4})").title(),
                         "answers": [(a, b.strip()) for a, b in re.findall(r"^\d+\. (.*?): (.*)$", t, re.M)]})
    tt = pdf_text(FIX / "2026-09/prospects/fund_teaser_Harborlight_Ventures_IV.pdf")
    d["teaser"] = {"name": "Harborlight Ventures IV", "manager": "Harborlight Capital Partners", "strategy": field(tt, r"Strategy: (.*?),"), "asset_class": "venture",
                   "ticket": num(field(tt, r"Minimum commitment: USD ([\d,]+)")), "file": "fund_teaser_Harborlight_Ventures_IV.pdf"}
    nl = pdf_text(FIX / "reference/kestrel_ridge_q3_2026_newsletter.pdf")
    d["newsletter"] = {"title": "Kestrel Ridge Advisors Q3 2026 newsletter", "date": dt.date(2026, 9, 28), "team_change": " ".join(re.search(r"Team update\n(.*?)\nThe investment process", nl, re.S)[1].split())}
    note = (FIX / "2026-06/meeting_notes/04_kestrel_ridge_onsite_2026-06-12.md").read_text(encoding="utf-8")
    d["meeting"] = {"title": "Meeting note MN-2026-04", "date": when(field(note, r"\| Date \| (.*?) \|")), "counterparty": field(note, r"\| Counterparty \| (.*?) \(").strip()}
    return d


@pytest.fixture(scope="module")
def data():
    return read_all()


# ---- the small company model -----------------------------------------------------------------------------------------------------------------------

class Office:
    """The model's tables (the DDL of the warehouse) holding the office6m facts the way the loaders write them (v3_pack_readers): a call notice is one call row for the WHOLE
    notice amount (investment part plus management fee), and its management fee is the notice document's management_fee field; the notice document's source_record_id is the call row's;
    money out negative; a distribution is a noticed row superseded by the confirmed bank credit; statements are valuations that a later one for the period supersedes."""

    def __init__(self, d: dict):
        self.d, self.n = d, 0
        self.con = duckdb.connect(":memory:")
        self.con.execute("SET TimeZone='UTC'")
        self.con.execute(DDL.read_text(encoding="utf-8"))
        self.ent, self.pf, self.inst, self.commit, self.doc_of = {}, {}, {}, {}, {}
        self.load()

    def i(self, p: str) -> str:
        self.n += 1
        return f"{p}-{self.n:05d}"

    def ins(self, table: str, **row):
        row.setdefault("organization_id", ORG) if table != "organizations" else None
        self.con.execute(f"insert into {table} ({', '.join(row)}) values ({', '.join('?' * len(row))})", list(row.values()))

    def ts(self, day) -> str:
        return f"{day} 12:00:00+00"

    def document(self, kind, title, day, status="final", instrument=None, valuation=None, uri=None) -> str:
        did = self.i("doc")
        self.ins("documents", id=did, source_record_id=did, source_system_id="src-1", access_group_id="ag-1", instrument_id=instrument, document_type=kind, title=title, original_uri=uri or f"office6m/{title}",
                 content_hash=did, document_date=day, valuation_date=valuation, received_at=self.ts(day), recorded_at=self.ts(day), document_status=status, processing_status="done")
        return did

    def fld(self, doc, name, text=None, numeric=None, page=1):
        self.ins("extracted_fields", id=self.i("fld"), document_id=doc, field_name=name, value_text=text, value_numeric=numeric, page_number=page, confidence="high", review_status="confirmed")

    def load(self):
        d = self.d
        for code, name in ENTITY_NAME.items():
            self.ent[code] = self.i("ent")
            self.ins("legal_entities", id=self.ent[code], entity_code=code, entity_name=name, base_currency="USD")
        for code, ent in {**PORTFOLIO_ENTITY, **{f"CASH-{c}": c for c in ENTITY_NAME}}.items():
            self.pf[code] = self.i("pf")
            self.ins("portfolios", id=self.pf[code], legal_entity_id=self.ent[ent], portfolio_code=code, portfolio_name=code, base_currency="USD")
        for k, f in d["funds"].items():
            self.inst[k] = self.i("ins")
            self.ins("instruments", id=self.inst[k], canonical_name=f["name"], instrument_type="fund", asset_class="private fund", manager_name=f["manager"], currency="USD", created_at=self.ts("2026-04-01"))
            self.commit[k] = self.i("cmt")
            self.ins("commitments", id=self.commit[k], legal_entity_id=self.ent[f["entity"]], instrument_id=self.inst[k], source_record_id="register 2026-10-13", commitment_amount=f["commitment"],
                     currency="USD", committed_on=f["committed_on"], called_to_date=f["called"], called_as_at=ASOF, recorded_at=self.ts(ASOF))
            terms = self.document("fund_terms", f"Fund terms {f['name']}", "2026-04-01", instrument=self.inst[k], uri="reference/fund_terms.csv")
            self.fld(terms, "management_fee_rate", numeric=f["fee_pct"] / 100)  # a fraction per billing (A21)
            self.fld(terms, "fee_basis", text="commitment, per billing")
        for s in d["statements"]:
            if s["key"] in ("H1", "H2") and s["key"] not in self.inst:
                self.inst[s["key"]] = self.i("ins")
                self.ins("instruments", id=self.inst[s["key"]], canonical_name=s["fund"], instrument_type="fund", asset_class="hedge fund", manager_name=KESTREL, currency="USD", created_at=self.ts("2026-04-01"))
        last: dict = {}
        for s in sorted(d["statements"], key=lambda x: (x["key"], x["period"], x["issued"])):
            if s["key"] not in self.inst:
                continue
            doc = self.document("manager_statement", s["file"].removesuffix(".pdf"), s["issued"], status=s["kind"] if s["kind"] != "amended" else "final", instrument=self.inst[s["key"]], valuation=s["period"])
            self.fld(doc, "closing_balance", numeric=s["value"])
            if s["cum_called"] is not None:
                self.fld(doc, "cumulative_called", numeric=s["cum_called"])
            vid = self.i("val")
            kind = {"final": "manager_final", "estimate": "manager_estimate", "amended": "manager_amended"}[s["kind"]]
            self.ins("valuation_observations", id=vid, instrument_id=self.inst[s["key"]], portfolio_id=self.pf[PORTFOLIO_OF[s["key"]]], source_record_id=doc, evidence_document_id=doc,
                     valuation_date=s["period"], received_at=self.ts(s["issued"]), recorded_at=self.ts(s["issued"]), value_amount=s["value"], currency="USD", valuation_type=kind,
                     approval_status="accepted", supersedes_valuation_id=last.get((s["key"], s["period"])))
            last[(s["key"], s["period"])] = vid
        for n in d["notices"]:
            k, f = n["key"], d["funds"][n["key"]]
            doc = self.document("capital_call_notice" if n["kind"] == "call" else "distribution_notice", n["file"].removesuffix(".pdf"), n["notice"], instrument=self.inst[k])
            if n["kind"] == "call":
                paid = d["bank"].get(f"CC-CALL-{k}-{n['no']}")
                if n["fee"]:
                    self.fld(doc, "management_fee", numeric=n["fee"])
                self.ins("cash_movements", id=self.i("mov"), source_record_id=doc, portfolio_id=self.pf[PORTFOLIO_OF[k]], instrument_id=self.inst[k], movement_type="call", effective_date=n["due"],
                         received_at=self.ts(n["notice"]), recorded_at=self.ts(n["notice"]), amount=-(n["invest"] + n["fee"]), currency="USD", confirmation_status="confirmed" if paid else "noticed",
                         due_date=n["due"], notice_kind="capital_call", commitment_id=self.commit[k])
            else:
                ref = f"DI-DIST-{k}-{n['value_date']:%Y-%m}"
                noticed = self.i("mov")
                self.ins("cash_movements", id=noticed, source_record_id=doc, portfolio_id=self.pf[PORTFOLIO_OF[k]], instrument_id=self.inst[k], movement_type="distribution", effective_date=n["value_date"],
                         received_at=self.ts(n["notice"]), recorded_at=self.ts(n["notice"]), amount=n["amount"], currency="USD", confirmation_status="noticed", due_date=n["value_date"],
                         notice_kind="distribution", commitment_id=self.commit[k])
                if ref in d["bank"]:  # the bank credit is its own confirmed row (no notice_kind) and does not supersede the notice, as the reader writes it; its amount is what arrived (M19: 262,500 against 275,000)
                    day, amount = d["bank"][ref]
                    self.ins("cash_movements", id=self.i("mov"), source_record_id=doc, portfolio_id=self.pf[PORTFOLIO_OF[k]], instrument_id=self.inst[k], movement_type="distribution", effective_date=day,
                             received_at=self.ts(day), recorded_at=self.ts(day), amount=amount, currency="USD", confirmation_status="confirmed", due_date=n["value_date"],
                             commitment_id=self.commit[k])
        for q in d["ddq"]:
            doc = self.document("ddq", q["title"], f"{q['month']}-01", uri=q["file"])
            self.fld(doc, "manager_name", text="Cedarpoint Ventures")
            for i, (topic, answer) in enumerate(q["answers"], 1):
                self.fld(doc, f"ddq: {topic}", text=answer, page=1)
        t = d["teaser"]
        tdoc = self.document("fund_teaser", t["name"] + " teaser", "2026-09-15", uri=t["file"])
        self.ins("deal_pipeline", id=self.i("deal"), source_record_id=tdoc, source_document_id=tdoc, source_page=1, received_at=self.ts("2026-09-15"), recorded_at=self.ts("2026-09-15"),
                 deal_name=t["name"], manager_name=t["manager"], strategy=t["strategy"], asset_class=t["asset_class"], target_commitment=t["ticket"], currency="USD", stage="screening", stage_on="2026-09-15")
        m = d["meeting"]
        mdoc = self.document("meeting_note", m["title"], m["date"], uri="04_kestrel_ridge_onsite_2026-06-12.md")
        self.fld(mdoc, "counterparty", text=m["counterparty"])
        self.fld(mdoc, "meeting_date", text=str(m["date"]))
        nl = d["newsletter"]
        ndoc = self.document("newsletter", nl["title"], nl["date"], uri="kestrel_ridge_q3_2026_newsletter.pdf")
        self.fld(ndoc, "counterparty", text=KESTREL)
        self.fld(ndoc, "team_change", text=nl["team_change"])
        cash_inst: dict = {}
        for c in d["cash"]:
            cash_inst[c["account"]] = self.i("ins")
            self.ins("instruments", id=cash_inst[c["account"]], canonical_name=f"Cash {c['account']}", instrument_type="cash", currency=c["currency"], created_at=self.ts("2026-04-01"))
            self.ins("bank_accounts", id=self.i("ba"), source_record_id="bank statement", received_at=self.ts("2026-04-01"), recorded_at=self.ts("2026-04-01"), holder_kind="office", legal_entity_id=self.ent[c["entity"]], holder_name=ENTITY_NAME[c["entity"]], account_purpose="operating", bank_name="Office bank (synthetic)",
                     account_ref=c["account"], currency=c["currency"], cash_instrument_id=cash_inst[c["account"]], status="active")  # the office's own accounts (the 12); the desk and administrator views are not bank accounts
            self.ins("position_snapshots", id=self.i("pos"), source_record_id="bank statement", portfolio_id=self.pf[f"CASH-{c['entity']}"], instrument_id=cash_inst[c["account"]], position_date=ASOF,
                     as_of_at=self.ts(ASOF), received_at=self.ts(ASOF), recorded_at=self.ts(ASOF), quantity=c["balance"], source_market_value=c["balance"], currency=c["currency"], view_type="operational", data_status="Final")
        for day, rate in d["fx"]:
            self.ins("market_observations", id=self.i("obs"), source_record_id="fx file", series_key="USD/SGD", observation_type="fx_fixing", observed_at=f"{day} 16:00:00+00", received_at=f"{day} 16:00:00+00",
                     recorded_at=f"{day} 16:00:00+00", value=rate, base_currency="USD", quote_currency="SGD", quality_status="Final")

    # test-only additions ------------------------------------------------------------------------------------------------------------------------
    def sign_rule(self, code: str, max_pct: float):
        """A signed rule (test only: the office6m policy signs no private-markets limit)."""
        rid = self.i("rule")
        self.ins("business_rules", id=rid, rule_code=code, rule_type="policy", owner_user_id="u-1")
        self.ins("rule_versions", id=self.i("rv"), business_rule_id=rid, version_number=1, definition_text=code, parameters=f'{{"max_pct": {max_pct}}}', effective_from="2026-01-01",
                 approval_status="approved", approved_by="u-1")

    def hold(self, usd: int):
        """Net worth for the budget tests (test only): one liquid position."""
        iid = self.i("ins")
        self.ins("instruments", id=iid, canonical_name="Test liquid holding", instrument_type="listed_equity", currency="USD", created_at=self.ts(ASOF))
        self.ins("position_snapshots", id=self.i("pos"), source_record_id="test", portfolio_id=self.pf["EG-GROWTH"], instrument_id=iid, position_date=ASOF, as_of_at=self.ts(ASOF),
                 received_at=self.ts(ASOF), recorded_at=self.ts(ASOF), quantity=1, source_market_value=usd, currency="USD", view_type="operational", data_status="Final")

    # running a recipe ---------------------------------------------------------------------------------------------------------------------------
    def build(self, rid: str) -> list[dict]:
        r = R.recipe(rid)
        assert r, f"{rid} is still a stub"
        name = f"gold_{rid}"
        self.con.execute(f"drop table if exists {name}")
        self.con.execute(R.render(r, name))
        cur = self.con.execute(f"select * from {name}")
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


@pytest.fixture()
def office(data):
    return Office(data)


def by(rows, col):
    return {r[col]: r for r in rows}


def close(a, b, places=4):
    return round(float(a), places) == round(float(b), places)


# ---- the recipes are built, read only what they may, and tie out -----------------------------------------------------------------------------------

def test_the_invest_recipes_are_built_and_the_others_stay_stubs():
    stubs = {r["id"] for r in R.stubs()}
    assert {"watch_flags", "expected_distributions", "manager_score"} <= stubs  # cards 53, 71, 76 are outside the top 50
    for rid in MY_RECIPES:
        r = R.recipe(rid)
        assert r and r.get("status") != "stub", rid
        assert r.get("may_read") and r.get("never_read") is not None and r.get("formula") and r.get("grain") and r["sql"] and r.get("measure") and r.get("columns"), rid
        read = R.tables_read(R.render(r, "x"))
        assert read <= set(r["may_read"]), (rid, sorted(read - set(r["may_read"])))
        assert not read & set(r["never_read"]), rid
        assert not R.refusal(r, R.render(r, "x")), rid
        assert r["measure"] in r["columns"], rid  # the measure is a described column


@pytest.mark.parametrize("rid", MY_RECIPES)
def test_each_recipe_runs_ties_out_and_is_not_held(office, rid):
    office.sign_rule("allocation_private_markets", 60)  # so the budget recipe has its input; the tie-out is the same either way
    office.hold(100_000_000)
    rows = office.build(rid)
    assert rows, rid
    r = R.recipe(rid)
    t = R.tie_out(office.con, r, f"gold_{rid}")
    assert t is None or t["ok"], (rid, t)
    assert R.needs(office.con, r) is None, rid
    sql = R.render(r, "recheck").split(" as ", 1)[1] if False else None  # the recomputation is Decision 3's, proved in test_v3_recipes
    col = r["measure"]
    assert any(row[col] is not None for row in rows), (rid, col)


# ---- card 7: commitment pacing --------------------------------------------------------------------------------------------------------------------

def test_card7_unfunded_across_all_funds_with_call_7_counted(office):
    exp = KEYS["uc-007-pacing"]["questions"]["What's our unfunded commitment across all funds?"]["expected"]
    rows = office.build("commitments_by_fund")
    funds = by([r for r in rows if not r["is_total"]], "fund")
    assert len(funds) == 8
    for name, k in exp["by_fund"].items():
        assert (funds[name]["committed"], funds[name]["called"], funds[name]["unfunded"]) == (k["committed"], k["called"], k["unfunded"]), name
    total = next(r for r in rows if r["is_total"])
    assert total["unfunded"] == exp["total_unfunded"] == 14_600_000
    assert funds["Cedarpoint Ventures III"]["unfunded"] == exp["cedarpoint_iii_unfunded"] == 2_750_000
    assert funds["Cedarpoint Ventures III"]["noticed"] == 1_250_000  # call 7 is noticed, not recorded: the register still shows 6,000,000 called


def test_card7_shadow_commitment_rows_are_not_counted_as_unfunded(office, data):
    """r1 uc-007: placeholder rows (no register source, no called figure, no call) for commitments the register holds gave 98.85M committed, 58.6M unfunded."""
    for k, f in data["funds"].items():  # one placeholder per register line, and one for an investor the register does not list in that fund
        office.ins("commitments", id=office.i("cmt"), legal_entity_id=office.ent[f["entity"]], instrument_id=office.inst[k], commitment_amount=f["commitment"], currency="USD", recorded_at=office.ts(ASOF),
                   committed_on=f["committed_on"])
    k0 = next(iter(data["funds"]))
    other = next(c for c in ENTITY_NAME if c != data["funds"][k0]["entity"])
    office.ins("commitments", id=office.i("cmt"), legal_entity_id=office.ent[other], instrument_id=office.inst[k0], commitment_amount=6_000_000, currency="USD", committed_on="2023-09-20", recorded_at=office.ts(ASOF))
    rows = office.build("commitments_by_fund")
    total = next(r for r in rows if r["is_total"])
    assert total["unfunded"] == 14_600_000 and len(rows) == len(data["funds"]) + 1
    assert R.tie_out(office.con, R.recipe("commitments_by_fund"), "gold_commitments_by_fund")["ok"]


def test_card7_a_call_is_counted_once_whatever_its_state_and_month(office, data):
    funds = lambda: by([r for r in office.build("commitments_by_fund") if not r["is_total"]], "fund")  # noqa: E731
    c = funds()["Cedarpoint Ventures III"]
    assert (c["called"], c["noticed"]) == (7_250_000, 1_250_000)
    # the bank debit arrives: the same call is now paid, still counted once
    office.con.execute("update cash_movements set confirmation_status = 'confirmed' where commitment_id = ? and received_at >= '2026-10-13'", [office.commit["C"]])
    c = funds()["Cedarpoint Ventures III"]
    assert (c["called"], c["noticed"], c["unfunded"]) == (7_250_000, 0, 2_750_000)
    # a notice that came before the register date is in the register's called figure already: not added a second time
    office.con.execute("update cash_movements set received_at = '2026-10-01 12:00:00+00' where commitment_id = ? and received_at >= '2026-10-13'", [office.commit["C"]])
    c = funds()["Cedarpoint Ventures III"]
    assert (c["called"], c["noticed"], c["unfunded"]) == (6_000_000, 0, 4_000_000)


def test_card7_budget_is_held_when_the_policy_signs_none(office):
    exp = KEYS["uc-007-pacing"]["questions"]["Room to commit"]["expected"]
    assert exp["private_markets_budget"] is None
    r = R.recipe("private_markets_budget")
    assert office.build("private_markets_budget") == []  # nothing is guessed
    assert "no private-markets limit is signed" in R.needs(office.con, r).lower()


KEY41 = KEYS["uc-041-commitappr"]["questions"]["Whether the commitment fits the budget, limits and cash"]["expected"]
CASH_USD = Decimal(str(KEY41["cash_usd_equivalent"]))  # all 12 accounts at the 13 Oct fixing, from the key
NW_TEST = 100_000_000 + CASH_USD  # net worth in USD for the budget tests: the test holding plus the cash of every account, converted


def fix_on(data, day=ASOF) -> Decimal:
    """SGD per USD at the latest fixing on or before the day (from the fx files)."""
    return max((d, r) for d, r in data["fx"] if d <= day)[1]


def test_card7_budget_headroom_when_a_limit_is_signed(office, data):
    office.sign_rule("allocation_private_markets", 60)  # test-only rule, not the office's
    office.hold(100_000_000)
    nw = NW_TEST  # net worth counts the cash positions too, SGD accounts converted at the fixing
    (row,) = office.build("private_markets_budget")
    assert (row["currency"], row["net_worth"], row["limit_pct"], row["committed"], row["conversion_gaps"]) == ("USD", nw, 60, 54_850_000, 0)
    assert (row["budget"], row["headroom"]) == (round(nw * 60 / 100, 2), round(nw * 60 / 100 - 54_850_000, 2))


def test_budget_converts_commitments_in_another_currency(office, data):
    """A commitment in SGD counts in USD at the fixing, not as if it were USD (and the budget is one figure, not one per currency)."""
    office.sign_rule("allocation_private_markets", 60)
    office.hold(100_000_000)
    fund = data["funds"]["G"]
    office.con.execute("update commitments set currency = 'SGD' where id = ?", [office.commit["G"]])
    want = Decimal(54_850_000) - fund["commitment"] + fund["commitment"] / fix_on(data)
    (row,) = office.build("private_markets_budget")
    assert abs(row["committed"] - want) < Decimal("0.02") and row["conversion_gaps"] == 0
    office.con.execute("delete from market_observations")  # no fixing at all: the budget is not stated, never guessed
    (row,) = office.build("private_markets_budget")
    assert row["conversion_gaps"] > 0 and row["budget"] is None and row["headroom"] is None


# ---- card 25: what changed at Kestrel Ridge -------------------------------------------------------------------------------------------------------

def test_card25_timeline_since_the_last_meeting_newest_first(office):
    exp = KEYS["uc7-manager-diligence"]["questions"]["What changed at Kestrel Ridge since the last meeting?"]["expected"]
    rows = office.build("manager_timeline")
    st = sorted([r for r in rows if r["item_kind"] == "statement"], key=lambda r: (r["item_date"], r["fund"]), reverse=True)
    assert len(st) == exp["items_since_12_june"] == 9
    got = [(str(r["item_date"]), r["fund"], str(r["period"]), r["status_kind"], int(r["value"])) for r in st]
    want = sorted([(k["date"], k["fund"], k["period"], k["kind"], k["value"]) for k in exp["newest_first"]], key=lambda x: (x[0], x[1]), reverse=True)
    assert got == want
    amended = next(r for r in st if r["status_kind"] == "amended")
    assert (int(amended["restated_from"]), int(amended["value"])) == (exp["h1_july_restated_from"], exp["h1_july_restated_to"])
    replaced = {(r["fund"], str(r["period"]), r["status_kind"]): r["replaced_on"] for r in st if r["replaced_on"]}
    assert replaced == {("Kestrel Ridge Macro Fund", "2026-07-31", "final"): dt.date(2026, 8, 20)}  # the replaced statement stays (it did arrive) and says it was replaced
    team = [r for r in rows if r["item_kind"] == "newsletter"]
    assert len(team) == 1 and "Thomas Lindqvist left the firm" in team[0]["detail"] and team[0]["source"].endswith("newsletter")


# ---- card 34: screen a new fund --------------------------------------------------------------------------------------------------------------------

def test_card34_mandate_fit_numbers_and_a_policy_that_sets_no_limit(office):
    exp = KEYS["uc-034-prospect"]["questions"]["Whether to take the fund to diligence"]["expected"]
    (row,) = office.build("mandate_fit")
    assert (row["ticket"], row["uncalled_before"], row["uncalled_after"]) == (exp["minimum_ticket"], exp["uncalled_before"], exp["uncalled_after"])
    assert close(row["ticket_pct_of_uncalled"], exp["ticket_pct_of_current_uncalled"], 1) and row["asset_class"] == exp["asset_class"]
    assert exp["policy_limit_for_private_markets"] is None and row["private_markets_limit_pct"] is None and row["budget_status"] == "not set" and row["class_status"] == "not set"
    assert row["manager_held"] == 0


def test_card34_limits_when_signed(office, data):
    office.sign_rule("allocation_private_markets", 60)
    office.sign_rule("allocation_venture", 2)  # test-only: 2 percent of net worth for venture, nothing committed to venture yet
    office.hold(100_000_000)
    nw = NW_TEST
    (row,) = office.build("mandate_fit")
    assert (row["budget_room_after"], row["budget_status"]) == (round(nw * 60 / 100 - 54_850_000 - 2_000_000, 2), "within")
    assert (row["class_room_after"], row["class_status"]) == (round(nw * 2 / 100 - 2_000_000, 2), "within")
    office.con.execute("update deal_pipeline set target_commitment = 12000000")
    (row,) = office.build("mandate_fit")
    assert (row["budget_status"], row["class_status"], row["budget_room_after"]) == ("over", "over", round(nw * 60 / 100 - 54_850_000 - 12_000_000, 2))


# ---- card 35: questionnaires side by side ----------------------------------------------------------------------------------------------------------

def test_card35_five_answers_changed(office):
    exp = KEYS["uc-035-ddq"]["questions"]["Which answers differ from what the manager told us or from peers"]["expected"]
    rows = office.build("ddq_compare")
    assert len(rows) == 16 and sum(r["changed"] for r in rows) == exp["count"] == 5
    got = {r["topic"]: (r["previous_answer"], r["answer"]) for r in rows if r["changed"]}
    assert got == {k["question"]: (k["y2025"], k["y2026"]) for k in exp["differences"]}
    assert sum(r["open_item"] for r in rows) == 0


def test_card35_a_missing_answer_is_a_gap(office):
    office.con.execute("delete from extracted_fields where field_name = 'ddq: Audit firm' and document_id in (select id from documents where title like '%2026')")
    rows = office.build("ddq_compare")
    gap = [r for r in rows if r["open_item"]]
    assert [(r["topic"], r["answer"]) for r in gap] == [("Audit firm", None)]


def test_card40_and_card35_agree_when_a_questionnaire_is_replaced(office):
    ids = dict(office.con.execute("select title, id from documents where document_type = 'ddq'").fetchall())
    old, new = ids["Cedarpoint Ventures - Due Diligence Questionnaire 2025"], ids["Cedarpoint Ventures - Due Diligence Questionnaire 2026"]
    office.con.execute("update documents set supersedes_document_id = ? where id = ?", [old, new])  # the 2026 one replaces the 2025 one: nothing left to compare it with
    changed = sum(r["changed"] for r in office.build("ddq_compare"))
    memo = next(r for r in office.build("memo_support") if r["fund"] == "Cedarpoint Ventures III" and r["figure"] == "ddq_changes")
    assert changed == memo["value"] == 0


# ---- card 39: IRR, TVPI, DPI by fund ---------------------------------------------------------------------------------------------------------------

def test_card39_irr_tvpi_dpi_by_fund_match_the_key(office):
    exp = KEYS["uc-039-irr"]["questions"]["Which funds earned their place and which to stop adding to"]["expected"]["by_fund"]
    rows = by(office.build("fund_irr_tvpi"), "fund")
    assert set(rows) == set(exp)
    for name, k in exp.items():
        r = rows[name]
        assert close(r["irr_pct"], k["irr_pct_since_1_apr"], 2), (name, r["irr_pct"], k["irr_pct_since_1_apr"])
        assert close(r["tvpi"], k["tvpi"]) and close(r["dpi"], k["dpi"]), name
        assert int(r["latest_value"]) == k["latest_value"] and str(r["latest_period"]) == k["latest_period"], name
        assert r["irr_status"] == "ok" and r["history_gap"] == 0, name
    assert rows["Cedarpoint Ventures III"]["called"] == 6_000_000  # call 7 is noticed, not paid: not in TVPI
    assert rows["Cedarpoint Ventures III"]["latest_status"] == "amended" and rows["Evergreen Growth I"]["latest_status"] == "amended"


def test_card39_a_missing_call_makes_the_irr_incomplete(office):
    office.con.execute("delete from cash_movements where commitment_id = ? and received_at < '2026-07-01' and notice_kind = 'capital_call'", [office.commit["A"]])  # Growth I call 11 (and its fee)
    rows = by(office.build("fund_irr_tvpi"), "fund")
    assert rows["Evergreen Growth I"]["irr_status"] == "incomplete" and rows["Evergreen Growth I"]["history_gap"] == 500_000
    assert [n for n, r in rows.items() if r["irr_status"] != "ok"] == ["Evergreen Growth I"]


def test_card39_a_distribution_without_its_bank_credit_makes_the_irr_incomplete(office):
    n = office.con.execute("select count(*) from cash_movements where movement_type = 'distribution' and confirmation_status = 'confirmed' and commitment_id = ?", [office.commit["A"]]).fetchone()[0]
    assert n == 1
    office.con.execute("update cash_movements set supersedes_cash_movement_id = null where movement_type = 'distribution' and confirmation_status = 'confirmed' and commitment_id = ?", [office.commit["A"]])
    office.con.execute("delete from cash_movements where movement_type = 'distribution' and confirmation_status = 'confirmed' and commitment_id = ?", [office.commit["A"]])
    rows = by(office.build("fund_irr_tvpi"), "fund")
    assert rows["Evergreen Growth I"]["irr_status"] == "incomplete" and rows["Evergreen Growth I"]["distributions_not_received"] == 1


# ---- card 40: the figures cited in the memo --------------------------------------------------------------------------------------------------------

def test_card40_memo_figures_trace_to_files(office):
    exp = KEYS["uc-040-icmemo"]["questions"]["Whether to recommend the commitment"]["expected"]
    rows = [r for r in office.build("memo_support") if r["fund"] == exp["fund"]]
    f = {r["figure"]: r for r in rows}
    assert (f["commitment"]["value"], f["called"]["value"], f["unfunded"]["value"]) == (exp["commitment"], exp["called_incl_call_7"], exp["unfunded"])
    assert (f["latest_value"]["value"], str(f["latest_value"]["as_at"]), f["latest_value"]["detail"]) == (exp["latest_value"], exp["latest_period"], exp["statement_kind"])
    assert f["fee_in_call"]["value"] == exp["fee_in_call_7"]
    assert f["ddq_changes"]["value"] == exp["ddq_changes_2025_to_2026"]
    assert all(r["traced"] == 1 for r in rows) and "cedarpoint_C_2026-06-30_amended" in f["latest_value"]["source"]


def test_card40_a_figure_without_a_file_is_untraced(office):
    office.con.execute("update commitments set source_record_id = null where id = ?", [office.commit["C"]])
    rows = [r for r in office.build("memo_support") if r["fund"] == "Cedarpoint Ventures III" and r["traced"] == 0]
    assert {r["figure"] for r in rows} == {"commitment", "called", "unfunded"}


# ---- card 41: approve a new commitment -------------------------------------------------------------------------------------------------------------

def test_card41_budget_limit_and_cash_tests(office):
    exp = KEYS["uc-041-commitappr"]["questions"]["Whether the commitment fits the budget, limits and cash"]["expected"]
    (row,) = office.build("commit_check")
    assert (row["new_commitment"], row["uncalled_after"]) == (exp["new_commitment"], exp["uncalled_after"])
    assert float(row["cash_usd"]) == exp["cash_usd_equivalent"] and float(row["cash_cover_pct"]) == exp["cash_cover_of_uncalled_after_pct"]
    assert row["cash_status"] == "short" and row["budget_status"] == "not set" and exp["budget"] == "not set in policy v2026.1" and row["cash_unconverted"] == 0
    assert row["class_status"] == "not set" and row["conversion_gaps"] == 0 and "no signed pacing rule" in row["need_basis"]


def test_card41_commitments_in_another_currency_count_in_full_and_the_deal_is_not_dropped(office, data):
    exp = KEY41
    fund = data["funds"]["G"]  # Evergreen Credit III, no call noticed: unfunded = commitment less the register's called figure
    office.con.execute("update commitments set currency = 'SGD' where id = ?", [office.commit["G"]])
    unf = fund["commitment"] - fund["called"]
    (row,) = office.build("commit_check")
    want = exp["uncalled_after"] - unf + unf / fix_on(data) + 0  # the key's uncalled, with this fund's share converted
    assert abs(row["uncalled_after"] - Decimal(want).quantize(Decimal("0.01"))) < Decimal("0.02")
    # a deal in another currency is converted, not dropped
    office.con.execute("update deal_pipeline set currency = 'SGD'")
    (row,) = office.build("commit_check")
    assert row["new_commitment"] == exp["new_commitment"] and abs(row["uncalled_after"] - (Decimal(want) - exp["new_commitment"] + Decimal(exp["new_commitment"]) / fix_on(data))) < Decimal("0.02")
    # no fixing: the tests are not stated (and say so), never a number
    office.con.execute("delete from market_observations")
    (row,) = office.build("commit_check")
    assert (row["cash_status"], row["uncalled_after"], row["cash_usd"]) == ("not stated", None, None)


# ---- card 49: fees paid to each manager ------------------------------------------------------------------------------------------------------------

def test_card49_fees_and_fee_drag_by_manager(office):
    exp = KEYS["uc-049-feedrag"]["questions"]["Whether a manager earns its fees"]["expected"]["by_manager"]
    rows = by(office.build("fee_drag"), "manager")
    assert set(rows) == set(exp)
    for name, k in exp.items():
        r = rows[name]
        assert (r["fees_paid"], r["net_gain"], r["gross_gain"]) == (k["fees_paid_via_calls"], k["net_gain_since_1_apr"], k["gross_gain"]), name
        assert (r["fee_drag_pct"] is None) if k["fee_drag_pct"] is None else close(r["fee_drag_pct"], k["fee_drag_pct"], 2), name
    # M08 is in the MANIFEST, not in the key: the excess is worked out here from the notices and the fund terms files (fee on the notice less commitment x rate)
    manifest = (FIX / "MANIFEST.md").read_text(encoding="utf-8")
    assert "excess 9,375.00" in manifest
    excess: dict = {}
    for n in office.d["notices"]:
        if n["kind"] == "call" and n["fee"]:
            f = office.d["funds"][n["key"]]
            excess[f["manager"]] = excess.get(f["manager"], 0) + max(n["fee"] - f["commitment"] * f["fee_pct"] / 100, 0)
    assert {m: r["fees_above_terms"] for m, r in rows.items()} == {m: excess.get(m, 0) for m in rows} and rows["Bluewater Capital"]["fees_above_terms"] == 9_375
    assert all(r["fee_rows_without_terms"] == 0 and r["expected_fees"] is not None for r in rows.values())


def test_card49_missing_terms_are_not_zero_excess(office):
    office.con.execute("delete from extracted_fields where field_name = 'management_fee_rate'")
    rows = by(office.build("fee_drag"), "manager")
    assert all(r["fees_above_terms"] is None and r["expected_fees"] is None and r["fee_rows_without_terms"] > 0 for r in rows.values())
    assert count(office, "uc-049-feedrag-no-terms") == 4 and count(office, "uc-049-feedrag-above-terms") == 0
    # terms that are not on the commitment are not used either (no rule is invented)
    office.con.execute("insert into extracted_fields (id, organization_id, document_id, field_name, value_numeric, page_number, confidence, review_status) "
                       "select 'f-' || id, organization_id, id, 'management_fee_rate', 0.5, 1, 'high', 'confirmed' from documents where document_type = 'fund_terms'")
    office.con.execute("update extracted_fields set value_text = 'invested capital' where field_name = 'fee_basis'")
    assert all(r["fees_above_terms"] is None for r in office.build("fee_drag").__iter__())


# ---- the signals --------------------------------------------------------------------------------------------------------------------------------------

def signals() -> dict:
    out = {}
    for card in CARDS:
        for p in sorted((PACK / "signals").glob(f"{card}-*.yaml")):
            s = yaml.safe_load(p.read_text(encoding="utf-8"))
            if isinstance(s.get("trigger"), dict) and True in s["trigger"]:
                s["trigger"] = {("on" if k is True else k): v for k, v in s["trigger"].items()}
            s["_card"], s["_file"] = card, p.name
            out[s["id"]] = s
    return out


def role_ids() -> set:
    ids = {r["id"] for r in yaml.safe_load((PACK / "role_builds.yaml").read_text(encoding="utf-8"))["roles"]}
    for p in (PACK / "builds").glob("*.yaml"):
        ids |= {r["id"] for r in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("roles") or []}
    return ids


def fires(sig: dict, row: dict) -> bool:
    """The condition on one row of the figure the signal watches, as the engine reads it (a missing field skips the signal)."""
    need = [f for i in sig["inputs"] if i["kind"] == "doc" for f in i["fields"]]
    if any(row.get(f) in (None, "") for f in need):
        return False
    funcs = {"abs": abs, "min": min, "max": max, "round": round, "last4": S.last4, "num": S.num}
    doc = {f: S._dec(row[f]) if not isinstance(row[f], (dt.date, Decimal)) else row[f] for f in need}
    ns = {"doc": doc}
    for k, e in (sig.get("let") or {}).items():
        ns[k] = S.calc(e, ns, funcs)
    return bool(S.calc(sig["condition"], ns, funcs))


EXPECTED_SIGNALS = {  # id -> (recipe, severity, role)
    "uc-007-pacing-unfunded": ("commitments_by_fund", "info", "cio"), "uc-007-pacing-over-budget": ("mandate_fit", "problem", "cio"),
    "uc7-manager-diligence-team-change": ("manager_timeline", "needs", "investment_analyst"), "uc7-manager-diligence-restated": ("manager_timeline", "problem", "investment_analyst"),
    "uc-034-prospect-screened": ("mandate_fit", "needs", "investment_analyst"), "uc-034-prospect-known-manager": ("mandate_fit", "info", "investment_analyst"),
    "uc-034-prospect-class-over": ("mandate_fit", "problem", "cio"),
    "uc-035-ddq-differences": ("ddq_compare", "info", "investment_analyst"), "uc-035-ddq-fee-answer": ("ddq_compare", "needs", "investment_analyst"),
    "uc-035-ddq-open-item": ("ddq_compare", "problem", "investment_analyst"),
    "uc-039-irr-by-fund": ("fund_irr_tvpi", "info", "investment_analyst"), "uc-039-irr-incomplete": ("fund_irr_tvpi", "problem", "investment_analyst"),
    "uc-040-icmemo-figure-source": ("memo_support", "info", "cio"), "uc-040-icmemo-untraced": ("memo_support", "problem", "investment_analyst"),
    "uc-041-commitappr-tests": ("commit_check", "needs", "cio"), "uc-041-commitappr-cosign": ("commit_check", "needs", "principal"),
    "uc-041-commitappr-cash-short": ("commit_check", "problem", "cfo"), "uc-041-commitappr-test-not-on-record": ("commit_check", "needs", "cio"),
    "uc-049-feedrag-share": ("fee_drag", "info", "fund_accountant"), "uc-049-feedrag-above-terms": ("fee_drag", "problem", "fund_accountant"),
    "uc-049-feedrag-no-terms": ("fee_drag", "needs", "fund_accountant"),
}
EXCEPTIONS = {"uc-007-pacing-over-budget", "uc7-manager-diligence-restated", "uc-034-prospect-class-over", "uc-035-ddq-open-item", "uc-039-irr-incomplete", "uc-040-icmemo-untraced",
              "uc-041-commitappr-cash-short", "uc-049-feedrag-above-terms", "uc-041-commitappr-test-not-on-record", "uc-049-feedrag-no-terms"}


def test_every_card_has_signals_a_known_role_and_an_exception():
    sigs = signals()
    assert set(sigs) == set(EXPECTED_SIGNALS)
    roles = role_ids()
    for sid, (rid, sev, role) in EXPECTED_SIGNALS.items():
        s = sigs[sid]
        assert s["_file"] == f"{sid}.yaml" and s["suggestion"] is True
        assert S.check(s, {r: r for r in roles}) is None, (sid, S.check(s, {r: r for r in roles}))
        assert s["trigger"] == {"on": "figure_changed", "figure": rid} or s["trigger"]["on"] == "action_done", sid
        assert (s["severity"], s["route_to"]) == (sev, role), sid
        assert bool(s.get("hold")) == (sid in EXCEPTIONS), sid  # a hold on every exception row, on nothing else
        assert not re.search(r"\b(Sam|Helen|Raj|Mei|Daniel|Grace|Sofia)\b", yaml.safe_dump(s)), sid  # a role, never a person
    for card in CARDS:
        assert any(sid.startswith(card + "-") and sid in EXCEPTIONS for sid in sigs), card


def test_signal_fields_are_columns_of_the_figure_they_watch(office):
    cols = {}
    for rid in MY_RECIPES:
        office.sign_rule("allocation_private_markets", 60)
        cols[rid] = set(office.build(rid)[0])
    for sid, s in signals().items():
        if s["trigger"]["on"] != "figure_changed":
            continue
        have = cols[s["trigger"]["figure"]]
        for i in s["inputs"]:
            assert set(i["fields"]) <= have, (sid, set(i["fields"]) - have)
        used = set(re.findall(r"doc\.(\w+)", " ".join([s["condition"], *(s.get("let") or {}).values(), s["message"], s["subject"]])))
        assert used <= {f for i in s["inputs"] for f in i["fields"]}, (sid, used)


def count(office, sid: str) -> int:
    s = signals()[sid]
    return sum(fires(s, r) for r in office.build(EXPECTED_SIGNALS[sid][0]))


def test_the_normal_signals_fire_on_the_office_data(office):
    got = {sid: count(office, sid) for sid in ("uc-007-pacing-unfunded", "uc7-manager-diligence-team-change", "uc-034-prospect-screened", "uc-035-ddq-differences", "uc-035-ddq-fee-answer",
                                                  "uc-039-irr-by-fund", "uc-049-feedrag-share")}
    assert got == {"uc-007-pacing-unfunded": 1, "uc7-manager-diligence-team-change": 1, "uc-034-prospect-screened": 1, "uc-035-ddq-differences": 5, "uc-035-ddq-fee-answer": 1,
                   "uc-039-irr-by-fund": 8, "uc-049-feedrag-share": 4}  # fee share: the four managers; the two with a loss say the share is not stated


def test_the_exception_signals_fire_on_the_planted_rows(office):
    assert count(office, "uc7-manager-diligence-restated") == 1  # M03: Kestrel Macro July restated 7,050,000 to 7,012,500
    assert count(office, "uc-041-commitappr-cash-short") == 1  # cash cover 37.08 percent of the uncalled after the ticket
    assert count(office, "uc-049-feedrag-above-terms") == 1  # M08: Bluewater, 9,375 above the terms
    # budget not on record and cash short: no approve prompt and no co-sign page; the CIO gets the "not on record" prompt instead
    assert count(office, "uc-041-commitappr-tests") == 0 and count(office, "uc-041-commitappr-cosign") == 0 and count(office, "uc-041-commitappr-test-not-on-record") == 1
    assert count(office, "uc-049-feedrag-no-terms") == 0
    # no limit is signed in the policy, so the limit exceptions stay quiet rather than guess
    assert count(office, "uc-007-pacing-over-budget") == 0 and count(office, "uc-034-prospect-class-over") == 0 and count(office, "uc-034-prospect-known-manager") == 0
    assert count(office, "uc-035-ddq-open-item") == 0 and count(office, "uc-039-irr-incomplete") == 0 and count(office, "uc-040-icmemo-untraced") == 0
    assert count(office, "uc-040-icmemo-figure-source") == 2  # the two funds whose latest value is an amended statement (Growth I and Cedarpoint III), not every figure


def test_the_approve_prompt_needs_a_signed_budget_and_cash_that_covers(office):
    office.sign_rule("allocation_private_markets", 60)
    office.hold(100_000_000)
    office.con.execute("update deal_pipeline set target_commitment = 2000000")
    # budget within a signed limit but the cash is short: no approve prompt, the cash-short exception
    assert count(office, "uc-041-commitappr-tests") == 0 and count(office, "uc-041-commitappr-cash-short") == 1 and count(office, "uc-041-commitappr-test-not-on-record") == 0
    # add cash that covers the 16.6 million need
    office.con.execute("update position_snapshots set source_market_value = source_market_value + 20000000, quantity = quantity + 20000000 where currency = 'USD' and "
                       "instrument_id in (select id from instruments where instrument_type = 'cash') and id = (select min(id) from position_snapshots where currency = 'USD' and instrument_id in (select id from instruments where instrument_type = 'cash'))")
    assert count(office, "uc-041-commitappr-tests") == 1 and count(office, "uc-041-commitappr-cosign") == 1 and count(office, "uc-041-commitappr-cash-short") == 0
    # a budget that the commitment breaks: no approve prompt, no co-sign page
    office.con.execute("update deal_pipeline set target_commitment = 120000000")
    assert count(office, "uc-041-commitappr-tests") == 0 and count(office, "uc-041-commitappr-cosign") == 0


def test_the_exception_signals_fire_when_their_condition_is_planted(office):
    office.sign_rule("allocation_private_markets", 60)
    office.sign_rule("allocation_venture", 2)
    office.hold(100_000_000)
    office.con.execute("update deal_pipeline set target_commitment = 12000000")
    office.con.execute("delete from extracted_fields where field_name = 'ddq: Audit firm' and document_id in (select id from documents where title like '%2026')")
    office.con.execute("delete from cash_movements where commitment_id = ? and received_at < '2026-07-01' and notice_kind = 'capital_call'", [office.commit["A"]])
    office.con.execute("update commitments set source_record_id = null where id = ?", [office.commit["C"]])
    office.con.execute("update instruments set manager_name = 'Harborlight Capital Partners' where canonical_name = 'Evergreen Credit III'")
    assert count(office, "uc-007-pacing-over-budget") == 1 and count(office, "uc-034-prospect-class-over") == 1 and count(office, "uc-034-prospect-known-manager") == 1
    assert count(office, "uc-035-ddq-open-item") == 1 and count(office, "uc-039-irr-incomplete") == 1 and count(office, "uc-040-icmemo-untraced") == 3


# ---- the persona builds ----------------------------------------------------------------------------------------------------------------------------

def builds() -> dict:
    d = yaml.safe_load((PACK / "builds" / "invest.yaml").read_text(encoding="utf-8"))
    assert d["template"] == "family_office@1"
    return {b["id"]: (r["id"], b) for r in d["roles"] for b in r["builds"]}


def numbers(v) -> set:
    out = set()
    if isinstance(v, dict):
        for x in v.values():
            out |= numbers(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            out |= numbers(x)
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        out.add(round(float(v), 4))
    elif isinstance(v, str):
        out.add(v.strip())
    return out


def test_each_card_has_one_runnable_build_with_numbers_from_its_key():
    b = builds()
    no_build = {"uc7-manager-diligence"}  # card 25 keeps its build in role_builds.yaml
    assert set(b) == set(CARDS) - no_build
    existing = {x["id"] for r in yaml.safe_load((PACK / "role_builds.yaml").read_text(encoding="utf-8"))["roles"] for x in r["builds"]}
    assert not set(b) & existing and "uc7-manager-diligence" in existing
    for cid, (role, build) in b.items():
        assert role in role_ids() and build.get("say") and build.get("title") and build.get("dashboard") and build["skills"]
        assert len(build["say"]) > 80 and "?" not in build["say"][:20]
        assert build["check"]["ask"].endswith("?") and build["check"]["expect"], cid
        key = numbers(list(KEYS[cid]["questions"].values()))
        for e in build["check"]["expect"]:
            n = re.sub(r"[,%]", "", e)
            assert e in key or (re.fullmatch(r"-?[\d.]+", n) and round(float(n), 4) in key), (cid, e)
        assert build["files"], cid
        for f in build["files"]:
            assert f.startswith("office6m:") and glob.glob(str(FIX / f[len("office6m:"):])), (cid, f)
        want = {re.sub(r"^\*/", "", g) for g in KEYS[cid]["input_files"]}
        assert any(re.sub(r"^office6m:\*/", "", f).removeprefix("office6m:") in want or f.removeprefix("office6m:").removeprefix("*/") in want for f in build["files"]), cid
