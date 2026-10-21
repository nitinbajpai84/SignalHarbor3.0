"""Pack readers of the family group (cards 83 to 88): tax calendar, tax notices, grant ledger, grant requests, trust deed, estate planning.
v3_pack_readers calls `install(module)` once; the readers are methods of its Office and run as the step `family` (after `controls`).

Where the rows go (docs/v3/ASSUMPTIONS.md A40, A41, A44):
  tax_calendar   -> tax_obligations (one row per obligation; a changed status is a new row that supersedes); the 2026 rates as PROPOSED rules tax_rate_<entity>
  tax_notices    -> a document with extracted_fields taxpayer, filing_due (ISO), tax_rate_income (fraction); checked against the calendar
  grant_ledger   -> grants (paid and pledged; a pledge's planned date is a document field planned_date, grants has no column for it); PROPOSED rule grant_budget
  grant_requests -> grants with status requested (the request pdf and the mail that carried it are documents); facts against the budget are flagged
  trust_deed     -> a document in the restricted group: fields beneficiary_share (value_text the beneficiary, value_numeric a fraction), payout_cap_pct (a percent: 70),
                    trust_year_start, trust_year_end, successor_trustee. No table (A44).
  ownership_register (reference/ownership_register.csv, A61) -> entity_ownership, one row per period, plus a family_members row for a holder no allowance schedule names; the rule
                    checks (holders add to 100, no overlap, no circle) are exceptions ownership_gap, ownership_overlap, ownership_cycle
  estate_planning-> a document: fields estate_tax_exemption, estate_tax_rate (fraction), payment_term_months, valuation_basis; PROPOSED rules estate_tax_exemption, estate_tax_rate
Rules the files state are written as proposed (A20: signing is the office's, through approvals); a rule already signed is never touched. The legal entity of
a grant is EG-HOLD: the ledger names none and its bank references are paid from the Holdings USD account (flagged). Synthetic data only."""
from __future__ import annotations

import email
import io
import json
import re
from datetime import date
from decimal import Decimal
from email import policy as email_policy

from sh_platform.v1 import v3_pack_readers_controls as C

P = None  # the pack readers module, set by install()
KINDS = {
    "tax_calendar": ("tax calendar", "data.read-tax-calendar", "tax obligations and rules (proposed)"),
    "tax_notices": ("tax notice", "data.read-tax-notice", "documents and fields"),
    "grant_ledger": ("grant ledger", "data.read-grant-ledger", "grants and the grant budget rule (proposed)"),
    "grant_requests": ("grant request", "data.read-grant-request", "grants and documents"),
    "trust_deed": ("trust deed", "data.read-trust-deed", "documents and fields"),
    "estate_planning": ("transfer tax memo", "data.read-estate-memo", "documents, fields and rules (proposed)"),
}
SPEC = {  # for controls._put: table -> (the columns that say which row it is, the columns that say what it holds)
    "tax_obligations": (("obligation_ref",), ("legal_entity_id", "obligation", "due_date", "prepared_by", "estimated_amount", "currency", "status", "filed_on", "paid_on")),
    "grants": (("grant_ref",), ("charity_name", "charity_registered_on", "purpose", "legal_entity_id", "amount", "currency", "requested_on", "decided_on", "paid_on", "payment_reference", "status")),
}
SUPERSEDES = {"tax_obligations": "supersedes_tax_obligation_id", "grants": "supersedes_grant_id"}
DONE = {"filed", "paid", "complete", "completed", "done"}


def slug(text) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def kind_of(name: str, data: bytes):
    low = name.lower()
    try:
        if low.endswith((".xlsx", ".xlsm")):
            wb = P.openpyxl.load_workbook(io.BytesIO(data), read_only=True)
            try:
                s = set(wb.sheetnames)
            finally:
                wb.close()
            return ("tax_calendar", name) if {"Obligations", "Rates"} <= s else ("grant_ledger", name) if {"Grants", "Budget"} <= s else None
        if low.endswith(".pdf"):
            up = P._pdf_head(data).upper()
            for mark, kind in (("NOTICE TO FILE ESTIMATED CHARGEABLE INCOME", "tax_notices"), ("GRANT REQUEST", "grant_requests"), ("DEED OF SETTLEMENT", "trust_deed"),
                               ("TRANSFER TAX MEMO", "estate_planning")):
                if mark in up[:400]:
                    return kind, name
    except Exception:  # noqa: BLE001 - a file that cannot be read here is not one of ours; the generic path names the problem
        return None
    return None


