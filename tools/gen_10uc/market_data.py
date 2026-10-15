"""Deterministic market_data generator (no randomness): daily index levels and USD/SGD WMR 4pm fixing.
All figures come from docs/test/10uc_universe.json. Run: python tools/gen_10uc/market_data.py"""
import csv, json, datetime as dt
from decimal import Decimal as D, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tests/v1/fixtures/10uc/market_data"
U = json.load(open(ROOT / "docs/test/10uc_universe.json"))

def bdays(a, b):  # weekdays in (a, b]
    n, d = 0, a
    while d < b:
        d += dt.timedelta(1)
        n += d.weekday() < 5
    return n

def series(anchors, dp, start, end, override=None):
    pts = sorted((dt.date.fromisoformat(k), D(v)) for k, v in anchors.items())
    q = D(1).scaleb(-dp)
    out, d = {}, start
    while d <= end:
        if d.weekday() < 5:
            nxt = next((p for p in pts if p[0] >= d), None)
            prv = max((p for p in pts if p[0] <= d), key=lambda p: p[0], default=None)
            if prv and nxt:
                if prv[0] == nxt[0]: v = prv[1]
                else: v = prv[1] + (nxt[1] - prv[1]) * bdays(prv[0], d) / bdays(prv[0], nxt[0])
                out[d] = v.quantize(q, ROUND_HALF_UP)
        d += dt.timedelta(1)
    for k, v in (override or {}).items():
        out[dt.date.fromisoformat(k)] = D(v)
    return dict(sorted(out.items()))

S, E = dt.date(2025, 9, 30), dt.date(2026, 9, 30)
ids = U["index_levels"]["month_end_anchors"]
eq = series(ids["IDX:GLEQ:SYN"], 2, S, E)
bd = series(ids["IDX:GLBD:SYN"], 2, S, E)
fxu = U["fx_fixings"]
fx = series(fxu["month_end"], 4, S, dt.date(2026, 10, 9), fxu["daily_2026_09_01_to_10_09"])

with open(OUT / "index_levels_daily.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Date", "Global Equity Index (synthetic)", "Global Bond Index (synthetic)", "Currency", "Source"])
    for d in eq:
        w.writerow([d, eq[d], bd[d], "USD", "Synthetic Index Services - end of day"])
with open(OUT / "fx_usdsgd_wmr4pm.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Date", "Pair", "Fixing", "Rate (SGD per 1 USD)", "Source"])
    for d, v in fx.items():
        w.writerow([d, "USD/SGD", "WMR 4pm", v, "Synthetic FX fixing"])

def eff(d):  # weekend month-end anchors land on the prior Friday (no weekend rows)
    x = dt.date.fromisoformat(d)
    while x.weekday() > 4: x -= dt.timedelta(1)
    return str(x)
# verify by re-reading
def rd(p): return list(csv.DictReader(open(OUT / p)))
ie = {r["Date"]: r for r in rd("index_levels_daily.csv")}
for k, col in (("IDX:GLEQ:SYN", "Global Equity Index (synthetic)"), ("IDX:GLBD:SYN", "Global Bond Index (synthetic)")):
    for d, v in ids[k].items(): assert D(ie[eff(d)][col]) == D(v), (k, d)
fr = {r["Date"]: D(r["Rate (SGD per 1 USD)"]) for r in rd("fx_usdsgd_wmr4pm.csv")}
for d, v in fxu["month_end"].items(): assert fr[eff(d)] == D(v), d
for d, v in fxu["daily_2026_09_01_to_10_09"].items(): assert fr[d] == D(v), d
assert fr["2026-09-30"] == D(fxu["pinned"]["2026-09-30"]) and fr["2026-10-08"] == D(fxu["pinned"]["2026-10-08"])
b = U["benchmark"]["september_2026"]
r = lambda a, c: (D(ie[c]["Global Equity Index (synthetic)"]) / D(ie[a]["Global Equity Index (synthetic)"]) - 1) * 100
assert round(r("2026-08-31", "2026-09-30"), 4) == D(b["equity_index_return_pct"])
rb = (D(ie["2026-09-30"]["Global Bond Index (synthetic)"]) / D(ie["2026-08-31"]["Global Bond Index (synthetic)"]) - 1) * 100
assert round(rb, 4) == D(b["bond_index_return_pct"])
assert D("57600000") * fr["2026-09-30"] == D("77253120.00")
print(len(eq), "index rows;", len(fx), "fx rows; all asserts passed")
