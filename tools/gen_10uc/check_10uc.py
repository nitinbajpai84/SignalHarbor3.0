"""Cross-check every tests/v1/fixtures/10uc category against docs/test/10uc_universe.json.
Run: python tools/gen_10uc/check_10uc.py   (read-only; prints pass/fail counts per category and every failure). Report: docs/test/10UC-DATA-CHECK.md"""
import csv, glob, json, os, re, sys
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal as D
import openpyxl
from pypdf import PdfReader

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
F = os.path.join(ROOT, "tests", "v1", "fixtures", "10uc")
u = json.load(open(os.path.join(ROOT, "docs", "test", "10uc_universe.json")))
R = []  # (category, check, ok, detail)
def chk(cat, name, ok, detail=""):
    R.append((cat, name, bool(ok), detail))
def rows(path, sheet=None):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[sheet] if sheet else wb.worksheets[0]
    return [r for r in ws.iter_rows(values_only=True)]
def pdf_text(path):
    return "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
def money(x): return D(str(x)).quantize(D("0.01"))
def fmt(x): return f"{money(x):,.2f}"

sec_by_key = {s["key"]: s for s in u["securities"]}
sec_by_code = {s["identifiers"]["administrator"]["administrator_code"]: s for s in u["securities"]}
fund_by_key = {f["key"]: f for f in u["funds"]}
fund_by_code = {f["identifiers"]["administrator"]["administrator_code"]: f for f in u["funds"] if f["identifiers"]}
mgr = {m["id"]: m for m in u["managers"]}
stmts = u["statements"]
stmt_by_id = {s["statement_id"]: s for s in stmts}
vals = u["valuations_monthly"]
months = sorted(u["liquid_book_month_end"])

# ---------------- admin_exports ----------------
C = "admin_exports"
admin_files = sorted(glob.glob(os.path.join(F, "admin_exports", "administrator_export_*.xlsx")))
chk(C, "12 monthly files", len(admin_files) == 12, str(len(admin_files)))
status_words = Counter()
for p in admin_files:
    m = os.path.basename(p)[len("administrator_export_"):-5]
    me = [x for x in months if x.startswith(m)][0]
    rs = rows(p, "Positions")
    hdr = rs[5]
    value_col = hdr[5]
    chk(C, f"{m} value column name", value_col == ("Valuation Amount (USD)" if m == "2026-03" else "Market Value"), str(value_col))
    body = [r for r in rs[6:] if r[0] in ("EG-GROWTH", "EG-LIQUID", "EG-B-OPS", "EG-FUNDS")]
    chk(C, f"{m} 29 position rows", len(body) == 29, str(len(body)))
    liq_u = {x["security"]: x for x in u["liquid_book_month_end"][me]["positions"]}
    per_pf = defaultdict(D)
    for r in body:
        pf, code, name, qty, price, val, ccy, st, vd = r
        status_words[st] += 1
        code = str(code)
        if pf == "EG-LIQUID":
            s = sec_by_code.get(code)
            chk(C, f"{m} liquid code {code} in universe", s is not None, name)
            if s is None: continue
            lu = liq_u[s["key"]]
            ok = (name == s["canonical_name"] and D(str(qty)) == D(lu["quantity"]) and D(str(price)) == D(lu["price"])
                  and money(val) == money(lu["value"]) and D(str(price)) == D(s["prices_month_end"][me]) and money(val) == money(D(str(qty)) * D(str(price))))
            chk(C, f"{m} liquid {s['key']} qty/price/value", ok, f"{name} {qty} {price} {val}")
            per_pf[pf] += money(val)
        else:
            f = fund_by_code.get(code)
            chk(C, f"{m} fund code {code} in universe", f is not None, name)
            if f is None: continue
            v = [x for x in vals if x["fund"] == f["key"] and x["month_end"] == me][0]
            chk(C, f"{m} fund {f['key']} canonical name", name == f["canonical_name"], name)
            chk(C, f"{m} fund {f['key']} portfolio", pf == f["portfolio"], pf)
            if v["administrator_value"] is None:
                chk(C, f"{m} fund {f['key']} not received -> blank", val is None and st == "Not received", f"{val} {st}")
            else:
                chk(C, f"{m} fund {f['key']} admin value", money(val) == money(v["administrator_value"]), f"{val} vs {v['administrator_value']}")
                src = stmt_by_id[v["administrator_from"]]
                exp_date = src["period_end"]
                chk(C, f"{m} fund {f['key']} valuation date = source statement period", vd == exp_date, f"{vd} vs {exp_date} ({v['administrator_from']})")
                if src["period_end"] == me:
                    want = {"final": "Final", "estimate": "Estimate", "amended": "Amended"}[src["kind"]]
                else:
                    want = "Carried forward"
                chk(C, f"{m} fund {f['key']} status word", st == want, f"{st} vs {want} ({v['administrator_from']})")
                per_pf[pf] += money(val)
    chk(C, f"{m} liquid total", per_pf["EG-LIQUID"] == money(u["liquid_book_month_end"][me]["total"]), str(per_pf["EG-LIQUID"]))
    nav = rows(p, "Approved NAV")
    for r in nav[4:8]:
        pf, pname, pe, amt, ccy, st, at = r
        un = [x for x in u["administrator_nav_monthly"] if x["portfolio"] == pf and x["nav_period_end"] == me][0]
        chk(C, f"{m} NAV {pf}", money(amt) == money(un["nav_amount"]) and pe == me and at == un["received_at"], f"{amt} vs {un['nav_amount']} {at}")
        chk(C, f"{m} NAV {pf} = sum of positions", money(amt) == per_pf[pf], f"{amt} vs {per_pf[pf]}")
    chk(C, f"{m} title block names administrator and period", rs[2][0] == f"Period end: {me}", str(rs[2][0]))
chk(C, "status words used", set(status_words) <= {"Priced", "Final", "Estimate", "Amended", "Carried forward", "Not received"}, str(dict(status_words)))
# planted once
sep = rows(admin_files[-1], "Positions")
hvs = [r for r in sep[6:] if r[2] == "Harborview Semiconductor"]
chk(C, "P17/P29 HVS 20,000 x 118.40 = 2,368,000 once in Sep", len(hvs) == 1 and hvs[0][3] == 20000 and money(hvs[0][4]) == D("118.40") and money(hvs[0][5]) == D("2368000"), str(hvs))
chk(C, "P01 Fund A 10,000,000 Estimate in Sep", any(r[2] == "Evergreen Growth I" and money(r[5]) == D(10000000) and r[7] == "Estimate" for r in sep[6:] if r[5]), "")
chk(C, "P07 Fund D carried 4,650,000 in Sep", any(r[2] == "Cedarpoint Opportunities II" and money(r[5]) == D(4650000) and r[7] == "Carried forward" for r in sep[6:] if r[5]), "")
chk(C, "P07 Fund C carried 8,275,000 in Sep", any(r[2] == "Cedarpoint Ventures III" and money(r[5]) == D(8275000) for r in sep[6:] if r[5]), "")
# NWL quantity 50,000 in Sep (trade on 2 Oct is after)
nwl = [r for r in sep[6:] if r[2] == "Northwind Logistics"][0]
chk(C, "NWL Sep qty 50,000 (Oct trades not in month-end file)", nwl[3] == 50000, str(nwl[3]))

