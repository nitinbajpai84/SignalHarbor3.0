"""Synthetic structured sources for the demo family office (plan card D3).

Writes data/<company>/landing/<source>/ (CSV, one XLSX, a _manifest.json per folder),
a restorable copy at local/samples/<company>/ and the answer key
docs/product/FO-DEMO-ANSWER-KEY.md. Deterministic: same arguments, same files.
Run: python tools/make_samples_fo_demo.py [company_id] [company_name]
(the name defaults to the id without its numeric suffix, title-cased).
"""
import csv
import json
import random
import re
import shutil
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
START, END = date(2025, 9, 1), date(2026, 9, 30)
R = random.Random(20250901)
FOLDERS = ["custodian_positions", "custodian_transactions", "custodian_cash", "custodian_income", "custodian_fees",
           "custodian_tax_lots", "custodian_corporate_actions", "bank_balances", "bank_transfers", "market_prices",
           "fx_rates", "security_master", "benchmark_levels", "benchmark_blend", "target_allocation",
           "manual_adjustments", "private_portal", "entities"]
SYSTEMS = {"custodian": "Northgate Custody file service", "bank": "Harbour Bank and Lion Gate Bank statement export",
           "market_prices": "Pricing feed", "fx_rates": "FX rate feed", "security_master": "Security master (operations)",
           "benchmark_levels": "Index provider file", "benchmark_blend": "Investment policy register",
           "target_allocation": "Investment policy register", "manual_adjustments": "Manual adjustment workbook",
           "private_portal": "Private fund portals (manual download)", "entities": "Entity register"}
MANAGER2 = "Compass Investors (mandate)"
# name, class, sub_class, sector, geography, ccy, manager, issuer, account, opening value SGD m, price, coupon %
SECS = [
    ("Pacific Lion Bank", "equity", "listed_equity", "financials", "Singapore", "SGD", "in-house", "Pacific Lion Bank", "NC-001", 5, 38.5, 0),
    ("Merlion Telecom", "equity", "listed_equity", "communication", "Singapore", "SGD", "in-house", "Merlion Telecom", "NC-001", 4, 3.2, 0),
    ("Straits Property Trust", "equity", "reit", "real_estate", "Singapore", "SGD", "in-house", "Straits Property Trust", "NC-001", 3.5, 2.1, 0),
    ("Kallang Supply Chain", "equity", "listed_equity", "industrials", "Singapore", "SGD", "in-house", "Kallang Supply Chain", "NC-001", 3, 1.85, 0),
    ("Tanjong Energy", "equity", "listed_equity", "energy", "Singapore", "SGD", "in-house", "Tanjong Energy", "NC-001", 3, 6.4, 0),
    ("Orchid Foods", "equity", "listed_equity", "consumer_staples", "Singapore", "SGD", "in-house", "Orchid Foods", "NC-001", 2.5, 4.75, 0),
    ("Redwood Software", "equity", "listed_equity", "technology", "United States", "USD", MANAGER2, "Redwood Software", "NC-002", 7, 312, 0),
    ("Cobalt Semiconductor", "equity", "listed_equity", "technology", "United States", "USD", MANAGER2, "Cobalt Semiconductor", "NC-002", 6, 188, 0),
    ("Prairie Rail", "equity", "listed_equity", "industrials", "United States", "USD", MANAGER2, "Prairie Rail", "NC-002", 4.5, 142, 0),
    ("Bluewater Health", "equity", "listed_equity", "health_care", "United States", "USD", MANAGER2, "Bluewater Health", "NC-002", 5, 96, 0),
    ("Summit Payments", "equity", "listed_equity", "financials", "United States", "USD", MANAGER2, "Summit Payments", "NC-002", 4.5, 61, 0),
    ("Granite Insurance", "equity", "listed_equity", "financials", "United States", "USD", MANAGER2, "Granite Insurance", "NC-002", 4, 83, 0),
    ("Rhein Chemie Werke", "equity", "listed_equity", "materials", "Europe", "EUR", MANAGER2, "Rhein Chemie Werke", "NC-002", 4, 54, 0),
    ("Nordlicht Energie", "equity", "listed_equity", "utilities", "Europe", "EUR", MANAGER2, "Nordlicht Energie", "NC-002", 4, 22.4, 0),
    ("Lyon Luxe Group", "equity", "listed_equity", "consumer_discretionary", "Europe", "EUR", MANAGER2, "Lyon Luxe Group", "NC-002", 5, 615, 0),
    ("Iberia Grid", "equity", "listed_equity", "utilities", "Europe", "EUR", MANAGER2, "Iberia Grid", "NC-002", 3, 12.8, 0),
    ("Kowloon Gas Works", "equity", "listed_equity", "utilities", "Hong Kong", "HKD", "in-house", "Kowloon Gas Works", "NC-003", 4, 7.2, 0),
    ("Lantau Property", "equity", "listed_equity", "real_estate", "Hong Kong", "HKD", "in-house", "Lantau Property", "NC-003", 5, 11.6, 0),
    ("Pearl River Retail", "equity", "listed_equity", "consumer_discretionary", "Hong Kong", "HKD", "in-house", "Pearl River Retail", "NC-003", 5, 23.5, 0),
    ("Victoria Peak Insurance", "equity", "listed_equity", "financials", "Hong Kong", "HKD", "in-house", "Victoria Peak Insurance", "NC-003", 6, 68, 0),
    ("Pacific Lion Bank 3.85% 2031", "fixed_income", "corporate", "financials", "Singapore", "SGD", "in-house", "Pacific Lion Bank", "NC-001", 5, 101.2, 3.85),
    ("Republic of Singapore 2.875% 2030", "fixed_income", "government", "government", "Singapore", "SGD", "in-house", "Republic of Singapore", "NC-001", 9, 99.4, 2.875),
    ("Republic of Singapore 3.375% 2033", "fixed_income", "government", "government", "Singapore", "SGD", "in-house", "Republic of Singapore", "NC-001", 8, 101.8, 3.375),
    ("Island Housing Authority 3.1% 2029", "fixed_income", "agency", "government", "Singapore", "SGD", "in-house", "Island Housing Authority", "NC-001", 5, 100.3, 3.1),
    ("US Treasury 4.25% 2030", "fixed_income", "government", "government", "United States", "USD", MANAGER2, "US Treasury", "NC-002", 6, 100.9, 4.25),
    ("US Treasury 3.875% 2034", "fixed_income", "government", "government", "United States", "USD", MANAGER2, "US Treasury", "NC-002", 5, 97.6, 3.875),
    ("Redwood Software 5.1% 2032", "fixed_income", "corporate", "technology", "United States", "USD", MANAGER2, "Redwood Software", "NC-002", 3, 102.4, 5.1),
    ("Granite Insurance 4.6% 2031", "fixed_income", "corporate", "financials", "United States", "USD", MANAGER2, "Granite Insurance", "NC-002", 3, 99.8, 4.6),
    ("Federal Republic 2.5% 2034", "fixed_income", "government", "government", "Europe", "EUR", MANAGER2, "Federal Republic", "NC-002", 4, 98.1, 2.5),
    ("Nordlicht Energie 3.25% 2030", "fixed_income", "corporate", "utilities", "Europe", "EUR", MANAGER2, "Nordlicht Energie", "NC-002", 3, 100.6, 3.25),
    ("Victoria Peak Insurance 5.0% 2029", "fixed_income", "corporate", "financials", "Hong Kong", "USD", "in-house", "Victoria Peak Insurance", "NC-003", 3, 101.5, 5.0),
    ("Kowloon Gas Works 4.4% 2030", "fixed_income", "corporate", "utilities", "Hong Kong", "USD", "in-house", "Kowloon Gas Works", "NC-003", 3, 100.2, 4.4),
    ("Meridian Asia Equity Fund", "fund", "equity_fund", "diversified", "Asia", "USD", "Meridian Asset Management", "Meridian Asia Equity Fund", "NC-002", 3, 24.6, 0),
    ("Lighthouse Global Income Fund", "fund", "bond_fund", "diversified", "Global", "USD", "Lighthouse Capital", "Lighthouse Global Income Fund", "NC-002", 2.5, 11.2, 0),
    ("Compass US Dividend Fund", "fund", "equity_fund", "diversified", "United States", "USD", "Compass Investors", "Compass US Dividend Fund", "NC-002", 2.5, 48.3, 0),
    ("Anchor Emerging Markets Fund", "fund", "equity_fund", "diversified", "Emerging markets", "USD", "Anchor Partners", "Anchor Emerging Markets Fund", "NC-003", 2, 17.9, 0),
    ("Meridian Singapore Bond Fund", "fund", "bond_fund", "diversified", "Singapore", "SGD", "Meridian Asset Management", "Meridian Singapore Bond Fund", "NC-001", 2.5, 1.32, 0),
    ("Lighthouse Asia REIT Fund", "fund", "reit_fund", "real_estate", "Asia", "SGD", "Lighthouse Capital", "Lighthouse Asia REIT Fund", "NC-001", 2, 0.94, 0),
    ("Compass Europe Equity Fund", "fund", "equity_fund", "diversified", "Europe", "EUR", "Compass Investors", "Compass Europe Equity Fund", "NC-002", 2.5, 156.4, 0),
    ("Anchor Euro Credit Fund", "fund", "bond_fund", "diversified", "Europe", "EUR", "Anchor Partners", "Anchor Euro Credit Fund", "NC-002", 2, 102.7, 0),
    ("Meridian SGD Money Fund", "cash_equivalent", "money_market", "cash", "Singapore", "SGD", "Meridian Asset Management", "Meridian SGD Money Fund", "NC-001", 1, 1.0412, 0),
    ("Lighthouse SGD Liquidity Fund", "cash_equivalent", "money_market", "cash", "Singapore", "SGD", "Lighthouse Capital", "Lighthouse SGD Liquidity Fund", "NC-003", 0.6, 1.1873, 0),
    ("Meridian USD Money Fund", "cash_equivalent", "money_market", "cash", "United States", "USD", "Meridian Asset Management", "Meridian USD Money Fund", "NC-002", 1, 1.0735, 0),
    ("Anchor USD Cash Fund", "cash_equivalent", "money_market", "cash", "United States", "USD", "Anchor Partners", "Anchor USD Cash Fund", "NC-003", 0.7, 10.218, 0),
    ("Compass HKD Money Fund", "cash_equivalent", "money_market", "cash", "Hong Kong", "HKD", "Compass Investors", "Compass HKD Money Fund", "NC-003", 0.7, 1.0094, 0),
]
# fund_id, name, manager, sub_class, ccy, paying account, commitment, called, distributed, NAV at 30 Jun 2025, ownership %
PRIV = [
    ("PF01", "Lighthouse Asia Growth Fund III", "Lighthouse Capital", "private_equity", "USD", "NC-002", 10e6, 6e6, 0.5e6, 6.4e6, 1.2),
    ("PF02", "Wayfarer Venture Partners II", "Wayfarer Partners", "venture", "USD", "NC-002", 5e6, 3e6, 0, 3.1e6, 0.8),
    ("PF03", "Orchard Private Credit Fund", "Orchard Credit", "private_credit", "SGD", "NC-001", 8e6, 5e6, 0.8e6, 4.6e6, 2.5),
    ("PF04", "Alder Real Estate Partners", "Alder Real Estate", "real_estate", "EUR", "NC-002", 4e6, 2.5e6, 0.3e6, 2.4e6, 1.5),
]
OPEN_CASH = {("NC-001", "SGD"): 2.0e6, ("NC-001", "USD"): 0.3e6, ("NC-002", "USD"): 1.5e6, ("NC-002", "EUR"): 0.8e6,
             ("NC-002", "SGD"): 1.2e6, ("NC-003", "HKD"): 3.0e6, ("NC-003", "USD"): 0.5e6, ("NC-003", "SGD"): 0.6e6}
