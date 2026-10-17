"""The Evergreen Office world: entities, accounts, funds, and six months of daily life (1 Apr to 13 Oct 2026).
Everything the files and the answer keys show comes from the World built here. Deterministic (string seeds).
Reuses docs/test/10uc_universe.json for securities, prices, manager statements, fixings and the Oct trades."""
import bisect
import csv
import datetime as dt
import json
import math
import random
from decimal import Decimal as D, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
START, END = dt.date(2026, 4, 1), dt.date(2026, 10, 13)
OFFICE_RULES = dict(approval_over_usd=500000, buffer_usd=250000, single_name_pct=5, cash_tolerance=5000)


def q2(x): return D(x).quantize(D("0.01"), ROUND_HALF_UP)
def rng(tag): return random.Random("office6m:" + tag)
def d(s): return dt.date.fromisoformat(s)
def is_bd(x): return x.weekday() < 5
def ym(x): return x.strftime("%Y-%m")


def add_bd(x, n):
    step = 1 if n >= 0 else -1
    while n:
        x += dt.timedelta(days=step)
        if is_bd(x): n -= step
    return x


def next_bd(x):
    while not is_bd(x): x += dt.timedelta(days=1)
    return x


def bdays(a, b):
    out, x = [], a
    while x <= b:
        if is_bd(x): out.append(x)
        x += dt.timedelta(days=1)
    return out


DAYS = bdays(START, END)
MONTH_ENDS = [dt.date(2026, 3, 31), dt.date(2026, 4, 30), dt.date(2026, 5, 31), dt.date(2026, 6, 30), dt.date(2026, 7, 31), dt.date(2026, 8, 31), dt.date(2026, 9, 30)]


def lastbd(x):
    while not is_bd(x): x -= dt.timedelta(days=1)
    return x
ENT = {"EG-HOLD": "Evergreen Holdings", "EG-TRUST": "Evergreen Family Trust", "EG-B": "Entity B"}
SHORT = {"EG-HOLD": "HOLD", "EG-TRUST": "TRUST", "EG-B": "B"}
BANK = {"HB": "Harbour Bank (synthetic)", "TCB": "Tidewater Commercial Bank (synthetic)"}
ACCT = {}
for _i, _e in enumerate(ENT):
    for _j, _b in enumerate(BANK):
        for _k, _c in enumerate(("USD", "SGD")):
            _id = f"{_b}-{SHORT[_e]}-{_c}"
            ACCT[_id] = dict(id=_id, bank=_b, ent=_e, ccy=_c, no=f"{_b}-{4400 + 100 * _j + 10 * _i + _k}-{1101 + 37 * _i + 11 * _j + 3 * _k}")
PEOPLE = [("Raj Patel", "Chief Investment Officer", 21500), ("Daniel Foo", "Head of Finance", 19800), ("Anita Rao", "Head of Data", 17200),
          ("Mei Chen", "Principal", 0), ("Sofia Reyes", "Investment Analyst", 11200), ("Grace Ong", "Operations Lead", 10400),
          ("Helen Foo", "Fund Accountant", 8900), ("Tom Hale", "Risk and Compliance Officer", 12800), ("Priya Nair", "Office and HR Manager", 9300), ("Sam Lee", "Operations Clerk", 5600)]
MGR = {m["id"]: m for m in U["managers"]}
# funds: the universe's nine, plus F, G, K so there are 8 private funds with 4 managers (Northgate, Bluewater, Cedarpoint, Saltmarsh)
FUND = {f["key"]: dict(f) for f in U["funds"] if f["key"] != "LIQ"}
FUND["C"].update(legal_entity="EG-HOLD", portfolio="EG-PRIVATE")
FUND["F"] = dict(key="F", canonical_name="Evergreen Growth II", asset_class="private_equity", manager="MGR-NORTHGATE", statement_frequency="quarterly", legal_entity="EG-HOLD", portfolio="EG-PRIVATE")
FUND["G"] = dict(key="G", canonical_name="Evergreen Credit III", asset_class="private_credit", manager="MGR-BLUEWATER", statement_frequency="quarterly", legal_entity="EG-B", portfolio="EG-B-OPS")
FUND["K"] = dict(key="K", canonical_name="Saltmarsh Renewables I", asset_class="infrastructure", manager="MGR-SALTMARSH", statement_frequency="quarterly", legal_entity="EG-B", portfolio="EG-B-OPS")
FAMILY = [("Lin Chen", "spouse of the principal", 8000), ("Maya Chen", "daughter", 6000), ("Ethan Chen", "son", 5000), ("Wen Chen", "parent", 4000)]
ADMIN_RATE, CUST_RATE = D("0.0006"), D("0.0005")  # per year, on administered NAV and on the liquid book
PRIVATE = ["A", "B", "C", "D", "E", "F", "G", "K"]
# commitment, called before 1 Apr 2026, fee % of commitment per billing, billing months, standing account (last 4)
TERMS = {"A": (15000000, 10750000, "0.5", (3, 6, 9, 12), "3318"), "B": (8000000, 7200000, "0.5", (3, 6, 9, 12), "5520"),
         "C": (10000000, 3500000, "3.5", (4, 10), "2209"), "D": (5000000, 4500000, "0.375", (3, 6, 9, 12), "2210"),
         "E": (10000000, 2800000, "0.3125", (2, 5, 8, 11), "7741"), "F": (3000000, 1800000, "1.0", (2, 5, 8, 11), "3319"),
         "G": (2500000, 1500000, "0.75", (3, 6, 9, 12), "5521"), "K": (1350000, 1000000, "1.0", (2, 5, 8, 11), "7742")}