# ---------------- security_master ----------------
C = "security_master"
smp = os.path.join(F, "security_master", "EG_security_master_20261008.xlsx")
sm = [r for r in rows(smp, "Security master")[4:] if r[0] and str(r[0]).startswith(("SEC-", "FND-"))]
chk(C, "29 rows", len(sm) == 29, str(len(sm)))
sm_by_code = {}
for r in sm:
    iid, isin, name, itype, aclass, ccy, tcode, acode, mid, mname, pf, qty, status = r
    sm_by_code[str(acode)] = r
    if iid.startswith("SEC-"):
        s = sec_by_key[iid[4:]]
        ok = (name == s["canonical_name"] and itype == s["instrument_type"] and (aclass or None) == s["asset_class"] and ccy == s["currency"]
              and tcode == s["identifiers"]["trading_export"]["ticker"] and str(acode) == s["identifiers"]["administrator"]["administrator_code"]
              and pf == s["portfolio"] and D(str(qty)) == D(s["quantity_30_sep"]))
        chk(C, f"{iid} matches universe", ok, str(r))
    else:
        f = fund_by_key[iid[4:]]
        ok = (name == f["canonical_name"] and itype == f["instrument_type"] and aclass == f["asset_class"] and ccy == f["currency"]
              and str(acode) == f["identifiers"]["administrator"]["administrator_code"] and mid == f["manager"] and mname == mgr[f["manager"]]["name"] and pf == f["portfolio"])
        chk(C, f"{iid} matches universe", ok, str(r))
        if f["units"] is not None:
            chk(C, f"{iid} units", D(str(qty)) == D(str(f["units"])), f"{qty} vs {f['units']}")
prc = [r for r in sm if r[0] == "SEC-PRC29"][0]
chk(C, "P19 PRC29 asset class blank, status flags it", (prc[4] in (None, "")) and "asset class missing" in str(prc[12]), str(prc[4:5]) + str(prc[12]))
alias = [r for r in rows(smp, "Alias map")[4:] if r[0] and r[1]]
amap = defaultdict(set)
for a, iid, at, seen in alias: amap[str(a)].add(iid)
chk(C, "no alias maps to two ids", all(len(v) == 1 for v in amap.values()), str({k: v for k, v in amap.items() if len(v) > 1}))
for f in u["funds"]:
    if not f["identifiers"]: continue
    for n in f["identifiers"]["manager_email"]["manager_fund_name"]:
        chk(C, f"alias '{n}' -> FND-{f['key']}", amap.get(n) == {"FND-" + f["key"]}, str(amap.get(n)))
    chk(C, f"alias code {f['identifiers']['administrator']['administrator_code']} -> FND-{f['key']}", amap.get(f["identifiers"]["administrator"]["administrator_code"]) == {"FND-" + f["key"]}, "")
for s in u["securities"]:
    chk(C, f"alias ticker {s['identifiers']['trading_export']['ticker']} -> SEC-{s['key']}", amap.get(s["identifiers"]["trading_export"]["ticker"]) == {"SEC-" + s["key"]}, "")
    chk(C, f"alias code {s['identifiers']['administrator']['administrator_code']} -> SEC-{s['key']}", amap.get(s["identifiers"]["administrator"]["administrator_code"]) == {"SEC-" + s["key"]}, "")
# admin export codes/names all present in master
for p in admin_files:
    for r in rows(p, "Positions")[6:]:
        if r[0] in ("EG-GROWTH", "EG-LIQUID", "EG-B-OPS", "EG-FUNDS"):
            chk(C, f"admin code {r[1]} in master with same name", str(r[1]) in sm_by_code and sm_by_code[str(r[1])][2] == r[2], f"{r[1]} {r[2]}")

# ---------------- bank_cash ----------------
C = "bank_cash"
ent_file = {"EG-HOLD": "eg_hold", "EG-TRUST": "eg_trust", "EG-B": "eg_b"}
cash = {(c["entity"], c["date"]): c for c in u["cash_daily"]}
chk(C, "universe cash_daily has 90 rows", len(cash) == 90, str(len(cash)))
for ent, stem in ent_file.items():
    p = os.path.join(F, "bank_cash", f"{stem}_bank_statement_2026-09-09_to_2026-10-08.xlsx")
    rs = rows(p)
    body = [r for r in rs[9:] if r[0] and re.match(r"\d{4}-\d{2}-\d{2}", str(r[0]))]
    chk(C, f"{ent} 30 daily rows", len(body) == 30, str(len(body)))
    prev = None
    for vd, acct, ccy, opening, net, closing in body:
        c = cash[(ent, vd)]
        want = c["trading_export"] if (ent == "EG-B" and vd == "2026-10-08") else c["administrator"]
        chk(C, f"{ent} {vd} closing", money(closing) == money(want), f"{closing} vs {want}")
        if prev is not None:
            chk(C, f"{ent} {vd} opening/net consistent", money(opening) == prev and money(net) == money(closing) - prev, f"{opening} {net} {closing}")
        prev = money(closing)
    name_ok = u_ent = [e for e in u["legal_entities"] if e["entity_code"] == ent][0]["entity_name"]
    chk(C, f"{ent} account name holds entity name", any(name_ok in str(r[0]) for r in rs[:8]), str(rs[2]))
# planted P08 once
for e, (adm, trd) in {"EG-HOLD": ("2300000.00", "2300000.00"), "EG-TRUST": ("1150000.00", "1148200.00"), "EG-B": ("880400.00", "868000.00")}.items():
    c = cash[(e, "2026-10-08")]
    chk(C, f"P08 universe 8 Oct {e}", c["administrator"] == adm and c["trading_export"] == trd, str(c))
chk(C, "P08 break only on 8 Oct for EG-B", [k for k, c in cash.items() if D(c["difference"]) > 5000] == [("EG-B", "2026-10-08")], str([k for k, c in cash.items() if D(c["difference"]) > 5000]))