CASH_RATE = {"SGD": 0.015, "USD": 0.03, "EUR": 0.018, "HKD": 0.02}
WHT = {"USD": 0.30, "EUR": 0.15}
TARGET = [("equity", 45, 35, 50), ("fixed_income", 30, 20, 40), ("fund", 10, 5, 15), ("private", 10, 5, 15),
          ("cash_equivalent", 5, 1, 10)]
BLEND = [("STR50", 25), ("CWE", 40), ("AGB", 35)]
INDICES = {"STR50": (3200, 0.0002, 0.009, 0.035), "CWE": (5400, 0.0003, 0.010, 0.018), "AGB": (1050, 0.0001, 0.0025, 0.035)}
BANKS = {"HB-SGD-01": ("E1", "SGD", 2.5e6), "HB-USD-01": ("E1", "USD", 0.6e6), "LG-SGD-01": ("E2", "SGD", 3.0e6),
         "LG-HKD-01": ("E2", "HKD", 4.0e6)}
CONC_LIMIT, ISSUER = 10.0, "Pacific Lion Bank"


def bday(d):
    while d.weekday() >= 5:
        d += timedelta(1)
    return d


def add_bdays(d, n):
    for _ in range(n):
        d = bday(d + timedelta(1))
    return d


def isin(prefix, n):
    body = f"{prefix}{n:09d}"
    digits = "".join(str(int(c, 36)) for c in body)
    s = 0
    for i, ch in enumerate(reversed(digits)):
        k = int(ch) * (2 if i % 2 == 0 else 1)
        s += k - 9 if k > 9 else k
    return body + str((10 - s % 10) % 10)


DAYS = [START + timedelta(i) for i in range((END - START).days + 1)]
TDAYS = [d for d in DAYS if d.weekday() < 5]
MONTHS = sorted({(d.year, d.month) for d in DAYS})
MEND = {ym: max(d for d in TDAYS if (d.year, d.month) == ym) for ym in MONTHS}
MEND_SET = set(MEND.values())
QEND = {MEND[ym] for ym in MONTHS if ym[1] in (3, 6, 9, 12)}
DAILY_POS = {d for d in TDAYS if d >= date(2026, 8, 1)} | MEND_SET | {date(2026, 7, 15)}
FEB_DATE, MAY_DATE, DUP_DATE, MISS_DATE = date(2026, 2, 3), date(2026, 5, 12), date(2025, 12, 12), date(2026, 7, 15)
SPLIT_DATE, RENAME_DATE = date(2026, 4, 15), date(2026, 3, 2)
CASH_BREAK = ("NC-003", "SGD", 7450.00, MEND[(2026, 3)])
MISSING_PX_DAYS = (date(2026, 8, 3), date(2026, 8, 4))
UNKNOWN_ID = "NGC-88213"
STALE_BANK, STALE_LAST = "LG-HKD-01", date(2026, 9, 20)

