"""E3b reconciliation engine. Four checks in code: cash, NAV, limits, trades.

`cash_by_entity`: cash per legal entity per day, administrator vs trading export. Choice (from the data model): both come from
`position_snapshots` rows on cash instruments (`instruments.instrument_type = 'cash'`), summed over the entity's portfolios.
view_type `accounting` is the administrator's figure, `operational` is the trading export. We use positions, not `cash_movements`,
because a movement is an event and the two sources each report a balance. An entity with only one side is skipped and named.

`nav_vs_investment`: `nav_snapshots` (nav_period_end = as_of_date) against the sum of the latest valuation per instrument at or
before that date (`valuation_observations`), per portfolio. Same tolerance rule as cash (`cash_tolerance`): phase 1 has one tolerance.

`limits` (UC5): each signed rule of type `limit` ({dimension: asset_class|manager|liquidity|single_name, bucket, min_pct, max_pct}, in percent)
is tested against every portfolio: the latest valuation per instrument as known at the cutoff (rejected ones ignored), converted to the portfolio
currency, grouped by the dimension, as a share of the portfolio total. A breach opens a `limit_breach` case whose cause is stale data (an input older
than 90 days on the run date, or still unverified) or else a real breach. Every result carries `exposure_pct` (2 dp string) in the run's `results`.
An instrument with no asset class is listed in `questions` ("Needs a class"), counted in no bucket, and opens no case.
Liquidity: private funds, private markets and real assets count as illiquid, everything else as liquid. No cash tolerance is needed.

`trade_vs_admin` (UC8): transactions from the trading export (source type OMS or trading) against the administrator's, matched by
external_trade_id, then by instrument, date and amount within the signed `cash_tolerance`. A run on the last business day of a month checks that
calendar month; any other day checks the last 30 days. A mismatch or an unmatched trade opens a `break` case; each line carries its `type`:
quantity, price (an FX forward: contract rate and amount, in USD at the spot), missing (one side only) or timing (the same trade booked one business
day apart, net 0; it carries Tally's timing cause so Action offers "Close as timing"). An open trade break from an earlier window that is still
unreconciled is listed as carried, not raised again.

Rows are read as known at `cutoff` through E1a (`e1_asof.snapshot`). The tolerance is the signed `cash_tolerance` rule
(`parameters.abs_amount`, `currency`); materiality is the signed `cio_materiality` rule (`abs_amount`, optional `pct_of_fund` of the
administrator figure). No signed tolerance: nothing runs. A break opens a case through E4a unless an open one has the same title
(recon, subject, day). Every run is appended to `warehouse/recon_runs.jsonl`.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta
from decimal import Decimal

from sh_platform.v1 import wh
from sh_platform.v1.i2_north import Refused

log = logging.getLogger(__name__)
CODES = ("cash_by_entity", "nav_vs_investment", "limits", "trade_vs_admin")
STALE_DAYS = 90
TRADE_DAYS = 30
NO_RULE = "No signed cash tolerance is in force for {d}, so the check was not run. Ask the rule owner to get one signed."
NO_LIMIT = "No signed limit is in force for {d}, so the check was not run. Ask the rule owner to get one signed."


def _mod(name: str):
    try:
        return __import__(f"sh_platform.v1.{name}", fromlist=["x"])
    except ImportError:
        log.warning("%s is not available", name)
        raise


def _d(x) -> Decimal:
    return Decimal(str(x or 0))


def _day(x) -> date:
    if x is None:
        return wh.today()   # FIXE2: no day given = the company's cycle date
    return x if isinstance(x, date) and not isinstance(x, datetime) else (x.date() if isinstance(x, datetime) else date.fromisoformat(str(x)[:10]))


def _convert(plane, amount: Decimal, frm: str, to: str, on: date, cutoff) -> Decimal | None:
    if frm == to:
        return amount
    rate = _mod("e3_calc").fx(plane, frm, to, on, cutoff)
    return None if rate is None else amount * _d(rate)


def _material(plane, mat, diff: Decimal, base: Decimal, ccy: str, tccy: str, on: date, cutoff):
    if not mat:
        return "unknown", None
    pr = mat.get("parameters") or {}
    pct = pr.get("pct_of_fund", pr.get("pct"))
    mt = _convert(plane, diff, ccy, pr.get("currency") or tccy, on, cutoff)
    hit = mt is not None and mt > _d(pr.get("abs_amount"))
    if pct is not None and base:
        hit = hit or diff / abs(base) * 100 > _d(pct)
    return ("material" if hit else "below_threshold"), mat.get("rule_version_id")


def _open_titles(plane, kind: str) -> dict:
    """Open cases of this kind: title -> case id."""
    with wh.connect(plane, read_only=True) as con:
        return {r[0]: str(r[1]) for r in con.execute("select title, id from exceptions where exception_type = ? and status not in ('resolved', 'rejected')", [kind]).fetchall()}


def _earlier(plane, kind: str, title: str) -> str:
    """Words naming the last resolved case with the same title, so a break that comes back says what it follows."""
    with wh.connect(plane, read_only=True) as con:
        r = con.execute(
            "select (select v.event_note from exception_events v where v.exception_id = e.id and v.event_type = 'opened' limit 1), e.resolved_at, "
            "(select u.display_name from exception_events v join users u on u.id = v.performed_by_user_id where v.exception_id = e.id and v.event_type = 'resolved' "
            "order by v.occurred_at desc limit 1) from exceptions e where e.exception_type = ? and e.title = ? and e.status = 'resolved' "
            "order by e.resolved_at desc nulls last limit 1", [kind, title]).fetchone()
    if not r:
        return ""
    num, at, by = r
    when = f" on {_day(at).day} {_day(at):%b %Y}" if at else ""
    return f" This follows {num or 'an earlier case'}, resolved{when}{f' by {by}' if by else ''}, about the same {'break' if kind == 'break' else 'limit'}."


def _closed_same(plane, kind: str, title: str, amount) -> str | None:
    """A closed (resolved or dismissed) case for the same break or limit on the same day with the same size: the run found nothing new (uc2-03)."""
    with wh.connect(plane, read_only=True) as con:
        for cid, amt in con.execute("select id, candidate_impact_amount from exceptions where exception_type = ? and title = ? and status in ('resolved', 'rejected')"
                                    " order by resolved_at desc nulls last", [kind, title]).fetchall():
            if _d(amt) == _d(amount):
                return str(cid)
    return None


def _open(plane, fields: dict) -> tuple[str, bool]:
    """(case id, newly opened). The same break already closed, with the same size, is that closed case; a changed one opens a new case naming it."""
    same = _closed_same(plane, fields["exception_type"], fields["title"], fields.get("candidate_impact_amount"))
    if same:
        return same, False
    fields["description"] = (fields.get("description") or "") + _earlier(plane, fields["exception_type"], fields["title"])
    return _mod("e4_cases").open(plane, fields), True


def _title_day(title: str) -> date | None:
    """The as-at day a case title ends with ('... · 31 Jul 2026'), or None."""
    try:
        return datetime.strptime(title.rsplit(" · ", 1)[-1].strip(), "%d %b %Y").date()
    except ValueError:
        return None


def _refresh(plane, cid: str, amount, words_: str, always: bool = False) -> None:
    """A rerun for the same day found the open case again: when its size changed, the case takes the new amount and says so in its history.
    `always`: a later month of a standing breach is written in the history even when the size is the same."""
    e4 = _mod("e4_cases")
    with wh.connect(plane) as con:
        r = con.execute("select candidate_impact_amount from exceptions where id = ?", [cid]).fetchone()
        if r is None or (_d(r[0]) == _d(amount) and not always):
            return
        e4._set(con, cid, candidate_impact_amount=amount)
        e4._event(con, plane, cid, None, "rechecked", words_)


def _pretty(d: date) -> str:
    return f"{d.day} {d:%b %Y}"


def _m(x) -> str:
    """An amount for a person: thousands separated, no decimals when there are none."""
    x = _d(x)
    return f"{x:,.0f}" if x == x.to_integral_value() else f"{x:,.2f}"


def _breaks(plane, subjects, tol: dict, mat: dict | None, on: date, cutoff):
    """subjects: [(title, portfolio_id, ours, theirs, ccy, what)]. Returns (exceptions opened, breaks, skipped, one result line per subject)."""
    opened, found, skipped, results = [], 0, [], []
    limit, tccy = _d(tol.get("abs_amount")), tol.get("currency") or "USD"
    open_titles = _open_titles(plane, "break")
    for title, pid, a, b, ccy, what in subjects:
        diff = abs(a - b)
        test = _convert(plane, diff, ccy, tccy, on, cutoff)
        if test is None:
            skipped.append(f"{title}: no signed exchange rate to compare {ccy} with {tccy}")
            continue
        res = {"subject": title, "breached": bool(test > limit),
               "words": f"{what}: {_m(a)} against {_m(b)} {ccy}, a difference of {_m(diff)} {ccy}."}
        results.append(res)
        if test <= limit:
            continue
        found += 1
        if title in open_titles:
            res["case_id"] = open_titles[title]
            continue
        material, rule_id = _material(plane, mat, diff, a, ccy, tccy, on, cutoff)
        cid, new = _open(plane, {
            "exception_type": "break", "title": title, "portfolio_id": pid, "detected_at": wh.now(),
            "description": f"{what}: {a:,.2f} against {b:,.2f} {ccy} on {on.isoformat()}, a difference of {diff:,.2f} {ccy}.",
            "candidate_impact_amount": diff, "impact_currency": ccy,
            "materiality_status": material, "materiality_rule_version_id": rule_id})
        opened += [cid] if new else []
        open_titles[title] = res["case_id"] = cid
    return opened, found, skipped, results


def _finish(plane, subjects, skipped, tol, mat, on, cutoff, extra):
    opened, found, more, extra["results"] = _breaks(plane, subjects, tol, mat, on, cutoff)
    return opened, found, skipped + more, len(subjects)


def _cash_by_entity(plane, on: date, cutoff, tol, mat, extra):
    snap = _mod("e1_asof").snapshot
    with wh.connect(plane, read_only=True) as con:
        pe = {r[0]: (r[1], r[2]) for r in con.execute(
            "select p.id, e.id, e.entity_name from portfolios p join legal_entities e on e.id = p.legal_entity_id").fetchall()}
        cash = {r[0] for r in con.execute("select id from instruments where instrument_type = 'cash'").fetchall()}
    side: dict[tuple, dict[str, Decimal]] = {}
    pid_of: dict[str, str] = {}  # entity -> the portfolio its cash rows sit in: an entity-level case needs a portfolio so the right people see it
    for view, key in (("accounting", "admin"), ("operational", "trading")):
        for r in snap(plane, "position_snapshots", {"position_date": on, "view_type": view}, cutoff):
            if r["instrument_id"] in cash and r["portfolio_id"] in pe:
                k = (pe[r["portfolio_id"]], r["currency"])
                pid_of.setdefault(pe[r["portfolio_id"]][0], r["portfolio_id"])
                side.setdefault(k, {})
                side[k][key] = side[k].get(key, Decimal(0)) + _d(r["source_market_value"])
    subjects, skipped = [], []
    for ((eid, name), ccy), v in sorted(side.items(), key=lambda kv: str(kv[0])):
        if len(v) < 2:
            skipped.append(f"{name}: only the {'administrator' if 'admin' in v else 'trading export'} reported cash on {on.isoformat()}")
            continue
        subjects.append((f"Cash differs · {name} · {on.isoformat()}", pid_of.get(eid), v["admin"], v["trading"], ccy, f"{name} cash, administrator against trading export"))
    out = _finish(plane, subjects, skipped, tol, mat, on, cutoff, extra)
    for res in extra["results"]:      # a break the records show as timing carries that cause, so the line can offer "Close as timing"
        if res.get("case_id") and (why := _mod("n1_tally").timing_cause(plane, res["case_id"])):
            res["cause"] = why
    return out


def _nav_vs_investment(plane, on: date, cutoff, tol, mat, extra):
    snap = _mod("e1_asof").snapshot
    with wh.connect(plane, read_only=True) as con:
        names = {r[0]: r[1] for r in con.execute("select id, portfolio_name from portfolios").fetchall()}
    latest: dict[tuple, dict] = {}
    for r in snap(plane, "valuation_observations", {}, cutoff):
        if r["portfolio_id"] and _day(r["valuation_date"]) <= on:
            k = (r["portfolio_id"], r["instrument_id"])
            if k not in latest or _day(r["valuation_date"]) > _day(latest[k]["valuation_date"]):
                latest[k] = r
    subjects, skipped = [], []
    for n in snap(plane, "nav_snapshots", {"nav_period_end": on}, cutoff):
        pid, ccy = n["portfolio_id"], n["currency"]
        total = Decimal(0)
        for (p, _), r in latest.items():
            if p == pid:
                v = _convert(plane, _d(r["value_amount"]), r["currency"], ccy, on, cutoff)
                if v is None:
                    skipped.append(f"{names.get(pid, pid)}: no signed exchange rate for {r['currency']} to {ccy}")
                    break
                total += v
        else:
            if any(p == pid for p, _ in latest):
                subjects.append((f"NAV differs from valuations · {names.get(pid, pid)} · {on.isoformat()}", pid, _d(n["nav_amount"]), total, ccy,
                                 f"{names.get(pid, pid)} NAV against the sum of investment valuations"))
            else:
                skipped.append(f"{names.get(pid, pid)}: no investment valuations to compare on {on.isoformat()}")
    return _finish(plane, subjects, skipped, tol, mat, on, cutoff, extra)


# ---- limits (UC5) ---------------------------------------------------------------------------------------------------------------

def _illiquid(i: dict) -> bool:
    a = f"{i['asset_class'] or ''} {i['instrument_type'] or ''}".lower()
    return any(w in a for w in ("private", "real_estate", "real estate", "real_asset", "real asset"))


def _bucket_of(dim: str, i: dict) -> str | None:
    """The bucket an instrument sits in for this dimension, or None when it cannot be placed."""
    if dim == "asset_class":
        return (i["asset_class"] or "").strip().lower() or None
    if dim == "manager":
        return (i["manager_name"] or "").strip().lower() or None
    if dim == "liquidity":
        return "illiquid" if _illiquid(i) else "liquid"
    return i["canonical_name"].strip().lower()


ANY = ("", "*", "any")   # a single-name bucket that means every holding


def _label(dim: str, i: dict) -> str:
    """The bucket in words for a person: 'Hedge fund', 'Harborview Semiconductor', 'Liquid'."""
    s = (i["canonical_name"] if dim == "single_name" else _stored(dim, i)).replace("_", " ").strip()
    return s[:1].upper() + s[1:]


def _stored(dim: str, i: dict) -> str:
    """The bucket as the data holds it (case kept), for titles and words."""
    return ((i["asset_class"] if dim == "asset_class" else i["manager_name"] if dim == "manager" else None) or "").strip() or _bucket_of(dim, i) or ""


def _n(x) -> str:
    return format(_d(x).normalize(), "f")


def _limit_words(p: dict, portfolio: str | None = None) -> str:
    """'The listed equity share of the Evergreen Liquid portfolio must be between 60% and 90%.' A minimum of 0 is no minimum."""
    lo, hi = p.get("min_pct"), p.get("max_pct")
    lo = None if lo is not None and _d(lo) == 0 and hi is not None else lo
    rng = f"between {_n(lo)}% and {_n(hi)}%" if lo is not None and hi is not None else (f"at most {_n(hi)}%" if hi is not None else f"at least {_n(lo)}%")
    where = f"the {portfolio}" if portfolio else "each portfolio"
    if p.get("dimension") == "single_name" and str(p.get("bucket", "*")).strip().lower() in ANY:
        return f"Any single holding of {where} must be {rng} of it."
    return f"The {str(p.get('bucket')).replace('_', ' ')} share of {where} must be {rng}."


_UNVERIFIED = ("unverified", "pending", "proposed")


def _positions_as_values(plane, cutoff) -> list[dict]:
    """UC5 G-2: the administrator's month-end positions, read as values for the limits: the date is the value's own date (a fund line carries
    its statement date), the status is the administrator's ("estimate", "unverified", ...)."""
    out = []
    for p in _mod("e1_asof").snapshot(plane, "position_snapshots", {}, cutoff, by="received"):  # the files as received by the cutoff
        if p.get("source_market_value") is None or p.get("view_type") not in (None, "operational"):
            continue
        st = str(p.get("data_status") or "").strip().lower()
        out.append({"portfolio_id": p["portfolio_id"], "instrument_id": p["instrument_id"], "valuation_date": p["position_date"],
                    "value_amount": p["source_market_value"], "currency": p.get("currency"), "received_at": p.get("received_at"),
                    "approval_status": "pending" if st in _UNVERIFIED else "approved", "estimate": st == "estimate", "from": "administrator"})
    return out