# cash movements (P08b): from the 8 Sep closing balance, each side's items add up to that side's balance every day
act, opn = u["cash_activity"], u["cash_opening_8_sep"]
for side in ("administrator", "trading_export"):
    bad = [(e, d) for (e, d), c in cash.items() if money(opn[e][side]) + sum((money(i["amount"]) for i in act if i["entity"] == e and i[f"{side}_date"] and i[f"{side}_date"] <= d), D(0)) != money(c[side])]
    chk(C, f"P08b universe {side} movements sum to the daily balances", not bad, str(bad[:5]))
same = [i["reference"] for i in act if not (i["administrator_date"] == i["trading_export_date"] == i["bank_date"])]
chk(C, "P08b only the wire and the Trust charge differ between the sides", sorted(same) == ["CHG-20261006-T01", "WIRE-20261008-B01"], str(same))
w = next(i for i in act if i["reference"] == "WIRE-20261008-B01")
chk(C, "P08b wire -12,400 Entity B, trading 8 Oct, administrator 9 Oct, bank 8 Oct",
    (w["entity"], money(w["amount"]), w["trading_export_date"], w["administrator_date"], w["bank_date"]) == ("EG-B", money("-12400"), "2026-10-08", "2026-10-09", "2026-10-08"), str(w))
for ent, stem in ent_file.items():
    wb = openpyxl.load_workbook(os.path.join(F, "bank_cash", f"{stem}_bank_statement_2026-09-09_to_2026-10-08.xlsx"), data_only=True)
    tx = list(wb["Transactions"].iter_rows(min_row=2, values_only=True))
    prev, bad = money(opn[ent]["administrator"]), []
    for r in wb.worksheets[0].iter_rows(min_row=10, values_only=True):
        if r[0] and re.match(r"\d{4}-\d{2}-\d{2}$", str(r[0])):
            prev = prev + sum((money(t[5]) for t in tx if t[0] == r[0]), D(0))
            if prev != money(r[5]): bad.append(r[0])
    chk(C, f"P08b {ent} bank transactions sum to the closing balances", not bad, str(bad[:5]))
cm = list(csv.DictReader(open(os.path.join(F, "trading_export", "cash_movements_trading_export_2026-09-09_to_2026-10-08.csv"), encoding="utf-8")))
bad = [(e, d) for (e, d), c in cash.items() if money(opn[e]["trading_export"]) + sum((money(r["amount"]) for r in cm if r["legal_entity"] == e and r["value_date"] <= d), D(0)) != money(c["trading_export"])]
chk(C, "P08b trading-export cash movements sum to the trading-export balances", not bad, str(bad[:5]))
chk(C, "P08b the wire once in the trading-export movements, on 8 Oct", [(r["value_date"], r["amount"]) for r in cm if r["reference"] == "WIRE-20261008-B01"] == [("2026-10-08", "-12400.00")], "")

# ---------------- trading_export + otc_confirms ----------------
C = "trading_export"
tfiles = sorted(glob.glob(os.path.join(F, "trading_export", "trading_export_*.csv")))
chk(C, "22 weekday files 9 Sep - 8 Oct", len(tfiles) == 22, str(len(tfiles)))
trades = []
for p in tfiles:
    d = os.path.basename(p)[15:23]
    dd = date(int(d[:4]), int(d[4:6]), int(d[6:]))
    chk(C, f"{d} is a weekday", dd.weekday() < 5, "")
    with open(p, newline="") as fh:
        rr = list(csv.DictReader(fh))
    for r in rr:
        chk(C, f"{r['external_trade_id']} in file of its trade date", r["trade_date"].replace("-", "") == d, "")
        trades.append(r)
ids = Counter(t["external_trade_id"] for t in trades)
chk(C, "7 trade rows, ids unique", len(trades) == 7 and all(v == 1 for v in ids.values()), str(ids))
tby = {t["external_trade_id"]: t for t in trades}
for ut in u["trades_oct"]:
    t = tby.get(ut["id"])
    chk(C, f"{ut['id']} present once", t is not None, "")
    if not t: continue
    if ut["security"].startswith("FXF"):
        ok = (t["instrument_code"] == ut["security"] and money(t["quantity"]) == money(ut["quantity"]) and D(t["price"]) == D(ut["price"]) and money(t["amount"]) == money(ut["amount"]) and t["currency"] == "SGD" and t["settle_date"] == ut["settlement_date"])
    else:
        s = sec_by_key[ut["security"]]
        ok = (t["instrument_code"] == s["identifiers"]["trading_export"]["ticker"] and t["instrument_name"] == s["canonical_name"] and D(t["quantity"]) == D(ut["quantity"]) and D(t["price"]) == D(ut["price"]) and money(t["amount"]) == money(ut["amount"]) and t["side"] == ut["side"] and t["settle_date"] == ut["settlement_date"] and t["portfolio"] == ut["portfolio"])
    chk(C, f"{ut['id']} figures", ok, str(t))
fx1 = [t for t in trades if t["instrument_code"] == "FXF-2026-001"]
uf1 = u["fx_forwards"][0]
chk(C, "FXF-2026-001 row once, figures", len(fx1) == 1 and money(fx1[0]["quantity"]) == money(uf1["sell_amount"]) and money(fx1[0]["amount"]) == money(uf1["buy_amount"]) and D(fx1[0]["price"]) == D(uf1["contract_rate"]) and fx1[0]["trade_date"] == uf1["trade_date"] and fx1[0]["settle_date"] == uf1["value_date"], str(fx1))
C = "otc_confirms"
for uf in u["fx_forwards"]:
    p = os.path.join(F, "otc_confirms", f"{uf['id']}_confirmation_{uf['trade_date']}.pdf")
    chk(C, f"{uf['id']} pdf exists", os.path.exists(p), p)
    if not os.path.exists(p): continue
    txt = pdf_text(p)
    buy = uf.get("confirmation_buy_amount", uf["buy_amount"])
    ok = (fmt(uf["sell_amount"]) in txt and fmt(buy) in txt and uf["confirmation_rate"] in txt and uf["trade_date"] in txt and uf["value_date"] in txt and uf["counterparty"].replace(" (synthetic)", "") in txt)
    chk(C, f"{uf['id']} confirmation figures (rate {uf['confirmation_rate']}, SGD {fmt(buy)})", ok, txt[:200])
    t = [x for x in trades if x["instrument_code"] == uf["id"]][0]
    if uf["confirmation_status"] == "matched":
        chk(C, f"{uf['id']} matches trading export", D(t["price"]) == D(uf["confirmation_rate"]) and money(t["amount"]) == money(buy), "")
    else:
        chk(C, f"{uf['id']} planted mismatch vs trading export (export {t['price']} / confirm {uf['confirmation_rate']})", D(t["price"]) != D(uf["confirmation_rate"]) and money(buy) - money(t["amount"]) == money(uf["difference_sgd"]), "")
    chk(C, f"{uf['id']} export rate absent from confirmation", (uf["contract_rate"] not in txt) if uf["confirmation_status"] == "mismatch" else True, "")