SEC = {}
for i, s in enumerate(SECS, 1):
    sid = f"SEC{i:03d}"
    pre = "XS" if s[1] == "fixed_income" else "LU" if s[1] == "fund" else {"SGD": "SG", "USD": "US", "EUR": "DE", "HKD": "HK"}[s[5]]
    SEC[sid] = dict(zip(["name", "cls", "sub", "sector", "geo", "ccy", "manager", "issuer", "acct", "val", "p0", "cpn"], s))
    SEC[sid]["isin"] = isin(pre, 470000 + i * 137)
ID = {v["name"]: k for k, v in SEC.items()}
PF = {p[0]: dict(zip(["id", "name", "manager", "sub", "ccy", "acct", "commit", "called", "dist", "nav", "own"], p)) for p in PRIV}
for k, p in enumerate(PF.values()):
    p["isin"] = isin("KY", 990000 + k * 41)
CALLS = [("PF03", date(2025, 10, 20), "call", 1.0e6), ("PF01", date(2025, 11, 14), "call", 0.8e6),
         ("PF04", date(2026, 1, 20), "call", 0.3e6), ("PF02", date(2026, 2, 13), "call", 0.4e6),
         ("PF01", date(2026, 3, 16), "distribution", 0.5e6), ("PF03", date(2026, 4, 20), "call", 0.8e6),
         ("PF01", date(2026, 5, 15), "call", 0.6e6), ("PF03", date(2026, 6, 15), "distribution", 0.35e6),
         ("PF04", date(2026, 7, 20), "call", 0.25e6), ("PF04", date(2026, 9, 15), "distribution", 0.2e6)]
CALLS = [(f, bday(d), k, a) for f, d, k, a in CALLS]
# custodian <-> bank transfers: date, custodian account, bank account, amount (+ into custodian)
XFERS = [(date(2025, 10, 15), "NC-001", "HB-SGD-01", -400000), (date(2026, 1, 15), "NC-002", "HB-USD-01", 300000),
         (date(2026, 4, 15), "NC-001", "HB-SGD-01", -600000), (date(2026, 6, 10), "NC-003", "LG-SGD-01", 1000000),
         (date(2026, 8, 14), "NC-001", "HB-SGD-01", -350000)]
XFERS = [(bday(d), a, b, x) for d, a, b, x in XFERS]