def rule_proposed(self, code: str, text: str, params: dict, owner: str = "Daniel Foo") -> None:
    """A rule the files state, proposed. Nothing signed is touched; a different figure beside an earlier proposal is its next version."""
    rid = self.inst.get(("rule", code)) or self.k_rule.get(code)
    if rid is None:
        self.rule(code, "policy", text, params, owner, owner, status="proposed")
        return
    vers = [(v["version_number"], v["approval_status"], v["parameters"]) for v in self.rows.get("rule_versions", []) if v["business_rule_id"] == rid]
    try:
        vers += self.con.execute("select version_number, approval_status, parameters from rule_versions where business_rule_id = ?", [rid]).fetchall()
    except Exception:  # noqa: BLE001
        pass
    top = max(vers, default=None)
    if top is None or top[1] == "approved":
        return  # signed: the figure in the file is not written over it
    old = json.loads(top[2]) if isinstance(top[2], str) else top[2]
    if old != params:
        self.add("rule_versions", business_rule_id=rid, version_number=top[0] + 1, definition_text=text, parameters=json.dumps(params), effective_from="2026-04-01", approval_status="proposed")


def _src(self, kind, p, recv, did, ref, i, sheet=None):
    sr = self.record(kind, p, recv, rtype="row", external=ref, sheet=sheet, row=i)
    return dict(source_record_id=sr, source_document_id=did, source_page=1, received_at=P.stamp(recv), recorded_at=P.stamp(recv))


def _fields(self, p, dtype, kind, recv, fields, personal=False):
    return self.doc(p, dtype, p.stem, kind=kind, received=recv, date_=recv, fields=fields, personal=personal)


# ---------------------------------------------------------------------------------------------------------------- tax calendar
def fam_tax_calendar(self) -> None:
    for p in self.files("tax_calendar"):
        recv, n = self.arrival(p), 0
        rates = P.dicts(P.sheet_rows(p, "Rates"))
        fields = []
        for r in rates:
            code = C._entity_code(self, r["Entity"])
            if code is None:
                self.note("tax_calendar", flag=f"rate for {r['Entity']!r}: not an entity of the office; set aside")
                continue
            inc, gain = Decimal(str(r["Tax rate on income"])), Decimal(str(r["Tax rate on realised gains"]))
            fields += [(f"tax_rate_income", code, inc), (f"tax_rate_realised_gain", code, gain)]
            rule_proposed(self, f"tax_rate_{slug(code)}", f"{self.md['entities'][code]}: tax on income {inc:.0%}, on realised gains {gain:.0%} (tax calendar 2026-27, not yet signed)",
                          {"income": float(inc), "realised_gain": float(gain)}, "Helen Foo")
            self.__dict__.setdefault("_tax_rates", {})[code] = inc
        did = _fields(self, p, "tax_calendar", "adviser", recv, fields)
        seen = set()
        for i, r in enumerate(P.dicts(P.sheet_rows(p, "Obligations")), 2):
            ref, code = str(r["Id"] or "").strip(), C._entity_code(self, r["Entity"])
            if not ref or code is None or ref in seen:
                self.note("tax_calendar", flag=f"row {i}: {ref!r} {r['Entity']!r} is not a new obligation of an entity of the office; set aside")
                continue
            seen.add(ref)
            try:
                due = P.parse_date(r["Due"], hint=recv)
            except Exception:  # noqa: BLE001 - a date that cannot be read is not guessed
                self.note("tax_calendar", flag=f"{ref}: due date {r['Due']!r} not readable; set aside")
                continue
            status, est = str(r["Status"] or "").strip().lower(), r["Estimated amount"]
            rid = C._put(self, "tax_obligations", dict(obligation_ref=ref, legal_entity_id=self.ent[code], obligation=r["Obligation"], due_date=due, prepared_by=r["Prepared by"],
                                                       estimated_amount=None if est in (None, "") else Decimal(str(est)), currency=r["Currency"], status=status, filed_on=None, paid_on=None),
                         **_src(self, "tax_calendar", p, recv, did, ref, i, "Obligations"))
            n += rid is not None
            if due < self.today and status not in DONE:
                self.note("tax_calendar", flag=f"{ref} {code}: {r['Obligation']} was due {due} and is '{status}': {(self.today - due).days} days overdue")
                self.exception("tax_overdue", f"{ref} is overdue: {r['Obligation']}", f"{code}, due {due}, status '{status}'.", recv, legal_entity_id=self.ent[code])
        self.note("tax_calendar", files=1, rows=n)


