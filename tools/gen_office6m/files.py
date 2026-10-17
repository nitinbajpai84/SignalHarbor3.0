"""Write every file of the Evergreen Office 6-month data set from a World. Folder = month the file arrives or is dated."""
import datetime as dt
import shutil
from decimal import Decimal as D

from .world import (ACCT, BANK, DAYS, END, ENT, FUND, MGR, PRIVATE, SHORT, START, TERMS, U, World, add_bd, bdays, d, is_bd, next_bd, q2, ym, ROOT, OFFICE_RULES, SIGNED_RULES, COMMIT_DATE, VENDORS)
from .writers import Registry, copy_lf, write_csv, write_eml, write_pdf, write_xlsx, pdf_bytes

OPS = "ops@evergreen-office.example.test"
MESS = []  # filled while writing: dict(id, kind, where, what)


def mess(i, kind, where, what):
    MESS.append(dict(id=i, kind=kind, where=where, what=what))


def money(x): return f"{D(x):,.2f}"
def dlong(x): return (x if isinstance(x, dt.date) else d(x[:10])).strftime("%d %B %Y").lstrip("0")
def month_end(m):  # m = "2026-04"
    y, mm = int(m[:4]), int(m[5:])
    return dt.date(y + (mm == 12), mm % 12 + 1, 1) - dt.timedelta(days=1)
def months(a="2026-04", b="2026-09"):
    out, y, m = [], int(a[:4]), int(a[5:])
    while f"{y}-{m:02d}" <= b:
        out.append(f"{y}-{m:02d}"); y, m = y + (m == 12), m % 12 + 1
    return out
def arrive(m, n=2): return add_bd(month_end(m), n)
def pname(f): return FUND[f]["canonical_name"]
def acode(f): return {"F": "4490", "G": "4491", "K": "4492"}.get(f) or FUND[f]["identifiers"]["administrator"]["administrator_code"]
def mgr(f): return MGR[FUND[f]["manager"]]


def generate(out, w=None):
    MESS.clear(); RECV.clear()
    w = w or World()
    R = Registry(out)
    bank_statements(w, R); admin_cash(w, R); custodian(w, R); admin_nav(w, R); manager_statements(w, R); notices(w, R); trading(w, R)
    fx_files(w, R); vendors(w, R); people_and_property(w, R); notes_and_mail(w, R); reports(w, R); loans(w, R); approvals(w, R); reference(w, R)
    from .files2 import generate2
    generate2(w, R)
    from .more import generate3
    generate3(w, R)
    write_csv(R.out / "received_log_all.csv", ["file", "kind", "period", "expected_on", "received_on", "status"], RECV)
    return w, R, MESS


RECV = []  # (file, kind, period, expected, received, status)


def recv(R, p, kind, period, expected, received, status="received"):
    RECV.append([p.relative_to(R.out).as_posix(), kind, period, expected.isoformat(), received.isoformat() if received else "", status])


# ---------------------------------------------------------------------------------------------------- bank statements
LATE_BANK = {("HB-TRUST-SGD", "2026-05"): d("2026-06-16")}
MISSING_BANK = {("TCB-B-USD", "2026-07")}


def bank_statements(w, R):
    for a, v in ACCT.items():
        for m in months("2026-04", "2026-09") + ["2026-10"]:
            days = [x for x in DAYS if ym(x) == m]
            exp = arrive(m, 2 if v["bank"] == "HB" else 4) if m != "2026-10" else END
            if (a, m) in MISSING_BANK:
                RECV.append([f"(missing) bank_statements/{a}_{m}.xlsx", "bank_statement", m, exp.isoformat(), "", "never received"])
                mess("M02b", "statement missing", f"bank_statements/{a}_{m}", f"{BANK[v['bank']]} statement for {a} {m} never arrives (expected {exp})")
                continue
            got = LATE_BANK.get((a, m), exp)
            folder = ym(got)
            txs = [t for t in w.tx if t["acct"] == a and ym(t["date"]) == m]
            prev = w.open[a]
            daily = []
            for x in days:
                cl = w.bal[a][x]; daily.append([x.isoformat(), v["no"], v["ccy"], float(prev), float(cl - prev), float(cl)]); prev = cl
            p = R.path(folder, "bank_statements", f"{v['bank']}_{SHORT[v['ent']]}_{v['ccy']}_{m}{'_mtd' if m == '2026-10' else ''}.xlsx")
            write_xlsx(p, {"Transactions": [["Value date", "Reference", "Type", "Description", "Counterparty", "Amount", "Currency"]] +
                           [[t["date"].isoformat(), t["ref"], t["typ"], t["desc"], t["cpty"], float(t["amt"]), v["ccy"]] for t in txs],
                           "Daily balances": [["Value date", "Account number", "Currency", "Opening balance", "Net movement", "Closing ledger balance"]] + daily})
            tags = ["M02a"] if (a, m) in LATE_BANK else []
            if tags: mess("M02a", "statement late", f"bank_statements/{p.name}", f"{a} {m} statement expected {exp}, received {got}")
            R.add(p, "bank_statements", folder, f"{BANK[v['bank']]} {v['ccy']} account of {ENT[v['ent']]} ({v['no']}), {m}: Transactions and Daily balances", tags)
            recv(R, p, "bank_statement", m, exp, got, "late" if tags else "received")


# ---------------------------------------------------------------------------------------------------- administrator cash and nav
def admin_cash(w, R):
    for m in months("2026-04", "2026-09") + ["2026-10"]:
        days = [x for x in DAYS if ym(x) == m]
        rows = [[x.isoformat(), e, ENT[e], c, float(w.cash(e, c, x, "admin"))] for x in days for e in ENT for c in ("USD", "SGD")]
        arr = arrive(m, 2) if m != "2026-10" else END
        p = R.path(ym(arr), "administrator_cash", f"administrator_cash_{m}{'_mtd' if m == '2026-10' else ''}.csv")
        write_csv(p, ["date", "entity_code", "entity_name", "currency", "administrator_cash"], rows)
        tags = ["M04"] if m in ("2026-06", "2026-10") else []
        R.add(p, "administrator_cash", ym(arr), f"Administrator's official daily cash per entity and currency, {m}", tags)
    for m in months("2026-04", "2026-09") + ["2026-10"]:
        arr = arrive(m, 2) if m != "2026-10" else END
        rows = [[t["id"], t["trade"].isoformat(), t["sec"], float(t["admin_qty"]) if t["admin_qty"] is not None else "", t["side"]] for t in w.trades if ym(t["trade"]) == m and t["admin_qty"] is not None]
        p = R.path(ym(arr), "administrator_trades", f"administrator_trades_{m}.csv")
        write_csv(p, ["external_trade_id", "trade_date", "security_code", "administrator_quantity", "side"], rows)
        R.add(p, "administrator_trades", ym(arr), f"Trades as booked by the administrator, {m}", ["M16"] if m == "2026-10" else [])