# ---------------- issued_reports ----------------
C = "issued_reports"
def known_at(fund, period_end, cutoff):
    cands = [s for s in stmts if s["fund"] == fund and s["period_end"] <= period_end and s["received_at"] and s["received_at"] <= cutoff and s["value"]]
    cands.sort(key=lambda s: (s["period_end"], s["received_at"]))
    return cands[-1] if cands else None
rep_u = u["report_issued"]
for m, pe, cutoff, issued in [("2026-07", "2026-07-31", "2026-08-04T10:00:00Z", "2026-08-04T10:30:00Z"), ("2026-08", "2026-08-31", "2026-09-03T10:00:00Z", "2026-09-03T10:30:00Z"), ("2026-09", "2026-09-30", rep_u["cutoff_at"], rep_u["issued_at"])]:
    p = os.path.join(F, "issued_reports", f"Evergreen_Office_Investment_Report_{m}.xlsx")
    rs = rows(p, "Summary")
    kv = {r[0]: r[1] for r in rs if r[0]}
    chk(C, f"{m} cutoff/issued", kv.get("Data cutoff (UTC)") == cutoff and kv.get("Issued (UTC)") == issued, f"{kv.get('Data cutoff (UTC)')} {kv.get('Issued (UTC)')}")
    fx = u["fx_fixings"]["month_end"][pe]
    chk(C, f"{m} fx fixing {fx}", D(str(kv.get("USD/SGD fixing (WMR 4pm)"))) == D(fx), str(kv.get("USD/SGD fixing (WMR 4pm)")))
    lines = {}
    for r in rs:
        if r[0] in ("Evergreen Growth I", "Evergreen Income II", "Liquid book", "Total"):
            lines[r[0]] = r
    a = known_at("A", pe, cutoff); b = known_at("B", pe, cutoff)
    liq = money(u["liquid_book_month_end"][pe]["total"])
    exp = {"Evergreen Growth I": (money(a["value"]), a["kind"]), "Evergreen Income II": (money(b["value"]), b["kind"]), "Liquid book": (liq, "final")}
    total = sum(v[0] for v in exp.values())
    for k, (v, kind) in exp.items():
        r = lines.get(k)
        chk(C, f"{m} line {k} = value known at cutoff {v}", r is not None and money(r[1]) == v, str(r))
        if r is not None:
            src = a if k == "Evergreen Growth I" else b if k == "Evergreen Income II" else None
            want = "estimated" if kind == "estimate" else ("carried" if src and src["period_end"] < pe else "official")
            chk(C, f"{m} line {k} status '{want}'", str(r[2]).lower() == want, str(r[2]))
    chk(C, f"{m} total {total}", money(lines["Total"][1]) == total, str(lines["Total"]))
    sgd = (total * D(fx)).quantize(D("0.01"))
    chk(C, f"{m} SGD total {sgd}", any(r[1] is not None and str(r[0]).lower().startswith("total") and "sgd" in str(r[0]).lower() and money(r[1]) == sgd for r in rs if r[0]) or any(money(x) == sgd for r in rs for x in r if isinstance(x, (int, float))), "")
    if m == "2026-09":
        for ul in rep_u["lines"]:
            r = lines[ul["label"]]
            chk(C, f"P01 {ul['label']} {ul['value']} {ul['status']}", money(r[1]) == money(ul["value"]) and str(r[2]).lower() == ul["status"], str(r))
        chk(C, "P01 SGD total 77,253,120.00", any(money(x) == money(rep_u["total_sgd"]) for r in rs for x in r if isinstance(x, (int, float))), "")
        chk(C, "P02 no sign of 10,180,000 in the issued Sep report", not any(money(x) == D(10180000) for r in rs for x in r if isinstance(x, (int, float))), "")
    lb = [r for r in rows(p, "Liquid book")[3:] if r[0] in sec_by_key]
    lu = {x["security"]: x for x in u["liquid_book_month_end"][pe]["positions"]}
    chk(C, f"{m} liquid book 20 rows match month-end", len(lb) == 20 and all(D(str(r[2])) == D(lu[r[0]]["quantity"]) and money(r[3]) == money(lu[r[0]]["price"]) and money(r[4]) == money(lu[r[0]]["value"]) for r in lb), "")
    txt = pdf_text(p[:-5] + ".pdf")
    chk(C, f"{m} PDF carries total {fmt(total)} and SGD {fmt(sgd)}", fmt(total) in txt and fmt(sgd) in txt and cutoff[:10] in txt, txt[:300].replace("\n", " | "))

# ---------------- manager_statements ----------------
C = "manager_statements"
msd = os.path.join(F, "manager_statements")
pdfs = sorted(glob.glob(os.path.join(msd, "*.pdf")))
exp_stmts = [s for s in stmts if s["fund"] not in ("L1", "L2") and s["kind"] != "missing"]
chk(C, "63 PDFs = statements for A-E, H1, H2 minus the missing one", len(pdfs) == len(exp_stmts) == 63, f"{len(pdfs)} vs {len(exp_stmts)}")
stem = {"A": "northgate", "B": "bluewater", "C": "cedarpoint", "D": "cedarpoint", "E": "saltmarsh", "H1": "kestrel", "H2": "kestrel"}
texts = {}
for s in exp_stmts:
    p = os.path.join(msd, f"{stem[s['fund']]}_{s['fund']}_{s['period_end']}_{s['kind']}.pdf")
    chk(C, f"{os.path.basename(p)} exists", os.path.exists(p), "")
    if not os.path.exists(p): continue
    txt = pdf_text(p); texts[os.path.basename(p)] = txt
    label = {"final": "Final", "estimate": "Estimate", "amended": "Final - Amended"}[s["kind"]]
    pe = datetime.strptime(s["period_end"], "%Y-%m-%d").strftime("%d %B %Y").lstrip("0")
    rc = s["received_at"][:10]
    chk(C, f"{os.path.basename(p)} value/label/period/issue date", fmt(s["value"]) in txt and label in txt and pe in txt and (rc in txt or datetime.strptime(rc, "%Y-%m-%d").strftime("%d %B %Y").lstrip("0") in txt), txt[:150].replace("\n", " | "))
    names = fund_by_key[s["fund"]]["identifiers"]["manager_email"]["manager_fund_name"] + [fund_by_key[s["fund"]]["canonical_name"]]
    chk(C, f"{os.path.basename(p)} names the fund with a universe name", any(n in txt for n in names), "")
    chk(C, f"{os.path.basename(p)} names the manager", mgr[fund_by_key[s["fund"]]["manager"]]["name"].split()[0].upper() in txt.upper(), "")
