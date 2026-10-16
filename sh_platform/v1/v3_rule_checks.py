"""A figure read against the office's own signed rule (round 5, bugs 2 and 3).

- Single-issuer concentration asked about a limit ("which holding is over its single-name limit"): each holding's share of its portfolio from the ready
  table, against the signed single-name limit rule (e3_rules, the 2.0 limits register), else the limit the signed brief states. No limit on record: the
  shares are shown and the answer says the limit is not on record. A limit is never invented.
- Cash break: the day asked (else the latest day), each entity's break against the signed cash tolerance. A difference inside the tolerance is shown as
  within tolerance, not as a break.
Both return None when the table or the rule is not there, and the ordinary ready-table answer (v3_figures._read) answers instead.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from sh_platform.v1 import v3_recipes as R

LIMIT_Q = re.compile(r"\b(?:limits?|breach\w*|exceed\w*)\b", re.I)
BRIEF_LIMIT = re.compile(r"single[\s\-‐‑]*(?:name|issuer|holding)[^.;:]*?\b(?:over|above|more than|exceed(?:s|ing)?|at most|max(?:imum)?(?: of)?)\s+"
                         r"(\d+(?:\.\d+)?)\s*(?:%|per ?cent)", re.I)


def _day_words(d: date) -> str:
    from sh_platform.v1.v3_figures import _month_words
    return f"{d.day} {_month_words(d)}"


def _d(v) -> Decimal | None:
    return None if v is None else v if isinstance(v, Decimal) else Decimal(str(v))


def _n(v: Decimal) -> str:
    return format(v.normalize(), "f")


def _day(v) -> date | None:
    return None if v is None else v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


def _rows(plane, t: dict) -> list[dict]:
    """The ready table's rows, its date columns as dates (a ready table may hold a date as text)."""
    from sh_platform.v1 import cx_dash as CD
    rows = CD.run_sql(plane, f'select * from "{t["name"]}"')[1]
    return [{**x, **{c: _day(x[c]) for c in ("position_date", "day") if c in x}} for x in rows]


def answer(plane, k: dict, t: dict, text: str, th: dict | None) -> dict | None:
    r = R.bound(k)
    cols = {c["name"] for c in t.get("columns") or []}
    if r and r["id"] == "concentration" and LIMIT_Q.search(text) and {"issuer", "concentration_pct", "position_date"} <= cols:
        return _over_limit(plane, k, _rows(plane, t), text, th)
    if r and r["id"] == "cash_break" and {"entity", "day", "cash_break"} <= cols:
        return _breaks(plane, r, _rows(plane, t), text)
    return None


# ---- single-name limit -------------------------------------------------------------------------------------------------------------------

def _signed_limits(plane, on: date) -> list[dict]:
    """The signed single-name limit rules in force on the day: {words, max, bucket, portfolio (name or None)}."""
    from sh_platform.v1 import e3_recon as E, e3_rules, wh
    with wh.connect(plane, read_only=True) as con:
        codes = [x[0] for x in con.execute("select rule_code from business_rules where rule_type = 'limit' order by rule_code").fetchall()]
        names = {str(c or "").strip().lower(): n for c, n in con.execute("select portfolio_code, portfolio_name from portfolios").fetchall()}
    out = []
    for c in codes:
        rule = e3_rules.current(plane, c, on)
        p = (rule or {}).get("parameters") or {}
        if p.get("dimension") != "single_name" or p.get("max_pct") is None:
            continue
        pname = names.get(str(p.get("portfolio_code") or "").strip().lower()) if p.get("portfolio_code") else None
        out.append({"words": E._limit_words(p, pname), "max": _d(p["max_pct"]), "bucket": str(p.get("bucket", "*")).strip().lower(),
                    "portfolio": pname, "code": p.get("portfolio_code")})
    return out


def _brief_limit(th: dict | None) -> Decimal | None:
    m = BRIEF_LIMIT.search(str(((th or {}).get("brief") or {}).get("question") or ""))
    return Decimal(m[1]) if m else None


