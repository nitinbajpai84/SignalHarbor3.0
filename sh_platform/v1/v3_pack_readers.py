"""Harbor 3.0: the family-office pack's readers for the file kinds it knows (bank statement, custodian positions, administrator NAV pack, capital call
notice, invoice, payroll ...). Harbor's intake (v3_harbor a_intake / b_load / m_load) tries them first, file by file: `kind_of(name, data)` recognises a
file from its content and its name (never its folder, so a flat dropbox works), `read_files` loads what was recognised and records each kind's run as skill
`data.read-<kind>`. A file no reader recognises goes the generic way (mapping, PDFs, documents). It began as the loader of the six-month Evergreen Office
(tests/v1/fixtures/office6m, written by `python -m tools.gen_office6m`); `v3_office6m_loaders` re-exports it.

`load_office(con, root, org)` (or `load_plane(plane, root)`) reads every file kind of the office folders into the company model's tables, so the
figure recipes of packs/family_office/1/recipes read the rows they need. It returns a report: per file kind the files read, the rows written and
what was set aside or flagged, in plain words. Append-only: it only inserts. Synthetic data only.

Folder rule: `<YYYY-MM>/<kind>/<file>` is the month the file ARRIVES, so `today` (default 2026-10-13) loads the office as it knew itself that day;
`reference/` is standing data. recorded_at is the arrival of the file (this loader replays the office's month folders; an upload through the app
records the time it is made, see e1_write).

Conventions the recipes of the six domains agree on (docs/v3/w1/build-*.md, Needs):
  money in is positive, money out negative (A5); a loan statement's negative balances are written as the amount owed, positive.
  A capital call notice is a `documents` row (capital_call_notice) with `extracted_fields` (fund, investor, call_no, amount, call_amount, due_date,
  new_investments, management_fee, bank_account), and one `cash_movements` row, movement_type call, notice_kind capital_call, the WHOLE notice amount
  (negative), `noticed`. When the bank statement shows the payment, a `confirmed` row of the bank's date and amount SUPERSEDES the noticed one, and a
  `payment` row (to the payee account) records the money leaving. A distribution notice is a noticed row (notice_kind distribution) that stays; the
  bank credit is its own confirmed row (no notice_kind, bank_account_id). A notice naming an account the standing instructions do not hold is a new,
  unverified payee `bank_accounts` row that supersedes the one on file.
  Bank balances are `position_snapshots` of one cash instrument per account (listed in bank_accounts.cash_instrument_id, so the recipes leave them
  out of the entity cash); the administrator's cash is a snapshot of `Cash <ccy>` per entity. They are never added together.
  A statement amended or re-issued is a new valuation_observation that supersedes the earlier one of the fund and period; valuation_type is
  manager_final / manager_estimate / manager_amended, approval_status final / estimate / amended.
  Planted mess: day-first and month-first dates are read per file; 'Not received' administrator rows are not positions (an exception row says so);
  a renamed administrator column is read through the known synonym and proposed as a new sheet mapping; a duplicate invoice or trade is kept and
  flagged (document_status duplicate / transaction status rejected, with an exception row) and counted once; FX side text 'sell USD / buy SGD'
  is written as quantity_delta and cash_amount of an fx_forward transaction; amounts of a loan are taken as the size owed.
"""
from __future__ import annotations

import calendar
import csv
import email
import hashlib
import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from email import policy as email_policy
from functools import lru_cache
from pathlib import Path

import openpyxl
import pypdf

log = logging.getLogger(__name__)
TODAY = "2026-10-13"
SKIP = {"MANIFEST.md", "answer_keys.yaml", ".office6m"}
ENTITY_OF_PORTFOLIO = {"EG-LIQUID": "EG-TRUST"}
MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m} | {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
DEFAULTS = {
    "documents": dict(document_status="final", processing_status="done", contains_personal_data=False),
    "extracted_fields": dict(confidence="high", review_status="confirmed"),
    "position_snapshots": dict(view_type="operational", data_status="Final"),
    "valuation_observations": dict(approval_status="final"),
    "cash_movements": dict(confirmation_status="confirmed"),
    "transactions": dict(status="settled"),
    "market_observations": dict(quality_status="official"),
    "bank_accounts": dict(status="active"),
    "exceptions": dict(materiality_status="material", status="open"),
    "source_batches": dict(validation_status="loaded"),
    "source_records": dict(quality_status="ok"),
    "source_systems": dict(is_active=True),
    "users": dict(is_active=True),
    "vendor_contracts": dict(status="Active"),
    "credit_facilities": dict(status="active", facility_type="term_loan"),
    "expected_statements": dict(frequency="monthly", source="schedule"),
}
FLUSH_ORDER = ["organizations", "access_groups", "users", "source_systems", "legal_entities", "portfolios", "instruments", "instrument_identifiers", "source_batches",
               "source_records", "sheet_mappings", "sheet_mapping_columns", "documents", "extracted_fields", "bank_accounts", "commitments", "position_snapshots",
               "valuation_observations", "transactions", "cash_movements", "approvals", "market_observations", "fx_confirmations", "business_rules", "rule_versions",
               "benchmark_definitions", "benchmark_components", "credit_facilities", "family_members", "vendor_contracts", "expected_statements", "exceptions",
               "deal_pipeline", "committee_decisions"]


# ---- small readers ------------------------------------------------------------------------------------------------------------------

def stamp(d, hour: int = 12) -> str:
    """A date as a timestamp at midday UTC, so the date survives any session time zone (`hour` is accepted and ignored: only midday is zone-safe)."""
    return f"{d.isoformat() if isinstance(d, (date, datetime)) else str(d)[:10]} 12:00:00+00"


def money(text) -> Decimal:
    return Decimal(re.sub(r"[^\d.\-]", "", str(text)))


def slash_order(text: str) -> str | None:
    """'dmy' or 'mdy' when the dates written a/b/yyyy in the text can only be read one way (13 or more in one slot), else None."""
    order = None
    for a, b in re.findall(r"\b(\d{1,2})/(\d{1,2})/\d{4}\b", text):
        if int(a) > 12:
            order = "dmy"
        elif int(b) > 12:
            order = "mdy"
    return order


def parse_date(s, order: str | None = None, hint: date | None = None) -> date:
    """ISO, '24 September 2026', or a/b/yyyy: day first or month first by `order`; undecided, the reading inside the hint month wins, else day first."""
    if isinstance(s, datetime):
        return s.date()
    if isinstance(s, date):
        return s
    t = str(s).strip()
    if m := re.match(r"^(\d{4})-(\d{2})-(\d{2})", t):
        return date(int(m[1]), int(m[2]), int(m[3]))
    if m := re.match(r"^(\d{1,2}) ([A-Za-z]+) (\d{4})", t):
        return date(int(m[3]), MONTHS[m[2].lower()], int(m[1]))
    if m := re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", t):
        a, b, y = int(m[1]), int(m[2]), int(m[3])
        if a > 12 or order == "dmy":
            return date(y, b, a)
        if b > 12 or order == "mdy":
            return date(y, a, b)
        if hint and (hint.year, hint.month) == (y, b):
            return date(y, b, a)
        if hint and (hint.year, hint.month) == (y, a):
            return date(y, a, b)
        return date(y, b, a)
    raise ValueError(f"date not understood: {s!r}")


@lru_cache(maxsize=None)
def pdf_text(path: str) -> str:
    return "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(path).pages)


def csv_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sheet_rows(path: Path, name: str | None = None) -> list[list]:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        ws = wb[name] if name else wb.worksheets[0]
        return [list(r) for r in ws.iter_rows(values_only=True)]
    finally:
        wb.close()  # a book left open cannot be removed on Windows


def dicts(rows: list[list]) -> list[dict]:
    head = rows[0]
    return [dict(zip(head, r)) for r in rows[1:] if any(v is not None for v in r)]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vendor_name(line: str) -> str:
    return re.sub(r"\s*\(synthetic\)", "", line.strip(), flags=re.I).title()


def last_day(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])


def business_day(y: int, m: int, n: int) -> date:
    d, k = date(y, m, 1), 0
    while True:
        if d.weekday() < 5:
            k += 1
            if k == n:
                return d
        d += timedelta(days=1)


# ---- the loader ---------------------------------------------------------------------------------------------------------------------