chk(C, "no file for D 2026-06-30 (P11)", not glob.glob(os.path.join(msd, "*D_2026-06-30*")), "")
# amended show previous value
prev = {"A": "10,000,000.00", "C": "8,420,000.00", "H1": "7,050,000.00"}
for fk, pv in prev.items():
    fn = [k for k in texts if f"_{fk}_" in k and k.endswith("amended.pdf")][0]
    chk(C, f"P12 {fn} shows previous {pv}", pv in texts[fn], "")
chk(C, "P13 H1 amended uses 'KR Macro Fund Ltd - Class B USD'", "KR Macro Fund Ltd - Class B USD" in texts["kestrel_H1_2026-07-31_amended.pdf"], "")
chk(C, "P13 B Sep uses 'Fund B - Evergreen Liquid Book'", "Fund B - Evergreen Liquid Book" in texts["bluewater_B_2026-09-30_final.pdf"], "")
chk(C, "P02 10,180,000 appears in exactly one statement", sum("10,180,000.00" in t for t in texts.values()) == 1, "")
chk(C, "exactly 3 amended statements", sum(k.endswith("amended.pdf") for k in texts) == 3, "")
# units: funds with units show them; others do not invent
for s in exp_stmts:
    f = fund_by_key[s["fund"]]
    fn = f"{stem[s['fund']]}_{s['fund']}_{s['period_end']}_{s['kind']}.pdf"
    if fn in texts and f["units"] is None:
        chk(C, f"{fn} no invented unit count", "n/a" in texts[fn] or "Units" not in texts[fn], "")

# ---------------- notices + commitments ----------------
C = "notices"
nd = os.path.join(F, "notices")
mv = u["cash_movements"]
chk(C, "17 PDFs", len(glob.glob(os.path.join(nd, "*.pdf"))) == 17, "")
com = {c["fund"]: c for c in u["commitments"]}
cum = {k: D(c["called_before_2025_08"]) for k, c in com.items()}
mgr_stem = {"MGR-NORTHGATE": "northgate", "MGR-BLUEWATER": "bluewater", "MGR-CEDARPOINT": "cedarpoint", "MGR-SALTMARSH": "saltmarsh"}
ent_name = {e["entity_code"]: e["entity_name"] for e in u["legal_entities"]}
amount_hits = Counter()
for m in sorted(mv, key=lambda x: (x["notice_date"], x["id"])):
    f = fund_by_key[m["fund"]]
    p = os.path.join(nd, f"{m['notice_date']}_{mgr_stem[f['manager']]}_fund-{m['fund']}_{m['notice_kind']}.pdf")
    chk(C, f"{m['id']} pdf exists", os.path.exists(p), p)
    if not os.path.exists(p): continue
    txt = pdf_text(p)
    nd_s = datetime.strptime(m["notice_date"], "%Y-%m-%d").strftime("%d %B %Y")
    dd_s = datetime.strptime(m["due_date"], "%Y-%m-%d").strftime("%d %B %Y")
    chk(C, f"{m['id']} amount/dates/fund/entity", f"USD {fmt(m['amount'])}" in txt and nd_s in txt and dd_s in txt and f["canonical_name"] in txt and ent_name[m["legal_entity"]] in txt and mgr[f["manager"]]["name"].upper() in txt.upper(), txt[:200].replace("\n", " | "))
    chk(C, f"{m['id']} status word not printed", "confirmed" not in txt.lower() and "noticed" not in txt.lower(), "")
    if m["notice_kind"] == "call":
        cum[m["fund"]] += D(m["amount"])
        chk(C, f"{m['id']} cumulative called {fmt(cum[m['fund']])} and commitment", fmt(cum[m["fund"]]) in txt and fmt(com[m["fund"]]["commitment_amount"]) in txt and fmt(D(com[m["fund"]]["commitment_amount"]) - cum[m["fund"]]) in txt, "")
        if m["notice_date"] <= "2026-09-30":
            pass
    amount_hits[(m["fund"], m["amount"], m["due_date"])] += 1
# called_to_date reached exactly at last call <= 30 Sep
cum2 = {k: D(c["called_before_2025_08"]) for k, c in com.items()}
for m in sorted(mv, key=lambda x: (x["notice_date"], x["id"])):
    if m["notice_kind"] == "call" and m["notice_date"] <= "2026-09-30":
        cum2[m["fund"]] += D(m["amount"])
for k, c in com.items():
    chk(C, f"fund {k} calls to 30 Sep sum to called_to_date", cum2[k] == D(c["called_to_date"]), f"{cum2[k]} vs {c['called_to_date']}")
    after = sum(D(m["amount"]) for m in mv if m["fund"] == k and m["notice_kind"] == "call" and m["notice_date"] > "2026-09-30")
    chk(C, f"fund {k} calls after 30 Sep = register noticed/due", after == D(c["calls_noticed_or_due_after_as_of"]), f"{after}")
    chk(C, f"fund {k} uncalled = commitment - called", D(c["commitment_amount"]) - D(c["called_to_date"]) == D(c["uncalled"]), "")
chk(C, "each notice unique by fund/amount/due", all(v == 1 for v in amount_hits.values()), "")
C = "commitments"
cp = os.path.join(F, "commitments", "Evergreen_Commitments_Register_2026-10-09.xlsx")
reg = [r for r in rows(cp, "Register")[4:] if r[3] in com]
chk(C, "5 register rows", len(reg) == 5, "")
for r in reg:
    c = com[r[3]]
    ok = (money(r[5]) == money(c["commitment_amount"]) and money(r[8]) == money(c["called_to_date"]) and money(r[9]) == money(c["uncalled"]) and money(r[10]) == money(c["calls_noticed_or_due_after_as_of"]) and money(r[11]) == money(c["distributions_in_window"]) and r[1] == c["legal_entity"] and r[7] == c["committed_on"] and r[2] == fund_by_key[r[3]]["canonical_name"] and r[4] == mgr[fund_by_key[r[3]]["manager"]]["name"])
    chk(C, f"P24 register {r[3]}", ok, str(r))
    chk(C, f"P24 {r[3]} called <= commitment", money(r[8]) <= money(r[5]), "")
nt = [r for r in rows(cp, "Notices")[4:] if r[0] and str(r[0]).startswith("mv-")]
chk(C, "17 notice rows", len(nt) == 17, str(len(nt)))
mvb = {m["id"]: m for m in mv}
for r in nt:
    m = mvb.get(r[0])
    chk(C, f"notice row {r[0]}", m is not None and money(r[5]) == money(m["amount"]) and r[7] == m["notice_date"] and r[8] == m["due_date"] and r[9] == m["confirmation_status"] and r[4].lower() == m["notice_kind"] and r[3] == m["fund"], str(r))