def _rank(r: dict, i: dict) -> tuple:
    """Which value counts for a holding (the limit basis): the latest dated; on the same date a fund takes its manager's statement and a
    security takes the administrator's month-end value; then the one received last."""
    fund = str(i.get("instrument_type") or "").lower() == "fund"
    admin = r.get("from") == "administrator"
    return (_day(r["valuation_date"]), admin != fund, str(r.get("received_at") or ""))


def _limits(plane, on: date, cutoff, extra: dict):
    with wh.connect(plane, read_only=True) as con:
        codes = [r[0] for r in con.execute("select rule_code from business_rules where rule_type = 'limit' order by rule_code").fetchall()]
        pf = {r[0]: (r[1], r[2]) for r in con.execute("select id, portfolio_name, base_currency from portfolios").fetchall()}
        pcode = {r[0]: str(r[1] or "").strip().lower() for r in con.execute("select id, portfolio_code from portfolios").fetchall()}
        ins = {r[0]: dict(zip(("id", "canonical_name", "instrument_type", "asset_class", "manager_name"), r)) for r in con.execute(
            "select id, canonical_name, instrument_type, asset_class, manager_name from instruments").fetchall()}
    rules = [(c, r) for c in codes if (r := _mod("e3_rules").current(plane, c, on))]
    pname_of = {pcode[pid]: pf[pid][0] for pid in pf}
    words = lambda p: _limit_words(p, pname_of.get(str(p.get("portfolio_code") or "").strip().lower()))  # noqa: E731
    if not rules:
        raise Refused(409, NO_LIMIT.format(d=on.isoformat()))
    latest: dict[tuple, dict] = {}
    for r in _mod("e1_asof").snapshot(plane, "valuation_observations", {}, cutoff, by="received") + _positions_as_values(plane, cutoff):
        if r["portfolio_id"] in pf and r["instrument_id"] in ins and r["approval_status"] != "rejected" and _day(r["valuation_date"]) <= on:
            if r.get("from") == "administrator" and str(ins[r["instrument_id"]]["instrument_type"] or "").lower() == "cash":
                continue  # the limit base is the investment holdings; cash is not one
            k = (r["portfolio_id"], r["instrument_id"])
            if k not in latest or _rank(r, ins[r["instrument_id"]]) > _rank(latest[k], ins[r["instrument_id"]]):
                latest[k] = r
    skipped: list[str] = []
    held: dict[str, list] = {}      # portfolio -> [(instrument, value in portfolio currency, valuation row)]
    no_fx: set[str] = set()
    for (pid, iid), r in sorted(latest.items(), key=lambda kv: str(kv[0])):
        v = _convert(plane, _d(r["value_amount"]), r["currency"] or pf[pid][1], pf[pid][1], on, cutoff)  # no currency on the line: the portfolio's
        if v is None:
            skipped.append(f"{pf[pid][0]}: no signed exchange rate for {r['currency']} to {pf[pid][1]}")
            no_fx.add(pid)
        else:
            held.setdefault(pid, []).append((ins[iid], v, r))
    hits, checked, results, questions = [], 0, [], []
    for code, rule in rules:
        p = rule["parameters"] or {}
        dim, want = p.get("dimension", "asset_class"), str(p.get("bucket", "")).strip().lower()
        for pid, rows in held.items():
            if pid in no_fx or (p.get("portfolio_code") and str(p["portfolio_code"]).strip().lower() != pcode.get(pid)):
                continue
            total = sum((v for _, v, _ in rows), Decimal(0))
            sums: dict[str, Decimal] = {}
            shown: dict[str, str] = {}      # bucket key (lower-cased, for matching) -> the text as stored
            if dim == "asset_class":    # no class: a question for a person, counted in no bucket, never a breach
                for i, v, _ in rows:
                    if _bucket_of(dim, i) is None and not any(q["instrument_id"] == str(i["id"]) and q["portfolio"] == pf[pid][0] for q in questions):
                        questions.append({"instrument_id": str(i["id"]), "instrument": i["canonical_name"], "portfolio": pf[pid][0], "status": "Needs a class",
                                          "value": str(v.quantize(Decimal("0.01"))), "currency": pf[pid][1],
                                          "exposure_pct": str((v / total * 100).quantize(Decimal("0.01"))) if total else "0.00"})
            for i, v, _ in rows:
                b = _bucket_of(dim, i)
                if b is not None:
                    sums[b] = sums.get(b, Decimal(0)) + v
                    shown.setdefault(b, _stored(dim, i))
            label: dict[str, str] = {}
            for i, v, _ in rows:
                b = _bucket_of(dim, i)
                if b is not None:
                    label.setdefault(b, _label(dim, i))
            for b in ([k for k in sums if want in ANY or k == want] if dim == "single_name" else [want]):
                checked += 1
                share = sums.get(b, Decimal(0)) / total * 100 if total else Decimal(0)
                hi, lo = p.get("max_pct"), p.get("min_pct")
                over, under = hi is not None and share > _d(hi), lo is not None and share < _d(lo)
                pct = share.quantize(Decimal("0.01"))
                edge_words = (f"a minimum of {_n(lo)}%" if under or hi is None else f"a maximum of {_n(hi)}%")
                amount = sums.get(b, Decimal(0))
                room = (_d(hi) - pct) if hi is not None else (pct - _d(lo)) if lo is not None else None  # points to the nearer edge that binds
                res = {"rule_code": code, "portfolio": pf[pid][0], "bucket": b, "exposure_pct": str(pct), "breached": bool(over or under),
                       "max_pct": None if hi is None else str(_d(hi)), "headroom_pts": None if room is None else str(room.quantize(Decimal("0.01"))),
                       "words": f"{label.get(b) or b.replace('_', ' ').capitalize()}, {pf[pid][0]}: {_m(amount.quantize(Decimal('0.01')))} {pf[pid][1]} = {pct}% "
                                f"against {edge_words}."}
                est = sorted({i["canonical_name"] for i, _, r in rows if r.get("estimate") and _bucket_of(dim, i) == b})
                if est:  # UC5 C12: a figure that rests on an estimate says so (the estimate rule allows them in the report only)
                    res.update(estimates=est, words=res["words"] + f" Uses estimates: {', '.join(est)}.")
                results.append(res)
                if over or under:
                    hits.append((code, p, pid, rows, b, share, over, shown.get(b) or b, res))
    stale_on = wh.now().date()      # staleness is judged on the day the check runs, not on the month-end being checked
    opened, seen, causes = [], _open_titles(plane, "limit_breach"), []
    for code, p, pid, rows, b, share, over, label, res in hits:
        dim = p.get("dimension", "asset_class")
        total = sum((v for _, v, _ in rows), Decimal(0))
        old = [(i, v, r) for i, v, r in rows if (stale_on - _day(r["valuation_date"])).days > STALE_DAYS or r["approval_status"] in ("proposed", "pending")]
        cause = "stale data" if old else "real breach"
        one = next((i for i, _, _ in rows if dim == "single_name" and _bucket_of(dim, i) == b), None)
        name = one["canonical_name"] if one else label
        title = f"Limit breached · {name} · {pf[pid][0]} · {_pretty(on)}"
        causes.append({"title": title, "cause": cause})
        edge = _d(p["max_pct"]) if over else _d(p["min_pct"])
        gap = (abs(share - edge) / 100 * total).quantize(Decimal("0.01"))
        res.update(cause=cause, over_by=str(gap))     # UC5-C2-01: the line says why and by how much
        if title in seen:
            res["case_id"] = seen[title]
            _refresh(plane, seen[title], gap, f"Checked again: {share.quantize(Decimal('0.01'))}%, over by {_m(gap)} {pf[pid][1]}; cause {cause}.")
            continue
        stem = title.rsplit(" · ", 1)[0] + " · "
        standing = next((cid for t, cid in seen.items() if t.startswith(stem) and (d := _title_day(t)) and d < on), None)  # an earlier month only
        if standing:  # UC5: the same limit still breached at a later as-at day while its case is open: one case, with this month in its history
            res["case_id"] = standing
            _refresh(plane, standing, gap, f"Still in breach at {_pretty(on)}: {share.quantize(Decimal('0.01'))}%, over by {_m(gap)} {pf[pid][1]}; "
                                           f"cause {cause}.", always=True)
            continue
        named = "; ".join(f"{i['canonical_name']} valued {_day(r['valuation_date']).day} {_day(r['valuation_date']):%b %Y} ({(stale_on - _day(r['valuation_date'])).days} days)"
                          if (stale_on - _day(r["valuation_date"])).days > STALE_DAYS else f"{i['canonical_name']} {_m(r['value_amount'])} {r['currency']} not yet verified"
                          for i, _, r in old)
        why = {"stale data": f"{len(old)} input {'value is' if len(old) == 1 else 'values are'} older than {STALE_DAYS} days or not yet verified, so the share may be out of date: {named}.",
               "real breach": "All inputs are recent and verified."}[cause]
        cid, new = _open(plane, {
            "exception_type": "limit_breach", "title": title, "portfolio_id": pid, "instrument_id": str(one["id"]) if one else None, "detected_at": wh.now(),
            "description": f"{words(p)} It is {share.quantize(Decimal('0.01'))}%, {'above the signed maximum' if over else 'below the signed minimum'} of {_n(edge)}%. Cause: {cause}. {why}",
            "candidate_impact_amount": gap, "impact_currency": pf[pid][1], "materiality_status": "unknown"})
        opened += [cid] if new else []
        seen[title] = res["case_id"] = cid
    extra.update(rule_words=[words(r["parameters"] or {}) for _, r in rules], causes=causes, results=results, questions=questions, stale_as_of=stale_on.isoformat(),
                 limit_rule_version_ids=[r["rule_version_id"] for _, r in rules])
    return opened, len(hits), skipped, checked