def status_word(s, pe):
    if s is None: return "Not received"
    if s["period"] != pe: return "Carried forward"
    return {"final": "Final", "estimate": "Estimate", "amended": "Amended"}[s["kind"]]


def admin_nav(w, R):
    for me in [dt.date(2026, 3, 31)] + [month_end(m) for m in months("2026-04", "2026-09")]:
        arr = add_bd(me, 2); pe = me.isoformat(); cut = f"{arr}T06:00:00Z"; hdr = "Valuation Amount (USD)" if pe == "2026-06-30" else "Market Value"
        rows = [["Portfolio", "Admin Code", "Instrument", "Quantity", "Price", hdr, "Currency", "Valuation Status", "Valuation Date"]]
        nav = {}
        for k, s in w.sec.items():
            val = w.value(k, me); nav["EG-LIQUID"] = nav.get("EG-LIQUID", D(0)) + val
            rows.append(["EG-LIQUID", int(s["identifiers"]["administrator"]["administrator_code"]), s["canonical_name"], float(w.qty[me][k]), float(w.px[k][me]), float(val), "USD", "Priced", pe])
        for f in sorted(FUND):
            k = w.known(f, pe, cut)
            port = FUND[f]["portfolio"]
            nav[port] = nav.get(port, D(0)) + (k["value"] if k else D(0))
            rows.append([port, int(acode(f)), pname(f), "", "", float(k["value"]) if k else "", "USD", status_word(k, pe), k["period"] if k else ""])
        p = R.path(ym(arr), "administrator_nav", f"administrator_export_{ym(me)}.xlsx")
        write_xlsx(p, {"Positions": rows, "NAV by portfolio": [["Portfolio", "Administrator NAV", "As of"]] + [[k, float(v), pe] for k, v in sorted(nav.items())]})
        tags = ["M18"] if pe == "2026-06-30" else []
        if tags: mess("M18", "column renamed", f"administrator_nav/{p.name}", "In the 30 June pack the column 'Market Value' is called 'Valuation Amount (USD)'")
        R.add(p, "administrator_nav", ym(arr), f"Administrator monthly NAV pack as at {pe}, released {arr} 06:00 UTC: positions, status, NAV by portfolio", tags)


# ---------------------------------------------------------------------------------------------------- custodian
def custodian(w, R):
    for x in DAYS:
        rows = [[x.isoformat(), "EG-LIQUID", "Anchorage Custody (synthetic)", f"SEC-{k}", s["identifiers"]["trading_export"]["ticker"], s["canonical_name"], s["asset_class"] or "", float(w.qty[x][k]), float(w.px[k][x]), float(w.value(k, x)), "USD"]
                for k, s in w.sec.items()]
        p = R.path(ym(x), "custodian_positions", f"positions_{x:%Y%m%d}.csv")
        write_csv(p, ["as_of", "portfolio", "custodian", "security_id", "ticker", "security_name", "asset_class", "quantity", "price", "market_value", "currency"], rows)
        R.add(p, "custodian_positions", ym(x), f"Custodian end-of-day positions of the Evergreen Liquid portfolio, {x}", ["M17"])
    mess("M17", "missing class", "custodian_positions (every day)", "The Pacific Rim Convertible 2029 note (PRC29) has no asset class in the custodian file")
    for m in months("2026-04", "2026-09") + ["2026-10"]:
        rows = []
        for t in w.trades:
            if ym(t["trade"]) == m: rows.append([t["trade"], t["settle"], t["side"], f"SEC-{t['sec']}", float(t["qty"]), float(t["price"]), float(t["amt"]), "USD", f"CT-{t['id']}"])
        for t in w.tx:
            if t["typ"] in ("dividend", "coupon") and ym(t["date"]) == m: rows.append([t["date"], t["date"], t["typ"], "SEC-" + t["ev"], "", "", float(t["amt"]), "USD", f"CT-{t['ref']}"])
            if t["typ"] == "fee" and t["acct"] == "HB-TRUST-USD" and ym(t["date"]) == m: rows.append([t["date"], t["date"], "fee", "", "", "", float(t["amt"]), "USD", f"CT-{t['ref']}"])
        rows.sort(key=lambda r: (str(r[0]), r[8]))
        tags = []
        if m == "2026-07" and rows:  # planted: one date written day/month/year while the rest are ISO
            rows[0][0] = rows[0][0].strftime("%d/%m/%Y"); tags = ["M11a"]
            mess("M11a", "date format", f"custodian_transactions/transactions_2026-07.csv", f"First row txn_date is written {rows[0][0]} (dd/mm/yyyy); all other dates are ISO")
        rows = [[r[0].isoformat() if hasattr(r[0], "isoformat") else r[0], r[1].isoformat(), *r[2:]] for r in rows]
        arr = arrive(m, 1) if m != "2026-10" else END
        p = R.path(ym(arr), "custodian_transactions", f"transactions_{m}{'_mtd' if m == '2026-10' else ''}.csv")
        write_csv(p, ["txn_date", "settle_date", "type", "security_id", "quantity", "price", "amount", "currency", "reference"], rows)
        R.add(p, "custodian_transactions", ym(arr), f"Custodian transactions (trades, dividends, coupons, fees) of the Evergreen Liquid portfolio, {m}", tags)