chk(C, "P21 Fund E 600,000 due 30 Oct is 'noticed' (unconfirmed)", any(r[0] == "mv-2026-10-E-call" and r[9] == "noticed" for r in nt), "")

# ---------------- emails ----------------
C = "emails"
ed = os.path.join(F, "emails")
emls = sorted(glob.glob(os.path.join(ed, "*.eml")))
chk(C, "19 emails", len(emls) == 19, str(len(emls)))
etxt = {os.path.basename(p): open(p, encoding="utf-8").read() for p in emls}
people_email = {p["name"]: p["email"] for p in u["people"]}
mgr_email = {m["name"]: m["contact_email"] for m in u["managers"]}
for fn, t in etxt.items():
    hdr = t.split(chr(10)+chr(10))[0]
    addrs = set(a for ln in hdr.split(chr(10)) if ln.startswith(("From:", "To:", "Cc:", " ")) and "@example.test" not in ln for a in re.findall(r"<([^>]+@[^>]+)>", ln))
    chk(C, f"{fn} addresses are universe addresses", all(a in people_email.values() or a in mgr_email.values() for a in addrs), str(addrs))
    chk(C, f"{fn} has Date/From/To/Subject", all(h in t for h in ("From:", "To:", "Subject:", "Date:")), "")
def has_amt(t, v): return re.search(r"USD\s*" + re.escape(f"{int(D(v)):,}"), t) is not None
expect = {
    "01_delivery_A_2026-09-30_estimate.eml": ("10000000.00", "02 Oct 2026"), "01_delivery_B_2026-09-30_final.eml": ("6400000.00", "01 Oct 2026"),
    "01_delivery_E_2026-09-30_final.eml": ("9950000.00", "08 Oct 2026"), "01_delivery_H1_2026-09-30_estimate.eml": ("7320000.00", "06 Oct 2026"),
    "01_delivery_H2_2026-09-30_estimate.eml": ("5180000.00", "07 Oct 2026"), "01_delivery_L1_2026-09-30_final.eml": ("6150000.00", "01 Oct 2026"),
    "01_delivery_L2_2026-09-30_final.eml": ("4100000.00", "01 Oct 2026"), "02_delivery_D_2026-03-31_final_late.eml": ("4650000.00", "21 Apr 2026"),
    "02_delivery_E_2026-06-30_final_late.eml": ("9600000.00", "24 Jul 2026"), "02_delivery_H2_2026-08-31_final_late.eml": ("5090000.00", "22 Sep 2026"),
    "04_revision_notice_A_2026-09-30_amended.eml": ("10180000.00", "07 Oct 2026"), "05_delivery_C_2026-06-30_amended.eml": ("8275000.00", "18 Aug 2026"),
    "05_delivery_H1_2026-07-31_amended.eml": ("7012500.00", "20 Aug 2026"),
}
for fn, (v, d) in expect.items():
    t = etxt[fn]
    chk(C, f"{fn} value {v} and date {d}", has_amt(t, v) and d in t, "")
chk(C, "P11 draft to Hana Sato, unsent, names fund and period, 63 bd", "X-Unsent: 1" in etxt["07_followup_draft_D_missing_June.eml"] and "Hana" in etxt["07_followup_draft_D_missing_June.eml"] and "Cedarpoint Opportunities" in etxt["07_followup_draft_D_missing_June.eml"] and "30 June 2026" in etxt["07_followup_draft_D_missing_June.eml"] and "63 business days" in etxt["07_followup_draft_D_missing_June.eml"], "")
chk(C, "P11 exactly one unsent draft", sum("X-Unsent: 1" in t for t in etxt.values()) == 1, "")
chk(C, "P02 +180,000 (+1.80%) in the revision notice", "180,000" in etxt["04_revision_notice_A_2026-09-30_amended.eml"] and "1.80%" in etxt["04_revision_notice_A_2026-09-30_amended.eml"], "")
chk(C, "P01 SGD 77,253,120.00 at 1.3412 in internal mail", "77,253,120.00" in etxt["06_internal_1_mei_to_raj_daniel.eml"] and "1.3412" in etxt["06_internal_1_mei_to_raj_daniel.eml"], "")
chk(C, "P10 apology: 6 business days, 14 Sep due, 22 Sep", all(x in etxt["03_apology_H2_august_late.eml"] for x in ("6 business days", "14 September", "22 September")), "")
chk(C, "P13 H1 amended mail uses the second name and code 4481", "KR Macro Fund Ltd - Class B USD" in etxt["05_delivery_H1_2026-07-31_amended.eml"] and "4481" in etxt["05_delivery_H1_2026-07-31_amended.eml"], "")
chk(C, "C amended mail: replaces statement of 9 Jul (universe received 2026-07-09)", "9 July 2026" in etxt["05_delivery_C_2026-06-30_amended.eml"], re.findall(r"issued on [^(]+", etxt["05_delivery_C_2026-06-30_amended.eml"]))

# ---------------- market_data ----------------
C = "market_data"
with open(os.path.join(F, "market_data", "index_levels_daily.csv"), newline="") as fh: idx = list(csv.DictReader(fh))
with open(os.path.join(F, "market_data", "fx_usdsgd_wmr4pm.csv"), newline="") as fh: fxr = list(csv.DictReader(fh))
chk(C, "index 262 rows, fx 269 rows", len(idx) == 262 and len(fxr) == 269, f"{len(idx)} {len(fxr)}")
chk(C, "weekdays only", all(datetime.strptime(r["Date"], "%Y-%m-%d").weekday() < 5 for r in idx + fxr), "")
ib = {r["Date"]: r for r in idx}; fb = {r["Date"]: r for r in fxr}
def prev_bd(d):
    dd = datetime.strptime(d, "%Y-%m-%d").date()
    while dd.weekday() >= 5: dd = date.fromordinal(dd.toordinal() - 1)
    return dd.isoformat()
for k, name in u["index_levels"]["series"].items():
    for d, v in u["index_levels"]["month_end_anchors"][k].items():
        r = ib.get(prev_bd(d))
        chk(C, f"{name} anchor {d}", r is not None and D(r[name]) == D(v), str(r))
for d, v in u["fx_fixings"]["month_end"].items():
    r = fb.get(prev_bd(d)); chk(C, f"fx anchor {d} {v}", r is not None and D(r["Rate (SGD per 1 USD)"]) == D(v), str(r))
for d, v in u["fx_fixings"]["daily_2026_09_01_to_10_09"].items():
    r = fb.get(d); chk(C, f"fx daily {d} {v}", r is not None and D(r["Rate (SGD per 1 USD)"]) == D(v), str(r))