# ---- trades against the administrator (UC8) -------------------------------------------------------------------------------------

def _trade_start(on: date) -> date:
    """First day a trade run covers: the 1st when `on` is the last business day of its month, else 30 days back."""
    if not any((on + timedelta(days=n)).month == on.month and (on + timedelta(days=n)).weekday() < 5 for n in range(1, 4)):
        return on.replace(day=1)
    return on - timedelta(days=TRADE_DAYS - 1)


def _bdays(a: date, b: date) -> int:
    """Weekdays from a to b (no holiday calendar, per the universe convention)."""
    a, b = sorted((a, b))
    return sum((a + timedelta(days=n + 1)).weekday() < 5 for n in range((b - a).days))


def _trades(plane, on: date, cutoff, tol: dict, mat, extra: dict):
    start = _trade_start(on)
    with wh.connect(plane, read_only=True) as con:
        kind = {str(r[0]): r[1] for r in con.execute(
            "select r.id, s.source_type from source_records r join source_batches b on b.id = r.source_batch_id join source_systems s on s.id = b.source_system_id").fetchall()}
        pn = {r[0]: r[1] for r in con.execute("select id, portfolio_name from portfolios").fetchall()}
        inm = {r[0]: r[1] for r in con.execute("select id, canonical_name from instruments").fetchall()}
    adm, trd = [], []
    for r in _mod("e1_asof").snapshot(plane, "transactions", {}, cutoff):
        d, k = _day(r["trade_date"] or r["effective_date"]), kind.get(str(r["source_record_id"]))
        if start <= d <= on and k in ("administrator", "OMS", "trading") and r.get("status") != "cancelled":   # a withdrawn trade is not compared
            (adm if k == "administrator" else trd).append({**r, "_d": d})
    limit, tccy = _d(tol.get("abs_amount")), tol.get("currency") or "USD"
    extra["rule_words"] = [f"Trades from {_pretty(start)} to {_pretty(on)} must match by trade id, or by instrument, date and amount within {limit:,.0f} {tccy}."]
    total = len(adm) + len(trd)
    by_id = {a["external_trade_id"]: a for a in adm if a["external_trade_id"]}
    pairs, rest = [], []
    for t in trd:
        a = by_id.pop(t["external_trade_id"], None) if t["external_trade_id"] else None
        if a is None:
            rest.append(t)
        else:
            adm.remove(a)
            pairs.append((t, a))
    for t in rest[:]:                                      # second pass: same instrument, date and currency, amount within tolerance
        best = None
        for a in adm:
            if a["instrument_id"] == t["instrument_id"] and a["_d"] == t["_d"] and a["currency"] == t["currency"]:
                diff = abs(_d(a["cash_amount"]) - _d(t["cash_amount"]))
                c = _convert(plane, diff, t["currency"], tccy, on, cutoff)
                if c is not None and c <= limit and (best is None or diff < best[0]):
                    best = (diff, a)
        if best:
            rest.remove(t)
            adm.remove(best[1])
            pairs.append((t, best[1]))
    for t in rest[:]:                                      # third pass: the same trade booked one business day apart (timing)
        a = next((a for a in adm if a["instrument_id"] == t["instrument_id"] and a["currency"] == t["currency"] and _bdays(a["_d"], t["_d"]) == 1
                  and _d(a["cash_amount"]) == _d(t["cash_amount"]) and _d(a.get("quantity_delta")) == _d(t.get("quantity_delta"))), None)
        if a:
            rest.remove(t)
            adm.remove(a)
            pairs.append((t, a))
    found, skipped = [], []

    def label(r):
        return f"{inm.get(r['instrument_id'], 'trade')} · {r['_d'].isoformat()}" + (f" · {r['external_trade_id']}" if r["external_trade_id"] else "")

    def booked(r):
        """'buy 12,000 at 42.15 = 505,800 USD': one way of writing a trade, amounts without sign."""
        q, amt = abs(_d(r.get("quantity_delta"))), abs(_d(r["cash_amount"]))
        kind = re.sub(r"\bfx\b", "FX", (r.get("transaction_type") or "trade").replace("_", " "))    # analyst-uc8-04: 'FX forward', never fx_forward
        head = f"{kind} {_m(q)} at {_n((amt / q).quantize(Decimal('0.0001')))} = " if q else ""
        return f"{head}{_m(amt)} {r['currency']}"

    def sized(diff, ccy):
        """The difference, and its value in the tolerance currency when that is what made it a break."""
        if ccy == tccy:
            return f"{_m(diff)} {ccy}"
        c = _convert(plane, diff, ccy, tccy, on, cutoff)
        return f"{_m(diff)} {ccy}" + (f" ({_m(c.quantize(Decimal('0.01')))} {tccy} at the signed rate, against the {_m(limit)} {tccy} allowance)" if c is not None else "")

    is_fx = {str(r[0]) for r in _fx_ids(plane)}
    for t, a in pairs:
        diff = abs(_d(a["cash_amount"]) - _d(t["cash_amount"]))
        same = t["instrument_id"] == a["instrument_id"] and t["currency"] == a["currency"]
        dq = abs(abs(_d(t.get("quantity_delta"))) - abs(_d(a.get("quantity_delta"))))
        if same and t["_d"] != a["_d"] and not diff and not dq and _bdays(t["_d"], a["_d"]) == 1:
            found.append((f"Trade differs · {label(t)}", t, Decimal(0), f"Trading export {booked(t)} on {_pretty(t['_d'])}; administrator the same on {_pretty(a['_d'])}, "
                          "one business day apart: a timing difference, net 0.", "timing"))
            continue
        if not same or t["_d"] != a["_d"]:
            found.append((f"Trade differs · {label(t)}", t, diff, "The trading export and the administrator disagree on the instrument, currency or date.", "other"))
            continue
        c = _convert(plane, diff, t["currency"], tccy, on, cutoff)
        if c is None:
            skipped.append(f"{label(t)}: no signed exchange rate to compare {t['currency']} with {tccy}")
        elif c > limit:
            rate = ""
            if str(t["instrument_id"]) in is_fx and _d(t.get("quantity_delta")) and _d(a.get("quantity_delta")):
                rate = (f"Contract rate: trading export {abs(_d(t['cash_amount']) / _d(t['quantity_delta'])):,.4f}, "
                        f"administrator {abs(_d(a['cash_amount']) / _d(a['quantity_delta'])):,.4f}. ")
            found.append((f"Trade differs · {label(t)}", t, diff,
                          f"{rate}Trading export {booked(t)}; administrator {booked(a)}; a difference of {sized(diff, t['currency'])}"
                          + (f", {_m(dq)} in quantity." if dq else "."), "quantity" if dq else "price"))
    for rows, who, other in ((rest, "trading export", "administrator"), (adm, "administrator", "trading export")):
        for r in rows:
            found.append((f"Trade not matched · {label(r)}", r, abs(_d(r["cash_amount"])),
                          f"This trade ({booked(r)}) is in the {who} for {pn.get(r['portfolio_id'], 'a portfolio')} but there is no matching trade at the {other}.", "missing"))
    seen, opened, results = _open_titles(plane, "break"), [], []
    for title, r, amount, text, typ in found:
        res = {"subject": title, "breached": True, "type": typ, "words": f"{title}: {text}"}
        results.append(res)
        if title in seen:
            res["case_id"] = seen[title]
            continue
        material, rv = _material(plane, mat, amount, Decimal(0), r["currency"], tccy, on, cutoff)
        cid, new = _open(plane, {
            "exception_type": "break", "title": title, "portfolio_id": r["portfolio_id"], "instrument_id": r["instrument_id"], "detected_at": wh.now(),
            "description": text, "candidate_impact_amount": amount, "impact_currency": r["currency"],
            "materiality_status": material, "materiality_rule_version_id": rv})
        opened += [cid] if new else []
        seen[title] = res["case_id"] = cid
    for res, f in zip(results, found):      # a timing break carries Tally's reading, so Action offers "Close as timing"
        if f[4] == "timing" and res.get("case_id") and (why := _mod("n1_tally").timing_cause(plane, res["case_id"])):
            res["cause"] = why
    differs = {f[1]["id"] for f in found}
    results += [{"subject": label(t), "breached": False, "words": f"{label(t)}: matched, {booked(t)}."} for t, _ in pairs if t["id"] not in differs]
    carried = _carried(plane, start, kind, cutoff, limit, tccy, on)
    results += carried
    extra.update(carried=len(carried), results=results, matched=len(pairs) - len([1 for t, _ in pairs if t["id"] in differs]), records={"trading export": len(trd), "administrator": len(adm) + len(pairs)})
    return opened, len(found), skipped, total     # trade records compared, both sides


