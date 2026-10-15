"""Write docs/test/10uc_universe.json and docs/test/10UC-UNIVERSE.md: the single source of truth for the ten-use-case synthetic office.

Usage: python docs/test/make_10uc_universe.py
Deterministic (fixed seeds). Synthetic only: Evergreen Office, fictional managers, funds, people and indices. Every figure the
fixture generators and tools/seed_10uc.py use must come from the JSON this writes, never from here or from anywhere else.
Keeps every fact of tools/seed_evergreen.py and tools/seed_v3_demo.py and extends around them. Money is a string with 2 dp.
"""
from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
AS_OF = date(2026, 10, 9)
CUTOFF = "2026-10-09T18:00:00Z"
D = Decimal
CENT = D("0.01")


def m(x) -> str:
    return str(D(str(x)).quantize(CENT, ROUND_HALF_UP))


def pct(part, whole) -> str:
    return str((D(part) / D(whole) * 100).quantize(CENT, ROUND_HALF_UP))


def ts(d: date, h: int, mi: int = 0) -> str:
    return datetime(d.year, d.month, d.day, h, mi, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def month_end(y: int, mo: int) -> date:
    return (date(y + (mo == 12), mo % 12 + 1, 1) - timedelta(days=1))


def add_bd(d: date, n: int) -> date:
    """n business days after d (weekdays only; no holiday calendar, by convention)."""
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def bd_between(a: date, b: date) -> int:
    """Business days in (a, b]."""
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        n += d.weekday() < 5
    return n


MONTHS = [month_end(2025, mo) for mo in (10, 11, 12)] + [month_end(2026, mo) for mo in range(1, 10)]  # Oct 2025 .. Sep 2026
QUARTER_ENDS = {month_end(2025, 9), month_end(2025, 12), month_end(2026, 3), month_end(2026, 6), month_end(2026, 9)}
STATEMENT_DUE_BD = 10


def due(period_end: date) -> date:
    return add_bd(period_end, STATEMENT_DUE_BD)


def nav_received(period_end: date) -> str:
    return ts(add_bd(period_end, 2), 6)


# ---------- people, entities, portfolios ----------

PEOPLE = [  # (name, business role, platform role) exactly as tools/seed_evergreen.py
    ("Daniel Foo", "Chief Investment Officer", "sponsor"),
    ("Mei Chen", "Operations analyst", "analyst"),
    ("Raj Patel", "Finance", "approver"),
    ("Sofia Reyes", "Risk", "participant"),
    ("Anita Rao", "Head of data", "analyst"),
    ("Leo Park", "Data engineer", "analyst"),
    ("Grace Ong", "Company admin", "company_admin"),
]
ENTITIES = [("EG-HOLD", "Evergreen Holdings"), ("EG-TRUST", "Evergreen Family Trust"), ("EG-B", "Entity B")]
PORTFOLIOS = [  # (code, entity, name, holdings)
    ("EG-GROWTH", "EG-HOLD", "Evergreen Growth portfolio", ["A", "B"]),
    ("EG-LIQUID", "EG-TRUST", "Evergreen Liquid portfolio", ["LIQ"]),
    ("EG-B-OPS", "EG-B", "Entity B operating portfolio", ["C", "D", "E"]),
    ("EG-FUNDS", "EG-TRUST", "Evergreen Funds portfolio", ["H1", "H2", "L1", "L2"]),
]
MANAGERS = [
    ("MGR-NORTHGATE", "Northgate Partners", "Private equity, growth buyouts", "ir@northgate.example", "Elena Marsh"),
    ("MGR-BLUEWATER", "Bluewater Capital", "Private credit", "reporting@bluewater.example", "Tom Adeyemi"),
    ("MGR-CEDARPOINT", "Cedarpoint Ventures", "Venture and private equity", "lp@cedarpoint.example", "Hana Sato"),
    ("MGR-SALTMARSH", "Saltmarsh Real Assets", "Infrastructure", "investors@saltmarsh.example", "Marcus Bell"),
    ("MGR-KESTREL", "Kestrel Ridge Advisors", "Hedge funds (macro, equity long/short)", "ops@kestrelridge.example", "Priya Nair"),
    ("MGR-MERIDIAN", "Meridian Index Managers", "Index funds", "service@meridianindex.example", "Owen Clarke"),
]
# (key, name, type, asset_class, manager, frequency, admin code, naming variants)
FUNDS = [
    ("A", "Evergreen Growth I", "private_fund", "private_equity", "MGR-NORTHGATE", "monthly", "4471",
     ["EG Growth Fund I", "Fund A - Evergreen Growth I", "Evergreen Growth I"]),
    ("B", "Evergreen Income II", "private_fund", "private_credit", "MGR-BLUEWATER", "monthly", "4472",
     ["Fund B - Evergreen Liquid Book", "Fund B - Evergreen Income II", "Evergreen Income II"]),
    ("C", "Cedarpoint Ventures III", "private_fund", "venture", "MGR-CEDARPOINT", "quarterly", "4473", ["Cedarpoint Ventures III, L.P.", "CPV III"]),
    ("D", "Cedarpoint Opportunities II", "private_fund", "private_equity", "MGR-CEDARPOINT", "quarterly", "4474", ["Cedarpoint Opportunities Fund II", "CPO II"]),
    ("E", "Saltmarsh Infrastructure Fund II", "private_fund", "infrastructure", "MGR-SALTMARSH", "quarterly", "4475", ["Saltmarsh Infra II", "SIF II"]),
    ("H1", "Kestrel Ridge Macro Fund", "hedge_fund", "hedge_fund", "MGR-KESTREL", "monthly", "4481", ["Kestrel Ridge Macro Fund", "KR Macro Fund Ltd - Class B USD"]),
    ("H2", "Kestrel Ridge Equity Long/Short Fund", "hedge_fund", "hedge_fund", "MGR-KESTREL", "monthly", "4482", ["Kestrel Ridge Equity L/S", "KR Equity Long Short Ltd"]),
    ("L1", "Global Equity Index Fund (synthetic)", "liquid_fund", "listed_equity", "MGR-MERIDIAN", "monthly", "4491", ["Meridian Global Equity Index Fund"]),
    ("L2", "Global Bond Index Fund (synthetic)", "liquid_fund", "bond", "MGR-MERIDIAN", "monthly", "4492", ["Meridian Global Bond Index Fund"]),
]
UNITS = {"L1": D(50000), "L2": D(40000)}

# ---------- liquid securities: 30 Sep 2026 prices and quantities add to exactly 41,200,000 ----------
# (key, name, type, asset_class, sector, quantity, price 30 Sep). Equities: quantity a multiple of 10,000 so every value is a
# multiple of 100; bonds: nominal a multiple of 1,000,000, price per 1.00 nominal with 4 dp. PRC is the plug (10,000 units).
SECURITIES = [
    ("HVS", "Harborview Semiconductor", "listed_equity", "listed_equity", "Technology", 20000, "118.40"),
    ("NWL", "Northwind Logistics", "listed_equity", "listed_equity", "Industrials", 50000, "41.90"),
    ("BSU", "Bay Street Utilities", "listed_equity", "listed_equity", "Utilities", 40000, "48.05"),
    ("MRF", "Meridian Foods", "listed_equity", "listed_equity", "Consumer staples", 60000, "32.80"),
    ("CRH", "Coastal Rail Holdings", "listed_equity", "listed_equity", "Industrials", 30000, "77.50"),
    ("LKH", "Larkspur Health", "listed_equity", "listed_equity", "Health care", 40000, "56.25"),
    ("TWE", "Tidewater Energy", "listed_equity", "listed_equity", "Energy", 70000, "29.40"),
    ("GBM", "Granite Bay Materials", "listed_equity", "listed_equity", "Materials", 50000, "38.60"),
    ("OLR", "Orchard Lane Retail", "listed_equity", "listed_equity", "Consumer discretionary", 80000, "24.75"),
    ("SPS", "Silverpine Software", "listed_equity", "listed_equity", "Technology", 20000, "102.30"),
    ("BHI", "Blue Heron Insurance", "listed_equity", "listed_equity", "Financials", 30000, "64.10"),
    ("KFT", "Kingfisher Telecom", "listed_equity", "listed_equity", "Communication", 90000, "21.60"),
    ("RWP", "Redwood Pharma", "listed_equity", "listed_equity", "Health care", 40000, "47.35"),
    ("AHS", "Atlas Harbour Shipping", "listed_equity", "listed_equity", "Industrials", 60000, "35.20"),
    ("JCB", "Juniper Consumer Brands", "listed_equity", "listed_equity", "Consumer staples", 50000, "44.30"),
    ("EBG", "Evermore Banking Group", "listed_equity", "listed_equity", "Financials", 70000, "31.15"),
    ("CRB31", "Coastal Rail 5.1% 2031 bond", "bond", "bond", "Corporate bond", 2000000, "0.9910"),
    ("HTN29", "Harbour Treasury Note 2029 (synthetic sovereign)", "bond", "bond", "Government bond", 3000000, "0.9725"),
    ("KFB30", "Kingfisher Telecom 4.6% 2030 bond", "bond", "bond", "Corporate bond", 2000000, "0.9840"),
    ("PRC29", "Pacific Rim Convertible 2029 note", "convertible", None, "Unclassified", 10000, "112.20"),
]
LIQUID_SEP, LIQUID_AUG = D(41_200_000), D(39_552_000)


def security_prices() -> dict[str, dict[str, str]]:
    """Month-end prices per security, generated backward from 30 Sep with a fixed seed; the plug fixes 31 Aug to 39,552,000."""
    rng = random.Random(10)
    out = {k: {} for k, *_ in SECURITIES}
    for key, _, typ, *_rest, qty, p_sep in SECURITIES:
        dp = D("0.0001") if typ == "bond" else CENT
        p = D(p_sep)
        out[key][str(MONTHS[-1])] = str(p)
        for i in range(len(MONTHS) - 2, -1, -1):
            if typ == "bond":
                r = rng.uniform(-0.008, 0.008)
            elif i == len(MONTHS) - 2:
                r = rng.uniform(0.015, 0.065)  # Aug 2026 was about 4% below Sep (the seed's 0.96)
            else:
                r = rng.uniform(-0.045, 0.045)
            p = (p / (1 + D(str(round(r, 4))))).quantize(dp, ROUND_HALF_UP)
            out[key][str(MONTHS[i])] = str(p)
    aug = str(MONTHS[-2])
    raw = sum(D(q) * D(out[k][aug]) for k, *_r, q, _p in SECURITIES)
    for key, _, typ, *_rest, qty, _p in SECURITIES:  # scale every Aug price so the book lands near 39,552,000; the plug takes the rounding
        dp = D("0.0001") if typ == "bond" else CENT
        out[key][aug] = str((D(out[key][aug]) * LIQUID_AUG / raw).quantize(dp, ROUND_HALF_UP))
    others = sum(D(q) * D(out[k][aug]) for k, *_r, q, _p in SECURITIES if k != "PRC29")
    out["PRC29"][aug] = str(((LIQUID_AUG - others) / D(10000)).quantize(CENT))
    return out


# ---------- fund statements ----------

def hand_statements() -> list[dict]:
    """Every pinned statement (the seed's, the planted ones and the quarterly funds). key, period_end, kind, value, received, [title]."""
    S = []

    def add(key, pe, kind, value, received, title=None, status=None, note=None):
        S.append(dict(fund=key, period_end=str(pe), kind=kind, value=m(value) if value is not None else None, received_at=received,
                      title=title, status=status, note=note))

    # the seed's facts
    add("A", date(2026, 9, 30), "estimate", 10_000_000, ts(date(2026, 10, 2), 5), "Northgate Partners - Evergreen Growth I - 30 September 2026 - Estimate")
    add("A", date(2026, 9, 30), "amended", 10_180_000, ts(date(2026, 10, 7), 9), "Northgate Partners - Evergreen Growth I - 30 September 2026 - Amended statement",
        note="Not loaded by the seed; the demo drops the PDF (tools/make_e2_statements.py). Known now after loading: 10,180,000.")
    add("B", date(2026, 9, 30), "final", 6_400_000, ts(date(2026, 10, 1), 5), "Bluewater Capital - Fund B - Evergreen Liquid Book - 30 September 2026 - Final")
    add("A", date(2026, 8, 31), "final", 9_400_000, ts(date(2026, 9, 2), 5))
    add("B", date(2026, 8, 31), "final", 6_016_000, ts(date(2026, 9, 2), 5))
    # quarterly private funds (statement for 30 Sep 2025 carried into the window)
    for key, vals in {"C": [7_700_000, 7_900_000, 8_150_000, 8_420_000], "D": [4_300_000, 4_400_000, 4_650_000, None],
                      "E": [8_700_000, 8_900_000, 9_250_000, 9_600_000]}.items():
        for pe, v in zip(sorted(QUARTER_ENDS)[:4], vals):
            recv = {("D", "2026-03-31"): ts(date(2026, 4, 21), 10), ("E", "2026-06-30"): ts(date(2026, 7, 24), 15)}.get((key, str(pe)))
            if v is None:
                add(key, pe, "missing", None, None, status="missing", note="Never received. Due 14 Jul 2026.")
            else:
                add(key, pe, "final", v, recv or ts(add_bd(pe, 7), 10))
    add("C", date(2026, 6, 30), "amended", 8_275_000, ts(date(2026, 8, 18), 11), "Cedarpoint Ventures III - 30 June 2026 - Amended capital account statement",
        note="Replaces the 8,420,000 final of 10 Jul 2026; a portfolio company write-down of 145,000.")
    add("E", date(2026, 9, 30), "final", 9_950_000, ts(date(2026, 10, 8), 14), "Saltmarsh Infrastructure Fund II - Q3 2026 capital account statement",
        status="unverified", note="Extracted by Span on 8 Oct; Mei Chen has not confirmed the extraction yet.")
    # hedge funds: one final per month, Sep estimates so far; H1 Jul amended; H2 Aug late
    rng = random.Random(11)
    for key, sep_est, aug in (("H1", 7_320_000, 7_210_000), ("H2", 5_180_000, 5_090_000)):
        v = D(aug)
        series = {MONTHS[-2]: v}
        for pe in reversed(MONTHS[:-2]):
            v = (v / (1 + D(str(round(rng.uniform(-0.03, 0.03), 4))))).quantize(D("1"))
            series[pe] = v
        for pe, val in sorted(series.items()):
            recv = ts(add_bd(pe, 5), 9)
            if key == "H2" and pe == date(2026, 8, 31):
                recv = ts(date(2026, 9, 22), 9)
            if key == "H1" and pe == date(2026, 7, 31):
                add(key, pe, "final", 7_050_000, recv, "Kestrel Ridge Macro Fund - July 2026 - Final NAV")
                add(key, pe, "amended", 7_012_500, ts(date(2026, 8, 20), 9), "KR Macro Fund Ltd - Class B USD - July 2026 - Amended NAV",
                    note="Same fund under a second name; replaces 7,050,000 (fee accrual correction of 37,500).")
                continue
            add(key, pe, "final", val, recv)
        add(key, date(2026, 9, 30), "estimate", sep_est, ts(date(2026, 10, 6 if key == "H1" else 7), 9))
    # liquid index funds: official monthly statement on the first business day, value = units x price
    rng = random.Random(12)
    for key, p_sep in (("L1", D("123.00")), ("L2", D("102.50"))):
        p = p_sep
        prices = {MONTHS[-1]: p}
        for pe in reversed(MONTHS[:-1]):
            p = (p / (1 + D(str(round(rng.uniform(-0.035, 0.035) if key == "L1" else rng.uniform(-0.012, 0.012), 4))))).quantize(CENT)
            prices[pe] = p
        for pe, price in sorted(prices.items()):
            S.append(dict(fund=key, period_end=str(pe), kind="final", value=m(UNITS[key] * price), received_at=ts(add_bd(pe, 1), 7),
                          title=None, status=None, note=None, unit_price=str(price), units=str(UNITS[key])))
    # Fund A and B history before Aug 2026
    rng = random.Random(13)
    for key, aug in (("A", 9_400_000), ("B", 6_016_000)):
        v = D(aug)
        for pe in reversed(MONTHS[:-2]):
            v = (v / (1 + D(str(round(rng.uniform(-0.02, 0.04), 4))))).quantize(D("1"))
            S.append(dict(fund=key, period_end=str(pe), kind="final", value=m(v), received_at=ts(add_bd(pe, 2 + rng.randint(0, 3)), 5),
                          title=None, status=None, note=None))
    return S


def finish_statements(S: list[dict]) -> list[dict]:
    for s in S:
        pe = date.fromisoformat(s["period_end"])
        s["due_date"] = str(due(pe))
        s["statement_id"] = f"stmt-{s['fund']}-{s['period_end']}-{s['kind']}"
        if s["received_at"]:
            recd = date.fromisoformat(s["received_at"][:10])
            s["late_business_days"] = max(0, bd_between(due(pe), recd)) if s["kind"] != "amended" else 0
        else:
            s["late_business_days"] = None
        if s["status"] is None:
            s["status"] = {"estimate": "estimated", "final": "official", "amended": "official"}[s["kind"]]
    S.sort(key=lambda s: (s["fund"], s["period_end"], s["received_at"] or "9"))
    return S


def value_known(S, key, pe: date, at: str | None):
    """Latest statement value for a fund at period_end <= pe received by `at` (None = everything). Returns (value, statement)."""
    best = None
    for s in S:
        if s["fund"] != key or s["value"] is None or date.fromisoformat(s["period_end"]) > pe:
            continue
        if at and s["received_at"] > at:
            continue
        k = (s["period_end"], s["received_at"])
        if best is None or k > (best["period_end"], best["received_at"]):
            best = s
    return (D(best["value"]) if best else None), best


# ---------- market data ----------

def index_levels():
    rng = random.Random(14)
    anchors = {"IDX:GLEQ:SYN": {}, "IDX:GLBD:SYN": {}}
    eq, bd = D("1000.00"), D("1000.00")
    pes = [month_end(2025, 9)] + MONTHS
    for pe in pes:
        anchors["IDX:GLEQ:SYN"][str(pe)] = str(eq)
        anchors["IDX:GLBD:SYN"][str(pe)] = str(bd)
        last = pe == pes[-2]  # the Aug to Sep 2026 step is pinned: equity +3.50%, bonds +0.40%
        eq = (eq * (1 + (D("0.0350") if last else D(str(round(rng.uniform(-0.03, 0.045), 4)))))).quantize(CENT)
        bd = (bd * (1 + (D("0.0040") if last else D(str(round(rng.uniform(-0.008, 0.012), 4)))))).quantize(CENT)
    return anchors


def fx_fixings():
    rng = random.Random(15)
    pes = [month_end(2025, 9)] + MONTHS
    monthly = {}
    v = D("1.3412")
    for pe in reversed(pes):
        monthly[str(pe)] = str(v)
        v = (v / (1 + D(str(round(rng.uniform(-0.012, 0.012), 4))))).quantize(D("0.0001"))
    monthly = dict(sorted(monthly.items()))
    daily = {}
    a, b = D(monthly["2026-08-31"]), D("1.3412")
    d = date(2026, 9, 1)
    while d <= date(2026, 10, 9):
        if d <= date(2026, 9, 30):
            v = a + (b - a) * bd_between(date(2026, 8, 31), d) / bd_between(date(2026, 8, 31), date(2026, 9, 30))
        elif d <= date(2026, 10, 8):
            v = b + (D("1.3388") - b) * bd_between(date(2026, 9, 30), d) / bd_between(date(2026, 9, 30), date(2026, 10, 8))
        else:
            v = D("1.3388")  # 9 Oct: the 8 Oct fixing carried (not yet published)
        if d.weekday() < 5:
            daily[str(d)] = str(v.quantize(D("0.0001"), ROUND_HALF_UP))
        d += timedelta(days=1)
    return monthly, daily


# ---------- cash ----------

CASH_8OCT = {"EG-HOLD": ("2300000", "2300000"), "EG-TRUST": ("1150000", "1148200"), "EG-B": ("880400", "868000")}


def cash_daily():
    """30 calendar days 9 Sep .. 8 Oct, two views per entity, generated backward from the seed's 8 Oct figures."""
    rng = random.Random(16)
    rows = []
    for ent, (adm, trd) in CASH_8OCT.items():
        adm, trd = D(adm), D(trd)
        days = [date(2026, 10, 8) - timedelta(days=i) for i in range(30)]
        a = adm
        series = {}
        for i, d in enumerate(days):
            if i == 0:
                series[d] = (adm, trd)
                continue
            if d.weekday() < 5:
                a = a - D(rng.choice([-25000, -12000, -5000, 0, 0, 3000, 8000, 15000]) * (1 if ent != "EG-B" else 0.4)).quantize(D("1"))
            t = a - D(1800) if (ent == "EG-TRUST" and d >= date(2026, 10, 6)) else a
            series[d] = (a, t)
        for d in sorted(series):
            rows.append(dict(date=str(d), entity=ent, administrator=m(series[d][0]), trading_export=m(series[d][1]),
                             difference=m(series[d][0] - series[d][1])))
    return rows


# (movement_type, sign, low, high, description, counterparty, reference prefix): ordinary daily items, the same on both sides
ORDINARY = [("fee", -1, 150, 4500, "Bank and custody fee", "Harbourline Private Bank (synthetic)", "FEE"),
            ("coupon", 1, 500, 9000, "Coupon received", "Synthetic Paying Agent One", "CPN"),
            ("fx_settlement", -1, 1000, 20000, "USD leg of a USD/SGD spot settlement", "Synthetic FX Desk One", "FXS"),
            ("fx_settlement", 1, 1000, 20000, "USD leg of a SGD/USD spot settlement", "Synthetic FX Desk One", "FXS")]
ENT_TAG = {"EG-HOLD": "H", "EG-TRUST": "T", "EG-B": "B"}
B_WIRE = dict(reference="WIRE-20261008-B01", entity="EG-B", movement_type="wire", description="Legal fees, Saltmarsh Infrastructure Fund II",
              counterparty="Lowmoor & Tasker LLP (synthetic)", amount="-12400.00", currency="USD",
              administrator_date="2026-10-09", trading_export_date="2026-10-08", bank_date="2026-10-08")  # paid 8 Oct; the administrator books it a day late
T_CHARGE = dict(reference="CHG-20261006-T01", entity="EG-TRUST", movement_type="fee", description="Custody charge, booked by the trading desk only",
                counterparty="Harbourline Private Bank (synthetic)", amount="-1800.00", currency="USD",
                administrator_date=None, trading_export_date="2026-10-06", bank_date=None)  # the Trust's 1,800 (inside tolerance)


def cash_activity(daily: list[dict]) -> tuple[list[dict], dict]:
    """Every cash item per entity, 9 Sep .. 8 Oct, booked on each side on its own date, summing to the cash_daily balances on each side.
    Own random stream, so cash_daily's figures are unchanged. Returns (items, opening balances at the close of 8 Sep)."""
    rng = random.Random(1008)
    bal = {(r["entity"], r["date"]): r for r in daily}
    items, opening = [], {}
    for ent in CASH_8OCT:
        prev = None
        for ds in sorted(d for e, d in bal if e == ent):
            d, a = date.fromisoformat(ds), D(bal[(ent, ds)]["administrator"])
            if d.weekday() >= 5 and prev == a:
                continue
            day = []  # a weekend day only carries the automatic sweep (cash_daily moves some balances on a Saturday)
            for k, (typ, sign, lo, hi, text, cpty, pre) in enumerate(rng.sample(ORDINARY, rng.choice([2, 3])) if d.weekday() < 5 else [], 1):
                day.append(dict(reference=f"{pre}-{d:%Y%m%d}-{ENT_TAG[ent]}{k:02d}", entity=ent, movement_type=typ, description=text, counterparty=cpty,
                                amount=m(sign * D(rng.randint(lo * 100, hi * 100)) / 100), currency="USD"))
            if prev is None:
                opening[ent] = m(a - sum(D(i["amount"]) for i in day))
            else:
                rest = a - prev - sum(D(i["amount"]) for i in day)
                if rest:
                    day.append(dict(reference=f"TRF-{d:%Y%m%d}-{ENT_TAG[ent]}{len(day) + 1:02d}", entity=ent, movement_type="transfer",
                                    description="Sweep to or from the investment account", counterparty="Evergreen internal sweep account (synthetic)",
                                    amount=m(rest), currency="USD"))
            items += [dict(i, administrator_date=ds, trading_export_date=ds, bank_date=ds) for i in day]
            prev = a
    items += [B_WIRE, T_CHARGE]
    # proof: opening + items booked to date = the balance of that day, on each side, every day; the 8 Oct balances are the planted ones
    for r in daily:
        for side in ("administrator", "trading_export"):
            got = D(opening[r["entity"]]) + sum(D(i["amount"]) for i in items if i["entity"] == r["entity"] and i[f"{side}_date"] and i[f"{side}_date"] <= r["date"])
            assert got == D(r[side]), (r, side, got)
    return items, {e: dict(administrator=v, trading_export=v) for e, v in opening.items()}


# ---------- commitments and movements ----------

COMMITMENTS = [  # key, entity, commitment, committed_on, called before Aug 2025
    ("A", "EG-HOLD", 15_000_000, "2021-03-15", 10_500_000),
    ("B", "EG-HOLD", 8_000_000, "2022-06-01", 6_400_000),
    ("C", "EG-B", 6_000_000, "2023-09-20", 2_700_000),
    ("D", "EG-B", 5_000_000, "2022-11-10", 3_900_000),
    ("E", "EG-B", 10_000_000, "2024-04-02", 2_800_000),
]
MOVEMENTS = [  # id, fund, kind, amount, notice_date, due_date, status
    ("mv-2025-08-A-call", "A", "call", 250_000, "2025-08-04", "2025-08-20", "confirmed"),
    ("mv-2025-09-E-call", "E", "call", 600_000, "2025-09-08", "2025-09-25", "confirmed"),
    ("mv-2025-10-C-call", "C", "call", 300_000, "2025-10-06", "2025-10-24", "confirmed"),
    ("mv-2025-11-B-call", "B", "call", 400_000, "2025-11-03", "2025-11-19", "confirmed"),
    ("mv-2025-12-A-dist", "A", "distribution", 275_000, "2025-12-01", "2025-12-18", "confirmed"),
    ("mv-2026-01-D-call", "D", "call", 300_000, "2026-01-12", "2026-01-29", "confirmed"),
    ("mv-2026-02-E-call", "E", "call", 600_000, "2026-02-09", "2026-02-26", "confirmed"),
    ("mv-2026-03-A-call", "A", "call", 500_000, "2026-03-02", "2026-03-19", "confirmed"),
    ("mv-2026-04-C-call", "C", "call", 300_000, "2026-04-06", "2026-04-23", "confirmed"),
    ("mv-2026-05-B-call", "B", "call", 400_000, "2026-05-04", "2026-05-21", "confirmed"),
    ("mv-2026-06-C-call", "C", "call", 300_000, "2026-06-08", "2026-06-25", "confirmed"),
    ("mv-2026-07-D-call", "D", "call", 300_000, "2026-07-06", "2026-07-23", "confirmed"),
    ("mv-2026-09-D-dist", "D", "distribution", 180_000, "2026-09-01", "2026-09-15", "confirmed"),
    ("mv-2026-10-C-call", "C", "call", 450_000, "2026-10-02", "2026-10-20", "confirmed"),
    ("mv-2026-10-E-call", "E", "call", 600_000, "2026-10-06", "2026-10-30", "noticed"),
    ("mv-2026-11-A-dist", "A", "distribution", 320_000, "2026-10-05", "2026-11-16", "noticed"),
    ("mv-2026-12-D-call", "D", "call", 250_000, "2026-10-01", "2026-12-04", "confirmed"),
]


# ---------- trades (1-8 Oct 2026, EG-LIQUID) ----------

TRADES = [  # id, date, side, security, quantity, price, admin view (None = same), planted
    ("T-20261001-001", "2026-10-01", "buy", "MRF", 20000, "33.10", None, None),
    ("T-20261002-002", "2026-10-02", "sell", "BSU", 10000, "48.20", None, None),
    ("T-20261002-003", "2026-10-02", "buy", "NWL", 12000, "42.15", {"quantity": 10200}, "quantity mismatch"),
    ("T-20261006-005", "2026-10-06", "sell", "HVS", 5000, "118.40", "missing", "missing at administrator"),
    ("T-20261007-006", "2026-10-07", "buy", "CRB31", 1000000, "0.9910", None, None),
]


def build() -> dict:
    daily = cash_daily()
    activity, cash_opening = cash_activity(daily)
    S = finish_statements(hand_statements())
    prices = security_prices()
    sec_by = {s[0]: s for s in SECURITIES}
    idx = index_levels()
    fx_m, fx_d = fx_fixings()
    fund_by = {f[0]: f for f in FUNDS}
    sep, aug = MONTHS[-1], MONTHS[-2]

    # liquid book per month
    liquid = {}
    for pe in MONTHS:
        rows = [dict(security=k, quantity=str(q), price=prices[k][str(pe)], value=m(D(q) * D(prices[k][str(pe)]))) for k, *_r, q, _p in SECURITIES]
        liquid[str(pe)] = dict(total=m(sum(D(r["value"]) for r in rows)), positions=rows)
    assert D(liquid[str(sep)]["total"]) == LIQUID_SEP and D(liquid[str(aug)]["total"]) == LIQUID_AUG, liquid[str(sep)]["total"]

    # monthly valuations per fund: admin view (what the administrator knew at its NAV date) and known now (cutoff)
    valuations, admin_nav = [], []
    for pe in MONTHS:
        navat = nav_received(pe)
        for code, ent, _n, holdings in PORTFOLIOS:
            total_admin = total_now = D(0)
            for h in holdings:
                if h == "LIQ":
                    va = vn = D(liquid[str(pe)]["total"])
                    sa = sn = None
                else:
                    va, sa = value_known(S, h, pe, navat)
                    vn, sn = value_known(S, h, pe, CUTOFF)
                    age = (AS_OF - date.fromisoformat(sn["period_end"])).days if sn else None
                    status = sn["status"] if sn else "missing"
                    if sn and sn["kind"] == "amended":
                        status = "revised"
                    if sn and sn["period_end"] != str(pe):
                        status = "carried"
                    if pe == sep and sn and age > 90 and status in ("official", "carried", "revised"):
                        status = "stale"
                    valuations.append(dict(fund=h, portfolio=code, month_end=str(pe), administrator_value=m(va) if va else None,
                                           administrator_from=sa["statement_id"] if sa else None, known_now_value=m(vn) if vn else None,
                                           known_now_from=sn["statement_id"] if sn else None, known_now_status=status,
                                           valuation_date_known_now=sn["period_end"] if sn else None, age_days_at_as_of=age))
                total_admin += va or 0
                total_now += vn or 0
            admin_nav.append(dict(portfolio=code, nav_period_end=str(pe), nav_amount=m(total_admin), currency="USD", nav_status="approved_official",
                                  received_at=navat, investment_view_known_now=m(total_now)))
    nav_sep = {r["portfolio"]: r for r in admin_nav if r["nav_period_end"] == str(sep)}
    assert D(nav_sep["EG-GROWTH"]["nav_amount"]) == D(16_400_000), nav_sep["EG-GROWTH"]

    # NAV bridge at 30 Sep (known now at the cutoff vs administrator): revisions, timing, fx, unexplained
    bridge = []
    for code, ent, _n, holdings in PORTFOLIOS:
        rev = timing = D(0)
        parts = []
        for v in valuations:
            if v["portfolio"] != code or v["month_end"] != str(sep):
                continue
            diff = D(v["known_now_value"] or 0) - D(v["administrator_value"] or 0)
            if diff == 0:
                continue
            # every value recorded after the NAV was struck is a revision of what the NAV used, whether the manager revised the same statement
            # or a newer one arrived (the product's rule, answer key P04 and P05); timing stays for flows booked on different days (none at 30 Sep)
            kind = "revision"
            rev += diff
            parts.append(dict(fund=v["fund"], kind=kind, amount=m(diff), evidence=v["known_now_from"]))
        bridge.append(dict(portfolio=code, administrator_nav=nav_sep[code]["nav_amount"], investment_view=nav_sep[code]["investment_view_known_now"],
                           revisions=m(rev), timing=m(timing), fx="0.00", unexplained="0.00", parts=parts))
        assert D(nav_sep[code]["investment_view_known_now"]) - D(nav_sep[code]["nav_amount"]) == rev + timing

    # commitments
    commitments = []
    for key, ent, amt, on, opening in COMMITMENTS:
        called = D(opening) + sum(D(a) for _i, f, k, a, _n, dd, st in MOVEMENTS if f == key and k == "call" and st == "confirmed" and dd <= str(AS_OF))
        pending = sum(D(a) for _i, f, k, a, _n, dd, st in MOVEMENTS if f == key and k == "call" and (st == "noticed" or dd > str(AS_OF)))
        dist = D(opening) * 0 + sum(D(a) for _i, f, k, a, _n, dd, st in MOVEMENTS if f == key and k == "distribution" and st == "confirmed" and dd <= str(AS_OF))
        assert called + pending <= D(amt)
        commitments.append(dict(fund=key, legal_entity=ent, commitment_amount=m(amt), currency="USD", committed_on=on,
                                called_before_2025_08=m(opening), called_to_date=m(called), uncalled=m(D(amt) - called),
                                calls_noticed_or_due_after_as_of=m(pending), distributions_in_window=m(dist)))
    movements = [dict(id=i, fund=f, legal_entity=next(c[1] for c in COMMITMENTS if c[0] == f), notice_kind=k, amount=m(a), currency="USD",
                      notice_date=n, due_date=dd, confirmation_status=st, days_from_as_of=(date.fromisoformat(dd) - AS_OF).days)
                 for i, f, k, a, n, dd, st in MOVEMENTS]

    # liquidity at 9 Oct per entity
    liquidity = []
    for ent, (adm, _t) in CASH_8OCT.items():
        avail = D(adm)
        due_c = [x for x in movements if x["legal_entity"] == ent and x["notice_kind"] == "call" and 0 <= x["days_from_as_of"] <= 90]
        due_d = [x for x in movements if x["legal_entity"] == ent and x["notice_kind"] == "distribution" and 0 <= x["days_from_as_of"] <= 90]
        b = lambda lo, hi, xs: m(sum(D(x["amount"]) for x in xs if lo < x["days_from_as_of"] <= hi))
        conf30 = sum(D(x["amount"]) for x in due_c if x["days_from_as_of"] <= 30 and x["confirmation_status"] == "confirmed")
        all30 = sum(D(x["amount"]) for x in due_c if x["days_from_as_of"] <= 30)
        liquidity.append(dict(legal_entity=ent, available_cash_administrator_8_oct=m(avail),
                              calls_due={"30": b(-1, 30, due_c), "60": b(30, 60, due_c), "90": b(60, 90, due_c)},
                              distributions_expected={"30": b(-1, 30, due_d), "60": b(30, 60, due_d), "90": b(60, 90, due_d)},
                              unconfirmed_calls=[x["id"] for x in due_c if x["confirmation_status"] != "confirmed"],
                              after_confirmed_calls_30d=m(avail - conf30), after_all_noticed_calls_30d=m(avail - all30)))

    # limits at 30 Sep
    liq_total = LIQUID_SEP
    hvs = D(20000) * D("118.40")
    eq_share = sum(D(r["value"]) for r in liquid[str(sep)]["positions"] if sec_by[r["security"]][3] == "listed_equity")
    bops = nav_sep["EG-B-OPS"]
    ced = D(value_known(S, "C", sep, CUTOFF)[0]) + D(value_known(S, "D", sep, CUTOFF)[0])
    funds_total = D(nav_sep["EG-FUNDS"]["investment_view_known_now"])
    hedge = D(value_known(S, "H1", sep, CUTOFF)[0]) + D(value_known(S, "H2", sep, CUTOFF)[0])
    limits = [
        # a cap on one named holding: "any holding at most 5%" would breach on eight lines of this book, a sovereign note among them
        dict(rule="limit_single_name_liquid", portfolio="EG-LIQUID", dimension="single_name", bucket="Harborview Semiconductor", min_pct="0", max_pct="5",
             exposure_pct=pct(hvs, liq_total), item="HVS", item_value=m(hvs), result="breach", cause="real", case="limit_breach"),
        dict(rule="limit_listed_equity_liquid", portfolio="EG-LIQUID", dimension="asset_class", bucket="listed_equity", min_pct="60", max_pct="90",
             exposure_pct=pct(eq_share, liq_total), item="listed_equity", item_value=m(eq_share), result="within", cause=None, case=None,
             note="PRC29 has no asset class: shown as a classification question, not counted in any bucket."),
        dict(rule="limit_manager_entity_b", portfolio="EG-B-OPS", dimension="manager", bucket="Cedarpoint Ventures", min_pct="0", max_pct="55",
             exposure_pct=pct(ced, bops["investment_view_known_now"]), item="C+D", item_value=m(ced), result="breach", cause="stale data",
             case="limit_breach", note="Fund D's value is the 31 Mar 2026 statement, 192 days old; its 30 Jun statement is missing."),
        dict(rule="limit_hedge_funds", portfolio="EG-FUNDS", dimension="asset_class", bucket="hedge_fund", min_pct="20", max_pct="60",
             exposure_pct=pct(hedge, funds_total), item="H1+H2", item_value=m(hedge), result="within", cause=None, case=None),
    ]
    assert D(limits[0]["exposure_pct"]) > 5 and D(limits[2]["exposure_pct"]) > 55 and 60 < D(limits[1]["exposure_pct"]) < 90 and 20 < D(limits[3]["exposure_pct"]) < 60

    # FX forwards
    spot_sep, spot_8 = D("1.3412"), D("1.3388")
    fwd1_sgd = D(2_000_000) * D("1.3400")
    fwd2_sgd = D(3_000_000) * D("1.3425")
    fx_forwards = [
        dict(id="FXF-2026-001", asset_class="fx_forward", portfolio="EG-LIQUID", counterparty="Harbour Bank (synthetic)", trade_date="2026-09-15", value_date="2026-12-15",
             sell_currency="USD", sell_amount=m(2_000_000), buy_currency="SGD", buy_amount=m(fwd1_sgd), contract_rate="1.3400",
             mtm_usd_30_sep=m(fwd1_sgd / spot_sep - D(2_000_000)), mtm_rule="buy_amount / spot - sell_amount (forward points ignored by convention)",
             confirmation_rate="1.3400", confirmation_status="matched"),
        dict(id="FXF-2026-002", asset_class="fx_forward", portfolio="EG-LIQUID", counterparty="Harbour Bank (synthetic)", trade_date="2026-10-05", value_date="2027-01-05",
             sell_currency="USD", sell_amount=m(3_000_000), buy_currency="SGD", buy_amount=m(fwd2_sgd), contract_rate="1.3425",
             mtm_usd_8_oct=m(fwd2_sgd / spot_8 - D(3_000_000)), mtm_rule="buy_amount / spot - sell_amount (forward points ignored by convention)",
             confirmation_rate="1.3452", confirmation_buy_amount=m(D(3_000_000) * D("1.3452")), confirmation_status="mismatch",
             difference_sgd=m(D(3_000_000) * (D("1.3452") - D("1.3425"))), difference_usd_at_8_oct=m(D(3_000_000) * (D("1.3452") - D("1.3425")) / spot_8)),
    ]

    trades = []
    for tid, d, side, sec, q, p, adm, planted in TRADES:
        amt = m(D(q) * D(p))
        row = dict(id=tid, trade_date=d, settlement_date=str(add_bd(date.fromisoformat(d), 2)), portfolio="EG-LIQUID", side=side, security=sec,
                   quantity=str(q), price=p, amount=amt, currency="USD", trading_export="present", administrator="present" if adm != "missing" else "missing",
                   administrator_quantity=str(adm["quantity"]) if isinstance(adm, dict) else (None if adm == "missing" else str(q)),
                   planted=planted, difference_usd=None, result="matched" if planted is None else "break")
        if isinstance(adm, dict):
            row["difference_usd"] = m((D(q) - D(adm["quantity"])) * D(p))
        elif adm == "missing":
            row["difference_usd"] = amt
        trades.append(row)
    trades.append(dict(id="T-20261005-004", trade_date="2026-10-05", settlement_date="2027-01-05", portfolio="EG-LIQUID", side="sell USD / buy SGD",
                       security="FXF-2026-002", quantity=m(3_000_000), price="1.3425", amount=m(fwd2_sgd), currency="SGD", trading_export="present",
                       administrator="present", administrator_quantity=m(3_000_000), planted="FX forward confirmation rate mismatch",
                       difference_usd=fx_forwards[1]["difference_usd_at_8_oct"], result="break"))

    # benchmark returns
    def ret(series, a, b):
        return D(series[str(b)]) / D(series[str(a)]) - 1

    eq_r, bd_r = ret(idx["IDX:GLEQ:SYN"], aug, sep), ret(idx["IDX:GLBD:SYN"], aug, sep)
    pm_r = eq_r + D("0.0025")
    blend = D("0.42") * eq_r + D("0.28") * bd_r + D("0.30") * pm_r
    liquid_r = LIQUID_SEP / LIQUID_AUG - 1
    sixty_forty = D("0.6") * eq_r + D("0.4") * bd_r
    p4 = lambda x: str((x * 100).quantize(D("0.0001"), ROUND_HALF_UP))
    bench = dict(
        benchmark_code="EG-OFFICE-BLEND", benchmark_name="Evergreen office benchmark", reporting_currency="USD",
        versions=[
            dict(version_number=1, approval_status="approved", approved_by="Daniel Foo", effective_from="2026-01-01",
                 calculation_method="Weighted sum of monthly index returns; the private-markets sleeve is the equity index return plus 300 bps a year (25 bps a month). FX by the signed fx_fixing rule.",
                 components=[dict(market_series_key="IDX:GLEQ:SYN", component_weight="0.42", spread_bps=None, treatment_note="liquid sleeve 70% x 60% equity"),
                             dict(market_series_key="IDX:GLBD:SYN", component_weight="0.28", spread_bps=None, treatment_note="liquid sleeve 70% x 40% bonds"),
                             dict(market_series_key="IDX:GLEQ:SYN", component_weight="0.30", spread_bps="300", treatment_note="private-markets sleeve: equity index + 300 bps")]),
            dict(version_number=2, approval_status="in_progress", approved_by=None, effective_from="2026-10-01",
                 calculation_method="Re-weighting proposed by Sofia Reyes on 1 Oct 2026; component sheet still being filled in.",
                 components=[dict(market_series_key="IDX:GLEQ:SYN", component_weight="0.36", spread_bps=None, treatment_note="draft"),
                             dict(market_series_key="IDX:GLBD:SYN", component_weight="0.24", spread_bps=None, treatment_note="draft"),
                             dict(market_series_key="IDX:GLEQ:SYN", component_weight="0.40", spread_bps="300", treatment_note="draft")]),
        ],
        liquid_sleeve_60_40=dict(components={"IDX:GLEQ:SYN": "0.60", "IDX:GLBD:SYN": "0.40"}),
        september_2026=dict(equity_index_return_pct=p4(eq_r), bond_index_return_pct=p4(bd_r), private_sleeve_return_pct=p4(pm_r),
                            blend_v1_return_pct=p4(blend), sixty_forty_return_pct=p4(sixty_forty),
                            eg_liquid_portfolio_return_pct=p4(liquid_r), eg_liquid_minus_sixty_forty_pct=p4(liquid_r - sixty_forty),
                            note="EG-LIQUID had no flows in September (all trades are in October), so the return is 41,200,000 / 39,552,000 - 1."))

    rules = [
        dict(rule_code="cash_tolerance", rule_type="tolerance", owner="Raj Patel", approved_by="Daniel Foo", effective_from="2026-01-01",
             definition_text="Cash may differ by up to 5,000 USD per entity per day before it needs a case.",
             parameters={"abs_amount": 5000, "currency": "USD", "per": "entity_day"}),
        dict(rule_code="cio_materiality", rule_type="materiality", owner="Raj Patel", approved_by="Daniel Foo", effective_from="2026-01-01",
             definition_text="The CIO sees a change over 100,000 USD or 0.5% of a fund.",
             parameters={"abs_amount": 100000, "pct_of_fund": 0.5, "currency": "USD"}),
        dict(rule_code="estimate_use", rule_type="policy", owner="Raj Patel", approved_by="Daniel Foo", effective_from="2026-01-01",
             definition_text="A manager estimate may be used in the investment report only.", parameters={"allowed_in": ["investment_report"]}),
        dict(rule_code="statement_due", rule_type="deadline", owner="Mei Chen", approved_by="Daniel Foo", effective_from="2026-01-01",
             definition_text="A manager statement is due within 10 business days of the period end.", parameters={"business_days_after_month_end": 10}),
        dict(rule_code="fx_fixing", rule_type="fixing", owner="Raj Patel", approved_by="Daniel Foo", effective_from="2026-01-01",
             definition_text="Convert with the WMR 4pm USD/SGD fixing in the market data file.", parameters={"fixing": "WMR_4PM", "series_key": "FX:USDSGD:WMR_4PM"}),
        dict(rule_code="cash_call_alert_days", rule_type="deadline", owner="Raj Patel", approved_by="Daniel Foo", effective_from="2026-01-01",
             definition_text="A confirmed capital call due within 30 days opens a Finance case to fund it.", parameters={"days": 30}),
    ] + [dict(rule_code=l["rule"], rule_type="limit", owner="Sofia Reyes", approved_by="Daniel Foo", effective_from="2026-01-01",
              definition_text=(f"{l['portfolio']}: {l['bucket']} must be between {l['min_pct']}% and {l['max_pct']}% of the portfolio." if l["dimension"] == "single_name"
                               else f"{l['portfolio']}: {l['dimension']} '{l['bucket']}' between {l['min_pct']}% and {l['max_pct']}% of the portfolio."),
              parameters={"dimension": l["dimension"], "bucket": l["bucket"], "min_pct": float(l["min_pct"]), "max_pct": float(l["max_pct"]), "portfolio_code": l["portfolio"]})
         for l in limits]

    documents = [
        dict(id="doc-note-01", manager="MGR-NORTHGATE", document_type="meeting_note", document_date="2026-02-11", title="Northgate Partners annual meeting notes",
             key_facts=["Fund A expects two exits in 2026.", "Distribution of about 300,000 USD guided for Q4 2026."]),
        dict(id="doc-note-02", manager="MGR-BLUEWATER", document_type="meeting_note", document_date="2026-04-22", title="Bluewater Capital quarterly call",
             key_facts=["Fund B portfolio yield 9.1%.", "No defaults in the book."]),
        dict(id="doc-note-03", manager="MGR-CEDARPOINT", document_type="meeting_note", document_date="2026-05-19", title="Cedarpoint Ventures LP update call",
             key_facts=["Cedarpoint Ventures III: one portfolio company raising at a lower valuation.", "Cedarpoint Opportunities II reporting delayed by an auditor change."]),
        dict(id="doc-note-04", manager="MGR-KESTREL", document_type="meeting_note", document_date="2026-06-12", title="Kestrel Ridge Advisors on-site meeting",
             key_facts=["Macro fund run by two co-portfolio managers.", "Fee accruals reviewed monthly."]),
        dict(id="doc-note-05", manager="MGR-SALTMARSH", document_type="meeting_note", document_date="2026-07-30", title="Saltmarsh Real Assets Q2 call",
             key_facts=["Infrastructure Fund II: two new assets; a 600,000 USD call expected in Q4 2026."]),
        dict(id="doc-note-06", manager="MGR-MERIDIAN", document_type="meeting_note", document_date="2026-08-26", title="Meridian Index Managers service review",
             key_facts=["Daily pricing file to move to a new format in 2027."]),
        dict(id="doc-ddq-01", manager="MGR-KESTREL", document_type="ddq", document_date="2026-01-20", title="Kestrel Ridge Advisors DDQ 2026",
             key_facts=["Firm assets 2.4 bn USD (synthetic).", "Macro fund portfolio managers: Thomas Lindqvist, Priya Nair."]),
        dict(id="doc-ddq-02", manager="MGR-CEDARPOINT", document_type="ddq", document_date="2026-03-05", title="Cedarpoint Ventures DDQ 2026",
             key_facts=["Quarterly statements within 45 days of quarter end; under its side letter Evergreen Office receives them within 10 business days.", "Auditor change effective Q2 2026."]),
        dict(id="doc-news-01", manager="MGR-KESTREL", document_type="newsletter", document_date="2026-09-28", title="Kestrel Ridge Advisors Q3 2026 newsletter",
             key_facts=["Team change: Thomas Lindqvist left the firm on 30 September 2026; Priya Nair is sole portfolio manager of the Macro Fund from 1 October 2026."],
             planted="team change"),
        dict(id="doc-news-02", manager="MGR-NORTHGATE", document_type="newsletter", document_date="2026-07-15", title="Northgate Partners mid-year letter",
             key_facts=["Fund A: one exit signed, closing expected Q4 2026."]),
        dict(id="doc-ic-01", manager=None, document_type="ic_note", document_date="2026-09-17", title="Evergreen investment committee note, September 2026",
             key_facts=["Harborview Semiconductor above the 5% single-name limit; desk to trim.", "Benchmark re-weighting to be proposed by Risk."]),
    ]

    process = dict(
        project_title="Monthly investment report in USD and SGD", sponsor="Daniel Foo", builder="Leo Park", head_of_data="Anita Rao", ops="Mei Chen",
        needed_by="3rd business day of each month",
        steps=[
            dict(n=1, name="Collect the exports", who="Mei Chen", system="File drop", manual=True, control="Row count and file totals agree with the control totals of the file.", exception="A rejected file is re-requested the same day."),
            dict(n=2, name="Check cash against the administrator", who="Mei Chen", system="Excel", manual=True, control="Difference per entity per day within the cash tolerance of 5,000 USD.", exception="Over tolerance opens a break case (Entity B, 12,400 USD on 8 Oct 2026)."),
            dict(n=3, name="Collect manager statements", who="Mei Chen", system="Email", manual=True, control="Every expected statement received within 10 business days of the period end.", exception="Late or missing: follow-up draft to the manager."),
            dict(n=4, name="Convert to SGD", who="Raj Patel", system="Excel", manual=True, control="Converted at the WMR 4pm USD/SGD fixing of the period end.", exception="No fixing: hold the report."),
            dict(n=5, name="Review and approve the report", who="Raj Patel", system="Report pack", manual=False, control="Maker never checker; a manager estimate is used in the investment report only.", exception="A revision over the CIO materiality threshold (100,000 USD or 0.5% of a fund) reopens the review."),
            dict(n=6, name="Read the report", who="Daniel Foo", system="Report pack", manual=False, control="Issued version with cutoff shown.", exception="Questions to managers logged as open questions."),
        ],
        manual_steps_flagged_for_automation=[1, 2, 3, 4])

    report = dict(report_code="september_investment_report", period_end="2026-09-30", cutoff_at="2026-10-03T10:00:00Z", issued_at="2026-10-03T10:30:00Z",
                  approved_by="Daniel Foo", scope=["EG-GROWTH", "EG-LIQUID"], reporting_currencies=["USD", "SGD"], fx_rate_used="1.3412",
                  lines=[dict(label="Evergreen Growth I", value="10000000.00", status="estimated"), dict(label="Evergreen Income II", value="6400000.00", status="official"),
                         dict(label="Evergreen Liquid Book", value="41200000.00", status="official"), dict(label="Total", value="57600000.00", status="estimated")],
                  total_sgd=m(D(57_600_000) * spot_sep))

    # ---------- planted facts ----------
    stmt = {s["statement_id"]: s for s in S}
    sep_expected = {k: next((x for x in S if x["fund"] == k and x["period_end"] == "2026-09-30"), None) for k, *_ in FUNDS}
    d_missing_bd = bd_between(date(2026, 7, 14), AS_OF)
    kestrel_changes = ["Statement: July 2026 NAV amended on 20 Aug 2026 from 7,050,000 to 7,012,500 USD (fee accrual).",
                       "Statement: August 2026 statement for the Equity Long/Short Fund received 22 Sep 2026, 6 business days late (due 14 Sep).",
                       "Newsletter 28 Sep 2026: Thomas Lindqvist left; Priya Nair sole portfolio manager of the Macro Fund from 1 Oct 2026."]
    eg_funds_bridge = next(b for b in bridge if b["portfolio"] == "EG-FUNDS")
    P = []

    def plant(uc, fact, expected, where, role, ids=None):
        P.append(dict(id=f"P{sum(1 for x in P if x['id'][-1].isdigit()) + 1:02d}", use_case=uc, fact=fact, expected=expected, where=where, role=role, evidence=ids or []))

    plant("UC1", "September report as issued", "A 10,000,000 (estimated), B 6,400,000, Evergreen Liquid Book 41,200,000, total 57,600,000 USD; issued 3 Oct 2026 10:30, cutoff 3 Oct 10:00; SGD total 77,253,120.00 at 1.3412",
          "Consume > Office view > Issued vs known now; CIO Brief", "sponsor", ["report:september_investment_report"])
    plant("UC1", "Fund A amended statement (known now)", "10,180,000 USD, received 7 Oct 2026; +180,000 (1.80%) over the issued 10,000,000; over cio_materiality (100,000 USD / 0.5%); status word Revised",
          "Consume > Office view > Issued vs known now; Today card 'Revised'; CIO Brief", "sponsor", ["stmt-A-2026-09-30-amended"])
    plant("UC1", "NAV bridge EG-GROWTH 30 Sep", "Investment view 16,580,000 vs administrator NAV 16,400,000: revisions +180,000 (Fund A), timing 0, FX 0, unexplained 0",
          "Consume > Office view > NAV bridge", "sponsor", ["stmt-A-2026-09-30-amended"])
    plant("UC1", "NAV bridge EG-B-OPS 30 Sep", "Investment view 22,875,000 vs administrator NAV 22,525,000: revisions +350,000 (Fund E Q3 statement recorded 8 Oct, after the NAV of 2 Oct); timing 0",
          "Consume > Office view > NAV bridge", "sponsor", ["stmt-E-2026-09-30-final"])
    plant("UC1", "NAV bridge EG-FUNDS 30 Sep", f"Investment view {eg_funds_bridge['investment_view']} vs administrator NAV {eg_funds_bridge['administrator_nav']}: revisions {eg_funds_bridge['revisions']} (H1 and H2 September estimates received 6 and 7 Oct, after the NAV of 2 Oct); timing 0",
          "Consume > Office view > NAV bridge", "sponsor", ["stmt-H1-2026-09-30-estimate", "stmt-H2-2026-09-30-estimate"])
    plant("UC1", "Why did this move: liquid book Aug to Sep", f"39,552,000 to 41,200,000 USD, +1,648,000 (+{p4(liquid_r)}%); no trades in September; largest contributor shown per security from the monthly prices",
          "Consume > Office view > Why did this move", "sponsor")
    plant("UC1", "Holdings status words at 30 Sep", "A Revised (after the amended statement; Estimated before), B Official, C Stale (30 Jun 2026 amended value, 101 days), D Stale (31 Mar 2026, 192 days), E Unverified (9,950,000 extracted, not confirmed), H1/H2 Estimated, L1/L2 Official, PRC29 'Needs a class'",
          "Consume > Office view > Holdings", "analyst")
    plant("UC2", "Entity B cash break 8 Oct", "Administrator 880,400 vs trading export 868,000: 12,400 USD over the 5,000 tolerance; one break case. Trust 1,150,000 vs 1,148,200 (1,800, inside tolerance, no case). Holdings 2,300,000 both views.",
          "Action > Reconciliations (cash) and Cases", "analyst, approver")
    P.append(dict(id="P08b", use_case="UC2", fact="Entity B cash break cause: one wire booked a day apart",
                  expected="Tally ranks WIRE-20261008-B01, 12,400 USD (legal fees, Saltmarsh Infrastructure Fund II), first: paid and booked by the trading desk on 8 Oct "
                           "(the bank agrees, 868,000), booked by the administrator on 9 Oct: a timing difference that clears when the administrator books it. "
                           "Every other item of the 30 days is booked the same day on both sides; the Trust's 1,800 is one charge booked by the trading desk only (CHG-20261006-T01).",
                  where="Action > Cases > Cash differs · Entity B · 2026-10-08 > Tally", role="analyst", evidence=["WIRE-20261008-B01"]))
    plant("UC3", "September statements expected vs received at 9 Oct", "Due 14 Oct 2026 (10 business days). Received: A estimate 2 Oct, B final 1 Oct, E final 8 Oct (unverified), H1 estimate 6 Oct, H2 estimate 7 Oct, L1 and L2 1 Oct. Waiting, not yet late: C, D.",
          "Action > Managers", "analyst")
    plant("UC3", "Late statements", "H2 August 2026: due 14 Sep, received 22 Sep, 6 business days late. E June 2026: due 14 Jul, received 24 Jul, 8 business days late. (Also D March 2026: due 14 Apr, received 21 Apr, 5 business days late.)",
          "Action > Managers > late", "analyst", ["stmt-H2-2026-08-31-final", "stmt-E-2026-06-30-final", "stmt-D-2026-03-31-final"])
    plant("UC3", "Missing statement", f"Cedarpoint Opportunities II (Fund D) 30 June 2026: due 14 Jul 2026, never received, {d_missing_bd} business days overdue at 9 Oct. Follow-up draft addressed to Hana Sato, Cedarpoint Ventures, names the fund and the period; never sent by the product.",
          "Action > Managers > missing; Draft a follow-up", "analyst", ["stmt-D-2026-06-30-missing"])
    plant("UC3", "Revised statements (3)", "A 30 Sep: 10,000,000 to 10,180,000 (+180,000). C 30 Jun: 8,420,000 to 8,275,000 (-145,000, 18 Aug). H1 31 Jul: 7,050,000 to 7,012,500 (-37,500, 20 Aug).",
          "Action > Managers > revised; Consume > Managers > statements timeline", "analyst", ["stmt-A-2026-09-30-amended", "stmt-C-2026-06-30-amended", "stmt-H1-2026-07-31-amended"])
    plant("UC3", "Same fund under two names", "'KR Macro Fund Ltd - Class B USD' (July amended statement) and 'Kestrel Ridge Macro Fund' are one fund (H1, administrator code 4481); Fund B appears as 'Fund B - Evergreen Liquid Book' and 'Evergreen Income II'. The inbox shows one row per fund, never two.",
          "Action > Managers; Settings > identifiers", "analyst", ["stmt-H1-2026-07-31-amended"])
    plant("UC4", "Benchmark v1 September 2026", f"Equity index {p4(eq_r)}%, bond index {p4(bd_r)}%, private sleeve {p4(pm_r)}% (equity + 25 bps a month); blend v1 (0.42/0.28/0.30) {p4(blend)}%; 60/40 liquid sleeve {p4(sixty_forty)}%; EG-LIQUID {p4(liquid_r)}%, difference to 60/40 {p4(liquid_r - sixty_forty)} points",
          "Consume tile 'portfolio vs benchmark'; Build plan gold_investment_report_benchmark_monthly", "approver")
    plant("UC4", "Benchmark v2 In Progress", "Version 2 (0.36/0.24/0.40, proposed 1 Oct 2026 by Sofia Reyes) is in_progress: refused for certified output and shown as a policy question; certified figures use v1.",
          "Build > benchmark; Settings > Rules", "approver")
    plant("UC4", "SGD conversion", "USD figures at 30 Sep convert at 1.3412 (WMR 4pm, fx_fixing); 8 Oct fixing 1.3388. Total 57,600,000 USD = 77,253,120.00 SGD.",
          "Consume > Office view (USD/SGD switch)", "approver")
    plant("UC5", "Real limit breach", f"EG-LIQUID single name max 5%: Harborview Semiconductor 2,368,000 of 41,200,000 = {limits[0]['exposure_pct']}%; case limit_breach, cause 'real breach'. (The desk sold 5,000 shares on 6 Oct; the administrator has not booked it.)",
          "Action > Reconciliations > Limits; Cases", "participant, analyst")
    plant("UC5", "Limit breach caused by a stale valuation", f"EG-B-OPS manager Cedarpoint Ventures max 55%: C 8,275,000 + D 4,650,000 = 12,925,000 of {bops['investment_view_known_now']} = {limits[2]['exposure_pct']}%; case limit_breach, cause 'stale data' (Fund D valued 31 Mar 2026, 192 days old, June statement missing; Fund C's 30 Jun value is 101 days old).",
          "Action > Reconciliations > Limits; Cases", "participant, analyst")
    plant("UC5", "Instrument without asset class", f"Pacific Rim Convertible 2029 note (PRC29) has no asset_class; 1,122,000 USD = {pct(1_122_000, liq_total)}% of EG-LIQUID; shown as a classification question ('Needs a class'), counted in no bucket, no breach.",
          "Action > Reconciliations > Limits; Settings > instruments", "participant")
    plant("UC5", "Limits within range", f"EG-LIQUID listed_equity {limits[1]['exposure_pct']}% (60-90); EG-FUNDS hedge_fund {limits[3]['exposure_pct']}% (20-60). No case.",
          "Action > Reconciliations > Limits", "participant")
    plant("UC6", "Capital calls due within 30 days", "Fund C 450,000 USD due 20 Oct 2026 (notice 2 Oct, confirmed) and Fund E 600,000 USD due 30 Oct 2026 (notice 6 Oct, noticed, NOT confirmed, flagged). Both Entity B.",
          "Consume > Office view > Liquidity; Action > Cases (Finance)", "approver", ["mv-2026-10-C-call", "mv-2026-10-E-call"])
    plant("UC6", "Entity B after-call cash", "Available 880,400 (administrator, 8 Oct). After the confirmed call: 430,400. After both noticed calls: -169,600 (shortfall). Finance case 'Fund the capital call' opened for the Fund C call (due within cash_call_alert_days = 30).",
          "Consume > Office view > Liquidity; Action > Cases", "approver")
    plant("UC6", "Calls and distributions 60/90 days", "Fund D call 250,000 due 4 Dec 2026 (confirmed, 60-day bucket, Entity B). Fund A distribution 320,000 expected 16 Nov 2026 (noticed, Evergreen Holdings).",
          "Consume > Office view > Liquidity", "approver", ["mv-2026-12-D-call", "mv-2026-11-A-dist"])
    plant("UC6", "Commitments register", "; ".join(f"{c['fund']} {c['commitment_amount']} committed, {c['called_to_date']} called, {c['uncalled']} uncalled" for c in commitments) + ". Called never exceeds commitment.",
          "Consume > Managers > profile; Office view > Liquidity", "approver")
    plant("UC7", "Newsletter team change", "Kestrel Ridge Advisors Q3 2026 newsletter (28 Sep 2026): Thomas Lindqvist left on 30 Sep 2026; Priya Nair sole portfolio manager of the Macro Fund from 1 Oct 2026. Shown with the source chip; the product never says whether this is good or bad.",
          "Consume > Managers > Kestrel Ridge Advisors", "sponsor, analyst", ["doc-news-01"])
    plant("UC7", "What changed since the last meeting (Kestrel Ridge, 12 Jun 2026)", " | ".join(kestrel_changes),
          "Consume > Managers > 'What changed since the last meeting?'", "sponsor", ["doc-note-04", "stmt-H1-2026-07-31-amended", "stmt-H2-2026-08-31-final", "doc-news-01"])
    plant("UC7", "Cedarpoint Ventures profile", "Funds C and D; commitments 6,000,000 and 5,000,000; D last valuation 31 Mar 2026 (stale), June statement missing; DDQ says quarterly statements within 45 days (10 business days for Evergreen Office under its side letter) and an auditor change in Q2 2026; open question: June statement.",
          "Consume > Managers > Cedarpoint Ventures", "sponsor, analyst", ["doc-ddq-02", "doc-note-03"])
    plant("UC8", "Trade break: quantity mismatch", "T-20261002-003 buy Northwind Logistics: trading export 12,000 at 42.15, administrator 10,200; 1,800 shares = 75,870.00 USD, over the 5,000 tolerance; break case.",
          "Action > Reconciliations > trade_vs_admin; Cases", "analyst", ["T-20261002-003"])
    plant("UC8", "Trade break: missing at the administrator", "T-20261006-005 sell 5,000 Harborview Semiconductor at 118.40 (592,000.00 USD) is in the trading export and not at the administrator; break case.",
          "Action > Reconciliations > trade_vs_admin; Cases", "analyst", ["T-20261006-005"])
    plant("UC8", "FX forward confirmation mismatch", f"FXF-2026-002 sell USD 3,000,000 / buy SGD: trading export rate 1.3425 (SGD 4,027,500.00), counterparty confirmation 1.3452 (SGD 4,035,600.00); difference SGD 8,100.00 = USD {fx_forwards[1]['difference_usd_at_8_oct']} at 1.3388, over tolerance; break case. FXF-2026-001 matches.",
          "Action > Reconciliations > trade_vs_admin; Cases", "analyst", ["FXF-2026-002"])
    plant("UC8", "Matched trades", "T-20261001-001, T-20261002-002, T-20261007-006 match on external_trade_id and amount: no case.",
          "Action > Reconciliations > trade_vs_admin", "analyst")
    plant("UC9", "SOP from the signed process map", "6 steps with owner, system, input, output, control and exception; 4 manual steps flagged for automation: 1 Collect the exports (File drop), 2 Check cash against the administrator (Excel), 3 Collect manager statements (Email), 4 Convert to SGD (Excel); hand-overs 1-2, 2-3, 3-4, 4-5, 5-6; download as .docx or .md.",
          "Intent > signed intent 'Monthly investment report in USD and SGD' > Download the SOP", "sponsor")
    plant("UC10", "Pipeline and dashboard", "Project 'Monthly investment report in USD and SGD' live: bronze_administrator_positions, bronze_trading_export_positions; gold_investment_report_holdings_monthly, gold_investment_report_cash_daily; dashboard dash-0ad2b1c7 with 3 accepted tiles (K01 Net worth by entity, K02 Cash by entity, K03 Holdings by status) shared with Daniel Foo and Raj Patel.",
          "Intent > Build > Consume", "analyst")

    return dict(
        meta=dict(title="Evergreen Office: ten use case universe", as_of=str(AS_OF), cutoff_at=CUTOFF, synthetic=True, generator="docs/test/make_10uc_universe.py",
                  seeds=[10, 11, 12, 13, 14, 15, 16], money="strings, 2 dp, USD unless stated", conventions=[
                      "Business days are weekdays; no holiday calendar.",
                      "A statement is due 10 business days after its period end (statement_due); late = business days after the due date.",
                      "The administrator NAV of a portfolio is the sum of its investment holdings at the values the administrator had at 06:00 UTC on the 2nd business day after the month end; cash is held at entity level and reported in the cash file, not inside the portfolio NAV (this keeps the seed's EG-GROWTH NAV of 16,400,000 = A 10,000,000 + B 6,400,000).",
                      "Known now = the latest statement for the period received by the cutoff, whatever its status; the Fund A amended statement counts as known only once the demo drops it.",
                      "Quarterly funds carry their last statement forward in the months between; any value older than 90 days at the as-of date is Stale (C and D at 9 Oct 2026).",
                      "The liquid book instrument 'Evergreen Liquid Book' is the sum of the 20 securities; quantity x price = value on every line.",
                      "Bond prices are per 1.00 nominal (4 dp); the convertible is quoted per unit; equities per share.",
                      "FX forward mark-to-market = buy_amount / spot - sell_amount (forward points ignored).",
                      "Index and FX daily levels: linear interpolation between month-end anchors over business days, 2 dp (indices) or 4 dp (FX); no noise."]),
        company=dict(id="evergreen", name="Evergreen Office", industry="family_office", base_currency="USD", reporting_currencies=["USD", "SGD"]),
        people=[dict(name=n, business_role=r, platform_role=p, email=f"{'.'.join(n.lower().split())}.evergreen@example.test") for n, r, p in PEOPLE],
        legal_entities=[dict(entity_code=c, entity_name=n, base_currency="USD", active_from="2020-01-01") for c, n in ENTITIES],
        portfolios=[dict(portfolio_code=c, legal_entity=e, portfolio_name=n, base_currency="USD", active_from="2020-01-01", holdings=h) for c, e, n, h in PORTFOLIOS],
        managers=[dict(id=i, name=n, strategy=s, contact_email=e, contact_name=c, funds=[f[0] for f in FUNDS if f[4] == i]) for i, n, s, e, c in MANAGERS],
        funds=[dict(key=k, canonical_name=n, instrument_type=t, asset_class=a, manager=mg, statement_frequency=fr, currency="USD",
                    portfolio=next(p[0] for p in PORTFOLIOS if k in p[3]), legal_entity=next(p[1] for p in PORTFOLIOS if k in p[3]),
                    identifiers={"administrator": {"administrator_code": code}, "manager_email": {"manager_fund_name": names}},
                    units=str(UNITS[k]) if k in UNITS else None) for k, n, t, a, mg, fr, code, names in FUNDS]
              + [dict(key="LIQ", canonical_name="Evergreen Liquid Book", instrument_type="liquid_book", asset_class="listed", manager=None, statement_frequency="daily",
                      currency="USD", portfolio="EG-LIQUID", legal_entity="EG-TRUST", identifiers={}, units=None, note="roll-up of the 20 securities")],
        securities=[dict(key=k, canonical_name=n, instrument_type=t, asset_class=a, sector=s, currency="USD", portfolio="EG-LIQUID", quantity_30_sep=str(q),
                         identifiers={"administrator": {"administrator_code": str(5000 + i)}, "trading_export": {"ticker": f"{k}.SYN"}, "internal": {"security_id": f"SEC-{k}"}},
                         prices_month_end=prices[k]) for i, (k, n, t, a, s, q, _p) in enumerate(SECURITIES, 1)],
        liquid_book_month_end=liquid,
        fx_forwards=fx_forwards,
        statements=S,
        valuations_monthly=valuations,
        administrator_nav_monthly=admin_nav,
        nav_bridge_30_sep=bridge,
        cash_daily=daily,
        cash_opening_8_sep=cash_opening,
        cash_activity=activity,
        cash_8_oct=[dict(legal_entity=e, portfolio=next(p[0] for p in PORTFOLIOS if p[1] == e), administrator=m(a), trading_export=m(t), difference=m(D(a) - D(t)),
                         over_tolerance=abs(D(a) - D(t)) > 5000) for e, (a, t) in CASH_8OCT.items()],
        commitments=commitments,
        cash_movements=movements,
        liquidity_9_oct=liquidity,
        trades_oct=trades,
        index_levels=dict(series={"IDX:GLEQ:SYN": "Global Equity Index (synthetic)", "IDX:GLBD:SYN": "Global Bond Index (synthetic)"}, month_end_anchors=idx,
                          daily_rule="level(d) = anchor_prev + (anchor_next - anchor_prev) * business_days(prev, d) / business_days(prev, next), rounded to 2 dp; weekdays only"),
        fx_fixings=dict(series_key="FX:USDSGD:WMR_4PM", fixing="WMR_4PM", month_end=fx_m, daily_2026_09_01_to_10_09=fx_d, pinned={"2026-09-30": "1.3412", "2026-10-08": "1.3388"},
                        daily_rule="same linear rule as the indices, 4 dp; 9 Oct carries the 8 Oct fixing"),
        benchmark=bench,
        rules=rules,
        limits_check_30_sep=limits,
        documents=documents,
        process=process,
        report_issued=report,
        project=dict(title="Monthly investment report in USD and SGD", slug="investment_report", dashboard_id="dash-0ad2b1c7",
                     tiles=["t-000001 Net worth by entity (K01)", "t-000002 Cash by entity (K02)", "t-000003 Holdings by status (K03)"],
                     bronze=["bronze_administrator_positions", "bronze_trading_export_positions"],
                     gold=["gold_investment_report_holdings_monthly", "gold_investment_report_cash_daily"], stage="live"),
        planted=P,
    )


# ---------- readable file ----------

def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join("" if c is None else str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def markdown(U: dict) -> str:
    L = ["# Evergreen Office: the ten use case universe (synthetic)", "",
         f"As of {U['meta']['as_of']}, cutoff {U['meta']['cutoff_at']}. Machine file: `docs/test/10uc_universe.json`, written by `{U['meta']['generator']}` (fixed seeds). "
         "Every fixture, seed and expected figure must come from the JSON. All names, managers, funds, people and indices are fictional; money in USD unless stated.", "",
         "## Conventions", ""] + [f"- {c}" for c in U["meta"]["conventions"]] + ["", "## People", "",
         table(["Name", "Role in the office", "Platform role"], [(p["name"], p["business_role"], p["platform_role"]) for p in U["people"]]), "",
         "## Entities and portfolios", "",
         table(["Portfolio", "Entity", "Name", "Holdings"], [(p["portfolio_code"], p["legal_entity"], p["portfolio_name"], ", ".join(p["holdings"])) for p in U["portfolios"]]), "",
         "## Managers and funds", "",
         table(["Key", "Fund", "Type", "Asset class", "Manager", "Frequency", "Admin code", "Portfolio", "Names seen on statements"],
               [(f["key"], f["canonical_name"], f["instrument_type"], f["asset_class"], f["manager"], f["statement_frequency"],
                 f["identifiers"].get("administrator", {}).get("administrator_code"), f["portfolio"], "; ".join(f["identifiers"].get("manager_email", {}).get("manager_fund_name", [])))
                for f in U["funds"]]), "",
         "## Liquid book at 30 Sep 2026 (EG-LIQUID, total 41,200,000.00)", "",
         table(["Key", "Security", "Asset class", "Quantity", "Price", "Value"],
               [(r["security"], next(s["canonical_name"] for s in U["securities"] if s["key"] == r["security"]),
                 next(s["asset_class"] for s in U["securities"] if s["key"] == r["security"]) or "(none)", r["quantity"], r["price"], r["value"])
                for r in U["liquid_book_month_end"]["2026-09-30"]["positions"]]), "",
         "Month-end totals: " + ", ".join(f"{k} {v['total']}" for k, v in U["liquid_book_month_end"].items()), "",
         "## FX forwards (OTC, EG-LIQUID)", "",
         table(["Id", "Trade", "Value date", "Sell USD", "Buy SGD", "Rate", "Confirmation rate", "Status"],
               [(f["id"], f["trade_date"], f["value_date"], f["sell_amount"], f["buy_amount"], f["contract_rate"], f["confirmation_rate"], f["confirmation_status"]) for f in U["fx_forwards"]]), "",
         "## Statements (every one, Oct 2025 to Sep 2026)", "",
         table(["Fund", "Period end", "Kind", "Value", "Received", "Due", "Late (bd)", "Status", "Note"],
               [(s["fund"], s["period_end"], s["kind"], s["value"], (s["received_at"] or "")[:10], s["due_date"], s["late_business_days"], s["status"], s["note"] or "") for s in U["statements"]]), "",
         "## Administrator NAV per portfolio per month (investment view known now in brackets)", ""]
    pfs = [p["portfolio_code"] for p in U["portfolios"]]
    months = sorted({r["nav_period_end"] for r in U["administrator_nav_monthly"]})
    nav = {(r["portfolio"], r["nav_period_end"]): r for r in U["administrator_nav_monthly"]}
    L += [table(["Month end"] + pfs, [[mo] + [f"{nav[(p, mo)]['nav_amount']} ({nav[(p, mo)]['investment_view_known_now']})" for p in pfs] for mo in months]), "",
          "## NAV bridge at 30 Sep 2026", "",
          table(["Portfolio", "Administrator NAV", "Investment view", "Revisions", "Timing", "FX", "Unexplained", "Parts"],
                [(b["portfolio"], b["administrator_nav"], b["investment_view"], b["revisions"], b["timing"], b["fx"], b["unexplained"],
                  "; ".join(f"{p['fund']} {p['kind']} {p['amount']}" for p in b["parts"])) for b in U["nav_bridge_30_sep"]]), "",
          "## Cash on 8 Oct 2026 (two views; the daily file has 30 days)", "",
          table(["Entity", "Administrator", "Trading export", "Difference", "Over 5,000?"], [(c["legal_entity"], c["administrator"], c["trading_export"], c["difference"], c["over_tolerance"]) for c in U["cash_8_oct"]]), "",
          f"Cash activity: {len(U['cash_activity'])} items (fees, coupons, FX settlements, sweeps) from opening balances at the close of 8 Sep; they sum to the daily balances on each side. "
          "Every item is booked the same day on both sides except these:", "",
          table(["Reference", "Entity", "Amount", "Administrator", "Trading export", "Bank", "What"],
                [(i["reference"], i["entity"], i["amount"], i["administrator_date"] or "never", i["trading_export_date"] or "never", i["bank_date"] or "never", i["description"])
                 for i in U["cash_activity"] if not (i["administrator_date"] == i["trading_export_date"] == i["bank_date"])]), "",
          "## Commitments", "",
          table(["Fund", "Entity", "Commitment", "Called to date", "Uncalled", "Noticed / due later"],
                [(c["fund"], c["legal_entity"], c["commitment_amount"], c["called_to_date"], c["uncalled"], c["calls_noticed_or_due_after_as_of"]) for c in U["commitments"]]), "",
          "## Calls and distributions (Aug 2025 to Dec 2026)", "",
          table(["Id", "Fund", "Kind", "Amount", "Notice", "Due", "Status", "Days from 9 Oct"],
                [(x["id"], x["fund"], x["notice_kind"], x["amount"], x["notice_date"], x["due_date"], x["confirmation_status"], x["days_from_as_of"]) for x in U["cash_movements"]]), "",
          "## Liquidity at 9 Oct", "",
          table(["Entity", "Available (admin 8 Oct)", "Calls 30d", "Calls 60d", "Calls 90d", "Distributions 60d", "After confirmed calls", "After all noticed calls", "Unconfirmed"],
                [(l["legal_entity"], l["available_cash_administrator_8_oct"], l["calls_due"]["30"], l["calls_due"]["60"], l["calls_due"]["90"], l["distributions_expected"]["60"],
                  l["after_confirmed_calls_30d"], l["after_all_noticed_calls_30d"], ", ".join(l["unconfirmed_calls"])) for l in U["liquidity_9_oct"]]), "",
          "## Trades 1 to 8 Oct 2026 (trading export vs administrator)", "",
          table(["Id", "Date", "Side", "Security", "Quantity", "Price", "Amount", "Admin quantity", "Result", "Planted"],
                [(t["id"], t["trade_date"], t["side"], t["security"], t["quantity"], t["price"], t["amount"], t["administrator_quantity"] or "missing", t["result"], t["planted"] or "") for t in U["trades_oct"]]), "",
          "## Limits at 30 Sep 2026", "",
          table(["Rule", "Portfolio", "Dimension", "Bucket", "Min", "Max", "Exposure %", "Result", "Cause"],
                [(l["rule"], l["portfolio"], l["dimension"], l["bucket"], l["min_pct"], l["max_pct"], l["exposure_pct"], l["result"], l["cause"] or "") for l in U["limits_check_30_sep"]]), "",
          "## Benchmark", "",
          f"`{U['benchmark']['benchmark_code']}` {U['benchmark']['benchmark_name']}, v1 approved (equity 0.42, bonds 0.28, private sleeve 0.30 = equity + 300 bps), v2 in_progress (0.36/0.24/0.40). "
          "Liquid sleeve alone: 60% equity, 40% bonds.", "",
          table(["September 2026", "%"], list(U["benchmark"]["september_2026"].items())[:-1]), "",
          "Index month-end anchors:", "",
          table(["Month end", "Global Equity Index (synthetic)", "Global Bond Index (synthetic)", "USD/SGD WMR 4pm"],
                [(k, U["index_levels"]["month_end_anchors"]["IDX:GLEQ:SYN"][k], U["index_levels"]["month_end_anchors"]["IDX:GLBD:SYN"][k], U["fx_fixings"]["month_end"][k])
                 for k in U["index_levels"]["month_end_anchors"]["IDX:GLEQ:SYN"]]), "",
          "## Signed rules", "",
          table(["Code", "Type", "Owner", "Parameters", "Words"], [(r["rule_code"], r["rule_type"], r["owner"], json.dumps(r["parameters"]), r["definition_text"]) for r in U["rules"]]), "",
          "## Documents (library)", "",
          table(["Id", "Manager", "Type", "Date", "Title", "Key facts"], [(d["id"], d["manager"] or "", d["document_type"], d["document_date"], d["title"], " ".join(d["key_facts"])) for d in U["documents"]]), "",
          "## Month-end process (signed intent, UC9)", "",
          table(["#", "Step", "Who", "System", "Manual", "Control", "Exception"], [(s["n"], s["name"], s["who"], s["system"], s["manual"], s["control"], s["exception"]) for s in U["process"]["steps"]]), "",
          "## Planted facts (the answer key)", "",
          table(["Id", "UC", "Fact", "Expected", "Where", "Role"], [(p["id"], p["use_case"], p["fact"], p["expected"], p["where"], p["role"]) for p in U["planted"]]), ""]
    return "\n".join(L)


def main() -> None:
    U = build()
    (HERE / "10uc_universe.json").write_text(json.dumps(U, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (HERE / "10UC-UNIVERSE.md").write_text(markdown(U), encoding="utf-8")
    print(f"planted {len(U['planted'])}, statements {len(U['statements'])}, valuations {len(U['valuations_monthly'])}, cash rows {len(U['cash_daily'])}")


if __name__ == "__main__":
    main()
