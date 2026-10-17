"""Pack readers of the invest group (cards 57, 69, 77, 78, 79): fund holdings, deal pipeline, fund documents (redemption terms), market data (second price source)
and the proposed target allocation. v3_pack_readers calls `install(module)` once; the readers are methods of its Office and run as the step `invest` (after `family`).

Where the rows go (docs/v3/ASSUMPTIONS.md A43, A46):
  fund_holdings   -> fund_holdings (instrument_id the fund, one row per company and fund; a newer list supersedes the row of the same company and fund)
  deal_pipeline   -> deal_pipeline (one row per deal and stage; a new stage supersedes, also the 'screening' row that the fund teaser made), the teasers as documents
                     fund_teaser, the mail as a document with the field first_close
  fund_documents  -> one document per fund (instrument = the fund) with extracted_fields redemption_frequency, dealing_day, notice_days, lockup_end_date (ISO),
                     lockup_months, payment_lag_days, holdback_pct (a percent: 5), subscribed_on (ISO)
  market_data     -> market_observations, observation_type price_second_source, series_key the ticker, one per security and day; the price tolerance is not here
  target_allocation -> PROPOSED rules allocation_<asset_class> with {"portfolio", "asset_class", "target_pct", "value"}; a document with the fields
  manager_news    -> one document manager_news per mail with fields counterparty (the manager), subject, sent, body and team_change (A43; card 53)
Synthetic data only."""
from __future__ import annotations

import csv
import email
import io
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal
from email import policy as email_policy

from sh_platform.v1 import v3_pack_readers_controls as C
from sh_platform.v1 import v3_pack_readers_family as F

P = None  # the pack readers module, set by install()
KINDS = {
    "fund_holdings": ("fund look-through holdings", "data.read-fund-holdings", "fund holdings"),
    "deal_pipeline": ("deal pipeline", "data.read-deal-pipeline", "deal pipeline, fund teasers and documents"),
    "fund_documents": ("fund redemption terms", "data.read-redemption-terms", "documents and fields"),
    "market_data": ("second-source prices", "data.read-second-source-prices", "market observations"),
    "target_allocation": ("target allocation", "data.read-target-allocation", "allocation rules (proposed)"),
    "manager_news": ("manager news mails", "data.read-manager-news", "documents and fields"),
}
SPEC = {
    "fund_holdings": (("instrument_id", "holding_name"), ("sector", "weight_pct", "as_at")),
    "deal_pipeline": (("deal_name",), ("manager_name", "strategy", "asset_class", "target_commitment", "currency", "stage", "stage_on", "owner_user_id")),
}
SUPERSEDES = {"fund_holdings": "supersedes_fund_holding_id", "deal_pipeline": "supersedes_deal_id"}
PRICE = "price_second_source"
LOOKS_STUCK = 60  # days: only to word a flag; the stuck-deal limit is a rule of the office and is not signed


def kind_of(name: str, data: bytes):
    low = name.lower()
    try:
        if low.endswith(".csv"):
            cols = {c.strip().lower() for c in next(csv.reader(data[:4000].decode("utf-8-sig", errors="replace").splitlines()[:1]), [])}
            return ("deal_pipeline", name) if {"deal", "name", "sponsor", "stage", "stage_entered"} <= cols else ("market_data", name) if {"date", "security_id", "ticker", "price", "source"} <= cols else None
        if low.endswith((".xlsx", ".xlsm")):
            wb = P.openpyxl.load_workbook(io.BytesIO(data), read_only=True)
            try:
                for sheet, need, kind in (("Holdings", {"fund key", "company"}, "fund_holdings"), ("Targets", {"portfolio", "asset class"}, "target_allocation")):
                    if sheet in wb.sheetnames:
                        first = {str(c).strip().lower() for c in next(wb[sheet].iter_rows(values_only=True), ())}
                        if need <= first:
                            return kind, name
            finally:
                wb.close()
        if low.endswith(".pdf"):
            up = P._pdf_head(data).upper()[:400]
            if "REDEMPTION TERMS" in up:
                return "fund_documents", name
            if low.startswith("teaser_dl-") and "FUND TEASER" in up:  # the layout of a deal's teaser is read with the pipeline, not as a prospect
                return "deal_pipeline", name
    except Exception:  # noqa: BLE001 - a file that cannot be read here is not one of ours; the generic path names the problem
        return None
    return None