# ---------------------------------------------------------------------------------------------------- manager statements
def statement_pdf(w, s):
    f = s["fund"]; m = mgr(f); pe = d(s["period"]); start = pe.replace(day=1) if FUND[f]["statement_frequency"] == "monthly" else (pe - dt.timedelta(days=89)).replace(day=1)
    calls = sum((c["amount"] for c in w.calls if c["fund"] == f and start.isoformat() <= c["due"] <= s["period"]), D(0))
    dist = sum((x["amount"] for x in w.dists if x["fund"] == f and start.isoformat() <= x["pay"] <= s["period"]), D(0))
    prior = [t for t in w.stmts if t["fund"] == f and t["period"] < s["period"] and t["value"] is not None and t["kind"] != "amended"]
    opening = max(prior, key=lambda t: t["period"])["value"] if prior else q2(s["value"] * D("0.97"))
    gain = s["value"] - opening - calls + dist
    L = [(m["name"].upper(), 1, 16), f"Investor Relations | {m['contact_email']} | Contact: {m['contact_name']}", "---",
         ("CAPITAL ACCOUNT STATEMENT" + (" - AMENDED" if s["kind"] == "amended" else " (ESTIMATE)" if s["kind"] == "estimate" else ""), 1, 13),
         f"Fund: {pname(f)}", f"Limited partner: {ENT[FUND[f]['legal_entity']]}   Administrator investor code: {acode(f)}"]
    if s["title"]: L.append(f"Title: {s['title']}")
    L += [f"Statement date (period end): {dlong(pe)}", f"Issued: {dlong(s['received'])}", f"Status: {s['kind'].title()}", "---",
          ("Capital account roll-forward (USD)", 1), f"Opening balance                {money(opening)}", f"Contributions (capital calls)  {money(calls)}", f"Distributions                  {money(dist)}",
          f"Net gain / (loss)              {money(gain)}", (f"Closing capital account balance  {money(s['value'])}", 1, 12), "---"]
    if f in TERMS:
        com, bef = D(TERMS[f][0]), D(TERMS[f][1])
        called = bef + sum((c["amount"] for c in w.calls if c["fund"] == f and c["due"] <= s["period"] and c["id"] != "CALL-C-7"), D(0))
        L += [f"Total commitment {money(com)}", f"Cumulative contributions called {money(called)}", f"Remaining uncalled commitment {money(com - called)}", "---"]
    if s["note"]: L += [f"Note: {s['note']}"]
    L += [f"{m['name']} - synthetic document for test purposes only"]
    return L


def manager_statements(w, R):
    for s in w.stmts:
        if not s["received"] or s["value"] is None: continue
        f = s["fund"]; fn = f"{mgr(f)['name'].split()[0].lower()}_{f}_{s['period']}_{s['kind']}.pdf"
        p = R.path(s["received"][:7], "manager_statements", fn); L = statement_pdf(w, s); write_pdf(p, fn, L)
        tags = []
        if (f, s["period"], s["kind"]) == ("A", "2026-09-30", "amended"): tags = ["M03"]
        if (f, s["period"], s["kind"]) in (("C", "2026-06-30", "amended"), ("H1", "2026-07-31", "amended")): tags = ["M03"]
        if s["kind"] != "amended" and d(s["due"]) < d(s["received"]): tags.append("M01")
        R.add(p, "manager_statements", s["received"][:7], f"{pname(f)} {s['kind']} statement as at {s['period']}, value {money(s['value'])}, received {s['received']}", tags)
        recv(R, p, "manager_statement", s["period"], d(s["due"]), d(s["received"]), "late" if "M01" in tags else "received")
        subj = f"{pname(f)} - statement as at {dlong(s['period'])} ({s['kind']})"
        body = f"Dear Evergreen Office team,\n\nPlease find attached the {s['kind']} statement for {pname(f)} as at {dlong(s['period'])}.\n\nKind regards,\n{mgr(f)['contact_name']}\n{mgr(f)['name']}"
        write_eml(R.path(s["received"][:7], "emails", f"{s['received']}_stmt_{f}_{s['period']}_{s['kind']}.eml"), f"{mgr(f)['contact_name']} <{mgr(f)['contact_email']}>", f"Helen Foo <{OPS}>", subj,
                  dt.datetime.fromisoformat(s["rts"].replace("Z", "")), body, f"stmt-{f}-{s['period']}-{s['kind']}", attach=(fn, p.read_bytes()))
        R.add(R.path(s["received"][:7], "emails", f"{s['received']}_stmt_{f}_{s['period']}_{s['kind']}.eml"), "emails", s["received"][:7], f"Delivery email with the {pname(f)} {s['kind']} statement as at {s['period']}", tags)
    for s in w.stmts:
        if s["value"] is None and s["status"] == "missing":
            mess("M02", "statement missing", f"manager_statements (none)", f"{pname(s['fund'])} statement as at {s['period']} was due {s['due']} and never arrives")
            RECV.append([f"(missing) manager_statements/{s['fund']}_{s['period']}", "manager_statement", s["period"], s["due"], "", "never received"])
    mess("M01", "statement late", "manager_statements / emails", "Fund D 31 Mar statement 5 business days late; Fund E 30 Jun 8 days late; Fund H2 31 Aug 6 days late; Fund K 30 Jun 2 business days late (see received_log_all.csv)")
    mess("M03", "statement amended", "manager_statements", "Fund A 30 Sep amended (10,000,000 -> 10,180,000); Fund C 30 Jun amended (8,420,000 -> 8,275,000); Fund H1 31 Jul amended (7,050,000 -> 7,012,500)")


