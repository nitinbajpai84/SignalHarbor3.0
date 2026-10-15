"""CS1 Daily key numbers: the band at the top of Consume.

`daily(plane, viewer, currency, as_of)` puts six sections side by side, each read from a function that already exists (k4_office, k6_liquidity via
k4_office, k7_benchmark, e3_calc) and filtered by E1d there. Nothing here is worked out by a model and no money is added up except
sums of figures that are already visible to the viewer. Every figure carries a `trail_id` (stable text) and a `where` block that answers
"Where is this from?". A section that cannot be read says so in plain words and the others still show.

Sections: nav, issued, returns (month and year to date against the signed benchmark), levers, markets, liquidity.
ponytail: the benchmark is compared with the portfolio whose name has "liquid" in it (P14 compares the liquid book); there is no portfolio to benchmark link in the
warehouse yet. Add one when a second benchmark is signed.
"""
from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sh_platform.v1.scope_memo import memo
from sh_platform.v1 import e3_calc, k4_office as O, k7_benchmark, wh

log = logging.getLogger(__name__)
ZERO = Decimal(0)
WORST = ["stale", "unverified", "estimated", "revised", "official"]  # the status of a total is its weakest line
SERIES = {"IDX:GLEQ:SYN": "Global equity index", "IDX:GLBD:SYN": "Global bond index", "FX:USDSGD:WMR_4PM": "US dollar in Singapore dollars"}
NOT_YET = "Not available yet."


def _tid(*p) -> str:
    return "k9:" + ":".join(str(x) for x in p)


def _month_end(d: date) -> date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def _src(w: dict) -> dict:
    return {"text": w.get("text"), "table": w.get("table"), "row_id": w.get("row_id")}


def _skipped(name: str, skip: tuple):
    return {"available": False, "message": NOT_YET} if name in skip else None


def _safe(name: str, fn):
    try:
        return fn()
    except Exception:  # one section failing must not blank the band; the reason goes to the log, the person gets plain words
        log.warning("daily numbers: %s could not be read", name, exc_info=True)
        return {"available": False, "message": NOT_YET}


# ---- sections ---------------------------------------------------------------------------------------------------------

def _nav(plane, viewer, cur, day) -> dict:
    h = O.holdings(plane, viewer, cur, day)
    lines = [l for e in h["entities"] for p in e["portfolios"] for l in p["lines"]]
    status = next((s for s in WORST if any(l["data_status"] == s for l in lines)), "official").capitalize() if lines else "Not available yet"
    return {"available": True, "currency": cur, "total": h["total"], "partial": h["partial"], "portfolios": sum(len(e["portfolios"]) for e in h["entities"]), "entities": len(h["entities"]), "status": status, "trail_id": _tid("nav", "total", cur, day),
            "by_entity": [{"entity_id": e["entity_id"], "name": e["entity_name"], "value": e["total"], "trail_id": _tid("nav", "entity", e["entity_id"], cur, day)}
                          for e in h["entities"]],
            "where": {"text": f"Latest value of every holding on {day:%d %b %Y} in {cur}, from the valuations and positions in the company warehouse.",
                      "sources": [_src(l["where"]) for l in lines]}}


def _issued(plane, viewer, cur) -> dict:
    iv = O.issued_vs_known(plane, viewer, cur)
    if not iv.get("report"):
        return {"available": False, "message": iv.get("message") or NOT_YET}
    tot = next((l for l in iv["lines"] if l["label"] == "Total"), None)
    r = iv["report"]
    return {"available": tot is not None, "message": None if tot else NOT_YET, "currency": iv["currency"], "report": r["name"], "period_end": r["period_end"],
            "issued_at": r["issued_at"], "issued": tot and tot["issued"], "known_now": tot and tot["known_now"], "difference": tot and tot["difference"],
            "status": (tot or {}).get("status") and str(tot["status"]).capitalize(),
            "banner": iv["banner"] and iv["banner"].replace(" lines below show ", " report lines show ", 1).replace("1 line below shows ", "1 report line shows ", 1), "brief_link": iv["brief_link"],
            "trail_id": _tid("issued", r["report_version_id"], cur), "where": iv["where"]}


def _liquid_portfolio(plane, viewer):
    return next((p for p in O._portfolios(plane, viewer)[0] if "liquid" in f"{p['portfolio_code']} {p['portfolio_name']}".lower()), None)


