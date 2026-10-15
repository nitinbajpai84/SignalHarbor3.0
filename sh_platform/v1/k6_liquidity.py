"""K4: commitments, capital calls and the liquidity forecast (UC6).

Facts live in `commitments` (what an investor promised a fund) and `cash_movements` (calls and distributions, with `due_date`, `notice_kind`
and `commitment_id`). Both are append-only: a change is a new row that supersedes the old one (E1b). Figures are Decimal; nothing here
asks a model for a number.

`record_commitment(plane, row, supersedes_id=None) -> id`
`record_notice(plane, ...) -> {ids, exception_id}` used by E2b on read (status `noticed`) and on confirm (status `confirmed`, supersedes the noticed
    row); a confirmed call due within the signed `cash_call_alert_days` rule (default 30) opens a Finance case "Fund the capital call".
`forecast(plane, as_of, cutoff=None, viewer=None, currency=None) -> dict` read by the Office view (K2): per legal entity, available cash,
    calls and distributions due in 30/60/90 days, cash after those calls, uncalled commitment, and every call that is not confirmed yet.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from sh_platform.v1 import wh
from sh_platform.v1.e1_write import org_id
from sh_platform.v1.i2_north import Refused

log = logging.getLogger(__name__)
ALERT_RULE, ALERT_DEFAULT_DAYS = "cash_call_alert_days", 30
KINDS = ("call", "distribution", "recallable")
OPEN_CASE = ("new", "assigned", "investigating", "waiting_check")
BUCKETS = (("overdue", "Past due, not marked paid", None, -1), ("30", "Within 30 days", 0, 30), ("60", "31 to 60 days", 31, 60), ("90", "61 to 90 days", 61, 90))
CENT = Decimal("0.01")


def _d(x) -> Decimal:
    return Decimal(str(x if x is not None else 0))


def _day(x) -> date:
    return x.date() if isinstance(x, datetime) else x if isinstance(x, date) else date.fromisoformat(str(x)[:10])


def _cut(cutoff) -> datetime:
    if cutoff is None:
        return wh.now()
    if isinstance(cutoff, datetime):
        return cutoff if cutoff.tzinfo else cutoff.replace(tzinfo=timezone.utc)
    return datetime.combine(_day(cutoff), datetime.max.time(), tzinfo=timezone.utc)


def _rows(con, sql: str, params: list | None = None) -> list[dict]:
    cur = con.execute(sql, params or [])
    names = [c[0] for c in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def _live(con, table: str, sup: str, cut: datetime, where: str = "true", params: list | None = None) -> list[dict]:
    """Rows of an append-only table that were current as known at `cut`."""
    return _rows(con, f"select t.* from {table} t where t.recorded_at <= ? and ({where}) and not exists "
                      f"(select 1 from {table} s where s.{sup} = t.id and s.recorded_at <= ?) order by t.recorded_at, t.id",
                 [cut, *(params or []), cut])


# ---- commitments ------------------------------------------------------------------------------------------------------------------

def record_commitment(plane, row: dict, supersedes_id: str | None = None) -> str:
    """One commitment of an entity to a fund. Needs legal_entity_id, instrument_id, commitment_amount, currency, committed_on."""
    for k in ("legal_entity_id", "instrument_id", "commitment_amount", "currency", "committed_on"):
        if row.get(k) in (None, ""):
            raise Refused(400, f"A commitment needs {k.replace('_', ' ')}.")
    if _d(row["commitment_amount"]) <= 0:
        raise Refused(400, "A commitment must be more than zero.")
    from sh_platform.v1 import e1_write
    try:
        return e1_write.record(plane, "commitments", {**row, "committed_on": _day(row["committed_on"])}, supersedes_id=supersedes_id)
    except e1_write.WriteRefused as e:
        raise Refused(409, str(e)) from None


def _as_at(cell) -> date | None:
    """The date in a sheet line such as "As at 31 August 2026"; None for any other text."""
    m = re.search(r"as at (\d{1,2} [A-Za-z]+ \d{4})", str(cell), re.I)
    try:
        return datetime.strptime(m.group(1), "%d %B %Y").date() if m else None
    except ValueError:
        return None


def _file_called(con, source_record_id, grids: dict) -> tuple[Decimal, str, date | None] | None:
    """The "Called to date" figure on the commitments file row this commitment was loaded from, with where it came from and the file's
    "As at" date (None when the sheet has none); None when the commitment did not come from a file or the file has no such column.
    Read through the row's own locator (sheet, row), nothing stored twice."""
    if not source_record_id:
        return None
    r = con.execute("select b.storage_uri, x.sheet_name, x.row_number, b.batch_reference from source_records x join source_batches b on b.id = x.source_batch_id "
                    "where x.id = ?", [str(source_record_id)]).fetchone()
    if not r or not r[0]:
        return None
    try:
        from urllib.parse import urlparse
        from urllib.request import url2pathname
        from sh_platform.v1.e0b_tools import norm_header, read_grid
        path = url2pathname(urlparse(r[0]).path)
        if (path, r[1]) not in grids:
            grids[(path, r[1])] = read_grid(path, r[1])[1]
        grid, row = grids[(path, r[1])], int(r[2])
        head = next((g for g in grid[:row] if any(norm_header(c) == "called to date" for c in g if c is not None)), None)
        v = grid[row - 1][[norm_header(c) if c is not None else "" for c in head].index("called to date")] if head else None
        if v in (None, ""):
            return None
        as_at = next((d for d in (_as_at(c) for g in grid[:row] for c in g if c is not None) if d), None)
        return (_d(str(v).replace(",", "")), Path(path).name.split("__", 1)[-1], as_at)
    except Exception:  # noqa: BLE001 - any unreadable workbook (missing, not a zip, other layout) leaves the confirmed calls as the only source
        return None  # a missing file or an unreadable cell leaves the confirmed calls as the only source


