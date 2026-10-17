"""Harbor 3.0: pack readers for the "controls" kinds of the six-month office (cards 51 to 100): expense ledger and budget, payroll drafts, SOPs, access register,
KYC register, onboarding checklist, bank forms, family access, glossary, break register, load log, inbox and new feed.

`install(P)` is called once by v3_pack_readers (P is that module): it gives the Office class one step per kind, registers the kinds (KINDS, STEP_KINDS,
FLUSH_ORDER) and `kind_of` asks `kind_of` here first. Every reader follows the pack's rules: append-only (a changed row is a new row that supersedes the old
one, an identical row is not written twice), a source record per row, personal data in the `personal` access group, mess flagged in plain words in the report
(`flagged`), never a number typed into a reader: the budget, the approver limits, the signing policy and the family access levels are written as PROPOSED
business rules (A20: signed later through approvals), so a recipe that needs one is held until it is signed. Synthetic data only.
"""
from __future__ import annotations

import csv
import email
import io
import json
import re
from datetime import date
from decimal import Decimal
from email import policy as email_policy
from pathlib import Path

P = None  # the pack readers module, set by install()

KINDS = {
    "expense_ledger": ("expense ledger", "data.read-expense-ledger", "office expenses and approver limits"),
    "office_budget": ("office budget", "data.read-office-budget", "budget rules (proposed)"),
    "payroll_drafts": ("payroll draft", "data.read-payroll-draft", "staff payroll"),
    "sops": ("standard operating procedure", "data.read-sop", "documents and fields"),
    "access_register": ("system access register", "data.read-access-register", "system access grants"),
    "kyc_register": ("KYC register", "data.read-kyc-register", "KYC records"),
    "onboarding": ("manager onboarding file", "data.read-onboarding", "documents and KYC records"),
    "bank_forms": ("bank account form or signing policy", "data.read-bank-form", "bank accounts, signatories and rules"),
    "family_access": ("family access grants and policy", "data.read-family-access", "access group scopes and rules"),
    "glossary": ("office word list", "data.read-glossary", "documents and fields"),
    "break_register": ("break register", "data.read-break-register", "exceptions"),
    "load_log": ("load log", "data.read-load-log", "source batches and control totals"),
    "inbox": ("inbox file", "data.read-inbox", "documents"),
    "new_feed": ("new feed", "data.read-new-feed", "sheet mapping proposal"),
}
STEPS = ["ctl_payroll_paid", "ctl_expenses", "ctl_payroll_drafts", "ctl_sops", "ctl_access", "ctl_kyc", "ctl_onboarding", "ctl_bank_forms", "ctl_family_access", "ctl_glossary",
         "ctl_breaks", "ctl_new_feed", "ctl_inbox", "ctl_load_log"]
STEP_KINDS = {"controls": list(KINDS)}  # one step, named: its name is how STEP_KINDS finds the kinds
FLUSH = ["office_expenses", "staff_payroll", "kyc_records", "system_access_grants", "access_group_scopes", "access_group_memberships", "batch_control_totals"]
SUPERSEDES = {"office_expenses": "supersedes_office_expense_id", "staff_payroll": "supersedes_staff_payroll_id", "kyc_records": "supersedes_kyc_record_id",
              "system_access_grants": "supersedes_system_access_grant_id"}
SPEC = {  # table -> (columns that say which row it is, columns that say what it holds)
    "office_expenses": (("reference",), ("spent_on", "category", "payee_name", "legal_entity_id", "currency", "amount", "approver_name")),
    "staff_payroll": (("pay_period", "employee_name"), ("title", "employment_kind", "legal_entity_id", "currency", "gross_pay", "employee_contribution", "employer_contribution",
                                                        "net_pay", "pay_date", "run_status")),
    "kyc_records": (("legal_entity_id", "subject_kind", "subject_name", "document_kind"), ("issued_on", "expires_on", "verified_on", "status")),
    "system_access_grants": (("person_name", "system_name", "access_level"), ("granted_on", "approved_by_name", "last_used_on", "revoked_on", "status")),
}
LEVELS = {"none": 0, "summary": 1, "full": 2}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def _n(v) -> str:
    """A value as comparable text: numbers without trailing zeros, dates in ISO, nothing as ''."""
    if v is None:
        return ""
    if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
        return format(Decimal(str(v)).normalize(), "f")
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


# ---- recognising a file ------------------------------------------------------------------------------------------------------------------

CSV_HEADS = [("access_register", {"grant_id", "person", "system", "permission"}), ("kyc_register", {"entity", "counterparty", "document", "issued", "expires"}),
             ("family_access", {"member", "entity", "level", "granted_on"}), ("onboarding", {"item", "status", "note"}), ("glossary", {"term", "aliases", "definition"}),
             ("break_register", {"break_id", "type", "entity", "subject", "detected_on"}), ("load_log", {"source", "file", "on_time", "adds_up", "manual_fix"})]
PDF_MARKS = [("SUBSCRIPTION DOCUMENT", "onboarding"), ("ACCOUNT OPENING FORM", "bank_forms"), ("SIGNING POLICY", "bank_forms"), ("FAMILY ACCESS POLICY", "family_access")]


def kind_of(name: str, data: bytes) -> tuple[str, str] | None:
    """(kind, name) when the content is one of this module's kinds, else None."""
    low = name.lower()
    try:
        if low.endswith(".csv"):
            head = data[:4000].decode("utf-8-sig", errors="replace").splitlines()[:1]
            cols = {c.strip().lower() for c in next(csv.reader(head), [])}
            return next(((k, name) for k, need in CSV_HEADS if need <= cols), None)
        if low.endswith((".xlsx", ".xlsm")):
            wb = P.openpyxl.load_workbook(io.BytesIO(data), read_only=True)
            try:
                sheets = set(wb.sheetnames)
                if {"Ledger", "Approval limits"} <= sheets:
                    return "expense_ledger", name
                if sheets == {"Draft"}:
                    return "payroll_drafts", name
                if sheets == {"Budget"}:
                    first = next(wb["Budget"].iter_rows(values_only=True), ())
                    return ("office_budget", name) if first and str(first[0]).strip().lower() == "category" and "budget" in str(first[1]).lower() else None
            finally:
                wb.close()
            return None
        if low.endswith(".md"):
            first = data[:300].decode("utf-8-sig", errors="replace").lstrip().splitlines()[:1]
            t = first[0].lower() if first else ""
            return ("sops", name) if t.startswith("# sop:") else ("glossary", name) if t.startswith("# word review") else None
        if low.endswith(".pdf"):
            t = P._pdf_head(data)
            up = t.upper()[:400]
            if "KYC PACK" in up:
                return ("kyc_register" if re.search(r"\|\s*expires \d{4}-\d{2}-\d{2}", t) else "onboarding"), name
            return next(((k, name) for mark, k in PDF_MARKS if mark in up), None)
    except Exception:  # noqa: BLE001 - a file that cannot be read here is not one of ours; the generic path names the problem
        return None
    return None