def simulate():
    price = {s: v["p0"] for s, v in SEC.items()}
    fx = {"SGD": 1.0, "USD": 1.342, "EUR": 1.471, "HKD": 1.342 / 7.8}
    lvl = {k: v[0] for k, v in INDICES.items()}
    tri = {k: 10000.0 for k in INDICES}
    px, fxh, bench = {}, {}, {}
    hold, lots, cash = defaultdict(int), defaultdict(list), defaultdict(float)
    txns, income, fees, cas = [], [], [], []
    snaps, lot_snaps, weights, acct_val = {}, {}, {}, {}
    traded = defaultdict(float)
    nav_hist = {f: [(date(2025, 6, 30), p["nav"])] for f, p in PF.items()}   # reported NAVs
    called = {f: p["called"] for f, p in PF.items()}
    dist = {f: p["dist"] for f, p in PF.items()}
    portal, flows_q = {}, defaultdict(float)
    ref = {"dup": None, "miss": None}
    seq = [0]

    def txn(d, acct, sid, typ, qty, prc, gross, net, ccy, settle=None, reference=None):
        seq[0] += 1
        r = reference or f"NGC{seq[0]:06d}"
        txns.append(dict(trade_date=d, settle_date=settle or d, account_id=acct, security_id=sid, type=typ,
                         quantity=qty, price=prc, gross_amount=round(gross, 2), net_amount=round(net, 2), currency=ccy,
                         reference=r))
        cash[(acct, ccy)] += round(net, 2)
        return r

    def trade(d, acct, sid, side, qty):
        if qty <= 0:
            return None
        p, ccy = px[d][sid], SEC[sid]["ccy"]
        gross = round(qty * p, 2)
        traded[(acct, d.year, d.month)] += gross * fxh[d][ccy]
        if side == "buy":
            hold[(acct, sid)] += qty
            lots[(acct, sid)].append([f"L{seq[0] + 1:06d}", d, qty, gross, gross * fxh[d][ccy]])
        else:
            hold[(acct, sid)] -= qty
            left = qty
            for lot in lots[(acct, sid)]:
                take = min(left, lot[2])
                if take:
                    frac = take / lot[2]
                    lot[3] -= lot[3] * frac
                    lot[4] -= lot[4] * frac
                    lot[2] -= take
                    left -= take
            lots[(acct, sid)] = [lot for lot in lots[(acct, sid)] if lot[2] > 0]
        return txn(d, acct, sid, side, qty, p, gross, -gross if side == "buy" else gross, ccy, add_bdays(d, 2))

    def sell_sgd(d, acct, sid, sgd):
        q = min(hold[(acct, sid)], int(sgd / (px[d][sid] * fxh[d][SEC[sid]["ccy"]])))
        trade(d, acct, sid, "sell", q)
        return q * px[d][sid]

    def buy_local(d, acct, sid, amt):
        return trade(d, acct, sid, "buy", int(amt / px[d][sid]))

    def priv_value(d):
        out = {}
        for f, p in PF.items():
            nd, nav = max((x for x in nav_hist[f] if x[0] <= d), key=lambda x: x[0])
            adj = sum(a if k == "call" else -a for g, cd, k, a in CALLS if g == f and nd < cd <= d)
            out[f] = (nav + adj) * fxh[d][p["ccy"]]
        return out

    def valuation(d):
        by_cls, by_acct, iss = defaultdict(float), defaultdict(float), 0.0
        for (acct, sid), q in hold.items():
            if q:
                v = round(round(q * px[d][sid], 2) * fxh[d][SEC[sid]["ccy"]], 2)
                by_cls[SEC[sid]["cls"]] += v
                by_acct[acct] += v
                iss += v if SEC[sid]["issuer"] == ISSUER else 0
        for (acct, ccy), b in cash.items():
            by_cls["cash_equivalent"] += b * fxh[d][ccy]
            by_acct[acct] += b * fxh[d][ccy]
        by_cls["private"] = sum(priv_value(d).values())
        return by_cls, by_acct, iss

    divs = []  # sid, ex date, pay date, amount per share
    for sid, s in SEC.items():
        if s["cls"] == "equity" and s["name"] != "Cobalt Semiconductor":
            m0 = int(sid[3:]) % 6 + 1
            for y, m in MONTHS:
                if m in (m0, m0 + 6):
                    ex, pay = bday(date(y, m, 10)), bday(date(y, m, 24))
                    if pay <= END:
                        divs.append((sid, ex, pay, round(s["p0"] * 0.02, 4)))
    entitled = {}
    special = {FEB_DATE, MAY_DATE, DUP_DATE, MISS_DATE}

    for n, d in enumerate(TDAYS):
        if n:
            for sid, s in SEC.items():
                if s["cls"] == "cash_equivalent":
                    price[sid] *= 1 + CASH_RATE[s["ccy"]] / 252
                else:
                    mu, sg = {"equity": (0.00025, 0.012), "fixed_income": (0.00005, 0.002), "fund": (0.0002, 0.008)}[s["cls"]]
                    price[sid] *= 1 + R.gauss(mu, sg)
            fx["USD"] *= 1 + R.gauss(0, 0.003)
            fx["EUR"] *= 1 + R.gauss(0, 0.004)
            fx["HKD"] = fx["USD"] / 7.8 * (1 + R.gauss(0, 0.0005))
            for k, (_, mu, sg, yld) in INDICES.items():
                r = R.gauss(mu, sg)
                lvl[k] *= 1 + r
                tri[k] *= 1 + r + yld / 252
        if d == SPLIT_DATE:
            price[ID["Cobalt Semiconductor"]] /= 2
        px[d] = {s: round(p, 4) for s, p in price.items()}
        fxh[d] = {c: round(r, 6) for c, r in fx.items()}
        bench[d] = {k: (round(lvl[k], 2), round(tri[k], 2)) for k in INDICES}

        if d == START:  # onboarding: in-kind transfer of every holding and the opening cash
            for sid, s in SEC.items():
                q = int(s["val"] * 1e6 / (s["p0"] * fxh[d][s["ccy"]]))
                hold[(s["acct"], sid)] = q
                cl = q * s["p0"] * R.uniform(0.78, 1.02)
                od = d - timedelta(R.randint(200, 1500))
                lots[(s["acct"], sid)].append([f"L{seq[0] + 1:06d}", od, q, cl, cl * fxh[d][s["ccy"]] * R.uniform(0.97, 1.03)])
                txn(d, s["acct"], sid, "transfer", q, "", 0, 0, s["ccy"])
            for (acct, ccy), amt in OPEN_CASH.items():
                txn(d, acct, "", "transfer", "", "", amt, amt, ccy)
        if d == SPLIT_DATE:
            sid = ID["Cobalt Semiconductor"]
            for (acct, s2), q in list(hold.items()):
                if s2 == sid and q:
                    txn(d, acct, sid, "transfer", q, "", 0, 0, "USD", reference="CA-0001")
                    hold[(acct, sid)] = 2 * q
                    for lot in lots[(acct, sid)]:
                        lot[2] *= 2
        for sid, ex, pay, dps in divs:
            if d == ex:
                entitled[(sid, ex)] = hold[(SEC[sid]["acct"], sid)]
            if d == pay and entitled.get((sid, ex)):
                s, q = SEC[sid], entitled[(sid, ex)]
                g = round(q * dps, 2)
                w = round(g * WHT.get(s["ccy"], 0), 2)
                r = txn(d, s["acct"], sid, "dividend", q, dps, g, g - w, s["ccy"])
                income.append([d, s["acct"], sid, "dividend", g, w, round(g - w, 2), s["ccy"], r])
        for sid, s in SEC.items():
            m0 = int(sid[3:]) % 6 + 1
            if s["cls"] == "fixed_income" and d.month in (m0, m0 + 6) and d == bday(date(d.year, d.month, 15)):
                q = hold[(s["acct"], sid)]
                if q:
                    g = round(q * s["cpn"] / 2, 2)
                    r = txn(d, s["acct"], sid, "interest", q, round(s["cpn"] / 2, 4), g, g, s["ccy"])
                    income.append([d, s["acct"], sid, "coupon", g, 0, g, s["ccy"], r])
        for xd, acct, bank, amt in XFERS:
            if d == xd:
                txn(d, acct, "", "transfer", "", "", abs(amt), amt, BANKS[bank][1])
        for f, cd, k, amt in CALLS:
            if d == cd:
                p = PF[f]
                txn(d, p["acct"], f, k, "", "", amt, -amt if k == "call" else amt, p["ccy"])
                (called if k == "call" else dist)[f] += amt
        # fee invoices on the first trading day of each month, for the previous month
        prev = [ym for ym in MONTHS if MEND[ym] < d]
        if prev and d == min(x for x in TDAYS if (x.year, x.month) == (d.year, d.month)):
            py, pm = prev[-1]
            pfrom, pto = date(py, pm, 1), date(py, pm, 1).replace(day=28) + timedelta(4)
            pto = pto - timedelta(pto.day)
            k = 0
            for acct in ("NC-001", "NC-002", "NC-003"):
                av = acct_val[MEND[(py, pm)]][acct]
                lines = [("custody", av * 0.0004 / 12, pfrom, pto),
                         ("transaction", traded[(acct, py, pm)] * 0.0003, pfrom, pto)]
                if acct == "NC-002" and d.month in (1, 4, 7) and d > date(2025, 12, 1):
                    lines.append(("management", av * 0.006 / 4, date(py, pm - 2, 1), pto))
                if acct == "NC-002" and (d.year, d.month) == (2026, 1):
                    lines.append(("performance", 120000.0, START, pto))
                for ft, amt, a, b in lines:
                    if amt >= 0.01:
                        k += 1
                        inv = f"INV-{d:%Y%m}-{k:02d}"
                        fees.append([d, inv, acct, ft, round(amt, 2), "SGD", a, b])
                        txn(d, acct, "", "fee", "", "", amt, -amt, "SGD", reference=inv)
        # trading
        if d == FEB_DATE:  # concentration: switch government bonds into the Pacific Lion Bank bond
            proceeds = sum(sell_sgd(d, "NC-001", ID[n], v) for n, v in (("Republic of Singapore 2.875% 2030", 6e6),
                           ("Republic of Singapore 3.375% 2033", 5e6), ("Island Housing Authority 3.1% 2029", 3e6)))
            buy_local(d, "NC-001", ID["Pacific Lion Bank 3.85% 2031"], proceeds)
        elif d == MAY_DATE:  # drift: rotate bonds, funds and money funds into equities
            p1 = sum(sell_sgd(d, "NC-001", ID[n], v) for n, v in (("Republic of Singapore 2.875% 2030", 9e9),
                     ("Lighthouse Asia REIT Fund", 9e9), ("Meridian SGD Money Fund", 0.5e6)))
            for n in ("Merlion Telecom", "Tanjong Energy", "Orchid Foods"):
                buy_local(d, "NC-001", ID[n], p1 / 3)
            p2 = sum(sell_sgd(d, "NC-002", ID[n], v) for n, v in (("US Treasury 4.25% 2030", 5e6),
                     ("US Treasury 3.875% 2034", 2e6), ("Lighthouse Global Income Fund", 9e9),
                     ("Compass US Dividend Fund", 9e9), ("Meridian USD Money Fund", 0.5e6)))
            for n in ("Redwood Software", "Bluewater Health", "Summit Payments"):
                buy_local(d, "NC-002", ID[n], p2 / 3)
        elif d == DUP_DATE:
            proceeds = sell_sgd(d, "NC-001", ID["Tanjong Energy"], 0.6e6)
            ref["dup"] = buy_local(d, "NC-001", ID["Orchid Foods"], proceeds)
        elif d == MISS_DATE:
            ref["miss"] = trade(d, "NC-002", ID["Bluewater Health"], "buy", 2500)
        elif 3 <= d.day <= 18 and R.random() < 0.15 and d not in special and abs((d - SPLIT_DATE).days) > 3:
            acct = R.choice(["NC-001", "NC-002", "NC-003"])
            held = [s for (a, s), q in hold.items() if a == acct and q and SEC[s]["cls"] != "cash_equivalent"
                    and SEC[s]["issuer"] != ISSUER]
            sid = R.choice(held)
            pair = [s for s, v in SEC.items() if v["acct"] == acct and v["cls"] == SEC[sid]["cls"]
                    and v["ccy"] == SEC[sid]["ccy"] and s != sid and v["issuer"] != ISSUER]
            if pair:
                q = max(1, int(hold[(acct, sid)] * R.uniform(0.1, 0.25)))
                trade(d, acct, sid, "sell", q)
                buy_local(d, acct, R.choice(pair), q * px[d][sid])
        if d in MEND_SET:
            for (acct, ccy), b in list(cash.items()):
                if b > 0:
                    g = round(b * CASH_RATE[ccy] / 12, 2)
                    r = txn(d, acct, "", "interest", "", "", g, g, ccy)
                    income.append([d, acct, "", "interest", g, 0, g, ccy, r])
        if d in QEND and d.month in (3, 6, 9, 12) and date(d.year, d.month, 1) <= d:
            qd = date(d.year, d.month, 30 if d.month in (6, 9) else 31)
            if qd < END:
                for f in PF:
                    last = nav_hist[f][-1]
                    if f == "PF02" and qd > date(2025, 12, 31):
                        continue  # manager has not reported since 31 Dec 2025
                    flow = sum(a if k == "call" else -a for g, cd, k, a in CALLS if g == f and last[0] < cd <= qd)
                    nav_hist[f].append((qd, round(last[1] * (1 + R.uniform(0.005, 0.035)) + flow, 2)))
                portal[qd] = {f: (called[f], dist[f], nav_hist[f][-1]) for f in PF}
        assert all(b >= 0 for b in cash.values()), (d, dict(cash))
        by_cls, by_acct, iss = valuation(d)
        total = sum(by_cls.values())
        weights[d] = ({c: 100 * v / total for c, v in by_cls.items()}, 100 * iss / total, total)
        if d in MEND_SET:
            acct_val[d] = dict(by_acct)
        if d in DAILY_POS:
            snaps[d] = {k: (q, sum(lot[4] for lot in lots[k])) for k, q in hold.items() if q}
        if d in QEND:
            lot_snaps[d] = {k: [list(lot) for lot in v] for k, v in lots.items() if v}
    for sid, ex, pay, dps in divs:
        cas.append([ex, sid, "dividend", dps, f"pay date {pay}"])
    cas.append([SPLIT_DATE, ID["Cobalt Semiconductor"], "split", "2:1", "two for one; bonus shares booked as transfer CA-0001"])
    cas.append([RENAME_DATE, ID["Kallang Supply Chain"], "name_change", "", "formerly Kallang Logistics"])
    return locals()