def commitments(plane, cutoff=None, instrument_id: str | None = None) -> list[dict]:
    """Current commitments as known at `cutoff`, each with what has been called so far (confirmed calls, not cancelled). A confirmed call
    counts as called the day it is confirmed (answer key, known difference 3); `called_due_later` and `called_note` say how much of it is
    not due yet, so a reader comparing with the manager's last statement sees why."""
    cut = _cut(cutoff)
    today = cut.date()
    with wh.connect(plane, read_only=True) as con:
        rows = _live(con, "commitments", "supersedes_commitment_id", cut, "? is null or t.instrument_id = ?", [instrument_id, instrument_id])
        calls = _live(con, "cash_movements", "supersedes_cash_movement_id", cut,
                      "t.commitment_id is not null and t.notice_kind = 'call' and t.confirmation_status in ('confirmed', 'paid')")
    out, grids = [], {}
    for r in rows:
        mine = [c for c in calls if str(c["commitment_id"]) == str(r["id"])]
        called = sum((_d(c["amount"]) for c in mine), Decimal(0))
        with wh.connect(plane, read_only=True) as con:
            filed = _file_called(con, r.get("source_record_id"), grids)
        later = sorted((c for c in mine if c["confirmation_status"] != "paid" and c["due_date"] and _day(c["due_date"]) > today), key=lambda c: c["due_date"])
        amount = _d(r["commitment_amount"])
        note = ("Includes " + "; ".join(f"{_d(c['amount']):,.2f} {c['currency']} called for {_day(c['due_date']):%d %b %Y}, not due yet" for c in later)
                + ".") if later else None
        if filed and not mine:  # no confirmed call yet: the commitments file's own figure stands in, and says so
            called = filed[0]
            note = f"Called to date {filed[0]:,.2f} is from the commitments file {filed[1]}; no call is confirmed yet."
        elif filed and filed[2]:  # the file's figure is as at its date: a call received by then is in it already, only later ones add
            new = [c for c in mine if _day(c["received_at"]) > filed[2]]
            added = sum((_d(c["amount"]) for c in new), Decimal(0))
            called = filed[0] + added
            if new:
                note = (note + " " if note else "") + (f"Called to date {filed[0]:,.2f} is from the commitments file {filed[1]} as at {filed[2]:%d %b %Y}; "
                                                       f"{added:,.2f} confirmed since is added.")
        elif filed and filed[0] != called:  # no date to compare with: confirmed calls win; the difference is shown, not hidden
            note = (note + " " if note else "") + f"The commitments file {filed[1]} says {filed[0]:,.2f} called; confirmed calls add up to {called:,.2f}."
        out.append({**{k: (str(v) if k.endswith("_id") or k == "id" else v) for k, v in r.items() if v is not None or k.endswith("_id")},
                    "commitment_amount": amount, "called": called, "uncalled": amount - called,
                    "called_due_later": sum((_d(c["amount"]) for c in later), Decimal(0)), "called_note": note})
    return out