# ---------------------------------------------------------------------------------------------------- capital call and distribution notices
def notices(w, R):
    for c in w.calls:
        f, m = c["fund"], mgr(c["fund"]); seq = c["no"]; nd = d(c["notice"]); ref = f"{m['id'][4:8]}/{nd.year}/{seq:03d}"
        bank_name = "Harbour Bank (synthetic)" if c["changed"] else "Merchant Trust Bank (synthetic)"
        feepct = (c["fee"] / c["commit"] * 100) if c["fee"] else D(0)
        L = [(m["name"].upper(), 1, 16), f"Investor Relations | {m['contact_email']} | Contact: {m['contact_name']}", "---",
             ("CAPITAL CALL NOTICE", 1, 14), f"Notice ref: {ref}", f"Date of notice: {dlong(nd)}", (f"Payment due date: {dlong(c['due'])}", 1), "---",
             f"To: {ENT[c['ent']]} (limited partner)", f"Fund: {pname(f)}", f"Administrator investor code: {acode(f)}", "---",
             (f"Amount to be paid by the investor   USD {money(c['amount'])}", 1, 12), ("Purpose of this call", 1),
             f"  New investments                USD {money(c['invest'])}", f"  Management fee ({feepct.normalize():f}% of commitment)   USD {money(c['fee'])}" if c["fee"] else "  Management fee                 none in this call", "---",
             ("Commitment summary (after this notice)", 1), f"  Total commitment                 USD {money(c['commit'])}", f"  Cumulative contributions called  USD {money(c['cum'])}",
             f"  Remaining uncalled commitment    USD {money(c['commit'] - c['cum'])}", "---", ("Payment instructions", 1),
             f"  Beneficiary: {pname(f)} Fund Account", f"  Bank: {bank_name}", f"  Account: SYN-0000-{c['acct']}", f"  Reference: {ref} / {ENT[c['ent']]}", "---",
             "This notice is issued under the limited partnership agreement. Late payment may incur default interest.", f"{m['name']} - synthetic document for test purposes only"]
        p = R.path(ym(nd), "notices", f"{nd}_{f}_call{seq}.pdf"); write_pdf(p, p.name, L)
        tags = ["M05a"] if c["changed"] else (["M08"] if c["id"] == "CALL-G-3" else [])
        R.add(p, "notices", ym(nd), f"Capital call notice No. {seq}, {pname(f)}, {ENT[c['ent']]}, USD {money(c['amount'])}, due {c['due']}, account ending {c['acct']}", tags)
        when = dt.datetime(nd.year, nd.month, nd.day, 9, 12 if c["changed"] else 5)
        e = R.path(ym(nd), "emails", f"{nd}_call_{f}_{seq}.eml")
        write_eml(e, f"{m['contact_name']} <{m['contact_email']}>", f"Operations <{OPS}>", f"{pname(f)}, Capital Call Notice No. {seq}", when,
                  f"Dear Investor,\n\nPlease find attached Capital Call Notice No. {seq} for {pname(f)}. Amount USD {money(c['amount'])}, due {dlong(c['due'])}.\n\nKind regards,\n{m['name']}", f"call-{f}-{seq}", attach=(p.name, p.read_bytes()))
        R.add(e, "emails", ym(nd), f"Email delivering capital call notice No. {seq} of {pname(f)}", tags)
    mess("M05a", "changed bank account", "notices/2026-10-13_C_call7.pdf", "Cedarpoint Ventures III call 7 asks for account ending 4471; calls 5 and 6 and the standing instructions say 2209 (call-back needed)")
    mess("M08", "fee above terms", "notices/2026-06-10_G_call3.pdf", "Evergreen Credit III call 3 charges a management fee of 28,125.00 (0.5625% of commitment); fund terms say 0.375% = 18,750.00 (excess 9,375.00)")
    for x in w.dists:
        f, m = x["fund"], mgr(x["fund"]); nd = d(x["notice"]); us = f == "K"
        fmt = (lambda y: d(y).strftime("%m/%d/%Y")) if us else (lambda y: dlong(y))
        L = [(m["name"].upper(), 1, 16), f"Investor Relations | {m['contact_email']}", "---", ("DISTRIBUTION NOTICE", 1, 14), f"Date of notice: {fmt(x['notice'])}", (f"Payment value date: {fmt(x['pay'])}", 1),
             f"To: {ENT[x['ent']]}", f"Fund: {pname(f)}", f"Administrator investor code: {acode(f)}", "---", (f"Amount to be paid to the investor   USD {money(x['amount'])}", 1, 12),
             f"Nature: {'income distribution' if x['kind'] == 'income' else 'return of capital'}", "---", f"{m['name']} - synthetic document for test purposes only"]
        p = R.path(ym(nd), "notices", f"{nd}_{f}_distribution.pdf"); write_pdf(p, p.name, L)
        R.add(p, "notices", ym(nd), f"Distribution notice, {pname(f)}, {ENT[x['ent']]}, USD {money(x['amount'])}, paid {x['pay']}", ["M11b"] if us else [])
        e = R.path(ym(nd), "emails", f"{nd}_distribution_{f}.eml")
        write_eml(e, f"{m['contact_name']} <{m['contact_email']}>", f"Operations <{OPS}>", f"{pname(f)} - distribution notice", dt.datetime(nd.year, nd.month, nd.day, 10, 0),
                  f"Please find attached the distribution notice for {pname(f)}.", f"dist-{f}-{x['notice']}", attach=(p.name, p.read_bytes()))
        R.add(e, "emails", ym(nd), f"Email delivering the distribution notice of {pname(f)}")
    mess("M11b", "date format", "notices/2026-09-10_K_distribution.pdf", "Dates are written mm/dd/yyyy (09/24/2026) while every other notice writes 24 September 2026")


# ---------------------------------------------------------------------------------------------------- trading and fx
TRADE_HDR = ["external_trade_id", "trade_date", "settle_date", "portfolio", "side", "instrument_code", "instrument_name", "instrument_type", "quantity", "price", "amount", "currency", "counterparty", "status", "source_system"]