def main():
    cid = sys.argv[1] if len(sys.argv) > 1 else "ardmore-1"
    name = sys.argv[2] if len(sys.argv) > 2 else " ".join(w.capitalize() for w in re.sub(r"-\d+$", "", cid).split("-"))
    land, copy = ROOT / "data" / cid / "landing", ROOT / "local" / "samples" / cid
    m = simulate()
    px, fxh, bench, txns, snaps = m["px"], m["fxh"], m["bench"], m["txns"], m["snaps"]
    manifests = defaultdict(list)
    for f in FOLDERS:
        shutil.rmtree(land / f, ignore_errors=True)

    def write(folder, fname, header, rows, eff, lag_days=1, hour="06:30"):
        p = land / folder / fname
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(rows)
        manifests[folder].append({"name": fname, "effective_date": str(eff),
                                  "received_at": f"{bday(eff + timedelta(lag_days))}T{hour}:00+08:00", "version": 1})

    ym_of = lambda d: f"{d:%Y-%m}"  # noqa: E731
    visible = [t for t in txns if t["reference"] != m["ref"]["miss"]]
    dup = next(t for t in txns if t["reference"] == m["ref"]["dup"])
    # custodian positions
    for d, snap in sorted(snaps.items()):
        rows = []
        for (acct, sid), (q, cb) in sorted(snap.items()):
            s = SEC[sid]
            mvl = round(q * px[d][sid], 2)
            out_id = UNKNOWN_ID if (d == MEND[(2026, 6)] and sid == ID["Granite Insurance"]) else sid
            rows.append([d, acct, out_id, s["isin"], q, px[d][sid], s["ccy"], mvl, round(mvl * fxh[d][s["ccy"]], 2), round(cb, 2)])
        write("custodian_positions", f"custodian_positions_{d}.csv", ["as_of", "account_id", "security_id", "isin", "quantity",
              "price_local", "currency", "market_value_local", "market_value_base", "cost_basis_base"], rows, d)
    cols = ["trade_date", "settle_date", "account_id", "security_id", "type", "quantity", "price", "gross_amount",
            "net_amount", "currency", "reference"]
    for y, mo in MONTHS:
        rows = [[t[c] for c in cols] for t in visible if (t["trade_date"].year, t["trade_date"].month) == (y, mo)]
        if (y, mo) == (2025, 12):
            i = next(k for k, r in enumerate(rows) if r[-1] == dup["reference"])
            rows.insert(i + 1, list(rows[i]))
        write("custodian_transactions", f"custodian_transactions_{y}-{mo:02d}.csv", cols, rows, MEND[(y, mo)])
    # custodian cash: what the custodian holds (includes the trade missing from the file); settle-date balances
    for ym in MONTHS:
        d, rows = MEND[ym], []
        for acct, ccy in sorted({(t["account_id"], t["currency"]) for t in txns if t["security_id"] == "" or t["type"] in ("buy", "sell", "dividend", "interest", "call", "distribution")}):
            mine = [t for t in txns if t["account_id"] == acct and t["currency"] == ccy and t["trade_date"] <= d]
            bal = round(sum(t["net_amount"] for t in mine if t["settle_date"] <= d), 2)
            avail = round(bal + sum(t["net_amount"] for t in mine if t["settle_date"] > d), 2)
            if (acct, ccy, d) == (CASH_BREAK[0], CASH_BREAK[1], CASH_BREAK[3]):
                bal, avail = round(bal + CASH_BREAK[2], 2), round(avail + CASH_BREAK[2], 2)
            rows.append([d, acct, ccy, bal, avail])
        write("custodian_cash", f"custodian_cash_{ym[0]}-{ym[1]:02d}.csv", ["as_of", "account_id", "currency", "balance", "available"], rows, d)
    for ym in MONTHS:
        rows = [r for r in m["income"] if (r[0].year, r[0].month) == ym]
        write("custodian_income", f"custodian_income_{ym[0]}-{ym[1]:02d}.csv", ["pay_date", "account_id", "security_id", "kind",
              "gross", "withholding", "net", "currency", "reference"], rows, MEND[ym])
        rows = [r for r in m["fees"] if (r[0].year, r[0].month) == ym]
        if rows:
            write("custodian_fees", f"custodian_fees_{ym[0]}-{ym[1]:02d}.csv", ["invoice_date", "invoice_id", "account_id",
                  "fee_type", "amount", "currency", "period_from", "period_to"], rows, rows[0][0])
    for d, ls in sorted(m["lot_snaps"].items()):
        rows = [[d, a, s, lot[0], lot[1], lot[2], round(lot[4], 2), round(lot[3], 2), SEC[s]["ccy"]]
                for (a, s), v in sorted(ls.items()) for lot in v]
        write("custodian_tax_lots", f"custodian_tax_lots_{d}.csv", ["as_of", "account_id", "security_id", "lot_id",
              "open_date", "quantity", "cost_base", "cost_local", "currency"], rows, d)
    write("custodian_corporate_actions", f"custodian_corporate_actions_{END}.csv", ["ex_date", "security_id", "action",
          "ratio_or_amount", "note"], sorted(m["cas"], key=lambda r: (r[0], r[1])), END)
    # bank
    bank_tx = []
    for y, mo in MONTHS:
        for d, acct, cp, amt, memo in [(date(y, mo, 5), "HB-SGD-01", "Family office expenses", -22500, "monthly office costs"),
                                       (date(y, mo, 25), "HB-SGD-01", "Staff payroll", -48000, "household payroll"),
                                       (date(y, mo, 1), "LG-SGD-01", "Office landlord", -18500, "office rent"),
                                       (date(y, mo, 20), "LG-SGD-01", "Audit and tax fees", -9800, "professional fees"),
                                       (date(y, mo, 3), "LG-HKD-01", "Kowloon tenant", 68000, "rental income"),
                                       (date(y, mo, 10), "LG-HKD-01", "Property manager", -25000, "property management")]:
            bank_tx.append([bday(d), acct, cp, amt, memo])
        if mo in (9, 1):
            bank_tx.append([bday(date(y, mo, 8)), "HB-USD-01", "International school", -32000, "school fees"])
    for xd, acct, bank, amt in XFERS:
        bank_tx.append([xd, bank, f"Northgate Custody {acct}", -amt, "transfer with custodian account"])
    bal = {b: v[2] for b, v in BANKS.items()}
    bank_daily = []
    for d in DAYS:
        for b in BANKS:
            bal[b] += sum(r[3] for r in bank_tx if r[0] == d and r[1] == b)
        if d == MEND[(d.year, d.month)]:
            for b, (_, ccy, _) in BANKS.items():
                rate = {"SGD": 0.005, "USD": 0.01, "HKD": 0.008}[ccy]
                g = round(bal[b] * rate / 12, 2)
                bank_tx.append([d, b, b[:2] == "HB" and "Harbour Bank" or "Lion Gate Bank", g, "interest"])
                bal[b] += g
        for b, (ent, ccy, _) in BANKS.items():
            assert bal[b] > 0, (b, d)
            if not (b == STALE_BANK and d > STALE_LAST):
                bank_daily.append([d, b, ent, ccy, round(bal[b], 2)])
    for ym in MONTHS:
        last = date(ym[0], ym[1], 28) + timedelta(4)
        last -= timedelta(last.day)
        write("bank_balances", f"bank_balances_{ym[0]}-{ym[1]:02d}.csv", ["as_of", "bank_account_id", "entity_id", "currency",
              "balance"], [r for r in bank_daily if (r[0].year, r[0].month) == ym], last)
        rows = sorted([[r[0], r[1], "in" if r[3] > 0 else "out", r[2], round(abs(r[3]), 2), BANKS[r[1]][1], r[4]]
                       for r in bank_tx if (r[0].year, r[0].month) == ym])
        write("bank_transfers", f"bank_transfers_{ym[0]}-{ym[1]:02d}.csv", ["value_date", "bank_account_id", "direction",
              "counterparty", "amount", "currency", "memo"], rows, last)
    # market data
    gap = ID["Lyon Luxe Group"]
    src = {"equity": "EXCH", "fixed_income": "EVAL", "fund": "NAV", "cash_equivalent": "NAV"}
    for ym in MONTHS:
        ds = [d for d in TDAYS if (d.year, d.month) == ym]
        write("market_prices", f"market_prices_{ym[0]}-{ym[1]:02d}.csv", ["price_date", "security_id", "isin", "close_local",
              "currency", "source_code"], [[d, s, SEC[s]["isin"], px[d][s], SEC[s]["ccy"], src[SEC[s]["cls"]]] for d in ds
              for s in SEC if not (s == gap and d in MISSING_PX_DAYS)], ds[-1])
        write("fx_rates", f"fx_rates_{ym[0]}-{ym[1]:02d}.csv", ["rate_date", "base_currency", "quote_currency", "rate"],
              [[d, c, "SGD", fxh[d][c]] for d in ds for c in ("USD", "EUR", "HKD")], ds[-1])
        write("benchmark_levels", f"benchmark_levels_{ym[0]}-{ym[1]:02d}.csv", ["level_date", "index_code", "level",
              "total_return_index"], [[d, k, *bench[d][k]] for d in ds for k in INDICES], ds[-1])
    master = [[s, v["isin"], v["name"], v["cls"], v["sub"], v["sector"], v["geo"], v["ccy"], v["manager"], v["issuer"], "yes"]
              for s, v in SEC.items()]
    master += [[f, p["isin"], p["name"], "private", p["sub"], "diversified", "Asia" if p["ccy"] != "EUR" else "Europe",
                p["ccy"], p["manager"], p["name"], "no"] for f, p in PF.items()]
    write("security_master", f"security_master_{END}.csv", ["security_id", "isin", "name", "asset_class", "sub_class",
          "sector", "geography", "currency", "manager", "issuer", "listed"], master, END)
    write("benchmark_blend", f"benchmark_blend_{START}.csv", ["portfolio_id", "index_code", "weight", "effective_from"],
          [["PF-MAIN", k, w, START] for k, w in BLEND], START, 0)
    write("target_allocation", f"target_allocation_{START}.csv", ["portfolio_id", "asset_class", "target_weight",
          "min_weight", "max_weight", "effective_from"], [["PF-MAIN", c, t, lo, hi, START] for c, t, lo, hi in TARGET], START, 0)
    # private portal (quarterly, downloaded about 45 days after quarter-end)
    for qd, rows in sorted(m["portal"].items()):
        write("private_portal", f"private_portal_{qd}.csv", ["fund_id", "name", "commitment", "called_to_date",
              "distributed_to_date", "nav", "nav_date", "currency", "ownership_pct"],
              [[f, PF[f]["name"], PF[f]["commit"], c, dd, nav[1], nav[0], PF[f]["ccy"], PF[f]["own"]] for f, (c, dd, nav) in rows.items()],
              qd, 45, "10:00")
    write("entities", f"entities_{END}.csv", ["entity_id", "name", "kind", "beneficial_owners", "custodian_accounts", "bank_accounts"],
          [["E1", f"{name} Family Trust", "trust", "Meredith Shaw; Katie Kingsley", "NC-001;NC-002", "HB-SGD-01;HB-USD-01"],
           ["E2", f"{name} Holdings Pte Ltd", "holding", "E1 (100%)", "NC-003", "LG-SGD-01;LG-HKD-01"]], END)
    # manual adjustments workbook
    gd = MISSING_PX_DAYS[0]
    adj = [["ADJ-001", gd, "NC-002", gap, "price_local", "", px[gd][gap], "MISSING_PRICE", "Daniel Kerr"],
           ["ADJ-002", MEND[(2026, 6)], "NC-002", UNKNOWN_ID, "security_id", UNKNOWN_ID, ID["Granite Insurance"], "ID_MAPPING", "Grace Ward"],
           ["ADJ-003", date(2026, 6, 30), "NC-002", "PF02", "nav", m["nav_hist"]["PF02"][-1][1], "", "STALE_VALUATION", "Daniel Kerr"],
           ["ADJ-004", RENAME_DATE, "", ID["Kallang Supply Chain"], "name", "Kallang Logistics", "Kallang Supply Chain", "CORPORATE_ACTION", "Grace Ward"],
           ["ADJ-005", DUP_DATE, "NC-001", ID["Orchid Foods"], "transaction", f"{dup['reference']} x2", f"{dup['reference']} x1", "DUPLICATE", "Grace Ward"],
           ["ADJ-006", date(2026, 1, 5), "", ID["Lighthouse Asia REIT Fund"], "sub_class", "equity_fund", "reit_fund", "RECLASSIFICATION", "Daniel Kerr"]]
    appr = [["ADJ-001", "", "", "pending"], ["ADJ-002", "Meredith Shaw", "2026-07-03T10:15:00+08:00", "approved"],
            ["ADJ-003", "Meredith Shaw", "2026-08-20T16:40:00+08:00", "rejected"],
            ["ADJ-004", "Meredith Shaw", "2026-03-03T09:05:00+08:00", "approved"],
            ["ADJ-005", "Aaron Lyle", "2025-12-16T11:30:00+08:00", "approved"],
            ["ADJ-006", "Meredith Shaw", "2026-01-06T14:00:00+08:00", "approved"]]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "adjustments"
    ws.append(["adjustment_id", "as_of", "account_id", "security_id", "field", "old_value", "new_value", "reason_code", "requested_by"])
    for r in adj:
        ws.append([str(x) if isinstance(x, date) else x for x in r])
    ws = wb.create_sheet("approvals")
    ws.append(["adjustment_id", "approved_by", "approved_at", "status"])
    for r in appr:
        ws.append(r)
    p = land / "manual_adjustments" / f"manual_adjustments_{END}.xlsx"
    p.parent.mkdir(parents=True, exist_ok=True)
    wb.properties.created = wb.properties.modified = __import__("datetime").datetime(2026, 9, 30)
    wb.save(p)
    manifests["manual_adjustments"].append({"name": p.name, "effective_date": str(END), "received_at": "2026-10-01T09:00:00+08:00", "version": 1})
    for f in FOLDERS:
        key = "custodian" if f.startswith("custodian") else "bank" if f.startswith("bank") else f
        (land / f / "_manifest.json").write_text(json.dumps({"source_system": SYSTEMS[key], "files": manifests[f]}, indent=2), encoding="utf-8")
    shutil.rmtree(copy, ignore_errors=True)
    shutil.copytree(land, copy, ignore=lambda d, names: [n for n in names if Path(d) == land and n not in FOLDERS])
    write_key(m, visible, dup, gap)
    print(f"ok {sum(len(v) for v in manifests.values())} files in {len(FOLDERS)} folders -> data/{cid}/landing and local/samples/{cid}")