# ---- plumbing shared by the readers -----------------------------------------------------------------------------------------------------

def _latest(self, table: str) -> dict:
    """{key: (id, signature)} of the rows of the table not yet superseded: those on record, then those of this load."""
    cache = self.__dict__.setdefault("_ctl_latest", {})
    if table not in cache:
        keys, vals = SPEC[table]
        sup = SUPERSEDES[table]
        cache[table] = {}
        try:
            rows = self.con.execute(f"select id, {', '.join(keys + vals)} from {table} where id not in (select {sup} from {table} where {sup} is not null)").fetchall()
            for r in rows:
                cache[table][tuple(_n(v) for v in r[1:1 + len(keys)])] = (str(r[0]), tuple(_n(v) for v in r[1 + len(keys):]))
        except Exception:  # noqa: BLE001 - a warehouse without the table has nothing on record
            pass
    return cache[table]


def _put(self, table: str, rec: dict, **meta) -> str | None:
    """Write a row; the same row again is not written, a changed row supersedes the old one. -> the new id, or None when nothing was written."""
    keys, vals = SPEC[table]
    key = tuple(_n(rec.get(c)) for c in keys)
    sig = tuple(_n(rec.get(c)) for c in vals)
    cache = _latest(self, table)
    cur = cache.get(key)
    if cur and cur[1] == sig:
        return None
    extra = {SUPERSEDES[table]: cur[0]} if cur else {}
    rid = self.add(table, **rec, **meta, **extra)
    cache[key] = (rid, sig)
    return rid


def _meta(self, did: str, sr: str, recv: date, page: int | None = 1) -> dict:
    return dict(source_record_id=sr, source_document_id=did, source_page=page, received_at=P.stamp(recv), recorded_at=P.stamp(recv))


def _row_record(self, kind: str, p: Path, recv: date, external: str | None, row: int, sheet: str | None = None, eff: date | None = None) -> str:
    return self.record(kind, p, recv, rtype="row", external=external, sheet=sheet, row=row, effective=eff)


def _entity_code(self, text: str | None) -> str | None:
    """An entity code from a code or a name (Evergreen Holdings, Entity B ...)."""
    t = str(text or "").strip().lower()
    return next((c for c, n in self.md["entities"].items() if t in (c.lower(), n.lower())), None)


def _eml(p: Path):
    msg = email.message_from_bytes(p.read_bytes(), policy=email_policy.default)
    body = msg.get_body(preferencelist=("plain",))
    return msg, (body.get_content().strip() if body else ""), P.parsedate(msg["Date"])


def _email_doc(self, kind: str, p: Path, extra: list, personal: bool = False) -> tuple[str, str, date]:
    msg, text, sent = _eml(p)
    fields = [("subject", msg["Subject"]), ("from", str(msg["From"])), ("to", str(msg["To"])), ("sent", sent.isoformat()), ("body", text), *extra]
    did = self.doc(p, "email", str(msg["Subject"] or p.stem), kind=kind, received=sent.date(), date_=sent.date(), fields=fields, personal=personal)
    return did, text, sent.date()


def _proposed_rule(self, code: str, text: str, params: dict, owner: str = "Daniel Foo") -> None:
    self.rule(code, "policy", text, params, owner, owner, effective="2026-04-01", status="proposed")


# ---- payroll (staff_payroll: sensitive, so the source document is in the personal access group) ---------------------------------------------

def _payroll_file(self, kind: str, p: Path, status: str, sheet_name: str | None = None) -> int:
    recv = self.arrival(p)
    rows = P.dicts(P.sheet_rows(p))
    col = lambda r, start: next((v for k, v in r.items() if str(k).startswith(start)), None)  # noqa: E731 - the register names its columns with the rate: "Employee CPF (20%)"
    head = next(iter(rows[0])) if rows else "Employee"
    gcol = next((k for k in rows[0] if str(k).startswith("Gross")), "Gross (SGD)") if rows else "Gross (SGD)"
    ccy = (re.search(r"\(([A-Z]{3})\)", gcol) or [None, "SGD"])[1]
    staff = [r for r in rows if str(r[head]).strip().lower() != "total"]
    pay_date = P.parse_date(staff[0]["Pay date"]) if staff else None
    period = f"{pay_date:%Y-%m}" if pay_date else (re.search(r"\d{4}-\d{2}", p.name) or [""])[0]
    did = next((d["id"] for d in self.rows.get("documents", []) if d.get("original_filename") == p.name and d["document_type"] == "payroll"), None) if kind == "payroll" else None
    did = did or self.doc(p, "payroll_draft" if status == "draft" else "payroll", f"Payroll {period}" + (" (draft)" if status == "draft" else ""), kind=kind, received=recv, date_=pay_date,
                          personal=True, fields=[("month", period), ("employees", None, Decimal(len(staff))), ("run_status", status)])
    total = next((r for r in rows if str(r[head]).strip().lower() == "total"), None)
    if total and Decimal(str(total[gcol])) != sum(Decimal(str(r[gcol])) for r in staff):
        self.note(kind, flag=f"{p.name}: the total line does not add up to the people listed")
    pdate = date.fromisoformat(period + "-01")  # the period is the first day of its month
    prev = _previous_run(self, pdate)
    ent = self.ent.get("EG-HOLD")
    n = 0
    for i, r in enumerate(staff, 2):
        raw = str(r[head]).strip()
        contractor = "(contractor)" in raw.lower() or str(r.get("Title") or "").strip().lower() == "contractor"
        name = re.sub(r"\s*\(contractor\)", "", raw, flags=re.I).strip()
        rec = dict(pay_period=pdate, employee_name=name, title=r.get("Title"), employment_kind="contractor" if contractor else "employee", legal_entity_id=ent, currency=ccy,
                   gross_pay=Decimal(str(r[gcol])), employee_contribution=_dec(col(r, "Employee C")), employer_contribution=_dec(col(r, "Employer C")), net_pay=_dec(col(r, "Net")),
                   pay_date=P.parse_date(r["Pay date"]) if r.get("Pay date") else pay_date, run_status=status)
        sr = _row_record(self, kind, p, recv, f"{period}/{name}", i, "Payroll" if kind == "payroll" else "Draft", rec["pay_date"])
        n += _put(self, "staff_payroll", rec, **_meta(self, did, sr, recv)) is not None
        if status == "draft" and prev:
            if name not in prev["rows"]:
                self.note(kind, flag=f"{p.name}: {name} ({rec['employment_kind']}) is not on the staff register of {prev['period']:%Y-%m}")
            elif prev["rows"][name] != rec["gross_pay"]:
                was = prev["rows"][name]
                self.note(kind, flag=f"{p.name}: {name} gross changed from {was:,.2f} to {rec['gross_pay']:,.2f} ({(rec['gross_pay'] - was) / was * 100:+.1f} percent) against {prev['period']:%Y-%m}")
        if rec["net_pay"] is not None and rec["employee_contribution"] is not None and rec["gross_pay"] - rec["employee_contribution"] != rec["net_pay"]:
            self.note(kind, flag=f"{p.name}: {name} gross less contribution is not the net pay")
    return n