def _over_limit(plane, k: dict, rows: list[dict], text: str, th: dict | None) -> dict | None:
    from sh_platform.v1 import e3_recon as E
    latest: dict = {}
    for x in rows:
        if x.get("concentration_pct") is not None and x.get("position_date") is not None:
            latest[x.get("portfolio")] = max(latest.get(x.get("portfolio"), x["position_date"]), x["position_date"])
    now = [x for x in rows if x.get("concentration_pct") is not None and latest.get(x.get("portfolio")) == x.get("position_date")]
    if not now:
        return None
    on = max(latest.values())

    def who(x) -> str:
        return f"{x['issuer']}" + (f", {x['portfolio']}" if x.get("portfolio") else "") + f", {_n(_d(x['concentration_pct']))}% on {_day_words(x['position_date'])}"
    limits, checks = _signed_limits(plane, on), []
    for lim in limits:
        if lim["portfolio"] and "portfolio" not in (now[0] or {}):
            return {"answer": f"Not available yet: {lim['words']} The ready table for {k['name']} has no split by portfolio.", "figure": None, "rows": []}
        scope = [x for x in now if (not lim["portfolio"] or x.get("portfolio") == lim["portfolio"]) and (lim["bucket"] in E.ANY or str(x["issuer"]).strip().lower() == lim["bucket"])]
        checks.append((lim, scope, [x for x in scope if _d(x["concentration_pct"]) > lim["max"]]))
    source = "the signed limit rule"
    if not limits and (cap := _brief_limit(th)) is not None:
        lim = {"words": f"No single name over {_n(cap)}% (the signed brief).", "max": cap}
        checks, source = [(lim, now, [x for x in now if _d(x["concentration_pct"]) > cap])], "the signed brief"
    top = sorted(now, key=lambda x: -_d(x["concentration_pct"]))
    if not checks:
        say = "; ".join(who(x) for x in top[:5])
        return {"answer": f"The single-name limit is not on record: no signed limit rule and the brief states none. The largest shares: {say}.",
                "figure": {"label": f"{k['name']} · largest", "value": f"{_n(_d(top[0]['concentration_pct']))}%", "change": ""},
                "rows": [{"label": x["issuer"], "value": f"{_n(_d(x['concentration_pct']))}%"} for x in top[:5]]}
    over = [(lim, x) for lim, _, hits in checks for x in hits]
    rules = " ".join(dict.fromkeys(lim["words"] for lim, _, _ in checks))
    if not over:
        biggest = max((x for _, scope, _ in checks for x in scope), key=lambda x: _d(x["concentration_pct"]), default=top[0])
        return {"answer": f"No holding is over its single-name limit. {rules} The largest share checked: {who(biggest)}.",
                "figure": {"label": f"{k['name']} · largest", "value": f"{_n(_d(biggest['concentration_pct']))}%", "change": ""}, "rows": []}
    say = "; ".join(f"{who(x)} against a maximum of {_n(lim['max'])}%" for lim, x in over)
    return {"answer": f"Over the single-name limit: {say}. Limit from {source}: {rules}",
            "figure": {"label": f"{k['name']} · over the limit · {over[0][1]['issuer']}", "value": f"{_n(_d(over[0][1]['concentration_pct']))}%", "change": ""},
            "rows": [{"label": x["issuer"], "value": f"{_n(_d(x['concentration_pct']))}%"} for _, x in over]}


# ---- cash break against the tolerance ------------------------------------------------------------------------------------------------------

def _breaks(plane, r: dict, rows: list[dict], text: str) -> dict | None:
    from sh_platform.v1 import e3_rules
    from sh_platform.v1.v3_figures import parse_when
    rows = [x for x in rows if x.get("day") is not None and x.get("cash_break") is not None]
    if not rows:
        return None
    day = lambda x: _day(x["day"])  # noqa: E731
    asked = parse_when(text)
    if asked and asked[2]:
        pick = [x for x in rows if day(x).month == asked[1] and day(x).day == asked[2] and (asked[0] is None or day(x).year == asked[0])]
        if not pick:
            return {"answer": f"Not available yet: {r['label']} has no figure for that day.", "figure": None, "rows": []}
    else:
        pick = rows
    on = max(day(x) for x in pick)
    pick = [x for x in pick if day(x) == on]
    tol = e3_rules.current(plane, "cash_tolerance", on)
    p = (tol or {}).get("parameters") or {}
    if p.get("abs_amount") is None:
        return None  # no signed tolerance: the plain figures answer (v3_figures._read)
    cap, ccy = _d(p["abs_amount"]), p.get("currency")
    over = [x for x in pick if (not ccy or x.get("currency") in (None, ccy)) and abs(_d(x["cash_break"])) > cap]
    inside = [x for x in pick if x not in over and _d(x["cash_break"]) != 0]
    same = [x for x in pick if x not in over and _d(x["cash_break"]) == 0]
    amt = lambda x: f"{_d(x['cash_break']):,.2f}" + (f" {x['currency']}" if x.get("currency") else "")  # noqa: E731
    rule = f"the signed cash tolerance of {cap:,.0f}{' ' + ccy if ccy else ''} per entity per day"
    head = (f"{r['label']} on {_day_words(on)}, over {rule}: " + "; ".join(f"{x['entity']} {amt(x)}" for x in over) + "."
            if over else f"No cash break over {rule} on {_day_words(on)}.")
    tail = (" Within the tolerance, not a break: " + "; ".join(f"{x['entity']} {amt(x)}" for x in inside) + "." if inside else "") + \
           (" Agree: " + ", ".join(x["entity"] for x in same) + "." if same else "")
    return {"answer": head + tail,
            "figure": {"label": f"{r['label']} · {_day_words(on)}" + (f" · {over[0]['entity']}" if over else ""), "value": amt(over[0]) if over else "0.00", "change": ""},
            "rows": [{"label": x["entity"], "value": amt(x)} for x in over]}


def kpi_by_recipe(text: str, kpis: list[dict]) -> dict | None:
    """The figure the question names by its recipe ("which entity has a cash break" is the brief's "Variance over 5,000" when that figure is the
    pack's cash break): the one figure of the brief built from the recipe the question's words match, else None (v3_figures.kpi_for decides)."""
    r = R.match({"name": text}, strict=False)
    got = [k for k in kpis if r and (R.bound(k) or {}).get("id") == r["id"]]  # the figure's binding, never its name
    return got[0] if len(got) == 1 else None