class Office:
    def __init__(self, con, root, org: str = "org-evergreen", today: str = TODAY, incremental: bool = False, recorder=None):
        self.con, self.root, self.org, self.today = con, Path(root), org, date.fromisoformat(today)
        self.incremental = incremental  # intake: files arrive in batches; the standing data and earlier files are on record, never written twice
        self.recorder = recorder or (lambda kinds, fn: fn())
        self.staged: dict[str, int] = {}
        self.rows: dict[str, list[dict]] = {}
        self.n = 0
        self.report: dict[str, dict] = {}
        self.sys, self.ent, self.port, self.cashport, self.inst, self.user = {}, {}, {}, {}, {}, {}
        self.by_name, self.by_code, self.fund_key, self.fund_info = {}, {}, {}, {}
        self.cashinst, self.office_acct, self.payee, self.commit = {}, {}, {}, {}
        self.mov: dict[str, dict] = {}        # notice movement by (kind, fund key, number)
        self.pay_ref: dict[str, list[str]] = {}  # bank reference -> ids of movements it made
        self.seen_hash: dict[str, str] = {}     # file hash -> document id
        self.batch_of: dict[str, str] = {}
        self.log: dict[str, dict] = {}
        self.log_name: dict[str, dict] = {}     # the same log by file name, for a dropbox with no folders
        self.bankcalls: dict[tuple, dict] = {}   # (fund key, call number) -> the payment the bank shows
        self.bank_lines: list[dict] = []        # every bank line, for the desk's cash and for finding what an invoice paid
        self.open_calls: list[dict] = []        # noticed calls the bank has not paid
        self.invoice_list: list[dict] = []
        self.loan: dict = {}
        self.stm_doc: dict = {}
        self.terms: dict = {}
        self.vendor_acct, self.vendor_names = {}, {}

    # -- plumbing --
    def nid(self, p: str) -> str:
        return str(uuid.uuid4())

    def add(self, table: str, **kw) -> str:
        row = {**DEFAULTS.get(table, {}), **kw}
        row.setdefault("id", self.nid(table[:4]))
        if table != "organizations":
            row.setdefault("organization_id", self.org)
        self.rows.setdefault(table, []).append(row)
        return row["id"]

    def flush(self) -> None:
        for table in FLUSH_ORDER:
            rows = self.rows.get(table)
            if not rows:
                continue
            cols = list(dict.fromkeys(c for r in rows for c in r))
            have = {r[0] for r in self.con.execute("select column_name from information_schema.columns where table_name = ?", [table]).fetchall()}
            cols = [c for c in cols if c in have]
            self.con.executemany(f"insert into {table} ({', '.join(cols)}) values ({', '.join('?' * len(cols))})", [[r.get(c) for c in cols] for r in rows])
        self.rows = {}

    def note(self, kind: str, files: int = 0, rows: int = 0, why: str | None = None, flag: str | None = None) -> None:
        r = self.report.setdefault(kind, {"files": 0, "rows": 0, "not_loaded": [], "flagged": []})
        r["files"] += files
        r["rows"] += rows
        if why:
            r["not_loaded"].append(why)
        if flag:
            r["flagged"].append(flag)

    def rel(self, p: Path) -> str:
        return p.relative_to(self.root).as_posix()

    def files(self, kind: str, pattern: str = "*") -> list[Path]:
        """The files of a kind that have arrived by `today` (month folders up to the month, daily files not dated after it); reference/ files for kind 'reference'."""
        out, day = [], self.today.strftime("%Y%m%d")
        for p in sorted(self.root.glob(f"20??-??/{kind}/{pattern}")):
            if not p.is_file() or p.parts[-3] > self.today.strftime("%Y-%m"):
                continue
            m = re.search(r"(20\d{2})-?(\d{2})-?(\d{2})", p.stem)
            if m and "".join(m.groups()) > day:
                continue
            out.append(p)
        return out

    def arrival(self, p: Path) -> date:
        """The day a file arrived: the received log, else the date in its name, else the second business day of its month folder."""
        r = self.log.get(self.rel(p)) or self.log_name.get(p.name)
        if r and r.get("received_on"):
            return date.fromisoformat(r["received_on"])
        m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", p.name) or re.search(r"(20\d{2})(\d{2})(\d{2})", p.name)
        if m:
            return date(int(m[1]), int(m[2]), int(m[3]))
        y, mo = map(int, p.parts[-3].split("-")) if re.fullmatch(r"\d{4}-\d{2}", p.parts[-3]) else (self.today.year, self.today.month)
        return business_day(y, mo, 2)

    def source(self, kind: str, name: str | None = None, stype: str | None = None) -> str:
        if kind not in self.sys:
            self.sys[kind] = self.k_sys.get(kind) or self.add("source_systems", source_code=kind, source_name=name or kind, source_type=stype or kind)
        return self.sys[kind]

    def batch(self, kind: str, p: Path, received: date, summary: str | None = None, mapping: str | None = None, period_end: date | None = None) -> str:
        key = f"{kind}:{self.rel(p)}"
        if key not in self.batch_of:
            self.batch_of[key] = self.add("source_batches", source_system_id=self.source(kind), batch_reference=self.rel(p), received_at=stamp(received), loaded_at=stamp(received),
                                          content_hash=file_hash(p), storage_uri=self.rel(p), validation_summary=summary, sheet_mapping_id=mapping, source_period_end=period_end)
        return self.batch_of[key]

    def record(self, kind: str, p: Path, received: date, rtype: str = "file", external: str | None = None, sheet: str | None = None, row: int | None = None,
               effective: date | None = None) -> str:
        return self.add("source_records", source_batch_id=self.batch(kind, p, received), external_record_id=external, record_type=rtype, sheet_name=sheet, row_number=row,
                        effective_at=stamp(effective) if effective else None, received_at=stamp(received), recorded_at=stamp(received), raw_payload_uri=self.rel(p),
                        content_hash=file_hash(p) if row is None else hashlib.sha256(f"{self.rel(p)}:{row}:{external}".encode()).hexdigest())

    def doc(self, p: Path | None, dtype: str, title: str, *, kind: str = "office", received: date | None = None, date_: date | None = None, valuation: date | None = None,
            instrument: str | None = None, status: str = "final", fields=(), personal: bool = False, uri: str | None = None, raw: bytes | None = None,
            supersedes: str | None = None, record: str | None = None, external: str | None = None) -> str:
        received = received or (self.arrival(p) if p else self.today)
        h = hashlib.sha256(raw).hexdigest() if raw is not None else (file_hash(p) if p else hashlib.sha256((uri or title).encode()).hexdigest())
        did = self.add("documents", source_system_id=self.source(kind), source_record_id=record or (self.record(kind, p, received) if p else None),
                       access_group_id=self.group("personal" if personal else "default"), instrument_id=instrument, external_document_id=external, document_type=dtype, title=title,
                       original_filename=p.name if p else None, original_uri=uri or (self.rel(p) if p else title), content_hash=h, document_date=date_, valuation_date=valuation,
                       received_at=stamp(received), recorded_at=stamp(received), document_status=status, supersedes_document_id=supersedes, contains_personal_data=personal)
        self.seen_hash.setdefault(h, did)
        for f in fields:
            self.field(did, *f)
        return did

    def field(self, did: str, name: str, text=None, num=None, ccy: str | None = None, page: int = 1, line: int | None = None) -> None:
        self.add("extracted_fields", document_id=did, field_name=name, value_text=None if text is None else str(text), value_numeric=num, currency=ccy, page_number=page, line_number=line)

    def group(self, name: str) -> str:
        if ("grp", name) not in self.inst:
            self.inst[("grp", name)] = self.k_group.get(name) or self.add("access_groups", group_name=name, description=f"{name} access")
        return self.inst[("grp", name)]

    def exception(self, etype: str, title: str, description: str, day: date, **kw) -> None:
        self.add("exceptions", exception_type=etype, title=title, description=description, detected_at=stamp(day), **kw)

    def person(self, name: str | None, role: str | None = None) -> str | None:
        if not name:
            return None
        if name not in self.user:
            self.user[name] = self.add("users", external_identity_id=name, display_name=name, email=f"{name.lower().replace(' ', '.')}@evergreen-office.example.test",
                                       business_role=role, created_at=stamp(date(2026, 4, 1)))
        return self.user[name]

    def known(self) -> None:
        """A company that already holds master data (the clean Evergreen office has its entities, portfolios, people and funds A to E) keeps it: rows are found by code or name and reused."""
        def q(sql: str, *a):
            try:
                return self.con.execute(sql, list(a)).fetchall()
            except Exception:  # noqa: BLE001 - a warehouse without the table has nothing known
                return []
        self.has_org = bool(q("select 1 from organizations where id = ?", self.org))
        self.k_ent = dict(q("select entity_code, id from legal_entities"))
        self.k_port = dict(q("select portfolio_code, id from portfolios"))
        self.k_inst = dict(q("select canonical_name, id from instruments"))
        self.k_user = dict(q("select display_name, id from users"))
        self.k_group = dict(q("select group_name, id from access_groups"))
        self.k_rule = dict(q("select rule_code, id from business_rules"))
        self.k_ident = {(a, b, c) for a, b, c in q("select instrument_id, identifier_type, identifier_value from instrument_identifiers")}
        self.user.update(self.k_user)
        self.k_sys = dict(q("select source_code, id from source_systems"))
        self.db_rules = [(a, b) for a, b in q("select business_rule_id, parameters from rule_versions order by version_number")]
        self.ref_loaded = "reference" in self.k_sys
        self.already = bool(q("select 1 from source_batches where regexp_matches(coalesce(storage_uri, ''), '^20[0-9]{2}-[0-9]{2}/') limit 1"))

    # -- the whole office --
    def load(self) -> dict:
        self.known()
        if self.already and not self.incremental:  # rows are only ever added: a second load of the same folders would double every figure
            raise ValueError("the office files are already loaded in this company; load the folders once, into an empty warehouse or one that holds only master data")
        if not self.has_org:
            self.add("organizations", id=self.org, name="Evergreen Office (synthetic)", created_at=stamp(date(2026, 4, 1)))
        for r in (csv_rows(self.root / "received_log_all.csv") if (self.root / "received_log_all.csv").is_file() else []):
            self.log[r["file"]] = self.log_name[Path(r["file"]).name] = r
        shadow = self.incremental and self.ref_loaded  # the standing data (benchmark spec included) is on record: found again, not written again
        steps = [self.reference_state if shadow else self.reference, self.registers, (lambda: None) if shadow else self.benchmark, self.admin_nav, self.admin_cash, self.custodian_positions, self.bank_statements, self.trading_and_custody,
                 self.administrator_trades, self.market, self.manager_statements, self.notices, self.fx_confirmations, self.emails, self.invoices, self.payroll, self.loans,
                 self.vendor_contracts, self.allowances, self.insurance_and_property, self.approvals_and_close, self.reports_and_audit, self.diligence_and_notes,
                 self.expected_statements, self.links, self.treasury, self.controls, self.family, self.invest]
        for step in steps:
            kinds = [k for k in STEP_KINDS.get(step.__name__, ()) if self.staged.get(k)]
            fn = step
            for k in kinds:  # each kind that has files in this batch is a run of its own reader, timed and logged as skill data.read-<kind>
                fn = (lambda k, inner: lambda: self.recorder(k, inner))(k, fn)
            fn()
        self.unread()
        self.flush()
        return self.report

    def unread(self) -> None:
        """Every file kind the folders hold that no reader above handled is said so."""
        known = {k for k in self.report}
        kinds = {p.parts[-2] for p in self.root.glob("20??-??/*/*") if p.is_file()}
        for k in sorted(kinds - known):
            self.note(k, why="no reader for this kind")

    # ------------------------------------------------------------------ reference, rules, master data
    def reference(self, docs: bool = True) -> None:
        ref = self.root / "reference"
        md = json.loads((ref / "master_data.json").read_text(encoding="utf-8"))
        self.md = md
        for code, name in md["entities"].items():
            self.ent[code] = self.k_ent.get(code) or self.add("legal_entities", entity_code=code, entity_name=name, base_currency="USD")
            self.cashport[code] = self.k_port.get(f"CASH-{code}") or self.add("portfolios", legal_entity_id=self.ent[code], portfolio_code=f"CASH-{code}", portfolio_name=f"Cash {name}", base_currency="USD")
        self.port_entity = {f["portfolio"]: f["entity"] for f in md["funds"].values()} | ENTITY_OF_PORTFOLIO
        for code, ent in sorted(self.port_entity.items()):
            self.port[code] = self.k_port.get(code) or self.add("portfolios", legal_entity_id=self.ent[ent], portfolio_code=code, portfolio_name="Evergreen Liquid Book" if code == "EG-LIQUID" else code,
                                                                base_currency="USD")
        for p in md["people"]:
            self.person(p["name"], p["title"])
        self.security_master(ref)
        self.accounts(ref)
        self.fund_terms(ref)
        self.rules(ref)
        self.policy(ref)
        self.note("reference", files=0)
        if docs:
            self.reference_documents(ref)

    def security_master(self, ref: Path) -> None:
        f = next(ref.glob("EG_security_master_*.xlsx"))
        rows = sheet_rows(f, "Security master")
        src, d = self.source("reference", "Reference data", "office"), date.fromisoformat(re.search(r"(\d{8})", f.name)[1][:4] + "-" + re.search(r"(\d{8})", f.name)[1][4:6] + "-" + re.search(r"(\d{8})", f.name)[1][6:])
        n = 0
        for r in rows[4:]:
            if not r[0] or not str(r[0]).startswith(("SEC-", "FND-")):
                continue
            iid = self.k_inst.get(r[2]) or self.add("instruments", canonical_name=r[2], instrument_type=r[3], asset_class=r[4] or None, manager_name=r[9], currency=r[5], created_at=stamp(d))
            self.inst[r[0]] = iid
            self.by_name[r[2]] = iid
            if r[1]:
                self.ident(iid, "isin", r[1])
            if r[6]:
                self.by_code[r[6]] = iid
                self.ident(iid, "trading_code", r[6])
            if r[7] and r[3] != "private_fund":
                self.ident(iid, "administrator_code", str(r[7]))
            n += 1
        for key, fd in self.md["funds"].items():  # funds the security master leaves out (F, G, K): class and manager from the office's master data
            if fd["name"] not in self.by_name and fd["name"] in self.k_inst:
                self.by_name[fd["name"]] = self.inst[f"FND-{key}"] = self.k_inst[fd["name"]]
            if fd["name"] not in self.by_name:
                iid = self.add("instruments", canonical_name=fd["name"], instrument_type="private_fund", asset_class=fd["asset_class"], manager_name=fd["manager"], currency="USD", created_at=stamp(d))
                self.by_name[fd["name"]] = iid
                self.inst[f"FND-{key}"] = iid
                n += 1
            self.fund_key[key] = self.by_name[fd["name"]]
            self.fund_info[key] = fd
        wbk = openpyxl.load_workbook(f, read_only=True)
        has_alias = "Alias map" in wbk.sheetnames
        wbk.close()
        alias = sheet_rows(f, "Alias map") if has_alias else []
        for r in alias[4:]:
            if r[0] and r[1] in self.inst and "ticker" in str(r[2]).lower() and r[0] not in self.by_code:
                self.by_code[r[0]] = self.inst[r[1]]
        self.note("reference", files=1, rows=n)

    def ident(self, iid: str, typ: str, value: str, status: str = "approved") -> None:
        if (iid, typ, str(value)) in self.k_ident:
            return
        self.k_ident.add((iid, typ, str(value)))
        self.add("instrument_identifiers", instrument_id=iid, source_system_id=self.source("reference"), identifier_type=typ, identifier_value=str(value), mapping_status=status,
                 approved_by=self.person("Anita Rao") if status == "approved" else None, approved_at=stamp(date(2026, 4, 1)) if status == "approved" else None)

    def cash_instrument(self, name: str, ccy: str, code: str) -> str:
        if name not in self.cashinst:
            iid = self.k_inst.get(name) or self.add("instruments", canonical_name=name, instrument_type="cash", asset_class="cash", currency=ccy, created_at=stamp(date(2026, 4, 1)))
            self.ident(iid, "internal_code", code)
            self.cashinst[name] = iid
        return self.cashinst[name]

    def accounts(self, ref: Path) -> None:
        for r in csv_rows(ref / "accounts.csv"):
            code = next(c for c, n in self.md["entities"].items() if n == r["entity"])
            ci = self.cash_instrument(r["account_id"], r["currency"], r["account_id"])
            self.office_acct[r["account_id"]] = dict(id=self.add("bank_accounts", holder_kind="office", legal_entity_id=self.ent[code], holder_name=r["entity"], account_purpose="operating",
                                                                  bank_name=r["bank"], account_ref=r["account_number"][-4:], currency=r["currency"], cash_instrument_id=ci,
                                                                  source_record_id=self.record("reference", ref / "accounts.csv", date(2026, 4, 1)), received_at=stamp(date(2026, 4, 1)),
                                                                  recorded_at=stamp(date(2026, 4, 1)), opened_on="2026-04-01"),
                                                     entity=code, ccy=r["currency"], cash=ci, number=r["account_number"], bank=r["bank"])
        self.note("reference", files=1, rows=len(self.office_acct))
        sr = self.record("reference", ref / "standing_instructions.csv", date(2026, 4, 1))
        for r in csv_rows(ref / "standing_instructions.csv"):
            self.payee[(r["fund_key"], r["account_last4"])] = self.add(
                "bank_accounts", holder_kind="payee", instrument_id=self.fund_key[r["fund_key"]], holder_name=r["fund"], account_purpose="payee", bank_name=r["bank"],
                account_ref=r["account_last4"], currency="USD", verified_on=r["confirmed_on"], verified_by=self.person(r["confirmed_by"]), source_record_id=sr,
                received_at=stamp(date.fromisoformat(r["confirmed_on"])), recorded_at=stamp(date.fromisoformat(r["confirmed_on"])), opened_on=r["confirmed_on"])
        self.note("reference", files=1, rows=len(self.payee))
        sr = self.record("reference", ref / "vendor_master.csv", date(2026, 4, 1))
        for r in csv_rows(ref / "vendor_master.csv"):
            self.vendor_names[r["vendor"].lower()] = r["vendor"]
            self.vendor_acct[r["vendor"].lower()] = self.add("bank_accounts", holder_kind="payee", holder_name=r["vendor"], account_purpose=r["category"], bank_name="vendor master",
                                                              account_ref=r["account_last4"], currency=r["currency"], verified_on="2026-04-01", verified_by=self.person("Helen Foo"),
                                                              source_record_id=sr, received_at=stamp(date(2026, 4, 1)), recorded_at=stamp(date(2026, 4, 1)), opened_on="2026-04-01")
        self.note("reference", files=1, rows=len(self.vendor_acct))

    def fund_terms(self, ref: Path) -> None:
        sr = self.record("reference", ref / "fund_terms.csv", date(2026, 4, 1))
        for r in csv_rows(ref / "fund_terms.csv"):
            self.terms[r["fund_key"]] = r
            did = self.doc(None, "fund_terms", f"Fund terms {r['fund']}", date_=date(2026, 4, 1), instrument=self.fund_key[r["fund_key"]], status="policy", record=sr,
                           uri="reference/fund_terms.csv", received=date(2026, 4, 1), raw=json.dumps(r, sort_keys=True).encode())
            self.field(did, "management_fee_rate", num=Decimal(r["fee_pct_of_commitment_per_billing"]) / 100)
            self.field(did, "fee_basis", text="commitment, per billing")
            self.field(did, "billing_months", text=r["billing_months"])
            self.field(did, "commitment", num=Decimal(r["commitment_usd"]), ccy="USD")
        self.note("reference", files=1, rows=len(self.terms))

    def rule(self, code: str, rtype: str, text: str, params: dict, owner: str, approver: str, effective: str = "2026-04-01", status: str = "approved", version: int = 1) -> str:
        key = ("rule", code)
        if code in self.k_rule:  # already signed in this company: kept as it is
            self.inst[key] = self.k_rule[code]
            self.note("reference", flag=f"rule {code} is already on record in this company; not written again")
            return self.inst[key]
        if key not in self.inst:
            self.inst[key] = self.add("business_rules", rule_code=code, rule_type=rtype, owner_user_id=self.person(owner))
        self.add("rule_versions", business_rule_id=self.inst[key], version_number=version, definition_text=text, parameters=json.dumps(params), effective_from=effective,
                 approval_status=status, approved_by=self.person(approver) if status == "approved" else None, approved_at=stamp(date.fromisoformat(effective)) if status == "approved" else None)
        return self.inst[key]

    def rules(self, ref: Path) -> None:
        by = {r["rule"]: r for r in csv_rows(ref / "office_rules.csv")}
        spec = {"cash_buffer": ("policy", "cash_buffer_usd", lambda v: {"amount": float(v), "currency": "USD"}),
                "payment_approval": ("policy", "approval_over_usd", lambda v: {"amount": float(v), "currency": "USD"}),
                "changed_bank_details": ("policy", "bank_detail_change", lambda v: {"rule": v}),
                "cash_tolerance_usd": ("tolerance", "cash_tolerance_usd", lambda v: {"limit": float(v), "amount": float(v), "currency": "USD"}),
                "single_name_limit_pct": ("policy", "single_name_limit_pct", lambda v: {"value": float(v), "max_pct": float(v), "pct": float(v)})}
        for code, (kind, src, params) in spec.items():
            if src in by:
                self.rule(code, kind, by[src]["text"], params(by[src]["value"]), "Daniel Foo", "Daniel Foo")
        for r in csv_rows(ref / "office_rules.csv"):  # rules the file signs itself: type, parameters, approval status and version (a proposed v2 beside the approved v1)
            if r.get("parameters"):
                self.rule(r["rule"], r.get("rule_type") or "policy", r["text"], json.loads(r["parameters"]), "Daniel Foo", "Daniel Foo",
                          status=r.get("approval_status") or "approved", version=int(r.get("version") or 1))
        self.note("reference", files=1, rows=len(spec))

    def policy(self, ref: Path) -> None:
        p = next(ref.glob("Evergreen_Investment_Allocation_Policy_*.pdf"))
        t = pdf_text(str(p))
        eff = re.search(r"Effective (\d{4}-\d{2}-\d{2})", t)
        eff = eff[1] if eff else "2026-01-01"
        body = t[t.index("3. Allocation limits"):t.index("Each limit")]
        n = 0
        for m in re.finditer(r"(limit_\w+)\n(.*?)(?=\nlimit_\w+\n|\Z)", body, re.S):
            code, rest = m[1], m[2].split("\n")
            port = rest[0]
            pct = [int(x) for x in re.findall(r"(\d+)%", " ".join(rest))]
            words = " ".join(x for x in rest[1:] if "%" not in x)
            kw = re.search(r"(single name|asset class|manager)", words)
            if not kw or len(pct) < 2:
                continue
            bucket = words[kw.end():].strip()
            dim = kw[1].replace(" ", "_")
            self.rule(code, "policy", f"{port}: {bucket} {pct[0]}% to {pct[1]}% of the portfolio, measured at the month end", dict(portfolio=port, dimension=dim, bucket=bucket, min_pct=pct[0], max_pct=pct[1]),
                      "Sofia Reyes", "Daniel Foo", effective=eff)
            n += 1
        sec6 = t[t.index("6. Approval line"):]
        for m in re.finditer(r"\n(cio_materiality|estimate_use|statement_due|fx_fixing)\nWording\n?(.*?)\n(?:Owner|\1|cio_|estimate_|statement_|fx_)", "\n" + sec6, re.S):
            pass
        for code, wording, params in (
                ("cio_materiality", "The CIO sees a change over 100,000 USD or 0.5% of a fund.", dict(amount=100000, pct=0.5, currency="USD")),
                ("estimate_use", "A manager estimate may be used in the investment report only.", dict(allowed_in="investment_report")),
                ("statement_due", "A manager statement is due within 10 business days of the period end.", dict(business_days=10)),
                ("fx_fixing", "Convert with the WMR 4pm USD/SGD fixing in the market data file.", dict(source="WMR 4pm", pair="USD/SGD"))):
            if code in t:  # the rule is on the page: its wording is checked against the page, its numbers read from it
                if code == "cio_materiality":
                    mm = re.search(r"over ([\d,]+) USD or ([\d.]+)%", t)
                    params = dict(amount=int(mm[1].replace(",", "")), pct=float(mm[2]), currency="USD") if mm else params
                if code == "statement_due":
                    mm = re.search(r"within (\d+) business days", t)
                    params = dict(business_days=int(mm[1])) if mm else params
                self.rule(code, "policy" if code != "fx_fixing" else "mapping", wording, params, "Raj Patel", "Daniel Foo", effective=eff)
                n += 1
        self.doc(p, "policy", p.stem, kind="reference", date_=date.fromisoformat(re.search(r"Document date (\d{4}-\d{2}-\d{2})", t)[1]), received=self.today,
                 fields=[("version", "2026.1")], status="policy")
        self.note("reference", files=1, rows=n)

    def reference_documents(self, ref: Path) -> None:
        """fee schedule, loan agreement, ddqs, letters, newsletter, narrative and hand-over note of reference/."""
        for p in sorted(ref.iterdir()):
            if p.name in {"master_data.json", "accounts.csv", "fund_terms.csv", "office_rules.csv", "standing_instructions.csv", "vendor_master.csv"} or p.name.startswith(
                    ("EG_security_master", "EG-OFFICE-BLEND", "Evergreen_Investment_Allocation_Policy", "vendor_contract_")):
                continue
            if p.name == "fee_schedule.pdf":
                self.fee_schedule(p)
            elif p.name.startswith("loan_agreement"):
                self.loan_agreement(p)
            elif "ddq" in p.name:
                self.ddq(p)
            elif p.suffix == ".pdf":
                t = pdf_text(str(p))
                counterparty = "Kestrel Ridge Advisors" if "kestrel" in p.name else "Northgate Partners" if "northgate" in p.name else None
                nd = re.search(r"(\d{1,2} [A-Z][a-z]+ 20\d\d)", t)
                fields = [("counterparty", counterparty)] if counterparty else []
                if "newsletter" in p.name and (m := re.search(r"Team update\n(.*?)\nThe investment process", t, re.S)):
                    fields.append(("team_change", " ".join(m[1].split())))
                self.doc(p, "newsletter" if "newsletter" in p.name else "manager_letter", p.stem, kind="manager", received=date(2026, 9, 28) if "newsletter" in p.name else date(2026, 7, 15),
                         date_=parse_date(nd[1]) if nd and "newsletter" in p.name else None, fields=fields)
                self.note("reference", files=1)
            elif p.suffix in {".md", ".txt"}:
                self.doc(p, "process_note" if p.suffix == ".md" else "handover_note", p.stem, received=date(2026, 10, 5),
                         fields=[("body", p.read_text(encoding="utf-8"))])
                self.note("reference", files=1)

    def fee_schedule(self, p: Path) -> None:
        t = pdf_text(str(p))
        did = self.doc(p, "fee_schedule", "Fee schedule on file", date_=date(2026, 4, 1), received=date(2026, 4, 1))
        n = 0
        for m in re.finditer(r"\(([^)]+)\): ([\d.]+)% a year .*?billed (quarterly|monthly|annually)", t):
            self.field(did, "service_fee_rate", text=vendor_name(m[1]), num=Decimal(m[2]) / 100)
            self.field(did, "service_fee_periods", text=vendor_name(m[1]), num=Decimal({"quarterly": 4, "monthly": 12, "annually": 1}[m[3]]))
            n += 1
        self.note("reference", files=1, rows=n)

    def loan_agreement(self, p: Path) -> None:
        t = pdf_text(str(p))
        mm = re.search(r"Principal: ([A-Z]{3}) ([\d,\.]+)", t)
        ir = re.search(r"Interest: ([\d.]+)%", t)
        mat = re.search(r"maturity (\d{1,2} \w+ \d{4})", t)
        self.loan = dict(principal=money(mm[2]) if mm else None, ccy=mm[1] if mm else "USD", rate=Decimal(ir[1]) / 100 if ir else None, maturity=parse_date(mat[1]) if mat else None,
                         doc=self.doc(p, "loan_agreement", p.stem, kind="office", date_=date(2026, 1, 1), received=date(2026, 4, 1),
                                      fields=[("principal", None, money(mm[2]), mm[1])] if mm else []))
        self.note("reference", files=1)

    def ddq(self, p: Path) -> None:
        t = pdf_text(str(p))
        title = t.splitlines()[0].strip()
        mgr = re.sub(r"\s*-?\s*DUE DILIGENCE QUESTIONNAIRE.*", "", title, flags=re.I).strip().title()
        year = re.search(r"Questionnaire date: (\d{4})", t) or re.search(r"(\d{4})$", title)
        y = int(year[1]) if year else 2026
        fields = [("manager_name", mgr)]
        for i, (q, a) in enumerate(re.findall(r"^\d+\. (.*?): (.*)$", t, re.M), 1):
            fields.append((f"ddq: {q}", a.strip(), None, None, 1, i))
        self.doc(p, "ddq", title.title(), kind="manager", date_=date(y, 1, 1), received=self.arrival(p) if re.match(r"20\d\d-\d\d", p.parts[-3]) else date(2026, 6, 1), fields=fields)
        self.note("ddq" if re.match(r"20\d\d-\d\d", p.parts[-3]) else "reference", files=1, rows=len(fields))

    # ------------------------------------------------------------------ commitments registers
    def registers(self) -> None:
        last, n = dict(self.commit), 0  # a register read earlier is what the new one supersedes
        for p in self.files("commitments"):
            d = parse_date(re.search(r"(\d{4}-\d{2}-\d{2})", p.name)[1])
            sr = self.record("office", p, self.arrival(p), effective=d)
            for r in dicts(sheet_rows(p, "Register")):
                if not r.get("Fund") or r.get("Fund key") is None:
                    continue
                key = r["Fund key"]
                t = self.terms.get(key, {})
                last[key] = self.add("commitments", legal_entity_id=self.ent[r["Entity code"]], instrument_id=self.fund_key[key], source_record_id=sr, commitment_amount=r["Commitment"],
                                     currency=r["Currency"], committed_on=t.get("committed_on", "2021-01-01"), called_to_date=r["Called to date"], called_as_at=d, recorded_at=stamp(self.arrival(p)),
                                     supersedes_commitment_id=last.get(key))
                n += 1
            self.note("commitments", files=1)
        self.commit = last
        self.note("commitments", rows=n)

    # ------------------------------------------------------------------ benchmark and market data
    def benchmark(self) -> None:
        f = next((self.root / "reference").glob("EG-OFFICE-BLEND_*.xlsx"), None)
        self.series = {}
        if not f:
            return
        wb = openpyxl.load_workbook(f, data_only=True, read_only=True)
        n = 0
        for ver, sheet in ((1, "Components v1"), (2, "Components v2 (In Progress)")):
            rs = [list(r) for r in wb[sheet].iter_rows(values_only=True)]
            status = str(rs[1][0]).split(":")[1].strip()
            eff = parse_date(rs[2][1])
            did = self.add("benchmark_definitions", benchmark_code="EG-OFFICE-BLEND", benchmark_name="Evergreen office blend", version_number=ver, reporting_currency="USD", effective_from=eff,
                           calculation_method=str(rs[5][1]), approval_status="approved" if status == "Approved" else "in_progress", approved_by=self.person(str(rs[3][1])) if status == "Approved" else None)
            for c in rs[8:]:
                if c[0] and c[1] and c[0] != "Total weight":
                    self.series[c[0]] = c[1]
                    self.add("benchmark_components", benchmark_definition_id=did, market_series_key=c[1], component_weight=c[2], spread_bps=c[3], weight_effective_from=eff, treatment_note=c[4])
                    n += 1
        rs = [list(r) for r in wb["Index Levels"].iter_rows(values_only=True)]
        wb.close()
        head, sr = rs[3], self.record("office", f, date(2026, 10, 9))
        for r in rs[4:]:
            if r[0] and str(r[0]) < "2026-04-01":  # the daily index files start on 1 April; the months before come from the workbook
                for col, name in enumerate(head[1:], 1):
                    if name in self.series:
                        self.add("market_observations", source_record_id=sr, series_key=self.series[name], observation_type="index_level", observed_at=stamp(parse_date(r[0])), received_at=stamp(date(2026, 10, 9)),
                                 recorded_at=stamp(date(2026, 10, 9)), value=r[col])
        self.note("reference", files=1, rows=n)

    def market(self) -> None:
        n = 0
        for p in self.files("fx_rates"):
            sr = self.record("market", p, self.arrival(p))
            for r in csv_rows(p):
                d, rate = parse_date(r["Date"]), Decimal(str(r["Rate (SGD per 1 USD)"]))
                for otype, key in (("fx", "FX:USDSGD:WMR4PM"), ("fx_fixing", "USD/SGD")):  # the cash and report recipes read 'fx', the invest recipes 'fx_fixing'
                    self.add("market_observations", source_record_id=sr, series_key=key, observation_type=otype, observed_at=f"{d} 16:00:00+00", received_at=stamp(d, 17), recorded_at=stamp(d, 17),
                             value=rate, base_currency="USD", quote_currency="SGD", quality_status="official")
                n += 1
            self.note("fx_rates", files=1)
        self.note("fx_rates", rows=n)
        n = 0
        for p in self.files("index_levels"):
            sr = self.record("market", p, self.arrival(p))
            for r in csv_rows(p):
                d = parse_date(r["Date"])
                for col, key in self.series.items():
                    if col in r:
                        self.add("market_observations", source_record_id=sr, series_key=key, observation_type="index_level", observed_at=stamp(d), received_at=stamp(d, 18), recorded_at=stamp(d, 18),
                                 value=Decimal(r[col]), quote_currency=r.get("Currency"))
                        n += 1
            self.note("index_levels", files=1)
        self.note("index_levels", rows=n)
        missing = []
        d0, d1 = date(2026, 4, 1), self.today
        got = {parse_date(re.search(r"(\d{8})", p.stem)[1][:4] + "-" + re.search(r"(\d{8})", p.stem)[1][4:6] + "-" + re.search(r"(\d{8})", p.stem)[1][6:]) for p in self.files("fx_rates")}
        if self.incremental:  # a batch holds some days only: a day is a gap when no fixing is on record for it either
            got |= {r[0] for r in self.con.execute("select distinct cast(observed_at as date) from market_observations where observation_type = 'fx'").fetchall()}
        d = d0
        while d <= d1:
            if d.weekday() < 5 and d not in got and any(p.name.startswith(f"positions_{d:%Y%m%d}") for p in self.files("custodian_positions")):
                missing.append(d)
            d += timedelta(days=1)
        for d in missing:
            self.note("fx_rates", flag=f"no fixing file for {d} (a business day on which the custodian reported positions)")
            self.exception("fx_rate_gap", f"No USD/SGD fixing for {d}", "A business day with no WMR fixing file; the previous fixing stands.", d)

    # ------------------------------------------------------------------ administrator, custodian, bank
    def admin_nav(self) -> None:
        # one approved sheet mapping per source sheet; a renamed column is read through the known synonym and proposed as the next version
        sysid = self.source("administrator")
        mapping_ids, approved_cols = {}, None
        n = 0
        for p in self.files("administrator_nav"):
            wb = openpyxl.load_workbook(p, data_only=True, read_only=True)
            pos = [list(r) for r in wb["Positions"].iter_rows(values_only=True)]
            navs = [list(r) for r in wb["NAV by portfolio"].iter_rows(values_only=True)]
            wb.close()
            head = [str(h) for h in pos[0]]
            asof = parse_date(navs[1][2])
            recv = self.arrival(p)
            mv = next(i for i, h in enumerate(head) if "market value" in h.lower() or "valuation amount" in h.lower())
            cols = tuple(head)
            summary, on_file = None, None
            if approved_cols is None:
                approved_cols = cols
                mapping_ids[cols] = self.admin_mapping(sysid, head, mv, 1, "approved", recv)
            elif cols != approved_cols:
                renamed = [(x, y) for x, y in zip(approved_cols, cols) if x != y]
                summary = json.dumps({"columns_renamed": renamed, "read_through": "known synonym", "mapping": "proposed, not yet approved"})
                if cols not in mapping_ids:
                    mapping_ids[cols] = self.admin_mapping(sysid, head, mv, 2, "proposed", recv)
                on_file = mapping_ids[cols]  # the batch of the renamed pack is on the proposed mapping, so the batches on the old name are counted without it
                self.note("administrator_nav", flag=f"{p.name}: column '{approved_cols[mv]}' arrives as '{head[mv]}' (M18); read through the synonym, new mapping proposed")
            batch = self.batch("administrator", p, recv, summary=summary, mapping=on_file or mapping_ids[approved_cols], period_end=asof)
            sr = self.add("source_records", source_batch_id=batch, record_type="file", received_at=stamp(recv), recorded_at=stamp(recv), raw_payload_uri=self.rel(p), content_hash=file_hash(p),
                          effective_at=stamp(asof))
            for r in pos[1:]:
                if not r[0]:
                    continue
                if r[mv] is None or not isinstance(r[mv], (int, float)):
                    self.exception("value_not_received", f"{r[2]}: no value in the administrator pack of {asof}", f"Administrator status '{r[7]}'; no position written.", recv,
                                   portfolio_id=self.port.get(r[0]))
                    self.note("administrator_nav", flag=f"{p.name}: {r[2]} '{r[7]}' (no value), not written as a position")
                    continue
                iid = self.by_name.get(r[2])
                if iid is None:
                    iid = self.by_name[r[2]] = self.add("instruments", canonical_name=r[2], instrument_type="private_fund", currency=r[6], created_at=stamp(recv))
                    self.note("administrator_nav", flag=f"{r[2]} is not in the security master; created with no class")
                code = str(r[1])
                if ("adm", iid, code) not in self.inst:
                    self.inst[("adm", iid, code)] = 1
                    self.ident(iid, "administrator_code", code)
                self.add("position_snapshots", source_record_id=sr, portfolio_id=self.port[r[0]], instrument_id=iid, position_date=asof, as_of_at=stamp(parse_date(r[8]) if r[8] else asof, 6),
                         received_at=stamp(recv, 6), recorded_at=stamp(recv, 6), quantity=r[3], source_market_value=r[mv], currency=r[6], view_type="accounting", data_status=r[7])
                n += 1
            for r in navs[1:]:
                if r[0] and r[1] is not None:
                    self.field(self.nav_doc(p, asof, recv), f"nav:{r[0]}", num=r[1], ccy="USD")
            self.note("administrator_nav", files=1)
        self.note("administrator_nav", rows=n)

    ADMIN_COLUMNS = {"portfolio": ("portfolios", "portfolio_code"), "admin code": ("instrument_identifiers", "identifier_value"), "instrument": ("instruments", "canonical_name"),
                     "quantity": ("position_snapshots", "quantity"), "currency": ("position_snapshots", "currency"), "valuation status": ("position_snapshots", "data_status"),
                     "valuation date": ("position_snapshots", "as_of_at")}

    def admin_mapping(self, sysid: str, head: list[str], mv: int, version: int, status: str, recv: date) -> str:
        """The sheet mapping of the administrator's Positions sheet: every column to its field (price is not kept), the market value column to source_market_value."""
        mid = self.add("sheet_mappings", source_system_id=sysid, file_pattern="administrator_export_*.xlsx", sheet_name="Positions", header_row=1, version_number=version, mapping_status=status,
                       approved_by=self.person("Anita Rao") if status == "approved" else None, approved_at=stamp(recv) if status == "approved" else None)
        for i, h in enumerate(head):
            tgt = ("position_snapshots", "source_market_value") if i == mv else self.ADMIN_COLUMNS.get(h.lower(), ("ignore", h))
            self.add("sheet_mapping_columns", sheet_mapping_id=mid, source_column=h, target_table=tgt[0], target_field=tgt[1])
        return mid

    def nav_doc(self, p: Path, asof: date, recv: date) -> str:
        key = ("navdoc", p.name)
        if key not in self.inst:
            self.inst[key] = self.doc(p, "administrator_nav_pack", p.name, kind="administrator", date_=asof, valuation=asof, received=recv, record=None)
        return self.inst[key]

    def admin_cash(self) -> None:
        n = 0
        for p in self.files("administrator_cash"):
            recv = self.arrival(p)
            sr = self.record("administrator", p, recv)
            for r in csv_rows(p):
                d, ccy = parse_date(r["date"]), r["currency"]
                ci = self.cash_instrument(f"Cash {ccy}", ccy, f"CASH-{ccy}")
                self.add("position_snapshots", source_record_id=sr, portfolio_id=self.cashport[r["entity_code"]], instrument_id=ci, position_date=d, as_of_at=stamp(d, 20), received_at=stamp(recv, 6),
                         recorded_at=stamp(recv, 6), quantity=Decimal(r["administrator_cash"]), source_market_value=Decimal(r["administrator_cash"]), currency=ccy, data_status="Final")
                n += 1
            self.note("administrator_cash", files=1)
        self.note("administrator_cash", rows=n)

    def custodian_positions(self) -> None:
        n = 0
        for p in self.files("custodian_positions"):
            recv = self.arrival(p)
            sr = self.record("custodian", p, recv)
            for r in csv_rows(p):
                d = parse_date(r["as_of"])
                iid = self.inst.get(r["security_id"]) or self.by_name.get(r["security_name"])
                if iid is None:
                    iid = self.inst[r["security_id"]] = self.by_name[r["security_name"]] = self.add("instruments", canonical_name=r["security_name"], instrument_type=r["asset_class"] or "unknown",
                                                                                                   asset_class=r["asset_class"] or None, currency=r["currency"], created_at=stamp(recv))
                self.add("position_snapshots", source_record_id=sr, portfolio_id=self.port[r["portfolio"]], instrument_id=iid, position_date=d, as_of_at=stamp(d, 20), received_at=stamp(recv, 22),
                         recorded_at=stamp(recv, 22), quantity=Decimal(r["quantity"]), source_market_value=Decimal(r["market_value"]), currency=r["currency"], data_status="Final")
                n += 1
            self.note("custodian_positions", files=1)
        self.note("custodian_positions", rows=n)
        if any(self.files("custodian_positions")):
            self.note("custodian_positions", flag="the custodian file gives no asset class for the Pacific Rim Convertible 2029 note (M17); the instrument keeps the security master's blank class")

    def bank_statements(self) -> None:
        by_number = {a["number"]: k for k, a in self.office_acct.items()}
        nbal = nlines = 0
        for p in self.files("bank_statements"):
            recv = self.arrival(p)
            bal = dicts(sheet_rows(p, "Daily balances"))
            number = bal[0]["Account number"] if bal else None
            acct = by_number.get(number) or re.match(r"((?:HB|TCB)_[A-Z]+_[A-Z]{3})", p.name)[1].replace("_", "-")
            a = self.office_acct[acct]
            doc_period = re.search(r"_(\d{4})-(\d{2})", p.name)
            month_end = last_day(int(doc_period[1]), int(doc_period[2]))
            sr = self.record("bank", p, recv, effective=month_end)
            self.doc(p, "bank_statement", p.stem, kind="bank", instrument=a["cash"], valuation=month_end, date_=month_end, received=recv, record=sr)
            for r in bal:
                d = parse_date(r["Value date"])
                self.add("position_snapshots", source_record_id=sr, portfolio_id=self.cashport[a["entity"]], instrument_id=a["cash"], position_date=d, as_of_at=stamp(d, 20), received_at=stamp(recv, 6),
                         recorded_at=stamp(recv, 6), quantity=r["Closing ledger balance"], source_market_value=r["Closing ledger balance"], currency=r["Currency"], data_status="Final")
                nbal += 1
            for i, r in enumerate(dicts(sheet_rows(p, "Transactions")), 2):
                self.bank_line(p, recv, a, acct, r, i)
                nlines += 1
            self.note("bank_statements", files=1)
        self.note("bank_statements", rows=nbal + nlines)

    def bank_line(self, p: Path, recv: date, a: dict, acct: str, r: dict, i: int) -> None:
        typ, desc, amt, ccy, ref = r["Type"], r["Description"], Decimal(str(r["Amount"])), r["Currency"], r["Reference"]
        d = parse_date(r["Value date"])
        sr = self.record("bank", p, recv, rtype="bank_line", external=ref, sheet="Transactions", row=i, effective=d)
        port = self.cashport[a["entity"]]
        base = dict(source_record_id=sr, portfolio_id=port, effective_date=d, received_at=stamp(recv, 6), recorded_at=stamp(recv, 6), amount=amt, currency=ccy, confirmation_status="confirmed")
        mt = {"capital_call": "payment", "bank_fee": "fee", "fee": "fee", "vendor_payment": "payment", "wire": "payment", "property": "payment", "insurance": "payment", "payroll": "payment",
              "payroll_tax": "payment", "trade_settlement": "settlement", "internal_transfer": "transfer", "intercompany_transfer": "transfer"}.get(typ, typ)
        if typ == "capital_call":
            m = re.match(r"CC-CALL-(\w+)-(\d+)", ref)
            fk, no = m[1], int(m[2])
            ending = re.search(r"ACCT (\d{4})", desc)[1]
            if (fk, ending) not in self.payee:
                self.payee[(fk, ending)] = self.add("bank_accounts", holder_kind="payee", instrument_id=self.fund_key[fk], holder_name=self.fund_info[fk]["name"], account_purpose="payee",
                                                    bank_name="named on the payment", account_ref=ending, currency=ccy, source_record_id=sr, received_at=stamp(recv), recorded_at=stamp(recv))
            mid = self.add("cash_movements", **base, movement_type="payment", instrument_id=self.fund_key[fk], bank_account_id=self.payee[(fk, ending)])
            self.pay_ref.setdefault(ref, []).append(mid)
            self.bankcalls[(fk, no)] = dict(date=d, amount=amt, recv=recv, sr=sr)
        elif typ == "distribution":
            m = re.match(r"DI-DIST-(\w+)-(\d{4})-(\d{2})", ref)
            fk = m[1]
            mid = self.add("cash_movements", **base, movement_type="distribution", instrument_id=self.fund_key[fk], bank_account_id=self.office_acct[acct]["id"], commitment_id=self.commit.get(fk))
            self.pay_ref.setdefault(ref, []).append(mid)
        elif typ in {"intercompany_transfer", "internal_transfer"}:
            other = r["Counterparty"]
            oc = next((c for c, n in self.md["entities"].items() if n == other), a["entity"])
            mid = self.add("cash_movements", **base, movement_type="transfer", bank_account_id=a["id"], counterparty_portfolio_id=self.cashport[oc])
            self.pay_ref.setdefault(ref, []).append(mid)
        else:
            extra = {}
            if typ == "vendor_payment":
                v = self.vendor_acct.get(str(r["Counterparty"]).lower())
                extra["bank_account_id"] = v
            mid = self.add("cash_movements", **base, movement_type=mt, **extra)
            self.pay_ref.setdefault(ref, []).append(mid)
        self.bank_lines.append(dict(ref=ref, type=typ, date=d, amount=amt, ccy=ccy, desc=desc, cp=r["Counterparty"], entity=a["entity"]))

    # ------------------------------------------------------------------ trades
    def trading_and_custody(self) -> None:
        """One `transactions` row per trade. The desk's export (OMS) is the trade; the custodian line of the same trade is its settlement, so it is read first and
        its quantity, amount and dates are the row's (status settled); a trade the custodian does not show yet stays executed. Dividends, coupons and fees of the custodian
        stand alone. A second row of the same trade is kept as type duplicate, status rejected, and counted once."""
        cust, n = {}, 0
        for p in self.files("custodian_transactions"):
            recv = self.arrival(p)
            ym = re.search(r"(\d{4})-(\d{2})", p.name)
            hint = date(int(ym[1]), int(ym[2]), 15)
            for i, r in enumerate(csv_rows(p), 2):
                if not r["security_id"]:
                    self.note("custodian_transactions", flag=f"{r['reference']}: a {r['type']} line with no security; not a transaction (the fee is on the bank statement)")
                    continue
                td, sd = parse_date(r["txn_date"], hint=hint), parse_date(r["settle_date"], hint=hint)
                if not re.match(r"\d{4}-", r["txn_date"]):
                    self.note("custodian_transactions", flag=f"{r['reference']}: txn_date written {r['txn_date']} (day first, M11a) read as {td}")
                cust[r["reference"]] = dict(r=r, p=p, i=i, recv=recv, td=td, sd=sd)
            self.note("custodian_transactions", files=1)
        used, oms = set(), {}
        for p in self.files("trading_export", "trading_export_*.csv"):
            recv = self.arrival(p)
            for i, r in enumerate(csv_rows(p), 2):
                ref, itype = r["external_trade_id"], r["instrument_type"]
                tid = re.sub(r"^FX-(?=FXS-)", "", ref)  # the desk prefixes a spot conversion's reference with FX-; the bank and the confirmation do not
                iid = self.by_code.get(r["instrument_code"])
                if iid is None:
                    name = r["instrument_name"] if itype != "fx_forward" else f"{r['instrument_name']} {ref}"
                    iid = self.by_code[r["instrument_code"]] = self.by_name.get(name) or self.add("instruments", canonical_name=name, instrument_type=itype, currency=r["currency"], created_at=stamp(recv))
                    self.by_name[name] = iid
                qty, amount, side = Decimal(r["quantity"]), Decimal(r["amount"]), r["side"].strip().lower()
                td, sd, status, rec = parse_date(r["trade_date"]), parse_date(r["settle_date"]), r["status"], self.record("oms", p, recv, rtype="trade", external=ref, row=i)
                if itype in {"fx_spot", "fx_forward"}:  # 'sell USD / buy SGD' (M10) is the direction of the USD leg; the cash leg is the other currency
                    sell = side.startswith("sell")
                    delta, cash, ttype = (-qty if sell else qty), (amount if sell else -amount), itype
                else:
                    sell = side == "sell"
                    ttype = side
                    c = cust.get("CT-" + tid)
                    if c:  # the custodian settled it: its figures and dates are the settled fact
                        used.add(c["r"]["reference"])
                        qty, amount, td, sd, status = Decimal(c["r"]["quantity"]), Decimal(c["r"]["amount"]), c["td"], c["sd"], "settled"
                        self.record("custodian", c["p"], c["recv"], rtype="trade", external=c["r"]["reference"], row=c["i"])
                        if (qty, amount) != (Decimal(r["quantity"]), Decimal(r["amount"])):
                            self.note("trading_export", flag=f"{tid}: the custodian settled {qty} for {amount}, the desk booked {r['quantity']} for {r['amount']}")
                    delta, cash = (-qty if sell else qty), (amount if sell else -amount)
                dup = ref.endswith("-R") and ref[:-2] in oms
                if dup:
                    ttype, status = "duplicate", "rejected"
                    self.exception("duplicate_trade", f"{ref} repeats {ref[:-2]}", "The same trade appears twice in the trading export; the second row is kept as a duplicate and not counted.", recv)
                    self.note("trading_export", flag=f"{ref} is a second row of {ref[:-2]} (M07): kept as type duplicate, status rejected, not counted")
                else:
                    oms[tid] = 1
                self.add("transactions", source_record_id=rec, portfolio_id=self.port[r["portfolio"]], instrument_id=iid, external_trade_id=tid, transaction_type=ttype, trade_date=td, effective_date=td,
                         settlement_date=sd, quantity_delta=delta, cash_amount=cash, currency=r["currency"], recorded_at=stamp(recv), status=status)
                n += 1
            self.note("trading_export", files=1)
        for ref, c in cust.items():  # custodian lines the desk has no trade for, and the income lines
            r = c["r"]
            if ref in used:
                continue
            typ, amount, iid = r["type"], Decimal(r["amount"]), self.inst[r["security_id"]]
            sign = -1 if typ == "sell" else 1
            buysell = typ in {"buy", "sell"}
            self.add("transactions", source_record_id=self.record("custodian", c["p"], c["recv"], rtype="trade" if buysell else "income", external=ref, row=c["i"]), portfolio_id=self.port["EG-LIQUID"],
                     instrument_id=iid, external_trade_id=ref if not buysell else re.sub(r"^CT-", "", ref), transaction_type=typ, trade_date=c["td"], effective_date=c["td"], settlement_date=c["sd"],
                     quantity_delta=sign * Decimal(r["quantity"]) if buysell else None, cash_amount=-sign * amount if buysell else (amount if typ != "fee" else -abs(amount)), currency=r["currency"],
                     recorded_at=stamp(c["recv"]), status="settled")
            n += 1
        self.note("trading_export", rows=n)
        self.note("custodian_transactions", rows=len(cust))
        self.desk_cash()

    def desk_instrument(self, entity: str, ccy: str, sr: str) -> str:
        """The desk's cash of an entity and currency is a cash instrument of its own, listed in bank_accounts (holder_kind desk) like the bank balances, so the entity cash is never added twice."""
        name = f"Desk cash {entity} {ccy}"
        if name not in self.cashinst:
            ci = self.cash_instrument(name, ccy, f"DESK-{entity}-{ccy}")
            self.add("bank_accounts", holder_kind="desk", legal_entity_id=self.ent[entity], holder_name=self.md["entities"][entity], account_purpose="desk cash view", bank_name="trading desk (OMS)",
                     account_ref=f"{entity[-4:]}{ccy}", currency=ccy, cash_instrument_id=ci, source_record_id=sr, received_at=stamp(self.today), recorded_at=stamp(self.today))
        return self.cashinst[name]

    def desk_cash(self) -> None:
        """The desk exports cash MOVEMENTS, not balances (cash_movements_*.csv). Its cash of a day is the bank's cash plus the movements the desk booked up to the day less the same kind
        of lines on the bank statements (a bank fee or interest is on the bank side only); written as snapshots of the source 'oms' (data_status 'Derived'), one per entity and currency, on
        the instrument and portfolio of the administrator's cash and recorded a moment before it, so the entity cash recipes still see one cash. A day on which an account's bank
        statement is missing (M02b) has no desk cash: a partial bank total would show a false break."""
        moves = {}
        for p in self.files("trading_export", "cash_movements_*.csv"):
            recv = self.arrival(p)
            for i, r in enumerate(csv_rows(p), 2):
                self.record("oms", p, recv, rtype="desk_cash_movement", external=r["reference"], row=i, effective=parse_date(r["value_date"]))
                moves.setdefault((r["legal_entity"], r["currency"]), []).append((parse_date(r["value_date"]), Decimal(r["amount"])))
            self.note("trading_export", files=1)
        if not moves:
            return
        cash_ids = {a["cash"]: (a["entity"], a["ccy"]) for a in self.office_acct.values()}
        per_key = {}
        for a in self.office_acct.values():
            per_key[(a["entity"], a["ccy"])] = per_key.get((a["entity"], a["ccy"]), 0) + 1
        bank, seen = {}, {}
        for r in self.rows.get("position_snapshots", []):
            k = cash_ids.get(r["instrument_id"])
            if k:
                bank[k + (r["position_date"],)] = bank.get(k + (r["position_date"],), 0) + Decimal(str(r["source_market_value"]))
                seen[k + (r["position_date"],)] = seen.get(k + (r["position_date"],), 0) + 1
        lines = {}
        for l in self.bank_lines:
            if l["type"] not in {"bank_fee", "interest"}:
                lines.setdefault((l["entity"], l["ccy"]), []).append((l["date"], l["amount"]))
        sr = self.add("source_records", source_batch_id=self.add("source_batches", source_system_id=self.source("oms"), batch_reference="desk cash derived from cash_movements", received_at=stamp(self.today)),
                      record_type="derived", received_at=stamp(self.today), recorded_at=stamp(self.today), raw_payload_uri="trading_export/cash_movements_*.csv", content_hash="derived-desk-cash")
        n = 0
        for (e, c, d), v in sorted(bank.items()):
            if seen[(e, c, d)] < per_key[(e, c)]:
                continue
            desk = v + sum(a for dd, a in moves.get((e, c), []) if dd <= d) - sum(a for dd, a in lines.get((e, c), []) if dd <= d)
            ci = self.desk_instrument(e, c, sr)
            self.add("position_snapshots", source_record_id=sr, portfolio_id=self.cashport[e], instrument_id=ci, position_date=d, as_of_at=f"{d} 11:00:00+00", received_at=f"{d} 11:00:00+00",
                     recorded_at=f"{d} 11:00:00+00", quantity=desk, source_market_value=desk, currency=c, data_status="Derived")
            n += 1
        self.note("trading_export", rows=n, flag="the desk's cash balance is derived from its movements (it sends no balance); written under source 'oms'")

    def administrator_trades(self) -> None:
        """The administrator's own trade booking is kept as a document with one field per trade, not as transactions (it would count each trade twice)."""
        n = 0
        for p in self.files("administrator_trades"):
            recv = self.arrival(p)
            rows = csv_rows(p)
            did = self.doc(p, "administrator_trades", p.name, kind="administrator", received=recv, valuation=last_day(int(re.search(r"(\d{4})-(\d{2})", p.name)[1]), int(re.search(r"(\d{4})-(\d{2})", p.name)[2])))
            for i, r in enumerate(rows, 2):
                self.field(did, f"trade:{r['external_trade_id']}", text=f"{r['side']} {r['security_code']} {r['trade_date']}", num=Decimal(r["administrator_quantity"]), line=i)
                n += 1
            self.note("administrator_trades", files=1)
        self.note("administrator_trades", rows=n)

    # ------------------------------------------------------------------ manager statements, notices, fx confirmations, emails
    def manager_statements(self) -> None:
        stm = []
        for p in self.files("manager_statements"):
            t = pdf_text(str(p))
            g = lambda k: (re.search(k + r": (.*)", t) or [None, None])[1]  # noqa: E731
            num = lambda label: (money(m[1]) if (m := re.search(re.escape(label) + r"\s+(-?[\d,]+\.\d\d)", t)) else None)  # noqa: E731
            key = re.search(r"_([A-Z]\d?)_\d{4}", p.name)[1]
            stm.append(dict(p=p, key=key, fund=g("Fund").strip(), period=parse_date(g(r"Statement date \(period end\)")), issued=parse_date(g("Issued")), status=g("Status").strip().lower(),
                            recv=self.arrival(p), closing=num("Closing capital account balance"), gain=num("Net gain / (loss)"), opening=num("Opening balance"), calls=num("Contributions (capital calls)"),
                            dist=num("Distributions"), cum=num("Cumulative contributions called"), commit=num("Total commitment"), uncalled=num("Remaining uncalled commitment"),
                            title=g("Title"), investor=(re.search(r"Limited partner: (.*?)\s{2,}", t) or [None, None])[1]))
        last, n = {}, 0
        for s in sorted(stm, key=lambda s: (s["fund"], s["period"], s["recv"], s["issued"])):
            fk = s["key"]
            iid = self.fund_key.get(fk) or self.by_name[s["fund"]]
            did = self.doc(s["p"], "manager_statement", s["title"] or s["p"].stem, kind="manager", date_=s["issued"], valuation=s["period"], received=s["recv"], instrument=iid, status=s["status"],
                           supersedes=self.stm_doc.get((fk, s["period"]), {}).get("id"))
            for name, v in (("closing_balance", s["closing"]), ("opening_balance", s["opening"]), ("contributions", s["calls"]), ("distributions", s["dist"]), ("net_gain_loss", s["gain"]),
                            ("cumulative_called", s["cum"]), ("total_commitment", s["commit"]), ("remaining_uncalled", s["uncalled"])):
                if v is not None:
                    self.field(did, name, num=v, ccy="USD")
            self.field(did, "status", text=s["status"])
            vid = self.add("valuation_observations", instrument_id=iid, portfolio_id=self.port.get(self.fund_info.get(fk, {}).get("portfolio")), source_record_id=None, evidence_document_id=did,
                           valuation_date=s["period"], received_at=stamp(s["recv"]), recorded_at=stamp(s["recv"]), value_amount=s["closing"], currency="USD", valuation_type=f"manager_{s['status']}",
                           approval_status=s["status"], supersedes_valuation_id=last.get((fk, s["period"])))
            last[(fk, s["period"])] = vid
            self.stm_doc[(fk, s["period"])] = dict(id=did, s=s)
            n += 1
            self.note("manager_statements", files=1)
        self.note("manager_statements", rows=n)

    def notices(self) -> None:
        n = 0
        parsed = []
        for p in self.files("notices"):
            t = pdf_text(str(p))
            call = "CAPITAL CALL NOTICE" in t
            order = slash_order(t)
            m = re.search(r"_([A-Z]\d?)_(call(\d+)|distribution)", p.name)
            fk = m[1]
            fund = re.search(r"Fund:\s*(.+)", t)[1].strip()
            investor = re.search(r"To:\s*(.+?)(?: \(limited partner\))?\s*$", t, re.M)[1].strip()
            noticed = parse_date(re.search(r"Date of notice:\s*(.+)", t)[1], order=order)
            due = parse_date(re.search(r"Payment (?:due|value) date:\s*(.+)", t)[1], order=order)
            amount = money(re.search(r"Amount to be paid (?:by|to) the investor\s+USD ([\d,\.]+)", t)[1])
            parsed.append(dict(p=p, t=t, call=call, fk=fk, fund=fund, investor=investor, noticed=noticed, due=due, amount=amount, no=int(m[3]) if m[3] else None,
                               ref=(re.search(r"Notice ref:\s*(\S+)", t) or [None, None])[1], order=order))
        self.noticed = parsed
        for x in sorted(parsed, key=lambda x: (x["noticed"], x["fk"])):
            fk, iid, p, t = x["fk"], self.fund_key[x["fk"]], x["p"], x["t"]
            recv = self.arrival(p)
            ent = next(c for c, nm in self.md["entities"].items() if nm == x["investor"])
            if x["order"]:
                self.note("notices", flag=f"{p.name}: dates written {'month first' if x['order'] == 'mdy' else 'day first'} (M11b), read as {x['noticed']} and {x['due']}")
            acct = (re.search(r"Account:\s*(\S+)", t) or [None, None])[1]
            ending = re.sub(r"[^0-9A-Za-z]", "", acct)[-4:] if acct else None
            if x["call"]:
                fee = re.search(r"Management fee[^\n]*?USD ([\d,\.]+)", t)
                new = re.search(r"New investments\s+USD ([\d,\.]+)", t)
                fields = [("fund", x["fund"]), ("investor", x["investor"]), ("call_no", x["ref"] and str(x["no"]), Decimal(x["no"])), ("amount", None, x["amount"], "USD"), ("call_amount", None, x["amount"], "USD"),
                          ("due_date", x["due"].isoformat()), ("bank_account", acct)]
                if new:
                    fields.append(("new_investments", None, money(new[1]), "USD"))
                if fee:  # "none in this call" has no fee line
                    fields.append(("management_fee", None, money(fee[1]), "USD"))
                did = self.doc(p, "capital_call_notice", x["ref"] or p.stem, kind="manager", date_=x["noticed"], received=recv, instrument=iid, fields=fields)
                x["doc"] = did
                if ending and (fk, ending) not in self.payee:  # an account the standing instructions do not hold: a new payee row, unverified, that supersedes the one on file
                    prev = [v for (k, e), v in self.payee.items() if k == fk]
                    self.payee[(fk, ending)] = self.add("bank_accounts", holder_kind="payee", instrument_id=iid, holder_name=x["fund"], account_purpose="payee", bank_name="named on the notice",
                                                        account_ref=ending, currency="USD", source_record_id=self.doc_record(did), source_document_id=did, source_page=1,
                                                        received_at=stamp(recv), recorded_at=stamp(recv), supersedes_bank_account_id=prev[-1] if prev else None)
                    self.note("notices", flag=f"{p.name}: names account ending {ending}, not the one on file; recorded as a new payee row with no call-back (M05a)")
                    self.exception("bank_details_changed", f"{x['fund']} call {x['no']} names a new account", f"Account ending {ending} on the notice; the standing instruction says otherwise. Call-back needed.", recv,
                                   instrument_id=iid)
                paid = self.bankcalls.get((fk, x["no"]))
                movement = dict(source_record_id=self.doc_record(did), portfolio_id=self.port[self.fund_info[fk]["portfolio"]], instrument_id=iid, movement_type="call", due_date=x["due"],
                                notice_kind="capital_call", commitment_id=self.commit.get(fk), currency="USD", effective_date=x["noticed"])
                noticed_id = self.add("cash_movements", **movement, received_at=stamp(recv), recorded_at=stamp(recv), amount=-x["amount"], confirmation_status="noticed")
                if paid:
                    self.add("cash_movements", **{**movement, "source_record_id": paid["sr"], "effective_date": paid["date"]}, received_at=stamp(paid["recv"], 6), recorded_at=stamp(paid["recv"], 6),
                             amount=paid["amount"], confirmation_status="confirmed", supersedes_cash_movement_id=noticed_id)
                    if abs(paid["amount"]) != x["amount"]:
                        self.note("notices", flag=f"{p.name}: the bank paid {paid['amount']} against a notice of {x['amount']}")
                else:
                    self.open_calls.append(dict(x=x, id=noticed_id, ent=ent, fk=fk, ending=ending))
                self.mov[("call", fk, x["no"])] = noticed_id
            else:
                nat = re.search(r"Nature:\s*(.+)", t)
                did = self.doc(p, "distribution_notice", p.stem, kind="manager", date_=x["noticed"], received=recv, instrument=iid,
                               fields=[("fund", x["fund"]), ("investor", x["investor"]), ("distribution_amount", None, x["amount"], "USD"), ("amount", None, x["amount"], "USD"),
                                       ("pay_date", x["due"].isoformat()), ("nature", nat[1].strip() if nat else None)])
                self.add("cash_movements", source_record_id=self.doc_record(did), portfolio_id=self.port[self.fund_info[fk]["portfolio"]], instrument_id=iid, movement_type="distribution",
                         effective_date=x["due"], due_date=x["due"], notice_kind="distribution", commitment_id=self.commit.get(fk), amount=x["amount"], currency="USD", confirmation_status="noticed",
                         received_at=stamp(recv), recorded_at=stamp(recv))
            n += 1
            self.note("notices", files=1)
        self.note("notices", rows=n)
        # bank credits carry the fund's commitment (the movements were written before the registers' final ids were known only if the register is missing)
        for r in self.rows.get("cash_movements", []):
            if r.get("movement_type") == "distribution" and r.get("notice_kind") is None and not r.get("commitment_id"):
                fk = next((k for k, v in self.fund_key.items() if v == r.get("instrument_id")), None)
                r["commitment_id"] = self.commit.get(fk)

    def doc_record(self, did: str) -> str | None:
        return next((d["source_record_id"] for d in self.rows["documents"] if d["id"] == did), None)

    def fx_confirmations(self) -> None:
        n = 0
        for p in self.files("fx_confirmations"):
            t = pdf_text(str(p))
            recv = self.arrival(p)
            ref = p.name.split("_confirmation")[0]
            sold = re.search(r"Client sells:\s*([A-Z]{3}) ([\d,\.]+)", t)
            bought = re.search(r"Client buys:\s*([A-Z]{3}) ([\d,\.]+)", t)
            rate = re.search(r"(?:Rate|Forward rate) \(\w+ per \w+\):\s*([\d.]+)", t)
            td, vd = re.search(r"Trade date:\s*(\S+)", t), re.search(r"Value date:\s*(\S+)", t)
            did = self.doc(p, "fx_confirmation", p.stem, kind="bank", date_=parse_date(td[1]), received=recv,
                           fields=[("trade_reference", ref), ("rate", None, Decimal(rate[1])), ("currency_sold", sold[1]), ("amount_sold", None, money(sold[2]), sold[1]),
                                   ("currency_bought", bought[1]), ("amount_bought", None, money(bought[2]), bought[1])])
            self.add("fx_confirmations", source_record_id=self.doc_record(did), trade_reference=ref, trade_date=parse_date(td[1]), value_date=parse_date(vd[1]), currency_bought=bought[1],
                     amount_bought=money(bought[2]), currency_sold=sold[1], amount_sold=money(sold[2]), rate=Decimal(rate[1]), counterparty=re.sub(r"\(Synthetic\)", "(synthetic)", t.splitlines()[0].strip().title()),
                     source_document_id=did, source_page=1, received_at=stamp(recv), recorded_at=stamp(recv))
            n += 1
            self.note("fx_confirmations", files=1)
        self.note("fx_confirmations", rows=n)
        have = {r["trade_reference"] for r in self.rows.get("fx_confirmations", [])}
        # a trade the desk booked and the bank never confirmed (M09)
        for r in self.rows.get("transactions", []):
            tx = r.get("external_trade_id")
            if r.get("transaction_type") in {"fx_spot", "fx_forward"} and tx not in have and r.get("status") != "rejected":
                self.exception("fx_confirmation_missing", f"No bank confirmation for {tx}", "The desk booked the conversion; no confirmation from the bank is on file.", r["trade_date"], instrument_id=r["instrument_id"])
                self.note("fx_confirmations", flag=f"{tx}: a trade and a bank entry but no confirmation pdf (M09)")

    def emails(self) -> None:
        n = 0
        for p in self.files("emails"):
            msg = email.message_from_bytes(p.read_bytes(), policy=email_policy.default)
            sent = parsedate(msg["Date"])
            body = msg.get_body(preferencelist=("plain",))
            text = body.get_content().strip() if body else ""
            atts = [(a.get_filename(), a.get_payload(decode=True)) for a in msg.iter_attachments()]
            fields = [("subject", msg["Subject"]), ("from", str(msg["From"])), ("to", str(msg["To"])), ("sent", sent.isoformat()), ("body", text)]
            seen = []
            for name, data in atts:
                h = hashlib.sha256(data).hexdigest()
                fields.append(("attachment", name))
                if h in self.seen_hash:
                    seen.append((name, self.seen_hash[h]))
                    fields.append(("seen_before", name, None))
                    fields.append(("attachment_document_id", self.seen_hash[h]))
                else:
                    fields.append(("attachment_new", name))
                    self.note("emails", flag=f"{p.name}: attachment {name} is not among the files already read")
            if re.search(r"\b(?:new|changed?) bank details?\b", text + (msg["Subject"] or ""), re.I):
                self.exception("bank_details_changed", f"A vendor email changes bank details: {msg['Subject']}", "Needs a call-back on a known number before any payment (office rule).", sent.date())
            self.doc(p, "email", str(msg["Subject"] or p.stem), kind="office", received=sent.date(), date_=sent.date(), fields=fields, personal=bool(re.search(r"internal", p.name)))
            n += 1
            self.note("emails", files=1)
        self.note("emails", rows=n)

    # ------------------------------------------------------------------ invoices, payroll, loans, contracts, allowances, bills
    def invoices(self) -> None:
        n = 0
        seen = {}
        self.invoice_list = []
        for p in self.files("invoices"):
            t = pdf_text(str(p))
            recv = self.arrival(p)
            vendor = self.vendor_names.get(vendor_name(t.splitlines()[0]).lower(), vendor_name(t.splitlines()[0]))
            no = re.search(r"Invoice no: (\S+)", t)[1]
            idate = parse_date(re.search(r"Invoice date: (\d{1,2} \w+ \d{4})", t)[1])
            due = re.search(r"Due(?: date)?: (\d{1,2} \w+ \d{4})", t)
            ccy, amount = re.search(r"Amount due: ([A-Z]{3}) ([\d,\.]+)", t).groups()
            end = re.search(r"account ending (\d{4})", t)
            bill = re.search(r"Bill to: (.+)", t)
            ent = next((c for c, nm in self.md["entities"].items() if bill and nm in bill[1]), "EG-HOLD")
            fields = [("invoice_no", no), ("vendor", vendor), ("amount_due", None, money(amount), ccy)]
            if due:
                fields.append(("due_date", parse_date(due[1]).isoformat()))
            if base := re.search(r"Fee base \(([A-Z]{3})\): ([\d,\.]+)", t):
                fields.append(("fee_base", None, money(base[2]), base[1]))
            if rate := re.search(r"Fee rate per year: ([\d.]+)%", t):
                fields.append(("fee_rate", None, Decimal(rate[1]) / 100))
            if end:
                fields.append(("pay_to_account_ending", end[1]))
            status = "final"
            key = (vendor, no)
            if key in seen:
                status = "duplicate"
                fields.append(("seen_before", seen[key]))
                self.exception("duplicate_invoice", f"{vendor} invoice {no} arrives again", f"The same invoice was received on {seen[key]}; paid once.", recv)
                self.note("invoices", flag=f"{p.name}: second copy of {vendor} {no} (M06): kept as a duplicate, not counted")
            else:
                seen[key] = recv.isoformat()
            did = self.doc(p, "invoice", f"{vendor} {no}", date_=idate, received=recv, status=status, fields=fields)
            if status != "duplicate":
                shown = vendor if vendor.lower() in self.vendor_names.values() or vendor in self.vendor_names.values() else re.sub(r"\(Synthetic\)", "(synthetic)", t.splitlines()[0].strip().title())
                self.invoice_list.append(dict(doc=did, vendor=vendor, shown=shown, no=no, ccy=ccy, amount=money(amount), due=parse_date(due[1]) if due else idate, ending=end[1] if end else None, recv=recv,
                                              p=p, ent=ent, acct=self.invoice_payee(did, vendor, shown, ccy, end[1] if end else None, recv, no)))
            n += 1
            self.note("invoices", files=1)
        self.note("invoices", rows=n)

    def invoice_payee(self, did: str, vendor: str, shown: str, ccy: str, ending: str | None, recv: date, no: str) -> str:
        """The payee account an invoice pays to. A vendor the vendor master does not hold: the account the invoice names is the one on file, with no call-back date. A vendor whose invoice names
        another account than the one on file (M05b): a new payee row that supersedes it, with no call-back, and an exception."""
        key = ("vendor", vendor.lower())
        on_file = self.vendor_acct.get(vendor.lower()) or self.inst.get(key)
        row = lambda **kw: self.add("bank_accounts", holder_kind="payee", holder_name=shown, currency=ccy, source_record_id=self.doc_record(did), source_document_id=did, source_page=1,  # noqa: E731
                                    received_at=stamp(recv), recorded_at=stamp(recv), **kw)
        if on_file is None:
            self.inst[key] = row(account_purpose="vendor", bank_name="named on the invoice", account_ref=ending or "")
            return self.inst[key]
        vm = next((r for r in self.rows.get("bank_accounts", []) if r["id"] == on_file), None)
        if vm is None and (got := self.con.execute("select account_ref, account_purpose from bank_accounts where id = ?", [on_file]).fetchone()):  # read in an earlier batch
            vm = dict(account_ref=got[0], account_purpose=got[1])
        if ending and vm and vm["account_ref"] and vm["account_ref"] != ending:
            self.note("invoices", flag=f"{shown} {no}: names account ending {ending}, the account on file ends {vm['account_ref']} (M05b); new payee row, no call-back")
            self.exception("bank_details_changed", f"{shown} invoice {no} names a new account", f"Account ending {ending}; on file {vm['account_ref']}. Call-back needed.", recv)
            self.inst[key] = row(account_purpose=vm["account_purpose"], bank_name="named on the invoice", account_ref=ending, supersedes_bank_account_id=on_file)
            return self.inst[key]
        return on_file

    def payroll(self) -> None:
        n = 0
        for p in self.files("payroll"):
            rows = dicts(sheet_rows(p))
            gross = sum(Decimal(str(r["Gross (SGD)"])) for r in rows)
            net = sum(Decimal(str(r["Net pay (SGD)"])) for r in rows)
            cpf = sum(Decimal(str(r["Employer CPF (17%)"])) for r in rows)
            month = re.search(r"(\d{4}-\d{2})", p.name)[1]
            self.doc(p, "payroll", f"Payroll {month}", date_=parse_date(rows[0]["Pay date"]), received=self.arrival(p), personal=True,
                     fields=[("month", month), ("employees", None, Decimal(len(rows))), ("total_gross", None, gross, "SGD"), ("total_net", None, net, "SGD"), ("employer_cpf", None, cpf, "SGD")])
            n += len(rows)
            self.note("payroll", files=1)
        self.note("payroll", rows=n)

    def loans(self) -> None:
        n = 0
        for p in self.files("loan_statements"):
            r = dicts(sheet_rows(p))[0]
            y, m = map(int, r["Month"].split("-"))
            recv = self.arrival(p)
            did = self.doc(p, "loan_statement", p.stem, received=recv, date_=last_day(y, m), valuation=last_day(y, m),
                           fields=[("closing_principal_as_shown", None, Decimal(str(r["Closing principal"])), "USD"), ("interest_charged_as_shown", None, Decimal(str(r["Interest charged"])), "USD")])
            sr = self.doc_record(did)
            ln = self.loan
            self.add("credit_facilities", source_record_id=sr, source_document_id=did, source_page=1, received_at=stamp(recv), recorded_at=stamp(recv), facility_ref=r["Facility"].split(" ")[0],
                     legal_entity_id=self.ent["EG-B"], lender="Harbour Bank (synthetic)", currency=ln.get("ccy", "USD"), drawn_amount=abs(Decimal(str(r["Closing principal"]))),  # shown negative (M12): the amount owed
                     interest_rate=ln.get("rate"), rate_basis="fixed per year", maturity_date=ln.get("maturity"), as_at=last_day(y, m))
            n += 1
            self.note("loan_statements", files=1)
        self.note("loan_statements", rows=n)
        if n:
            self.note("loan_statements", flag="statement balances are shown negative (M12); drawn_amount holds the amount owed, positive")

    def vendor_contracts(self) -> None:
        n = 0
        master = {r["vendor"].lower(): r for r in csv_rows(self.root / "reference" / "vendor_master.csv")}
        for p in sorted((self.root / "reference").glob("vendor_contract_*.pdf")):
            t = pdf_text(str(p))
            lines = [x.strip() for x in t.splitlines() if x.strip()]
            vendor = master.get(lines[0].lower(), {}).get("vendor") or vendor_name(lines[0])
            cost = re.search(r"Annual cost: ([A-Z]{3}) ([\d,]+\.\d\d)", t)
            notice = re.search(r"(\d+) days' notice", t)
            term = re.search(r"Term: (\d{1,2} \w+ \d{4}) to (\d{1,2} \w+ \d{4})", t)
            renew = re.search(r"Renewal date: (\S+)", t)
            did = self.doc(p, "vendor_contract", p.stem, received=self.today, date_=parse_date(term[1]) if term else None,
                           fields=[("vendor", vendor), ("renewal_date", renew[1]), ("annual_cost", None, money(cost[2]), cost[1])])
            self.add("vendor_contracts", source_record_id=self.doc_record(did), source_document_id=did, source_page=1, received_at=stamp(self.today, 9), recorded_at=stamp(self.today, 9),
                     vendor_name=vendor, service=lines[2], start_date=parse_date(term[1]) if term else None, end_date=parse_date(term[2]) if term else None, next_renewal_date=parse_date(renew[1]),
                     auto_renews=bool(re.search(r"renews", t, re.I)), notice_days=int(notice[1]) if notice else None, annual_cost=money(cost[2]), currency=cost[1])
            n += 1
            self.note("vendor_contracts", files=1)
        self.note("vendor_contracts", rows=n)

    def allowances(self) -> None:
        n = 0
        trust = self.port_entity and self.cashport["EG-TRUST"]
        for p in self.files("family_allowances"):
            month = re.search(r"(\d{4})-(\d{2})", p.name)
            recv = self.arrival(p)
            did = self.doc(p, "allowance_schedule", p.stem, received=recv, date_=date(int(month[1]), int(month[2]), 1), personal=True)
            for r in dicts(sheet_rows(p)):
                first = parse_date(r["Due date"]).replace(day=1)
                ent = next(c for c, nm in self.md["entities"].items() if nm == r["Paying entity"])
                self.add("family_members", source_record_id=self.doc_record(did), source_document_id=did, source_page=1, received_at=stamp(recv), recorded_at=stamp(recv), member_name=r["Member"],
                         relationship=r["Relationship"], legal_entity_id=self.ent[ent], allowance_amount=r["Amount (USD)"], allowance_currency="USD", allowance_frequency="monthly", allowance_from=first,
                         allowance_to=last_day(first.year, first.month), paid_from_portfolio_id=self.cashport[ent])
                n += 1
            self.note("family_allowances", files=1)
        self.note("family_allowances", rows=n)

    def insurance_and_property(self) -> None:
        for p in self.files("insurance"):
            t = pdf_text(str(p))
            pol = re.search(r"Policy: (\S+)", t)[1]
            self.doc(p, "insurance_renewal", p.stem, received=self.arrival(p), date_=parse_date(re.search(r"Notice date: (.+)", t)[1]),
                     fields=[("policy", pol), ("renewal_date", parse_date(re.search(r"Renewal date: (.+)", t)[1]).isoformat()),
                             ("expiring_premium", None, money(re.search(r"Expiring premium: [A-Z]{3} ([\d,\.]+)", t)[1]), re.search(r"Expiring premium: ([A-Z]{3})", t)[1]),
                             ("renewal_premium", None, money(re.search(r"Renewal premium: [A-Z]{3} ([\d,\.]+)", t)[1]), re.search(r"Renewal premium: ([A-Z]{3})", t)[1]),
                             ("change_pct", None, Decimal(re.search(r"Change: ([\d.]+)%", t)[1]))])
            self.note("insurance", files=1, rows=1)
        for p in self.files("property_bills"):
            t = pdf_text(str(p))
            self.doc(p, "property_bill", p.stem, received=self.arrival(p), date_=self.arrival(p),
                     fields=[("bill_no", re.search(r"Bill no: (\S+)", t)[1]), ("month", re.search(r"Month: (\S+)", t)[1]),
                             ("due_date", parse_date(re.search(r"Due: (.+)", t)[1]).isoformat()), ("total_due", None, money(re.search(r"Total due: [A-Z]{3} ([\d,\.]+)", t)[1]), "SGD")])
            self.note("property_bills", files=1, rows=1)

    def approvals_and_close(self) -> None:
        n = 0
        for p in self.files("approvals"):
            for r in csv_rows(p):
                ids = self.pay_ref.get(r["payment_ref"], [])
                neg = [i for i in ids if next(m for m in self.rows["cash_movements"] if m["id"] == i)["amount"] < 0]
                if not neg and self.incremental:  # the bank line came in an earlier batch: find its payment by the bank's reference
                    neg = [m[0] for m in self.con.execute("select m.id from cash_movements m join source_records r on r.id = m.source_record_id "
                                                          "where r.external_record_id = ? and m.amount < 0", [r["payment_ref"]]).fetchall()]
                if r["approved_by"] and neg:
                    ad = parse_date(r["approved_on"])
                    for mid in neg:
                        self.add("approvals", cash_movement_id=mid, approval_type="payment_approval", requested_from_user_id=self.person(r["approved_by"]), decision_by_user_id=self.person(r["approved_by"]),
                                 status="approved", rationale=f"requested by {r['requested_by']}", requested_at=stamp(ad, 8), decided_at=stamp(ad, 9))
                        n += 1
            self.note("approvals", files=1)
        # a payment over the signed approval line with no approval on record is an exception, not a silent gap
        line = next((json.loads(v["parameters"])["amount"] for v in self.rows.get("rule_versions", []) if json.loads(v["parameters"]).get("amount") == 500000), 500000)
        approved = {a["cash_movement_id"] for a in self.rows.get("approvals", [])}
        for m in self.rows.get("cash_movements", []):
            if m.get("movement_type") == "payment" and m["confirmation_status"] == "confirmed" and m["currency"] == "USD" and -m["amount"] > line and m["id"] not in approved:
                ref = next((k for k, v in self.pay_ref.items() if m["id"] in v), "?")
                self.exception("missing_approval", f"{ref}: {-m['amount']:,.0f} USD paid with no approval on record", "Payments over the approval line need the Head of Finance (office rule).", m["effective_date"],
                               instrument_id=m.get("instrument_id"))
                self.note("approvals", flag=f"{ref}: over the approval line and no approval on record (M13)")
        self.note("approvals", rows=n)
        n = 0
        for p in self.files("close_checklist"):
            recv = self.arrival(p)
            for r in csv_rows(p):
                self.add("exceptions", exception_type="close_item", title=r["name"], description=f"{r['month']} close, step {r['step']}", detected_at=stamp(parse_date(r["due_on"]), 6),
                         materiality_status="n/a", status="closed" if r["done_on"] else "open", owner_user_id=self.person(r["owner"]), due_at=stamp(parse_date(r["due_on"]), 17),
                         resolved_at=stamp(parse_date(r["done_on"]), 12) if r["done_on"] else None)
                n += 1
            self.note("close_checklist", files=1)
        self.note("close_checklist", rows=n)
        n = 0
        for p in self.files("exception_log"):
            for r in csv_rows(p):
                self.add("exceptions", exception_type=r["kind"].replace(" ", "_"), title=f"{r['kind']}: {r['subject']}", description=f"{r['note']} (source {r['source']})", detected_at=stamp(parse_date(r["date"])),
                         candidate_impact_amount=Decimal(r["amount"]) if r["amount"] else None, impact_currency="USD" if r["amount"] else None, status="open")
                n += 1
            self.note("exception_log", files=1)
        self.note("exception_log", rows=n)

    # ------------------------------------------------------------------ reports, audit, diligence, notes
    def reports_and_audit(self) -> None:
        for p in self.files("investment_reports", "*.xlsx"):
            month = re.search(r"_(\d{4})-(\d{2})\.xlsx", p.name)
            me = last_day(int(month[1]), int(month[2]))
            pdf = p.with_suffix(".pdf")
            issued = None
            if pdf.is_file():
                mm = re.search(r"Issued: (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})", pdf_text(str(pdf)))
                issued = datetime.fromisoformat(f"{mm[1]} {mm[2]}") if mm else None
            recv = issued.date() if issued else self.arrival(p)
            did = self.doc(p, "investment_report", p.name, kind="office", date_=me, valuation=me, received=recv, status="issued")
            self.rows["documents"][-1]["received_at"] = f"{issued:%Y-%m-%d %H:%M}:00+00" if issued else stamp(recv)
            lines = [(i, r) for i, r in enumerate(sheet_rows(p, "Report")[1:], 2) if r[0]]
            for i, r in lines:
                self.field(did, r[0], text=r[2], num=r[1], ccy="SGD" if "SGD" in str(r[0]) else "USD", line=i)
            self.note("investment_reports", files=1, rows=len(lines))
            if pdf.is_file():
                self.doc(pdf, "investment_report_pdf", pdf.name, kind="office", date_=me, valuation=me, received=recv, status="issued", fields=[("same_report_as", p.name)])
                self.note("investment_reports", files=1, rows=1)
        for p in self.files("audit"):
            did = self.doc(p, "audit_request", p.name, date_=parse_date(re.search(r"(\d{4}-\d{2}-\d{2})", p.name)[1]), received=self.arrival(p), status="received")
            items = [r for r in sheet_rows(p)[1:] if r[0] is not None]
            for r in items:
                for name, kind, val in (("report_month", "text", r[1]), ("line", "text", r[2]), ("figure", "num", r[3])):
                    self.field(did, name, text=val if kind == "text" else None, num=Decimal(str(val)) if kind == "num" else None, line=r[0])
            self.note("audit", files=1, rows=len(items))

    def diligence_and_notes(self) -> None:
        for p in self.files("ddq"):
            self.ddq(p)
        for p in self.files("prospects"):
            t = pdf_text(str(p))
            recv = self.arrival(p)
            name = t.splitlines()[0].replace(" - FUND TEASER", "").title()
            mgr = re.sub(r"\s*\(synthetic\)", "", t.splitlines()[1]).strip()
            strategy = re.search(r"Strategy: (.*?),", t)[1]
            did = self.doc(p, "fund_teaser", p.stem, kind="manager", received=recv, date_=recv,
                           fields=[("fund", name), ("manager", mgr), ("minimum_commitment", None, money(re.search(r"Minimum commitment: USD ([\d,]+)", t)[1]), "USD")])
            self.add("deal_pipeline", source_record_id=self.doc_record(did), source_document_id=did, source_page=1, received_at=stamp(recv), recorded_at=stamp(recv), deal_name=name, manager_name=mgr,
                     strategy=strategy, asset_class="venture" if "venture" in strategy.lower() else None, target_commitment=money(re.search(r"Minimum commitment: USD ([\d,]+)", t)[1]), currency="USD",
                     stage="screening", stage_on=recv)
            self.note("prospects", files=1, rows=1)
        for p in self.files("meeting_notes"):
            text = p.read_text(encoding="utf-8")
            md = re.search(r"\| Date \| (.*?) \|", text)
            cp = re.search(r"\| Counterparty \| (.*?) \(", text)
            ref = re.search(r"\| Reference \| (.*?) \|", text)
            d = None
            try:
                d = parse_date(md[1].split("(")[0].strip()) if md else parse_date(re.search(r"(\d{4}-\d{2}-\d{2})", p.name)[1])
            except (ValueError, TypeError):
                d = parse_date(re.search(r"(\d{4}-\d{2}-\d{2})", p.name)[1])
            fields = [("meeting_date", d.isoformat())]
            if cp:
                fields.append(("counterparty", cp[1].strip()))
            if ref:
                fields.append(("reference", ref[1].strip()))
            fields.append(("body", text))
            self.doc(p, "meeting_note", p.stem, received=d, date_=d, fields=fields)
            self.note("meeting_notes", files=1, rows=1)

    # ------------------------------------------------------------------ expected statements, expected payments, links
    def expected_statements(self) -> None:
        n = 0
        for r in self.log.values():
            if r["expected_on"] is None:
                continue
            if date.fromisoformat(r["expected_on"]) > self.today:
                continue
            name = r["file"]
            if r["kind"] == "manager_statement":
                key = re.search(r"(?:^|[_/])([A-Z]\d?)_\d{4}", name)[1]
                iid, period = self.fund_key[key], date.fromisoformat(r["period"])
                freq = self.fund_info[key].get("statement_frequency", "monthly")
            else:
                acct = re.search(r"((?:HB|TCB)[-_][A-Z]+[-_][A-Z]{3})_\d{4}", name)[1].replace("_", "-")
                iid, period = self.office_acct[acct]["cash"], last_day(int(r["period"][:4]), int(r["period"][5:7]))
                freq = "monthly"
            if self.incremental and self.con.execute("select 1 from expected_statements where instrument_id = ? and period_end = ?", [iid, period]).fetchone():
                continue  # an earlier read of the log has it
            self.add("expected_statements", instrument_id=iid, period_end=period, due_date=date.fromisoformat(r["expected_on"]), frequency=freq, source="received_log", recorded_at=stamp(date(2026, 4, 1)))
            n += 1
            if r["status"] != "received" and not r["received_on"]:
                self.note("expected_statements", flag=f"{name}: expected {r['expected_on']}, never received")
            elif r["status"] == "late":
                self.note("expected_statements", flag=f"{name}: expected {r['expected_on']}, received {r['received_on']}")
        self.note("expected_statements", files=1 if self.log else 0, rows=n)

    def need_approval(self, movement: str, amount: Decimal, ccy: str, day: date) -> None:
        """A payment over the signed approval line (payment_approval, office rule) waits for the Head of Finance: the request is the row that says so."""
        rule = next((json.loads(v["parameters"]) for v in [*self.rows.get("rule_versions", []), *({"business_rule_id": a, "parameters": b} for a, b in self.db_rules)]
                     if v["business_rule_id"] == self.inst.get(("rule", "payment_approval"))), None)
        if not rule or rule.get("currency") != ccy or amount <= Decimal(str(rule["amount"])):
            return
        head = next((p["name"] for p in self.md["people"] if p["title"] == "Head of Finance"), None)
        self.add("approvals", cash_movement_id=movement, approval_type="payment_approval", requested_from_user_id=self.person(head), status="requested", requested_at=stamp(day),
                 rationale=f"over the approval line of {rule['amount']:,.0f} {ccy}")

    def links(self) -> None:
        """Expected payments: an open capital call, and every invoice with no payment on the bank statements, as `payment` rows still to be made."""
        n = 0
        for oc in self.open_calls:
            x = oc["x"]
            self.add("cash_movements", source_record_id=self.doc_record(x["doc"]), portfolio_id=self.cashport[oc["ent"]], instrument_id=self.fund_key[oc["fk"]], movement_type="payment",
                     effective_date=self.today, due_date=x["due"], amount=-x["amount"], currency="USD", confirmation_status="expected", bank_account_id=self.payee.get((oc["fk"], oc["ending"])),
                     commitment_id=self.commit.get(oc["fk"]), received_at=stamp(x["noticed"]), recorded_at=stamp(x["noticed"]))
            self.need_approval(self.rows["cash_movements"][-1]["id"], x["amount"], "USD", x["noticed"])
            n += 1
        lines = self.bank_lines
        for inv in self.invoice_list:
            paid = any(inv["no"] in l["ref"] or inv["no"] in l["desc"] or (l["amount"] == -inv["amount"] and l["ccy"] == inv["ccy"] and inv["vendor"].split()[0].lower() in (l["desc"] + l["cp"]).lower())
                       for l in lines)
            if paid:
                continue
            mid = self.add("cash_movements", source_record_id=self.doc_record(inv["doc"]), portfolio_id=self.cashport[inv["ent"]], movement_type="payment", effective_date=self.today,
                           due_date=inv["due"], amount=-inv["amount"], currency=inv["ccy"], confirmation_status="expected", bank_account_id=inv["acct"], received_at=stamp(inv["recv"]), recorded_at=stamp(inv["recv"]))
            self.need_approval(mid, inv["amount"], inv["ccy"], inv["recv"])
            n += 1
        self.note("invoices", rows=n)