# ---- notices ----------------------------------------------------------------------------------------------------------------------

def _notice_source(plane, doc: dict) -> str:
    """The source record of a notice document (one per document), created on first use."""
    ref = f"notice:{doc['id']}"
    with wh.connect(plane) as con:
        r = con.execute("select r.id from source_records r join source_batches b on b.id = r.source_batch_id where b.batch_reference = ? limit 1", [ref]).fetchone()
        if r:
            return str(r[0])
        batch, rec, now = wh.new_id(), wh.new_id(), wh.now()
        con.execute("insert into source_batches (id, organization_id, source_system_id, batch_reference, received_at, loaded_at, validation_status) values (?,?,?,?,?,?,?)",
                    [batch, org_id(plane), doc["source_system_id"], ref, doc["received_at"], now, "loaded"])
        con.execute("insert into source_records (id, organization_id, source_batch_id, external_record_id, record_type, received_at, recorded_at, raw_payload_uri,"
                    " content_hash, quality_status) values (?,?,?,?,?,?,?,?,?,?)",
                    [rec, org_id(plane), batch, str(doc["id"]), "manager_notice", doc["received_at"], now, doc["original_uri"],
                     doc["content_hash"] or hashlib.sha256(ref.encode()).hexdigest(), "loaded"])
        return rec


def _portfolio_for(con, entity_id: str, instrument_id: str) -> str | None:
    """The entity's portfolio that holds the fund (latest valuation), else its first portfolio by code."""
    r = con.execute("select v.portfolio_id from valuation_observations v join portfolios p on p.id = v.portfolio_id where p.legal_entity_id = ? and v.instrument_id = ?"
                    " order by v.valuation_date desc, v.recorded_at desc limit 1", [entity_id, instrument_id]).fetchone()
    r = r or con.execute("select id from portfolios where legal_entity_id = ? order by portfolio_code limit 1", [entity_id]).fetchone()
    return str(r[0]) if r else None


def record_notice(plane, document_id: str, instrument_id: str, kind: str, amount, currency: str, due_date, status: str, actor=None,
                  page: int | None = None, line: int | None = None) -> dict:
    """Write the notice as one cash movement per current commitment of the fund (the amount is shared by commitment size when an entity
    group holds several). `status` is `noticed` (read, waiting for a person) or `confirmed`. A row for the same notice that is still current
    is superseded, so the history of the notice stays. Returns {ids, exception_id}; ids is [] when the fund has no commitment yet (a read) and a confirm refuses."""
    from sh_platform.v1 import e1_write
    if kind not in KINDS:
        raise Refused(400, "A notice is a call, a distribution or a recallable distribution.")
    amount = _d(amount)
    if amount <= 0:
        raise Refused(422, "The notice amount must be more than zero.")
    due = _day(due_date) if due_date else None
    if kind == "call" and due is None:
        raise Refused(409, "The due date of a capital call must be read or confirmed first.")
    with wh.connect(plane, read_only=True) as con:
        doc = _rows(con, "select id, source_system_id, original_uri, content_hash, received_at from documents where id = ?", [document_id])
    if not doc:
        raise Refused(404, "We could not find that document.")
    doc = doc[0]
    com = commitments(plane, instrument_id=instrument_id)
    if not com:
        if status == "confirmed":
            raise Refused(409, "No commitment is recorded for this fund, so the notice cannot be tied to one. Record the commitment first.")
        return {"ids": [], "exception_id": None}
    src = _notice_source(plane, doc)
    total, left, ids, made = sum((c["commitment_amount"] for c in com), Decimal(0)), amount, [], []
    effective = due or _day(doc["received_at"])
    for i, c in enumerate(com):
        share = left if i == len(com) - 1 else (amount * c["commitment_amount"] / total).quantize(CENT, ROUND_HALF_UP)
        left -= share
        with wh.connect(plane, read_only=True) as con:
            prev = _live(con, "cash_movements", "supersedes_cash_movement_id", wh.now(),
                         "t.commitment_id = ? and t.source_record_id = ?", [c["id"], src])
            pf = _portfolio_for(con, c["legal_entity_id"], instrument_id)
        if pf is None:
            raise Refused(409, "The entity that made this commitment has no portfolio yet.")
        row = {"source_record_id": src, "portfolio_id": pf, "instrument_id": instrument_id, "movement_type": "distribution" if kind != "call" else "call",
               "effective_date": effective, "received_at": doc["received_at"], "amount": share, "currency": currency, "confirmation_status": status,
               "due_date": due, "notice_kind": kind, "commitment_id": c["id"]}
        sup = str(prev[-1]["id"]) if prev else None
        ids.append((e1_write.record(plane, "cash_movements", row, supersedes_id=sup), row))
    case = None
    if status == "confirmed" and kind == "call":
        for _, row in ids:
            case = alert_if_due(plane, row, actor, page, line) or case
    return {"ids": [i for i, _ in ids], "exception_id": case}