COMMIT_DATE = {"A": "2021-03-15", "B": "2022-06-01", "C": "2023-09-20", "D": "2022-11-10", "E": "2024-04-02", "F": "2025-02-10", "G": "2024-09-05", "K": "2025-06-12"}
# (fund, call no, notice date, due date, amount, fee billed in this call)
CALLS = [("C", 5, "2026-04-07", "2026-04-21", 1000000, 350000), ("E", 4, "2026-05-05", "2026-05-19", 600000, 31250), ("A", 11, "2026-06-03", "2026-06-17", 500000, 75000),
         ("G", 3, "2026-06-10", "2026-06-24", 400000, 28125), ("C", 6, "2026-07-07", "2026-07-21", 1500000, 0), ("F", 2, "2026-08-04", "2026-08-18", 600000, 30000),
         ("K", 2, "2026-08-11", "2026-08-25", 200000, 13500), ("G", 4, "2026-09-02", "2026-09-16", 300000, 18750), ("D", 5, "2026-09-01", "2026-09-15", 250000, 18750),
         ("E", 5, "2026-09-08", "2026-09-22", 600000, 0), ("C", 7, "2026-10-13", "2026-10-23", 1250000, 350000)]
# (fund, notice date, pay date, amount, kind)
DISTS = [("B", "2026-04-08", "2026-04-15", 120000, "income"), ("D", "2026-06-02", "2026-06-12", 180000, "capital"), ("B", "2026-07-08", "2026-07-15", 120000, "income"),
         ("A", "2026-07-07", "2026-07-16", 275000, "capital"), ("G", "2026-07-03", "2026-07-10", 55000, "income"), ("K", "2026-09-10", "2026-09-24", 30000, "income")]
VENDORS = [("Lakeside Legal LLP", "legal", "SGD", "3047"), ("Brightline Audit LLP", "audit", "USD", "8812"), ("Orchard IT Services", "it", "SGD", "2290"),
           ("Quill Research Subscriptions", "research", "USD", "6615"), ("Marina Office Suites", "rent", "SGD", "7001"), ("Summit Tax Advisory", "tax", "SGD", "4432"),
           ("Harbourview Courier", "courier", "SGD", "1188")]
TARGETS = {"HB-HOLD-USD": ("2026-10-13", 1030000), "TCB-HOLD-USD": ("2026-10-13", 200000), "HB-HOLD-SGD": ("2026-10-13", 1350000), "TCB-HOLD-SGD": ("2026-10-13", 250000),
           "HB-TRUST-USD": ("2026-10-08", 1090000), "TCB-TRUST-USD": ("2026-10-08", 60000), "HB-TRUST-SGD": ("2026-10-08", 2000000), "TCB-TRUST-SGD": ("2026-10-08", 300000),
           "HB-B-USD": ("2026-10-08", 668000), "TCB-B-USD": ("2026-10-08", 200000), "HB-B-SGD": ("2026-10-08", 1100000), "TCB-B-SGD": ("2026-10-08", 150000)}