def _dec(v):
    return None if v is None or v == "" else Decimal(str(v))


def _previous_run(self, period: date) -> dict | None:
    """The latest run before `period`: {period, rows: {name: gross}}, from this load and from what is on record."""
    found: dict[str, dict] = {}
    try:
        for per, name, gross in self.con.execute("select pay_period, employee_name, gross_pay from staff_payroll where pay_period < ? and id not in "
                                                 "(select supersedes_staff_payroll_id from staff_payroll where supersedes_staff_payroll_id is not null)", [period]).fetchall():
            found.setdefault(per, {})[name] = Decimal(str(gross))
    except Exception:  # noqa: BLE001
        pass
    for r in self.rows.get("staff_payroll", []):
        if r["pay_period"] < period:
            found.setdefault(r["pay_period"], {})[r["employee_name"]] = r["gross_pay"]
    return {"period": max(found), "rows": found[max(found)]} if found else None


def ctl_payroll_paid(self) -> None:
    """The monthly payroll registers (read as documents by the payroll reader) also give one staff_payroll row per person: paid once the pay date has passed."""
    n = 0
    for p in self.files("payroll"):
        m = P.parse_date(P.dicts(P.sheet_rows(p))[0]["Pay date"])
        n += _payroll_file(self, "payroll", p, "paid" if m <= self.today else "approved")


def ctl_payroll_drafts(self) -> None:
    files = self.files("payroll_drafts")
    n = sum(_payroll_file(self, "payroll_drafts", p, "draft") for p in files)
    self.note("payroll_drafts", files=len(files), rows=n)


# ---- expenses and the budget -------------------------------------------------------------------------------------------------------------------

def ctl_expenses(self) -> None:
    n = 0
    for p in self.files("office_budget"):
        recv = self.arrival(p)
        rows = P.dicts(P.sheet_rows(p))
        seen = set()
        did = self.doc(p, "office_budget", p.stem, kind="office_budget", received=recv, fields=[("categories", None, Decimal(len(rows)))])
        for r in rows:
            cat, amt = str(r["Category"]).strip(), r.get("Annual budget (USD)")
            if cat in seen or amt in (None, ""):
                self.note("office_budget", flag=f"{p.name}: '{cat}' is {'listed twice' if cat in seen else 'without an amount'}; not written")
                continue
            seen.add(cat)
            _proposed_rule(self, f"office_budget_{slug(cat)}", f"Annual office budget for {cat}: {float(amt):,.0f} USD (from {p.name}, not yet signed)", {"annual": float(amt), "currency": "USD"})
            n += 1
        self.note("office_budget", files=1)
    self.note("office_budget", rows=n)
    n = 0
    for p in self.files("expense_ledger"):
        recv = self.arrival(p)
        wb = P.openpyxl.load_workbook(p, data_only=True, read_only=True)
        sheets = wb.sheetnames
        wb.close()
        rows = P.dicts(P.sheet_rows(p, "Ledger"))
        limits = {str(r["Approver"]).strip(): float(r["Limit (USD)"]) for r in P.dicts(P.sheet_rows(p, "Approval limits"))} if "Approval limits" in sheets else {}
        dates = [P.parse_date(r["Date"]) for r in rows if r.get("Date")]
        did = self.doc(p, "expense_ledger", p.stem, kind="expense_ledger", received=recv, date_=max(dates) if dates else None, fields=[("payments", None, Decimal(len(rows)))])
        for who, lim in limits.items():
            _proposed_rule(self, f"approver_limit_{slug(who)}", f"{who} approves payments up to {lim:,.0f} USD (from {p.name}, not yet signed)", {"limit": lim, "currency": "USD"})
        seen = set()
        for i, r in enumerate(rows, 2):
            ref = str(r.get("Reference") or "").strip()
            if not ref or r.get("Amount") in (None, "") or not r.get("Date"):
                self.note("expense_ledger", flag=f"{p.name} row {i}: no reference, date or amount; not written")
                continue
            if ref in seen:
                self.note("expense_ledger", flag=f"{p.name} row {i}: reference {ref} appears twice; counted once")
                continue
            seen.add(ref)
            code = _entity_code(self, r.get("Entity"))
            if code is None:
                self.note("expense_ledger", flag=f"{p.name} row {i}: entity '{r.get('Entity')}' is not one of the office's; kept without an entity")
            approver = str(r.get("Approver") or "").strip() or None
            if approver is None:
                self.note("expense_ledger", flag=f"{ref}: no approver on the ledger line")
            d = P.parse_date(r["Date"])
            rec = dict(spent_on=d, category=str(r["Category"]).strip(), payee_name=r.get("Payee"), legal_entity_id=self.ent.get(code), currency=r["Currency"], amount=Decimal(str(r["Amount"])),
                       reference=ref, approver_name=approver, approver_user_id=self.person(approver) if approver else None)
            sr = _row_record(self, "expense_ledger", p, recv, ref, i, "Ledger", d)
            n += _put(self, "office_expenses", rec, **_meta(self, did, sr, recv)) is not None
            usd = r.get("USD equivalent")
            if approver in limits and usd is not None and float(usd) > limits[approver]:
                self.note("expense_ledger", flag=f"{ref}: {float(usd):,.2f} USD to {r.get('Payee')} approved by {approver}, whose limit is {limits[approver]:,.0f}")
        self.note("expense_ledger", files=1)
    self.note("expense_ledger", rows=n)


# ---- SOPs --------------------------------------------------------------------------------------------------------------------------------------