def _ret(c: dict, cur: str, label: str, start, end) -> dict:
    sh = lambda v: None if v is None else v * 100  # noqa: E731
    return {"label": label, "start": start, "end": end, "portfolio": sh(c["portfolio"]["value"]), "benchmark": sh(c["benchmark"]["value"]),
            "difference": sh(c["difference"]), "certified": c["certified"], "problems": list(dict.fromkeys(c["problems"])),
            "message": None if c["portfolio"]["value"] is not None else
            (f"Not available yet: there is no signed exchange rate for {start:%d %b %Y}." if any("fx_fixing" in x for x in c["problems"]) else NOT_YET),
            "trail_id": _tid("return", label.lower().replace(" ", "-"), cur, end)}


def _returns(plane, viewer, cur, end: date) -> dict:
    pf = _liquid_portfolio(plane, viewer)
    code = (_signed(plane) or {}).get("benchmark_code")
    if pf is None or not code:
        return {"available": False, "message": "No signed benchmark applies to what you can see yet."}
    month_start, year_start = (end.replace(day=1) - timedelta(1)), date(end.year - 1, 12, 31)
    out = [_ret(k7_benchmark.comparison(plane, pf["id"], code, s, end, currency=cur), cur, lab, s, end)
           for lab, s in (("Month", month_start), ("Year to date", year_start))]
    m = out[0]
    return {"available": True, "currency": cur, "portfolio": pf["portfolio_name"], "benchmark_code": code, "periods": out,
            "status": "Certified" if m["certified"] else "Not certified", "trail_id": _tid("return", pf["id"], code, cur, end),
            "where": {"text": f"{pf['portfolio_name']} return between month ends against the signed benchmark {code}: opening and closing values and index levels from the warehouse; "
                              "the benchmark is certified only when its definition is approved and every closing value is official or revised.", "sources": []}}


@memo
def _signed(plane) -> dict | None:
    with wh.connect(plane, read_only=True) as con:
        r = con.execute("select benchmark_code, version_number from benchmark_definitions where approval_status = 'approved' order by version_number desc limit 1").fetchone()
    return r and {"benchmark_code": r[0], "version": r[1]}


def _levers(plane, viewer, cur, start: date, end: date) -> dict:
    """The liquid book's own move over the month, split as why_moved splits it (price, trades, revisions, exchange rates; the parts add up to
    the change). Cycle 2: the parts were the NAV-bridge parts of every portfolio, which is a different question."""
    wm = O.why_moved(plane, viewer, start, end, cur, None, "liquid")
    if not wm.get("available"):
        return {"available": False, "message": wm.get("message") or NOT_YET}
    parts = [{"code": x["code"], "label": x["label"], "amount": x["amount"], "trail_id": _tid("lever", x["code"], cur, end)} for x in wm["parts"]]
    price = next((x for x in wm["parts"] if x["code"] == "price"), {"lines": []})
    movers = [{"name": l["label"], "amount": l["amount"], "trail_id": _tid("mover", l["label"], cur, end), "plain": l["plain"],
               "sources": [_src(e) for e in l["evidence"]]} for l in price["lines"][:3]]
    explained = sum((x["amount"] for x in parts), ZERO) == wm["change"]
    return {"available": True, "message": None, "currency": cur, "period_end": end, "parts": parts, "movers": movers,
            "mover_book": ", ".join(wm.get("portfolios", [])) if movers else None, "change": wm["change"], "percent": wm.get("percent"),
            "status": "Fully explained" if explained else "Some unexplained", "trail_id": _tid("lever", "all", cur, end),
            "where": {"text": f"Change in the value of the liquid book ({', '.join(wm.get('portfolios', []))}) from {start:%d %b %Y} to {end:%d %b %Y} in {cur}, "
                              "split into price moves, trades, revisions and exchange rates.",
                      "sources": [_src(e) for x in wm["parts"] for l in x["lines"] for e in l["evidence"]]}}


def _pct(a, b):
    return None if a is None or not b else (a - b) / b * 100