# ---------------------------------------------------------------------------------------------------------------- tax notices
def fam_tax_notices(self) -> None:
    for p in self.files("tax_notices"):
        t, recv = P.pdf_text(str(p)), self.arrival(p)
        who, due, rate = (re.search(x, t) for x in (r"Taxpayer:\s*(.+)", r"Filing due:\s*(\d{1,2} \w+ \d{4})", r"Tax rate on income:\s*([\d.]+) percent"))
        if not (who and due):
            self.note("tax_notices", why=f"{p.name}: taxpayer or filing date not readable")
            continue
        code, due_d = C._entity_code(self, who[1]), P.parse_date(due[1])
        self.doc(p, "tax_notice", p.stem, kind="tax authority", received=recv, date_=recv,
                 fields=[("taxpayer", who[1].strip()), ("entity", code), ("filing_due", due_d.isoformat()), *([("tax_rate_income", None, Decimal(rate[1]) / 100)] if rate else [])])
        mine = [r for r in self.rows.get("tax_obligations", []) if r["legal_entity_id"] == self.ent.get(code) and "ECI" in r["obligation"]]
        if not mine:
            self.note("tax_notices", flag=f"{p.name}: no ECI filing for {who[1].strip()} in the tax calendar")
        elif mine[-1]["due_date"] != due_d:
            self.note("tax_notices", flag=f"{p.name}: the notice says {due_d}, the tax calendar {mine[-1]['due_date']}")
        if rate and code in self.__dict__.get("_tax_rates", {}) and self._tax_rates[code] != Decimal(rate[1]) / 100:
            self.note("tax_notices", flag=f"{p.name}: the notice rate {rate[1]} percent differs from the tax calendar")
        self.note("tax_notices", files=1, rows=1)


# ---------------------------------------------------------------------------------------------------------------- grant ledger
def fam_grant_ledger(self) -> None:
    hold = self.ent["EG-HOLD"]
    for p in self.files("grant_ledger"):
        recv, n = self.arrival(p), 0
        budget = P.dicts(P.sheet_rows(p, "Budget"))
        year, amount = (budget[0]["Year"], Decimal(str(budget[0]["Annual grant budget (USD)"]))) if budget else (None, None)
        fields = [("budget_year", str(year), amount, "USD")] if amount is not None else []
        rows = P.dicts(P.sheet_rows(p, "Grants"))
        for r in rows:
            if str(r["Status"]).strip().lower() == "pledged":
                fields.append(("planned_date", str(P.parse_date(r["Date"]))[:10], None))  # the pledge's payment date: grants has no column for it
        did = _fields(self, p, "grant_ledger", "office", recv, fields)
        if amount is not None:
            rule_proposed(self, "grant_budget", f"Annual grant budget {year}: {amount:,.0f} USD (from {p.name}, not yet signed)", {"annual": float(amount), "currency": "USD", "year": year, "value": float(amount)})
        paid = pledged = Decimal(0)
        for i, r in enumerate(rows, 2):
            ref, st = str(r["Grant"] or "").strip(), str(r["Status"] or "").strip().lower()
            if not ref or st not in {"paid", "pledged", "declined"}:
                self.note("grant_ledger", flag=f"row {i}: {ref!r} status {st!r} is not paid, pledged or declined; set aside")
                continue
            amt, day, bank = Decimal(str(r["Amount (USD)"])), P.parse_date(r["Date"], hint=recv), (str(r["Bank reference"]).strip() if r["Bank reference"] else None)
            if st == "paid" and not bank:
                self.note("grant_ledger", flag=f"{ref}: paid but no bank reference; the bank cannot be matched")
            if st == "pledged" and bank:
                self.note("grant_ledger", flag=f"{ref}: pledged but a bank reference is given")
            paid += amt if st == "paid" else 0
            pledged += amt if st == "pledged" else 0
            rid = C._put(self, "grants", dict(grant_ref=ref, charity_name=r["Charity"], charity_registered_on=None, purpose=r["Purpose"], legal_entity_id=hold, amount=amt, currency="USD",
                                              requested_on=None, decided_on=None, paid_on=day if st == "paid" else None, payment_reference=bank, status=st),
                         **_src(self, "grant_ledger", p, recv, did, ref, i, "Grants"))
            n += rid is not None
        self.__dict__["_gr_state"] = (amount, paid, pledged)
        self.note("grant_ledger", flag="the ledger names no entity; the grants are placed on Evergreen Holdings (paid from its USD bank account)")
        self.note("grant_ledger", files=1, rows=n)


