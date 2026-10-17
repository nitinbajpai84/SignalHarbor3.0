"""Pack readers of the treasury group (cards 51 to 100): payment schedule, income calendar, corporate action notices, settlement report, tax lot register
and the managers' distribution outlooks. v3_pack_readers calls `install(module)` once; the readers are methods of its Office and run as the step `treasury`
after the invoices have written their expected payments (links), so a scheduled payment that an invoice already made is the same row, not a second one.

Where the rows go (docs/v3/ASSUMPTIONS.md A34, A35, A40, A43, A45):
  payment_schedule  -> cash_movements, type payment, confirmation_status expected, payment_stage expected/approved/scheduled/held, payee_name, reference, amount negative
  income_calendar   -> cash_movements, type dividend or coupon, expected, due_date the pay date, amount positive (the office's USD figure)
  corporate_actions -> corporate_actions (one row per notice, a re-issued notice supersedes) and a document with its fields (quantity_held, expected_cash ...); no cash
  settlement_status -> transactions: a failed trade is status failed with counterparty_name and status_reason; a trade the desk has no row for is added
  tax_lots          -> tax_lots (a newer register supersedes the lot of the same reference)
  realised_lots     -> one document per report with extracted_fields per lot sold: realised_gain, proceeds, cost (value_text the lot and the trade, value_numeric USD)
  manager_outlook   -> one document per fund with extracted_fields projected_payout_rate, one per quarter (value_text the quarter end, value_numeric a fraction)
Synthetic data only."""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

PAYMENT_STAGES = {"expected", "approved", "scheduled", "held", "released"}
KINDS = {
    "payment_schedule": ("treasury payment schedule", "data.read-payment-schedule", "expected payments with their stage"),
    "income_calendar": ("income calendar", "data.read-income-calendar", "expected dividends and coupons"),
    "corporate_actions": ("corporate action notice", "data.read-corporate-action", "corporate actions and documents"),
    "settlement_status": ("settlement report", "data.read-settlement-status", "transactions"),
    "tax_lots": ("tax lot register", "data.read-tax-lots", "tax lots"),
    "realised_lots": ("realised gains report", "data.read-tax-lots", "documents and realised gains per lot"),
    "manager_outlook": ("manager distribution outlook", "data.read-manager-outlook", "documents and projected payout rates"),
}


def install(M) -> None:
    """Register the seven kinds in the pack's tables and give Office the step `treasury`."""
    M.CSV_KINDS += [("payment_schedule", {"ref", "payee", "due_date", "basis"}), ("income_calendar", {"pay_date", "security_id", "event", "expected_cash_usd"}),
                    ("settlement_status", {"trade_ref", "settle_date", "cash_booked"}), ("realised_lots", {"trade_ref", "lot", "proceeds", "realised_gain"})]
    M.XLSX_KINDS.append(({"Lots"}, "tax_lots"))
    M.PDF_KINDS += [("CORPORATE ACTION NOTICE", "corporate_actions"), ("DISTRIBUTION OUTLOOK FOR INVESTORS", "manager_outlook")]
    M.KINDS.update(KINDS)
    M.STEP_KINDS["treasury"] = list(KINDS)
    M.FLUSH_ORDER += [t for t in ("corporate_actions", "tax_lots") if t not in M.FLUSH_ORDER]

    def treasury(self) -> None:  # named: the step's name is how STEP_KINDS finds its kinds
        for fn in (payment_schedule, income_calendar, corporate_actions, settlement_status, tax_lots, realised_lots, manager_outlook):
            fn(M, self)
    M.Office.treasury = treasury


def _prior(o, table: str, where: str, args: list):
    """The id of the row a new one replaces: the last of the same key already staged in this run, else on record."""
    key = {"corporate_actions": "supersedes_corporate_action_id", "tax_lots": "supersedes_tax_lot_id"}[table]
    mine = [r for r in o.rows.get(table, []) if all(r.get(c) == v for c, v in zip(re.findall(r"(\w+) = \?", where), args))]
    if mine:
        return mine[-1]["id"]
    try:
        r = o.con.execute(f"select id from {table} where {where} and id not in (select {key} from {table} where {key} is not null) order by recorded_at desc limit 1", args).fetchone()
    except Exception:  # noqa: BLE001 - a warehouse without the table has nothing on record
        return None
    return r[0] if r else None


