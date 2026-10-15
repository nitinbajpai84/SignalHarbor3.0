"""A2 the trail: "where is this from". Six steps for a figure: source, file, read, checked, stored, used by.

`trail(plane, viewer, kind, id)` -> {kind, id, title, figure, steps:[{key, label, state, what, who, when, refs}]}.
state: done | waiting | missing | restricted. Nothing here writes. Every step is built from rows already in the warehouse
(source_systems, batches and records, documents, extracted fields, agent runs, the supersession chain, calculation runs, metric
evidence, report versions, cases) or, for a dashboard tile, from the project's build plan, run log and dashboard file.
Access: the figure needs E1d access to its portfolio (else PermissionError); a step that shows a statement's content needs document
access, else it reads "restricted" and carries nothing."""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import date
from decimal import Decimal

from sh_platform.v1 import wh

log = logging.getLogger(__name__)

KINDS = ("valuation", "position", "cash", "nav", "metric", "case", "tile")
STEPS = (("source", "Source"), ("file", "File"), ("read", "Read"), ("checked", "Checked"), ("stored", "Stored"), ("used_by", "Used by"))
FACTS = {"valuation": ("valuation_observations",), "position": ("position_snapshots",), "nav": ("nav_snapshots",),
         "cash": ("cash_movements", "position_snapshots")}
AMOUNT = {"valuation_observations": "value_amount", "position_snapshots": "source_market_value", "nav_snapshots": "nav_amount", "cash_movements": "amount"}
STATUS = {"valuation_observations": "approval_status", "position_snapshots": "data_status", "nav_snapshots": "nav_status", "cash_movements": "confirmation_status"}
WORKERS = frozenset({"analyst", "company_admin"})
RESTRICTED = "You do not have access to this step."
NOUN = {"valuation_observations": "valuation", "position_snapshots": "holding", "nav_snapshots": "net asset value", "cash_movements": "cash movement"}
FIELD_WORDS = {"nav": "net asset value"}


# ---- small helpers -------------------------------------------------------------------------------------------------