def _fx_ids(plane):
    with wh.connect(plane, read_only=True) as con:
        return con.execute("select id from instruments where instrument_type = 'fx_forward'").fetchall()


def _carried(plane, start: date, kind: dict, cutoff, limit: Decimal, tccy: str, on: date) -> list[dict]:
    """Open trade breaks dated before this window that the records still show unreconciled: listed as carried, never raised again."""
    with wh.connect(plane, read_only=True) as con:
        open_ = con.execute("select id, title, candidate_impact_amount, impact_currency from exceptions where exception_type = 'break' "
                            "and status not in ('resolved', 'rejected') and title like 'Trade %'").fetchall()
    out = []
    for cid, title, amount, ccy in open_:
        parts = [p.strip() for p in title.split("·")]
        try:
            if len(parts) < 4 or _day(parts[2]) >= start:
                continue
        except ValueError:
            continue
        side = {"admin": [], "trd": []}
        for r in _mod("e1_asof").snapshot(plane, "transactions", {"external_trade_id": parts[3]}, cutoff):
            if r.get("status") == "cancelled":
                continue
            side["admin" if kind.get(str(r["source_record_id"])) == "administrator" else "trd"].append(r)
        if not (side["admin"] or side["trd"]):
            continue
        if side["admin"] and side["trd"]:       # the latest booking each side holds (an amendment row replaces the first)
            a, t = (max(v, key=lambda r: str(r["effective_date"])) for v in (side["admin"], side["trd"]))
            c = _convert(plane, abs(_d(a["cash_amount"]) - _d(t["cash_amount"])), t["currency"], tccy, on, cutoff)
            if c is None or c <= limit:
                continue                        # amended: no longer a break; the case stays for a person to close
        out.append({"subject": title, "breached": True, "carried": True, "case_id": str(cid), "type": "missing" if not (side["admin"] and side["trd"]) else "price",
                    "words": f"{title}: carried from {_pretty(_day(parts[2]))}, still open at {_m(amount)} {ccy}."})
    return out