def _num(x) -> Decimal | None:
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(x if x is not None else ""))  # the first number written, 'USD 31.50 per share' -> 31.50
    return Decimal(m[0].replace(",", "")) if m else None


# ---------------------------------------------------------------------------------------------------------------- payment schedule
def payment_schedule(M, o) -> None:
    seen: set[str] = set()
    for p in o.files("payment_schedule"):
        recv, n = o.arrival(p), 0
        for i, r in enumerate(M.csv_rows(p), 2):
            ref, ent = (r.get("ref") or "").strip(), (r.get("entity") or "").strip()
            if not ref or ent not in o.cashport:
                o.note("payment_schedule", flag=f"row {i}: reference {ref!r} entity {ent!r} is not an entity of the office; set aside")
                o.exception("payment_schedule_row", f"Payment schedule row {i} not placed", f"Entity {ent!r} is unknown; the line is left out.", recv)
                continue
            if ref in seen:
                o.note("payment_schedule", flag=f"{ref}: listed twice; counted once")
                continue
            seen.add(ref)
            try:
                amount, due = abs(M.money(r["amount"])), M.parse_date(r["due_date"], hint=recv)
            except Exception:  # noqa: BLE001 - an amount or date that cannot be read is not guessed
                o.note("payment_schedule", flag=f"{ref}: amount or due date not readable; set aside")
                continue
            stage = (r.get("status") or "").strip().lower()
            if stage not in PAYMENT_STAGES:
                o.note("payment_schedule", flag=f"{ref}: stage {stage!r} is not one of the five; read as expected")
                stage = "expected"
            ccy, payee = (r.get("currency") or "USD").strip(), (r.get("payee") or "").strip()
            sr = o.record("payment_schedule", p, recv, rtype="schedule_line", external=ref, row=i)
            twin = next((m for m in o.rows.get("cash_movements", []) if m.get("confirmation_status") == "expected" and m.get("movement_type") == "payment" and m.get("currency") == ccy
                         and m.get("portfolio_id") == o.cashport[ent] and -m["amount"] == amount and m.get("due_date") == due and not m.get("reference")), None)
            if twin:  # an invoice already made this expected payment: the schedule says where it stands
                twin.update(payment_stage=stage, payee_name=payee, reference=ref)
                o.note("payment_schedule", flag=f"{ref}: the invoice's expected payment is the same payment; it takes the stage {stage}")
            else:
                o.add("cash_movements", source_record_id=sr, portfolio_id=o.cashport[ent], movement_type="payment", effective_date=o.today, due_date=due, amount=-amount, currency=ccy,
                      confirmation_status="expected", payment_stage=stage, payee_name=payee, reference=ref, received_at=M.stamp(recv), recorded_at=M.stamp(recv))
            if stage == "held":
                o.note("payment_schedule", flag=f"{ref}: held ({(r.get('basis') or '').strip()})")
            n += 1
        o.note("payment_schedule", files=1, rows=n)