def _alert_days(plane, today: date) -> int:
    try:
        from sh_platform.v1 import e3_rules
        rule = e3_rules.current(plane, ALERT_RULE, today)
    except ImportError:
        log.warning("e3_rules is not available; the default of %d days is used for call alerts", ALERT_DEFAULT_DAYS)
        rule = None
    p = (rule or {}).get("parameters") or {}
    for k in ("days", "alert_days", ALERT_RULE):
        if p.get(k) not in (None, ""):
            return int(p[k])
    return ALERT_DEFAULT_DAYS


def alert_if_due(plane, row: dict, actor=None, page: int | None = None, line: int | None = None, today: date | None = None) -> str | None:
    """A confirmed call due within the signed alert window opens a Finance case "Fund the capital call" (one per fund and portfolio while
    it is open; a later notice for it adds a line to that case). Returns the case id."""
    today = today or wh.today(plane)
    due = _day(row["due_date"])
    if due > today + timedelta(days=_alert_days(plane, today)):
        return None
    from sh_platform.v1 import e4_cases
    where = f" Notice page {page}, line {line}." if page else ""
    with wh.connect(plane, read_only=True) as con:
        name = con.execute("select canonical_name from instruments where id = ?", [row["instrument_id"]]).fetchone()
        ent = con.execute("select e.entity_name from portfolios p join legal_entities e on e.id = p.legal_entity_id where p.id = ?", [row["portfolio_id"]]).fetchone()
        old = con.execute("select id from exceptions where exception_type = 'capital_call' and instrument_id = ? and portfolio_id = ? and status in "
                          f"({','.join('?' * len(OPEN_CASE))}) order by detected_at desc limit 1", [row["instrument_id"], row["portfolio_id"], *OPEN_CASE]).fetchone()
    said = f"{name[0] if name else 'The fund'} has called {_d(row['amount']):,.2f} {row['currency']}, due {due.isoformat()}.{where}"
    if old:
        e4_cases.add_event(plane, str(old[0]), actor, "comment", "A new notice for this call: " + said)
        return str(old[0])
    title = " · ".join(["Fund the capital call", *(x[0] for x in (name, ent) if x), due.isoformat()])  # like "Cash differs · Entity B · 2026-10-08"
    return e4_cases.open(plane, {"exception_type": "capital_call", "title": title, "description": said, "portfolio_id": str(row["portfolio_id"]),
                                 "instrument_id": str(row["instrument_id"]), "candidate_impact_amount": _d(row["amount"]), "impact_currency": row["currency"],
                                 "due_at": datetime.combine(due, datetime.min.time(), tzinfo=timezone.utc), "accounting_view_affected": True, "actor": actor})


# ---- the forecast -----------------------------------------------------------------------------------------------------------------

def _rate(plane, frm: str, to: str, on: date, cutoff) -> Decimal | None:
    if frm == to:
        return Decimal(1)
    from sh_platform.v1 import e3_calc
    return e3_calc.fx(plane, frm, to, on, cutoff)