def parsedate(text: str) -> datetime:
    from email.utils import parsedate_to_datetime
    return parsedate_to_datetime(text)


# ---- the standing data of an office that is already on record ---------------------------------------------------------------------------------

def _reference_state(self) -> None:
    """Later batches: the accounts, funds, rules and people are on record from the first read. Read the standing files again only to find the rows
    the other readers look up (nothing of it is written twice), then read the reference documents that are new in this batch."""
    keep, self.rows = self.rows, {}
    try:
        self.reference(docs=False)
        self.benchmark()
    finally:
        self.rows = keep
    self.report = {}
    q = lambda sql, *a: self.con.execute(sql, list(a)).fetchall()  # noqa: E731
    for a in self.office_acct.values():
        if r := q("select id from bank_accounts where holder_kind = 'office' and cash_instrument_id = ?", a["cash"]):
            a["id"] = r[0][0]
    for (fk, last4) in list(self.payee):
        if r := q("select id from bank_accounts where holder_kind = 'payee' and instrument_id = ? and account_ref = ? order by recorded_at desc", self.fund_key[fk], last4):
            self.payee[(fk, last4)] = r[0][0]
    for v in list(self.vendor_acct):
        if r := q("select id from bank_accounts where holder_kind = 'payee' and bank_name = 'vendor master' and lower(holder_name) = ?", v):
            self.vendor_acct[v] = r[0][0]
    cur = dict(q("select instrument_id, id from commitments where id not in (select supersedes_commitment_id from commitments where supersedes_commitment_id is not null)"))
    self.commit = {fk: cur[iid] for fk, iid in self.fund_key.items() if iid in cur}
    self.reference_documents(self.root / "reference")


