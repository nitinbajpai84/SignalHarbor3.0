"""W1 'operate' domain (cards uc-001-noticelog, uc10-pipeline, uc-016-schemadrift, uc3-statements-inbox, uc-022-amendlog, uc-026-stmtadmin,
uc2-recon-break-desk, uc-029-closeck): every recipe of recipes/operate.yaml for these cards is run over the synthetic Evergreen Office files (office6m) loaded into
a small DuckDB with the company model's tables, and the answer-key numbers (tests/v1/fixtures/office6m/answer_keys.yaml) are read from the keys file, never typed.
The files are read here with openpyxl / pypdf / csv and inserted row by row: the real loaders (e0c_load, v3_pdf) are not called (see 'Needs' in docs/v3/w1/build-operate.md).
Also checks the signal yaml (format of the signal engine) and the persona builds. Synthetic data only."""
import ast
import csv
import functools
import glob
import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb
import openpyxl
import pypdf
import pytest
import yaml

from sh_platform.v1 import v3_recipes as R

ROOT = Path(__file__).resolve().parents[2]
OFFICE = ROOT / "tests" / "v1" / "fixtures" / "office6m"
PACK = ROOT / "packs" / "family_office" / "1"
DDL = ROOT / "docs" / "v2" / "evidence-to-action-mvp.duckdb.sql"
KEYS = yaml.safe_load((OFFICE / "answer_keys.yaml").read_text(encoding="utf-8"))["keys"]
ORG = "org-1"
ENT = {"EG-HOLD": "Evergreen Holdings", "EG-TRUST": "Evergreen Family Trust", "EG-B": "Entity B"}
PORT = {"EG-GROWTH": "EG-HOLD", "EG-PRIVATE": "EG-HOLD", "EG-B-OPS": "EG-B", "EG-FUNDS": "EG-TRUST", "EG-LIQUID": "EG-TRUST"}
DEFAULTS = {
    "documents": dict(source_system_id="sys-doc", access_group_id="grp", original_uri="file", content_hash="h", processing_status="registered", contains_personal_data=False),
    "extracted_fields": dict(confidence="high", review_status="unreviewed"),
    "cash_movements": dict(recorded_at="2026-10-13 12:00:00+00"),
    "exceptions": dict(materiality_status="material", status="open"),
    "expected_statements": dict(frequency="monthly", source="schedule", recorded_at="2026-04-01 00:00:00+00"),
    "valuation_observations": dict(approval_status="unapproved"),
    "source_batches": dict(validation_status="loaded"),
    "source_records": dict(record_type="row", raw_payload_uri="file", content_hash="h", quality_status="good"),
    "source_systems": dict(is_active=True),
    "position_snapshots": dict(view_type="operational"),
    "instruments": dict(created_at="2026-04-01 00:00:00+00"),
    "users": dict(is_active=True, created_at="2026-04-01 00:00:00+00"),
}
_n = [0]


def nid() -> str:
    _n[0] += 1
    return f"id-{_n[0]:07d}"


def ts(d, t="12:00:00") -> str:
    return f"{d} {t}+00"


def month_end(m: str) -> date:
    y, mo = int(m[:4]), int(m[5:7])
    return (date(y + (mo == 12), mo % 12 + 1, 1)) - timedelta(days=1)