def ctl_sops(self) -> None:
    n = 0
    for p in self.files("sops", "*.md"):
        text = p.read_text(encoding="utf-8-sig")
        recv = self.arrival(p)
        title = (re.match(r"\s*#\s*SOP:\s*(.+)", text) or [None, p.stem])[1].strip()
        owner = (re.search(r"^Owner:\s*(.+)$", text, re.M) or [None, None])[1]
        rev = (re.search(r"^Last reviewed:\s*(.+)$", text, re.M) or [None, None])[1]
        runs = (re.search(r"^Runs per month:\s*([\d.]+)", text, re.M) or [None, None])[1]
        try:
            reviewed = P.parse_date(rev.strip()) if rev else None
        except ValueError:
            reviewed = None
        fields = [("owner", owner.strip() if owner else None)]
        if reviewed:
            fields.append(("last_reviewed_on", reviewed.isoformat()))
        else:
            self.note("sops", flag=f"{p.name}: no readable review date ('{rev}'); it cannot be aged")
        if runs:
            fields.append(("runs_per_month", None, Decimal(runs)))
        steps = [[c.strip() for c in line.strip().strip("|").split("|")] for line in text.splitlines() if line.strip().startswith("|")][2:]
        for i, s in enumerate(steps, 1):
            fields += [("step", s[0], Decimal(s[2]) if len(s) > 2 and re.fullmatch(r"[\d.]+", s[2]) else None, None, 1, i), ("step_owner", s[1] if len(s) > 1 else None, None, None, 1, i),
                       ("step_manual", s[3].lower() if len(s) > 3 else None, None, None, 1, i)]
        self.doc(p, "sop", title, kind="sops", received=recv, date_=reviewed, fields=fields)
        n += 1
        self.note("sops", files=1)
    self.note("sops", rows=n)


# ---- access register and the joiner / leaver mail ---------------------------------------------------------------------------------------------

def ctl_access(self) -> None:
    n = 0
    grants = []
    for p in self.files("access_register", "*.csv"):
        recv = self.arrival(p)
        rows = P.csv_rows(p)
        did = self.doc(p, "access_register", p.stem, kind="access_register", received=recv, date_=recv, personal=True, fields=[("grants", None, Decimal(len(rows)))])
        for i, r in enumerate(rows, 2):
            who, system = r["person"].strip(), r["system"].strip()
            appr = (r.get("approved_by") or "").strip() or None
            used = P.parse_date(r["last_used"]) if (r.get("last_used") or "").strip() else None
            gid = r.get("grant_id")
            if appr is None:
                self.note("access_register", flag=f"{gid}: {who} holds {system} ({r['permission']}) with no approver")
            elif appr == who:
                self.note("access_register", flag=f"{gid}: {who} approved their own {system} access ({r['permission']})")
            if used is None:
                self.note("access_register", flag=f"{gid}: {who} on {system} has no last-used date")
            rec = dict(person_name=who, user_id=self.person(who, r.get("title")), system_name=system, access_level=r["permission"].strip(), granted_on=P.parse_date(r["granted_on"]),
                       approved_by_name=appr, approved_by_user_id=self.person(appr) if appr else None, last_used_on=used, status="active")
            sr = _row_record(self, "access_register", p, recv, gid, i, None, rec["granted_on"])
            n += _put(self, "system_access_grants", rec, **_meta(self, did, sr, recv, None)) is not None
            grants.append(rec)
        self.note("access_register", files=1)
    for p in self.files("access_register", "*.eml"):
        msg, text, sent = _eml(p)
        extra = []
        j = re.search(r"Joiner:\s*([^,]+),\s*([^,]+),.*?Please give\s+(.+?)\.(?:\s|$)", text, re.S)
        if j:
            asked = [re.sub(r"\s*\([^)]*\)", "", s).strip() for s in re.split(r",\s*|\s+and\s+", j[3]) if s.strip()]
            asked = [(s[4:] if s.lower().startswith("the ") else s) for s in asked]
            asked = [s[0].upper() + s[1:] for s in asked]
            extra += [("joiner", j[1].strip()), ("joiner_title", j[2].strip())] + [("joiner_access", s) for s in asked]
            held = {g["system_name"] for g in grants if g["person_name"] == j[1].strip()}
            asked_l = {a.lower() for a in asked}
            for s in sorted(h for h in held if h.lower() not in asked_l):
                self.note("access_register", flag=f"{j[1].strip()} holds {s}, which the joiner mail did not ask for")
        lv = re.search(r"Leaver:\s*([^,]+),\s*([^,]+),\s*last day\s+(\d{1,2} \w+)", text)
        if lv:
            extra += [("leaver", lv[1].strip()), ("leaver_last_day", P.parse_date(f"{lv[3]} {sent.year}").isoformat())]
            held = [g["system_name"] for g in grants if g["person_name"] == lv[1].strip()]
            if held:
                self.note("access_register", flag=f"leaver {lv[1].strip()} still holds {', '.join(held)}")
        _email_doc(self, "access_register", p, extra, personal=True)
        self.note("access_register", files=1)
    self.note("access_register", rows=n)


# ---- KYC register, onboarding file, bank forms -------------------------------------------------------------------------------------------------

def _kyc_row(self, p: Path, did: str, recv: date, i: int, code: str, counterparty: str, document: str, issued, expires, status: str | None = None) -> int:
    kind, _, who = document.partition(",")
    person = bool(who.strip())
    entity_name = self.md["entities"][code]
    today = self.today
    st = status or ("expired" if expires and expires < today else "valid")
    rec = dict(subject_kind="person" if person else "entity", subject_name=who.strip() if person else entity_name, legal_entity_id=self.ent[code], document_kind=f"{kind.strip()} for {counterparty}",
               issued_on=issued, expires_on=expires, verified_on=None, verified_by=None, status=st)
    sr = _row_record(self, "kyc_register", p, recv, f"{code}/{counterparty}/{document}", i, None, issued)
    self.field(did, "counterparty", counterparty, line=i)
    if st == "expired":
        self.note("kyc_register", flag=f"{entity_name}: {document} for {counterparty} expired on {expires}")
    return _put(self, "kyc_records", rec, **_meta(self, did, sr, recv)) is not None