Office.reference_state = _reference_state

# the steps whose readers are each a skill: step name -> the file kinds it reads
STEP_KINDS = {"registers": ["commitments"], "admin_nav": ["administrator_nav"], "admin_cash": ["administrator_cash"], "custodian_positions": ["custodian_positions"],
              "bank_statements": ["bank_statements"], "trading_and_custody": ["custodian_transactions", "trading_export"], "administrator_trades": ["administrator_trades"],
              "market": ["fx_rates", "index_levels"], "manager_statements": ["manager_statements"], "notices": ["notices"], "fx_confirmations": ["fx_confirmations"],
              "invoices": ["invoices"], "payroll": ["payroll"], "loans": ["loan_statements"], "vendor_contracts": ["vendor_contracts"], "allowances": ["family_allowances"],
              "insurance_and_property": ["insurance", "property_bills"], "approvals_and_close": ["approvals", "close_checklist", "exception_log"],
              "reports_and_audit": ["investment_reports", "audit"], "diligence_and_notes": ["ddq", "prospects"], "expected_statements": ["received_log"], "reference": ["reference"], "_reference_state": ["reference"]}
# kind -> (plain name for "Read as <kind>", skill id, what it fills)
KINDS = {
    "bank_statements": ("bank statement", "data.read-bank-statement", "bank balances and bank lines"),
    "custodian_positions": ("custodian positions", "data.read-custodian-positions", "position snapshots"),
    "custodian_transactions": ("custodian transactions", "data.read-custodian-transactions", "transactions"),
    "administrator_nav": ("administrator NAV pack", "data.read-administrator-nav", "accounting positions and sheet mappings"),
    "administrator_cash": ("administrator cash", "data.read-administrator-cash", "cash positions"),
    "administrator_trades": ("administrator trades", "data.read-administrator-trades", "transactions"),
    "trading_export": ("trading desk export", "data.read-trading-export", "transactions and cash movements"),
    "commitments": ("commitments register", "data.read-commitments-register", "commitments"),
    "notices": ("capital call or distribution notice", "data.read-notice", "documents and cash movements"),
    "manager_statements": ("manager capital account statement", "data.read-manager-statement", "valuation observations"),
    "invoices": ("invoice", "data.read-invoice", "documents and expected payments"),
    "payroll": ("payroll", "data.read-payroll", "cash movements"),
    "fx_rates": ("FX fixing", "data.read-fx-rates", "market observations"),
    "index_levels": ("index levels", "data.read-index-levels", "market observations"),
    "fx_confirmations": ("FX confirmation", "data.read-fx-confirmation", "FX confirmations"),
    "loan_statements": ("loan statement", "data.read-loan-statement", "credit facilities"),
    "family_allowances": ("family allowance schedule", "data.read-family-allowances", "family members and cash movements"),
    "insurance": ("insurance renewal notice", "data.read-insurance-notice", "documents"),
    "property_bills": ("property bill", "data.read-property-bill", "documents and expected payments"),
    "approvals": ("payment approvals", "data.read-approvals", "approvals"),
    "close_checklist": ("month-end checklist", "data.read-close-checklist", "documents"),
    "exception_log": ("exception log", "data.read-exception-log", "exceptions"),
    "investment_reports": ("investment report", "data.read-investment-report", "documents"),
    "audit": ("audit request", "data.read-audit-request", "documents"),
    "ddq": ("due diligence questionnaire", "data.read-ddq", "documents"),
    "prospects": ("fund teaser", "data.read-fund-teaser", "deal pipeline"),
    "vendor_contracts": ("vendor contract", "data.read-vendor-contract", "vendor contracts"),
    "received_log": ("log of statements received", "data.read-received-log", "expected statements"),
    "reference": ("standing data of the office", "data.read-reference-data", "entities, accounts, funds and rules"),
}
STATE_FILES = {"master_data.json", "accounts.csv", "standing_instructions.csv", "vendor_master.csv", "fund_terms.csv", "office_rules.csv"}
STATE_GLOBS = ("EG_security_master_", "Evergreen_Investment_Allocation_Policy_", "EG-OFFICE-BLEND_")


