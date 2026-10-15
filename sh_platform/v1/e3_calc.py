"""E3d calculation library: deterministic Decimal arithmetic for FX and portfolio value, as known at a cutoff.

A row counts at a cutoff when recorded_at <= cutoff and no row superseding it was recorded by then (same rule as E1a;
done here in one small query so this card stands alone). Money is never computed by a model.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sh_platform.v1.scope_memo import memo
from sh_platform.v1 import wh

log = logging.getLogger(__name__)
CALC_VERSION = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
_STATUS = {"official": "official", "estimated": "estimated", "indicative": "unverified"}


def _cutoff(c) -> datetime:
    """None = now; a plain date = the end of that day (UTC)."""
    if c is None:
        return wh.now()
    if isinstance(c, datetime):
        return c if c.tzinfo else c.replace(tzinfo=timezone.utc)
    return datetime.combine(c, time.max, tzinfo=timezone.utc)


def _live(con, plane, table, sup_col, cutoff, where: str, args: list) -> list[dict]:
    """Rows of `table` (one warehouse file per company, so no organization filter) known at `cutoff` and not superseded by then."""
    cur = con.execute(
        f"select * from {table} t where t.recorded_at <= ? and ({where}) "
        f"and not exists (select 1 from {table} n where n.{sup_col} = t.id and n.recorded_at <= ?)",
        [cutoff, *args, cutoff])
    cols = [d[0] for d in cur.description]
    return [{c: str(v) if isinstance(v, uuid.UUID) else v for c, v in zip(cols, r)} for r in cur.fetchall()]


def _dec(x) -> Decimal:
    return Decimal(str(x))


@memo
def fx_explained(plane, from_ccy: str, to_ccy: str, on_date: date, cutoff=None) -> tuple[Decimal | None, str]:
    """(rate, reason). Rate converts one unit of from_ccy to to_ccy; None comes with the reason in plain words."""
    f, t = from_ccy.upper(), to_ccy.upper()
    if f == t:
        return Decimal(1), "same currency"
    try:
        from sh_platform.v1 import e3_rules
        rule = e3_rules.current(plane, "fx_fixing", on_date)
    except ImportError:
        log.warning("e3_rules is not installed; cannot read the fx_fixing rule")
        raise
    if not rule:
        return None, f"No signed fx_fixing rule applies on {on_date}, so {f} to {t} cannot be converted."
    fixing = str((rule.get("parameters") or {}).get("fixing", "")).strip()
    if not fixing:
        return None, "The signed fx_fixing rule does not name a fixing."
    cut = _cutoff(cutoff)
    end = datetime.combine(on_date, time.max, tzinfo=timezone.utc)
    with wh.connect(plane, read_only=True) as con:
        rows = _live(con, plane, "market_observations", "supersedes_observation_id", cut,
                     "t.observation_type = 'fx' and t.observed_at <= ? and t.series_key like ?", [end, f"%{fixing}%"])
    best: tuple | None = None
    for r in rows:
        b, q = r["base_currency"], r["quote_currency"]
        if (b, q) == (f, t):
            rate = _dec(r["value"])
        elif (b, q) == (t, f) and _dec(r["value"]) != 0:
            rate = Decimal(1) / _dec(r["value"])
        else:
            continue
        if best is None or r["observed_at"] > best[0]:
            best = (r["observed_at"], rate)
    if best is None:
        return None, f"No {fixing} rate for {f} to {t} on or before {on_date} was known by the cutoff."
    return best[1], f"{fixing} fixing observed {best[0].day} {best[0]:%b %Y}"


def fx(plane, from_ccy: str, to_ccy: str, on_date: date, cutoff=None) -> Decimal | None:
    rate, why = fx_explained(plane, from_ccy, to_ccy, on_date, cutoff)
    if rate is None:
        log.info("fx unavailable: %s", why)
    return rate


def _val_status(r: dict) -> str:
    if r["valuation_type"] == "manager_estimate":
        return "estimated"
    if r["approval_status"] not in ("approved", "approved_official", "confirmed"):
        return "unverified"
    return "revised" if r["supersedes_valuation_id"] else "official"


@memo
def portfolio_value(plane, portfolio_id: str, as_of_date: date, cutoff=None, currency: str = "USD") -> dict:
    """{total, lines, calc_version, problems}. Per instrument: the latest valuation on or before as_of_date, else the latest
    position (market value, or quantity times the latest price). total is None when any line cannot be converted."""
    cut = _cutoff(cutoff)
    end = datetime.combine(as_of_date, time.max, tzinfo=timezone.utc)
    lines: list[dict] = []
    problems: list[str] = []
    with wh.connect(plane, read_only=True) as con:
        vals = _live(con, plane, "valuation_observations", "supersedes_valuation_id", cut,
                     "t.portfolio_id = ? and t.valuation_date <= ?", [portfolio_id, as_of_date])
        pos = _live(con, plane, "position_snapshots", "supersedes_position_id", cut,
                    "t.portfolio_id = ? and t.position_date <= ?", [portfolio_id, as_of_date])
        prices = _live(con, plane, "market_observations", "supersedes_observation_id", cut,
                       "t.observation_type = 'price' and t.observed_at <= ?", [end])
        cash = {str(r[0]) for r in con.execute("select id from instruments where instrument_type = 'cash'").fetchall()}  # cash is not a holding
    best_v: dict = {}
    for r in vals:
        k = r["instrument_id"]
        if k not in best_v or (r["valuation_date"], r["received_at"] or datetime.min.replace(tzinfo=timezone.utc)) > (best_v[k]["valuation_date"], best_v[k]["received_at"] or datetime.min.replace(tzinfo=timezone.utc)):
            best_v[k] = r
    best_p: dict = {}
    for r in pos:
        k = r["instrument_id"]
        if r["view_type"] == "accounting" or k in cash:
            continue
        if k not in best_p or (r["position_date"], r["received_at"] or datetime.min.replace(tzinfo=timezone.utc)) > (best_p[k]["position_date"], best_p[k]["received_at"] or datetime.min.replace(tzinfo=timezone.utc)):
            best_p[k] = r
    for iid in sorted(set(best_v) | set(best_p)):
        if iid in best_v:
            r = best_v[iid]
            amount, ccy, status = _dec(r["value_amount"]), r["currency"], _val_status(r)
        else:
            r = best_p[iid]
            ccy, status = r["currency"], _STATUS.get(r["data_status"], "unverified")
            if r["source_market_value"] is not None:
                amount = _dec(r["source_market_value"])
            else:
                px = [p for p in prices if p["instrument_id"] == iid]
                if r["quantity"] is None or not px:
                    problems.append(f"No value or price for instrument {iid}.")
                    lines.append({"instrument_id": iid, "value": None, "status": "unverified", "source_row_id": r["id"]})
                    continue
                p = max(px, key=lambda x: x["observed_at"])
                amount, ccy = _dec(r["quantity"]) * _dec(p["value"]), p["base_currency"] or ccy
        rate, why = fx_explained(plane, ccy, currency, as_of_date, cut)
        if rate is None:
            problems.append(why)
        lines.append({"instrument_id": iid, "value": None if rate is None else amount * rate, "status": status,
                      "source_row_id": r["id"], "valuation_date": r["valuation_date"] if iid in best_v else r["position_date"]})
    total = None if problems else sum((l["value"] for l in lines), Decimal(0))
    return {"total": total, "lines": lines, "calc_version": CALC_VERSION, "problems": problems}


# ---- returns and the benchmark (card K5) -----------------------------------------------------------------------------------------------

STALE_DAYS = 7  # an index level older than this before the date asked for is not "the level on that date"
_FLOW = {"subscription": 1, "call": 1, "redemption": -1, "distribution": -1}  # money into (+) or out of (-) the portfolio; dividends and fees stay inside


def _day(d) -> date:
    return d.date() if isinstance(d, datetime) else d if isinstance(d, date) else date.fromisoformat(str(d)[:10])


@memo
def benchmark_definition(plane, benchmark_code: str, on_date) -> dict | None:
    """The latest version of the definition in force on `on_date`, with its components in force then. Any approval status is returned; callers decide."""
    on = _day(on_date)
    with wh.connect(plane, read_only=True) as con:
        cur = con.execute("select id, benchmark_code, benchmark_name, version_number, reporting_currency, approval_status from benchmark_definitions "
                          "where benchmark_code = ? and effective_from <= ? and (effective_to is null or effective_to >= ?) order by version_number desc limit 1",
                          [benchmark_code, on, on])
        row = cur.fetchone()
        if not row:
            return None
        d = dict(zip([c[0] for c in cur.description], row))
        cur = con.execute("select market_series_key, component_weight, spread_bps from benchmark_components where benchmark_definition_id = ? "
                          "and weight_effective_from <= ? and (weight_effective_to is null or weight_effective_to >= ?) order by market_series_key", [d["id"], on, on])
        d["components"] = [{"series_key": r[0], "weight": _dec(r[1]), "spread_bps": _dec(r[2] or 0)} for r in cur.fetchall()]
    return d


def _unfinished(pe: date, cut: datetime) -> str | None:
    """A period that has not ended by the cutoff has no closing figure yet (a4.7): never fall back to an older value and show a 0% return."""
    return f"Not available yet: the period runs to {pe:%d %b %Y} and has not ended." if pe > cut.date() else None


def _index_level(rows: list[dict], key: str, on: date):
    """(level row, problem or None): the latest known level of the series on or before `on`."""
    end = datetime.combine(on, time.max, tzinfo=timezone.utc)
    got = [r for r in rows if r["series_key"] == key and r["observed_at"] <= end]
    if not got:
        return None, f"No level for {key} on or before {on} was known by the cutoff."
    r = max(got, key=lambda x: (x["observed_at"], x["received_at"]))
    if (on - r["observed_at"].date()).days > STALE_DAYS:
        return None, f"The latest level for {key} is from {r['observed_at']:%d %b %Y}, too old for {on}."
    return r, None


@memo
def benchmark_return(plane, benchmark_code: str, period_start, period_end, cutoff=None, currency: str | None = None) -> dict:
    """Blended benchmark return between two dates (the opening and closing index levels, normally month ends).

    Each component: index return in `currency` (levels converted by the signed fixing at their own dates) plus its spread (spread_bps a year: a twelfth per whole month between month ends,
    else pro rata for the days), weighted by the weights in force on the first day the period covers (period_start + 1: the opening level is the
    previous month end, so October is governed by the definition in force on 1 Oct, a4.2). Returns {value, definition, components, problems, calc_version}; value is None
    when anything is missing or the weights do not add to 1. The definition's approval status is returned, not judged (see k7_benchmark)."""
    ps, pe, cut = _day(period_start), _day(period_end), _cutoff(cutoff)
    out = {"value": None, "definition": None, "components": [], "problems": [], "calc_version": CALC_VERSION}
    first = ps + timedelta(days=1)
    d = benchmark_definition(plane, benchmark_code, first)
    if d is None:
        out["problems"].append(f"No benchmark {benchmark_code} is defined for {first}.")
        return out
    ccy = (currency or d["reporting_currency"]).upper()
    out["definition"] = {k: d[k] for k in ("id", "benchmark_code", "benchmark_name", "version_number", "reporting_currency", "approval_status")}
    if not d["components"]:
        out["problems"].append(f"Benchmark {benchmark_code} has no components in force on {first}.")
        return out
    if why := _unfinished(pe, cut):
        out["problems"].append(why)
        return out
    wsum = sum(c["weight"] for c in d["components"])
    if abs(wsum - 1) > Decimal("0.000001"):
        out["problems"].append(f"The weights of {benchmark_code} add up to {wsum}, not 1.")
        return out
    marks = ",".join("?" * len(d["components"]))
    with wh.connect(plane, read_only=True) as con:
        obs = _live(con, plane, "market_observations", "supersedes_observation_id", cut,
                    f"t.observation_type = 'index_level' and t.series_key in ({marks})", [c["series_key"] for c in d["components"]])
    days = Decimal((pe - ps).days)
    # month end to month end: the spread is a twelfth a month (300 bps a year = 25 bps a month), as signed definitions state it; else pro rata days
    months = (pe.year - ps.year) * 12 + pe.month - ps.month if (ps + timedelta(days=1)).day == 1 and (pe + timedelta(days=1)).day == 1 else 0
    total = Decimal(0)
    for c in d["components"]:
        lv = []
        for on in (ps, pe):
            r, why = _index_level(obs, c["series_key"], on)
            if r is None:
                out["problems"].append(why)
                break
            rate, why = fx_explained(plane, r["base_currency"] or ccy, ccy, on, cut)
            if rate is None:
                out["problems"].append(why)
                break
            lv.append(_dec(r["value"]) * rate)
        if len(lv) < 2:
            continue
        if lv[0] == 0:
            out["problems"].append(f"The opening level of {c['series_key']} is zero.")
            continue
        idx = lv[1] / lv[0] - 1
        spread = c["spread_bps"] / 10000 * (Decimal(months) / 12 if months else days / 365)
        total += c["weight"] * (idx + spread)
        out["components"].append({"series_key": c["series_key"], "weight": c["weight"], "index_return": idx, "spread_return": spread,
                                  "contribution": c["weight"] * (idx + spread)})
    if not out["problems"]:
        out["value"] = total
    return out