def trading(w, R):
    by = {}
    for t in w.trades:
        s = w.sec[t["sec"]]; row = [t["id"], t["trade"].isoformat(), t["settle"].isoformat(), "EG-LIQUID", t["side"], s["identifiers"]["trading_export"]["ticker"], s["canonical_name"], s["instrument_type"],
                                    float(t["qty"]), float(t["price"]), float(t["amt"]), "USD", "Synthetic Broker One", "executed", "OMS-SYN"]
        by.setdefault(t["trade"], []).append(row)
        if t["dup"]: by[t["trade"]].append([t["id"] + "-R"] + row[1:])
    for c in w.convs:
        by.setdefault(c["date"], []).append([f"FX-{c['id']}", c["date"].isoformat(), add_bd(c["date"], 2).isoformat(), {"EG-HOLD": "EG-GROWTH", "EG-TRUST": "EG-LIQUID", "EG-B": "EG-B-OPS"}[c["ent"]],
                                              "buy", "USDSGD", "USD/SGD spot", "fx_spot", float(c["usd"]), float(c["rate"]), float(c["sgd"]), "SGD", "Harbour Bank FX desk", "executed", "OMS-SYN"])
    for fx in U["fx_forwards"]:
        td = d(fx["trade_date"])
        by.setdefault(td, []).append([fx["id"], fx["trade_date"], fx["value_date"], fx["portfolio"], "sell USD / buy SGD", fx["id"], "USD/SGD forward", "fx_forward", float(fx["sell_amount"]),
                                      float(fx["contract_rate"]), float(fx["buy_amount"]), "SGD", fx["counterparty"], "executed", "OMS-SYN"])
    for x, rows in sorted(by.items()):
        p = R.path(ym(x), "trading_export", f"trading_export_{x:%Y%m%d}.csv"); write_csv(p, TRADE_HDR, rows)
        tags = []
        if any(r[0].endswith("-R") for r in rows): tags.append("M07")
        if any(r[4] == "sell USD / buy SGD" for r in rows): tags.append("M10")
        R.add(p, "trading_export", ym(x), f"Trading desk (OMS) export for {x}: {len(rows)} row(s)", tags)
    dup = next(t for t in w.trades if t["dup"])
    mess("M07", "trade booked twice", f"trading_export/trading_export_{dup['trade']:%Y%m%d}.csv", f"Trade {dup['id']} ({dup['side']} {dup['qty']:,.0f} {dup['sec']}) appears twice (second row id {dup['id']}-R); the custodian and administrator hold it once")
    mess("M10", "fx side text", "trading_export/trading_export_20260915.csv and _20261005.csv", "FX forward rows carry side 'sell USD / buy SGD' instead of buy/sell of an instrument")
    for m in months("2026-04", "2026-09") + ["2026-10"]:
        pm = {"EG-HOLD": "EG-GROWTH", "EG-TRUST": "EG-LIQUID", "EG-B": "EG-B-OPS"}
        rows = [[t["oms"].isoformat(), t["ref"], ACCT[t["acct"]]["ent"], pm[ACCT[t["acct"]]["ent"]], t["typ"], t["desc"], t["cpty"], float(t["amt"]), ACCT[t["acct"]]["ccy"], "OMS-SYN"]
                for t in sorted(w.tx, key=lambda t: (t["oms"], t["n"])) if ym(t["oms"]) == m and t["typ"] not in ("bank_fee", "interest")]
        arr = arrive(m, 1) if m != "2026-10" else END
        p = R.path(ym(arr), "trading_export", f"cash_movements_{m}{'_mtd' if m == '2026-10' else ''}.csv")
        write_csv(p, ["value_date", "reference", "legal_entity", "portfolio", "movement_type", "description", "counterparty", "amount", "currency", "source_system"], rows)
        R.add(p, "trading_export", ym(arr), f"Trading desk cash movements as the desk booked them, {m}", ["M04"] if m in ("2026-06", "2026-10") else [])
    mess("M04", "cash break", "administrator_cash / bank_statements / trading_export cash_movements",
         "Entity B USD 8 Oct: bank 868,000.00 vs administrator 880,400.00 (administrator books the 12,400.00 legal fee wire on 9 Oct), over the 5,000 tolerance; Trust USD 17 Jun: 6,200.00 fee booked by the administrator a day late; Trust 8 Oct: desk 1,148,200.00 vs 1,150,000.00 (1,800.00, inside tolerance)")


def fx_files(w, R):
    for x in sorted(w.fx):
        if x < START or not is_bd(x): continue
        if x == d("2026-06-03"):
            mess("M14", "fx rate gap", "fx_rates/fx_usdsgd_20260603.csv (missing)", "No FX rate file for 3 June 2026 although it was a business day"); continue
        p = R.path(ym(x), "fx_rates", f"fx_usdsgd_{x:%Y%m%d}.csv")
        write_csv(p, ["Date", "Pair", "Fixing", "Rate (SGD per 1 USD)", "Source"], [[x.isoformat(), "USD/SGD", "WMR 4pm", str(w.fx[x]), "Synthetic FX fixing"]])
        R.add(p, "fx_rates", ym(x), f"USD/SGD WMR 4pm fixing for {x}", ["M14"] if x == d("2026-06-02") else [])
    for m in months("2026-04", "2026-09") + ["2026-10"]:
        rows = [[x, str(w.idx[x.isoformat()][0]), str(w.idx[x.isoformat()][1]), "USD", "Synthetic Index Services - end of day"] for x in DAYS if ym(x) == m]
        p = R.path(m, "index_levels", f"index_levels_{m}.csv"); write_csv(p, ["Date", "Global Equity Index (synthetic)", "Global Bond Index (synthetic)", "Currency", "Source"], [[r[0].isoformat()] + r[1:] for r in rows])
        R.add(p, "index_levels", m, f"Daily levels of the two synthetic indices, {m}")
    for c in w.convs:
        if not c["confirm"]:
            mess("M09", "missing fx confirmation", f"fx_confirmations (none for {c['id']})", f"Spot conversion {c['id']} (USD {money(c['usd'])} at {c['rate']}) has a bank entry, a trading row and no confirmation PDF"); continue
        L = [("HARBOUR BANK (SYNTHETIC)", 1, 16), "Global Markets Operations | Confirmations Desk | confirmations@harbourbank.example", "---", ("FX SPOT TRADE CONFIRMATION", 1, 13),
             f"Confirmation reference: HB{c['id'].replace('FXS-', '').replace('-', '')}", f"Trade date: {c['date']}   Value date: {add_bd(c['date'], 0)}", f"Client: {ENT[c['ent']]}",
             f"Client sells: SGD {money(c['sgd'])}", f"Client buys: USD {money(c['usd'])}", f"Rate (SGD per USD): {c['rate']}", "---", "Synthetic document for test purposes only"]
        p = R.path(ym(c["date"]), "fx_confirmations", f"{c['id']}_confirmation.pdf"); write_pdf(p, p.name, L)
        R.add(p, "fx_confirmations", ym(c["date"]), f"Bank confirmation of the {c['ent']} spot conversion {c['id']}: USD {money(c['usd'])} at {c['rate']}")
    for fx in U["fx_forwards"]:
        buy = fx.get("confirmation_buy_amount", fx["buy_amount"])
        L = [("HARBOUR BANK (SYNTHETIC)", 1, 16), "Global Markets Operations | Confirmations Desk", "---", ("FX FORWARD TRADE CONFIRMATION", 1, 13), f"Our ref (client): {fx['id']}   Trade date: {fx['trade_date']}   Value date: {fx['value_date']}",
             f"Client: Evergreen Family Trust (portfolio {fx['portfolio']})", f"Client sells: USD {money(fx['sell_amount'])}", f"Client buys: SGD {money(buy)}", f"Forward rate (SGD per USD): {fx['confirmation_rate']}", "---", "Synthetic document for test purposes only"]
        td = d(fx["trade_date"]); p = R.path(ym(td), "fx_confirmations", f"{fx['id']}_confirmation.pdf"); write_pdf(p, p.name, L)
        R.add(p, "fx_confirmations", ym(td), f"Bank confirmation of FX forward {fx['id']}: sell USD {money(fx['sell_amount'])}, rate {fx['confirmation_rate']}", ["M16"] if fx["confirmation_status"] == "mismatch" else [])
    mess("M16", "trade breaks (October)", "trading_export 2026-10 / administrator_trades_2026-10.csv / fx_confirmations", "NWL buy 12,000 vs administrator 10,200; HVS sell 5,000 missing at the administrator; FX forward FXF-2026-002 confirmed at 1.3452 vs booked 1.3425 (SGD 8,100.00)")