def _month_diff(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + b.month - a.month - (b.day < a.day)


# ---------------------------------------------------------------------------------------------------------------- fund holdings
def inv_fund_holdings(self) -> None:
    for p in self.files("fund_holdings"):
        recv, n = self.arrival(p), 0
        rows = P.dicts(P.sheet_rows(p))
        asat = None
        for r in rows:
            m = re.search(r"as at (\d{1,2} \w+ \d{4})", str(r.get("Source") or ""))
            asat = P.parse_date(m[1]) if m else asat
        asat = asat or recv
        did = self.doc(p, "fund_holdings_list", p.stem, kind="manager", received=recv, date_=asat, valuation=asat, fields=[("as_at", asat.isoformat())])
        weights, seen, funds = defaultdict(Decimal), set(), defaultdict(set)
        for i, r in enumerate(rows, 2):
            key, company = str(r["Fund key"] or "").strip(), str(r["Company"] or "").strip()
            iid = self.fund_key.get(key)
            if iid is None or not company or r["Weight (% of fund)"] is None:
                self.note("fund_holdings", flag=f"row {i}: fund {key!r} company {company!r} is not a fund of the office or has no weight; set aside")
                continue
            if r.get("Fund") and self.fund_info[key]["name"] != r["Fund"]:
                self.note("fund_holdings", flag=f"row {i}: fund {key} is called {r['Fund']!r} here and {self.fund_info[key]['name']!r} in the office's list")
            if (key, company) in seen:
                self.note("fund_holdings", flag=f"fund {key} {company}: listed twice; counted once")
                continue
            seen.add((key, company))
            w = Decimal(str(r["Weight (% of fund)"]))
            weights[key] += w
            if company.lower() != "other holdings":
                funds[company].add(key)
            rid = C._put(self, "fund_holdings", dict(instrument_id=iid, holding_name=company, sector=r.get("Sector"), weight_pct=w, as_at=asat),
                         source_record_id=self.record("fund_holdings", p, recv, rtype="row", external=f"{key}:{company}", row=i), source_document_id=did, source_page=1,
                         received_at=P.stamp(recv), recorded_at=P.stamp(recv))
            n += rid is not None
        for key, w in weights.items():
            if w != 100:
                self.note("fund_holdings", flag=f"fund {key}: the weights add to {w}, not 100")
        many = sorted(c for c, k in funds.items() if len(k) > 1)
        if many:
            self.note("fund_holdings", flag="the same company sits in several funds: " + "; ".join(f"{c} ({', '.join(sorted(funds[c]))})" for c in many))
        self.note("fund_holdings", flag="'Other holdings' is the manager's remainder, not a company; kept as written")
        self.note("fund_holdings", files=1, rows=n)


# ---------------------------------------------------------------------------------------------------------------- deal pipeline
def inv_deal_pipeline(self) -> None:
    teasers = {}
    for p in self.files("deal_pipeline", "*.pdf"):
        t, recv = P.pdf_text(str(p)), self.arrival(p)
        nm, st, mn = (re.search(x, t, re.I | re.M) for x in (r"^(.+?) - fund teaser", r"Strategy:\s*(.+)", r"Minimum commitment: USD ([\d,.]+)"))
        mgr = re.sub(r"\s*\(synthetic\)", "", t.splitlines()[0], flags=re.I).strip().title()
        if not nm:
            self.note("deal_pipeline", why=f"{p.name}: the fund name is not readable")
            continue
        did = self.doc(p, "fund_teaser", p.stem, kind="manager", received=recv, date_=recv,
                       fields=[("fund", nm[1].strip()), ("manager", mgr), *([("strategy", st[1].strip())] if st else []), *([("minimum_commitment", None, P.money(mn[1]), "USD")] if mn else [])])
        teasers[nm[1].strip()] = (did, st[1].strip() if st else None, P.money(mn[1]) if mn else None)
        self.note("deal_pipeline", files=1, rows=1)
    for p in self.files("deal_pipeline", "*.csv"):
        recv, n, seen = self.arrival(p), 0, set()
        for i, r in enumerate(P.csv_rows(p), 2):
            name, ref = (r.get("name") or "").strip(), (r.get("deal") or "").strip()
            try:
                since, ticket = P.parse_date(r["stage_entered"], hint=recv), P.money(r["ticket_usd"])
            except Exception:  # noqa: BLE001 - a date or an amount that cannot be read is not guessed
                self.note("deal_pipeline", flag=f"{ref or i}: stage date or ticket not readable; set aside")
                continue
            if not name or not r.get("stage", "").strip() or name in seen:
                self.note("deal_pipeline", flag=f"row {i}: {ref!r} {name!r} has no name or stage, or is listed twice; set aside")
                continue
            seen.add(name)
            tdoc, strategy, minimum = teasers.get(name, (None, None, None))
            cache = C._latest(self, "deal_pipeline")
            for k in [k for k in cache if k[0].lower() == name.lower() and k[0] != name]:  # the prospect reader spells a name in title case: the same deal
                cache[(name,)] = cache.pop(k)
            prior = next((x for x in reversed(self.rows.get("deal_pipeline", [])) if x["deal_name"].lower() == name.lower()), None)  # the 'screening' row a prospect teaser made in this run
            if prior and (name,) not in cache:
                cache[(name,)] = (prior["id"], tuple(C._n(prior.get(c)) for c in SPEC["deal_pipeline"][1]))
            strategy = strategy or (prior or {}).get("strategy")
            rid = C._put(self, "deal_pipeline", dict(deal_name=name, manager_name=(r.get("sponsor") or "").strip() or None, strategy=strategy, asset_class=(r.get("asset_class") or "").strip() or None,
                                                     target_commitment=ticket, currency="USD", stage=r["stage"].strip(), stage_on=since, owner_user_id=self.person((r.get("owner") or "").strip() or None)),
                         source_record_id=self.record("deal_pipeline", p, recv, rtype="deal", external=ref, row=i), source_document_id=tdoc or (prior or {}).get("source_document_id"),
                         source_page=1, received_at=P.stamp(recv), recorded_at=P.stamp(recv))
            n += rid is not None
            if minimum is not None and minimum != ticket:
                self.note("deal_pipeline", flag=f"{name}: the ticket {ticket:,.0f} differs from the teaser's minimum commitment {minimum:,.0f}")
            if (self.today - since).days > LOOKS_STUCK:
                self.note("deal_pipeline", flag=f"{name} has been in {r['stage'].strip()} since {since}: {(self.today - since).days} days (the stuck-deal limit is not signed)")
        for name in teasers:
            if name not in seen:
                self.note("deal_pipeline", flag=f"teaser of {name}: no such deal in {p.name}")
        self.note("deal_pipeline", files=1, rows=n)
    for p in self.files("deal_pipeline", "*.eml"):
        msg = email.message_from_bytes(p.read_bytes(), policy=email_policy.default)
        body = msg.get_body(preferencelist=("plain",))
        text, sent = (body.get_content().strip() if body else ""), P.parsedate(msg["Date"])
        fields = [("subject", msg["Subject"]), ("from", str(msg["From"])), ("to", str(msg["To"])), ("sent", sent.isoformat()), ("body", text)]
        m = re.search(r"first close of (.+?) is on (\d{1,2} \w+)", text)
        if m:
            close = P.parse_date(f"{m[2]} {sent.year}")
            fields += [("deal", m[1].strip()), ("first_close", close.isoformat())]
        self.doc(p, "email", str(msg["Subject"] or p.stem), kind="manager", received=sent.date(), date_=sent.date(), fields=fields)
        self.note("deal_pipeline", files=1, rows=1)


# ---------------------------------------------------------------------------------------------------------------- redemption terms
def inv_fund_documents(self) -> None:
    for p in self.files("fund_documents"):
        t, recv = P.pdf_text(str(p)), self.arrival(p)
        nm = re.search(r"^(.+?) - redemption terms", t, re.M)
        iid = self.by_name.get(nm[1].strip()) if nm else None
        dealing, notice, pay = (re.search(x, t) for x in (r"Dealing:\s*(monthly|quarterly|weekly|annual\w*)(?:, (.+))?", r"Notice:\s*(\d+) calendar days", r"Payment:\s*(\d+) days after the dealing date(?:, (\d+(?:\.\d+)?) percent held back)?"))
        lock = re.search(r"Lock-up:\s*(?:ended|no redemption before) (\d{1,2} \w+ \d{4})", t)
        sub = re.search(r"Subscribed:\s*(\d{1,2} \w+ \d{4})", t)
        if iid is None or not (dealing and notice and pay):
            self.note("fund_documents", why=f"{p.name}: fund, dealing, notice or payment terms not readable")
            continue
        end = P.parse_date(lock[1]) if lock else None
        subscribed = P.parse_date(sub[1]) if sub else None
        fields = [("redemption_frequency", dealing[1]), ("dealing_day", (dealing[2] or "").strip() or None), ("notice_days", None, Decimal(notice[1])),
                  ("payment_lag_days", None, Decimal(pay[1])), ("holdback_pct", None, Decimal(pay[2] or 0))]
        if end:
            fields.append(("lockup_end_date", end.isoformat()))
        if end and subscribed:
            fields += [("subscribed_on", subscribed.isoformat()), ("lockup_months", None, Decimal(_month_diff(subscribed, end)))]
        self.doc(p, "redemption_terms", p.stem, kind="manager", received=recv, date_=recv, instrument=iid, fields=fields)
        if end and end > self.today:
            self.note("fund_documents", flag=f"{nm[1].strip()}: locked up until {end}; no redemption before then")
        if not lock:
            self.note("fund_documents", flag=f"{nm[1].strip()}: no lock-up date in the terms")
        self.note("fund_documents", files=1, rows=len(fields))


# ---------------------------------------------------------------------------------------------------------------- second-source prices
def inv_market_data(self) -> None:
    have = {}
    try:
        for i, ins, d, v in self.con.execute(f"select id, instrument_id, cast(observed_at as date), value from market_observations o where observation_type = '{PRICE}' "
                                             "and not exists (select 1 from market_observations x where x.supersedes_observation_id = o.id)").fetchall():
            have[(ins, d)] = (i, v)
    except Exception:  # noqa: BLE001 - a warehouse with no observations yet
        pass
    for p in self.files("market_data"):
        recv, n = self.arrival(p), 0
        sr = self.record("market_data", p, recv)
        for i, r in enumerate(P.csv_rows(p), 2):
            sec, iid = (r.get("security_id") or "").strip(), self.inst.get((r.get("security_id") or "").strip())
            try:
                day, price = P.parse_date(r["date"], hint=recv), Decimal(str(r["price"]).strip())
            except Exception:  # noqa: BLE001 - a date or a price that cannot be read is not guessed
                self.note("market_data", flag=f"row {i}: {sec} date or price not readable; set aside")
                continue
            if iid is None:
                self.note("market_data", flag=f"row {i}: security {sec!r} is not one the office holds; set aside")
                continue
            old = have.get((iid, day))
            if old and Decimal(str(old[1])) == price:
                continue
            if old:
                self.note("market_data", flag=f"{sec} {day}: the second source now says {price}, was {old[1]}; the new price supersedes")
            oid = self.add("market_observations", source_record_id=sr, instrument_id=iid, series_key=(r.get("ticker") or sec).strip(), observation_type=PRICE, observed_at=P.stamp(day),
                           received_at=P.stamp(max(recv, day), 18), recorded_at=P.stamp(max(recv, day), 18), value=price, supersedes_observation_id=old[0] if old else None)
            have[(iid, day)] = (oid, price)
            n += 1
        self.note("market_data", files=1, rows=n)


# ---------------------------------------------------------------------------------------------------------------- target allocation
def inv_target_allocation(self) -> None:
    for p in self.files("target_allocation"):
        recv, n, total = self.arrival(p), 0, Decimal(0)
        rows = P.dicts(P.sheet_rows(p))
        fields = []
        for i, r in enumerate(rows, 2):
            cls, pct = F.slug(r["Asset class"] or ""), r["Target % of the book"]
            if not cls or pct is None:
                self.note("target_allocation", flag=f"row {i}: asset class or target missing; set aside")
                continue
            pct, status = Decimal(str(pct)), str(r.get("Status") or "")
            total += pct
            fields.append((f"allocation_{cls}", r["Portfolio"], pct))
            F.rule_proposed(self, f"allocation_{cls}", f"{r['Portfolio']}: {cls.replace('_', ' ')} {pct}% of the book ({status or 'from ' + p.name}; not signed)",
                            {"portfolio": r["Portfolio"], "asset_class": cls, "target_pct": float(pct), "value": float(pct)}, "Raj Patel")
            if re.search(r"\bsigned\b", status) and not re.search(r"not (yet )?signed", status):
                self.note("target_allocation", flag=f"{cls}: the file says '{status}'; it is still written as proposed until it is signed here")
            n += 1
        self.doc(p, "target_allocation", p.stem, kind="committee", received=recv, date_=recv, fields=fields)
        if total != 100:
            self.note("target_allocation", flag=f"the targets add to {total} percent, not 100")
        self.note("target_allocation", flag="the targets are proposals of the committee, not signed: a suggestion only")
        self.note("target_allocation", files=1, rows=n)


# ---------------------------------------------------------------------------------------------------------------- manager news
def inv_manager_news(self) -> None:
    """A mail from a manager to its investors (manager_news/*.eml): who it is from and the team change it announces. The manager is the part of the
    subject before ':' ("Saltmarsh Real Assets: Head of Infrastructure resigns"), else the last line of the mail; the change is the subject after it."""
    for p in self.files("manager_news", "*.eml"):
        msg = email.message_from_bytes(p.read_bytes(), policy=email_policy.default)
        body = msg.get_body(preferencelist=("plain",))
        text, sent, subject = (body.get_content().strip() if body else ""), P.parsedate(msg["Date"]), str(msg["Subject"] or "").strip()
        who, _, change = subject.partition(":")
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        manager = who.strip() if change else (lines[-1] if lines else None)
        if not manager:
            self.note("manager_news", why=f"{p.name}: the manager is not readable")
            continue
        fields = [("counterparty", manager), ("subject", subject), ("from", str(msg["From"])), ("sent", sent.isoformat()), ("body", text),
                  ("team_change", (change or subject).strip())]
        self.doc(p, "manager_news", subject or p.stem, kind="manager", received=sent.date(), date_=sent.date(), fields=fields)
        self.note("manager_news", files=1, rows=1)


def install(module) -> None:
    """Register the five kinds and the step `invest`. Called at the end of v3_pack_readers, after v3_pack_readers_family."""
    global P
    P = module
    C.SPEC.update(SPEC)
    C.SUPERSEDES.update(SUPERSEDES)
    fns = (inv_fund_holdings, inv_deal_pipeline, inv_fund_documents, inv_market_data, inv_target_allocation, inv_manager_news)
    for fn in fns:
        setattr(module.Office, fn.__name__, fn)

    def invest(self) -> None:  # named: the step's name is how STEP_KINDS finds its kinds
        for fn in fns:
            fn(self)
    module.Office.invest = invest
    module.KINDS.update(KINDS)
    module.STEP_KINDS["invest"] = list(KINDS)
    module.FLUSH_ORDER[:] = [*module.FLUSH_ORDER, *(t for t in ("fund_holdings",) if t not in module.FLUSH_ORDER)]
    plain = module.kind_of

    def kind_of_invest(name: str, data: bytes):
        return kind_of(name, data) or plain(name, data)  # first: a deal's teaser has the layout of a prospect's but belongs to the pipeline
    kind_of_invest.__doc__ = plain.__doc__
    module.kind_of = kind_of_invest