class World:
    def __init__(self):
        self.tx, self.n = [], 0
        self.fx = self._fx()
        self.idx = self._idx()
        self.sec, self.px = self._prices()
        self.trades = self._trades()
        self.qty = self._positions()
        self.calls = self._calls()
        self.dists = [dict(id=f"DIST-{f}-{n[:7]}", fund=f, ent=FUND[f]["legal_entity"], notice=n, pay=next_bd(d(p)).isoformat(), amount=D(a), kind=k,
                           paid=D(a) - (D(12500) if (f, n) == ("A", "2026-07-07") else D(0))) for f, n, p, a, k in DISTS]  # planted: Fund A pays 12,500 less (withholding)
        self.stmts = self._stmts()
        self.invoices, self.policies, self.props, self.payroll, self.loan = [], [], [], [], []
        self.convs, self.approvals, self.fee_invoices, self.allow = [], [], [], []
        self._events()
        self._calibrate()

    # ------------------------------------------------------------------ market data
    def _fx(self):
        m = {d(k): D(v) for k, v in U["fx_fixings"]["month_end"].items()}
        daily = {d(k): D(v) for k, v in U["fx_fixings"]["daily_2026_09_01_to_10_09"].items()}
        out, anchors = {}, sorted(m)
        for a, b in zip(anchors, anchors[1:]):
            if b <= d("2026-03-31"): continue
            span = bdays(a, b)
            for i, x in enumerate(span):
                out[x] = (m[a] + (m[b] - m[a]) * i / (len(span) - 1)).quantize(D("0.0001"))
        out.update(daily); out.update({k: v for k, v in m.items() if k >= d("2026-03-31")})
        out[d("2026-10-12")], out[d("2026-10-13")] = D("1.3394"), D("1.3400")
        return {k: v for k, v in out.items() if k >= d("2026-03-31")}

    def _idx(self):
        rows = list(csv.reader(open(ROOT / "tests/v1/fixtures/10uc/market_data/index_levels_daily.csv", encoding="utf-8")))[1:]
        out = {r[0]: (D(r[1]), D(r[2])) for r in rows if r[0] >= "2026-03-31"}
        r, prev = rng("idx"), out["2026-09-30"]
        for x in bdays(d("2026-10-01"), END):  # October: small seeded drift
            prev = tuple((v * (1 + D(str(round(r.uniform(-0.002, 0.003), 5))))).quantize(D("0.01")) for v in prev)
            out[x.isoformat()] = prev
        return out

    def _prices(self):
        sec = {s["key"]: s for s in U["securities"]}
        px = {}
        for k, s in sec.items():
            a = {d(x): D(p) for x, p in s["prices_month_end"].items() if x >= "2026-03-31"}
            r, ds, dp = rng("px:" + k), sorted(a), 4 if s["instrument_type"] == "bond" else 2
            amp = D("0.004") if dp == 4 else D("0.012")
            px[k] = {}
            for x, y in zip(ds, ds[1:]):
                span = bdays(x, y)
                for i, t in enumerate(span):
                    f = i / (len(span) - 1)
                    lin = a[x] + (a[y] - a[x]) * D(str(round(f, 6)))
                    mult = 1 + amp * D(str(round(math.sin(math.pi * f), 6))) * D(str(round(r.uniform(-1, 1), 3)))
                    px[k][t] = (lin * mult).quantize(D(10) ** -dp)
                px[k][y] = a[y]
            for t in bdays(d("2026-10-01"), END):
                px[k][t] = (a[ds[-1]] * (1 + D(str(round(r.uniform(-0.006, 0.006), 4))))).quantize(D(10) ** -dp)
        return sec, px

    def _trades(self):
        """Apr-Aug trades (generated, one booked twice in the export) plus the Oct trades of the universe."""
        r, out = rng("trades"), []
        keys = [k for k in self.sec if k != "PRC29"]
        days = bdays(d("2026-04-06"), d("2026-08-26"))
        for i in range(16):
            k, day = r.choice(keys), r.choice(days)
            bond = self.sec[k]["instrument_type"] == "bond"
            qty = r.choice([250000, 500000]) if bond else r.choice([2000, 3000, 5000, 8000])
            side, p = r.choice(["buy", "sell"]), self.px[k][day]
            out.append(dict(id=f"T-{day:%Y%m%d}-{i + 1:03d}", trade=day, settle=add_bd(day, 2), sec=k, side=side, qty=D(qty), price=p, amt=q2(D(qty) * p), dup=False, admin_qty=D(qty), planted=None))
        out.sort(key=lambda t: (t["trade"], t["id"]))
        next(t for t in out if t["trade"].month == 6)["dup"] = True  # booked twice in the trading export
        for t in U["trades_oct"]:
            if t["security"].startswith("FXF"): continue
            out.append(dict(id=t["id"], trade=d(t["trade_date"]), settle=d(t["settlement_date"]), sec=t["security"], side=t["side"], qty=D(t["quantity"]), price=D(t["price"]), amt=D(t["amount"]), dup=False,
                            admin_qty=None if t["administrator_quantity"] is None else D(t["administrator_quantity"]), planted=t["planted"]))
        return out

    def _positions(self):
        sign = lambda t: t["qty"] if t["side"] == "buy" else -t["qty"]
        start = {k: D(s["quantity_30_sep"]) for k, s in self.sec.items()}
        for t in self.trades:
            if t["settle"] <= d("2026-09-30"): start[t["sec"]] -= sign(t)
        assert all(v >= 0 for v in start.values()), {k: v for k, v in start.items() if v < 0}
        return {x: {k: start[k] + sum(sign(t) for t in self.trades if t["sec"] == k and t["settle"] <= x) for k in start} for x in sorted(set(DAYS) | set(MONTH_ENDS))}

    def nav_total(self, pe):
        """Administrator NAV across all portfolios at period end pe (released 06:00 UTC on the 2nd business day after)."""
        cut = f"{add_bd(d(pe), 2)}T06:00:00Z"
        funds = sum((k["value"] for f in FUND for k in [self.known(f, pe, cut)] if k), D(0))
        return funds + self.book(lastbd(d(pe)))

    def value(self, k, x): return q2(self.qty[x][k] * self.px[k][x])
    def book(self, x): return sum((self.value(k, x) for k in self.sec), D(0))

    # ------------------------------------------------------------------ calls and statements
    def _calls(self):
        cum, out = {f: D(TERMS[f][1]) for f in PRIVATE}, []
        for f, no, nd, dd, amt, fee in sorted(CALLS, key=lambda c: (c[2], c[0])):
            cum[f] += amt
            chg = f == "C" and no == 7
            out.append(dict(id=f"CALL-{f}-{no}", fund=f, no=no, ent=FUND[f]["legal_entity"], notice=nd, due=next_bd(d(dd)).isoformat(), amount=D(amt), fee=D(fee), invest=D(amt) - D(fee),
                            cum=cum[f], commit=D(TERMS[f][0]), acct="4471" if chg else TERMS[f][4], std_acct=TERMS[f][4], changed=chg))
        return out

    def _stmts(self):
        S = [dict(fund=s["fund"], period=s["period_end"], kind=s["kind"], value=None if s["value"] is None else D(s["value"]), received=s["received_at"][:10] if s["received_at"] else None, rts=s["received_at"],
                  title=s["title"], status=s["status"], note=s["note"], due=s["due_date"]) for s in U["statements"] if s["period_end"] >= "2026-03-31" and s["fund"] != "LIQ"]
        vals = {"F": ("2350000", "2410000", "3080000"), "G": ("1610000", "2090000", "2420000"), "K": ("1040000", "1055000", "1310000")}
        lag = {"F": (7, 7, 8), "G": (9, 9, 7), "K": (11, 12, 99)}
        for f, v in vals.items():
            for i, pe in enumerate(("2026-03-31", "2026-06-30", "2026-09-30")):
                rec = add_bd(d(pe), lag[f][i]) if lag[f][i] < 99 else None
                if rec and rec > END: rec = None
                S.append(dict(fund=f, period=pe, kind="final", value=D(v[i]) if rec else None, received=rec.isoformat() if rec else None, rts=f"{rec}T05:00:00Z" if rec else None, title=None,
                              status="official" if rec else "not received", note=None, due=add_bd(d(pe), 10).isoformat()))
        return S

    def known(self, fund, period_end, asof):
        """Latest statement (amended > final > estimate) for the newest period <= period_end received by asof (an ISO timestamp); None if nothing."""
        rank = {"amended": 3, "final": 2, "estimate": 1}
        c = [s for s in self.stmts if s["fund"] == fund and s["value"] is not None and s["rts"] and s["rts"] <= asof and s["period"] <= period_end and s["kind"] in rank]
        c.sort(key=lambda s: (s["period"], rank[s["kind"]], s["received"]))
        return c[-1] if c else None

    # ------------------------------------------------------------------ the money
    def add(self, acct, day, amt, typ, desc, cpty, ref, admin=None, oms=None, ev=None):
        self.n += 1
        day = next_bd(day if isinstance(day, dt.date) else d(day))
        self.tx.append(dict(n=self.n, acct=acct, date=day, admin=admin or day, oms=oms or day, amt=q2(amt), typ=typ, desc=desc, cpty=cpty, ref=ref, ev=ev))

    def convert(self, ent, day, usd, why, confirm=True):
        day = next_bd(d(day)); e = SHORT[ent]
        rate = (self.fx[day] + D("0.0005")).quantize(D("0.0001")); sgd = q2(usd * rate); ref = f"FXS-{day:%Y%m%d}-{e}"
        self.add(f"HB-{e}-SGD", day, -sgd, "fx_conversion", f"Sold SGD {sgd:,.2f} / bought USD {usd:,.2f} at {rate} ({why})", "Harbour Bank FX desk", ref, ev=ref)
        self.add(f"HB-{e}-USD", day, usd, "fx_conversion", f"Bought USD {usd:,.2f} / sold SGD {sgd:,.2f} at {rate} ({why})", "Harbour Bank FX desk", ref, ev=ref)
        self.convs.append(dict(id=ref, ent=ent, date=day, usd=D(usd), sgd=sgd, rate=rate, fix=self.fx[day], why=why, confirm=confirm))

    def approve(self, ref, ent, day, usd, payee, approved=True):
        self.approvals.append(dict(ref=ref, ent=ent, date=day if isinstance(day, dt.date) else d(day), usd=q2(usd), payee=payee, approved_by="Daniel Foo" if approved else "", approved=approved))

    def _events(self):
        r = rng("events")
        for c in self.calls:  # capital calls are paid on the due date
            if c["due"] > END.isoformat(): continue
            e = SHORT[c["ent"]]
            src = "TCB-B-USD" if c["ent"] == "EG-B" else f"HB-{e}-USD"
            if c["ent"] == "EG-B":
                self.add("HB-B-USD", c["due"], -c["amount"], "internal_transfer", f"Transfer to Tidewater USD for {c['id']}", "Entity B", f"TRF-{c['id']}", ev=c["id"])
                self.add("TCB-B-USD", c["due"], c["amount"], "internal_transfer", f"Transfer from Harbour USD for {c['id']}", "Entity B", f"TRF-{c['id']}", ev=c["id"])
            self.add(src, c["due"], -c["amount"], "capital_call", f"CAPCALL {FUND[c['fund']]['canonical_name']} No.{c['no']} ACCT {c['acct']}", MGR[FUND[c["fund"]]["manager"]]["name"], f"CC-{c['id']}", ev=c["id"])
            if c["amount"] > OFFICE_RULES["approval_over_usd"]:
                self.approve(f"CC-{c['id']}", c["ent"], d(c["due"]), c["amount"], FUND[c["fund"]]["canonical_name"], approved=c["id"] != "CALL-F-2")  # F call 2: planted, no approval on record
        for x in self.dists:
            if x["pay"] <= END.isoformat():
                self.add(f"HB-{SHORT[x['ent']]}-USD", x["pay"], x["paid"], "distribution", f"DISTRIBUTION {FUND[x['fund']]['canonical_name']} ({x['kind']})" + (" net of withholding" if x["paid"] != x["amount"] else ""), MGR[FUND[x["fund"]]["manager"]]["name"], f"DI-{x['id']}", ev=x["id"])
        self.convert("EG-HOLD", "2026-04-16", D(1000000), "fund capital call 5")
        self.convert("EG-HOLD", "2026-06-02", D(500000), "fund capital call 11", confirm=False)  # planted: no confirmation on file
        self.convert("EG-HOLD", "2026-07-14", D(1500000), "fund capital call 6")
        self.convert("EG-B", "2026-05-12", D(600000), "fund capital call 4")
        self.convert("EG-B", "2026-06-05", D(400000), "fund capital call 3")
        self.convert("EG-B", "2026-08-10", D(200000), "fund capital call 2")
        self.convert("EG-B", "2026-09-08", D(1150000), "fund September calls")
        self.convert("EG-TRUST", "2026-05-20", D(300000), "treasury")
        self.add("HB-TRUST-USD", "2026-08-05", D(-600000), "intercompany_transfer", "Transfer to Evergreen Holdings (intercompany loan IC-2026-08-01)", "Evergreen Holdings", "IC-2026-08-01", ev="IC-2026-08-01")
        self.add("HB-HOLD-USD", "2026-08-05", D(600000), "intercompany_transfer", "Transfer from Evergreen Family Trust (intercompany loan IC-2026-08-01)", "Evergreen Family Trust", "IC-2026-08-01", ev="IC-2026-08-01")
        self.approve("IC-2026-08-01", "EG-TRUST", d("2026-08-05"), D(600000), "Evergreen Holdings")
        for t in self.trades:  # trade settlements
            if t["settle"] > END: continue
            self.add("HB-TRUST-USD", t["settle"], t["amt"] if t["side"] == "sell" else -t["amt"], "trade_settlement", f"{t['side'].upper()} {t['qty']:,.0f} {t['sec']} @ {t['price']}", "Synthetic Broker One", f"TS-{t['id']}", ev=t["id"])
            if t["amt"] > OFFICE_RULES["approval_over_usd"] and t["side"] == "buy":
                self.approve(f"TS-{t['id']}", "EG-TRUST", t["settle"], t["amt"], "Synthetic Broker One")
        cpn = {"CRB31": (D("0.051"), (3, 9), 15), "HTN29": (D("0.039"), (6, 12), 30), "KFB30": (D("0.046"), (1, 7), 20)}  # custodian income
        for i, (k, s) in enumerate(self.sec.items()):
            if k in cpn:
                for mth in cpn[k][1]:
                    x = next_bd(dt.date(2026, mth, cpn[k][2]))
                    if START <= x <= END:
                        self.add("HB-TRUST-USD", x, cpn[k][0] / 2 * self.qty[x][k], "coupon", f"COUPON {s['canonical_name']}", "Anchorage Custody (synthetic)", f"CP-{k}-{x:%Y%m%d}", ev=k)
            elif k != "PRC29":
                for mth in (4, 7, 10):
                    x = next_bd(dt.date(2026, mth, 10 + (i % 3) * 5))
                    if START <= x <= END:
                        self.add("HB-TRUST-USD", x, self.qty[x][k] * self.px[k][x] * D("0.0045"), "dividend", f"DIVIDEND {s['canonical_name']}", "Anchorage Custody (synthetic)", f"DV-{k}-{x:%Y%m%d}", ev=k)
        for m in range(4, 11):  # family allowances from the Trust on the first business day; Ethan Chen's September allowance is not paid (planted)
            day = next_bd(dt.date(2026, m, 1))
            for nm, rel, amt in FAMILY:
                paid = not (nm == "Ethan Chen" and m == 9)
                self.allow.append(dict(member=nm, rel=rel, month=f"2026-{m:02d}", due=day, amount=D(amt), paid=paid))
                if paid: self.add("HB-TRUST-USD", day, -D(amt), "allowance", f"ALLOWANCE {nm} {2026}-{m:02d}", nm, f"AL-{nm.split()[0]}-2026{m:02d}", ev="allowance")
        for q, pe, inv_day in (("Q2", "2026-06-30", "2026-07-06"), ("Q3", "2026-09-30", "2026-10-05")):  # administrator and custodian quarterly invoices
            idd = d(inv_day); due = next_bd(idd + dt.timedelta(days=14))
            nav = self.nav_total(pe); book = self.book(lastbd(d(pe)))
            for who, base, rate, name in (("admin", nav, ADMIN_RATE, "Harbourline Fund Services (synthetic)"), ("cust", book, CUST_RATE * (D("1.2") if (q, "cust") == ("Q3", "cust") else 1), "Anchorage Custody (synthetic)")):
                amt = q2(base * rate / 4); exp = q2(base * (ADMIN_RATE if who == "admin" else CUST_RATE) / 4)
                self.fee_invoices.append(dict(id=f"FEE-{who.upper()}-{q}", who=who, vendor=name, quarter=q, date=idd, due=due, base=base, rate=rate, amount=amt, expected=exp))
                if due <= END: self.add("HB-TRUST-USD", due, -amt, "vendor_payment", f"PAY {who} fee {q} {name}", name, f"VP-FEE-{who.upper()}-{q}", ev=f"FEE-{who.upper()}-{q}")
        # the three cash breaks: the administrator or the desk books an item on another day than the bank
        self.add("HB-TRUST-USD", "2026-06-17", D("-6200"), "fee", "Custody and fund administration fee Q2", "Anchorage Custody (synthetic)", "FEE-20260617-T01", admin=d("2026-06-18"), ev="BRK-T-0617")
        self.add("HB-TRUST-USD", "2026-10-09", D("-1800"), "fee", "Bank and custody fee", "Anchorage Custody (synthetic)", "FEE-20261009-T01", oms=d("2026-10-08"), ev="BRK-T-1008")
        self.add("HB-B-USD", "2026-10-08", D("-12400"), "wire", "Wire to Lakeside Legal LLP - legal fees", "Lakeside Legal LLP", "WIRE-20261008-B01", admin=d("2026-10-09"), ev="BRK-B-1008")
        bal = D(3000000)  # Entity B term loan TL-B-01 at Harbour Bank: interest monthly on the 28th, 100,000 principal quarterly
        for m in range(4, 10):
            pay = next_bd(dt.date(2026, m, 28))
            intr, amort = q2(bal * D("0.0610") / 12), D(100000) if m in (6, 9) else D(0)
            self.add("HB-B-USD", pay, -(intr + amort), "loan_service", f"Term loan TL-B-01 interest {intr:,.2f}" + (f" and principal {amort:,.2f}" if amort else ""), BANK["HB"], f"LOAN-{pay:%Y%m}", ev="TL-B-01")
            self.loan.append(dict(month=f"2026-{m:02d}", open=bal, interest=intr, principal=amort, close=bal - amort, date=pay)); bal -= amort
        for m in range(4, 10):  # payroll: net on the 25th (previous bd if weekend) from Holdings SGD; CPF on the 14th of the next month
            rows = [(n, t, D(g), q2(D(g) * D("0.80")), q2(D(g) * D("0.17"))) for n, t, g in PEOPLE if g]
            day = dt.date(2026, m, 25)
            while not is_bd(day): day -= dt.timedelta(days=1)
            net, cpf = sum((x[3] for x in rows), D(0)), sum((x[4] + q2(x[2] * D("0.20")) for x in rows), D(0))
            self.payroll.append(dict(month=f"2026-{m:02d}", date=day, rows=rows, net=net, gross=sum((x[2] for x in rows), D(0)), cpf=cpf))
            self.add("HB-HOLD-SGD", day, -net, "payroll", f"PAYROLL 2026-{m:02d} net pay run", "Evergreen Holdings payroll", f"PAY-2026{m:02d}", ev=f"PAY-2026-{m:02d}")
            self.add("HB-HOLD-SGD", dt.date(2026, m + 1, 14), -cpf, "payroll_tax", f"CPF contributions for 2026-{m:02d}", "Central Provident Fund (synthetic)", f"CPF-2026{m:02d}", ev=f"PAY-2026-{m:02d}")
        vend = {v[0]: v for v in VENDORS}
        inv = [("Marina Office Suites", f"MOS-26{m:02d}", dt.date(2026, m, 1), D(18500), "Office rent " + dt.date(2026, m, 1).strftime("%B %Y")) for m in range(4, 11)]
        inv += [("Orchard IT Services", f"INV-OIT-26{m:02d}", dt.date(2026, m, 3), D(2950), "Managed IT and security, " + dt.date(2026, m, 1).strftime("%B %Y")) for m in range(4, 10)]
        inv += [("Quill Research Subscriptions", "QRS-0426", d("2026-04-01"), D(4800), "Research subscription Q2"), ("Quill Research Subscriptions", "QRS-0726", d("2026-07-01"), D(4800), "Research subscription Q3"),
                ("Lakeside Legal LLP", "LL-2026-0418", d("2026-04-20"), D(14800), "Fund documentation review"), ("Lakeside Legal LLP", "LL-2026-0708", d("2026-07-08"), D(22300), "Subscription agreements, side letters"),
                ("Lakeside Legal LLP", "LL-2026-0828", d("2026-08-28"), D(9600), "Trust deed amendment"), ("Brightline Audit LLP", "BAL-2026-051", d("2026-05-12"), D(38000), "Audit of Evergreen Holdings FY2025"),
                ("Summit Tax Advisory", "STA-2606", d("2026-06-15"), D(7200), "Tax filing support"), ("Summit Tax Advisory", "STA-2609", d("2026-09-14"), D(5400), "Tax advisory Q3"),
                ("Harbourview Courier", "HC-26-0612", d("2026-06-12"), D(380), "Courier and document delivery"), ("Harbourview Courier", "HC-26-0903", d("2026-09-03"), D(420), "Courier and document delivery")]
        for n, (vn, no, day, amt, desc) in enumerate(sorted(inv, key=lambda t: (t[2], t[1]))):
            v = vend[vn]; due = next_bd(day + dt.timedelta(days=0 if v[1] == "rent" else 30))
            acct_end = "6029" if no == "LL-2026-0828" else v[3]  # planted: Lakeside Legal's August invoice shows a new bank account
            self.invoices.append(dict(id=f"INV-{n + 1:03d}", vendor=vn, no=no, date=day, due=due, amt=amt, ccy=v[2], desc=desc, cat=v[1], acct_end=acct_end, std_acct=v[3], changed=acct_end != v[3], dup=False))
            if due <= END: self.add(f"HB-HOLD-{v[2]}", due, -amt, "vendor_payment", f"PAY {no} {vn}", vn, f"VP-{no}", ev=no)
        o = next(i for i in self.invoices if i["no"] == "INV-OIT-2606")  # planted duplicate: the June IT invoice sent again, same number and amount
        self.invoices.append(dict(o, id="INV-DUP-001", date=d("2026-06-24"), dup=True))
        for pol, nm, ccy, prem, ren in [("POL-HOME-01", "Bayview Residence home and contents", "SGD", 18400, "2026-06-01"), ("POL-ART-02", "Fine art collection", "USD", 22500, "2026-08-15"),
                                        ("POL-LIAB-03", "Umbrella liability", "USD", 9800, "2026-11-01"), ("POL-CYB-04", "Family office cyber", "SGD", 6200, "2026-12-01")]:
            rd = d(ren)
            self.policies.append(dict(id=pol, name=nm, ccy=ccy, premium=D(prem), renewal=rd, notice=rd - dt.timedelta(days=45), prior=q2(D(prem) * D("0.85")) if pol == "POL-HOME-01" else D(prem)))
            if START <= next_bd(rd) <= END: self.add(f"HB-HOLD-{ccy}", rd, -D(prem), "insurance", f"PREMIUM {pol} {nm}", "SafeHarbour Insurance Brokers (synthetic)", f"INS-{pol}", ev=pol)
        for pn, ent in [("Bayview Residence", "EG-HOLD"), ("Hillcrest House", "EG-TRUST")]:
            for m in range(4, 11):
                items = [("Management and maintenance", D(1850) if pn == "Hillcrest House" else D(2400)), ("Utilities", q2(r.uniform(380, 640)))]
                if m in (4, 7, 10): items.append(("Property tax (quarter)", D(5400) if pn.startswith("Bay") else D(3900)))
                self.props.append(dict(id=f"PB-{'BV' if pn.startswith('Bay') else 'HC'}-26{m:02d}", prop=pn, month=f"2026-{m:02d}", date=dt.date(2026, m, 5), due=next_bd(dt.date(2026, m, 26)), ccy="SGD", ent=ent,
                                       items=items, total=sum((i[1] for i in items), D(0))))
        for p in self.props:
            if p["due"] <= END: self.add(f"HB-{SHORT[p['ent']]}-SGD", p["due"], -p["total"], "property", f"PAY {p['id']} {p['prop']}", p["prop"] + " managing agent", f"PB-{p['id']}", ev=p["id"])
        for a in ACCT:  # noise: bank fee and interest per account per month
            for m in range(4, 11):
                rr = rng(f"noise:{a}:{m}")
                self.add(a, dt.date(2026, m, 28 if m < 10 else 12), -q2(rr.uniform(18, 60)), "bank_fee", "Account maintenance fee", BANK[ACCT[a]["bank"]], f"BF-{a}-{m:02d}")
                self.add(a, dt.date(2026, m, 30 if m < 10 else 12), q2(rr.uniform(15, 380)), "interest", "Credit interest", BANK[ACCT[a]["bank"]], f"IN-{a}-{m:02d}")
        self.tx = sorted((t for t in self.tx if t["date"] <= END), key=lambda t: (t["date"], t["n"]))

    # ------------------------------------------------------------------ opening balances and the three cash views
    def _calibrate(self):
        self.open, self.bal = {}, {a: {} for a in ACCT}
        for a, (day, amt) in TARGETS.items():
            self.open[a] = D(amt) - sum((t["amt"] for t in self.tx if t["acct"] == a and t["date"] <= d(day)), D(0))
        for a in ACCT:
            run, items = self.open[a], [t for t in self.tx if t["acct"] == a]
            for x in DAYS:
                run += sum((t["amt"] for t in items if t["date"] == x), D(0))
                self.bal[a][x] = run

    def cash(self, ent, ccy, x, src="bank"):
        """Cash of an entity in one currency at end of day x, as the bank, the administrator or the trading desk books it."""
        if not hasattr(self, "_cum"):
            self._cum = {}
            for a in ACCT:
                for sname, f in (("bank", "date"), ("admin", "admin"), ("oms", "oms")):
                    ev = sorted(((t[f], t["n"], t["amt"]) for t in self.tx if t["acct"] == a)); run, ds, rs = self.open[a], [], []
                    for day, _, amt in ev: run += amt; ds.append(day); rs.append(run)
                    self._cum[(a, sname)] = (ds, rs)
        tot = D(0)
        for a, v in ACCT.items():
            if v["ent"] == ent and v["ccy"] == ccy:
                ds, rs = self._cum[(a, src)]; i = bisect.bisect_right(ds, x); tot += rs[i - 1] if i else self.open[a]
        return tot


if __name__ == "__main__":
    w = World()
    for a in ACCT:
        print(a, w.open[a], min(w.bal[a].values()), max(w.bal[a].values()))
    print(w.book(d("2026-09-30")), w.book(d("2026-08-31")), len(w.tx))
    print(w.cash("EG-HOLD", "USD", END), w.cash("EG-B", "USD", d("2026-10-08"), "admin"), w.cash("EG-TRUST", "USD", d("2026-10-08"), "oms"))