def twr_q2(m, visible):
    """Monthly Modified Dietz on written month-end positions plus ledger cash, chained over April to June 2026."""
    px_rows = {}
    for d in (MEND[(2026, 3)], MEND[(2026, 4)], MEND[(2026, 5)], MEND[(2026, 6)]):
        pos = sum(round(round(q * m["px"][d][s], 2) * m["fxh"][d][SEC[s]["ccy"]], 2) for (a, s), (q, cb) in m["snaps"][d].items())
        cash = defaultdict(float)
        for t in visible:
            if t["settle_date"] <= d:
                cash[t["currency"]] += t["net_amount"]
        px_rows[d] = (pos, sum(v * m["fxh"][d][c] for c, v in cash.items()))
    ends = sorted(px_rows)
    flows, monthly, link = [], [], 1.0
    for a, b in zip(ends, ends[1:]):
        # net_amount already carries the sign seen by the listed portfolio: calls out, distributions and transfers in or out
        fl = [(t["trade_date"], t["net_amount"] * m["fxh"][t["trade_date"]][t["currency"]], t) for t in visible
              if a < t["trade_date"] <= b and ((t["type"] == "transfer" and t["security_id"] == "") or t["type"] in ("call", "distribution"))]
        v0, v1 = sum(px_rows[a]), sum(px_rows[b])
        f = sum(x for _, x, _ in fl)
        wf = sum(x * (b - d).days / (b - a).days for d, x, _ in fl)
        r = (v1 - v0 - f) / (v0 + wf)
        monthly.append((b, v0, v1, f, r))
        flows += fl
        link *= 1 + r
    a, b = ends[0], ends[-1]
    bm = {k: m["bench"][b][k][1] / m["bench"][a][k][1] - 1 for k in INDICES}
    blend = sum(w / 100 * bm[k] for k, w in BLEND)
    return px_rows, monthly, flows, link - 1, bm, blend