# ---------------------------------------------------------------------------------------------------- vendors, people, property
def vendors(w, R):
    for i in w.invoices:
        if i["date"] > END: continue
        L = [(i["vendor"].upper(), 1, 16), "Synthetic vendor - for test purposes only", "---", ("INVOICE", 1, 14), f"Invoice no: {i['no']}", f"Invoice date: {dlong(i['date'])}", f"Due date: {dlong(i['due'])}",
             f"Bill to: {ENT['EG-HOLD']}", "---", f"Description: {i['desc']}", (f"Amount due: {i['ccy']} {money(i['amt'])}", 1, 12), "---", f"Pay to account ending {i['acct_end']} at Harbour Bank (synthetic)"]
        if i["changed"]: L += [("NOTICE: our bank details have changed. Please use the account above (ending %s) from this invoice onward." % i["acct_end"], 1)]
        if i["dup"]: L += ["REMINDER COPY - second sending of this invoice"]
        p = R.path(ym(i["date"]), "invoices", f"{i['date']}_{i['vendor'].split()[0].lower()}_{i['no']}{'_copy' if i['dup'] else ''}.pdf"); write_pdf(p, p.name, L)
        R.add(p, "invoices", ym(i["date"]), f"Invoice {i['no']} from {i['vendor']}, {i['ccy']} {money(i['amt'])}", ["M06"] if i["dup"] else ["M05b"] if i["changed"] else [])
    mess("M06", "duplicate invoice", "invoices/2026-06-24_orchard_INV-OIT-2606_copy.pdf", "Orchard IT Services invoice INV-OIT-2606 (SGD 2,950.00) arrives twice: 3 June and again 24 June; paid once")
    mess("M05b", "changed bank account", "invoices/2026-08-28_lakeside_LL-2026-0828.pdf", "Lakeside Legal LLP invoice names an account ending 6029; the vendor master and earlier payments use 3047")
    bad = next(i for i in w.invoices if i["changed"])
    write_eml(R.path(ym(bad["date"]), "emails", f"{bad['date']}_lakeside_new_bank_details.eml"), "Accounts <accounts@lakeside-legal.example.test>", f"Operations <{OPS}>", "Invoice LL-2026-0828 and our new bank details",
              dt.datetime(2026, 8, 28, 8, 40), "Dear team,\n\nInvoice LL-2026-0828 is attached. Please note we have moved our client account; use the account ending 6029 from now on.\n\nLakeside Legal LLP", "lakeside-newbank")
    R.add(R.path(ym(bad["date"]), "emails", f"{bad['date']}_lakeside_new_bank_details.eml"), "emails", ym(bad["date"]), "Vendor email announcing new bank details", ["M05b"])


def people_and_property(w, R):
    for p in w.payroll:
        p_ = R.path(p["month"], "payroll", f"payroll_{p['month']}.xlsx")
        write_xlsx(p_, {"Payroll": [["Employee", "Title", "Gross (SGD)", "Employee CPF (20%)", "Net pay (SGD)", "Employer CPF (17%)", "Pay date"]] +
                        [[r[0], r[1], float(r[2]), float(q2(r[2] * D("0.20"))), float(r[3]), float(r[4]), p["date"].isoformat()] for r in p["rows"]] +
                        [["Total", "", float(p["gross"]), float(sum((q2(r[2] * D("0.20")) for r in p["rows"]), D(0))), float(p["net"]), float(sum((r[4] for r in p["rows"]), D(0))), ""]]})
        R.add(p_, "payroll", p["month"], f"Monthly payroll of Evergreen Holdings, {p['month']}: 9 employees, gross {money(p['gross'])} SGD, net {money(p['net'])} SGD")
    for pol in w.policies:
        if pol["notice"] > END: continue
        L = [("SAFEHARBOUR INSURANCE BROKERS (SYNTHETIC)", 1, 14), "---", ("RENEWAL NOTICE", 1, 14), f"Policy: {pol['id']}  {pol['name']}", f"Renewal date: {dlong(pol['renewal'])}", f"Notice date: {dlong(pol['notice'])}",
             f"Expiring premium: {pol['ccy']} {money(pol['prior'])}", (f"Renewal premium: {pol['ccy']} {money(pol['premium'])}", 1), f"Change: {((pol['premium'] / pol['prior']) - 1) * 100:.1f}%", "---", "Synthetic document for test purposes only"]
        p = R.path(ym(pol["notice"]), "insurance", f"{pol['notice']}_{pol['id']}_renewal.pdf"); write_pdf(p, p.name, L)
        R.add(p, "insurance", ym(pol["notice"]), f"Renewal notice for {pol['id']} ({pol['name']}), premium {pol['ccy']} {money(pol['premium'])}, renews {pol['renewal']}")
    for b in w.props:
        if b["date"] > END: continue
        L = [(b["prop"].upper() + " - MANAGING AGENT (SYNTHETIC)", 1, 14), "---", ("PROPERTY STATEMENT AND BILL", 1, 13), f"Bill no: {b['id']}", f"Month: {b['month']}", f"Due: {dlong(b['due'])}", "---"]
        L += [f"{n}: SGD {money(a)}" for n, a in b["items"]] + ["---", (f"Total due: SGD {money(b['total'])}", 1, 12)]
        p = R.path(ym(b["date"]), "property_bills", f"{b['date']}_{b['id']}.pdf"); write_pdf(p, p.name, L)
        R.add(p, "property_bills", ym(b["date"]), f"Property bill {b['id']} for {b['prop']}, SGD {money(b['total'])}")