def _grant_state(self):
    """(budget, paid, pledged): from the ledger read in this run, else from what is on record."""
    if "_gr_state" not in self.__dict__:
        try:
            b = self.con.execute("select v.parameters from business_rules r join rule_versions v on v.business_rule_id = r.id where r.rule_code = 'grant_budget' order by v.version_number desc limit 1").fetchone()
            q = dict(self.con.execute("select status, sum(amount) from grants where id not in (select supersedes_grant_id from grants where supersedes_grant_id is not null) group by status").fetchall())
            self._gr_state = (Decimal(str(json.loads(b[0])["annual"])) if b else None, Decimal(str(q.get("paid", 0))), Decimal(str(q.get("pledged", 0))))
        except Exception:  # noqa: BLE001 - a warehouse with no ledger yet
            self._gr_state = (None, Decimal(0), Decimal(0))
    return self._gr_state


# ---------------------------------------------------------------------------------------------------------------- grant requests
def fam_grant_requests(self) -> None:
    sent_by = {}  # the day a request reached the office is the day of the mail that carried it; the pdf alone has no date
    for e in self.files("grant_requests", "*.eml"):
        sent_by[(re.search(r"REQ-\d{4}-\d+", e.name) or [e.name])[0]] = P.parsedate(email.message_from_bytes(e.read_bytes(), policy=email_policy.default)["Date"]).date()
    for p in self.files("grant_requests", "*.pdf"):  # the pdfs first: the mail that carries one is then seen to carry a file already read
        t = P.pdf_text(str(p))
        recv = sent_by.get((re.search(r"REQ-\d{4}-\d+", p.name) or [p.name])[0]) or self.arrival(p)
        m = {k: re.search(rx, t) for k, rx in (("ref", r"Request:\s*(\S+)"), ("amt", r"Amount requested:\s*([A-Z]{3}) ([\d,.]+)"), ("purpose", r"Purpose:\s*(.+)"),
                                               ("reg", r"Charity registered:\s*(\d{1,2} \w+ \d{4})"), ("who", r"^(.+)\nGRANT REQUEST"))}
        if not (m["ref"] and m["amt"] and m["who"]):
            self.note("grant_requests", why=f"{p.name}: request number, amount or charity not readable")
            continue
        charity, amt, ccy = m["who"][1].strip().title(), P.money(m["amt"][2]), m["amt"][1]
        reg = P.parse_date(m["reg"][1]) if m["reg"] else None
        months = None if reg is None else (self.today.year - reg.year) * 12 + self.today.month - reg.month - (self.today.day < reg.day)
        did = self.doc(p, "grant_request", p.stem, kind="charity", received=recv, date_=recv,
                       fields=[("request", m["ref"][1]), ("charity", charity), ("amount", None, amt, ccy), ("purpose", m["purpose"][1].strip() if m["purpose"] else None),
                               *([("charity_registered_on", reg.isoformat()), ("charity_age_months", None, months)] if reg else [])])
        rid = C._put(self, "grants", dict(grant_ref=m["ref"][1], charity_name=charity, charity_registered_on=reg, purpose=m["purpose"][1].strip() if m["purpose"] else None,
                                          legal_entity_id=self.ent["EG-HOLD"], amount=amt, currency=ccy, requested_on=recv, decided_on=None, paid_on=None, payment_reference=None, status="requested"),
                     **_src(self, "grant_requests", p, recv, did, m["ref"][1], 1))
        budget, paid, pledged = _grant_state(self)
        facts = [f"asks {ccy} {amt:,.0f}"]
        if budget is not None:
            facts.append(f"{budget - paid - pledged:,.0f} of the {budget:,.0f} budget is left")
        if months is not None:
            facts.append(f"the charity was registered {months} months ago")
        self.note("grant_requests", flag=f"{m['ref'][1]} {charity} " + "; ".join(facts))
        if budget is not None and amt > budget - paid - pledged:
            self.exception("grant_request_over_budget", f"Grant request {m['ref'][1]} is more than the budget left", "; ".join(facts) + ". The policy decides; nothing is paid.", recv, legal_entity_id=self.ent["EG-HOLD"])
        self.note("grant_requests", flag="the request names no entity; it is placed on Evergreen Holdings")
        self.note("grant_requests", files=1, rows=rid is not None)
    for p in self.files("grant_requests", "*.eml"):
        msg = email.message_from_bytes(p.read_bytes(), policy=email_policy.default)
        body = msg.get_body(preferencelist=("plain",))
        sent = P.parsedate(msg["Date"])
        fields = [("subject", msg["Subject"]), ("from", str(msg["From"])), ("to", str(msg["To"])), ("sent", sent.isoformat()), ("body", body.get_content().strip() if body else "")]
        for a in msg.iter_attachments():
            h = P.hashlib.sha256(a.get_payload(decode=True)).hexdigest()
            fields += [("attachment", a.get_filename()), *([("attachment_document_id", self.seen_hash[h])] if h in self.seen_hash else [("attachment_new", a.get_filename())])]
        self.doc(p, "email", str(msg["Subject"] or p.stem), kind="charity", received=sent.date(), date_=sent.date(), fields=fields)
        self.note("grant_requests", files=1, rows=1)