def write_key(m, visible, dup, gap):
    W = m["weights"]
    f2 = lambda x: f"{x:,.2f}"  # noqa: E731
    pct = lambda x: f"{x:.2f} %"  # noqa: E731
    eq_max = next(t[3] for t in TARGET if t[0] == "equity")
    eq_first = min(d for d in TDAYS if all(W[x][0]["equity"] > eq_max for x in TDAYS if x >= d))
    cn_first = min(d for d in TDAYS if all(W[x][1] > CONC_LIMIT for x in TDAYS if x >= d))
    assert eq_first == MAY_DATE and all(W[d][0]["equity"] <= eq_max for d in TDAYS if d < MAY_DATE), "drift plant failed"
    assert cn_first == FEB_DATE and all(W[d][1] <= CONC_LIMIT for d in TDAYS if d < FEB_DATE), "concentration plant failed"
    miss = next(t for t in m["txns"] if t["reference"] == m["ref"]["miss"])
    q15 = m["snaps"][MISS_DATE][("NC-002", miss["security_id"])][0]
    vals, monthly, flows, twr, bm, blend = twr_q2(m, visible)
    stale_nav = m["nav_hist"]["PF02"][-1]
    L = ["# Demo family office: answer key for the structured sources", "",
         "Generated by `tools/make_samples_fo_demo.py`; do not edit by hand. Outside the product: a reviewer compares the platform's",
         "findings with these values. Paths are relative to `data/<company>/landing/`. Base currency SGD. FX rates in `fx_rates` are",
         "SGD per one unit of `base_currency`. Bond quantities are units of 100 nominal, so quantity x price = market value for every row.", "",
         "## 1. Reconciliation break (15 July 2026)",
         f"- File: `custodian_positions/custodian_positions_{MISS_DATE}.csv`, account NC-002, security {miss['security_id']} ({SEC[miss['security_id']]['name']}).",
         f"- Custodian quantity {q15:,}; transaction ledger quantity {q15 - miss['quantity']:,}; difference {miss['quantity']:,} shares.",
         f"- Cause: a buy of {miss['quantity']:,} at USD {miss['price']} (gross USD {f2(miss['gross_amount'])}, trade {miss['trade_date']}, settle {miss['settle_date']}, custodian reference {miss['reference']}) is missing from `custodian_transactions/custodian_transactions_2026-07.csv`.",
         f"- Knock-on: from 31 July 2026 the NC-002 USD cash in `custodian_cash` is USD {f2(miss['gross_amount'])} lower than the ledger sum, and every later positions file carries the same quantity difference. Tax lots of 30 Sep 2026 hold the lot.", "",
         "## 2. Missing price",
         f"- {gap} ({SEC[gap]['name']}, ISIN {SEC[gap]['isin']}, EUR) has no row in `market_prices/market_prices_2026-08.csv` on 2026-08-03 and 2026-08-04; it is priced on 2026-07-31 ({m['px'][date(2026, 7, 31)][gap]}) and 2026-08-05 ({m['px'][date(2026, 8, 5)][gap]}).",
         f"- The custodian positions files of those two days still carry a price ({m['px'][MISSING_PX_DAYS[0]][gap]} and {m['px'][MISSING_PX_DAYS[1]][gap]}). Manual adjustment ADJ-001 proposes the first and is still pending.", "",
         "## 3. Unknown security",
         f"- `custodian_positions/custodian_positions_{MEND[(2026, 6)]}.csv`, account NC-002, security_id `{UNKNOWN_ID}` is not in `security_master`.",
         f"- Its ISIN {SEC[ID['Granite Insurance']]['isin']} matches {ID['Granite Insurance']} (Granite Insurance), which is absent from that file under its own id. Every other file uses {ID['Granite Insurance']}. ADJ-002 maps it (approved).", "",
         "## 4. Duplicate transaction (12 December 2025)",
         f"- `custodian_transactions/custodian_transactions_2025-12.csv` holds reference {dup['reference']} twice: buy of {dup['quantity']:,} {dup['security_id']} ({SEC[dup['security_id']]['name']}) in NC-001 at SGD {dup['price']}, net SGD {f2(dup['net_amount'])}.",
         f"- Counting both rows overstates the NC-001 quantity of {dup['security_id']} by {dup['quantity']:,} and understates SGD cash by {f2(-dup['net_amount'])} from that date. ADJ-005 records the removal (approved by Aaron Lyle).", "",
         "## 5. Stale file",
         f"- `bank_balances`: account {STALE_BANK} (HKD, entity E2) has its last row on {STALE_LAST}; the other three accounts run to 2026-09-30. The September file and manifest still arrive on time.", "",
         "## 6. Out-of-balance cash (31 March 2026)",
         f"- `custodian_cash/custodian_cash_2026-03.csv`: {CASH_BREAK[0]} {CASH_BREAK[1]} balance and available are SGD {f2(CASH_BREAK[2])} higher than the sum of settled `net_amount` in the transaction ledger up to {CASH_BREAK[3]}. No transaction explains it; April onwards agrees again.",
         "- Every other account and month agrees to the cent, apart from the effects of truths 1 and 4.", "",
         "## 7. Stale private valuation",
         f"- In `private_portal/private_portal_2026-06-30.csv` fund PF02 ({PF['PF02']['name']}) shows nav_date {stale_nav[0]} (NAV USD {f2(stale_nav[1])}); PF01, PF03 and PF04 show 2026-06-30. It is 181 days old at 30 June 2026 (stale under a 180-day rule). PF02 is also stale in the 2026-03-31 file. ADJ-003 (a proposed manual NAV) was rejected.", "",
         f"## 8. Allocation drift (equity max {eq_max} %)",
         f"- Perimeter: three custodian accounts (positions plus cash, cash counted as cash_equivalent) plus private funds at the latest reported NAV with calls added and distributions deducted after the NAV date, all in SGD.",
         f"- First day above the maximum: {eq_first} (switch of bonds, funds and money funds into equities in NC-001 and NC-002). Equity stays above {eq_max} % on every trading day after, and is at or below it on every day before.",
         "- Month-end equity weights: " + "; ".join(f"{d}: {pct(W[d][0]['equity'])}" for d in sorted(MEND_SET)) + ".", "",
         f"## 9. Single-issuer concentration above {CONC_LIMIT:.0f} %",
         f"- Issuer {ISSUER}: equity {ID[ISSUER]} plus bond {ID['Pacific Lion Bank 3.85% 2031']}, same perimeter as truth 8.",
         f"- First day above {CONC_LIMIT:.0f} %: {cn_first} (government bonds switched into the bond in NC-001); above on every later trading day, at or below before.",
         "- Month-end weights: " + "; ".join(f"{d}: {pct(W[d][1])}" for d in sorted(MEND_SET)) + ".", "",
         "## 10. Performance, Q2 2026 (31 Mar to 30 Jun 2026)",
         "- Method: portfolio PF-MAIN listed part = three custodian accounts. Month-end value = sum of `market_value_base` in the month-end positions file plus ledger cash (settled `net_amount` per currency up to that date, duplicate removed) converted at that date's `fx_rates`. "
         "External flows = custodian `transfer` rows with blank security_id (bank transfers) plus capital calls (outflow) and distributions (inflow), converted at the flow date's rate. "
         "Monthly Modified Dietz with weight (month-end minus flow date) / (days in period), chained over April, May, June. Fees and income stay inside the return (net of fees).",
         "- Month-end values (positions + cash, SGD): " + "; ".join(f"{d}: {f2(p)} + {f2(c)}" for d, (p, c) in vals.items()) + ".",
         "- External flows (SGD): " + "; ".join(f"{d} {t['type']} {t['account_id']} {f2(x)}" for d, x, t in flows) + ".",
         "- Monthly returns: " + "; ".join(f"{b:%b} {r * 100:.4f} %" for b, v0, v1, f, r in monthly) + ".",
         f"- **Time-weighted return Q2 2026: {twr * 100:.4f} %.**",
         "- Benchmark: blend " + ", ".join(f"{k} {w} %" for k, w in BLEND) + " on `total_return_index`, buy and hold over the quarter (weights at 31 Mar): "
         + "; ".join(f"{k} {v * 100:.4f} %" for k, v in bm.items()) + f"; **blended {blend * 100:.4f} %**.",
         f"- **Benchmark-relative (TWR minus blend): {(twr - blend) * 100:+.4f} percentage points.**", ""]
    (ROOT / "docs" / "product" / "FO-DEMO-ANSWER-KEY.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