class Office:
    """A small company model in memory: the DDL of the model, rows put in by the loaders below."""

    def __init__(self):
        self.con = duckdb.connect()
        self.con.execute("set TimeZone='UTC'")
        self.con.execute(DDL.read_text(encoding="utf-8"))
        self.cache: dict = {}

    def put(self, table: str, **v) -> str:
        v = {**DEFAULTS.get(table, {}), **v}
        v.setdefault("id", nid())
        v.setdefault("organization_id", ORG)
        self.con.execute(f"insert into {table} ({','.join(v)}) values ({','.join('?' * len(v))})", list(v.values()))
        return v["id"]

    def once(self, key, make):
        if key not in self.cache:
            self.cache[key] = make()
        return self.cache[key]

    def entity(self, code):
        return self.once(("e", code), lambda: self.put("legal_entities", entity_code=code, entity_name=ENT[code], base_currency="USD"))

    def portfolio(self, code, ent=None):
        return self.once(("p", code), lambda: self.put("portfolios", legal_entity_id=self.entity(ent or PORT[code]), portfolio_code=code, portfolio_name=code, base_currency="USD"))

    def inst(self, name, itype="fund", ccy="USD"):
        return self.once(("i", name), lambda: self.put("instruments", canonical_name=name, instrument_type=itype, currency=ccy))

    def record(self, stype, code=None):
        """(source_system_id, source_record_id) of a source system of this type; one batch and one record stand for all its rows."""
        def make():
            sid = self.put("source_systems", source_code=code or stype, source_name=code or stype, source_type=stype)
            bid = self.put("source_batches", source_system_id=sid, batch_reference=code or stype, received_at=ts("2026-10-13"))
            return sid, self.put("source_records", source_batch_id=bid, received_at=ts("2026-10-13"), recorded_at=ts("2026-10-13"))
        return self.once(("r", stype, code), make)

    def doc(self, dtype, title, received, instrument=None, valuation=None, status="final", date_=None, record=None, fields=()):
        did = self.put("documents", document_type=dtype, title=title, instrument_id=instrument, valuation_date=valuation, document_date=date_, received_at=ts(received),
                       recorded_at=ts(received), document_status=status, source_record_id=record)
        for name, text, num, ccy, page in fields:
            self.put("extracted_fields", document_id=did, field_name=name, value_text=text, value_numeric=num, currency=ccy, page_number=page)
        return did

    def rows(self, sql: str) -> list[dict]:
        cur = self.con.execute(sql)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]

    def build(self, rid: str, dims=None, name=None) -> list[dict]:
        """Run the recipe's SQL as Span would (the same render), return the ready table's rows."""
        r = R.recipe(rid)
        assert r, f"recipe {rid} is not ready"
        name = name or f"gold_{rid}"
        self.con.execute(f"drop table if exists {name}")
        assert not R.needs(self.con, r), R.needs(self.con, r)
        self.con.execute(R.render(r, name, dims))
        return self.rows(f"select * from {name}")

    def tie(self, rid: str, name=None) -> dict:
        return R.tie_out(self.con, R.recipe(rid), name or f"gold_{rid}")


def rel(p) -> str:
    return str(p).replace("\\", "/").split("office6m/")[1]


def text_of(path) -> str:
    return "\n".join(p.extract_text() for p in pypdf.PdfReader(str(path)).pages)


def num(s: str) -> Decimal:
    return Decimal(s.replace(",", ""))