# ---------------------------------------------------------------------------------------------------------------- trust deed
def fam_trust_deed(self) -> None:
    for p in self.files("trust_deed"):
        t, recv = P.pdf_text(str(p)), self.arrival(p)
        sh = re.search(r"Beneficiaries and shares of distributable income:\s*(.+)", t)
        cap = re.search(r"distribute up to (\d+(?:\.\d+)?) percent", t)
        yr = re.search(r"Trust year:\s*(\d{1,2} \w+) to (\d{1,2} \w+)", t)
        succ = re.search(r"Successor trustee:\s*(.+)", t)
        shares = re.findall(r"([A-Z][\w' -]+?) (\d+(?:\.\d+)?) percent", sh[1]) if sh else []
        if not shares or not cap:
            self.note("trust_deed", why=f"{p.name}: the shares or the payout cap are not readable")
            continue
        fields = [("beneficiary_share", n.strip(), Decimal(v) / 100) for n, v in shares] + [("payout_cap_pct", None, Decimal(cap[1]))]
        if yr:
            fields += [("trust_year_start", f"{P.parse_date(yr[1] + ' 2000'):%m-%d}"), ("trust_year_end", f"{P.parse_date(yr[2] + ' 2000'):%m-%d}")]
        if succ:
            fields.append(("successor_trustee", succ[1].strip()))
        if re.search(r"Allowances paid to beneficiaries count as distributions", t):
            fields.append(("allowances_count_as_distributions", "yes"))
        self.doc(p, "trust_deed", p.stem, kind="trustees", received=recv, date_=recv, fields=fields, personal=True)  # restricted group (A44)
        total = sum(Decimal(v) for _, v in shares)
        if total != 100:
            self.note("trust_deed", flag=f"the shares add to {total} percent, not 100")
        self.note("trust_deed", files=1, rows=len(shares))