# ---------------------------------------------------------------------------------------------------- notes and emails
def notes_and_mail(w, R):
    src = ROOT / "tests/v1/fixtures/10uc/notes"
    for f in sorted(src.glob("0*.md")):
        day = d(f.stem[-10:])
        if START <= day <= END:
            p = R.path(ym(day), "meeting_notes", f.name); copy_lf(f, p)
            R.add(p, "meeting_notes", ym(day), "Meeting note (reused from the 10-use-case set): " + f.stem[3:-11].replace("_", " "))
    ic = [("2026-04-15", "Call 5 of Cedarpoint Ventures III (USD 1,000,000, due 21 April) is within the commitment. Daniel Foo approves the funding by converting SGD."),
          ("2026-05-20", "Entity B call from Saltmarsh Infrastructure Fund II approved (USD 600,000). Raj Patel asks for a weekly cash view per entity."),
          ("2026-06-17", "Fund A call 11 (USD 500,000) paid. Tom Hale reminds the committee that Harborview Semiconductor must stay below the 5 percent single-name limit, and proposes raising the limit of the liquid book to 6 percent; the proposal goes to Daniel Foo to sign."),
          ("2026-07-15", "Call 6 of Cedarpoint Ventures III (USD 1,500,000) paid. Grace Ong to chase Cedarpoint Opportunities II for the missing 30 June statement."),
          ("2026-08-19", "Trust lends Holdings USD 600,000 (IC-2026-08-01) for the Evergreen Growth II call. Approval record to be filed.")]
    for day, text in ic:
        x = d(day); p = R.path(ym(x), "meeting_notes", f"ic_note_{day}.md")
        p.write_text(f"# Investment committee note, {dlong(x)}\n\n| | |\n|---|---|\n| Chair | Raj Patel (Chief Investment Officer) |\n| Present | Daniel Foo, Mei Chen, Grace Ong, Tom Hale |\n\n## Decisions\n- {text}\n\n## Actions\n- [ ] Grace Ong: file the payment records by Friday\n- [ ] Helen Foo: update the commitments register\n- [x] Daniel Foo: approve payments over 500,000\n", encoding="utf-8", newline="\n")
        R.add(p, "meeting_notes", ym(x), f"Investment committee note {day} (generated)")
    d_stmt = next(s for s in w.stmts if s["fund"] == "D" and s["status"] == "missing")
    for day, who, subj, body in [("2026-07-28", "Helen Foo", "Cedarpoint Opportunities II - 30 June statement", "Dear Hana,\n\nWe have not yet received the 30 June 2026 statement for Cedarpoint Opportunities II (due 14 July). Could you send it this week?\n\nHelen"),
                                 ("2026-09-01", "Helen Foo", "Reminder: Cedarpoint Opportunities II - 30 June statement", "Dear Hana,\n\nSecond reminder: the 30 June 2026 statement is still missing, now more than 30 business days overdue.\n\nHelen"),
                                 ("2026-06-16", "Helen Foo", "Harbour Bank: May statement for Evergreen Family Trust SGD", "Dear Harbour Bank,\n\nThe May statement for the Family Trust SGD account has not arrived.\n\nHelen"),
                                 ("2026-08-07", "Helen Foo", "Tidewater: July statement for Entity B USD", "Dear Tidewater,\n\nThe July 2026 statement for the Entity B USD account has not arrived. Please resend.\n\nHelen")]:
        x = d(day); p = R.path(ym(x), "emails", f"{day}_chase_{subj.split()[0].lower().strip(':')}_{day[5:7]}.eml")
        write_eml(p, f"{who} <helen.foo.evergreen@example.test>", "Counterparty <ops@counterparty.example.test>", subj, dt.datetime(x.year, x.month, x.day, 9, 30), body, f"chase-{day}")
        R.add(p, "emails", ym(x), f"Chase email: {subj}")
    for day, frm, to, subj, body in [("2026-05-04", "Daniel Foo", "Mei Chen", "Approval record: Saltmarsh call 4", "Mei, approved USD 600,000 to Saltmarsh. Daniel"), ("2026-08-04", "Helen Foo", "Daniel Foo", "Fund F call 2: USD 600,000 due 18 Aug",
                                     "Daniel, call 2 of Evergreen Growth II is USD 600,000. Holdings USD is short; can the Trust lend 600,000 (IC-2026-08-01)? Helen"),
                                     ("2026-10-13", "Sam Lee", "Helen Foo", "New Cedarpoint call 7, new account", "Helen, the Cedarpoint call 7 notice came in this morning for USD 1,250,000, but the account ends 4471, not 2209. Sam")]:
        x = d(day); p = R.path(ym(x), "emails", f"{day}_internal_{frm.split()[0].lower()}.eml")
        write_eml(p, f"{frm} <{frm.lower().replace(' ', '.')}.evergreen@example.test>", f"{to} <{to.lower().replace(' ', '.')}.evergreen@example.test>", subj, dt.datetime(x.year, x.month, x.day, 14, 0), body, f"int-{day}")
        R.add(p, "emails", ym(x), f"Internal email: {subj}")


# ---------------------------------------------------------------------------------------------------- reports, loans, approvals, reference
def report_lines(w, m):
    me = month_end(m); issue = dt.date(me.year + (me.month == 12), me.month % 12 + 1, 3); cut = f"{issue}T10:00:00Z"
    lines = []
    for f, lab in (("A", pname("A")), ("B", pname("B"))):
        k = w.known(f, me.isoformat(), cut); lines.append((lab, k["value"], "estimated" if k["kind"] == "estimate" else "official"))
    lines.append(("Evergreen Liquid Book", w.book(me), "official"))
    tot = sum((x[1] for x in lines), D(0)); return issue, lines, tot, q2(tot * w.fx[me])


def reports(w, R):
    for m in months("2026-04", "2026-09"):
        issue, lines, tot, sgd = report_lines(w, m)
        st = "estimated" if any(x[2] == "estimated" for x in lines) else "official"
        rows = [["Line", "Value (USD)", "Status"]] + [[a, float(b), c] for a, b, c in lines] + [["Total", float(tot), st], ["Total (SGD) at WMR 4pm", float(sgd), ""]]
        p = R.path(ym(issue), "investment_reports", f"Evergreen_Office_Investment_Report_{m}.xlsx"); write_xlsx(p, {"Report": rows})
        R.add(p, "investment_reports", ym(issue), f"Monthly investment report as at {m}, issued {issue}: total USD {money(tot)}")
        L = [("EVERGREEN OFFICE - MONTHLY INVESTMENT REPORT", 1, 14), f"Period end: {month_end(m)}   Issued: {issue} 10:30 UTC   Approved by Daniel Foo", "---"] + [f"{a:34s} {money(b):>18s} USD  ({c})" for a, b, c in lines] + \
            ["---", (f"Total {money(tot)} USD ({st})", 1), f"Total in SGD at WMR 4pm {w.fx[month_end(m)]}: {money(sgd)}", "Synthetic document for test purposes only"]
        p = R.path(ym(issue), "investment_reports", f"Evergreen_Office_Investment_Report_{m}.pdf"); write_pdf(p, p.name, L)
        R.add(p, "investment_reports", ym(issue), f"Monthly investment report as at {m} (PDF)")