def ctl_kyc(self) -> None:
    n = 0
    for p in self.files("kyc_register"):
        recv = self.arrival(p)
        if p.suffix.lower() == ".csv":
            rows = P.csv_rows(p)
            did = self.doc(p, "kyc_register", p.stem, kind="kyc_register", received=recv, date_=recv, personal=True, fields=[("documents", None, Decimal(len(rows)))])
            for i, r in enumerate(rows, 2):
                code = _entity_code(self, r["entity"])
                if code is None or not r["expires"].strip():
                    self.note("kyc_register", flag=f"{p.name} row {i}: entity '{r['entity']}' or expiry date is missing; not written")
                    continue
                n += _kyc_row(self, p, did, recv, i, code, r["counterparty"].strip(), r["document"].strip(), P.parse_date(r["issued"]) if r["issued"].strip() else None, P.parse_date(r["expires"]))
        elif p.suffix.lower() == ".pdf":
            text = P.pdf_text(str(p))
            lines = [x.strip() for x in text.splitlines() if x.strip()]
            code = _entity_code(self, re.sub(r"\s*-\s*KYC PACK.*", "", lines[0]))
            did = self.doc(p, "kyc_pack", lines[0].title(), kind="kyc_register", received=recv, date_=recv, personal=True)
            for i, line in enumerate(lines[1:], 2):
                m = re.fullmatch(r"(.+?) \| (.+?) \| issued (\d{4}-\d{2}-\d{2}) \| expires (\d{4}-\d{2}-\d{2})", line)
                if m and code:
                    n += _kyc_row(self, p, did, recv, i, code, m[2], m[1], P.parse_date(m[3]), P.parse_date(m[4]))
        self.note("kyc_register", files=1)
    self.note("kyc_register", rows=n)


def ctl_onboarding(self) -> None:
    n = 0
    for p in self.files("onboarding"):
        recv = self.arrival(p)
        suffix = p.suffix.lower()
        if suffix == ".csv":
            rows = P.csv_rows(p)
            who = (re.search(r"checklist[_ ]+(.+)$", p.stem, re.I) or [None, p.stem])[1].replace("_", " ")
            fields = []
            for i, r in enumerate(rows, 1):
                fields += [("checklist_item", r["item"].strip(), None, None, 1, i), ("checklist_status", r["status"].strip().lower(), None, None, 1, i), ("checklist_note", r.get("note"), None, None, 1, i)]
                if r["status"].strip().lower() != "complete":
                    self.note("onboarding", flag=f"{who}: '{r['item'].strip()}' is {r['status'].strip().lower()} ({(r.get('note') or '').strip()})")
            self.doc(p, "onboarding_checklist", f"Onboarding checklist {who}", kind="onboarding", received=recv, date_=recv, fields=[("manager", who), *fields])
            n += len(rows)
        else:
            text = P.pdf_text(str(p))
            lines = [x.strip() for x in text.splitlines() if x.strip()]
            if "KYC PACK" in lines[0].upper():
                who = re.sub(r"\s*-\s*KYC PACK.*", "", lines[0]).title()
                items = [re.fullmatch(r"\d+\.\s*(.+?):\s*(\w+)", x) for x in lines[1:]]
                did = self.doc(p, "kyc_pack", lines[0].title(), kind="onboarding", received=recv, date_=recv, personal=True, fields=[("manager", who)])
                for i, m in enumerate(filter(None, items), 2):
                    rec = dict(subject_kind="manager", subject_name=who, legal_entity_id=None, document_kind=m[1].strip(), issued_on=None, expires_on=None, verified_on=None, verified_by=None,
                               status=m[2].lower())
                    sr = _row_record(self, "onboarding", p, recv, f"{who}/{m[1]}", i)
                    n += _put(self, "kyc_records", rec, **_meta(self, did, sr, recv)) is not None
            else:
                inv = re.search(r"Investor:\s*(.+?)\s{2,}Commitment:\s*([A-Z]{3})\s*([\d,]+)", text)
                unsigned = bool(re.search(r"not yet signed", text, re.I))
                bank = re.search(r"Bank details for calls:\s*(.+)", text)
                fields = [("signature_status", "not signed" if unsigned else "signed"), ("call_bank_details", bank[1].strip() if bank else None)]
                if inv:
                    fields += [("investor", inv[1]), ("commitment", None, P.money(inv[3]), inv[2])]
                if unsigned:
                    self.note("onboarding", flag=f"{p.name}: the subscription document is not signed")
                if bank and "to be advised" in bank[1].lower():
                    self.note("onboarding", flag=f"{p.name}: bank details for calls are still to be advised")
                self.doc(p, "subscription_document", lines[0].title(), kind="onboarding", received=recv, date_=recv, status="draft" if "DRAFT" in lines[0].upper() else "final", fields=fields)
        self.note("onboarding", files=1)
    self.note("onboarding", rows=n)


def ctl_bank_forms(self) -> None:
    n = 0
    for p in self.files("bank_forms"):
        recv = self.arrival(p)
        text = P.pdf_text(str(p))
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        head = lines[0].upper()
        if "SIGNING POLICY" in head:
            mn = re.search(r"at least (\d+) signator", text)
            role = re.search(r"one of whom is the ([A-Z][\w ]+?)[.,]", text)
            fields = [("min_signatories", None, Decimal(mn[1])) if mn else ("min_signatories", None), ("required_role", role[1] if role else None)]
            self.doc(p, "signing_policy", lines[0].title(), kind="bank_forms", received=recv, date_=recv, fields=fields)
            if mn and role:
                _proposed_rule(self, "signing_policy", f"Every office account has at least {mn[1]} signatories, one of whom is the {role[1]} (from {p.name}, not yet signed)",
                               {"min_signatories": int(mn[1]), "required_role": role[1]})
                n += 1
            else:
                self.note("bank_forms", flag=f"{p.name}: the signing policy has no readable minimum or required role; no rule written")
        else:
            holder = re.search(r"Account holder:\s*(.+)", text)
            bank = re.search(r"Bank:\s*(.+?)\s{2,}Currency:\s*([A-Z]{3})", text)
            purpose = re.search(r"Purpose:\s*(.+)", text)
            sigs = [(m[1].strip(), (m[2] or "").strip()) for m in re.finditer(r"Signatory \d+:\s*([^(\n]+?)\s*(?:\(([^)]*)\))?\s*$", text, re.M)]
            mandate = re.search(r"Mandate:\s*(.+)", text)
            code = _entity_code(self, holder[1] if holder else None)
            fields = [("account_holder", holder[1].strip() if holder else None), ("mandate", mandate[1].strip() if mandate else None)]
            for i, (nm, role) in enumerate(sigs, 1):
                fields += [("signatory", nm, None, None, 1, i), ("signatory_role", role or None, None, None, 1, i)]
            did = self.doc(p, "account_opening_form", lines[0].title(), kind="bank_forms", received=recv, date_=recv, fields=fields, personal=True)
            sr = self.doc_record(did)
            self.add("bank_accounts", holder_kind="office", legal_entity_id=self.ent.get(code), holder_name=holder[1].strip() if holder else None, account_purpose=(purpose[1].strip() if purpose else "operating"),
                     bank_name=bank[1].strip() if bank else None, account_ref="pending", currency=bank[2] if bank else None, status="pending", source_record_id=sr, source_document_id=did, source_page=1,
                     received_at=P.stamp(recv), recorded_at=P.stamp(recv))
            n += 1
            if len(sigs) < 2:
                self.note("bank_forms", flag=f"{p.name}: {len(sigs)} signatory on the form")
            if not any("head of finance" in role.lower() for _, role in sigs):
                self.note("bank_forms", flag=f"{p.name}: no signatory is the Head of Finance")
        self.note("bank_forms", files=1)
    self.note("bank_forms", rows=n)