def run_detail(plane, recon_code: str, as_of_date, cutoff=None, who: str | None = None) -> dict:
    rec = _run_detail(plane, recon_code, as_of_date, cutoff)
    n = _len(rec.get("breaks"))
    rec["run_id"] = _mod("run_log").record(plane, "recon", "production", "manual", who, [dict(name=recon_code, layer="check", target="recon_runs", rows_in=_len(rec.get("checked")), inserted=_len(rec.get("opened")),
                           rejected=0, checks_passed=max(_len(rec.get("checked")) - n, 0), checks_failed=n)], "ok")
    with open(wh.path(plane).parent / "recon_runs.jsonl", "a", encoding="utf-8") as f:  # UC5: each run carries its Operations run id
        f.write(json.dumps(rec) + "\n")
    if recon_code == "limits":
        _write_limit_results(plane, rec)
    return rec


LIMIT_RESULTS = "limit_results"


def _write_limit_results(plane, rec: dict) -> None:
    """UC5 G-1: when the company's approved model has a `limit_results` table (added by a model change the head of data signs), each limits
    run writes its lines there, so a dashboard can show them; a rerun for the same as-at day replaces that day's lines. Only the columns the
    table has are written. Without the table nothing is written (the run itself is unchanged)."""
    cols = set(_mod("e0a_catalogue").columns_of(plane, LIMIT_RESULTS) or [])
    if not cols:
        return
    lines = [{"run_id": rec.get("run_id"), "as_of_date": rec["as_of_date"], "ran_at": rec["ran_at"], "portfolio": r.get("portfolio"),
              "rule_code": r.get("rule_code"), "item": r.get("bucket"), "exposure_pct": r.get("exposure_pct"), "max_pct": r.get("max_pct"),
              "headroom_pts": r.get("headroom_pts"), "result": "breach" if r.get("breached") else "inside", "cause": r.get("cause"),
              "over_by": r.get("over_by"), "estimates": ", ".join(r.get("estimates") or []) or None, "words": r.get("words")} for r in rec.get("results") or []]
    lines += [{"run_id": rec.get("run_id"), "as_of_date": rec["as_of_date"], "ran_at": rec["ran_at"], "portfolio": q.get("portfolio"),
               "rule_code": None, "item": q.get("instrument"), "exposure_pct": q.get("exposure_pct"), "result": "question", "cause": q.get("status"),
               "words": f"{q.get('instrument')}: {q.get('status')}, {q.get('exposure_pct')}% of the portfolio, in no class."} for q in rec.get("questions") or []]
    try:
        with wh.connect(plane) as con:
            if "as_of_date" in cols:
                con.execute(f"delete from {LIMIT_RESULTS} where cast(as_of_date as varchar) = ?", [rec["as_of_date"]])
            for ln in lines:
                row = {k: v for k, v in ln.items() if k in cols}
                if "id" in cols:
                    row["id"] = wh.new_id()
                if "organization_id" in cols:
                    row["organization_id"] = _mod("e1_write").org_id(plane)
                con.execute(f"insert into {LIMIT_RESULTS} ({', '.join(row)}) values ({', '.join('?' * len(row))})", list(row.values()))
    except Exception:  # noqa: BLE001 - the run and its cases stand; the dashboard table is a copy of them
        log.exception("UC5: the limit results could not be written to %s", LIMIT_RESULTS)