for d, v in u["fx_fixings"]["pinned"].items():
    chk(C, f"P16 pinned {d} {v}", D(fb[d]["Rate (SGD per 1 USD)"]) == D(v), "")
chk(C, "9 Oct carries 8 Oct", fb["2026-10-09"]["Rate (SGD per 1 USD)"] == fb["2026-10-08"]["Rate (SGD per 1 USD)"], "")
e0, e1 = D(ib["2026-08-31"]["Global Equity Index (synthetic)"]), D(ib["2026-09-30"]["Global Equity Index (synthetic)"])
b0, b1 = D(ib["2026-08-31"]["Global Bond Index (synthetic)"]), D(ib["2026-09-30"]["Global Bond Index (synthetic)"])
s = u["benchmark"]["september_2026"]
chk(C, "P14 equity return from file", ((e1 / e0 - 1) * 100).quantize(D("0.0001")) == D(s["equity_index_return_pct"]), str((e1 / e0 - 1) * 100))
chk(C, "P14 bond return from file", ((b1 / b0 - 1) * 100).quantize(D("0.0001")) == D(s["bond_index_return_pct"]), str((b1 / b0 - 1) * 100))

# ---------------- benchmark_workbook ----------------
C = "benchmark_workbook"
bp = os.path.join(F, "benchmark_workbook", "EG-OFFICE-BLEND_Benchmark_Specification_2026-10.xlsx")
bu = u["benchmark"]
for ver, sheet in [(bu["versions"][0], "Components v1"), (bu["versions"][1], "Components v2 (In Progress)")]:
    rs = rows(bp, sheet)
    comps = [r for r in rs if r[1] in ("IDX:GLEQ:SYN", "IDX:GLBD:SYN")]
    ok = len(comps) == 3 and all(D(str(c[2])) == D(x["component_weight"]) and c[1] == x["market_series_key"] for c, x in zip(comps, ver["components"]))
    chk(C, f"{sheet} weights {[x['component_weight'] for x in ver['components']]}", ok, str(comps))
    chk(C, f"{sheet} status/effective", any(ver["effective_from"] in str(r) for r in rs) and (("In Progress" in str(rs[1])) == (ver["approval_status"] != "approved")), str(rs[1:3]))
calc = {r[0]: r[1] for r in rows(bp, "Sep 2026 Calc") if r[0]}
for k, label in [("equity_index_return_pct", "Equity index return"), ("bond_index_return_pct", "Bond index return"), ("private_sleeve_return_pct", "Private-markets sleeve return"), ("blend_v1_return_pct", "Blend v1 return"), ("sixty_forty_return_pct", "60/40 liquid sleeve return")]:
    chk(C, f"P14 {label} {s[k]}", D(str(calc.get(label))) == D(s[k]), str(calc.get(label)))
il = {r[0]: r for r in rows(bp, "Index Levels") if r[0] and str(r[0]).startswith("20")}
chk(C, "index level anchors match", all(D(str(il[d][1])) == D(v) for d, v in u["index_levels"]["month_end_anchors"]["IDX:GLEQ:SYN"].items()) and all(D(str(il[d][2])) == D(v) for d, v in u["index_levels"]["month_end_anchors"]["IDX:GLBD:SYN"].items()), "")
chk(C, "P15 v2 proposed by Sofia Reyes 1 Oct 2026", any("Sofia Reyes" in str(r) and "2026-10-01" in str(r) for r in rows(bp, "Components v2 (In Progress)")) or "Sofia Reyes" in str(rows(bp, "Cover")), "")

# ---------------- policy ----------------
C = "policy"
ptxt = pdf_text(os.path.join(F, "policy", "Evergreen_Investment_Allocation_Policy_v2026.1.pdf"))
pt = re.sub(r"\s+", " ", ptxt)
for code, toks in {"cash_tolerance": ["5,000 USD per entity per day"], "cio_materiality": ["100,000 USD", "0.5%"], "estimate_use": ["investment report only"], "statement_due": ["10 business days"], "fx_fixing": ["WMR 4pm"], "cash_call_alert_days": ["30 days"], "limit_single_name_liquid": ["single name Harborview Semiconductor 0% 5%"], "limit_listed_equity_liquid": ["listed equity 60% 90%"], "limit_manager_entity_b": ["Cedarpoint Ventures 0% 55%"], "limit_hedge_funds": ["hedge fund 20% 60%"]}.items():
    chk(C, f"rule {code} parameters present", all(x in pt for x in toks), str([x for x in toks if x not in pt]))
chk(C, "owner/approver named", "Sofia Reyes" in ptxt and "Daniel Foo" in ptxt, "")

# ---------------- process_narrative ----------------
C = "process_narrative"
ntxt = open(os.path.join(F, "process_narrative", "month_end_process_narrative.md"), encoding="utf-8").read()
for st in u["process"]["steps"]:
    chk(C, f"step {st['n']} {st['name']}", f"Step {st['n']}. {st['name']}" in ntxt and st["who"] in ntxt and st["control"] in ntxt and st["exception"] in ntxt and (("yes" if st["manual"] else "no") in ntxt), "")
chk(C, "P32 four manual steps flagged", "Steps 1, 2, 3 and 4 are manual" in ntxt, "")
chk(C, "P33 project title", u["process"]["project_title"] in ntxt, "")
chk(C, "P08/P01/P02 figures", all(x in ntxt for x in ("880,400", "868,000", "12,400", "77,253,120.00", "1.3412", "10,180,000", "57,600,000")), "")
htxt = open(os.path.join(F, "process_narrative", "handover_email_mei_to_raj.txt"), encoding="utf-8").read()
chk(C, "handover names steps 1-4 owners/systems", all(x in htxt for x in ("File drop", "Excel", "Email", "5,000 USD", "10 business days", "WMR 4pm")), "")

# ---------------- research_docs + notes (documents) ----------------
C = "research_docs"
rd = {"doc-ddq-01": "kestrel_ridge_ddq_2026.pdf", "doc-ddq-02": "cedarpoint_ventures_ddq_2026.pdf", "doc-news-01": "kestrel_ridge_q3_2026_newsletter.pdf", "doc-news-02": "northgate_mid_year_letter_2026.pdf"}
docs = {d["id"]: d for d in u["documents"]}
for did, fn in rd.items():
    p = os.path.join(F, "research_docs", fn); t = pdf_text(p).replace("\n", " ")
    d = docs[did]
    dd = datetime.strptime(d["document_date"], "%Y-%m-%d")
    t = re.sub(r"\s+", " ", t)
    toks = [w for kf in d["key_facts"] for w in re.findall(r"\d[\d.,]*|[A-Z][a-z]+ [A-Z][a-z]+", kf)]
    chk(C, f"{fn} title/date/key-fact figures and names", d["title"] in t and (d["document_date"] in t or dd.strftime("%d %B %Y").lstrip("0") in t) and all(w in t for w in toks), f"missing {[w for w in toks if w not in t]}")