# ---------------------------------------------------------------------------------------------------------------- ownership register (A61)
def ownership_problems(rows, asat: date) -> list[tuple[str, str, str]]:
    """The rule checks on an ownership register, as at a date: (exception type, title, description) for each problem.
    rows: dicts with owner (name), owned (name), pct, valid_from, valid_to (None = in force). The holders of an entity must add to 100 percent (a gap is flagged),
    two periods of the same holder and entity must not overlap, and no entity may own itself through the chain (checked on every date a period starts)."""
    out = []
    live = lambda day: [r for r in rows if r["valid_from"] <= day and (r["valid_to"] is None or day <= r["valid_to"])]
    by = {}
    for r in live(asat):
        by[r["owned"]] = by.get(r["owned"], Decimal(0)) + Decimal(str(r["pct"]))
    for owned, tot in sorted(by.items()):
        if tot != 100:
            out.append(("ownership_gap", f"{owned}: the owners add to {tot:f} percent, not 100", f"As at {asat}, the register gives {tot:f} percent of {owned} to its owners; the other {100 - tot:f} percent has no owner on record."))
    seen = set()
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            k = (a["owner"], a["owned"])
            if k == (b["owner"], b["owned"]) and a["valid_from"] <= (b["valid_to"] or date.max) and b["valid_from"] <= (a["valid_to"] or date.max) and k not in seen:
                seen.add(k)
                out.append(("ownership_overlap", f"{a['owner']} in {a['owned']}: two periods overlap", f"The register holds two periods for {a['owner']} in {a['owned']} that share days ({a['valid_from']} to {a['valid_to'] or 'now'} and {b['valid_from']} to {b['valid_to'] or 'now'})."))
    for day in sorted({r["valid_from"] for r in rows} | {asat}):
        edges = {}
        for r in live(day):
            edges.setdefault(r["owner"], set()).add(r["owned"])
        for start in sorted(edges):
            stack, hit = [(start, [start])], None
            while stack and hit is None:
                node, path = stack.pop()
                for nxt in sorted(edges.get(node, ())):
                    if nxt == start:
                        hit = path + [start]
                        break
                    if nxt not in path:
                        stack.append((nxt, path + [nxt]))
            key = ("cycle", tuple(sorted(hit[:-1]))) if hit else None
            if hit and key not in seen:
                seen.add(key)
                out.append(("ownership_cycle", f"Circular ownership: {' > '.join(hit)}", f"On {day} {start} owns itself through {' > '.join(hit)}; a look-through would never end."))
    return out


def fam_ownership_register(self) -> None:
    """reference/ownership_register.csv -> entity_ownership (one row per period; standing data, written once) and a family_members row for a holder the allowance schedules do not name."""
    p = self.root / "reference" / "ownership_register.csv"
    if not p.is_file():
        return
    try:
        if self.con.execute("select count(*) from entity_ownership").fetchone()[0]:
            self.note("ownership_register", flag="the ownership register is already on record in this company; not written again")
            return
    except Exception:  # noqa: BLE001 - a warehouse built before the table existed: nothing is written
        self.note("ownership_register", why="this warehouse has no entity_ownership table yet")
        return
    recv = date(2026, 4, 1)
    did = self.doc(p, "ownership_register", p.stem, kind="reference", received=recv, date_=recv)
    members, rows, n = {}, [], 0
    for r in self.rows.get("family_members", []):
        members.setdefault(r["member_name"], r["id"])
    for i, r in enumerate(P.csv_rows(p), 2):
        kind, owner, owned = r["owner_kind"].strip(), r["owner"].strip(), C._entity_code(self, r["owned_entity"])
        code = C._entity_code(self, owner) if kind == "entity" else None
        try:
            pct, vf, vt = Decimal(r["ownership_pct"]), P.parse_date(r["valid_from"]), (P.parse_date(r["valid_to"]) if r["valid_to"].strip() else None)
        except Exception:  # noqa: BLE001 - a figure or date that cannot be read is not guessed
            self.note("ownership_register", flag=f"row {i}: percent or dates not readable; set aside")
            continue
        if owned is None or kind not in ("entity", "family_member") or (kind == "entity" and code is None) or not 0 < pct <= 100:
            self.note("ownership_register", flag=f"row {i}: {owner!r} in {r['owned_entity']!r} is not an owner of an entity of the office; set aside")
            continue
        sr = self.record("reference", p, recv, rtype="row", external=f"{owner}>{owned}:{vf}", row=i)
        if kind == "family_member" and owner not in members:
            members[owner] = self.add("family_members", source_record_id=sr, source_document_id=did, source_page=1, received_at=P.stamp(recv), recorded_at=P.stamp(recv), member_name=owner,
                                      relationship="principal" if owner == "Mei Chen" else "other", active_from=vf)
        self.add("entity_ownership", source_record_id=sr, source_document_id=did, source_page=1, received_at=P.stamp(recv), recorded_at=P.stamp(recv), owner_kind=kind,
                 owner_entity_id=self.ent[code] if code else None, owner_family_member_id=members[owner] if kind == "family_member" else None, owned_entity_id=self.ent[owned],
                 ownership_pct=pct, valid_from=vf, valid_to=vt)
        rows.append(dict(owner=owner if kind == "family_member" else self.md["entities"][code], owned=self.md["entities"][owned], pct=pct, valid_from=vf, valid_to=vt))
        n += 1
    for etype, title, text in ownership_problems(rows, self.today):
        self.note("ownership_register", flag=title)
        self.exception(etype, title, text, self.today)
    self.note("ownership_register", files=1, rows=n)