def day(s: str) -> date:
    for f in ("%d %B %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), f).date()
        except ValueError:
            pass
    raise ValueError(s)


@functools.lru_cache(maxsize=1)
def statements() -> list[dict]:
    """Every manager statement PDF: fund, period end, status, closing capital account balance, file."""
    out = []
    for f in sorted(OFFICE.glob("*/manager_statements/*.pdf")):
        t = text_of(f)
        out.append(dict(file=rel(f), fund=re.search(r"Fund: (.+)", t).group(1).strip(), period=day(re.search(r"Statement date \(period end\): (.+)", t).group(1)),
                        status=re.search(r"Status: (\w+)", t).group(1).lower(), closing=num(re.search(r"Closing capital account balance\s+([\d,.]+)", t).group(1)),
                        key=re.search(r"(?:^|[_/])([A-Z]\d?)_\d{4}", f.name).group(1)))
    return out


@functools.lru_cache(maxsize=1)
def received_log() -> list[dict]:
    return list(csv.DictReader((OFFICE / "received_log_all.csv").open(encoding="utf-8")))


@functools.lru_cache(maxsize=1)
def notices() -> list[dict]:
    out = []
    for f in sorted(OFFICE.glob("*/notices/*_call*.pdf")):
        t = text_of(f)
        g = lambda p: (re.search(p, t) or [None, None])[1]  # noqa: E731
        fee = g(r"Management fee[^\n]*USD ([\d,.]+)")
        out.append(dict(file=rel(f), notice_date=day(f.name[:10]), call_no=int(re.search(r"call(\d+)", f.name).group(1)), fund=g(r"Fund: (.+)").strip(), investor=g(r"To: (.+) \(limited").strip(),
                        amount=num(g(r"Amount to be paid by the investor\s+USD ([\d,.]+)")), due=day(g(r"Payment due date: (.+)")), new=num(g(r"New investments\s+USD ([\d,.]+)")),
                        fee=num(fee) if fee else None, account=g(r"Account: (\S+)"), page=1))
    return out


def load_notices(o: Office) -> None:
    """Documents with their extracted fields, and the call as a cash movement: noticed for the call the commitment register shows as 'noticed, not yet recorded'."""
    reg = openpyxl.load_workbook(next(OFFICE.glob("*/commitments/commitments_register_2026-10-13.xlsx")), data_only=True)["Register"]
    waiting = {r[2] for r in list(reg.iter_rows(values_only=True))[1:] if r[9]}
    latest = {}
    for n in notices():
        latest[n["fund"]] = max(latest.get(n["fund"], 0), n["call_no"])
    sysid, recid = o.record("manager", "notices")
    for n in notices():
        ins = o.inst(n["fund"])
        sr = o.put("source_records", source_batch_id=o.put("source_batches", source_system_id=sysid, batch_reference=n["file"], received_at=ts(n["notice_date"])),
                   received_at=ts(n["notice_date"]), recorded_at=ts(n["notice_date"]))
        fields = [("fund", n["fund"], None, None, 1), ("investor", n["investor"], None, None, 1), ("call_no", str(n["call_no"]), n["call_no"], None, 1),
                  ("amount", None, n["amount"], "USD", 1), ("due_date", n["due"].isoformat(), None, None, 1), ("new_investments", None, n["new"], "USD", 1),
                  ("bank_account", n["account"], None, None, 1)]
        if n["fee"] is not None:
            fields.append(("management_fee", None, n["fee"], "USD", 1))
        recv = n["notice_date"]
        o.doc("capital_call_notice", n["file"], recv, instrument=ins, record=sr, fields=fields)
        o.put("cash_movements", source_record_id=sr, portfolio_id=o.portfolio("EG-GROWTH" if n["investor"] == "Evergreen Holdings" else "EG-B-OPS"), instrument_id=ins, movement_type="capital_call",
              effective_date=n["due"], received_at=ts(recv), amount=-n["amount"], currency="USD", due_date=n["due"], notice_kind="call",
              confirmation_status="noticed" if (n["fund"] in waiting and n["call_no"] == latest[n["fund"]]) else "confirmed")


def load_statements(o: Office) -> None:
    """Manager and bank statements as documents with the date received from received_log_all.csv, the expected statements, and each manager statement's value as a
    valuation observation (a later statement of the same fund and period replaces the earlier)."""
    log = {r["file"]: r for r in received_log()}
    keymap = {s["key"]: s["fund"] for s in statements()}
    seen: dict = {}
    for s in sorted(statements(), key=lambda s: (log[s["file"]]["received_on"], s["file"])):
        ins = o.inst(s["fund"])
        did = o.doc("manager_statement", s["file"], log[s["file"]]["received_on"], instrument=ins, valuation=s["period"], status=s["status"])
        k = (ins, s["period"])
        seen[k] = o.put("valuation_observations", instrument_id=ins, evidence_document_id=did, valuation_date=s["period"], received_at=ts(log[s["file"]]["received_on"]),
              recorded_at=ts(log[s["file"]]["received_on"]), value_amount=s["closing"], currency="USD", supersedes_valuation_id=seen.get(k),
              valuation_type="manager_estimate" if s["status"] == "estimate" else "manager_final")
    done = set()
    for r in received_log():
        if r["kind"] == "manager_statement":
            key = re.search(r"(?:^|[_/])([A-Z]\d?)_\d{4}", r["file"]).group(1)
            ins = o.inst(keymap[key])
            period = day(r["period"])
            kind = "m"
        else:
            acct = re.search(r"([A-Z]{2,3}[-_][A-Z]{1,5}[-_][A-Z]{3})_\d{4}", r["file"]).group(1).replace("_", "-")
            ins = o.inst(acct, "cash")
            period = month_end(r["period"])
            kind = "b"
            if r["received_on"]:
                o.doc("bank_statement", r["file"], r["received_on"], instrument=ins, valuation=period)
        if (ins, period) not in done:
            done.add((ins, period))
            o.put("expected_statements", instrument_id=ins, period_end=period, due_date=day(r["expected_on"]))
    for f in sorted(OFFICE.glob("*/investment_reports/*.pdf")):
        issued = re.search(r"Issued: (\d{4}-\d{2}-\d{2})", text_of(f)).group(1)
        o.doc("investment_report", rel(f), issued, date_=issued)


def load_admin_pack(o: Office, month: str, header_into=None) -> int:
    f = next(OFFICE.glob(f"*/administrator_nav/administrator_export_{month}.xlsx"))
    wb = openpyxl.load_workbook(f, data_only=True)
    rows = list(wb["Positions"].iter_rows(values_only=True))
    as_of = date.fromisoformat(list(wb["NAV by portfolio"].iter_rows(values_only=True))[1][2])
    _, recid = o.record("administrator", "administrator")
    for r in rows[1:]:
        o.put("position_snapshots", source_record_id=recid, portfolio_id=o.portfolio(r[0]), instrument_id=o.inst(r[2], "equity" if r[0] == "EG-LIQUID" else "fund"),
              position_date=as_of, as_of_at=ts(as_of), received_at=ts(as_of), recorded_at=ts(as_of), quantity=r[3], source_market_value=r[5], currency=r[6], data_status=r[7])
    return len(rows) - 1


@pytest.fixture(scope="module")
def office() -> Office:
    o = Office()
    load_notices(o)
    load_statements(o)
    load_admin_pack(o, "2026-09")
    return o


# ---- card 1: uc-001-noticelog -----------------------------------------------------------------------------------------------------------

def test_card1_call_notice_fields_match_the_key(office):
    exp = KEYS["uc-001-noticelog"]["questions"]["Which fund, how much and by when?"]["expected"]
    rows = {(r["fund"], r["call_no"]): r for r in office.build("call_notice_fields")}
    r = rows[(exp["fund"], 7)]
    assert (r["investor"], r["amount"], r["currency"], str(r["due_date"]), r["new_investments"], r["management_fee"], r["account_ending"]) == (
        exp["investor"], Decimal(exp["amount_usd"]), "USD", exp["due"], Decimal(exp["new_investments"]), Decimal(exp["management_fee"]), exp["account_ending"])
    assert r["amount_page"] == 1 and len(rows) == len(notices())
    assert office.tie("call_notice_fields")["ok"]


def test_card1_notices_open_match_the_key(office):
    exp = KEYS["uc-001-noticelog"]["questions"]["Notices logged and not yet recorded"]["expected"]
    rows = office.build("notices_open")
    assert len(rows) == exp["count"] == 1 and exp["notices"] == ["CALL-C-7"]
    assert (rows[0]["fund"], rows[0]["call_no"], rows[0]["amount"]) == ("Cedarpoint Ventures III", 7, Decimal("1250000"))
    assert office.tie("notices_open")["ok"]


# ---- card 11: uc10-pipeline (recipe net_worth, hold.yaml) -------------------------------------------------------------------------------------

def test_card11_net_worth_by_portfolio_matches_the_key(office):
    exp = KEYS["uc10-pipeline"]["questions"]["What was the Evergreen Liquid portfolio worth at 30 September 2026?"]["expected"]
    r = R.recipe("net_worth")
    office.con.execute("drop table if exists gold_nw")
    office.con.execute(R.render(r, "gold_nw", ["portfolio"]))
    got = {x["portfolio"]: x["net_worth"] for x in office.rows("select * from gold_nw")}
    assert got == {k: Decimal(v) for k, v in exp["net_worth_by_portfolio"].items()} and got["EG-LIQUID"] == exp["evergreen_liquid"]
    assert R.tie_out(office.con, r, "gold_nw")["ok"]
    f = next(OFFICE.glob("*/administrator_nav/administrator_export_2026-09.xlsx"))
    rows_in = openpyxl.load_workbook(f, data_only=True)["Positions"].max_row - 1
    assert office.con.execute("select count(*) from position_snapshots").fetchone()[0] == rows_in == 32  # rows in equal rows out


# ---- card 16: uc-016-schemadrift ----------------------------------------------------------------------------------------------------------

TARGETS = {"Portfolio": ("portfolios", "portfolio_code"), "Admin Code": ("instrument_identifiers", "identifier_value"), "Instrument": ("instruments", "canonical_name"),
           "Quantity": ("position_snapshots", "quantity"), "Price": ("market_observations", "price"), "Market Value": ("position_snapshots", "source_market_value"),
           "Currency": ("position_snapshots", "currency"), "Valuation Status": ("position_snapshots", "data_status"), "Valuation Date": ("position_snapshots", "position_date")}


def headers(month):
    f = next(OFFICE.glob(f"*/administrator_nav/administrator_export_{month}.xlsx"))
    return [c for c in next(openpyxl.load_workbook(f, data_only=True)["Positions"].iter_rows(values_only=True))]


def test_card16_renamed_column_is_found_and_the_old_name_counted():
    exp = KEYS["uc-016-schemadrift"]["questions"]["The administrator renamed a column. What breaks, and is the new mapping safe?"]["expected"]
    o = Office()
    sysid, _ = o.record("administrator", "administrator")
    old = headers("2026-05")
    v1 = o.put("sheet_mappings", source_system_id=sysid, file_pattern="administrator_export_*.xlsx", sheet_name="Positions", header_row=1, version_number=1, mapping_status="approved")
    for h in old:
        o.put("sheet_mapping_columns", sheet_mapping_id=v1, source_column=h, target_table=TARGETS[h][0], target_field=TARGETS[h][1])
    # the 30 June pack: its header lined up with the approved one by position gives the proposal (version 2)
    new = headers("2026-06")
    v2 = o.put("sheet_mappings", source_system_id=sysid, file_pattern="administrator_export_*.xlsx", sheet_name="Positions", header_row=1, version_number=2, mapping_status="proposed")
    for h_old, h_new in zip(old, new):
        o.put("sheet_mapping_columns", sheet_mapping_id=v2, source_column=h_new, target_table=TARGETS[h_old][0], target_field=TARGETS[h_old][1])
    on_old = 0
    for m in ("2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"):
        held = m == "2026-06"
        on_old += headers(m) == old
        o.put("source_batches", source_system_id=sysid, batch_reference=m, received_at=ts(month_end(m)), sheet_mapping_id=v2 if held else v1, validation_status="held" if held else "loaded")
    rows = o.build("columns_changed")
    assert len(rows) == 1
    r = rows[0]
    assert (r["old_name"], r["new_name"], r["change"], r["target_field"]) == (exp["old_name"], exp["new_name"], "renamed", "position_snapshots.source_market_value")
    assert exp["file"] == "administrator_export_2026-06.xlsx" and headers("2026-06")[5] == exp["new_name"]
    # the key says 5; the fixture has six packs (March, April, May, July, August, September) that keep the old name: reported under Needs
    assert r["batches_on_old_name"] == on_old == 6
    assert o.tie("columns_changed")["ok"]


# ---- card 19: uc3-statements-inbox ----------------------------------------------------------------------------------------------------------

def test_card19_missing_late_and_bank_statements_match_the_key(office):
    q = KEYS["uc3-statements-inbox"]["questions"]
    rows = office.build("statement_timeliness")
    mgr = [r for r in rows if r["kind"] == "manager statement"]
    missing = [r for r in mgr if r["status"] == "missing"]
    e = q["Which statement is missing and how overdue is it?"]["expected"]["missing"][0]
    assert len(missing) == 1 and (missing[0]["statement_of"], str(missing[0]["period_end"]), str(missing[0]["due_date"]), missing[0]["business_days_overdue"]) == (
        e["fund"], e["period"], e["due"], e["business_days_overdue_13_oct"])
    late = sorted((r["statement_of"], str(r["period_end"]), str(r["due_date"]), str(r["received_on"]), r["business_days_late"]) for r in mgr if r["status"] == "late")
    want = sorted((x["fund"], x["period"], x["due"], x["received"], x["business_days_late"]) for x in q["Late statements"]["expected"]["late"])
    assert late == want and len(late) == 5
    bank = sorted((r["statement_of"], r["period_end"].strftime("%Y-%m"), str(r["due_date"]), str(r["received_on"] or ""), r["status"]) for r in rows if r["kind"] == "bank statement" and r["status"] != "on_time")
    keyed = sorted((re.search(r"([A-Z]+[-_][A-Z]+[-_][A-Z]+)", x[0].split("/")[-1]).group(1).replace("_", "-"), x[2], x[3], x[4], "late" if x[5] == "late" else "missing")
                   for x in q["Bank statements late or missing"]["expected"]["rows"])
    assert bank == keyed
    assert office.tie("statement_timeliness")["ok"]


# ---- card 22: uc-022-amendlog ---------------------------------------------------------------------------------------------------------------

def test_card22_amendments_match_the_key(office):
    exp = KEYS["uc-022-amendlog"]["questions"]["Which earlier value is replaced and whether reports already issued need a note"]["expected"]
    rows = office.build("amendments_open")
    got = {r["fund"]: r for r in rows}
    assert len(rows) == len(exp["amendments"]) == 3
    for a in exp["amendments"]:
        r = got[a["fund"]]
        assert (str(r["valuation_date"]), r["replaces"], r["amended_value"], r["change"], str(r["received_on"]), bool(r["open_amendments"])) == (
            a["period"], Decimal(a["replaces"]), Decimal(a["amended"]), Decimal(a["change"]), a["received"], a["after_last_issued_report"])
    assert {str(r["last_issued_report"]) for r in rows} == {exp["last_issued_report"]}
    assert sum(r["open_amendments"] for r in rows) == exp["open_count"] == 1
    assert office.tie("amendments_open")["ok"]


# ---- card 26: uc-026-stmtadmin ----------------------------------------------------------------------------------------------------------------

def test_card26_statement_against_administrator_matches_the_key(office):
    exp = KEYS["uc-026-stmtadmin"]["questions"]["Whether to accept the administrator value or ask the administrator to correct it"]["expected"]["differences"]
    rows = office.build("statement_vs_admin")
    differing = {r["fund"]: r for r in rows if r["difference"] != 0}
    assert set(differing) == set(exp)
    for fund, e in exp.items():
        r = differing[fund]
        assert (r["statement_value"], r["administrator_value"], r["difference"], r["administrator_status"], r["statement_kind"]) == (
            Decimal(e["statement"]), Decimal(e["administrator"]), Decimal(e["difference"]), e["administrator_status"], e["statement_kind"])
    assert {r["fund"] for r in rows if r["difference"] == 0} == {"Evergreen Income II", "Cedarpoint Ventures III", "Cedarpoint Opportunities II", "Saltmarsh Renewables I",
                                                                  "Global Equity Index Fund (synthetic)", "Global Bond Index Fund (synthetic)"}
    assert office.tie("statement_vs_admin")["ok"]


# ---- card 27: uc2-recon-break-desk ------------------------------------------------------------------------------------------------------------

def load_cash(o: Office) -> None:
    """Bank daily balances and lines, administrator cash, and the desk's cash, as position snapshots of a cash instrument per entity and currency. The desk exports
    movements, not balances: its cash is the bank's cash plus the movements the desk booked up to the day less the same kind of lines on the bank statements (bank fees and
    interest are on the bank side only), so the difference to the bank is the desk's timing difference."""
    accts = {r["account_id"]: r for r in csv.DictReader((OFFICE / "reference" / "accounts.csv").open(encoding="utf-8"))}
    ent_code = {n: k for k, n in ENT.items()}
    bank, first, items, seen = {}, {}, {}, {}
    for f in sorted(OFFICE.glob("*/bank_statements/*.xlsx")):
        acc = re.match(r"([A-Z]+_[A-Z]+_[A-Z]{3})_", f.name).group(1).replace("_", "-")
        key = (ent_code[accts[acc]["entity"]], accts[acc]["currency"])
        wb = openpyxl.load_workbook(f, data_only=True)
        for r in list(wb["Daily balances"].iter_rows(values_only=True))[1:]:
            bank[key + (r[0],)] = bank.get(key + (r[0],), 0) + Decimal(str(r[5]))
            seen[key + (r[0],)] = seen.get(key + (r[0],), 0) + 1
            if acc not in first or r[0] < first[acc][0]:
                first[acc] = (r[0], key, Decimal(str(r[3])))
        for r in list(wb["Transactions"].iter_rows(values_only=True))[1:]:
            if r[2] not in ("bank_fee", "interest"):  # the lines the desk also books
                items.setdefault(key, []).append((r[0], Decimal(str(r[5]))))
    start: dict = {}
    for d, key, opening in first.values():
        start[key] = start.get(key, 0) + opening
    admin = {}
    for f in sorted(OFFICE.glob("*/administrator_cash/*.csv")):
        for r in csv.DictReader(f.open(encoding="utf-8")):
            admin[(r["entity_code"], r["currency"], r["date"])] = Decimal(r["administrator_cash"])
    moves = {}
    for f in sorted(OFFICE.glob("*/trading_export/cash_movements_*.csv")):
        for r in csv.DictReader(f.open(encoding="utf-8")):
            moves.setdefault((r["legal_entity"], r["currency"]), []).append((r["value_date"], Decimal(r["amount"])))
    per_key = {}
    for a in accts.values():
        k = (ent_code[a["entity"]], a["currency"])
        per_key[k] = per_key.get(k, 0) + 1
    for (e, c, d), v in sorted(bank.items()):
        if seen[(e, c, d)] < per_key[(e, c)]:
            continue  # an account's statement is missing that month (M02b): the bank total is not the bank's cash, so no break can be called
        desk = v + sum(a for dd, a in moves.get((e, c), []) if dd <= d) - sum(a for dd, a in items.get((e, c), []) if dd <= d)
        for stype, value in (("bank", v), ("administrator", admin.get((e, c, d))), ("oms", desk)):
            if value is not None:
                o.put("position_snapshots", source_record_id=o.record(stype, stype)[1], portfolio_id=o.portfolio(f"{e}-CASH", e), instrument_id=o.inst(f"Cash {c} {e}", "cash", c),
                      position_date=d, as_of_at=ts(d), received_at=ts(d), recorded_at=ts(d), currency=c, data_status="Final", source_market_value=value)
    owner = o.put("users", external_identity_id="head-of-finance", display_name="Head of Finance", email="head.of.finance@evergreen.example.test")
    rule = o.put("business_rules", rule_code="cash_tolerance", rule_type="tolerance", owner_user_id=owner)
    o.put("rule_versions", business_rule_id=rule, version_number=1, definition_text="Daily cash may differ by up to 5,000 per entity before it is a break",
          parameters=json.dumps({"limit": 5000, "currency": "USD"}), effective_from="2026-04-01", approval_status="approved")


def test_card27_cash_breaks_match_the_key():
    q = KEYS["uc2-recon-break-desk"]["questions"]
    o = Office()
    load_cash(o)
    rows = [r for r in o.build("cash_difference_by_source") if r["currency"] == "USD"]
    e8 = q["Which entity has a cash break on 8 October and by how much?"]["expected"]
    b = next(r for r in rows if r["entity"] == e8["entity"] and str(r["day"]) == e8["date"] and r["source"] == "administrator")
    assert (b["bank_cash"], b["other_cash"], b["cash_break"]) == (Decimal(e8["bank"]), Decimal(e8["administrator"]), Decimal(e8["difference"]))
    ex = q["All breaks over the 5,000 tolerance, and those inside it"]["expected"]
    src = {"admin": "administrator", "oms": "desk"}
    over = sorted((str(r["day"]), r["entity"], r["source"], r["bank_cash"], r["other_cash"], r["cash_break"]) for r in rows if r["over_tolerance"])
    want_over = sorted((x["date"], x["entity"], src[x["source"]], Decimal(str(x["bank"])), Decimal(str(x["other"])), Decimal(str(x["difference"]))) for x in ex["over_tolerance"])
    inside = sorted((str(r["day"]), r["entity"], r["source"], r["cash_break"]) for r in rows if not r["over_tolerance"])
    want_in = sorted((x["date"], x["entity"], src[x["source"]], Decimal(str(x["difference"]))) for x in ex["inside_tolerance"])
    assert over == want_over and inside == want_in
    assert o.tie("cash_difference_by_source")["ok"]


def test_card27_without_a_signed_tolerance_the_figure_is_held():
    o = Office()
    load_cash(o)
    o.con.execute("update rule_versions set approval_status = 'proposed'")
    assert "tolerance" in R.needs(o.con, R.recipe("cash_difference_by_source"))


# ---- card 29: uc-029-closeck ------------------------------------------------------------------------------------------------------------------

def load_close(o: Office) -> None:
    users = {}
    for r in csv.DictReader(next(OFFICE.glob("2026-10/close_checklist/close_checklist_2026-09.csv")).open(encoding="utf-8")):
        users.setdefault(r["owner"], o.put("users", external_identity_id=r["owner"], display_name=r["owner"], email=r["owner"].replace(" ", ".").lower() + "@evergreen.example.test"))
        o.put("exceptions", exception_type="close_item", title=r["name"], description=f"{r['month']} close, step {r['step']}", detected_at=ts(month_end(r["month"])),
              owner_user_id=users[r["owner"]], due_at=ts(r["due_on"], "23:59:00"), resolved_at=ts(r["done_on"]) if r["done_on"] else None, status="resolved" if r["done_on"] else "open")
    o.doc("capital_call_notice", "latest file received", "2026-10-13")  # the latest date the office received anything: 13 October


def test_card29_close_items_match_the_key():
    exp = KEYS["uc-029-closeck"]["questions"]["Whether the close is complete and the report can start"]["expected"]
    o = Office()
    load_close(o)
    rows = o.build("close_items_done")
    assert len(rows) == exp["steps"] and sum(r["done"] for r in rows) == exp["done"]
    assert sorted(r["step_name"] for r in rows if r["open"]) == sorted(exp["open"])
    assert sorted(r["step_name"] for r in rows if r["late"]) == sorted(exp["late"])
    assert {r["close_month"] for r in rows} == {"2026-09"}
    assert o.tie("close_items_done")["ok"]


# ---- recipes: shape ---------------------------------------------------------------------------------------------------------------------------

OWN = ["close_items_done", "call_notice_fields", "notices_open", "columns_changed", "statement_timeliness", "amendments_open", "statement_vs_admin", "cash_difference_by_source"]


def test_every_recipe_of_the_domain_is_ready_and_reads_only_what_it_may():
    for rid in OWN:
        r = R.recipe(rid)
        assert r and r.get("status") != "stub" and r["sql"] and r["measure"] and r["grain"] and r["tie_out"] and r["cards"]
        assert R.refusal(r, R.render(r, "t")) is None, rid


def test_new_recipes_do_not_take_over_the_names_of_other_figures():
    for n in ["Cash break", "Cash balance per entity", "Net worth by portfolio", "Statements missing by fund", "Change since the issued report"]:
        assert (R.match({"name": n}) or {}).get("id") not in OWN, n


# ---- signals and builds -----------------------------------------------------------------------------------------------------------------------

CARDS = {"uc-001-noticelog": 1, "uc10-pipeline": 11, "uc-016-schemadrift": 16, "uc3-statements-inbox": 19, "uc-022-amendlog": 22, "uc-026-stmtadmin": 26,
         "uc2-recon-break-desk": 27, "uc-029-closeck": 29}
ALLOWED = {"abs", "min", "max", "round", "last4", "num", "same_fund"}


def signals() -> list[tuple[str, dict]]:
    out = []
    for card in CARDS:
        for p in sorted((PACK / "signals").glob(f"{card}-*.yaml")):
            s = yaml.safe_load(p.read_text(encoding="utf-8"))
            s["trigger"] = {("on" if k is True else k): v for k, v in s["trigger"].items()}  # YAML 1.1 reads a bare `on` as true; the engine does the same
            out.append((p.name, s))
    return out


def roles() -> set[str]:
    out = {r["id"] for r in yaml.safe_load((PACK / "role_builds.yaml").read_text(encoding="utf-8"))["roles"]}
    return out


def test_signals_follow_the_engine_format_and_every_card_has_an_exception():
    got: dict[str, list] = {}
    for name, s in signals():
        card = next(c for c in CARDS if name.startswith(c + "-"))
        got.setdefault(card, []).append(s)
        assert s["suggestion"] is True and s["id"] == name[:-5] and s["title"] and s["message"] and s["subject"]
        assert s["trigger"]["on"] in {"file_arrived", "figure_changed", "date_passed", "schedule", "run", "action_done"}, name
        assert s["severity"] in {"info", "needs", "problem"} and s["route_to"] in roles(), name
        assert s["action"]["verb"] in {"log", "record", "approve", "call_back", "see"} and s["action"]["options"], name
        assert s["inputs"] and all(i["kind"] in {"doc", "figure", "rule"} for i in s["inputs"]), name
        tree = ast.parse(str(s["condition"]), mode="eval")  # parsed, never evaluated, as the engine does
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                assert n.func.id in ALLOWED, (name, n.func.id)
        if s["severity"] == "problem":
            assert s["hold"]["blocks"] and s["hold"]["until"], name
    assert set(got) == set(CARDS)
    for card, ss in got.items():
        assert any(s["severity"] == "problem" and s.get("hold") for s in ss), f"{card} has no exception signal"


def test_builds_are_new_cards_only_and_expect_numbers_from_the_key():
    builds = yaml.safe_load((PACK / "builds" / "operate.yaml").read_text(encoding="utf-8"))
    old = {b["id"] for r in yaml.safe_load((PACK / "role_builds.yaml").read_text(encoding="utf-8"))["roles"] for b in r["builds"]}
    ids = []
    for role in builds["roles"]:
        assert role["id"] in roles()
        for b in role["builds"]:
            ids.append(b["id"])
            assert b["id"] in CARDS and b["id"] not in old
            assert b["say"] and b["files"] and all(f.startswith("office6m:") for f in b["files"]) and b["check"]["ask"] and b["check"]["expect"]
            assert all(glob.glob(str(OFFICE / f[len("office6m:"):])) for f in b["files"]), b["id"]
            blob = json.dumps(KEYS[b["id"]]["questions"], default=str).replace(",", "")
            plain = re.sub(r"(\d)(?=(\d{3})+$)", r"\1,", "")
            for e in b["check"]["expect"]:
                assert e.replace(",", "") in blob, (b["id"], e)
    assert sorted(ids) == sorted(["uc-001-noticelog", "uc-016-schemadrift", "uc-022-amendlog", "uc-026-stmtadmin", "uc-029-closeck"])