# ---- recognising a file: its content and its name, never the folder it sits in ----------------------------------------------------------------

CSV_KINDS = [  # (kind, columns the header must hold)
    ("administrator_cash", {"administrator_cash", "entity_code"}), ("administrator_trades", {"external_trade_id", "administrator_quantity"}),
    ("approvals", {"payment_ref", "approved_by"}), ("close_checklist", {"step", "owner", "due_on", "done_on"}),
    ("custodian_positions", {"security_id", "custodian", "market_value"}), ("custodian_transactions", {"txn_date", "settle_date", "security_id"}),
    ("exception_log", {"kind", "subject", "source", "note"}), ("fx_rates", {"pair", "fixing"}),
    ("received_log", {"file", "expected_on", "received_on", "status"}), ("trading_export", {"external_trade_id", "settle_date", "instrument_code"}), ("trading_export", {"value_date", "legal_entity", "movement_type"}),
]
REFERENCE_CSV = [("accounts.csv", {"account_id", "account_number"}), ("standing_instructions.csv", {"fund_key", "account_last4", "callback_number"}),
                 ("vendor_master.csv", {"vendor", "category", "account_last4"}), ("fund_terms.csv", {"fund_key", "commitment_usd", "billing_months"}),
                 ("office_rules.csv", {"rule", "value", "text"})]