# ---------------------------------------------------------------------------------------------------------------- estate planning
def fam_estate_planning(self) -> None:
    for p in self.files("estate_planning"):
        t, recv = P.pdf_text(str(p)), self.arrival(p)
        ex, rate = re.search(r"Exemption: USD ([\d,.]+)", t), re.search(r"Rate above the exemption: ([\d.]+) percent", t)
        term, basis = re.search(r"Payable within (\d+) months", t), re.search(r"(Assets are valued at .+?)\.?$", t, re.M)
        if not (ex and rate):
            self.note("estate_planning", why=f"{p.name}: exemption or rate not readable")
            continue
        exemption, r = P.money(ex[1]), Decimal(rate[1]) / 100
        self.doc(p, "transfer_tax_memo", p.stem, kind="adviser", received=recv, date_=recv,
                 fields=[("estate_tax_exemption", None, exemption, "USD"), ("estate_tax_rate", None, r), *([("payment_term_months", None, Decimal(term[1]))] if term else []),
                         *([("valuation_basis", basis[1])] if basis else [])])
        rule_proposed(self, "estate_tax_exemption", f"Transfer tax exemption {exemption:,.0f} USD (from {p.name}, not yet signed)", {"amount": float(exemption), "currency": "USD", "value": float(exemption)}, "Helen Foo")
        rule_proposed(self, "estate_tax_rate", f"Transfer tax rate {r:.0%} above the exemption (from {p.name}, not yet signed)", {"rate": float(r), "value": float(r)}, "Helen Foo")
        self.note("estate_planning", files=1, rows=1)


def install(module) -> None:
    """Register the six kinds, their tables for the shared writer, and the step `family`. Called at the end of v3_pack_readers."""
    global P
    P = module
    C.SPEC.update(SPEC)
    C.SUPERSEDES.update(SUPERSEDES)
    for fn in (fam_tax_calendar, fam_tax_notices, fam_grant_ledger, fam_grant_requests, fam_trust_deed, fam_estate_planning, fam_ownership_register):
        setattr(module.Office, fn.__name__, fn)

    def family(self) -> None:  # named: the step's name is how STEP_KINDS finds its kinds
        for fn in (fam_tax_calendar, fam_tax_notices, fam_grant_ledger, fam_grant_requests, fam_trust_deed, fam_estate_planning, fam_ownership_register):
            fn(self)
    module.Office.family = family
    module.KINDS.update(KINDS)
    module.STEP_KINDS["family"] = list(KINDS)
    module.FLUSH_ORDER[:] = [*module.FLUSH_ORDER, *(t for t in ("tax_obligations", "grants", "entity_ownership") if t not in module.FLUSH_ORDER)]
    plain = module.kind_of

    def kind_of_family(name: str, data: bytes):
        return plain(name, data) or kind_of(name, data)
    kind_of_family.__doc__ = plain.__doc__
    module.kind_of = kind_of_family
