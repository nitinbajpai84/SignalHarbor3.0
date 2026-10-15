"""K2 Office view: holdings, the latest issued report against what is known now, the NAV bridge and the liquidity forecast.

Every figure is read from the warehouse (E3d calc library, E1c reports, E1d access) and copied by the program; nothing is
computed by a model. Each figure carries a `where` block so the screen can answer "Where is this from?".

NAV bridge identity (exact, Decimal): investment view total - administrator NAV = fx + timing + revisions + unexplained, where
  fx          = the same holdings valued at today's rate instead of the rate on the NAV date
  timing      = valuations dated after the NAV date
  revisions   = valuations recorded after the administrator struck the NAV (restated, or arrived late)
  unexplained = what is left when the view as known when the NAV was struck is set against the NAV
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sh_platform.v1 import scope_memo
from sh_platform.v1.scope_memo import memo
from sh_platform.v1 import wh

log = logging.getLogger(__name__)
STALE_DAYS = 90
FRESH = ("official", "revised", "estimated")
ZERO = Decimal(0)
NEEDS_CLASS = "Needs a class"  # no asset class: a classification question, whatever the data status


def _s(v):
    return str(v) if isinstance(v, uuid.UUID) else v


def _rows(con, sql: str, params: list) -> list[dict]:
    cur = con.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [{c: _s(v) for c, v in zip(cols, r)} for r in cur.fetchall()]


def _calc():
    from sh_platform.v1 import e3_calc
    return e3_calc


def _day(as_of) -> date:
    if as_of is None:
        return wh.now().date()
    return as_of if isinstance(as_of, date) and not isinstance(as_of, datetime) else date.fromisoformat(str(as_of)[:10])


@memo
def _portfolios(plane, viewer) -> tuple[list[dict], bool]:
    """(portfolios the viewer may see, whether some are hidden). Fails closed when access cannot be read."""
    from sh_platform.v1 import e1_access
    allowed = {str(a) for a in e1_access.visible_portfolios(plane, viewer)}
    with wh.connect(plane, read_only=True) as con:
        rows = _rows(con, "select p.id, p.portfolio_code, p.portfolio_name, p.base_currency, p.legal_entity_id, e.entity_name"
                          " from portfolios p left join legal_entities e on e.id = p.legal_entity_id order by e.entity_name, p.portfolio_name", [])
    keep = [r for r in rows if r["id"] in allowed]
    return keep, len(keep) < len(rows)


# ---- where is this from -----------------------------------------------------------------------------------------------

_DOC = "select id, title, document_status from documents where id {}"
_FIELD = "select id, page_number, line_number from extracted_fields where id {}"
_SRC = ("select x.id as id, s.source_name from source_records x join source_batches b on b.id = x.source_batch_id"
        " join source_systems s on s.id = b.source_system_id where x.id {}")


def _lookup(con, kind: str, sql: str, key) -> dict | None:
    """One row by id, remembered for the rest of the request (the same statement, page or file backs many figures)."""
    st = scope_memo.store(kind)
    if st is not None and key in st:
        return st[key]
    got = (_rows(con, sql.format("= ?"), [key]) or [None])[0]
    if st is not None:
        st[key] = got
    return got


def _fill(con, kind: str, sql: str, ids: list[str]) -> None:
    st = scope_memo.store(kind)
    todo = [i for i in dict.fromkeys(ids) if i and i not in st]
    for r in (_rows(con, sql.format(f"in ({','.join('?' * len(todo))})"), todo) if todo else []):
        st[r["id"]] = r
    for i in todo:
        st.setdefault(i, None)


def prefetch_sources(con, row_ids: list[str]) -> None:
    """Read the rows behind many figures, and the statements, pages and files they name, in five queries instead of one set per figure.
    Inside a request scope only; elsewhere each figure looks itself up, as before."""
    st = scope_memo.store("src")
    if st is None:
        return
    todo = [i for i in dict.fromkeys(row_ids) if i and i not in st]
    if not todo:
        return
    marks = ",".join("?" * len(todo))
    for table in ("valuation_observations", "position_snapshots"):
        for r in _rows(con, f"select * from {table} where id in ({marks})", todo):  # table from the fixed pair above
            st.setdefault(r["id"], (table, r))
    rows = [st[i][1] for i in todo if st.get(i)]
    for i in todo:
        st.setdefault(i, None)
    _fill(con, "doc", _DOC, [r.get("evidence_document_id") for r in rows])
    _fill(con, "field", _FIELD, [r.get("extracted_field_id") for r in rows])
    _fill(con, "srcname", _SRC, [r.get("source_record_id") for r in rows])


def _source_row(con, row_id: str) -> tuple[str, dict] | None:
    st = scope_memo.store("src")
    if st is not None and row_id in st:
        return st[row_id]
    got = None
    for table in ("valuation_observations", "position_snapshots"):
        r = _rows(con, f"select * from {table} where id = ?", [row_id])  # table from the fixed pair above
        if r:
            got = table, r[0]
            break
    if st is not None:
        st[row_id] = got
    return got


def _where(con, row_id: str | None) -> dict:
    """What the figure came from, in words: the statement page for a manager valuation, the file for an administrator position."""
    got = _source_row(con, row_id) if row_id else None
    if got is None:
        return {"table": None, "row_id": row_id, "text": "No source record was found for this figure."}
    table, r = got
    if table == "valuation_observations":
        doc = fld = None
        if r.get("evidence_document_id"):
            doc = _lookup(con, "doc", _DOC, r["evidence_document_id"])
        if r.get("extracted_field_id"):
            fld = _lookup(con, "field", _FIELD, r["extracted_field_id"])
        kind = "Manager valuation" if str(r["valuation_type"]).startswith("manager") else "Valuation"
        text = f"{kind} dated {r['valuation_date']:%d %b %Y}"
        if doc:
            text += f", from the statement \"{doc['title']}\"" + (f", page {fld['page_number']}, line {fld['line_number']}" if fld and fld.get("page_number") else "")
        return {"table": table, "row_id": r["id"], "text": text, "document_id": doc and doc["id"], "document_title": doc and doc["title"],
                "page": fld and fld.get("page_number"), "line": fld and fld.get("line_number"), "received_at": r["received_at"],
                "recorded_at": r["recorded_at"], "approval_status": r["approval_status"], "as_of": r["valuation_date"]}
    src = None
    if r.get("source_record_id"):
        src = _lookup(con, "srcname", _SRC, r["source_record_id"])
    text = f"Position dated {r['position_date']:%d %b %Y}" + (f" from {src['source_name']}" if src else " from the loaded position file")
    return {"table": table, "row_id": r["id"], "text": text, "document_id": None, "document_title": None, "page": None, "line": None,
            "received_at": r["received_at"], "recorded_at": r["recorded_at"], "approval_status": r["data_status"], "as_of": r["position_date"]}


def _status(raw: str, as_of, day: date) -> str:
    """Stale beats official/revised/estimated once the value is older than STALE_DAYS; unverified stays unverified."""
    if raw in FRESH and as_of is not None and (day - (as_of if isinstance(as_of, date) else date.fromisoformat(str(as_of)[:10]))).days > STALE_DAYS:
        return "stale"
    return raw


# ---- holdings ---------------------------------------------------------------------------------------------------------

@memo
def holdings(plane, viewer, currency: str = "USD", as_of=None) -> dict:
    """Per entity and portfolio: each holding with value, status word and source. Totals only where everything under them is
    visible and convertible."""
    C, cur, day = _calc(), currency.upper(), _day(as_of)
    pfs, partial = _portfolios(plane, viewer)
    ents: dict[str, dict] = {}
    with wh.connect(plane, read_only=True) as con:
        names = {r["id"]: r["canonical_name"] for r in _rows(con, "select id, canonical_name from instruments", [])}
        classes = {r["id"]: (r["asset_class"] or "").strip() or None for r in _rows(con, "select id, asset_class from instruments", [])}
        all_by_ent: dict[str, int] = {r["legal_entity_id"]: r["n"] for r in _rows(con, "select legal_entity_id, count(*) as n from portfolios group by 1", [])}
        hidden = _containers(con)
    for pf in pfs:
        pv = C.portfolio_value(plane, pf["id"], day, None, cur)
        lines = []
        with wh.connect(plane, read_only=True) as con:
            prefetch_sources(con, [l["source_row_id"] for l in pv["lines"]])
            for l in pv["lines"]:
                if l["instrument_id"] in hidden and not l["value"]:
                    continue  # the liquid book's own zero line: its securities carry the value
                w = _where(con, l["source_row_id"])
                src = _source_row(con, l["source_row_id"])
                native = {"amount": None, "currency": None}
                if src:
                    t, r = src
                    native = {"amount": r["value_amount"] if t == "valuation_observations" else r["source_market_value"], "currency": r["currency"]}
                ac, st = classes.get(l["instrument_id"]), _status(l["status"], w.get("as_of"), day)
                lines.append({"instrument_id": l["instrument_id"], "name": names.get(l["instrument_id"], "Unnamed holding"), "value": l["value"],
                              "currency": cur, "native": native, "asset_class": ac, "data_status": st, "status": st if ac else NEEDS_CLASS,
                              "source": w["text"], "where": w})
        e = ents.setdefault(pf["legal_entity_id"], {"entity_id": pf["legal_entity_id"], "entity_name": pf["entity_name"] or "No entity", "portfolios": []})
        e["portfolios"].append({"portfolio_id": pf["id"], "portfolio_name": pf["portfolio_name"], "currency": cur, "total": pv["total"],
                                "lines": lines, "message": "; ".join(dict.fromkeys(pv["problems"])) or None})
    out = list(ents.values())
    for e in out:
        full = len(e["portfolios"]) == all_by_ent.get(e["entity_id"], 0) and all(p["total"] is not None for p in e["portfolios"])
        e["total"] = sum((p["total"] for p in e["portfolios"]), ZERO) if full else None
    company = None if partial or not out or any(e["total"] is None for e in out) else sum((e["total"] for e in out), ZERO)
    rates = []  # UC1-C2-07: name the rate behind every converted figure, as the issued report does
    for ccy in sorted({l["native"]["currency"] for e in out for p in e["portfolios"] for l in p["lines"]} - {cur, None}):
        rate, why = C.fx_explained(plane, ccy, cur, day, None)
        if rate is not None:
            rates.append(f"{ccy} to {cur} at {rate.normalize():f} ({why})")
    return {"currency": cur, "as_of": day, "entities": out, "total": company, "partial": partial,
            "rate_note": f"Converted at the latest rate: {'; '.join(rates)}." if rates else None,
            "stale_after_days": STALE_DAYS, "calc_version": C.CALC_VERSION}


# ---- issued versus known now ------------------------------------------------------------------------------------------

def _stamp(t) -> str:
    """'3 Oct 2026, 18:30 (UTC+08:00)': the time as stamped, with its offset (as the CIO Brief shows it)."""
    if not isinstance(t, datetime):
        return f"{t:%d %b %Y}".lstrip("0") if isinstance(t, date) else str(t or "")
    z = t.strftime("%z") or "+0000"
    return f"{t:%d %b %Y, %H:%M}".lstrip("0") + f" (UTC{z[:3]}:{z[3:]})"


@memo
def issued_vs_known(plane, viewer, currency: str | None = None) -> dict:
    """The latest issued report, as issued beside as known now (E5b), with the link to the full CIO Brief."""
    from sh_platform.v1 import e1_reports, e5_brief
    issued = [(v, r) for r in e1_reports.listing(plane) for v in r["versions"] if v["status"] == "issued"]
    if not issued:
        return {"report": None, "message": "No report has been issued yet."}
    v, r = max(issued, key=lambda x: str(x[0]["issued_at"]))
    b = e5_brief.brief(plane, viewer, v["id"], currency or None)
    when = (f"issued {_stamp(b['issued_at'])}" if b.get("issued_at") else "") + (f", data cutoff {_stamp(b['cutoff_at'])}" if b.get("cutoff_at") else "")
    text = f"The report \"{b['report_name']}\"" + (f" as {when}" if when else "") + ", compared with what the company knows now."
    src, rate_note = (b["currencies"] or [None])[0], None
    if src and b["currency"] and b["currency"] != src:  # figures shown in another currency: name the rate used
        rate, why = _calc().fx_explained(plane, src, b["currency"], b["period_end"], b["cutoff_at"])
        if rate is not None:
            rate_note = f"Converted from {src} to {b['currency']} at {rate.normalize():f} ({why})."
            text += " " + rate_note
    return {"report": {"report_version_id": v["id"], "name": b["report_name"], "period_end": b["period_end"], "issued_at": b["issued_at"],
                       "cutoff_at": b.get("cutoff_at"), "when": when[:1].upper() + when[1:] if when else None},
            "lines": b["lines"], "banner": b["banner"] and b["banner"].replace(" lines below show ", " report lines show ", 1).replace("1 line below shows ", "1 report line shows ", 1), "currency": b["currency"], "currencies": b["currencies"],
            "currency_message": b["currency_message"], "partial": b["partial"], "brief_link": f"/centre/consume/brief/{v['id']}",
            "rate_note": rate_note, "where": {"text": text}}


# ---- NAV bridge -------------------------------------------------------------------------------------------------------

def _values(plane, pid: str, on: date, cutoff, cur: str) -> tuple[dict[str, Decimal], dict[str, str], list[str]]:
    pv = _calc().portfolio_value(plane, pid, on, cutoff, cur)
    return ({l["instrument_id"]: l["value"] for l in pv["lines"] if l["value"] is not None},
            {l["instrument_id"]: l["source_row_id"] for l in pv["lines"]}, pv["problems"])


def _sum(d: dict) -> Decimal:
    return sum(d.values(), ZERO)


def _latest_nav(plane, pid: str, day: date) -> dict | None:
    # own copy of the "known now and not superseded" query, so a change inside e3_calc cannot break the bridge
    with wh.connect(plane, read_only=True) as con:
        rows = _rows(con, "select * from nav_snapshots t where t.portfolio_id = ? and t.nav_period_end <= ? and t.recorded_at <= ? "
                          "and not exists (select 1 from nav_snapshots n where n.supersedes_nav_id = t.id and n.recorded_at <= ?)",
                     [pid, day, wh.now(), wh.now()])
    return max(rows, key=lambda r: (r["nav_period_end"], r["recorded_at"])) if rows else None


def _line_currency(con, src: tuple[str, dict], day: date) -> str:
    """The currency e3_calc.portfolio_value priced this line in: the row's own, except a quantity-only position, which takes the latest price's base currency."""
    table, r = src
    if table == "position_snapshots" and r.get("source_market_value") is None and r.get("quantity") is not None:
        px = _rows(con, "select base_currency, observed_at from market_observations t where t.observation_type = 'price' and t.instrument_id = ? "
                        "and t.observed_at <= ? and t.recorded_at <= ? and not exists (select 1 from market_observations n "
                        "where n.supersedes_observation_id = t.id and n.recorded_at <= ?)",
                   [r["instrument_id"], datetime.combine(day, datetime.max.time(), tzinfo=timezone.utc), wh.now(), wh.now()])
        if px:
            return max(px, key=lambda x: x["observed_at"])["base_currency"] or r["currency"]
    return r["currency"]


def _delta_evidence(con, ids: dict[str, str], names: dict[str, str], keys: set[str], label: str) -> list[dict]:
    out = []
    for k in sorted(keys):
        w = _where(con, ids.get(k))
        out.append({"label": f"{names.get(k, 'A holding')}: {label}", "table": w["table"], "row_id": w["row_id"], "text": w["text"]})
    return out


def _bridge_one(plane, pf: dict, cur: str, day: date, names: dict) -> dict:
    C = _calc()
    base = {"portfolio_id": pf["id"], "portfolio_name": pf["portfolio_name"], "entity_name": pf["entity_name"], "currency": cur}
    nav = _latest_nav(plane, pf["id"], day)
    if nav is None:
        return {**base, "available": False, "message": "No administrator NAV has been received for this portfolio yet."}
    n_day, n_cut = nav["nav_period_end"], nav["recorded_at"]
    rate, why = C.fx_explained(plane, nav["currency"], cur, n_day, None)
    if rate is None:
        return {**base, "available": False, "message": why}
    admin = Decimal(str(nav["nav_amount"])) * rate
    v_asof, ids_asof, p1 = _values(plane, pf["id"], day, None, cur)
    v_n_now, ids_n, p2 = _values(plane, pf["id"], n_day, None, cur)
    v_n_nav, ids_nav, p3 = _values(plane, pf["id"], n_day, n_cut, cur)
    problems = list(dict.fromkeys(p1 + p2 + p3))
    if problems:
        return {**base, "available": False, "message": "; ".join(problems)}
    # holdings at the as-of date, re-expressed at the rate on the NAV date (isolates the exchange-rate part)
    v_asof_nr: dict[str, Decimal] = {}
    fx_notes: list[str] = []
    with wh.connect(plane, read_only=True) as con:
        prefetch_sources(con, list(ids_asof.values()))
        for k, v in v_asof.items():
            src = _source_row(con, ids_asof[k])
            ccy = _line_currency(con, src, day) if src else cur
            r_now, r_then = C.fx(plane, ccy, cur, day, None), C.fx(plane, ccy, cur, n_day, None)
            if not r_now or r_then is None:
                return {**base, "available": False, "message": f"No signed exchange rate for {ccy} to {cur} on {day} and {n_day}."}
            v_asof_nr[k] = v * r_then / r_now
            if r_then != r_now and f"{ccy}>{cur}" not in fx_notes:
                fx_notes.append(f"{ccy}>{cur}")
        A, a_nr, a_n, a_nav = _sum(v_asof), _sum(v_asof_nr), _sum(v_n_now), _sum(v_n_nav)
        fx, timing, revisions, unexplained = A - a_nr, a_nr - a_n, a_n - a_nav, a_nav - admin
        diff = A - admin
        keys = set(v_asof) | set(v_n_now) | set(v_n_nav)
        rev_keys = {k for k in keys if v_n_now.get(k, ZERO) != v_n_nav.get(k, ZERO)}
        tim_keys = {k for k in keys if v_asof_nr.get(k, ZERO) != v_n_now.get(k, ZERO)}
        nav_ev = {"label": f"Administrator NAV for {n_day:%d %b %Y}", "table": "nav_snapshots", "row_id": nav["id"],
                  "text": f"Administrator NAV {nav['nav_amount']:,.2f} {nav['currency']} for {n_day:%d %b %Y}, received {nav['received_at']:%d %b %Y}, status {nav['nav_status']}"}
        parts = [
            {"code": "revisions", "label": "Revisions", "amount": revisions,
             "plain": "Valuations that were recorded after the administrator struck this NAV.",
             "evidence": _delta_evidence(con, ids_n, names, rev_keys, "revised since the NAV was struck")},
            {"code": "timing", "label": "Timing (valuation date)", "amount": timing,
             "plain": f"Valuations dated after the NAV date of {n_day:%d %b %Y}.",
             "evidence": _delta_evidence(con, ids_asof, names, tim_keys, "dated after the NAV date")},
            {"code": "fx", "label": "Exchange rates", "amount": fx,
             "plain": (f"The same holdings valued at the rate on {day:%d %b %Y} instead of the rate on {n_day:%d %b %Y}." if day != n_day
                       else "The report date and the NAV date are the same, so exchange rates play no part."),
             "evidence": [{"label": f"Rate {p}", "table": "market_observations", "row_id": None,
                           "text": f"{C.fx_explained(plane, p.split('>')[0], cur, n_day, None)[1]}; {C.fx_explained(plane, p.split('>')[0], cur, day, None)[1]}"} for p in fx_notes]},
            {"code": "unexplained", "label": "Unexplained", "amount": unexplained,
             "plain": "What is left after the three parts above. No record explains it yet." if unexplained else "Nothing is left unexplained.",
             "evidence": [nav_ev]},
        ]
    return {**base, "available": True, "as_of": day, "nav_date": n_day, "investment_total": A, "administrator_nav": admin, "nav_status": nav["nav_status"],
            "difference": diff, "parts": parts, "where": {"text": nav_ev["text"], "table": "nav_snapshots", "row_id": nav["id"]}}


@memo
def nav_bridge(plane, viewer, currency: str = "USD", as_of=None) -> dict:
    cur, day = currency.upper(), _day(as_of)
    pfs, partial = _portfolios(plane, viewer)
    with wh.connect(plane, read_only=True) as con:
        names = {r["id"]: r["canonical_name"] for r in _rows(con, "select id, canonical_name from instruments", [])}
    return {"currency": cur, "as_of": day, "partial": partial, "portfolios": [_bridge_one(plane, p, cur, day, names) for p in pfs]}


# ---- liquidity --------------------------------------------------------------------------------------------------------

@memo
def liquidity(plane, viewer, currency: str = "USD", as_of=None) -> dict:
    """Per entity: available cash, calls and distributions due in 30/60/90 days, cash after the calls, uncalled commitment and the
    calls not confirmed yet. Read from card K4's `k6_liquidity.forecast(plane, as_of, viewer=, currency=)`; until that is installed
    the screen says commitments are not loaded."""
    cur, day = currency.upper(), _day(as_of)
    try:
        from sh_platform.v1 import k6_liquidity
        data = k6_liquidity.forecast(plane, day, viewer=viewer, currency=cur)
    except (ImportError, AttributeError):
        log.warning("k6_liquidity.forecast is not installed; the liquidity forecast is empty")
        return {"available": False, "currency": cur, "as_of": day,
                "message": "Commitments and capital calls are not loaded yet, so there is no liquidity forecast."}
    return {"available": True, "currency": cur, "as_of": day, **data}


# ---- why did this move ------------------------------------------------------------------------------------------------

BUY, SELL = {"buy", "purchase", "subscription", "contribution"}, {"sell", "sale", "redemption", "withdrawal"}


def _scope(plane, viewer, portfolio_id, book):
    pfs, partial = _portfolios(plane, viewer)
    if portfolio_id:
        pfs = [p for p in pfs if p["id"] == portfolio_id]
    elif book:
        pfs = [p for p in pfs if book.lower() in f"{p['portfolio_code']} {p['portfolio_name']}".lower()]
    return pfs, partial


def _containers(con) -> set[str]:
    """Roll-up instruments (a liquid book carried by its securities): a zero line for one is not a holding."""
    return {r["id"] for r in _rows(con, "select id from instruments where instrument_type = 'liquid_book'", [])}


def _first_values(con, plane, ids: dict, now: dict, day: date, cur: str) -> dict:
    """For each line, the value first recorded for the same date, when a later row replaced it (superseding it or not), in `cur`.
    A month-end value recorded a few days later is not a revision; only a second value for the same date is.
    ponytail: a quantity-only position (priced from market data) is never counted as revised."""
    out = {}
    for k, rid in ids.items():
        got = _source_row(con, rid) if k in now else None
        if not got:
            continue
        table, r = got
        if table == "valuation_observations":
            first = _rows(con, "select value_amount as amount, currency, recorded_at from valuation_observations where portfolio_id = ? "
                               "and instrument_id = ? and valuation_date = ? order by recorded_at, id limit 1",
                          [r["portfolio_id"], r["instrument_id"], r["valuation_date"]])
        else:
            first = _rows(con, "select source_market_value as amount, currency, recorded_at from position_snapshots where portfolio_id = ? "
                               "and instrument_id = ? and position_date = ? and view_type = ? order by recorded_at, id limit 1",
                          [r["portfolio_id"], r["instrument_id"], r["position_date"], r["view_type"]])
        if not first or first[0]["recorded_at"] >= r["recorded_at"] or first[0]["amount"] is None:
            continue
        rate = _calc().fx(plane, first[0]["currency"], cur, day, None)  # the rate portfolio_value used for the line
        if rate is not None:
            out[k] = Decimal(str(first[0]["amount"])) * rate
    return out


def _big(lines: list[dict]) -> list[dict]:
    return sorted(lines, key=lambda x: (-abs(x["amount"]), x["label"]))


@memo
def why_moved(plane, viewer, start, end, currency: str = "USD", portfolio_id: str | None = None, book: str | None = None) -> dict:
    """Value at `start` and `end` (month-ends), the change and its percentage (Decimal, program arithmetic), split into
    price moves per instrument, trades in the period, revisions and exchange rates; the four parts add up to the change exactly.
      fx        = end value minus the same holdings at the rate on the start date
      revisions = a later value for the same date that replaced the first one recorded (a month-end value recorded days later is not one)
      trades    = signed cash of buys and sells of instruments held in the book; other trades (an FX forward) are listed, no effect on value
      price     = what is left per instrument
    ponytail: a trade's effect is its cash amount, not quantity times price; refine if partial-period fills matter."""
    C, cur, d0, d1 = _calc(), currency.upper(), _day(start), _day(end)
    if d0 >= d1:
        raise ValueError("start must be before end")
    pfs, partial = _scope(plane, viewer, portfolio_id, book)
    base = {"currency": cur, "start": d0, "end": d1, "partial": partial, "calc_version": C.CALC_VERSION}
    if not pfs:
        return {**base, "available": False, "message": "There is no portfolio to explain."}
    with wh.connect(plane, read_only=True) as con:
        names = {r["id"]: r["canonical_name"] for r in _rows(con, "select id, canonical_name from instruments", [])}
    s_now, e_now, ids_e, ids_s, problems = {}, {}, {}, {}, []
    for pf in pfs:
        for tgt, ids, on in ((s_now, ids_s, d0), (e_now, ids_e, d1)):
            v, i, pr = _values(plane, pf["id"], on, None, cur)
            tgt.update({(pf["id"], k): x for k, x in v.items()})
            ids.update({(pf["id"], k): x for k, x in i.items()})
            problems += pr
    if problems:
        return {**base, "available": False, "message": "; ".join(dict.fromkeys(problems))}
    with wh.connect(plane, read_only=True) as con:
        hidden = _containers(con)
        prefetch_sources(con, [*ids_s.values(), *ids_e.values()])
        s_kn, e_kn = _first_values(con, plane, ids_s, s_now, d0, cur), _first_values(con, plane, ids_e, e_now, d1, cur)
    s_now, e_now = ({k: v for k, v in d.items() if not (k[1] in hidden and not v)} for d in (s_now, e_now))
    keys = set(s_now) | set(e_now)
    pids = [p["id"] for p in pfs]
    held = {k[1] for k in keys}
    with wh.connect(plane, read_only=True) as con:
        trades = C._live(con, plane, "transactions", "supersedes_transaction_id", wh.now(),
                         f"t.portfolio_id in ({', '.join('?' * len(pids))}) and coalesce(t.trade_date, t.effective_date) > ? "
                         "and coalesce(t.trade_date, t.effective_date) <= ?", [*pids, d0, d1])
        fx_amt: dict = {}
        fx_ccy: dict = {}
        for k in keys:
            src = _source_row(con, ids_e[k]) if k in ids_e else None
            if e_now.get(k) and src:
                ccy = _line_currency(con, src, d1)
                r1, r0 = C.fx(plane, ccy, cur, d1, None), C.fx(plane, ccy, cur, d0, None)
                if not r1 or r0 is None:
                    return {**base, "available": False, "message": f"No signed exchange rate for {ccy} to {cur} on {d0} and {d1}."}
                fx_amt[k], fx_ccy[k] = e_now[k] - e_now[k] * r0 / r1, ccy
        tr_lines, tr_eff, seen = [], {}, set()
        for t in sorted(trades, key=lambda x: (str(x["trade_date"] or x["effective_date"]), x["id"])):
            ref = (t["portfolio_id"], t["external_trade_id"]) if t["external_trade_id"] else None
            if ref and ref in seen:  # one trade arrives from each source system (trading export and administrator); count it once
                continue
            if ref:
                seen.add(ref)
            on = t["trade_date"] or t["effective_date"]
            rate = C.fx(plane, t["currency"] or cur, cur, on, None)
            amt = None if rate is None or t["cash_amount"] is None else Decimal(str(t["cash_amount"])) * rate
            kind = str(t["transaction_type"]).lower()
            eff = ZERO
            if amt is not None and t["instrument_id"] in held and (kind in BUY or kind in SELL):
                eff = abs(amt) if kind in BUY else -abs(amt)
                key = (t["portfolio_id"], t["instrument_id"])
                tr_eff[key] = tr_eff.get(key, ZERO) + eff
            nm = names.get(t["instrument_id"], "A holding")
            plain = f"{kind.replace('_', ' ').capitalize()} of {nm} on {on:%d %b %Y}" \
                + (f", {abs(amt):,.2f} {cur}" if amt is not None else ", no exchange rate to show an amount") \
                + ("." if eff else ", which does not change the value of the holdings.")
            tr_lines.append({"label": nm, "amount": eff, "plain": plain,
                             "evidence": [{"label": "Trade", "table": "transactions", "row_id": _s(t["id"]), "document_id": None,
                                           "text": f"{kind.replace('_', ' ').capitalize()} {t['external_trade_id'] or ''} dated {on:%d %b %Y}".replace("  ", " ")
                                                   + (f", {Decimal(str(t['cash_amount'])):,.2f} {t['currency'] or cur}" if t["cash_amount"] is not None else "")}]})
        price, rev = [], []
        for k in keys:
            rv = (e_now.get(k, ZERO) - e_kn.get(k, e_now.get(k, ZERO))) - (s_now.get(k, ZERO) - s_kn.get(k, s_now.get(k, ZERO)))
            pm = e_now.get(k, ZERO) - s_now.get(k, ZERO) - rv - fx_amt.get(k, ZERO) - tr_eff.get(k, ZERO)
            nm = names.get(k[1], "A holding")
            ev = []
            for tag, ids in (("end", ids_e), ("start", ids_s)):
                if k in ids:
                    w = _where(con, ids[k])
                    ev.append({"label": f"{nm}, {tag}", "table": w["table"], "row_id": w["row_id"], "text": w["text"], "document_id": w.get("document_id")})
            if pm:
                price.append({"label": nm, "amount": pm, "start_value": s_now.get(k), "end_value": e_now.get(k), "evidence": ev,
                              "plain": f"{nm} moved from {s_now.get(k, ZERO):,.2f} to {e_now.get(k, ZERO):,.2f} {cur}."})
            if rv:
                rev.append({"label": nm, "amount": rv, "evidence": ev, "plain": "A later value for the same date replaced the one first recorded."})
        fx_lines = [{"label": names.get(k[1], "A holding"), "amount": a, "plain": f"Valued at the rate on {d1:%d %b %Y} instead of the rate on {d0:%d %b %Y}.",
                     "evidence": [{"label": "Rate", "table": "market_observations", "row_id": None, "document_id": None,
                                   "text": f"{C.fx_explained(plane, fx_ccy[k], cur, d0, None)[1]}; {C.fx_explained(plane, fx_ccy[k], cur, d1, None)[1]}"}]}
                    for k, a in fx_amt.items() if a]
    parts = [{"code": c, "label": lab, "amount": sum((x["amount"] for x in ls), ZERO), "lines": ls if c == "trades" else _big(ls)}
             for c, lab, ls in (("price", "Price moves", price), ("trades", "Trades in the period", tr_lines),
                                ("revisions", "Revisions", rev), ("fx", "Exchange rates", fx_lines))]
    a, b = _sum(s_now), _sum(e_now)
    return {**base, "available": True, "portfolios": [p["portfolio_name"] for p in pfs], "start_value": a, "end_value": b, "change": b - a,
            "percent": ((b - a) / a * 100).quantize(Decimal("0.0001")) if a else None, "parts": parts,
            "largest": _big(price)[0]["label"] if price else None,
            "message": f"{len(tr_lines)} trade(s) in the period are listed." if tr_lines else "There were no trades in the period."}