# ---- family access ---------------------------------------------------------------------------------------------------------------------------

def ctl_family_access(self) -> None:
    n = 0
    policy: dict[tuple[str, str], str] = {}
    for p in self.files("family_access", "*.pdf"):
        recv = self.arrival(p)
        text = P.pdf_text(str(p))
        names = sorted(self.md["entities"].values(), key=len, reverse=True)
        fields = []
        for line in text.splitlines():
            m = re.match(r"([A-Z][a-z]+ [A-Z][a-z]+):\s*(.+)", line.strip())
            if not m:
                continue
            for ename, level in re.findall("(" + "|".join(re.escape(x) for x in names) + r")\s+(full|summary|none)", m[2]):
                code = _entity_code(self, ename)
                policy[(m[1], code)] = level
                fields.append(("policy_level", f"{m[1]} | {code} | {level}"))
                _proposed_rule(self, f"family_access_{slug(m[1])}_{slug(code)}", f"{m[1]} sees {ename} at the level '{level}' (family access policy, not yet signed)", {"level": level})
                n += 1
        self.doc(p, "family_access_policy", p.stem, kind="family_access", received=recv, date_=recv, fields=fields, personal=True)
        self.note("family_access", files=1)
    scopes = _scope_state(self)
    for p in self.files("family_access", "*.csv"):
        recv = self.arrival(p)
        rows = P.csv_rows(p)
        did = self.doc(p, "family_view_grants", p.stem, kind="family_access", received=recv, date_=recv, personal=True, fields=[("grants", None, Decimal(len(rows)))])
        for i, r in enumerate(rows, 2):
            who, code, level = r["member"].strip(), _entity_code(self, r["entity"]), r["level"].strip().lower()
            if code is None or level not in LEVELS:
                self.note("family_access", flag=f"{p.name} row {i}: entity '{r['entity']}' or level '{level}' not understood; not written")
                continue
            gname = f"family:{who}"
            uid = self.person(who, "family member")
            if (gname, code) not in scopes and level != "none":
                gid = self.group(gname)
                if ("member", gname) not in self.inst:
                    self.inst[("member", gname)] = 1
                    self.add("access_group_memberships", access_group_id=gid, user_id=uid, granted_at=P.stamp(P.parse_date(r["granted_on"])))
                self.add("access_group_scopes", access_group_id=gid, scope_type="entity", scope_value=code, access_level="preview" if level == "summary" else level)
                scopes[(gname, code)] = level
                n += 1
            elif scopes.get((gname, code)) not in (None, level):
                self.note("family_access", flag=f"{who} on {code}: the grant is now '{level}', was '{scopes[(gname, code)]}'; the earlier scope row stays on record")
            allowed = policy.get((who, code)) or self._ctl_rule_level(who, code)
            if allowed is not None and LEVELS[level] > LEVELS[allowed]:
                self.note("family_access", flag=f"{who} is granted '{level}' on {self.md['entities'][code]}, the policy allows '{allowed}'")
        self.note("family_access", files=1)
    for p in self.files("family_access", "*.eml"):
        msg, text, sent = _eml(p)
        who = re.sub(r"\s*<.*", "", str(msg["From"]))
        names = sorted(self.md["entities"].values(), key=len, reverse=True)
        ent = next((x for x in names if x.lower() in text.lower()), None)
        fields = [("requester", who), ("requested_entity", _entity_code(self, ent)), ("requested_level", "summary" if re.search(r"\breport\b", text, re.I) else None)]
        _email_doc(self, "family_access", p, fields, personal=True)
        self.note("family_access", files=1)
    self.note("family_access", rows=n)


def _scope_state(self) -> dict:
    out = {}
    try:
        for g, v, lvl in self.con.execute("select g.group_name, s.scope_value, s.access_level from access_group_scopes s join access_groups g on g.id = s.access_group_id").fetchall():
            out[(g, v)] = "summary" if lvl == "preview" else lvl
    except Exception:  # noqa: BLE001
        pass
    return out


def _ctl_rule_level(self, who: str, code: str) -> str | None:
    """The level a signed or proposed rule `family_access_<member>_<entity>` gives, when the policy file is not in this batch."""
    try:
        r = self.con.execute("select v.parameters from business_rules b join rule_versions v on v.business_rule_id = b.id where b.rule_code = ? order by v.version_number desc limit 1",
                             [f"family_access_{slug(who)}_{slug(code)}"]).fetchone()
        return json.loads(r[0])["level"] if r else None
    except Exception:  # noqa: BLE001
        return None


# ---- glossary ------------------------------------------------------------------------------------------------------------------------------------

def ctl_glossary(self) -> None:
    n = 0
    listed: set[str] = set()
    for p in self.files("glossary", "*.csv"):
        recv = self.arrival(p)
        rows = P.csv_rows(p)
        fields = []
        for i, r in enumerate(rows, 1):
            term = r["term"].strip()
            listed.add(term.lower())
            fields.append(("term", term, None, None, 1, i))
            for a in filter(None, (x.strip() for x in (r.get("aliases") or "").split(";"))):
                fields.append(("alias", a, None, None, 1, i))
                listed.add(a.lower())
            fields.append(("definition", r.get("definition"), None, None, 1, i))
        self.doc(p, "glossary", p.stem, kind="glossary", received=recv, date_=recv, fields=fields)
        n += len(rows)
        self.note("glossary", files=1)
    proposed = []
    for p in self.files("glossary", "*.md"):
        recv = self.arrival(p)
        terms = [m[1].strip() for m in re.finditer(r"^\s*[-*]\s+(.+)$", p.read_text(encoding="utf-8-sig"), re.M)]
        proposed += terms
        self.doc(p, "word_review", p.stem, kind="glossary", received=recv, date_=recv, fields=[("proposed_term", t) for t in terms])
        self.note("glossary", files=1)
    for p in self.files("glossary", "*.eml"):
        msg, text, sent = _eml(p)
        terms = [a or b for a, b in re.findall(r"'([^']{2,60})'|“([^”]{2,60})”", text)]
        proposed += terms
        _email_doc(self, "glossary", p, [("proposed_term", t) for t in terms])
        self.note("glossary", files=1)
    if listed:
        for t in sorted({x.lower() for x in proposed}):
            if t in listed:
                self.note("glossary", flag=f"'{t}' is proposed but already in the word list")
    self.note("glossary", rows=n + len(proposed))