def _cash(plane, cut: datetime, as_of: date) -> list[dict]:
    """Latest cash position per portfolio and cash instrument at or before `as_of`: the administrator's (accounting) view, else the trading
    export (operational)."""
    with wh.connect(plane, read_only=True) as con:
        rows = _live(con, "position_snapshots", "supersedes_position_id", cut,
                     "t.position_date <= ? and t.instrument_id in (select id from instruments where instrument_type = 'cash')", [as_of])
    best: dict[tuple, dict] = {}
    for r in rows:
        k = (str(r["portfolio_id"]), str(r["instrument_id"]))
        rank = (r["view_type"] == "accounting", r["position_date"], r["recorded_at"])
        if k not in best or rank > best[k][0]:
            best[k] = (rank, r)
    return [r for _, r in best.values() if r["source_market_value"] is not None]


def _notice(d: dict | None) -> dict:
    """Where a call or distribution comes from: the notice document, when it was received, and the page and line of the amount."""
    if not d:
        return {"document_id": None, "document_title": None, "received_at": None, "page": None, "line": None}
    return {"document_id": str(d["document_id"]), "document_title": d["title"], "received_at": d["received_at"], "page": d["page_number"], "line": d["line_number"]}


def _shortfall(entity: str, label: str, running: Decimal, firm: Decimal, pending: list[dict], ccy: str) -> str:
    """The first bucket where cash after the calls goes below zero, in words."""
    short = f"Shortfall: {entity} is short by {-running:,.2f} {ccy} {label.lower()} if every call is paid"
    if not pending:
        return short + "."
    who = " and ".join(f"the {i['fund'] or 'unnamed fund'} call" for i in pending)
    after = f"after the confirmed calls alone {firm:,.2f} {ccy} remains" if firm >= 0 else f"even after the confirmed calls alone it is short by {-firm:,.2f} {ccy}"
    return f"{short}, including {who}, not confirmed yet; {after}."