def _len(x) -> int:
    return len(x) if isinstance(x, (list, tuple, set)) else int(x or 0)


def _run_detail(plane, recon_code: str, as_of_date, cutoff=None) -> dict:
    if recon_code not in CODES:
        raise Refused(404, f"We do not know the check {recon_code}.")
    on, cutoff = _day(as_of_date), cutoff or wh.now()
    rules = _mod("e3_rules")
    extra: dict = {}
    tol = None
    if recon_code == "limits":
        opened, found, skipped, checked = _limits(plane, on, cutoff, extra)
    else:
        tol = rules.current(plane, "cash_tolerance", on)
        if not tol:
            raise Refused(409, NO_RULE.format(d=on.isoformat()))
        mat = rules.current(plane, "cio_materiality", on)
        pr = tol["parameters"]
        extra["rule_words"] = [f"Differences up to {_d(pr.get('abs_amount')):,.0f} {pr.get('currency') or 'USD'} are accepted."]
        if recon_code == "trade_vs_admin":
            opened, found, skipped, checked = _trades(plane, on, cutoff, pr, mat, extra)
        else:
            fn = _cash_by_entity if recon_code == "cash_by_entity" else _nav_vs_investment
            opened, found, skipped, checked = fn(plane, on, cutoff, pr, mat, extra)
    if not checked and not skipped:
        skipped = [f"Nothing was reported on either side for {on.isoformat()}, so there was nothing to compare. Pick a day the files cover."]
    rec = {"recon_code": recon_code, "as_of_date": on.isoformat(), "cutoff": cutoff.isoformat() if hasattr(cutoff, "isoformat") else str(cutoff), "ran_at": wh.now().isoformat(),
           "tolerance_rule_version_id": (tol or {}).get("rule_version_id"), "checked": checked, "breaks": found, "opened": opened, "skipped": skipped, **extra}
    return rec