# ---------------------------------------------------------------------------------------------------------------- income calendar
def income_calendar(M, o) -> None:
    for p in o.files("income_calendar"):
        recv, n, seen = o.arrival(p), 0, set()
        for i, r in enumerate(M.csv_rows(p), 2):
            sec, event = (r.get("security_id") or "").strip(), (r.get("event") or "").strip().lower()
            iid = o.inst.get(sec)
            if iid is None or event not in {"dividend", "coupon"}:
                o.note("income_calendar", flag=f"row {i}: {sec or 'no security'} {event or 'no event'} is not a security or an event the office holds; set aside")
                continue
            pay = M.parse_date(r["pay_date"], hint=recv)
            key = (sec, event, pay)
            if key in seen:
                o.note("income_calendar", flag=f"{sec} {event} {pay}: listed twice; counted once")
                continue
            seen.add(key)
            if pay < o.today:
                o.note("income_calendar", flag=f"{sec} {event} {pay}: already past; the custodian's cash is the fact, not the calendar")
                continue
            qty, cash = _num(r.get("quantity")), _num(r.get("expected_cash_usd"))
            unit = _num(r.get("per_share")) if event == "dividend" else (_num(r.get("rate_per_year")) or Decimal(0)) / 2
            calc = None if qty is None or unit is None else (qty * unit).quantize(Decimal("0.01"))
            if cash is None:
                cash = calc
            elif calc is not None and abs(calc - cash) > Decimal("0.05"):
                o.note("income_calendar", flag=f"{sec} {event} {pay}: calendar cash {cash} differs from {calc} (rate times holding); the calendar figure is kept")
            if cash is None:
                o.note("income_calendar", flag=f"row {i}: {sec} has no cash and no rate; set aside")
                continue
            sr = o.record("income_calendar", p, recv, rtype="calendar_line", external=f"{sec}:{event}:{pay}", row=i)
            o.add("cash_movements", source_record_id=sr, portfolio_id=o.port["EG-LIQUID"], instrument_id=iid, movement_type=event, effective_date=o.today, due_date=pay, amount=cash, currency="USD",
                  confirmation_status="expected", notice_kind=event, received_at=M.stamp(recv), recorded_at=M.stamp(recv))
            n += 1
        o.note("income_calendar", files=1, rows=n)


# ---------------------------------------------------------------------------------------------------------------- corporate actions
def corporate_actions(M, o) -> None:
    for p in o.files("corporate_actions"):
        t = M.pdf_text(str(p))
        recv = o.arrival(p)
        sec = re.search(r"Security:.*\((SEC-[A-Z0-9]+)\)\s*$", t, re.M)
        ev = re.search(r"Event:\s*(.+)", t)
        iid = o.inst.get(sec[1]) if sec else None
        if not (sec and ev and iid):
            o.note("corporate_actions", why=f"{p.name}: security or event not readable")
            continue

        def get(label):
            m = re.search(label + r":?\s*([^\n]+)", t)
            return m[1].strip() if m else None
        low = ev[1].lower()
        kind = "tender_offer" if "tender" in low else "coupon" if "coupon" in low else "dividend" if "dividend" in low else "other"
        election = "no election" not in low and ("instruction" in low or "voluntary" in low)
        ex = get("Ex-date")
        pay = get("Payment date") or get(r"Payment date if accepted")
        respond = re.search(r"Respond by:\s*(\d{1,2} \w+ \d{4})", t)
        if kind == "tender_offer":
            pay = re.search(r"Payment date if accepted:\s*(\d{1,2} \w+ \d{4})", t)
            pay = pay[1] if pay else None
        qty = _num((get("Your holding") or "").replace(",", ""))
        cash = _num(get("Expected cash"))
        rate = _num(get("Dividend per share")) if kind == "dividend" else (_num(get("Coupon rate per year")) or Decimal(0)) / 100 if kind == "coupon" else _num(get(r"Offer price"))
        deadline = M.parse_date(respond[1]) if respond else None
        status = ("election_open" if deadline >= o.today else "election_missed") if election and deadline else "announced"
        did = o.doc(p, "corporate_action_notice", p.stem, kind="custodian", received=recv, date_=recv, instrument=iid,
                    fields=[f for f in [("event", kind), ("quantity_held", None, qty), ("expected_cash", None, cash, "USD") if cash is not None else None,
                                        ("default_if_silent", "no tender") if "silence means no tender" in t.lower() else None] if f])
        pay_d = M.parse_date(pay) if pay else None
        kw = dict(instrument_id=iid, action_type=kind, custodian_ref=p.stem, announced_on=recv, ex_date=M.parse_date(ex) if ex else None, pay_date=pay_d)
        where = "instrument_id = ? and action_type = ? and pay_date = ?"
        prior = _prior(o, "corporate_actions", where, [iid, kind, pay_d]) if pay_d else None
        o.add("corporate_actions", source_record_id=o.doc_record(did), source_document_id=did, source_page=1, received_at=M.stamp(recv), recorded_at=M.stamp(recv),
              supersedes_corporate_action_id=prior, rate_per_unit=rate, currency="USD", election_required=election, election_deadline=deadline, status=status, **kw)
        if prior:
            o.note("corporate_actions", flag=f"{p.name}: the same event was noticed before; this notice supersedes it")
        if election:
            o.note("corporate_actions", flag=f"{p.name}: a decision is due by {deadline}; no cash comes unless the office elects, silence means no tender")
            o.exception("corporate_action_election", f"Election needed: {kind.replace('_', ' ')} {sec[1]}", f"Respond by {deadline}; silence means no tender.", recv, instrument_id=iid)
        if cash is not None and qty is not None and rate is not None and kind == "dividend" and abs(qty * rate - cash) > Decimal("0.05"):
            o.note("corporate_actions", flag=f"{p.name}: expected cash {cash} differs from {qty * rate} (rate times holding)")
        o.note("corporate_actions", files=1, rows=1)