@memo
def _markets(plane, day: date) -> dict:
    cut = datetime.combine(day, datetime.max.time(), tzinfo=timezone.utc)
    with wh.connect(plane, read_only=True) as con:
        rows = e3_calc._live(con, plane, "market_observations", "supersedes_observation_id", wh.now(),
                             "t.series_key in (select series_key from market_observations where observation_type in ('fx','index_level')) and t.observed_at <= ?", [cut])
    by: dict[str, list] = {}
    for r in rows:
        if r["observation_type"] in ("fx", "index_level"):
            by.setdefault(r["series_key"], []).append((r["observed_at"].astimezone(timezone.utc).date(), Decimal(str(r["value"])), r))
    month_ago = day - timedelta(days=30)
    out = []
    for key, obs in sorted(by.items()):
        obs.sort(key=lambda x: x[0])
        d, v, row = obs[-1]
        m = next((o for o in reversed(obs) if o[0] <= month_ago), None)
        p = obs[-2] if len(obs) > 1 and (d - obs[-2][0]).days <= 4 else None  # a monthly index has no last-day move: it says so
        out.append({"series_key": key, "name": SERIES.get(key, key), "kind": row["observation_type"], "level": v, "level_date": d,
                    "month_change_pct": _pct(v, m and m[1]), "day_change_pct": _pct(v, p and p[1]), "trail_id": _tid("market", key, d),
                    "where": {"text": f"{SERIES.get(key, key)}: level {v.normalize():f} on {d:%d %b %Y}"
                                      + (f", against {m[1].normalize():f} on {m[0]:%d %b %Y}" if m else "") + ".", "table": "market_observations", "row_id": str(row["id"])}})
    return {"available": bool(out), "message": None if out else NOT_YET, "series": out, "status": "Official" if out else NOT_YET, "trail_id": _tid("market", "all", day),
            "where": {"text": "Index levels and exchange rates recorded in the warehouse. A monthly index has no move for the last day.", "sources": [s["where"] for s in out]}}


def _liquidity(plane, viewer, cur, day) -> dict:
    lq = O.liquidity(plane, viewer, cur, day)
    if not lq.get("available") or not lq.get("entities"):
        return {"available": False, "message": lq.get("message") or NOT_YET}
    ents, tot = [], dict(cash=ZERO, calls=ZERO, after=ZERO, after_all=ZERO)
    for e in lq["entities"]:
        b = next((k for k in e["buckets"] if k["key"] == "30"), None)
        if b is None:
            continue
        row = {"entity_id": e["entity_id"], "name": e["entity_name"], "cash": e["available_cash"], "calls_30": b["calls"],
               "cash_after_confirmed": b["cash_after_confirmed_calls"], "cash_after_all": b["cash_after_calls"], "unconfirmed": len(e["unconfirmed"]),
               "problems": e["problems"], "trail_id": _tid("liquidity", e["entity_id"], cur, day)}
        ents.append(row)
        for k, v in (("cash", row["cash"]), ("calls", row["calls_30"]), ("after", row["cash_after_confirmed"]), ("after_all", row["cash_after_all"])):
            tot[k] += v
    short = any(e["cash_after_all"] < 0 for e in ents)
    return {"available": bool(ents), "message": None if ents else NOT_YET, "currency": cur, "cash": tot["cash"], "calls_30": tot["calls"],
            "cash_after_confirmed": tot["after"], "cash_after_all": tot["after_all"], "entities": ents, "partial": any(e["problems"] for e in ents), "status": "Short if every call is paid" if short else "Covered",
            "trail_id": _tid("liquidity", "all", cur, day), "where": {"text": f"Cash held on the latest administrator report less capital calls due within 30 days of {day:%d %b %Y}. "
                                                                              "Confirmed calls are firm; calls only noticed are shown separately.", "sources": []}}


# ---- the band ---------------------------------------------------------------------------------------------------------

def daily(plane, viewer, currency: str = "USD", as_of=None, skip: tuple = ()) -> dict:
    """`skip` names sections the caller will not show ("liquidity", "markets", ...): they are not read and answer "Not available yet." """
    cur, day = currency.upper(), O._day(as_of)
    if cur not in ("USD", "SGD"):
        raise ValueError("currency")
    issued = _safe("issued", lambda: _issued(plane, viewer, cur))
    pe = O._day(issued["period_end"]) if issued.get("available") and issued.get("period_end") else None
    end = pe or (day.replace(day=1) - timedelta(1))  # the last month end, else the month end before today
    start = end.replace(day=1) - timedelta(1)
    return {"currency": cur, "as_of": day, "period_end": end, "period_start": start,
            "nav": _skipped("nav", skip) or _safe("nav", lambda: _nav(plane, viewer, cur, day)), "issued": issued,
            "returns": _skipped("returns", skip) or _safe("returns", lambda: _returns(plane, viewer, cur, end)),
            "levers": _skipped("levers", skip) or _safe("levers", lambda: _levers(plane, viewer, cur, start, end)),
            "markets": _skipped("markets", skip) or _safe("markets", lambda: _markets(plane, day)),
            "liquidity": _skipped("liquidity", skip) or _safe("liquidity", lambda: _liquidity(plane, viewer, cur, day))}