def loans(w, R):
    for r in w.loan:
        arr = add_bd(month_end(r["month"]), 3)
        rows = [["Facility", "Month", "Opening principal", "Interest charged", "Principal repaid", "Closing principal"], ["TL-B-01 (Harbour Bank, Entity B)", r["month"], float(-r["open"]), float(-r["interest"]), float(-r["principal"]), float(-r["close"])]]
        p = R.path(ym(arr), "loan_statements", f"loan_statement_TL-B-01_{r['month']}.xlsx"); write_xlsx(p, {"Loan": rows})
        R.add(p, "loan_statements", ym(arr), f"Term loan TL-B-01 statement {r['month']}: closing principal shown as -{money(r['close'])}", ["M12"])
    mess("M12", "negative sign for loans", "loan_statements", "The loan statements show principal, interest and repayments as negative numbers (closing -2,800,000.00 at 30 Sep); bank statements show the repayment debit as negative too, the administrator would show the loan as positive")


def approvals(w, R):
    for m in months("2026-04", "2026-10"):
        rows = [[a["ref"], a["ent"], a["date"].isoformat(), float(a["usd"]), a["payee"], "Sam Lee", a["approved_by"], (a["date"] - dt.timedelta(days=1)).isoformat() if a["approved"] else ""] for a in w.approvals if ym(a["date"]) == m]
        if not rows: continue
        p = R.path(m, "approvals", f"approvals_{m}.csv"); write_csv(p, ["payment_ref", "entity", "payment_date", "amount_usd", "payee", "requested_by", "approved_by", "approved_on"], rows)
        R.add(p, "approvals", m, f"Approval log for payments over 500,000 USD, {m}", ["M13"] if any(not r[6] for r in rows) else [])
    mess("M13", "missing approval", "approvals/approvals_2026-08.csv", "The 600,000 USD payment of Evergreen Growth II call 2 (CC-CALL-F-2) has no approval on record")


def reference(w, R):
    ref = R.out / "reference"; ref.mkdir(parents=True, exist_ok=True)
    cb = {f: f"+65 6555 {1000 + i * 37:04d}" for i, f in enumerate(PRIVATE)}
    rows = [[f, pname(f), mgr(f)["name"], "Merchant Trust Bank (synthetic)", TERMS[f][4], "2026-04-07" if f == "C" else "2026-04-01", "Helen Foo", cb[f]] for f in PRIVATE]
    write_csv(ref / "standing_instructions.csv", ["fund_key", "fund", "manager", "bank", "account_last4", "confirmed_on", "confirmed_by", "callback_number"], rows)
    write_csv(ref / "fund_terms.csv", ["fund_key", "fund", "entity", "commitment_usd", "committed_on", "called_before_2026_04_01", "fee_pct_of_commitment_per_billing", "billing_months"],
              [[f, pname(f), FUND[f]["legal_entity"], TERMS[f][0], COMMIT_DATE[f], TERMS[f][1], TERMS[f][2], " ".join(map(str, TERMS[f][3]))] for f in PRIVATE])
    write_csv(ref / "vendor_master.csv", ["vendor", "category", "currency", "account_last4"], [list(v) for v in VENDORS])
    write_csv(ref / "accounts.csv", ["account_id", "bank", "entity", "currency", "account_number"], [[a, BANK[v["bank"]], ENT[v["ent"]], v["ccy"], v["no"]] for a, v in ACCT.items()])
    import json
    from .more import wave2_rules  # the rules of cards 51 to 100 (A48 onward); imported here because more imports this module
    write_csv(ref / "office_rules.csv", ["rule", "value", "text", "rule_type", "parameters", "approval_status", "version"], [[*r, "", "", "", ""] for r in [["approval_over_usd", 500000, "Payments over 500,000 need the Head of Finance's approval"], ["bank_detail_change", "call-back", "Changed bank details need a call-back on a known number before payment"],
              ["cash_buffer_usd", 250000, "Keep a 250,000 USD cash buffer per entity"], ["single_name_limit_pct", 5, "No single name above 5 percent of the liquid portfolio"], ["cash_tolerance_usd", 5000, "Daily cash may differ by up to 5,000 per entity before it is a break"]]]
              + [[c, v, t, k, json.dumps(p, sort_keys=True), s, n] for c, v, t, k, p, s, n in SIGNED_RULES + wave2_rules(w)])
    from .world import PEOPLE
    md = dict(office="Evergreen Office (synthetic)", period=["2026-04-01", "2026-10-13"], entities={k: v for k, v in ENT.items()},
              accounts={a: dict(bank=BANK[v["bank"]], entity=v["ent"], currency=v["ccy"], number=v["no"]) for a, v in ACCT.items()},
              funds={f: dict(name=pname(f), manager=mgr(f)["name"], entity=FUND[f]["legal_entity"], portfolio=FUND[f]["portfolio"], asset_class=FUND[f]["asset_class"], statement_frequency=FUND[f]["statement_frequency"],
                             **({"commitment_usd": TERMS[f][0], "called_before_2026_04_01": TERMS[f][1], "committed_on": COMMIT_DATE[f], "fee_pct_per_billing": TERMS[f][2], "billing_months": list(TERMS[f][3]), "standing_account_last4": TERMS[f][4]} if f in TERMS else {}))
                     for f in FUND}, people=[dict(name=n, title=t) for n, t, g in PEOPLE], rules=OFFICE_RULES)
    (ref / "master_data.json").write_text(json.dumps(md, indent=1, sort_keys=True, default=str) + chr(10), encoding="utf-8", newline="\n")
    for src in ["benchmark_workbook", "policy", "process_narrative", "research_docs", "security_master"]:
        for f in sorted((ROOT / "tests/v1/fixtures/10uc" / src).glob("*")):
            if f.name != "MANIFEST.md": copy_lf(f, ref / f.name)
    for f in sorted(ref.glob("*")): R.rows.append(dict(path=f.relative_to(R.out).as_posix(), kind="reference", month="reference", desc="Reference or policy file: " + f.stem.replace("_", " "), mess=["M05a"] if f.name == "standing_instructions.csv" else []))