def forecast(plane, as_of, cutoff=None, viewer=None, currency: str | None = None) -> dict:
    """Per legal entity: {entity_id, entity_code, entity_name, currency, available_cash, cash_sources, buckets: [{key, label, calls, distributions,
    cash_after_calls, items}], uncalled, unconfirmed, problems}. Amounts are in `currency`, else in the entity's own currency; a figure that
    cannot be converted is left out and named in `problems` (never guessed). `viewer` limits entities to those the person may see (E1d)."""
    as_of, cut = _day(as_of), _cut(cutoff)
    if viewer is not None:
        from sh_platform.v1 import e1_access
        allowed = e1_access.visible_entities(plane, viewer)
    with wh.connect(plane, read_only=True) as con:
        ents = _rows(con, "select id, entity_code, entity_name, base_currency from legal_entities order by entity_code")
        pf = {str(r["id"]): str(r["legal_entity_id"]) for r in _rows(con, "select id, legal_entity_id from portfolios")}
        moves = _live(con, "cash_movements", "supersedes_cash_movement_id", cut,
                      "t.confirmation_status <> 'cancelled' and (t.notice_kind in ('call','distribution','recallable') or t.movement_type in ('call','distribution'))")
        names = {str(r["id"]): r["canonical_name"] for r in _rows(con, "select id, canonical_name from instruments")}
        docs = {str(r["rec"]): r for r in _rows(con, "select x.id as rec, d.id as document_id, d.title, d.received_at, f.page_number, f.line_number"
                                                     " from source_records x join documents d on cast(d.id as varchar) = x.external_record_id"
                                                     " left join extracted_fields f on f.document_id = d.id and f.field_name in ('call_amount', 'distribution_amount')"
                                                     " where x.record_type = 'manager_notice'")}
    com = {c["id"]: c for c in commitments(plane, cutoff=cut)}
    cash = _cash(plane, cut, as_of)
    out = []
    for e in ents:
        eid = str(e["id"])
        if viewer is not None and eid not in {str(x) for x in allowed}:
            continue
        ccy, problems = currency or e["base_currency"], []

        def conv(amount, frm, on, what):
            rate = _rate(plane, frm, ccy, on, cut)
            if rate is None:
                problems.append(f"{what}: no signed exchange rate from {frm} to {ccy} for {on.isoformat()}, so it is left out.")
                return None
            return _d(amount) * rate
        sources, total = [], Decimal(0)
        for r in cash:
            if pf.get(str(r["portfolio_id"])) == eid:
                v = conv(r["source_market_value"], r["currency"] or ccy, as_of, "Cash")
                if v is not None:
                    total += v
                    sources.append({"position_id": str(r["id"]), "portfolio_id": str(r["portfolio_id"]), "position_date": r["position_date"].isoformat(),
                                    "status": r["data_status"], "amount": v})
        items = []
        for m in moves:
            c = com.get(str(m["commitment_id"])) if m["commitment_id"] else None
            if (str(c["legal_entity_id"]) if c else pf.get(str(m["portfolio_id"]))) != eid:
                continue
            kind = m["notice_kind"] or m["movement_type"]
            due = _day(m["due_date"] or m["effective_date"])
            v = conv(m["amount"], m["currency"], due, f"{names.get(str(m['instrument_id']), 'A fund')} {kind}")
            if v is None:
                continue
            items.append({"id": str(m["id"]), "kind": "distribution" if kind == "recallable" else kind, "recallable": kind == "recallable",
                          "instrument_id": str(m["instrument_id"]) if m["instrument_id"] else None, "fund": names.get(str(m["instrument_id"])),
                          "commitment_id": str(m["commitment_id"]) if m["commitment_id"] else None, "due_date": due.isoformat(), "amount": v,
                          "days": (due - as_of).days, "own_amount": _d(m["amount"]), "own_currency": m["currency"], "status": m["confirmation_status"],
                          "confirmed": m["confirmation_status"] in ("confirmed", "paid"),
                          "estimated": len([x for x in com.values() if str(x["instrument_id"]) == str(m["instrument_id"])]) > 1, "source_record_id": str(m["source_record_id"]),
                          **_notice(docs.get(str(m["source_record_id"])))})
        buckets, running, firm, warnings = [], total, total, []
        for key, label, lo, hi in BUCKETS:
            sel = [i for i in items if i["kind"] == "call" and i["days"] < 0 and i["status"] != "paid"] if key == "overdue" else                   [i for i in items if lo <= i["days"] <= hi]
            calls = sum((i["amount"] for i in sel if i["kind"] == "call"), Decimal(0))
            dist = sum((i["amount"] for i in sel if i["kind"] == "distribution"), Decimal(0))
            if key != "overdue":
                running -= calls
                firm -= sum((i["amount"] for i in sel if i["kind"] == "call" and i["confirmed"]), Decimal(0))
                if running < 0 and not warnings:
                    pending = [i for i in items if i["kind"] == "call" and not i["confirmed"] and 0 <= i["days"] <= hi]
                    warnings.append(_shortfall(e["entity_name"], label, running, firm, pending, ccy))
            buckets.append({"key": key, "label": label, "calls": calls, "distributions": dist,
                            "cash_after_calls": None if key == "overdue" else running,
                            "cash_after_confirmed_calls": None if key == "overdue" else firm, "items": sorted(sel, key=lambda i: i["due_date"])})
        unconfirmed = sorted((i for i in items if i["kind"] == "call" and not i["confirmed"]), key=lambda i: i["due_date"])  # every one, in or out of the buckets
        unconfirmed_dist = sorted((i for i in items if i["kind"] == "distribution" and not i["confirmed"] and i["days"] >= 0), key=lambda i: i["due_date"])
        mine = [c for c in com.values() if str(c["legal_entity_id"]) == eid]
        uncalled = Decimal(0)
        for c in mine:
            v = conv(c["uncalled"], c["currency"], as_of, "Uncalled commitment")
            uncalled += v or Decimal(0)
        out.append({"entity_id": eid, "entity_code": e["entity_code"], "entity_name": e["entity_name"], "currency": ccy, "available_cash": total,
                    "cash_sources": sources, "buckets": buckets, "uncalled": uncalled, "unconfirmed": unconfirmed,
                    "unconfirmed_distributions": unconfirmed_dist, "warnings": warnings, "problems": problems})
    return {"as_of": as_of.isoformat(), "cutoff": cut.isoformat(), "entities": out}
