"""K11 attribution: Brinson-Fachler allocation, selection and interaction per sleeve against the signed benchmark (k7_benchmark), contribution by
asset class and fund, active weights. Records only: portfolio values, flows and index returns all come from e3_calc / k7_benchmark (Decimal, never a model).

Per sleeve i, with portfolio weight wp, benchmark weight wb, returns rp, rb and total benchmark return Rb:
  allocation = (wp - wb)(rb - Rb)    selection = wb(rp - rb)    interaction = (wp - wb)(rp - rb)
Their sum over the sleeves is exactly Rp - Rb when Rp is the Modified Dietz return of e3_calc: weights and sleeve returns are built from the same
instrument values and confirmed flows (wp = (opening + day-weighted flows) / base, sleeve contribution = (closing - opening - flows) / base).
A holding outside every benchmark sleeve (hedge fund, no asset class) sits in "Outside the benchmark" with wb = 0 and rb = Rb, so it only has an interaction effect.
A sleeve the portfolio does not hold has rp taken as rb (no selection or interaction) and its allocation is the whole story.
Access (E1d): a fund the viewer may not see is a line without figures, and every sleeve holding one is masked (weight, return, contribution, effects),
since sleeve minus its visible funds would give the hidden fund. The totals then cover only the sleeves shown: the portfolio and active return and
the reconciling residual are withheld, as each would give the masked part by subtraction."""
from __future__ import annotations

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from sh_platform.v1 import a5_trail, e3_calc, k7_benchmark, wh
from sh_platform.v1.e3_calc import _FLOW, _dec, _live

# ponytail: asset_class text -> sleeve is a small map; a signed mapping table in the rules replaces it when asset classes multiply.
SLEEVE_OF = {"listed_equity": "equity", "listed": "equity", "bond": "bond",
             "private_equity": "private", "private_credit": "private", "infrastructure": "private", "venture": "private"}
LABEL = {"equity": "Global equity", "bond": "Global bonds", "private": "Private markets", "other": "Outside the benchmark"}
SPLITS = {"cap_size": ("cap_size", "market_cap_band"), "region": ("region", "country_of_risk", "country")}
ZERO = Decimal(0)
TOL = Decimal("0.0001")  # one basis point
MASKED = "Some funds in this sleeve are not visible to you"


def _fig(v) -> dict | None:
    return None if v is None else {"value": str(v), "pct": str((v * 100).quantize(Decimal("0.0001"), ROUND_HALF_UP))}


def _kind(c: dict) -> str:
    k = c["series_key"].upper()
    return "private" if c["spread_return"] != 0 else "equity" if "EQ" in k else "bond" if "BD" in k or "BOND" in k else c["series_key"]


def _instruments(con, ids: set) -> tuple[dict, dict]:
    """{id: {name, asset_class, type, + any split attribute the table has}}, {split: column or None}."""
    cols = {r[0] for r in con.execute("describe instruments").fetchall()}
    extra = {s: next((c for c in cs if c in cols), None) for s, cs in SPLITS.items()}
    named = [c for c in extra.values() if c]
    rows = con.execute("select " + ", ".join(["cast(id as varchar)", "canonical_name", "asset_class", "instrument_type"] + named) + " from instruments").fetchall()
    out = {}
    for r in rows:
        if r[0] in ids:
            out[r[0]] = {"name": r[1], "asset_class": r[2], "type": r[3], **{s: r[4 + named.index(c)] for s, c in extra.items() if c}}
    return out, extra