# ---------------------------------------------------------------------------------------------------------------- settlement report
def settlement_status(M, o) -> None:
    for p in o.files("settlement_status"):
        recv, n = o.arrival(p), 0
        rows = M.csv_rows(p)
        refs = [r["trade_ref"] for r in rows]
        have = {r["external_trade_id"]: r for r in o.rows.get("transactions", []) if r.get("external_trade_id")}
        try:
            for tid, st, sid in o.con.execute(f"select external_trade_id, status, id from transactions where external_trade_id in ({', '.join('?' * len(refs))})", refs).fetchall():
                have.setdefault(tid, {"status": st, "id": sid})
        except Exception:  # noqa: BLE001
            pass
        for i, r in enumerate(rows, 2):
            ref, iid = r["trade_ref"].strip(), o.inst.get(r["security_id"].strip())
            if iid is None:
                o.note("settlement_status", flag=f"{ref}: security {r['security_id']!r} unknown; set aside")
                continue
            status = r["status"].strip().lower()
            old = have.get(ref)
            if old and (status != "failed" or old.get("status") == "failed"):
                continue  # the desk and the custodian already hold it; only a failure is news
            qty, amt = _num(r["quantity"]), _num(r["amount"])
            sell = r["side"].strip().lower() == "sell"
            o.add("transactions", source_record_id=o.record("custodian", p, recv, rtype="settlement_line", external=ref, row=i), portfolio_id=o.port["EG-LIQUID"], instrument_id=iid, external_trade_id=ref,
                  transaction_type="sell" if sell else "buy", trade_date=M.parse_date(r["trade_date"]), effective_date=M.parse_date(r["trade_date"]), settlement_date=M.parse_date(r["settle_date"]),
                  quantity_delta=-qty if sell else qty, cash_amount=None if status == "failed" else (amt if sell else -amt), currency="USD", recorded_at=M.stamp(recv), status=status,
                  supersedes_transaction_id=old.get("id") if old else None, counterparty_name=(r.get("counterparty") or "").strip() or None, status_reason=(r.get("reason") or "").strip() or None)
            n += 1
            if status == "failed":
                o.note("settlement_status", flag=f"{ref}: failed ({r.get('reason')}), counterparty {r.get('counterparty')}, cash booked: {r.get('cash_booked')}")
                o.exception("settlement_fail", f"Trade {ref} has not settled", f"Settle date {r['settle_date']}, {r.get('reason')}; chase {r.get('counterparty')}.", recv, instrument_id=iid)
        o.note("settlement_status", files=1, rows=n)