@memo
def portfolio_return(plane, portfolio_id: str, period_start, period_end, cutoff=None, currency: str = "USD") -> dict:
    """Return of a portfolio over the period: (closing - opening - flows) / (opening + day-weighted flows), flows being confirmed calls and
    subscriptions in and distributions and redemptions out. This is the Modified Dietz approximation of a time-weighted return; it equals the exact
    one when there are no flows. {value, opening, closing, flows, statuses, problems, calc_version}; value is None with the reason in problems."""
    ps, pe, cut = _day(period_start), _day(period_end), _cutoff(cutoff)
    out = {"value": None, "opening": None, "closing": None, "flows": Decimal(0), "statuses": [], "valuation_dates": [], "problems": [], "calc_version": CALC_VERSION}
    if pe <= ps:
        out["problems"].append("The period must end after it starts.")
        return out
    if why := _unfinished(pe, cut):
        out["problems"].append(why)
        return out
    v0, v1 = (portfolio_value(plane, portfolio_id, d, cut, currency) for d in (ps, pe))
    out["problems"] += v0["problems"] + v1["problems"]
    out["statuses"] = sorted({l["status"] for l in v1["lines"]})
    out["valuation_dates"] = sorted({l["valuation_date"] for l in v1["lines"] if l.get("valuation_date")})  # the dates the closing value really rests on
    with wh.connect(plane, read_only=True) as con:
        moves = _live(con, plane, "cash_movements", "supersedes_cash_movement_id", cut,
                      "t.portfolio_id = ? and t.effective_date > ? and t.effective_date <= ? and t.confirmation_status = 'confirmed'", [portfolio_id, ps, pe])
    flows, weighted = Decimal(0), Decimal(0)
    for m in moves:
        sign = _FLOW.get(m["movement_type"])
        if sign is None:
            continue
        rate, why = fx_explained(plane, m["currency"], currency, m["effective_date"], cut)
        if rate is None:
            out["problems"].append(why)
            continue
        amt = sign * abs(_dec(m["amount"])) * rate
        flows += amt
        weighted += amt * Decimal((pe - m["effective_date"]).days) / Decimal((pe - ps).days)
    out["flows"] = flows
    if out["problems"]:
        return out
    out["opening"], out["closing"] = v0["total"], v1["total"]
    base = v0["total"] + weighted
    if base == 0:
        out["problems"].append("The portfolio had no value at the start of the period, so a return cannot be worked out.")
        return out
    out["value"] = (v1["total"] - v0["total"] - flows) / base
    return out