# ---- break register ---------------------------------------------------------------------------------------------------------------------------

def ctl_breaks(self) -> None:
    n = 0
    have: set[str] = set()
    try:
        have = {r[0] for r in self.con.execute("select external_ref from exceptions where exception_type = 'break' and external_ref is not null").fetchall()}
    except Exception:  # noqa: BLE001
        pass
    for p in self.files("break_register"):
        recv = self.arrival(p)
        rows = P.csv_rows(p)
        self.doc(p, "break_register", p.stem, kind="break_register", received=recv, date_=recv, fields=[("breaks", None, Decimal(len(rows)))])
        for r in rows:
            bid = r["break_id"].strip()
            if bid in have:
                self.note("break_register", flag=f"{bid} is already on record; not written twice")
                continue
            have.add(bid)
            status = r["status"].strip().lower()
            code = _entity_code(self, r["entity"])
            d = P.parse_date(r["detected_on"])
            self.add("exceptions", exception_type="break", external_ref=bid, title=r["subject"].strip(), description=f"{r['type'].strip()}; owner {r['owner'].strip()}", detected_at=P.stamp(d),
                     legal_entity_id=self.ent.get(code), owner_user_id=self.person(r["owner"].strip()), status="open" if status == "open" else "closed", materiality_status="n/a")
            n += 1
            if status == "open" and (self.today - d).days > 5:
                self.note("break_register", flag=f"{bid}: {r['type'].strip()} open since {d}, {(self.today - d).days} calendar days")
        self.note("break_register", files=1)
    self.note("break_register", rows=n)


# ---- new feed: profile the columns and propose a mapping with a confidence mark each ------------------------------------------------------------

FEED_FIELDS = {  # a header word -> the model fields it could be; more than one is a doubt
    "acct": [("bank_accounts", "account_ref")], "account": [("bank_accounts", "account_ref")], "secref": [("instrument_identifiers", "identifier_value")],
    "description": [("instruments", "canonical_name")], "qty": [("position_snapshots", "quantity")], "px": [("market_observations", "value")], "price": [("market_observations", "value")],
    "cost": [("ignore", "cost")], "ccy": [("position_snapshots", "currency")], "currency": [("position_snapshots", "currency")], "status": [("position_snapshots", "data_status")],
    "value": [("position_snapshots", "source_market_value"), ("ignore", "book value")],  # market value or book value
    "dt": [("position_snapshots", "as_of_at"), ("transactions", "trade_date"), ("transactions", "settlement_date")], "date": [("position_snapshots", "as_of_at"), ("transactions", "trade_date")],
}


def ctl_new_feed(self) -> None:
    n = 0
    provider = None
    for p in self.files("new_feed", "*.pdf"):
        recv = self.arrival(p)
        text = P.pdf_text(str(p))
        first = next((x.strip() for x in text.splitlines() if x.strip()), p.stem)
        provider = provider or re.sub(r"\s*\(synthetic\)", "", first, flags=re.I).title()
        self.doc(p, "feed_cover_note", p.stem, kind="new_feed", received=recv, date_=recv, fields=[("provider", provider), ("note", re.sub(r"\s+", " ", text)[:300])])
        self.note("new_feed", files=1)
    for p in self.files("new_feed", "*.csv"):
        recv = self.arrival(p)
        rows = P.csv_rows(p)
        head = list(rows[0]) if rows else next(csv.reader(open(p, encoding="utf-8-sig")), [])
        sysid = self.source("new_feed", name=provider or "new feed")
        mid = self.add("sheet_mappings", source_system_id=sysid, file_pattern=re.sub(r"\d{4}-\d{2}-\d{2}", "*", p.name), sheet_name=None, header_row=1, version_number=1, mapping_status="proposed")
        doubt = []
        for h in head:
            cands = FEED_FIELDS.get(re.sub(r"[^a-z]", "", h.lower()))
            if not cands:
                tgt, conf, how = ("ignore", h), "doubt", "no known meaning for this header"
            elif len(cands) > 1:
                tgt, conf, how = cands[0], "doubt", "could be " + " or ".join(f"{t}.{f}" for t, f in cands)
            else:
                tgt, conf, how = cands[0], "high", None
            if conf == "doubt":
                doubt.append(h)
            self.add("sheet_mapping_columns", sheet_mapping_id=mid, source_column=h, target_table=tgt[0], target_field=tgt[1], transform_rule=how, confidence=conf)
        summary = json.dumps({"columns": len(head), "mapped_with_confidence": len(head) - len(doubt), "in_doubt": doubt, "rows_in_sample": len(rows), "mapping": "proposed, not approved"})
        b = self.batch("new_feed", p, recv, summary=summary, mapping=mid)
        for r in self.rows.get("source_batches", []):
            if r["id"] == b:
                r["validation_status"] = "mapping_proposed"
        self.add("source_records", source_batch_id=b, record_type="file", received_at=P.stamp(recv), recorded_at=P.stamp(recv), raw_payload_uri=self.rel(p), content_hash=P.file_hash(p))
        self.note("new_feed", files=1, flag=f"{p.name}: {len(head) - len(doubt)} of {len(head)} columns mapped with confidence; in doubt: {', '.join(doubt) or 'none'}; no rows loaded until the mapping is approved")
        n += len(head)
    self.note("new_feed", rows=n)


# ---- inbox: files of unknown origin, read by content --------------------------------------------------------------------------------------------