def run(plane, recon_code: str, as_of_date, cutoff=None) -> list[str]:
    """Contract: exception ids newly opened by this run."""
    return run_detail(plane, recon_code, as_of_date, cutoff)["opened"]


def last_runs(plane, limit: int = 20) -> list[dict]:
    p = wh.path(plane).parent / "recon_runs.jsonl"
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    return [json.loads(x) for x in lines[-limit:]][::-1]


# ---- a capital call matched to the payment that settled it (W10, method 3; UC01 step 6) ------------------------------------------------------
CALL_WINDOW = 5  # business days either side of the due date


def _call_no(ref: str | None, no: str | None) -> bool:
    """The call number in a payment's reference ('CC-CALL-C-7', 'call 7'), as a whole number."""
    return bool(no and re.search(rf"(?<!\d){re.escape(str(no))}(?!\d)", ref or ""))


def match_calls(plane, as_of_date=None) -> dict:
    """Match each noticed capital call (cash_movements, call, noticed, not yet replaced) to a bank outflow in the same currency by amount (exact, or within the
    signed cash_tolerance), a date window (due date +- 5 business days) and reference words (the fund's name or the call number in the payment's reference or payee).
    A match is marked paid the way the loader marks a call the bank shows: a confirmed call row with the bank's receipt, replacing the noticed row (which keeps the
    notice's receipt); the expected payment of that call is cancelled. One payment is never used twice. A call still unmatched after its due date opens a card.
    -> {"paid": [{call, payment, notice_receipt, bank_receipt, ...}], "open": [...], "cards": [exception ids]}"""
    on = _day(as_of_date)
    tol = (_mod("e3_rules").current(plane, "cash_tolerance", on) or {}).get("parameters") or {}
    limit = _d(tol.get("abs_amount"))
    out: dict = {"paid": [], "open": [], "cards": []}
    with wh.connect(plane) as con:
        q = lambda sql, *a: (lambda c: [dict(zip([d[0] for d in c.description], r)) for r in c.fetchall()])(con.execute(sql, list(a)))  # noqa: E731
        calls = q("select m.*, i.canonical_name as fund, (select f.value_text from extracted_fields f join documents d on d.id = f.document_id where d.source_record_id = m.source_record_id "
                  "and f.field_name = 'call_no' limit 1) as call_no from cash_movements m join instruments i on i.id = m.instrument_id where m.movement_type = 'call' "
                  "and m.confirmation_status = 'noticed' and not exists (select 1 from cash_movements x where x.supersedes_cash_movement_id = m.id) order by m.due_date, m.id")
        pays = q("select * from cash_movements m where m.movement_type = 'payment' and m.confirmation_status = 'confirmed' and m.amount < 0 and m.effective_date is not null "
                 "and not exists (select 1 from cash_movements x where x.source_record_id = m.source_record_id and x.movement_type = 'call' and x.confirmation_status = 'confirmed')")
        ent = {r[0]: r[1] for r in con.execute("select id, legal_entity_id from portfolios").fetchall()}
        scored = []
        for c in calls:
            words = [w for w in re.findall(r"[a-z]{4,}", c["fund"].lower())]
            for p in pays:
                if p["currency"] != c["currency"] or not c["due_date"]:
                    continue
                diff = abs(abs(_d(p["amount"])) - abs(_d(c["amount"])))
                text = f"{p.get('reference') or ''} {p.get('payee_name') or ''}"
                by_no = _call_no(p.get("reference"), c["call_no"])
                hit = sum(w in text.lower() for w in words)
                if diff > limit or ent.get(p["portfolio_id"]) != ent.get(c["portfolio_id"]) or _bdays(c["due_date"], _day(p["effective_date"])) > CALL_WINDOW or not (by_no or hit):
                    continue
                scored.append((not by_no, -hit, diff, abs((c["due_date"] - _day(p["effective_date"])).days), str(c["id"]), str(p["id"]), c, p))
        used_c, used_p = set(), set()
        for _, _, diff, _, cid, pid, c, p in sorted(scored, key=lambda s: s[:6]):
            if cid in used_c or pid in used_p:
                continue
            used_c.add(cid), used_p.add(pid)
            cols = [k for k in c if k not in ("id", "fund", "call_no", "supersedes_cash_movement_id")]
            row = {**{k: c[k] for k in cols}, "id": wh.new_id(), "confirmation_status": "confirmed", "amount": p["amount"], "effective_date": p["effective_date"],
                   "source_record_id": p["source_record_id"], "supersedes_cash_movement_id": c["id"],
                   "received_at": p["received_at"], "recorded_at": wh.now()}
            have = {r[0] for r in con.execute("select column_name from information_schema.columns where table_name = 'cash_movements'").fetchall()}
            row = {k: v for k, v in row.items() if k in have}
            con.execute(f"insert into cash_movements ({', '.join(row)}) values ({', '.join('?' * len(row))})", list(row.values()))
            con.execute("update cash_movements set confirmation_status = 'cancelled' where movement_type = 'payment' and confirmation_status = 'expected' and instrument_id = ? and due_date = ? and amount = ?",
                        [c["instrument_id"], c["due_date"], c["amount"]])
            out["paid"].append({"call": str(c["id"]), "fund": c["fund"], "call_no": c["call_no"], "payment": str(p["id"]), "paid_row": row["id"], "notice_receipt": str(c["source_record_id"]),
                                "bank_receipt": str(p["source_record_id"]), "amount_difference": str(diff),
                                "words": f"{c['fund']} call {c['call_no']} ({_m(abs(_d(c['amount'])))} due {_pretty(c['due_date'])}) was paid on {_pretty(_day(p['effective_date']))}."})
        late = [c for c in calls if str(c["id"]) not in used_c and c["due_date"] and c["due_date"] < on]
        out["open"] = [{"call": str(c["id"]), "fund": c["fund"], "call_no": c["call_no"]} for c in calls if str(c["id"]) not in used_c]
    for c in late:
        title = f"{c['fund']} call {c['call_no']} not paid by {_pretty(c['due_date'])}"
        if title in _open_titles(plane, "call_unpaid"):
            continue
        out["cards"].append(_mod("e4_cases").open(plane, {
            "exception_type": "call_unpaid", "title": title, "instrument_id": c["instrument_id"], "portfolio_id": c["portfolio_id"], "detected_at": wh.now(), "owner_user_id": "Daniel Foo",
            "description": f"{c['fund']} call {c['call_no']} for {_m(abs(_d(c['amount'])))} {c['currency']} was due on {_pretty(c['due_date'])} and no bank payment of that amount "
                           f"within {CALL_WINDOW} business days of it names the fund or the call. Daniel Foo (Head of Finance) checks whether it was paid from another account or is still to be paid.",
            "candidate_impact_amount": abs(_d(c["amount"])), "impact_currency": c["currency"], "materiality_status": "material"}))
    return out