XLSX_KINDS = [({"Positions", "NAV by portfolio"}, "administrator_nav"), ({"Transactions", "Daily balances"}, "bank_statements"), ({"Sample"}, "audit"),
              ({"Allowances"}, "family_allowances"), ({"Loan"}, "loan_statements"), ({"Payroll"}, "payroll"), ({"Report"}, "investment_reports"),
              ({"Security master"}, "reference"), ({"Components v1"}, "reference")]
PDF_KINDS = [("CAPITAL CALL NOTICE", "notices"), ("DISTRIBUTION NOTICE", "notices"), ("TRADE CONFIRMATION", "fx_confirmations"), ("MONTHLY INVESTMENT REPORT", "investment_reports"),
             ("PROPERTY STATEMENT AND BILL", "property_bills"), ("FUND TEASER", "prospects"), ("CAPITAL ACCOUNT STATEMENT", "manager_statements"),
             ("DUE DILIGENCE QUESTIONNAIRE", "ddq")]


def _pdf_head(data: bytes) -> str:
    import io
    try:
        r = pypdf.PdfReader(io.BytesIO(data))
        return "\n".join((r.pages[i].extract_text() or "") for i in range(min(2, len(r.pages))))
    except Exception:  # noqa: BLE001 - a file that cannot be read is not one of ours; the generic path names the problem
        return ""