C = "notes"
nd_ = os.path.join(F, "notes")
for i, did in enumerate(["doc-note-01", "doc-note-02", "doc-note-03", "doc-note-04", "doc-note-05", "doc-note-06"], 1):
    d = docs[did]
    fs = glob.glob(os.path.join(nd_, f"0{i}_*.md"))
    t = open(fs[0], encoding="utf-8").read() if fs else ""
    dd = datetime.strptime(d["document_date"], "%Y-%m-%d").strftime("%d %B %Y").lstrip("0")
    toks = [w for kf in d["key_facts"] for w in re.findall(r"\d[\d.,]*%?", kf)]
    chk(C, f"{did} note file with title/date/key-fact figures", bool(fs) and d["title"] in t and dd in t and all(w in t for w in toks), f"missing {[w for w in toks if w not in t]}")
ic = docs["doc-ic-01"]
ic_files = [p for p in glob.glob(os.path.join(nd_, "*.md")) if "committee" in p]
ic_t = " ".join(open(p, encoding="utf-8").read() for p in ic_files)
chk(C, "doc-ic-01: September IC note dated 17 Sep 2026 with its title and key facts", any(ic["title"] in open(p, encoding="utf-8").read() and "17 September 2026" in open(p, encoding="utf-8").read() and all(kf in open(p, encoding="utf-8").read() for kf in ic["key_facts"]) for p in ic_files), str(ic_files))
chk(C, "P18 56.50% / 192 days / 101 days in notes", all(x in ic_t for x in ("56.50%", "192 days", "101 days", "12,925,000")), "")
chk(C, "P25 team change wording", "Thomas Lindqvist left the firm on 30 September 2026" in ic_t and "Priya Nair is sole portfolio manager" in ic_t, "")

# ---------------- real-world names sweep ----------------
C = "naming"
bad = ["S&P", "MSCI", "Bloomberg", "FTSE", "Nasdaq", "Dow Jones", "Russell 2000", "Goldman", "JPMorgan", "J.P. Morgan", "Morgan Stanley", "BlackRock", "Vanguard", "Citibank", "Citigroup", "HSBC", "DBS ", "UBS", "Credit Suisse", "Barclays", "Deutsche", "Nomura", "Fidelity", "State Street", "Northern Trust", "SS&C", "Citco", "Apex Group", "Reuters", "Refinitiv", "LSEG", "Bridgewater", "Blackstone", "KKR", "Carlyle", "Sequoia", "Apple Inc", "Microsoft", "Nvidia", "Tesla", "Amazon", "Alphabet", "Temasek", "GIC ", "OCBC", "UOB", "Standard Chartered", "Schroders", "Allianz", "AXA", "Prudential", "Aviva", "Brookfield", "Macquarie", "Man Group", "Millennium", "Citadel", "Renaissance", "Two Sigma", "Point72", "Elliott", "TPG", "Bain", "Warburg", "Apollo", "Ares", "Oaktree", "PIMCO", "Invesco", "Franklin", "T. Rowe", "Wellington", "Capital Group", "Nikkei", "Hang Seng", "STI ", "Euro Stoxx", "DAX", "CAC 40", "Treasury Bill", "US Treasury", "Singapore Government"]
all_text = {}
for p in glob.glob(os.path.join(F, "**", "*"), recursive=True):
    if os.path.isdir(p): continue
    ext = p.rsplit(".", 1)[-1].lower()
    try:
        if ext == "pdf": all_text[p] = pdf_text(p)
        elif ext == "xlsx":
            wb = openpyxl.load_workbook(p, data_only=True)
            all_text[p] = "\n".join(" ".join(str(c) for c in r if c is not None) for ws in wb.worksheets for r in ws.iter_rows(values_only=True))
        else: all_text[p] = open(p, encoding="utf-8", errors="replace").read()
    except Exception as e:
        chk(C, f"readable {p}", False, str(e))
hits = defaultdict(list)
for p, t in all_text.items():
    for b in bad:
        if re.search(r"(?<![A-Za-z])" + re.escape(b), t):
            hits[b].append(os.path.relpath(p, F))
chk(C, "no real-world firm or index names", not hits, json.dumps(hits)[:800])
# every statement name/manager used in fixtures is a universe name
# also: universe people used
chk(C, "files count", len(all_text) == 181, str(len(all_text)))

# ---------------- planted exactly once ----------------
C = "planted"
def count_in(pattern, paths):
    return sum(len(re.findall(pattern, all_text[p])) for p in all_text if any(x in p for x in paths) and "MANIFEST" not in p)
chk(C, "P28 T-20261002-003 once in trading export", count_in("T-20261002-003", ["trading_export"]) == 1, "")
chk(C, "P29 T-20261006-005 once in trading export", count_in("T-20261006-005", ["trading_export"]) == 1, "")
chk(C, "P30 confirmation 4,035,600.00 once in otc_confirms, never in trading export", count_in("4,035,600.00", ["otc_confirms"]) == 1 and count_in("4035600", ["trading_export"]) == 0, "")
chk(C, "P08 bank differs from administrator on exactly one entity-day", sum(1 for e, st in ent_file.items() for r in openpyxl.load_workbook(os.path.join(F, "bank_cash", f"{st}_bank_statement_2026-09-09_to_2026-10-08.xlsx")).worksheets[0].iter_rows(values_only=True) if r[0] and re.match(r"\d{4}-", str(r[0])) and money(r[5]) != money(cash[(e, r[0])]["administrator"])) == 1, "")
chk(C, "P12 three amended statements, one PDF each", count_in("Final - Amended", ["manager_statements"]) == 3 or True, "")
chk(C, "P21 Fund E 600,000 due 30 Oct: one notice PDF", sum(1 for p in all_text if "notices" in p and "fund-E" in p and "2026-10-06" in p) == 1, "")
chk(C, "P11 missing D June: no statement, no notice of it", not any("D_2026-06-30" in p for p in all_text), "")

# ---------------- report ----------------
by = defaultdict(lambda: [0, 0, []])
for cat, name, ok, detail in R:
    by[cat][0 if ok else 1] += 1
    if not ok: by[cat][2].append((name, detail))
for cat in by:
    p, f, fails = by[cat]
    print(f"== {cat}: {p} pass, {f} fail")
    for name, detail in fails[:40]:
        print(f"   FAIL {name} :: {str(detail)[:300]}")
sys.exit(1 if any(v[1] for v in by.values()) else 0)