# ---------------------------------------------------------------------------------------------------------------- tax lots
def tax_lots(M, o) -> None:
    for p in o.files("tax_lots"):
        recv, n, seen = o.arrival(p), 0, set()
        did = o.doc(p, "tax_lot_register", p.stem, kind="custodian", received=recv)
        for i, r in enumerate(M.dicts(M.sheet_rows(p)), 2):
            ref, iid = str(r.get("Lot") or "").strip(), o.inst.get(str(r.get("Security id") or "").strip())
            if not ref or iid is None:
                o.note("tax_lots", flag=f"row {i}: lot {ref!r} security {r.get('Security id')!r} unknown; set aside")
                continue
            if ref in seen:
                o.note("tax_lots", flag=f"{ref}: listed twice in the register; counted once")
                continue
            seen.add(ref)
            qty, unit, cost = _num(r["Quantity"]), _num(r["Unit cost"]), _num(r["Cost"])
            if cost is None or qty is None:
                o.note("tax_lots", flag=f"{ref}: quantity or cost missing; set aside")
                continue
            if unit is not None and abs(qty * unit - cost) > max(Decimal("1"), cost * Decimal("0.0001")):
                o.note("tax_lots", flag=f"{ref}: cost {cost} differs from quantity times unit cost {qty * unit}; the register's cost is kept")
            as_at = M.parse_date(r["As at"])
            prior = _prior(o, "tax_lots", "lot_ref = ?", [ref])
            o.add("tax_lots", source_record_id=o.record("custodian", p, recv, rtype="lot", external=ref, row=i), source_document_id=did, source_page=1, received_at=M.stamp(recv), recorded_at=M.stamp(recv),
                  supersedes_tax_lot_id=prior, portfolio_id=o.port["EG-LIQUID"], instrument_id=iid, lot_ref=ref, acquired_on=M.parse_date(r["Acquired"]), quantity=qty, unit_cost=unit, cost_amount=cost,
                  currency="USD", as_at=as_at, status="open")
            n += 1
        o.note("tax_lots", files=1, rows=n)


def realised_lots(M, o) -> None:
    """The custodian's realised gains report: each lot sold, matched first-in first-out, as fields of the report (the lot and the trade in value_text)."""
    for p in o.files("realised_lots"):
        recv, n = o.arrival(p), 0
        did = o.doc(p, "realised_gains_report", p.stem, kind="custodian", received=recv, date_=recv)
        for i, r in enumerate(M.csv_rows(p), 2):
            ref = f"{str(r.get('lot') or '').strip()} {str(r.get('trade_ref') or '').strip()} {str(r.get('settle_date') or '').strip()}".strip()
            vals = {k: _num(r.get(k)) for k in ("realised_gain", "proceeds", "cost")}
            if not ref or vals["realised_gain"] is None:
                o.note("realised_lots", flag=f"row {i}: lot {r.get('lot')!r} has no realised gain; set aside")
                continue
            for k, v in vals.items():
                if v is not None:
                    o.field(did, k, ref, v, "USD", line=i)
            n += 1
        o.note("realised_lots", files=1, rows=n)


# ---------------------------------------------------------------------------------------------------------------- manager outlooks
QUARTER = re.compile(r"(\d{4}-\d{2}-\d{2})\s+(-?[\d.]+)\s*%")


def manager_outlook(M, o) -> None:
    for p in o.files("manager_outlook"):
        t = M.pdf_text(str(p))
        recv, n = o.arrival(p), 0
        for ln, line in enumerate(t.splitlines(), 1):
            m = re.match(r"(.+?): payout as % of NAV at quarter end (.+)", line.strip())
            if not m:
                continue
            fund, iid = m[1].strip(), o.by_name.get(m[1].strip())
            quarters = QUARTER.findall(m[2])
            if iid is None or not quarters:
                o.note("manager_outlook", flag=f"{fund}: not a fund the office holds, or no quarters; set aside")
                continue
            did = o.doc(p, "manager_distribution_outlook", f"{fund} distribution outlook", kind="manager", received=recv, date_=recv, instrument=iid, raw=f"{o.rel(p)}#{fund}".encode(),
                        record=o.record("manager", p, recv, rtype="outlook", external=fund, row=ln))
            for q, pct in quarters:
                o.field(did, "projected_payout_rate", q, Decimal(pct) / 100, line=ln)
                n += 1
            if len(quarters) != 4:
                o.note("manager_outlook", flag=f"{fund}: {len(quarters)} quarters given, not four")
        if not n:
            o.note("manager_outlook", why=f"{p.name}: no fund line read")
        o.note("manager_outlook", files=1, rows=n)