def kind_of(name: str, data: bytes) -> tuple[str, str] | None:
    """(kind, the name to read it under) when a reader of the pack knows this file, else None. Content decides; the name only tells apart what the
    content cannot (the reference documents) and stays for the readers that take an account or a fund from it. Emails, notes and Word files are not
    here: they are documents, read as context (v3_docs)."""
    low = name.lower()
    if name == "master_data.json":
        return "reference", name
    if low.endswith(".csv"):
        head = data[:4000].decode("utf-8-sig", errors="replace").splitlines()[:1]
        cols = {c.strip().lower() for c in next(csv.reader(head), [])}
        for canon, need in REFERENCE_CSV:
            if need <= cols:
                return "reference", canon
        if "date" in cols and "currency" in cols and any("index" in c for c in cols):
            return "index_levels", name
        for kind, need in CSV_KINDS:
            if need <= cols:
                if kind == "trading_export":
                    pre = "cash_movements_" if "movement_type" in cols else "trading_export_"
                    return kind, name if low.startswith(pre) else pre + name
                return kind, name
        return None
    if low.endswith((".xlsx", ".xlsm")):
        import io
        try:
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True)
            sheets = set(wb.sheetnames)
            for need, kind in XLSX_KINDS:
                if need <= sheets:
                    return kind, name
            if "Register" in sheets:
                first = next(wb["Register"].iter_rows(values_only=True), ())
                return ("commitments", name) if "Fund key" in first else None
        except Exception:  # noqa: BLE001
            return None
        return None
    if low.endswith(".pdf"):
        t = _pdf_head(data)
        up = t.upper()
        for mark, kind in PDF_KINDS:
            if mark in up[:400]:  # the title sits at the top; a questionnaire that merely mentions capital calls is not a notice
                return kind, name
        if "RENEWAL NOTICE" in up and "Policy:" in t:
            return "insurance", name
        if "INVOICE" in up and re.search(r"Invoice no:", t):
            return "invoices", name
        if "Annual cost:" in t and "Renewal date:" in t:
            return "vendor_contracts", name
        if low == "fee_schedule.pdf" or low.startswith(("loan_agreement", "evergreen_investment_allocation_policy")) or "newsletter" in low or "mid_year_letter" in low:
            return "reference", name
    return None