def _rows(con, sql: str, args: list | None = None) -> list[dict]:
    cur = con.execute(sql, args or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _one(con, sql: str, args: list | None = None) -> dict | None:
    r = _rows(con, sql, args)
    return r[0] if r else None


def _uuid(v: str) -> str:
    try:
        return str(uuid.UUID(str(v)))
    except ValueError:
        raise LookupError("We could not find that.") from None


def _s(v):
    return str(v) if v is not None else None


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _date(v) -> str:
    """A day as the screens print it: 7 Oct 2026."""
    if v is None:
        return "no date"
    d = v if isinstance(v, date) else date.fromisoformat(str(v)[:10])
    return f"{d.day} {d:%b %Y}"


def _person(con, uid) -> str | None:
    if not uid:
        return None
    r = _one(con, "select display_name from users where id = ? or external_identity_id = ?", [str(uid), str(uid).replace("-", "")])  # a review keeps the account's id
    return r["display_name"] if r else None


def _roles(viewer) -> set[str]:
    return set(getattr(viewer, "roles", ()) or ())


def _step(key: str, state: str, what: str = "", who=None, when=None, refs=None) -> dict:
    label = {**dict(STEPS), "decided": "Decided", "shown": "Shown"}[key]  # N1: a case a reconciliation opened ends "Decided", "Shown"
    if state == "restricted":
        return {"key": key, "label": label, "state": "restricted", "what": RESTRICTED, "who": None, "when": None, "refs": []}
    return {"key": key, "label": label, "state": state, "what": what, "who": who, "when": _iso(when), "refs": refs or []}


def _missing(key: str, what: str) -> dict:
    return _step(key, "missing", what)


# ---- access --------------------------------------------------------------------------------------------------------

def _may(plane, viewer, portfolio_id, instrument_id=None) -> bool:
    """May the viewer see a figure of this portfolio (or, with none, this fund)? Fail closed."""
    from sh_platform.v1 import e1_access
    if e1_access.is_admin(viewer):
        return True
    if portfolio_id:
        return e1_access.level(plane, viewer, portfolio_id=str(portfolio_id)) != "none"
    if instrument_id:
        from sh_platform.v1 import e2_screen
        return e2_screen.can_see(plane, viewer, str(instrument_id))
    return bool(_roles(viewer) & WORKERS)


def _doc_ok(con, plane, viewer, doc: dict) -> bool:
    """Statement access: Operations, or a person with access to the fund (E1d) who is in the document's group or a group that
    reads this document type. Fail closed."""
    if _roles(viewer) & WORKERS:
        return True
    from sh_platform.v1 import e1_access
    from sh_platform.v1.e2_screen import can_see
    if not can_see(plane, viewer, _s(doc.get("instrument_id"))):
        return False
    uid = e1_access.user_id_of(con, viewer)
    if not uid:
        return False
    groups = {str(r["access_group_id"]) for r in _rows(
        con, "select access_group_id from access_group_memberships where user_id = ? and (expires_at is null or expires_at > ?)", [uid, wh.now()])}
    if _s(doc.get("access_group_id")) in groups:
        return True
    return any(str(r["access_group_id"]) in groups for r in _rows(
        con, "select access_group_id from access_group_scopes where scope_type = 'document_type' and scope_value = ? and access_level in ('read','full')",
        [doc.get("document_type")]))


# ---- the six steps of a stored fact --------------------------------------------------------------------------------

def _chain(con, table: str, row: dict) -> tuple[dict | None, dict | None]:
    """(the row this one replaced, the row that replaced this one)."""
    col = next((c for c in row if c.startswith("supersedes_")), None)
    if not col:
        return None, None
    old = _one(con, f"select * from {table} where id = ?", [str(row[col])]) if row[col] else None  # table is from FACTS
    new = _one(con, f"select * from {table} where {col} = ? order by recorded_at limit 1", [str(row["id"])])
    return old, new


def _used_by(con, table: str, row_id: str, instrument_id, extra: list | None = None, plane=None) -> dict:
    refs = list(extra or [])
    if plane is not None and table == "cash_movements":     # a cash item is used by the case whose Tally findings name it as a candidate cause
        from sh_platform.v1 import n1_tally
        refs += [{"kind": "case", "id": str(ex["id"]), "label": f"Case: {ex['title']} ({ex['status']}), as a candidate cause"} for ex in n1_tally.cited_by(plane, row_id)]
    for rv in _rows(con, "select distinct rv.id, rv.period_end, rv.status, rv.issued_at, r.report_name from metric_evidence e "
                         "join metric_values v on v.id = e.metric_value_id join report_versions rv on rv.calculation_run_id = v.calculation_run_id "
                         "join reports r on r.id = rv.report_id where e.note = ? order by rv.issued_at", [f"{table}:{row_id}"]):
        refs.append({"kind": "report_version", "id": str(rv["id"]), "label": f"{rv['report_name']} for {_date(rv['period_end'])} ({rv['status']})"})
    if instrument_id:
        for ex in _rows(con, "select id, title, status, exception_type from exceptions where instrument_id = ? order by detected_at", [str(instrument_id)]):
            if table == "valuation_observations" and ex["exception_type"] == "capital_call":   # a call is traced from its notice, not from a valuation
                continue
            if not any(r["id"] == str(ex["id"]) for r in refs):
                refs.append({"kind": "case", "id": str(ex["id"]), "label": f"Case: {ex['title']} ({ex['status']})"})
    if plane is not None and table == "valuation_observations":   # a limit case on a manager or a class names its inputs, not one instrument
        refs += [{"kind": "case", "id": str(ex["id"]), "label": f"Case: {ex['title']} ({ex['status']}), as an input"} for ex in _limit_cases(plane, con, row_id)]
    if table == "valuation_observations" and instrument_id and _is_current(con, row_id, instrument_id):
        refs.append({"kind": "page", "id": "office", "label": "the Office view holdings, as the fund's current value"})
    if not refs:
        return _missing("used_by", "Not in an issued report or an open case yet.")
    return _step("used_by", "done", "Used in " + "; ".join(r["label"] for r in refs) + ".", refs=refs)


def _limit_cases(plane, con, row_id: str) -> list[dict]:
    """Limit-breach cases with no instrument of their own (a manager or a class) whose inputs include this valuation."""
    from sh_platform.v1 import n1_tally
    out = []
    for ex in _rows(con, "select * from exceptions where exception_type = 'limit_breach' and instrument_id is null order by detected_at"):
        try:
            inputs = (n1_tally.BUILDERS["limit_breach"](plane, ex).get("raw") or {}).get("inputs") or []
        except Exception:  # noqa: BLE001 - one odd case must not stop the trail
            log.warning("the limit case %s could not be read for the trail", ex["id"], exc_info=True)
            continue
        if any(str(i.get("id")) == row_id for i in inputs):
            out.append(ex)
    return out


def _is_current(con, row_id: str, instrument_id) -> bool:
    """Is this the fund's latest valuation (newest date, then newest record), the one the Office view shows?"""
    r = _one(con, "select id from valuation_observations where instrument_id = ? and approval_status <> 'rejected' "
                  "order by valuation_date desc, recorded_at desc limit 1", [str(instrument_id)])
    return bool(r) and str(r["id"]) == row_id


def _cadence(con, doc: dict | None) -> str | None:
    """How often this fund's statements come, from the periods its statements cover (one email channel carries funds of every rhythm)."""
    if not doc or not doc.get("instrument_id"):
        return None
    if "notice" in str(doc.get("document_type") or ""):
        return "when the manager sends a notice"
    days = sorted({r["valuation_date"] for r in _rows(con, "select distinct valuation_date from documents where instrument_id = ? and valuation_date is not null",
                                                         [str(doc["instrument_id"])])})
    gaps = sorted((b - a).days for a, b in zip(days, days[1:]))
    if not gaps:
        return None
    return "quarterly" if gaps[len(gaps) // 2] > 45 else "monthly"


def _fact_steps(plane, viewer, con, table: str, row: dict) -> list[dict]:
    rid, iid = str(row["id"]), _s(row.get("instrument_id"))
    rec = _one(con, "select * from source_records where id = ?", [str(row["source_record_id"])]) if row.get("source_record_id") else None
    batch = _one(con, "select * from source_batches where id = ?", [str(rec["source_batch_id"])]) if rec else None
    fld = _one(con, "select * from extracted_fields where id = ?", [str(row["extracted_field_id"])]) if row.get("extracted_field_id") else None
    doc_id = row.get("evidence_document_id") or (fld or {}).get("document_id")
    if not doc_id and rec and rec.get("record_type") == "manager_notice" and rec.get("external_record_id"):    # k6_liquidity keeps the notice's document id there
        doc_id = rec["external_record_id"]
        fld = _one(con, "select * from extracted_fields where document_id = ? and value_numeric is not null order by page_number, line_number limit 1", [str(doc_id)])
    doc = _one(con, "select * from documents where id = ?", [str(doc_id)]) if doc_id else None
    sys_id = (batch or {}).get("source_system_id") or (doc or {}).get("source_system_id")
    sysrow = _one(con, "select * from source_systems where id = ?", [str(sys_id)]) if sys_id else None
    doc_ok = _doc_ok(con, plane, viewer, doc) if doc else True

    if sysrow:
        every = _cadence(con, doc) or sysrow.get("expected_cadence")
        cad = f", arrives {every}" if every else ""
        source = _step("source", "done", f"{sysrow['source_name']} ({sysrow['source_type']}){cad}.", _person(con, sysrow.get("owner_user_id")),
                       (batch or (doc if doc_ok else None) or {}).get("received_at"), [{"kind": "source_system", "id": str(sysrow["id"]), "label": sysrow["source_name"]}])
    else:
        source = _missing("source", "The source of this figure was not recorded.")

    if doc and not doc_ok:
        file = _step("file", "restricted")
    elif doc:
        file = _step("file", "done", f"{'Notice' if 'notice' in str(doc.get('document_type') or '') else 'Statement'} \"{doc['title']}\" ({doc['original_filename'] or 'file'}), "
                     f"received {_date(doc['received_at'])}.", None,
                     doc["received_at"], [{"kind": "document", "id": str(doc["id"]), "label": doc["title"]}])
    elif batch:
        file = _step("file", "done", f"File {batch['batch_reference']} ({str(batch.get('storage_uri') or '').rsplit('/', 1)[-1] or 'stored copy'}).", None,
                     batch["received_at"], [{"kind": "batch", "id": str(batch["id"]), "label": batch["batch_reference"]}])
    else:
        file = _missing("file", "No file is linked to this figure.")

    if fld:
        if not doc_ok:
            read = _step("read", "restricted")
        else:
            run = _one(con, "select * from agent_runs where id = ?", [str(fld["extracted_by_agent_run_id"])]) if fld.get("extracted_by_agent_run_id") else None
            where = f"page {fld['page_number']}" + (f", line {fld['line_number']}" if fld.get("line_number") else "") if fld.get("page_number") else "the statement"
            read = _step("read", "done", f"The intake agent read the {FIELD_WORDS.get(fld['field_name'], str(fld['field_name']).replace('_', ' '))} from {where} (confidence {fld['confidence']}).",
                         f"{run['agent_type']} agent" if run else "Intake agent", (run or {}).get("started_at") or (doc or {}).get("recorded_at"),
                         [{"kind": "agent_run", "id": str(run["id"]), "label": "Agent run"}] if run else [])
    elif rec:
        loc = f"sheet {rec['sheet_name']}, row {rec['row_number']}" if rec.get("sheet_name") else "one row"
        mp = _one(con, "select * from sheet_mappings where id = ?", [str(batch["sheet_mapping_id"])]) if batch and batch.get("sheet_mapping_id") else None
        read = _step("read", "done", f"Loaded from {loc}" + (" using an approved sheet mapping." if mp else "."), "Loading program",
                     rec.get("recorded_at"), [{"kind": "sheet_mapping", "id": str(mp["id"]), "label": "Sheet mapping"}] if mp else [])
    else:
        read = _missing("read", "How this was read is not recorded.")

    if fld and fld["review_status"] == "pending":
        checked = _step("checked", "waiting", "Waiting for a person in Operations to check the value read.")
    elif fld and fld.get("reviewed_by"):
        verb = {"confirmed": "Confirmed", "corrected": "Corrected", "rejected": "Rejected"}.get(fld["review_status"], "Reviewed")
        paper = "notice" if "notice" in str((doc or {}).get("document_type") or "") else "statement"
        checked = _step("checked", "done", f"{verb} by a person against the {paper}.", _person(con, fld["reviewed_by"]), fld.get("reviewed_at"))
    elif batch:
        totals = _rows(con, "select passed from batch_control_totals where source_batch_id = ?", [str(batch["id"])])
        ok = bool(totals) and all(t["passed"] for t in totals)
        what = (f"Row count and totals matched the file ({len(totals)} checks)." if ok else "A control total did not match the file." if totals
                else f"The file was {batch['validation_status']}.")
        checked = _step("checked", "done" if ok or not totals else "waiting", what, _person(con, (sysrow or {}).get("owner_user_id")), batch.get("loaded_at") or batch["received_at"])
    else:
        checked = _missing("checked", "No check is recorded for this figure.")

    old, new = _chain(con, table, row)
    amount = Decimal(str(row[AMOUNT[table]]))
    while old and Decimal(str(old[AMOUNT[table]])) == amount:     # a confirmation stores the same value again: name the value it really replaced
        old = _chain(con, table, old)[0]
    while new and Decimal(str(new[AMOUNT[table]])) == amount:
        nxt = _chain(con, table, new)[1]
        if not nxt:
            break
        new = nxt
    # one sentence joined by semicolons: a date never ends a sentence mid-step ("... 7 Oct 2026. The ..." reads as a step number)
    bits = [f"Stored as a {NOUN[table]}, status {row.get(STATUS[table]) or 'not set'}"]
    refs = []
    if old:
        was = "estimate" if "estimat" in f"{old.get(STATUS[table])} {old.get('valuation_type')}" else "value"
        bits.append(f"it replaced the earlier {was} of {_money(old[AMOUNT[table]], old.get('currency'))} recorded on {_date(old['recorded_at'])}")
        refs.append({"kind": table, "id": str(old["id"]), "label": "Earlier value"})
    if new and Decimal(str(new[AMOUNT[table]])) == amount:
        bits.append(f"a person confirmed it on {_date(new['recorded_at'])}")
        refs.append({"kind": table, "id": str(new["id"]), "label": "Confirmed value"})
    elif new:
        bits.append(f"it was replaced by a newer value of {_money(new[AMOUNT[table]], new.get('currency'))} recorded on {_date(new['recorded_at'])}")
        refs.append({"kind": table, "id": str(new["id"]), "label": "Newer value"})
    if table == "valuation_observations" and row.get("valuation_date") and iid and _is_current(con, rid, iid):
        from sh_platform.v1.k4_office import STALE_DAYS
        if (wh.now().date() - date.fromisoformat(str(row["valuation_date"])[:10])).days > STALE_DAYS:
            bits.append(f"its valuation date, {_date(row['valuation_date'])}, is more than {STALE_DAYS} days ago, so the screens mark it Stale")
    stored = _step("stored", "done", "; ".join(bits) + ".", None, row.get("recorded_at"), refs)
    return [source, file, read, checked, stored, _used_by(con, table, rid, iid, plane=plane)]


def _by_key(steps: list[dict]) -> dict:
    return {s["key"]: s for s in steps}


def _figure(con, label_row: dict, amount, currency) -> dict:
    name = None
    if label_row.get("instrument_id"):
        r = _one(con, "select canonical_name from instruments where id = ?", [str(label_row["instrument_id"])])
        name = r["canonical_name"] if r else None
    if not name and label_row.get("portfolio_id"):
        r = _one(con, "select portfolio_name from portfolios where id = ?", [str(label_row["portfolio_id"])])
        name = r["portfolio_name"] if r else None
    return {"label": name or "Total", "value": None if amount is None else _plain(amount), "currency": currency}


def _plain(amount) -> str:
    """A stored amount as plain digits without the column's trailing zeros (10000000.0000000000 -> 10000000); the screen adds the separators."""
    d = Decimal(str(amount))
    return format(d.quantize(Decimal(1)) if d == d.to_integral_value() else d.normalize(), "f")


def _money(amount, currency: str | None = None) -> str:
    from sh_platform.v1.n1_tally import money
    return money(amount, currency)


# ---- kinds ---------------------------------------------------------------------------------------------------------

def _fact(plane, viewer, con, kind: str, rid: str) -> dict:
    for table in FACTS[kind]:
        row = _one(con, f"select * from {table} where id = ?", [rid])  # table is from FACTS
        if row:
            break
    else:
        raise LookupError("We could not find that figure.")
    if not _may(plane, viewer, row.get("portfolio_id"), row.get("instrument_id")):
        raise PermissionError
    fig = _figure(con, row, row[AMOUNT[table]], row.get("currency"))
    title = f"{fig['label']}, {kind}"
    if table == "cash_movements":     # a cash item is named by what it is and its reference, not by the cash account it sits in
        rec = _one(con, "select external_record_id, record_type from source_records where id = ?", [str(row["source_record_id"])]) if row.get("source_record_id") else None
        ref = (rec or {}).get("external_record_id") if (rec or {}).get("record_type") != "manager_notice" else None
        what = "Capital call" if row.get("movement_type") == "call" else str(row.get("movement_type") or "Cash movement").replace("_", " ").capitalize()
        fund = _one(con, "select canonical_name from instruments where id = ? and instrument_type <> 'cash'", [str(row["instrument_id"])]) if row.get("instrument_id") else None
        ent = _one(con, "select e.entity_name from portfolios p join legal_entities e on e.id = p.legal_entity_id where p.id = ?", [str(row["portfolio_id"])]) if row.get("portfolio_id") else None
        title = ", ".join([what + (f" {ref}" if ref else "")] + [x for x in ((fund or {}).get("canonical_name"), (ent or {}).get("entity_name")) if x])
        fig["label"] = title
    return {"kind": kind, "id": rid, "title": title, "figure": fig, "steps": _fact_steps(plane, viewer, con, table, row)}


def _all_visible(plane, viewer, con) -> bool:
    from sh_platform.v1 import e1_access
    if e1_access.is_admin(viewer):
        return True
    return {str(r["id"]) for r in _rows(con, "select id from portfolios")} <= {str(x) for x in e1_access.visible_portfolios(plane, viewer)}


def _run_used_by(con, mv: dict, extra: list | None = None) -> dict:
    refs = list(extra or [])
    for rv in _rows(con, "select rv.id, rv.period_end, rv.status, r.report_name from report_versions rv join reports r on r.id = rv.report_id "
                         "where rv.calculation_run_id = ? order by rv.issued_at", [str(mv["calculation_run_id"])]):
        refs.append({"kind": "report_version", "id": str(rv["id"]), "label": f"{rv['report_name']} for {_date(rv['period_end'])} ({rv['status']})"})
    for pi in _rows(con, "select id, headline from pulse_items where metric_value_id = ? limit 5", [str(mv["id"])]):
        refs.append({"kind": "pulse_item", "id": str(pi["id"]), "label": f"Daily card: {pi['headline']}"})
    if not refs:
        return _missing("used_by", "Not used in any report or card yet.")
    return _step("used_by", "done", "Used in " + "; ".join(r["label"] for r in refs) + ".", refs=refs)


def _metric(plane, viewer, con, rid: str, extra_used: list | None = None) -> dict:
    mv = _one(con, "select * from metric_values where id = ?", [rid])
    if not mv:
        raise LookupError("We could not find that figure.")
    if mv.get("portfolio_id") or mv.get("instrument_id"):
        if not _may(plane, viewer, mv.get("portfolio_id"), mv.get("instrument_id")):
            raise PermissionError
    elif not _all_visible(plane, viewer, con):  # a company total is shown only to someone who can see every portfolio
        raise PermissionError
    run = _one(con, "select * from calculation_runs where id = ?", [str(mv["calculation_run_id"])])
    mdef = _one(con, "select metric_name from metric_definitions where id = ?", [str(mv["metric_definition_id"])])
    fig = _figure(con, mv, mv["numeric_value"], mv.get("currency"))
    calc = _step("stored", "done", f"Calculated by {run['code_version']} with a cut-off of {_date(run['knowledge_cutoff_at'])} "
                                   f"({mdef['metric_name'] if mdef else 'metric'}, status {mv['value_status']}; run {run['validation_status']}).",
                 None, run["finished_at"] or run["started_at"], [{"kind": "calculation_run", "id": str(run["id"]), "label": "Calculation run"}])
    ev = _rows(con, "select * from metric_evidence where metric_value_id = ? order by id", [rid])
    primary = next((e for e in ev if e.get("note") and ":" in e["note"] and e["note"].split(":", 1)[0] in AMOUNT), None)
    if primary:
        table, src_id = primary["note"].split(":", 1)
        row = _one(con, f"select * from {table} where id = ?", [src_id])  # table is whitelisted by the AMOUNT check above
        steps = _fact_steps(plane, viewer, con, table, row) if row else None
    else:
        steps = None
    if steps:
        by = _by_key(steps)
        others = [{"kind": "evidence", "id": str(e["id"]), "label": e["note"]} for e in ev if e is not primary and e.get("note")]
        by["source"]["refs"] += others
        if others:
            by["source"]["what"] += f" {len(others)} more input(s) also fed this figure."
        by["stored"] = calc
        by["used_by"] = _run_used_by(con, mv, extra_used)
        steps = [by[k] for k, _ in STEPS]
    else:  # a total or a figure with no source row of its own: it is added up from other lines
        parts = [] if mv.get("instrument_id") else _rows(
            con, "select id from metric_values where calculation_run_id = ? and id <> ? and instrument_id is not null", [str(mv["calculation_run_id"]), rid])
        src = _step("source", "done", f"Added up from {len(parts)} line(s) in the same calculation run.", None, run["started_at"],
                    [{"kind": "metric", "id": str(p["id"]), "label": "Line in this total"} for p in parts]) if parts else _missing("source", "The inputs of this figure were not recorded.")
        steps = [src, _missing("file", "Not read from a file of its own."), _missing("read", "Not read from a file of its own."),
                 _step("checked", "done" if run["validation_status"] == "passed" else "waiting", f"The calculation run's validation: {run['validation_status']}.", None, run["finished_at"]),
                 calc, _run_used_by(con, mv, extra_used)]
    return {"kind": "metric", "id": rid, "title": f"{fig['label']}, {mdef['metric_name'] if mdef else 'metric'}", "figure": fig, "steps": steps}


def _case(plane, viewer, con, rid: str) -> dict:
    ex = _one(con, "select * from exceptions where id = ?", [rid])
    if not ex:
        raise LookupError("We could not find that case.")
    if not _may(plane, viewer, ex.get("portfolio_id"), ex.get("instrument_id")):
        raise PermissionError
    me = [{"kind": "case", "id": rid, "label": f"Case: {ex['title']} ({ex['status']})"}]
    try:  # N1: a break or limit breach from a reconciliation run reads its steps from the run record
        from sh_platform.v1 import n1_tally
        recon = n1_tally.recon_trail(plane, rid)
    except Exception:  # noqa: BLE001 - the plain trail below still answers
        log.warning("the recon trail could not be built for case %s", rid, exc_info=True)
        recon = None
    if recon:
        return {"kind": "case", "id": rid, "title": ex["title"], "figure": None, "steps": [_step(*r) for r in recon]}
    if ex.get("exception_type") == "capital_call":     # a call is traced from its notice, not from the fund's last valuation
        from sh_platform.v1 import n1_tally
        call = (n1_tally.build(plane, ex).get("raw") or {}).get("call_id")
        if call:
            base = _fact(plane, viewer, con, "cash", call)
            return {"kind": "case", "id": rid, "title": ex["title"], "figure": base["figure"], "steps": base["steps"]}
        # never the fund's last valuation: that is a different figure
        steps = [_missing(k, "The call notice behind this case is not on file yet.") for k, _ in STEPS[:5]] + [_step("used_by", "done", me[0]["label"], refs=me)]
        return {"kind": "case", "id": rid, "title": ex["title"], "figure": None, "steps": steps}
    if ex.get("exception_type") == "revision" and ex.get("instrument_id"):
        got = _revision(plane, viewer, con, rid, ex, me)
        if got:
            return got
    imp = _one(con, "select metric_value_id from exception_impacts where exception_id = ? and metric_value_id is not null limit 1", [rid])
    base = None
    if imp:
        try:
            base = _metric(plane, viewer, con, str(imp["metric_value_id"]), me)
        except PermissionError:
            base = None
    if base is None and ex.get("instrument_id"):
        v = _one(con, "select id from valuation_observations where instrument_id = ? order by recorded_at desc limit 1", [str(ex["instrument_id"])])
        if v:
            base = _fact(plane, viewer, con, "valuation", str(v["id"]))
            base["steps"][5] = _used_by(con, "valuation_observations", str(v["id"]), ex["instrument_id"])
    steps = base["steps"] if base else [_missing(k, "Not recorded for this case.") for k, _ in STEPS[:5]] + [_step("used_by", "done", me[0]["label"], refs=me)]
    return {"kind": "case", "id": rid, "title": ex["title"], "figure": base["figure"] if base else None, "steps": steps}


def _revision(plane, viewer, con, rid: str, ex: dict, me: list) -> dict | None:
    """The newer statement's trail (the value the case is about), with the value the issued report used beside it."""
    from sh_platform.v1 import n1_tally
    facts = n1_tally.gather(plane, rid)
    if not facts["valuations"]:
        return None
    new = facts["valuations"][-1]
    base = _fact(plane, viewer, con, "valuation", str(new["id"]))
    imp = facts["impacts"][0] if facts["impacts"] else None
    if imp and imp.get("issued_value") is not None:
        base["figure"].update(was=_plain(imp["issued_value"]), was_label=f"used in {imp['report_name']}")
        base["steps"][4]["what"] = base["steps"][4]["what"].rstrip(".") + f"; the issued {imp['report_name']} used {_money(imp['issued_value'], imp['currency'])} and stays as issued."
    refs = list(me) + [{"kind": "report_version", "id": str(i["report_version_id"]), "label": f"{i['report_name']} for {_date(i['period_end'])} (issued, used the earlier value)"}
                       for i in facts["impacts"]]
    base["steps"][5] = _step("used_by", "done", "Used in " + "; ".join(r["label"] for r in refs) + ".", refs=refs)
    return {"kind": "case", "id": rid, "title": ex["title"], "figure": base["figure"], "steps": base["steps"]}


def _latest_plan(plane, pid: str) -> dict | None:
    best, n = None, -1
    for p in plane.path("build", pid).glob("plan-v*.json"):
        m = re.fullmatch(r"plan-v(\d+)\.json", p.name)
        if m and int(m.group(1)) > n:
            best, n = p, int(m.group(1))
    return json.loads(best.read_text(encoding="utf-8")) if best else None


def _last_run(plane, pid: str, plan_table: str) -> dict | None:
    f = plane.path("build", pid, "runs.jsonl")
    if not f.is_file():
        return None
    last = None
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("status") in ("ok", "succeeded", "success", "done", "finished") and any(s.get("table") == plan_table for s in r.get("steps", [])):
            last = r
    return last


def _tile(plane, viewer, rid: str) -> dict:
    root = plane.path("consume")
    found = None
    for f in root.glob("*/dashboards/*.json") if root.is_dir() else []:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        t = next((t for t in d.get("tiles", []) if t.get("id") == rid), None)
        if t:
            found = (d, t)
            break
    if not found:
        raise LookupError("We could not find that tile.")
    d, t = found
    from sh_platform.v1 import cx_dash  # the one audience rule: maker, admin, or named / group member with E1d access
    if not (_roles(viewer) & WORKERS or cx_dash.may_view(plane, viewer, d)):
        raise PermissionError
    pid = d["project_id"]
    plan = _latest_plan(plane, pid) or {}
    gold = [g for g in dict.fromkeys(re.findall(r"\bgold_\w+", t.get("sql") or "")) if any(x.get("name") == g for x in plan.get("tables", []))] or \
        list(dict.fromkeys(re.findall(r"\bgold_\w+", t.get("sql") or "")))
    tables = {x["name"]: x for x in plan.get("tables", [])}

    def upstream(name: str, seen: set) -> set:
        for dep in tables.get(name, {}).get("depends_on", []):
            if dep not in seen:
                seen.add(dep)
                upstream(dep, seen)
        return seen
    ups = set().union(*[upstream(g, set()) for g in gold]) if gold else set()
    bronze = sorted(n for n in ups if tables.get(n, {}).get("layer") == "bronze")
    warehouse = sorted(n for n in ups if n not in tables)
    if not bronze and warehouse:     # the gold tables read the warehouse, which the plan's sources fill; those sources landed as the plan's bronze tables
        bronze = sorted(n for n, x in tables.items() if x.get("layer") == "bronze")
    srcs = plan.get("sources", [])
    source = (_step("source", "done", "; ".join(f"{s.get('code')} ({s.get('kind')}, owner {s.get('owner') or 'not named'})" for s in srcs) + ".", None, None,
                    [{"kind": "source", "id": str(s.get("code")), "label": str(s.get("code"))} for s in srcs]) if srcs else _missing("source", "No build plan was found for this project."))
    file = _step("file", "done", "Landed as " + ", ".join(bronze) + (f", then loaded into the warehouse ({', '.join(w.replace('_', ' ') for w in warehouse)})" if warehouse else "")
                 + ".", None, None, [{"kind": "table", "id": b, "label": b} for b in bronze]) if bronze else \
        _missing("file", "The raw tables behind this tile are not recorded.")
    read = _step("read", "done", f"Built by the pipeline from plan version {plan.get('version')}, proposed by {plan.get('proposed_by') or 'Span'}.", "Span, the build agent") if plan else \
        _missing("read", "No build plan was found.")
    approved = plan.get("state") in ("approved", "built", "live")
    checked = (_step("checked", "done", "The head of data approved the plan.", plan.get("approved_by"), plan.get("approved_at")) if approved
               else _step("checked", "waiting", f"The plan is {plan.get('state', 'not approved')}; nobody has approved it yet.")) if plan else _missing("checked", "No approval is recorded.")
    run = _last_run(plane, pid, gold[0]) if gold else None
    step = next((s for s in (run or {}).get("steps", []) if gold and s.get("table") == gold[0]), {})
    stored = (_step("stored", "done", f"Stored in {gold[0]}" + (f", {step.get('rows')} rows, last built {_date(run.get('finished'))}." if run else "; it has not been built yet."), None,
                    (run or {}).get("finished"), [{"kind": "table", "id": g, "label": g} for g in gold]) if gold
              else _missing("stored", "This tile does not read a gold table."))
    n = len(d.get("audience", []))
    used = _step("used_by", "done", f"Tile \"{t.get('title')}\" ({t.get('state')}) on the dashboard \"{d.get('title')}\", shared with {n} {'person' if n == 1 else 'people'}.",
                 refs=[{"kind": "dashboard", "id": str(d.get("id")), "label": str(d.get("title"))}])
    return {"kind": "tile", "id": rid, "title": str(t.get("title")), "figure": {"label": str(t.get("kpi") or t.get("title")), "value": None, "currency": None},
            "steps": [source, file, read, checked, stored, used]}


# ---- entry ---------------------------------------------------------------------------------------------------------

def trail(plane, viewer, kind: str, item_id: str) -> dict:
    """The six-step trail for one figure. ValueError: unknown kind. LookupError: not found. PermissionError: not yours to see."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}")
    if kind == "tile":
        return _tile(plane, viewer, item_id)
    with wh.connect(plane, read_only=True) as con:
        if kind == "case":     # a case is reached by its id or by its number (CASE-0003), as the case page is
            from sh_platform.v1 import e4_cases
            item_id = e4_cases._resolve_ref(con, plane, item_id)
        rid = _uuid(item_id)
        if kind == "metric":
            return _metric(plane, viewer, con, rid)
        if kind == "case":
            return _case(plane, viewer, con, rid)
        return _fact(plane, viewer, con, kind, rid)