def ctl_inbox(self) -> None:
    n = 0
    known_refs: set[str] = {r["external_record_id"] for r in self.rows.get("source_records", []) if r.get("external_record_id")}
    known_hash = {h for h in self.seen_hash}
    try:
        known_refs |= {r[0] for r in self.con.execute("select external_record_id from source_records where record_type = 'bank_line' and external_record_id is not null").fetchall()}
        known_hash |= {r[0] for r in self.con.execute("select content_hash from documents where content_hash is not null").fetchall()}
        known_hash |= {r[0] for r in self.con.execute("select content_hash from source_batches where content_hash is not null").fetchall()}
    except Exception:  # noqa: BLE001
        pass
    office = [x.lower() for x in [*self.md["entities"].values(), "evergreen"]]
    for p in self.files("inbox"):
        recv = self.arrival(p)
        data = p.read_bytes()
        digest = P.hashlib.sha256(data).hexdigest()
        found = P.kind_of(p.name, data)
        what = _what(p, data)
        fields = [("what", what)]
        if found is None:
            refuse = p.suffix.lower() == ".pdf" and not any(o in what.lower() or o in P.pdf_text(str(p)).lower() for o in office)
            action = "refuse and return to the sender" if refuse else "hold and ask the sender what it is"
            fields += [("belongs_in", "unknown"), ("inbox_action", action)]
            self.doc(p, "unrecognised", p.name, kind="inbox", received=recv, date_=recv, fields=fields)
            self.note("inbox", flag=f"{p.name}: not a kind the office knows ({what}); {action}")
        else:
            dup = digest in known_hash
            if not dup and p.suffix.lower() in (".xlsx", ".xlsm") and found[0] == "bank_statements":
                refs = {str(r["Reference"]) for r in P.dicts(P.sheet_rows(p, "Transactions")) if r.get("Reference")}
                dup = bool(refs) and refs <= known_refs
            action = "duplicate of a file already loaded" if dup else "new, to be read as " + found[0]
            fields += [("belongs_in", found[0]), ("inbox_action", action)]
            self.doc(p, "inbox_file", p.name, kind="inbox", received=recv, date_=recv, status="duplicate" if dup else "final", fields=fields)
            self.note("inbox", flag=f"{p.name}: looks like {found[0]} ({what}); {action}")
        n += 1
        self.note("inbox", files=1)
    self.note("inbox", rows=n)


def _what(p: Path, data: bytes) -> str:
    if p.suffix.lower() == ".pdf":
        lines = [x.strip() for x in P._pdf_head(data).splitlines() if x.strip()]
        return " / ".join(lines[:2])[:160]
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        wb = P.openpyxl.load_workbook(io.BytesIO(data), read_only=True)
        try:
            ws = wb.worksheets[0]
            head = next(ws.iter_rows(values_only=True), ())
            return f"sheet {ws.title}, columns {', '.join(str(h) for h in head if h is not None)}"[:160]
        finally:
            wb.close()
    return p.name


# ---- load log: the desk's record of each load, put on the batches it describes -------------------------------------------------------------------------

def _with_source(summary: str | None, source: str) -> str:
    """The batch's validation summary (JSON) with the load log's name for its source added; other words in it are kept."""
    try:
        d = json.loads(summary) if summary else {}
        d = d if isinstance(d, dict) else {"summary": summary}
    except ValueError:
        d = {"summary": summary}
    return json.dumps({**d, "load_log_source": source})


def ctl_load_log(self) -> None:
    n = 0
    by_name: dict[str, tuple[str, dict | None]] = {}
    for r in self.rows.get("source_batches", []):
        by_name[Path(str(r.get("batch_reference"))).name] = (r["id"], r)
    try:
        for bid, ref in self.con.execute("select id, batch_reference from source_batches").fetchall():
            by_name.setdefault(Path(str(ref)).name, (str(bid), None))
    except Exception:  # noqa: BLE001
        pass
    for p in self.files("load_log"):
        recv = self.arrival(p)
        rows = P.csv_rows(p)
        self.doc(p, "load_log", p.stem, kind="load_log", received=recv, date_=recv, fields=[("loads", None, Decimal(len(rows)))])
        flag = lambda v: str(v).strip().lower() in ("true", "yes", "1", "y")  # noqa: E731
        for i, r in enumerate(rows, 2):
            name = Path(r["file"].strip()).name
            on_time, adds_up, fix = flag(r["on_time"]), flag(r["adds_up"]), flag(r["manual_fix"])
            if r["file"].strip().startswith("(missing)"):
                self.note("load_log", flag=f"{r['source']}: {name} never arrived; there is no batch to mark")
                continue
            hit = by_name.get(name)
            if hit is None:
                self.note("load_log", flag=f"{r['source']}: {name} is not among the loaded files; not marked")
                continue
            bid, mem = hit
            if mem is not None:
                mem.update(arrived_on_time=on_time, manual_fix=fix, validation_summary=_with_source(mem.get("validation_summary"), r["source"]))
            else:
                was = self.con.execute("select validation_summary from source_batches where id = ?", [bid]).fetchone()[0]
                self.con.execute("update source_batches set arrived_on_time = ?, manual_fix = ?, validation_summary = ? where id = ?", [on_time, fix, _with_source(was, r["source"]), bid])
            self.add("batch_control_totals", source_batch_id=bid, measure_name="adds_up", expected_value=Decimal(1), loaded_value=Decimal(1 if adds_up else 0), tolerance=Decimal(0), passed=adds_up)
            n += 1
            for bad, why in ((not on_time, "late"), (not adds_up, "did not add up"), (fix, "needed a manual fix")):
                if bad:
                    self.note("load_log", flag=f"{r['source']}: {name} {why}")
        self.note("load_log", files=1)
    self.note("load_log", rows=n)


# ---- registering with the pack readers -----------------------------------------------------------------------------------------------------------

def install(module) -> None:
    """Register the kinds and give Office the step `controls` (it runs last: the load log marks batches the other steps made). Called at the end of v3_pack_readers."""
    global P
    P = module
    for fn in (ctl_payroll_paid, ctl_expenses, ctl_payroll_drafts, ctl_sops, ctl_access, ctl_kyc, ctl_onboarding, ctl_bank_forms, ctl_family_access, ctl_glossary, ctl_breaks,
               ctl_new_feed, ctl_inbox, ctl_load_log, _ctl_rule_level):
        setattr(module.Office, fn.__name__, fn)

    def controls(self) -> None:
        for name in STEPS:
            getattr(self, name)()
    module.Office.controls = controls
    module.KINDS.update(KINDS)
    module.STEP_KINDS.update(STEP_KINDS)
    module.OWN_MONTH.add("payroll_drafts")  # the draft of October arrives in October
    module.FLUSH_ORDER[:] = [*module.FLUSH_ORDER, *(t for t in FLUSH if t not in module.FLUSH_ORDER)]
    plain = module.kind_of

    def kind_of(name: str, data: bytes):
        return plain(name, data) or globals()["kind_of"](name, data)  # noqa: F821 - this module's kind_of, the one above
    kind_of.__doc__ = plain.__doc__
    module.kind_of = kind_of