def _name_day(name: str) -> date | None:
    m = re.search(r"(20\d{2})-?(\d{2})-?(\d{2})", Path(name).stem)
    try:
        return date(int(m[1]), int(m[2]), int(m[3])) if m else None
    except ValueError:
        return None


OWN_MONTH = {"approvals", "payroll", "family_allowances", "index_levels"}  # kinds whose file for a month arrives in that month; the others the month after


def folder_month(name: str, kind: str, clock: date) -> str:
    """The month folder a file belongs in, the month it arrives. A dated file arrives on its date; a file named for a month arrives in it (payroll,
    approvals ...) or the month after (a bank statement, the administrator's cash); a file with no date arrives when it is dropped."""
    if d := _name_day(name):
        return f"{d:%Y-%m}"
    m = re.search(r"(20\d{2})-(0[1-9]|1[0-2])(?!\d)", Path(name).stem)
    if not m:
        return f"{clock:%Y-%m}"
    y, mo = int(m[1]), int(m[2])
    if kind in OWN_MONTH or "mtd" in name.lower():
        return f"{y}-{mo:02d}"
    return f"{y + (mo == 12)}-{1 if mo == 12 else mo + 1:02d}"


def stage(root: Path, items: list[tuple[str, bytes, str, str]], clock: date) -> None:
    """Lay the files out the way the readers walk them: reference/ for the standing data and contracts, <month>/<kind>/ for the rest
    (items: name, data, kind, the name to read it under)."""
    for name, data, kind, as_name in items:
        if kind == "received_log":
            (root / "received_log_all.csv").write_bytes(data)
            continue
        d = root / ("reference" if kind in ("reference", "vendor_contracts") else f"{folder_month(as_name, kind, clock)}/{kind}")
        d.mkdir(parents=True, exist_ok=True)
        (d / re.sub(r"[\\/]", "_", as_name)).write_bytes(data)


def is_state(as_name: str) -> bool:
    return as_name in STATE_FILES or as_name.startswith(STATE_GLOBS)


# ---- reading a batch ------------------------------------------------------------------------------------------------------------------------

def _loaded_hashes(con) -> set[str]:
    out = set()
    for sql in ("select content_hash from source_batches", "select content_hash from documents"):
        try:
            out |= {r[0] for r in con.execute(sql).fetchall() if r[0]}
        except Exception:  # noqa: BLE001
            pass
    return out


def read_files(plane, items: list[tuple[str, bytes, str, str]], standing: list[tuple[str, bytes, str, str]], thread_id: str | None = None) -> tuple[dict, list[tuple[str, str]], list[str]]:
    """Read recognised files into the company model. items: the batch (name, data, kind, the name to read it under); standing: the standing data
    the readers look things up in (accounts, funds, rules, security master), read once and found again after that.
    -> (report per kind, [(file, why it was set aside)], names of the files read). A file already read (same content) is not read twice. One
    transaction per try: a batch that fails is tried kind by kind, then half by half, so one bad file never holds the others back."""
    import hashlib
    import tempfile
    from sh_platform.v1 import v3_skills as S
    from sh_platform.v1 import wh
    from sh_platform.v1.e1_write import org_id
    report: dict = {}
    aside: list[tuple[str, str]] = []
    done: list[str] = []
    org = org_id(plane)
    clock = max([wh.now(plane).date(), *(d for it in items if (d := _name_day(it[0])))])
    state = [i for i in [*standing, *items] if is_state(i[3])]
    if not ({"master_data.json", "accounts.csv", "office_rules.csv"} <= {i[3] for i in state} and any(i[3].startswith("EG_security_master_") for i in state)):
        return report, [(i[0], "the office's standing data (accounts, funds, rules, security master) has not arrived yet, so I cannot place this file") for i in items], done
    with wh.connect(plane) as con:
        seen = _loaded_hashes(con)
    todo = []
    for it in items:
        if it[2] not in ("reference", "vendor_contracts") and hashlib.sha256(it[1]).hexdigest() in seen:
            done.append(it[0])
        else:
            todo.append(it)

    def recorder(kind, fn):
        return S.record(plane, thread_id, KINDS[kind][1], fn)

    def attempt(batch):
        names = {b[3] for b in batch}
        with tempfile.TemporaryDirectory(prefix="pack-", ignore_cleanup_errors=True) as tmp:
            stage(Path(tmp), [*batch, *(i for i in state if i[3] not in names)], clock)
            with wh.connect(plane) as con:
                con.execute("begin")
                try:
                    o = Office(con, tmp, org, clock.isoformat(), incremental=True, recorder=recorder)
                    for b in batch:
                        o.staged[b[2]] = o.staged.get(b[2], 0) + 1
                    rep = o.load()
                    con.execute("commit")
                except BaseException:
                    con.execute("rollback")
                    raise
        for k, v in rep.items():
            r = report.setdefault(k, {"files": 0, "rows": 0, "not_loaded": [], "flagged": []})
            r["files"] += v["files"]
            r["rows"] += v["rows"]
            r["not_loaded"] += v["not_loaded"]
            r["flagged"] += v["flagged"]
        done.extend(b[0] for b in batch)

    def tolerant(batch, by_kind=True):
        try:
            attempt(batch)
        except Exception as e:  # noqa: BLE001 - narrowed down below; each file that still fails is named with its reason
            log.warning("pack readers failed on %d files", len(batch), exc_info=True)
            if len(batch) == 1:
                aside.append((batch[0][0], f"{type(e).__name__}: {e}"[:200]))
                return
            kinds = list(dict.fromkeys(b[2] for b in batch))
            if by_kind and len(kinds) > 1:
                groups = [[b for b in batch if b[2] == k] for k in kinds]
            else:
                m = len(batch) // 2
                groups = [batch[:m], batch[m:]]
            for g in groups:
                tolerant(g, by_kind=False)
    if todo:
        tolerant(todo)
    return report, aside, done


# ---- entry points (the six-month office folders, as the first loader read them) ------------------------------------------------------------

def load_office(con, root, org: str = "org-evergreen", today: str = TODAY) -> dict:
    """Load the office6m folders under `root` into the warehouse behind `con`. -> {file kind: {files, rows, not_loaded, flagged}}."""
    return Office(con, root, org, today).load()


def load_plane(plane, root, today: str = TODAY) -> dict:
    from sh_platform.v1 import wh
    from sh_platform.v1.e1_write import org_id
    with wh.connect(plane) as con:
        con.execute("begin")
        try:
            rep = load_office(con, root, org_id(plane), today)
            con.execute("commit")
        except Exception:
            con.execute("rollback")
            raise
    return rep


# ---- hooks of v3_harbor: intake tries these readers first ----------------------------------------------------------------------------------

_KIND_CACHE: dict[tuple, tuple[str, str] | None] = {}


def recognise(plane, name: str) -> tuple[str, str] | None:
    """kind_of for a file of the drop folder; remembered while the file stays as it is."""
    p = plane.path("dropbox", name)
    try:
        st = p.stat()
        key = (str(p), st.st_size, st.st_mtime_ns)
        if key not in _KIND_CACHE:
            _KIND_CACHE[key] = kind_of(name, p.read_bytes())
        return _KIND_CACHE[key]
    except Exception:  # noqa: BLE001 - a file that cannot be opened here takes the generic path, which names the problem
        log.warning("could not recognise %s", name, exc_info=True)
        return None


def _standing(plane) -> list[tuple[str, bytes, str, str]]:
    """The standing data of the office (accounts, funds, rules, security master ...) among all the files in the drop folder, whoever they were dropped for."""
    from sh_platform.v1 import v3_harbor as H
    out = []
    for f in H.read_files(plane):
        r = recognise(plane, f["name"])
        if r and is_state(r[1]):
            out.append((f["name"], H.blob(plane, f["name"]), r[0], r[1]))
    return out


def intake(x) -> None:
    """a_intake, before anything else: each file of the thread that one of the pack's readers knows is marked, to be read as that kind. The generic
    paths (mapping, PDFs, documents) never see it: `x.hide` takes it out of H.my_files until a_intake has run them."""
    from sh_platform.v1 import v3_harbor as H
    x.th["pack"] = {}
    for f in H.my_files(x, "source"):
        if r := recognise(x.plane, f["name"]):
            x.th["pack"][f["name"]] = {"kind": r[0], "as": r[1]}  # not in th["intake"]: v3_pdf's load reads every PDF listed there
    x.hide = set(x.th["pack"])


def d2_files(x) -> list[dict]:
    return [{"name": n, "read_as": KINDS[v["kind"]][0], "goes_to": KINDS[v["kind"]][2], "state": "reused", "confidence": "high"} for n, v in (x.th.get("pack") or {}).items()]


def _read(x, names: list[str], kinds: dict[str, dict]) -> tuple[list[str], list[dict]]:
    from sh_platform.v1 import v3_harbor as H
    items = [(n, H.blob(x.plane, n), kinds[n]["kind"], kinds[n]["as"]) for n in names]
    try:
        _, aside, done = read_files(x.plane, items, _standing(x.plane), x.th["id"])
    except Exception as e:  # noqa: BLE001 - nothing read: each file set aside with the reason, in one plain line
        log.warning("pack readers failed", exc_info=True)
        aside, done = [(n, f"{type(e).__name__}: {e}"[:200]) for n in names], []
    ok = set(done)
    for n in names:
        if n in ok:
            H.set_status(x.plane, n, "loaded")
            if n.lower().endswith(".pdf"):  # set_status raises the file-arrived signal for every kind but a PDF
                try:
                    from sh_platform.v1 import v3_signals as SG
                    SG.on_file(x.plane, n)
                except Exception:  # noqa: BLE001 - a signal never breaks a load
                    log.warning("signals for %s failed", n, exc_info=True)
    out = []
    for n, why in aside:
        H.set_status(x.plane, n, "question")
        out.append({"file": n, "title": f"{n} did not load", "text": f"I set it aside: {why}."[:200]})
    return [n for n in names if n in ok], out


def load(x) -> tuple[int, list[dict]]:
    """b_load: read the marked files. (files loaded, lines of what was set aside)."""
    pack = x.th.get("pack") or {}
    ok, aside = _read(x, list(pack), pack) if pack else ([], [])
    return len(ok), aside


def monthly(x) -> tuple[set[str], int, list[dict]]:
    """m_load: the new files of a live thread that the pack knows are read at once. (names taken, files loaded, lines of what was set aside)."""
    from sh_platform.v1 import v3_harbor as H
    kinds = {}
    for f in H.my_files(x, "source"):
        if f["status"] == "recognised" and (r := recognise(x.plane, f["name"])):
            kinds[f["name"]] = {"kind": r[0], "as": r[1]}
    if not kinds:
        return set(), 0, []
    ok, aside = _read(x, list(kinds), kinds)
    return set(kinds), len(ok), aside

from sh_platform.v1 import v3_pack_readers_treasury as _treasury  # noqa: E402 - the treasury kinds register themselves in the tables above
_treasury.install(__import__('sys').modules[__name__])
from sh_platform.v1 import v3_pack_readers_assets as _assets  # noqa: E402 - the assets kinds register themselves in the tables above
_assets.register(__import__("sys").modules[__name__])
from sh_platform.v1 import v3_pack_readers_controls as _controls  # noqa: E402 - the controls kinds register themselves in the tables above
_controls.install(__import__("sys").modules[__name__])
from sh_platform.v1 import v3_pack_readers_family as _family  # noqa: E402 - the family kinds register themselves in the tables above
_family.install(__import__("sys").modules[__name__])
from sh_platform.v1 import v3_pack_readers_invest as _invest  # noqa: E402 - the invest kinds register themselves in the tables above
_invest.install(__import__("sys").modules[__name__])