def attribute(plane, viewer, portfolio_id: str, portfolio_code: str, code: str, first, last) -> dict:
    """first/last: the first and last day the period covers. Figures are fractions with a pct string; problems say why a figure is missing."""
    ps = first - timedelta(1)
    c = k7_benchmark.comparison(plane, portfolio_id, code, ps, last)
    b, p = c["benchmark"], c["portfolio"]
    d = b["definition"]
    out = {"portfolio": {"id": portfolio_id, "code": portfolio_code}, "benchmark_code": code, "period": {"start": str(ps), "end": str(last)},
           "version_used": d and {"version": d["version_number"], "status": d["approval_status"], "name": d["benchmark_name"]},
           "certified": c["certified"], "problems": list(c["problems"]), "sleeves": [], "funds": [], "totals": None, "splits": {}}
    if c["difference"] is None or not b["components"]:
        return out
    ccy = d["reporting_currency"]
    v0, v1 = (e3_calc.portfolio_value(plane, portfolio_id, day, None, ccy) for day in (ps, last))
    o0, o1 = ({l["instrument_id"]: l for l in v["lines"]} for v in (v0, v1))
    cut = e3_calc._cutoff(None)
    days = Decimal((last - ps).days)
    flow, wflow = {}, {}
    with wh.connect(plane, read_only=True) as con:
        for m in _live(con, plane, "cash_movements", "supersedes_cash_movement_id", cut,
                       "t.portfolio_id = ? and t.effective_date > ? and t.effective_date <= ? and t.confirmation_status = 'confirmed'", [portfolio_id, ps, last]):
            sign = _FLOW.get(m["movement_type"])
            rate, _ = e3_calc.fx_explained(plane, m["currency"], ccy, m["effective_date"], cut)
            if sign is None or rate is None:
                continue
            amt = sign * abs(_dec(m["amount"])) * rate
            k = m.get("instrument_id")
            flow[k] = flow.get(k, ZERO) + amt
            wflow[k] = wflow.get(k, ZERO) + amt * Decimal((last - m["effective_date"]).days) / days
        ids = sorted({*o0, *o1, *[k for k in flow if k]})
        ins, extra = _instruments(con, set(ids))
        kinds = {r[0]: k for t, k in (("valuation_observations", "valuation"), ("position_snapshots", "position"))
                 for r in con.execute(f"select cast(id as varchar) from {t}").fetchall()}   # table is fixed above
    base = v0["total"] + sum(wflow.values(), ZERO)
    if base == 0:
        out["problems"].append("The portfolio had no value at the start of the period, so it cannot be attributed.")
        return out
    comps = {}
    for x in b["components"]:
        s = comps.setdefault(_kind(x), {"wb": ZERO, "rb_w": ZERO})
        s["wb"] += x["weight"]
        s["rb_w"] += x["weight"] * (x["index_return"] + x["spread_return"])
    Rb = b["value"]
    acc, groups, masked = {}, {s: {} for s, col in extra.items() if col}, set()
    for iid in ids + ([None] if None in flow else []):
        open_, close = (o0.get(iid, {}).get("value") or ZERO), (o1.get(iid, {}).get("value") or ZERO)
        f, w = flow.get(iid, ZERO), wflow.get(iid, ZERO)
        info = ins.get(iid, {"name": "Cash flows not tied to a fund", "asset_class": None})
        kind = SLEEVE_OF.get(info["asset_class"] or "", "other")
        kind = kind if kind in comps else "other"
        wp, contrib = (open_ + w) / base, (close - open_ - f) / base
        refs = [{"kind": kinds[l["source_row_id"]], "id": l["source_row_id"], "as_of": when, "date": str(l.get("valuation_date"))}
                for when, l in (("opening", o0.get(iid)), ("closing", o1.get(iid))) if l and l["source_row_id"] in kinds]
        a = acc.setdefault(kind, {"wp": ZERO, "contrib": ZERO, "trail": []})
        a["wp"] += wp          # sleeve totals use every holding; only the fund line is hidden from a person who may not see the fund
        a["contrib"] += contrib
        visible = iid is None or a5_trail._may(plane, viewer, None, iid)
        if visible:
            a["trail"] += refs
            out["funds"].append({"instrument_id": iid, "name": info["name"], "asset_class": info["asset_class"], "sleeve": kind, "visible": True,
                                 "weight": _fig(wp), "return": _fig(contrib / wp) if wp else None, "contribution": _fig(contrib), "trail": refs})
            for s, g in groups.items():
                gg = g.setdefault(info.get(s) or "Not recorded", {"wp": ZERO, "contrib": ZERO})
                gg["wp"] += wp
                gg["contrib"] += contrib
        else:
            masked.add(kind)
            out["funds"].append({"instrument_id": None, "name": "A fund you may not see", "sleeve": kind, "visible": False})
    for s, col in extra.items():
        out["splits"][s] = ({"available": True, "attribute": col, "groups": {k: {"weight": _fig(v["wp"]), "contribution": _fig(v["contrib"])} for k, v in sorted(groups[s].items())}}
                            if col else {"available": False, "missing": f"No instrument carries a {s.replace('_', ' ')} attribute, so this split cannot be worked out (looked for: {', '.join(SPLITS[s])})."})
    sleeves, tot = [], {"allocation": ZERO, "selection": ZERO, "interaction": ZERO}
    for kind in list(comps) + (["other"] if "other" in acc else []):
        wb = comps.get(kind, {}).get("wb", ZERO)
        rb = comps[kind]["rb_w"] / wb if kind in comps and wb else Rb
        a = acc.get(kind, {"wp": ZERO, "contrib": ZERO, "trail": []})
        wp = a["wp"]
        rp = a["contrib"] / wp if wp else None
        r = rb if rp is None else rp
        eff = {"allocation": (wp - wb) * (rb - Rb), "selection": wb * (r - rb), "interaction": (wp - wb) * (r - rb)}
        if kind in masked:
            sleeves.append({"sleeve": kind, "label": LABEL.get(kind, kind), "masked": True, "note": MASKED, "benchmark_weight": _fig(wb), "benchmark_return": _fig(rb),
                            **{k: None for k in ("portfolio_weight", "active_weight", "portfolio_return", "contribution", *eff, "total")}, "trail": [],
                            "benchmark_source": {"code": code, "version": d["version_number"]}})
            continue
        for k, v in eff.items():
            tot[k] += v
        sleeves.append({"sleeve": kind, "label": LABEL.get(kind, kind), "portfolio_weight": _fig(wp), "benchmark_weight": _fig(wb), "active_weight": _fig(wp - wb),
                        "portfolio_return": _fig(rp), "benchmark_return": _fig(rb), "contribution": _fig(a["contrib"]),
                        **{k: _fig(v) for k, v in eff.items()}, "total": _fig(sum(eff.values(), ZERO)), "trail": a["trail"],
                        "benchmark_source": {"code": code, "version": d["version_number"]}})
    explained = sum(tot.values(), ZERO)
    if masked:
        out.update({"sleeves": sleeves, "totals": {"partial": True, "note": "Some funds in this portfolio are not visible to you, so the totals cover only the sleeves shown.",
                                                   "portfolio_return": None, "benchmark_return": _fig(Rb), "active_return": None, **{k: _fig(v) for k, v in tot.items()},
                                                   "explained": _fig(explained), "unexplained": None, "reconciles": None}})
        return out
    resid = c["difference"] - explained
    out.update({"sleeves": sleeves, "totals": {"portfolio_return": _fig(p["value"]), "benchmark_return": _fig(Rb), "active_return": _fig(c["difference"]),
                                               **{k: _fig(v) for k, v in tot.items()}, "explained": _fig(explained), "unexplained": _fig(resid), "reconciles": abs(resid) < TOL, "partial": False}})
    if abs(resid) >= TOL:
        out["problems"].append("The effects do not add up to the active return; some cash flows could not be placed.")
    return out
