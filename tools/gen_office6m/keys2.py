"""Answer keys of the other 49 cards (no priority 1 to 50). Same rule as keys.py: every expected value is a calculation on the World (w) or on the tables of more.py (w.X), which also write the files."""
import datetime as dt
from decimal import Decimal as D

from .files import RECV, month_end, months, pname
from .files2 import close_items
from .keys import KEYS, Q, cash, latest, pct, uc
from .more import (ACCOUNT_FORM, ACCOUNT_STEPS, APPROVERS, BUDGET, ESTATE, FAMILY_GRANTED, FAMILY_POLICY, FAMILY_REQUEST, FEED, GLOSSARY, GLOSSARY_PROPOSED, GRANT_POLICY, GRANT_REQUEST, HF_TERMS, HOLDINGS, INSURED,
                   ONBOARD, PAYOUT, PAYOUT_Q, PERSONNEL, PRICE_TOL, SIGNING, SOP_FAIL_MIN, STAGE_LIMIT_DAYS, TARGET_ALLOC, TAX, TAX_RATES, TRUST_DEED, bd_between, eq, months_iter)
from .world import ACCT, COMMIT_DATE, END, ENT, FAMILY, FUND, GRANT_BUDGET, MGR, OFFICE_RULES, PEOPLE, PRIVATE, TERMS, U, add_bd, d, lastbd, next_bd, q2

S0, S1 = d("2026-04-01"), d("2026-09-30")
ZERO = D(0)
DAY90 = dt.timedelta(days=90)


def ssum(it): return sum(it, ZERO)
def cash_eq(w, e, src="admin"): return cash(w, e, "USD", src) + q2(cash(w, e, "SGD", src) / w.fx[END])
def ex(w, id_, n=0): return list(KEYS[id_](w).values())[n]["expected"]
def prev_bd(x):
    while not x.weekday() < 5: x -= dt.timedelta(days=1)
    return x


# ---------------------------------------------------------------------------------------------------- operate and control
@uc("uc-052-insurance", ["*/insurance_schedule/insurance_schedule_2026-10-01.pdf", "*/insurance/*_renewal.pdf"])
def k052(w):
    rows = []
    for p in w.policies:
        nxt = p["renewal"] if p["renewal"] > END else p["renewal"].replace(year=p["renewal"].year + 1)
        rows.append(dict(policy=p["id"], name=p["name"], next_renewal=nxt, days_left=(nxt - END).days, sum_insured=INSURED[p["id"]][1], premium=p["premium"], currency=p["ccy"], renewal_notice_received=p["notice"] <= END))
    rows.sort(key=lambda r: r["days_left"]); due = [r for r in rows if r["days_left"] <= 60]
    return Q("Which policies expire in the next 60 days and what is each worth?", dict(expiring_in_60_days=due, count=len(due), all_policies=rows), "next renewal date (renewal date this year, else next year) less 13 Oct 2026; worth = sum insured and premium from the insurance schedule")


def stmt_flags(w, m):
    lo = END - DAY90; fs = [f for f in FUND if FUND[f]["manager"] == m]
    late = [s for s in w.stmts if s["fund"] in fs and s["kind"] != "amended" and s["received"] and d(s["received"]) >= lo and d(s["received"]) > d(s["due"])]
    am = [s for s in w.stmts if s["fund"] in fs and s["kind"] == "amended" and d(s["received"]) >= lo]
    miss = [s for s in w.stmts if s["fund"] in fs and s["status"] == "missing"]
    pers = [p for p in PERSONNEL if p[0] == m and d(p[1]) >= lo]
    return dict(late=len(late), amended=len(am), missing=len(miss), personnel_changes=len(pers), total=len(late) + len(am) + len(miss) + len(pers))


@uc("uc-053-watchlist", ["*/manager_statements/*.pdf", "*/manager_news/*.eml", "reference/kestrel_ridge_q3_2026_newsletter.pdf", "received_log_all.csv"])
def k053(w):
    mgrs = sorted({FUND[f]["manager"] for f in FUND}); rows = {MGR[m]["name"]: stmt_flags(w, m) for m in mgrs}
    return Q("Which managers have given us a late, restated or changed statement this quarter?", dict(window_start=END - DAY90, by_manager=rows, on_watchlist=[n for n, r in rows.items() if r["total"]]),
             "per manager: statements received in the last 90 days after their due date, amended statements received in the window, statements still missing, personnel-change mails dated in the window")


def ladder(w):
    out = {}
    for e in ENT:
        c = cash_eq(w, e); win = {}
        for n in (30, 60, 90):
            hi = END + dt.timedelta(days=n); calls = ssum(x["amount"] for x in w.calls if x["ent"] == e and END < d(x["due"]) <= hi)
            pays = ssum(eq(w, i["amount"], i["ccy"]) for i in w.X.sched if i["ent"] == e and i["status"] in ("approved", "scheduled") and i["due"] <= hi)
            win[str(n)] = dict(calls=calls, approved_and_scheduled_payments=pays, cash_after=c - calls - pays, below_buffer=c - calls - pays < OFFICE_RULES["buffer_usd"])
        out[ENT[e]] = dict(cash_usd=cash(w, e, "USD", "admin"), cash_sgd=cash(w, e, "SGD", "admin"), cash_usd_equivalent=c, windows=win)
    return out


@uc("uc-054-ladder", ["*/payment_schedule/payment_schedule_2026-10-13.csv", "*/administrator_cash/administrator_cash_2026-10_mtd.csv", "*/notices/2026-10-13_C_call7.pdf", "*/commitments/commitments_register_2026-10-13.xlsx"])
def k054(w):
    return Q("How much cash do we have against calls and payments in the next 30, 60 and 90 days?", dict(by_entity=ladder(w)),
             "administrator cash of 13 Oct (SGD at the 1.3400 fixing) less calls with a due date inside the window less payments of status approved or scheduled in the payment schedule (held and expected ones are left out)")


@uc("uc-055-corpact", ["*/corporate_actions/*.pdf", "reference/EG_security_master_20261008.xlsx"])
def k055(w):
    X = w.X; hi = END + dt.timedelta(days=14); book, outside = [], []
    for n in X.caction_notices:
        row = dict(security=w.sec[n["sec"]]["canonical_name"], event=n["kind"], ex_date=n["ex"], pay_date=n["pay"], quantity=n["qty"], expected_cash=n["amount"])
        (book if END <= n["ex"] <= hi or END <= n["pay"] <= hi else outside).append(row)
    t = X.tender
    dec = [dict(security=w.sec[t["sec"]]["canonical_name"], event="voluntary tender offer", respond_by=d(t["deadline"]), offer_price=t["offer"], last_price=t["px"], premium_pct=pct(t["offer"] - t["px"], t["px"], 2), quantity_held=t["qty_held"]) if END <= d(t["deadline"]) <= hi else None]
    return Q("Which actions need a decision or a booking", dict(window=[END, hi], to_book=book, cash_to_book=ssum(r["expected_cash"] for r in book), to_decide=[x for x in dec if x], announced_outside_window=outside),
             "notices with an ex-date or pay date between 13 and 27 Oct are bookings (mandatory cash events at the quantity held); the tender offer is a decision with a deadline inside the window; the HTN29 coupon of 30 Dec is announced but outside")


@uc("uc-056-custrecon", ["*/custody_statements/custody_statement_2026-09-30.pdf", "*/administrator_nav/administrator_export_2026-09.xlsx", "*/custodian_positions/positions_20260930.csv"])
def k056(w):
    from .more import CUST_BREAKS
    rows = [dict(security=w.sec[k]["canonical_name"], administrator_qty=w.qty[S1][k], custodian_qty=w.X.custody[k], difference=w.qty[S1][k] - w.X.custody[k], value_usd=q2((w.qty[S1][k] - w.X.custody[k]) * w.px[k][S1]), reason=CUST_BREAKS[k][1])
            for k in w.sec if w.qty[S1][k] != w.X.custody[k]]
    return Q("Which holdings differ between the custodian and the administrator, and why", dict(breaks=rows, holdings_compared=len(w.sec)), "administrator quantity (30 Sep pack) less the quantity on the custodian's 30 Sep safekeeping statement, per holding; value at the 30 Sep price; the reason is the custodian's own note")


@uc("uc-057-pricecheck", ["*/market_data/second_source_prices_2026-09-30_and_2026-10-13.csv", "*/administrator_nav/administrator_export_2026-09.xlsx"])
def k057(w):
    rows, n = [], 0
    for day in (S1, END):
        for k in w.sec:
            n += 1; a, b = w.px[k][day], w.X.second[(day, k)]; gap = pct(a - b, b, 4)
            if abs(D(str(gap))) > PRICE_TOL * 100: rows.append(dict(date=day, security=w.sec[k]["canonical_name"], administrator_price=a, second_source_price=b, gap_pct=gap))
    return Q("Which prices differ from a second source by more than tolerance", dict(tolerance_pct=PRICE_TOL * 100, prices_compared=n, over_tolerance=rows), "(administrator price less second-source price) over second-source price, for 20 securities on 30 Sep and 13 Oct, flagged above 0.5 percent")


@uc("uc-058-settle", ["*/settlement_status/settlement_report_2026-10-13.csv", "*/trading_export/trading_export_2026100*.csv"])
def k058(w):
    f = [dict(trade=x["id"], security=w.sec[x["sec"]]["canonical_name"], side=x["side"], quantity=x["qty"], amount=x["amount"], settle_date=x["settle"], business_days_late=bd_between(x["settle"], END), chase=x["cpty"], reason=x["reason"], cash_booked=False) for x in w.X.fails if x["settle"] < END]
    ok = [t["id"] for t in w.trades if S1 - dt.timedelta(days=2) <= t["settle"] <= END]
    return Q("Which trades failed to settle and whom to chase", dict(failed=f, count=len(f), settled_in_report=ok, chase_counterparties=sorted({x["chase"] for x in f})), "trades in the custodian settlement report with a settle date before 13 Oct, status not settled and no cash booked; age in business days after the settle date")


@uc("uc-059-breakage", ["*/break_register/break_register_2026-10-13.csv", "*/exception_log/exception_log_2026-10-13.csv"])
def k059(w):
    rows = [dict(id=b["id"], type=b["type"], entity=ENT[b["ent"]], subject=b["subject"], detected=b["detected"], age_business_days=bd_between(b["detected"], END)) for b in w.X.breaks]
    cb = [r for r in rows if r["type"] == "cash break"]
    return Q("Which breaks are older than five days and go to Finance", dict(cash_breaks_over_5_days=[r for r in cb if r["age_business_days"] > 5], open_cash_breaks=len(cb), all_open=rows), "open cash breaks in the register: business days from the detection date to 13 Oct; older than five go to Finance")


@uc("uc-060-docinbox", ["*/inbox/*"])
def k060(w):
    rows = [dict(file=f, what=what, belongs_in=dest or "unknown", action=act) for f, what, dest, act in w.X.inbox]
    return Q("Where each unrecognised file belongs or whether to refuse it", dict(files=len(rows), recognised=[r for r in rows if r["belongs_in"] != "unknown"], unrecognised=[r for r in rows if r["belongs_in"] == "unknown"]),
             "the five files of the inbox read by content: three are known kinds, two are not (a receipt to refuse, a sheet to query)")


@uc("uc-061-dqscore", ["*/load_log/load_log_2026-10-13.csv", "received_log_all.csv"])
def k061(w):
    by = {}
    for r in w.X.load_log: by.setdefault(r["source"], []).append(r)
    rows = sorted(({"source": s, "loads": len(v), "passed": sum(1 for r in v if r["on_time"] and r["adds_up"] and not r["manual_fix"]), "late_or_missing": sum(1 for r in v if not r["on_time"]), "did_not_add_up": sum(1 for r in v if not r["adds_up"]), "manual_fixes": sum(1 for r in v if r["manual_fix"])} for s, v in by.items()), key=lambda r: r["source"])
    for r in rows: r["score_pct"] = pct(r["passed"], r["loads"], 1)
    rows.sort(key=lambda r: (r["score_pct"], r["source"]))
    return Q("Which source to fix first", dict(by_source=rows, fix_first=rows[0]["source"]), "per source: share of loads that were on time, added up and needed no manual fix (load log built from the planted mess of each file and the received log); lowest score first")


def fx_rows(w):
    fx = w.fx[END]; out = []
    for f in U["fx_forwards"]:
        sell, buy = D(f["sell_amount"]), D(f["buy_amount"]); vd = d(f["value_date"])
        out.append(dict(id=f["id"], value_date=vd, days_to_value=(vd - END).days, sell_usd=sell, buy_sgd=buy, contract_rate=D(f["contract_rate"]), spot=fx, mtm_usd=q2(buy / fx - sell), confirmation_status=f["confirmation_status"]))
    return out


@uc("uc-062-fxlife", ["*/fx_confirmations/FXF-*_confirmation.pdf", "*/fx_rates/fx_usdsgd_20261013.csv", "*/trading_export/trading_export_2026091*.csv", "*/trading_export/trading_export_2026100*.csv"])
def k062(w):
    rows = fx_rows(w); trust = cash(w, "EG-TRUST", "USD", "admin"); need = ssum(r["sell_usd"] for r in rows)
    return Q("Which forwards need settlement cash or a roll", dict(forwards=rows, due_within_30_days=[r["id"] for r in rows if r["days_to_value"] <= 30], total_usd_to_deliver=need, trust_usd_cash=trust, trust_usd_shortfall=max(ZERO, need - trust), next_value_date=min(r["value_date"] for r in rows)),
             "mark to market = buy amount over the 13 Oct spot (1.3400) less sell amount (forward points ignored by convention); USD to deliver on each value date against the Trust's USD cash")


@uc("uc-063-cashcode", ["*/bank_statements/HB_HOLD_USD_2026-08.xlsx", "*/bank_statements/TCB_HOLD_USD_2026-09.xlsx", "*/bank_statements/HB_B_USD_2026-10_mtd.xlsx"])
def k063(w):
    rows = [dict(account=t["acct"], date=t["date"], amount=t["amt"], description=t["desc"]) for t in w.tx if t["ev"] is None and t["typ"] not in ("bank_fee", "interest")]
    return Q("Which bank lines have no purpose and need coding", dict(uncoded=rows, count=len(rows), net_amount=ssum(r["amount"] for r in rows)), "bank lines that carry no event of the World (no invoice, notice, payroll, trade or transfer), leaving out the bank's own fee and interest lines")


@uc("uc-064-fxexp", ["*/administrator_cash/administrator_cash_2026-10_mtd.csv", "*/fx_confirmations/FXF-*_confirmation.pdf", "*/fx_rates/fx_usdsgd_20261013.csv", "*/payment_schedule/payment_schedule_2026-10-13.csv"])
def k064(w):
    fx = w.fx[END]; usd = ssum(cash(w, e, "USD", "admin") for e in ENT); sgd = ssum(cash(w, e, "SGD", "admin") for e in ENT); fwd = ssum(D(f["buy_amount"]) for f in U["fx_forwards"]); inv = investments(w, S1)
    sgd_eq, fwd_eq = q2(sgd / fx), q2(fwd / fx); total = inv + usd + sgd_eq
    out90 = ssum(eq(w, i["amount"], i["ccy"]) for i in w.X.sched if i["ccy"] == "SGD" and i["status"] in ("approved", "scheduled") and i["due"] <= END + DAY90)
    return Q("Whether to hedge a currency exposure", dict(sgd_cash=sgd, sgd_cash_usd_eq=sgd_eq, sgd_bought_forward=fwd, sgd_forward_usd_eq=fwd_eq, net_sgd_exposure_usd_eq=sgd_eq + fwd_eq, share_of_family_pct=pct(sgd_eq + fwd_eq, total, 2), usd_exposure_usd_eq=inv + usd,
                                                              sgd_payments_next_90_days_usd_eq=out90, family_total_usd_eq=total),
             "SGD cash of the three entities plus SGD bought forward (both at the 13 Oct fixing) against the total of investments (fund values as known on 13 Oct, liquid book at 30 Sep) and cash; every investment is in USD; SGD payments in the next 90 days from the payment schedule")


def asset_usd(w, a, x=None): return eq(w, a["latest"]["value"], a["ccy"])


@uc("uc-065-realassets", ["*/property_valuations/valuation_RA-*.pdf", "*/title_deeds/title_deed_RA-*.pdf"])
def k065(w):
    rows = [dict(id=a["id"], name=a["name"], type=a["type"], entity=ENT[a["ent"]], latest_value=a["latest"]["value"], currency=a["ccy"], value_usd=asset_usd(w, a), appraised=a["latest"]["date"], title_holder=a["title"]) for a in w.X.assets]
    ty, en = {}, {}
    for r, a in zip(rows, w.X.assets): ty[a["type"]] = ty.get(a["type"], ZERO) + r["value_usd"]; en[r["entity"]] = en.get(r["entity"], ZERO) + r["value_usd"]
    wrong = [r["name"] for r, a in zip(rows, w.X.assets) if a["title"] != ENT[a["ent"]] and a["type"] in ("residential property", "land")]
    return Q("What real assets we own, their values and who holds them", dict(assets=rows, total_usd=ssum(r["value_usd"] for r in rows), by_type=ty, by_entity=en, title_not_in_entity_name=wrong), "latest appraisal per asset, SGD at the 13 Oct fixing; the title deed holder against the entity that owns the asset")


@uc("uc-066-propreval", ["*/property_valuations/valuation_RA-*.pdf"])
def k066(w):
    rows = [dict(id=a["id"], name=a["name"], appraised=a["latest"]["date"], age_days=(END - a["latest"]["date"]).days, due=(END - a["latest"]["date"]).days > 365) for a in w.X.assets]
    return Q("Whether to order a new appraisal", dict(by_asset=rows, order_new=[r["name"] for r in rows if r["due"]]), "13 Oct 2026 less the date of the latest appraisal, flagged above 365 days")


# ---------------------------------------------------------------------------------------------------- hold and invest
@uc("uc-067-unrl", ["*/tax_lots/lot_register_2026-09-30.xlsx", "*/trading_export/trading_export_2026*.csv", "*/administrator_nav/administrator_export_2026-09.xlsx"])
def k067(w):
    rows = []
    for l in w.X.lots30:
        v, c = q2(l["qty"] * w.px[l["sec"]][S1]), q2(l["qty"] * l["unit"]); rows.append(dict(lot=l["id"], security=w.sec[l["sec"]]["canonical_name"], acquired=l["acq"], days_held=(S1 - l["acq"]).days, quantity=l["qty"], cost=c, value=v, gain=v - c))
    by = {}
    for r in rows: by[r["security"]] = by.get(r["security"], ZERO) + r["gain"]
    hv = w.value("HVS", S1); tot = w.book(S1); cure = q2((hv - D("0.05") * tot) / D("0.95"))
    return Q("Which lots to sell for a tax or rebalance reason", dict(lots=len(rows), total_unrealised_gain=ssum(r["gain"] for r in rows), total_unrealised_loss=ssum(r["gain"] for r in rows if r["gain"] < 0), loss_lots=sorted((r for r in rows if r["gain"] < 0), key=lambda r: r["gain"]),
                                                                       largest_gain_lots=sorted(rows, key=lambda r: -r["gain"])[:5], gain_by_security=dict(sorted(by.items())), harborview_lots=[r for r in rows if r["security"] == "Harborview Semiconductor"], harborview_sale_to_reach_5_pct=cure),
             "market value at the 30 Sep price less cost for each open lot (opening lots of 31 Mar plus the 2026 buys, sells taken first-in first-out); losses are the tax candidates, Harborview lots the rebalance candidates")


@uc("uc-068-incomef", ["*/income_calendar/income_calendar_2026-10-13.csv", "*/corporate_actions/*.pdf", "reference/EG_security_master_20261008.xlsx"])
def k068(w):
    ev = w.X.income; q = {}
    for e in ev: k = f"{e['pay'].year}-Q{(e['pay'].month - 1) // 3 + 1}"; q[k] = q.get(k, ZERO) + e["amount"]
    return Q("How much income to plan for next year", dict(period=[END, d("2027-10-13")], total=ssum(e["amount"] for e in ev), coupons=ssum(e["amount"] for e in ev if e["kind"] == "coupon"), dividends=ssum(e["amount"] for e in ev if e["kind"] == "dividend"), by_quarter=dict(sorted(q.items())), events=len(ev)),
             "coupon rate over two times face for the three bonds, plus 0.45 percent of the 13 Oct price per share each quarter for the equities, at the quantity held on 13 Oct, paid between 14 Oct 2026 and 13 Oct 2027")


@uc("uc-069-lookthru", ["*/fund_holdings/fund_holdings_2026-09-30.xlsx", "*/manager_statements/*_final.pdf", "*/ddq/cedarpoint_ddq_2026.pdf"])
def k069(w):
    vals = {f: latest(w, f)["value"] for f in PRIVATE}; ex_, sec, funds = {}, {}, {}
    for f in PRIVATE:
        for c, s, wt in HOLDINGS[f]:
            if c == "Other holdings": continue
            amt = q2(vals[f] * D(wt) / 100); ex_[c] = ex_.get(c, ZERO) + amt; sec[s] = sec.get(s, ZERO) + amt; funds.setdefault(c, []).append(f)
    hv = w.value("HVS", END); book = w.book(END); fam = ssum(latest(w, f)["value"] for f in FUND) + book
    rows = sorted(({"company": c, "through_funds": v, "funds": sorted(funds[c]), "share_of_family_pct": pct(v, fam, 2)} for c, v in ex_.items()), key=lambda r: (-r["through_funds"], r["company"]))
    return Q("Whether the family is over-exposed to one company or sector through funds", dict(top_companies=rows[:5], companies_in_more_than_one_fund=[r["company"] for r in rows if len(r["funds"]) > 1], by_sector={k: v for k, v in sorted(sec.items(), key=lambda kv: -kv[1])},
                                                                                          harborview_direct=hv, harborview_through_funds=ex_["Harborview Semiconductor"], harborview_direct_pct_of_liquid_book=pct(hv, book, 2), harborview_with_funds_pct_of_liquid_book=pct(hv + ex_["Harborview Semiconductor"], book, 2), family_investments=fam),
             "latest statement value of each private fund times the weight in the manager's holdings list, summed by company and sector; the direct holding of Harborview Semiconductor from the 13 Oct book; share of the liquid book as the single-name limit measures it")


@uc("uc-070-idle", ["*/administrator_cash/administrator_cash_2026-10_mtd.csv", "*/payment_schedule/payment_schedule_2026-10-13.csv", "reference/office_rules.csv"])
def k070(w):
    L = ladder(w); out = {}
    for e in ENT:
        r = L[ENT[e]]; w90 = r["windows"]["90"]; idle = r["cash_usd_equivalent"] - w90["calls"] - w90["approved_and_scheduled_payments"] - OFFICE_RULES["buffer_usd"]
        out[ENT[e]] = dict(cash_usd_equivalent=r["cash_usd_equivalent"], outflow_90_days=w90["calls"] + w90["approved_and_scheduled_payments"], buffer=OFFICE_RULES["buffer_usd"], idle=max(ZERO, idle), short=max(ZERO, -idle))
    return Q("Whether to invest, repay or hold the surplus", dict(by_entity=out, total_idle=ssum(v["idle"] for v in out.values()), total_short=ssum(v["short"] for v in out.values())), "cash less the 90 day ladder outflow (calls plus approved and scheduled payments) less the 250,000 buffer, per entity; a negative result is a shortfall, not an idle amount")


@uc("uc-071-expdist", ["*/manager_outlook/*_distribution_outlook_2026-27.pdf", "*/manager_statements/*_final.pdf", "*/notices/*_call*.pdf"])
def k071(w):
    by, qt, rows = {}, {q: ZERO for q in PAYOUT_Q}, {}
    for f in PRIVATE:
        k = latest(w, f); amts = [q2(k["value"] * D(str(r)) / 100) for r in PAYOUT[f]]
        rows[pname(f)] = dict(latest_value=k["value"], valuation_date=k["period"], payout_pct=list(PAYOUT[f]), amounts=amts, total=ssum(amts))
        for q, a in zip(PAYOUT_Q, amts): qt[q] += a
    return Q("How much money to expect back from the funds", dict(by_quarter=qt, total_next_4_quarters=ssum(qt.values()), by_fund=rows), "latest statement value of each private fund times the payout rate of the manager's outlook, per quarter end (31 Dec 2026 to 30 Sep 2027)")


def month_key(x): return f"{x.year}-{x.month:02d}"


@uc("uc-072-cashfc", ["*/administrator_cash/administrator_cash_2026-10_mtd.csv", "*/commitments/commitments_register_2026-10-13.xlsx", "*/payment_schedule/payment_schedule_2026-10-13.csv", "*/income_calendar/income_calendar_2026-10-13.csv", "*/manager_outlook/*_distribution_outlook_2026-27.pdf"])
def k072(w):
    hz = d("2027-09-30"); ms = [f"{y}-{m:02d}" for y, m in months_iter(END, hz)]
    avg = q2(ssum(c["amount"] for c in w.calls if S0 <= d(c["due"]) <= S1) / 6); rows = {m: dict(distributions=ZERO, income=ZERO, calls=ZERO, expenses=ZERO) for m in ms}
    for c in w.calls:
        if END < d(c["due"]) <= hz: rows[month_key(d(c["due"]))]["calls"] += c["amount"]
    for m in ms[1:]: rows[m]["calls"] += avg
    for f in PRIVATE:
        v = latest(w, f)["value"]
        for q, r in zip(PAYOUT_Q, PAYOUT[f]): rows[q[:7]]["distributions"] += q2(v * D(str(r)) / 100)
    for e in w.X.income:
        if e["pay"] <= hz: rows[month_key(e["pay"])]["income"] += e["amount"]
    for i in w.X.sched:
        if i["status"] != "held" and i["due"] <= hz: rows[month_key(i["due"])]["expenses"] += eq(w, i["amount"], i["ccy"])
    run = ssum(cash_eq(w, e) for e in ENT); opening = run; out = {}; low = None
    for m in ms:
        r = rows[m]; close = run + r["distributions"] + r["income"] - r["calls"] - r["expenses"]; out[m] = dict(opening=run, **r, closing=close); run = close
        if low is None or close < low[1]: low = (m, close)
    floor = 3 * OFFICE_RULES["buffer_usd"]
    return Q("Whether the family needs to raise cash", dict(opening_cash_usd_eq=opening, monthly_call_assumption=avg, by_month=out, lowest_month=low[0], lowest_closing=low[1], floor=floor, cash_to_raise=max(ZERO, floor - low[1]), months_below_floor=[m for m in ms if out[m]["closing"] < floor], closing_sep_2027=run),
             "cash of 13 Oct (SGD at 1.3400) plus distributions (value x payout rate at each quarter end) plus coupons and dividends, less the noticed call 7, less future calls at the average of 1 Apr to 30 Sep (991,667 a month from November), less the payment schedule (held items left out); floor = three buffers")


@uc("uc-073-runway", ["*/expense_ledger/expense_ledger_2026-04_to_2026-09.xlsx", "*/administrator_cash/administrator_cash_2026-10_mtd.csv"])
def k073(w):
    spend = ssum(l["usd"] for l in w.X.ledger) / 6; c = ssum(cash_eq(w, e) for e in ENT); book = w.book(END); cat = {}
    for l in w.X.ledger: cat[l["cat"]] = cat.get(l["cat"], ZERO) + l["usd"]
    return Q("Whether spending is sustainable", dict(cash_usd_eq=c, average_monthly_spend=q2(spend), months_of_cash=round(float(c / spend), 2), months_of_cash_and_liquid_book=round(float((c + book) / spend), 2), liquid_book=book, six_month_spend_by_category=dict(sorted(cat.items()))),
             "cash of the three entities at 13 Oct (SGD at 1.3400) over the average monthly spending of April to September in the expense ledger (every payment in USD equivalent at its day's fixing)")


@uc("uc-074-boardpack", ["*/investment_reports/Evergreen_Office_Investment_Report_2026-09.pdf", "*/meeting_notes/ic_note_*.md", "*/meeting_notes/08_investment_committee_note_2026-10-08.md"])
def k074(w):
    nw, tw, cc, unf, am = ex(w, "morning-networth-note"), ex(w, "uc-044-twr"), ex(w, "uc-004-callcheck"), ex(w, "uc6-uncalled"), ex(w, "uc-022-amendlog")
    return Q("What to tell the board of the family", dict(net_worth_usd=nw["total_usd"], net_worth_sgd=nw["total_sgd"], net_worth_status="Evergreen Growth I is an estimate in the issued report", liquid_book_q3_return_pct=tw["q3_jul_sep_pct"], benchmark_since_1_apr_pct=tw["benchmark_since_1_apr_pct"],
                                                         cash_usd_eq=ssum(cash_eq(w, e) for e in ENT), call_7_shortfall_usd=cc["shortfall_usd"], uncalled_commitments=unf["uncalled_after_call_7"], statements_amended_after_last_report=am["open_count"],
                                                         sources=["investment_reports/Evergreen_Office_Investment_Report_2026-09.pdf", "custodian_positions", "administrator_cash", "notices/2026-10-13_C_call7.pdf", "commitments_register_2026-10-13.xlsx"]),
             "headline figures taken from the keys of the morning net worth note, the time-weighted return, the call check, the uncalled commitments and the amendment log, each of which traces to its own files")


def fund_value(w, f, pe): return w.known(f, pe.isoformat(), f"{END}T23:59:59Z")["value"]  # as the office knows it on 13 Oct


def investments(w, pe): return ssum(fund_value(w, f, pe) for f in FUND) + w.book(lastbd(pe))


def net_worth(w, x):
    bd = lastbd(x); cash_ = q2(ssum((w.bal[a][bd] if bd in w.bal[a] else w.open[a]) / (w.fx[bd] if v["ccy"] == "SGD" else 1) for a, v in ACCT.items()))
    loan = next((r["close"] for r in reversed(w.loan) if r["date"] <= x), D(3000000))
    return investments(w, x) + cash_ - loan


@uc("uc-075-yearwalk", ["*/investment_reports/Evergreen_Office_Investment_Report_*.pdf", "*/administrator_nav/administrator_export_*.xlsx", "*/bank_statements/*.xlsx"])
def k075(w):
    x0 = d("2026-03-31"); op, cl = net_worth(w, x0), net_worth(w, S1)
    buys = ssum((t["amt"] if t["side"] == "buy" else -t["amt"]) for t in w.trades if x0 < t["settle"] <= S1); book_gain = w.book(S1) - w.book(x0) - buys
    calls = ssum(c["amount"] for c in w.calls if x0 < d(c["due"]) <= S1); dist = ssum(x["paid"] for x in w.dists if x0 < d(x["pay"]) <= S1)
    fund_gain = ssum(fund_value(w, f, S1) - fund_value(w, f, x0) for f in FUND) - calls + dist
    fxd = lambda t: eq(w, t["amt"], ACCT[t["acct"]]["ccy"]) if ACCT[t["acct"]]["ccy"] == "USD" else q2(t["amt"] / w.fx[t["date"]])
    income = ssum(fxd(t) for t in w.tx if t["typ"] in ("coupon", "dividend", "interest") and S0 <= t["date"] <= S1)
    spend = ssum(l["usd"] for l in w.X.ledger if l["cat"] != "Debt service") + ssum(r["interest"] for r in w.loan)
    gains = book_gain + fund_gain; other = cl - op - (gains + income - spend)
    return Q("What to tell the family about the year", dict(period=[S0, S1], opening=op, investment_gains=gains, liquid_book_gain=book_gain, private_and_hedge_fund_gain=fund_gain, income=income, spending=spend, fx_and_other=other, closing=cl, adds_up=op + gains + income - spend + other == cl, fx_and_other_pct_of_closing=pct(other, cl, 3),
                                                            capital_calls_paid=calls, distributions_received=dist),
             "net worth = fund values as known on 13 Oct + liquid book + bank cash (SGD at the day's fixing) - term loan; gains = book value change less net purchases, plus fund value change less calls plus distributions; income = coupons, dividends and bank interest; spending = expense ledger without debt service, plus loan interest; fx and other is the balancing item. Six months of data (1 Apr to 30 Sep), not twelve")


@uc("uc-076-scorecard", ["*/manager_statements/*.pdf", "*/meeting_notes/*.md", "*/notices/*_call*.pdf", "*/manager_news/*.eml"])
def k076(w):
    out = {}
    for m in sorted({FUND[f]["manager"] for f in FUND if FUND[f]["manager"] != "MGR-MERIDIAN"}):
        fs = [f for f in FUND if FUND[f]["manager"] == m]; fees = ZERO; gain = ZERO; op = ZERO
        for f in fs:
            k0, k1 = w.known(f, "2026-03-31", "2026-04-30T00:00:00Z"), latest(w, f)
            cs = [c for c in w.calls if c["fund"] == f and d(c["due"]) <= END and c["id"] != "CALL-C-7"]; flows = ssum(c["amount"] for c in cs) - ssum(x["paid"] for x in w.dists if x["fund"] == f)
            gain += k1["value"] - k0["value"] - flows; op += k0["value"]; fees += ssum(c["fee"] for c in cs)
        ret = float(gain / op * 100); gross = gain + fees; drag = None if fees == 0 else (100.0 if gross <= 0 else float(fees / gross * 100))
        ss = [s for s in w.stmts if s["fund"] in fs and s["kind"] != "amended" and s["period"] >= "2026-03-31" and (s["received"] or s["status"] == "missing")]
        on_time = sum(1 for s in ss if s["received"] and d(s["received"]) <= d(s["due"])) / len(ss); flags = stmt_flags(w, m)["total"]
        parts = dict(returns=min(max(ret / 10, 0), 1), fees=0.5 if drag is None else 1 - min(drag / 50, 1), timeliness=on_time, watch=max(0.0, 1 - flags / 4)); score = round(100 * (0.4 * parts["returns"] + 0.2 * parts["fees"] + 0.2 * parts["timeliness"] + 0.2 * parts["watch"]), 1)
        out[MGR[m]["name"]] = dict(return_pct_since_1_apr=round(ret, 2), fee_drag_pct=None if drag is None else round(drag, 2), on_time_share=round(on_time, 3), watch_flags=flags, score=score, verdict="add" if score >= 75 else "keep" if score >= 50 else "review or exit")
    return Q("Which managers to keep, add to, or exit", dict(by_manager=out, weights=dict(returns=0.4, fees=0.2, timeliness=0.2, watch=0.2)),
             "score = 100 x (0.4 x return/10% capped at 1 + 0.2 x (1 - fee drag/50%) + 0.2 x on-time share + 0.2 x (1 - watch flags/4)); fee drag counts 100 when the gross gain is not positive and 0.5 when unknown (hedge funds); at least 75 add, 50 to 75 keep, below 50 review or exit")


@uc("uc-077-deals", ["*/deal_pipeline/deal_pipeline_2026-10-13.csv", "*/prospects/fund_teaser_Harborlight_Ventures_IV.pdf", "*/deal_pipeline/teaser_DL-*.pdf", "*/deal_pipeline/*.eml"])
def k077(w):
    rows = [dict(deal=x["name"], stage=x["stage"], days_in_stage=(END - x["entered"]).days, ticket=x["ticket"], stuck=(END - x["entered"]).days > STAGE_LIMIT_DAYS) for x in w.X.deals]
    st = {}
    for r in rows: st[r["stage"]] = st.get(r["stage"], 0) + 1
    return Q("Which deals to move forward or drop", dict(by_stage=dict(sorted(st.items())), deals=rows, stuck_over_60_days=[r["deal"] for r in rows if r["stuck"]], total_ticket=ssum(r["ticket"] for r in rows)), "13 Oct less the date the deal entered its stage; stuck above 60 days")


@uc("uc-078-redemption", ["*/fund_documents/kestrel_H*_redemption_terms.pdf", "*/manager_statements/kestrel_H*.pdf", "reference/kestrel_ridge_ddq_2026.pdf"])
def k078(w):
    out = {}
    for f, t in HF_TERMS.items():
        v = latest(w, f)["value"]; first = None
        for y, m in months_iter(END, d("2028-12-31")):
            if t["dealing"] == "quarterly" and m % 3: continue
            deal = lastbd(month_end(f"{y}-{m:02d}"))
            if deal >= d(t["lockup_end"]) and prev_bd(deal - dt.timedelta(days=t["notice"])) >= END: first = deal; break
        notice = prev_bd(first - dt.timedelta(days=t["notice"])); pay = next_bd(first + dt.timedelta(days=t["payout"])); now = q2(v * (100 - t["holdback"]) / 100)
        out[pname(f)] = dict(latest_value=v, dealing_date=first, send_notice_by=notice, days_to_send=(notice - END).days, cash_date=pay, cash_at_payment=now, held_back_until_audit=v - now)
    return Q("When the notice must be sent and the cash to expect", dict(by_fund=out), "first dealing date on or after the lock-up end whose notice deadline (dealing date less the notice days, back to a business day) is not before 13 Oct; cash = dealing date plus the payment lag, less the holdback")


@uc("uc-079-rebalance", ["reference/Evergreen_Investment_Allocation_Policy_v2026.1.pdf", "*/target_allocation/interim_targets_EG-LIQUID_2026-10-08.xlsx", "*/custodian_positions/positions_20261013.csv"])
def k079(w):
    book = w.book(END); cur = {}
    for k, s in w.sec.items(): c = s["asset_class"] or "convertible"; cur[c] = cur.get(c, ZERO) + w.value(k, END)
    rows = {c: dict(current=cur.get(c, ZERO), current_pct=pct(cur.get(c, ZERO), book, 2), target_pct=t, target=q2(book * t / 100), trade=q2(book * t / 100) - cur.get(c, ZERO)) for c, t in TARGET_ALLOC.items()}
    return Q("Which holdings to sell or buy and how much", dict(book=book, targets_status="proposed at the 8 Oct committee, not signed: a suggestion only", by_class=rows, net_trade=ssum(r["trade"] for r in rows.values())), "target percent of the 13 Oct liquid book less the current value of the class; positive = buy, negative = sell; the policy itself sets bands, not targets")


@uc("uc-080-vintage", ["*/commitments/commitments_register_2026-10-13.xlsx", "reference/fund_terms.csv"])
def k080(w):
    by, funds = {}, {}
    for f in PRIVATE: y = COMMIT_DATE[f][:4]; by[y] = by.get(y, ZERO) + D(TERMS[f][0]); funds.setdefault(y, []).append(pname(f))
    tot = ssum(by.values()); big = max(by, key=by.get)
    return Q("Whether commitments are too bunched in one year", dict(by_year={y: dict(commitment=v, share_pct=pct(v, tot, 2), funds=funds[y]) for y, v in sorted(by.items())}, total=tot, largest_year=big, largest_share_pct=pct(by[big], tot, 2)), "commitment amount of each of the eight private funds by the year of its commitment date (fund terms)")


# ---------------------------------------------------------------------------------------------------- office and people
@uc("uc-081-payroll", ["*/payroll_drafts/payroll_run_2026-10_draft.xlsx", "*/payroll/payroll_2026-09.xlsx", "*/bank_statements/HB_HOLD_SGD_2026-09.xlsx"])
def k081(w):
    sep = w.payroll[-1]; X = w.X; staff = {n: g for n, t, g in X.staff}
    net = ssum(q2(g * D("0.80")) for n, t, g in X.draft); emp = ssum(q2(g * D("0.17")) for n, t, g in X.draft); sep_cost = sep["net"] + ssum(r[4] for r in sep["rows"])
    flags = [dict(employee=n, kind="not in the staff register", gross=g) if n not in staff else dict(employee=n, kind="gross changed", change_pct=pct(g - staff[n], staff[n], 1)) for n, t, g in X.draft if n not in staff or g != staff[n]]
    paid = -next(t["amt"] for t in w.tx if t["ref"] == "PAY-202609")
    return Q("Whether to release the pay file", dict(draft_net=net, draft_employer_cpf=emp, draft_total_cost=net + emp, september_net=sep["net"], september_net_paid_per_bank=paid, september_total_cost=sep_cost, change_pct=pct(net + emp - sep_cost, sep_cost, 2), flags=flags, release=not flags),
             "net pay (80 percent of gross) plus employer CPF (17 percent) of the October draft against September's run; any line not on the staff register or with a changed gross is a flag, and the file is not released while a flag is open")


@uc("uc-082-covergap", ["*/insurance_schedule/insurance_schedule_2026-10-01.pdf", "*/property_valuations/valuation_RA-*.pdf"])
def k082(w):
    rows = []
    for a in w.X.assets:
        ins = [(p["ccy"], INSURED[p["id"]][1]) for p in w.policies if INSURED[p["id"]][0] == a["id"]]; si = ssum(eq(w, v, c) for c, v in ins)
        rows.append(dict(asset=a["name"], appraised_usd=asset_usd(w, a), insured_usd=si, gap_usd=si - asset_usd(w, a), status="no policy" if not ins else "under-insured" if si < asset_usd(w, a) else "covered"))
    return Q("Whether to raise or lower cover", dict(by_asset=rows, under_insured=[r["asset"] for r in rows if r["status"] == "under-insured"], no_policy=[r["asset"] for r in rows if r["status"] == "no policy"], total_gap_usd=ssum(r["gap_usd"] for r in rows)),
             "sum insured of the policies linked to the asset less its latest appraisal, both in USD (SGD at 1.3400)")


@uc("uc-083-taxcal", ["*/tax_calendar/tax_calendar_2026-27.xlsx", "*/tax_notices/eci_notice_EG-HOLD_2026.pdf"])
def k083(w):
    due = [dict(id=t[0], entity=ENT[t[1]], obligation=t[2], due=d(t[3]), days=(d(t[3]) - END).days, prepared_by=t[4], status=t[7]) for t in TAX if END < d(t[3]) <= END + dt.timedelta(days=60)]
    late = [dict(id=t[0], entity=ENT[t[1]], obligation=t[2], due=d(t[3]), days_overdue=(END - d(t[3])).days, prepared_by=t[4], status=t[7]) for t in TAX if d(t[3]) <= END and t[7] != "filed"]
    by = {}
    for r in due: by[r["entity"]] = by.get(r["entity"], 0) + 1
    return Q("Which filings and payments are due and who prepares them", dict(due_in_60_days=due, count_by_entity=by, overdue=late), "tax calendar items with a due date within 60 days of 13 Oct, and items past their due date that are not filed")


@uc("uc-084-taxest", ["*/tax_calendar/tax_calendar_2026-27.xlsx", "*/trading_export/trading_export_2026*.csv", "*/notices/*_distribution.pdf"])
def k084(w):
    out = {}
    for e in ENT:
        inc = ssum((t["amt"] if ACCT[t["acct"]]["ccy"] == "USD" else q2(t["amt"] / w.fx[t["date"]])) for t in w.tx if t["typ"] in ("coupon", "dividend", "interest") and ACCT[t["acct"]]["ent"] == e and S0 <= t["date"] <= END)
        inc += ssum(x["paid"] for x in w.dists if x["ent"] == e and x["kind"] == "income" and d(x["pay"]) <= END)
        gains = ssum(r["gain"] for r in w.X.realised) if e == "EG-TRUST" else ZERO
        credit = ssum(x["amount"] - x["paid"] for x in w.dists if x["ent"] == e and d(x["pay"]) <= END)
        ri, rg = TAX_RATES[e]; tax = inc * ri + max(gains, ZERO) * rg
        out[ENT[e]] = dict(income=inc, realised_gains=gains, rate_on_income=ri, rate_on_gains=rg, tax_before_credits=q2(tax), credits=credit, tax_to_set_aside=max(ZERO, q2(tax) - credit))
    return Q("How much cash to set aside for tax", dict(period=[S0, END], by_entity=out, total_to_set_aside=ssum(v["tax_to_set_aside"] for v in out.values())),
             "income = coupons, dividends, bank interest and income distributions received 1 Apr to 13 Oct; realised gains from the sells matched first-in first-out to the lots; times the 2026 rates of the tax calendar; credit = tax withheld on fund distributions (the 12,500 on Fund A)")


@uc("uc-085-grants", ["*/grant_ledger/grant_ledger_2026.xlsx", "*/bank_statements/HB_HOLD_USD_2026-0[5-9].xlsx"])
def k085(w):
    paid = ssum(g["amount"] for g in w.grants if g["state"] == "paid"); pl = ssum(g["amount"] for g in w.grants if g["state"] == "pledged")
    return Q("Whether to approve more grants this year", dict(budget=GRANT_BUDGET, paid=paid, pledged=pl, used=paid + pl, used_pct=pct(paid + pl, GRANT_BUDGET, 1), remaining=GRANT_BUDGET - paid - pl, paid_matches_bank=paid == -ssum(t["amt"] for t in w.tx if t["typ"] == "grant")), "paid plus pledged grants over the annual budget; paid grants agree with the bank debits")


@uc("uc-086-grantappr", ["*/grant_requests/grant_request_REQ-2026-06.pdf", "*/grant_requests/2026-10-09_REQ-2026-06.eml", "*/grant_ledger/grant_ledger_2026.xlsx"])
def k086(w):
    g = GRANT_REQUEST; used = ssum(x["amount"] for x in w.grants); reg = d(g["registered"]); months_ = (END.year - reg.year) * 12 + END.month - reg.month - (END.day < reg.day)
    c7 = ssum(c["amount"] for c in w.calls if c["ent"] == "EG-HOLD" and END < d(c["due"]) <= END + dt.timedelta(days=30)); hold = cash(w, "EG-HOLD", "USD", "admin")
    ok = dict(within_budget=g["amount"] <= GRANT_BUDGET - used, charity_old_enough=months_ >= GRANT_POLICY["min_registration_months"], cash_covers=hold - c7 - g["amount"] >= OFFICE_RULES["buffer_usd"])
    return Q("Whether to pay the grant", dict(request=g["id"], amount=g["amount"], remaining_budget=GRANT_BUDGET - used, charity_registered_months=months_, required_months=GRANT_POLICY["min_registration_months"], holdings_usd_cash=hold, calls_due_30_days=c7, cash_after_request_and_calls=hold - c7 - g["amount"], checks=ok, pay=all(ok.values())),
             "request against the remaining 2026 budget, the age of the charity's registration (policy 24 months) and Holdings USD cash less the call due in 30 days less the request, kept above the 250,000 buffer")


def trust_year(w):
    inc = ssum((t["amt"] if ACCT[t["acct"]]["ccy"] == "USD" else q2(t["amt"] / w.fx[t["date"]])) for t in w.tx if ACCT[t["acct"]]["ent"] == "EG-TRUST" and t["typ"] in ("coupon", "dividend", "interest") and S0 <= t["date"] <= END)
    exp = ssum((-t["amt"] if ACCT[t["acct"]]["ccy"] == "USD" else q2(-t["amt"] / w.fx[t["date"]])) for t in w.tx if ACCT[t["acct"]]["ent"] == "EG-TRUST" and (t["typ"] in ("fee", "bank_fee", "property") or t["ref"].startswith("VP-FEE")) and S0 <= t["date"] <= END)
    return inc, exp


@uc("uc-087-trustdist", ["*/trust_deed/evergreen_family_trust_deed.pdf", "*/administrator_cash/administrator_cash_2026-10_mtd.csv", "*/family_allowances/allowance_schedule_2026-*.xlsx"])
def k087(w):
    inc, exp = trust_year(w); dist = inc - exp; cap = q2(dist * D(TRUST_DEED["payout_cap"]) / 100); rows = {}
    for n, sh in TRUST_DEED["shares"].items():
        paid = -ssum(t["amt"] for t in w.tx if t["typ"] == "allowance" and t["cpty"] == n and S0 <= t["date"] <= END); room = q2(cap * D(sh) / 100)
        rows[n] = dict(share_pct=sh, room=room, paid=paid, left=room - paid, over=paid > room)
    return Q("Whether the trust pays what its deed allows", dict(trust_year_start=S0, trust_income=inc, trust_expenses=exp, distributable_income=dist, payout_cap_pct=TRUST_DEED["payout_cap"], distributable_cap=cap, by_beneficiary=rows, over_distributed=[n for n, r in rows.items() if r["over"]]),
             "distributable income = coupons, dividends and interest of the Trust accounts less fees, bank fees and property costs, 1 Apr to 13 Oct; the deed lets the trustees pay out 70 percent of it, split by share; allowances paid count as distributions")


@uc("uc-088-estateliq", ["*/trust_deed/evergreen_family_trust_deed.pdf", "*/estate_planning/transfer_tax_memo_2026.pdf", "*/property_valuations/valuation_RA-*.pdf"])
def k088(w):
    inv = investments(w, S1); c = ssum(cash_eq(w, e) for e in ENT); ra = ssum(asset_usd(w, a) for a in w.X.assets); loan = w.loan[-1]["close"]
    estate = inv + c + ra - loan; tax = q2(max(ZERO, estate - ESTATE["exemption"]) * ESTATE["rate"])
    liquid = c + w.book(END) + latest(w, "L1")["value"] + latest(w, "L2")["value"] - loan
    return Q("Whether the family could meet a transfer tax from liquid assets", dict(estate_value=estate, investments_30_sep=inv, cash=c, real_assets=ra, loan=loan, exemption=ESTATE["exemption"], rate=ESTATE["rate"], transfer_tax=tax, liquid_assets_after_debt=liquid, cover=round(float(liquid / tax), 2), can_meet=liquid >= tax),
             "estate = fund values as known on 13 Oct + liquid book (30 Sep) + cash (13 Oct) + latest real asset appraisals - term loan; tax = (estate - 5,000,000) x 15 percent; liquid = cash + liquid book + the two index funds - loan")


@uc("uc-089-expapp", ["*/expense_ledger/expense_ledger_2026-04_to_2026-09.xlsx", "reference/office_rules.csv"])
def k089(w):
    lim = dict(APPROVERS); bad = [dict(reference=l["ref"], payee=l["payee"], usd=l["usd"], approver=l["approver"], limit=lim[l["approver"]]) for l in w.X.ledger if l["usd"] > lim[l["approver"]]]
    by = {}
    for l in w.X.ledger: by[l["approver"]] = by.get(l["approver"], 0) + 1
    return Q("Which approval limits to set and who may approve", dict(limits=lim, payments=len(w.X.ledger), over_limit=bad, approvals_by_person=dict(sorted(by.items()))), "ledger payments whose USD equivalent exceeds the limit of the person who approved them")


@uc("uc-090-offcost", ["*/expense_ledger/expense_ledger_2026-04_to_2026-09.xlsx", "*/office_budget/office_budget_2026.xlsx", "*/payroll/payroll_2026-0[4-9].xlsx", "*/invoices/*.pdf"])
def k090(w):
    act = {}
    for l in w.X.ledger: act[l["cat"]] = act.get(l["cat"], ZERO) + l["usd"]
    rows = {c: dict(actual=act.get(c, ZERO), budget_half_year=D(b) / 2, variance=act.get(c, ZERO) - D(b) / 2, over=act.get(c, ZERO) > D(b) / 2) for c, b in BUDGET.items()}
    return Q("Whether the office costs more than planned", dict(by_category=rows, actual=ssum(r["actual"] for r in rows.values()), budget=ssum(r["budget_half_year"] for r in rows.values()), over_budget=[c for c, r in rows.items() if r["over"]], uncategorised=ssum(v for c, v in act.items() if c not in BUDGET)),
             "expense ledger of April to September by category (USD at the day's fixing) against half of the annual budget set in April")


@uc("uc-091-jml", ["*/access_register/access_register_2026-10-13.csv", "*/access_register/2026-10-02_joiner_leaver.eml"])
def k091(w):
    X = w.X; req = {"Harbor", "OMS", "Shared drive"}
    return Q("Which access to give or remove", dict(granted_without_approver=[dict(person=g["person"], system=g["system"], permission=g["permission"]) for g in X.access if not g["approver"]], leaver=X.leaver["name"], leaver_access_to_remove=[g["system"] for g in X.access if g["person"] == X.leaver["name"]],
                                                    joiner=X.joiner["name"], joiner_access_not_requested=[g["system"] for g in X.access if g["person"] == X.joiner["name"] and g["system"] not in req]),
             "grants with no approver in the register; every grant still held by the leaver; grants of the joiner outside the three systems the HR mail asked for")


@uc("uc-092-accessrev", ["*/access_register/access_register_2026-10-13.csv"])
def k092(w):
    st = [dict(person=g["person"], system=g["system"], last_used=g["last_used"], days_unused=(END - g["last_used"]).days) for g in w.X.access if (END - g["last_used"]).days > 90 and g["person"] != w.X.leaver["name"]]
    return Q("Which access to remove", dict(grants_reviewed=len(w.X.access), not_used_in_90_days=st, count=len(st)), "register grants whose last use is more than 90 days before 13 Oct (the leaver's grants are handled by the joiner and leaver card)")


@uc("uc-093-onbmgr", ["*/onboarding/*"])
def k093(w):
    miss = [o[0] for o in ONBOARD if o[1] == "missing"]
    return Q("Whether every document and feed is in place before the first call", dict(items=len(ONBOARD), complete=sum(1 for o in ONBOARD if o[1] == "complete"), missing=miss, ready=not miss), "rows of the onboarding checklist by status")


@uc("uc-094-onbbank", ["*/bank_forms/*"])
def k094(w):
    a = ACCOUNT_FORM; hof = next(n for n, t, g in PEOPLE if t == "Head of Finance"); sig = [s.split(" (")[0] for s in a["signatories"]]
    meets = len(sig) >= SIGNING["min_signatories"] and hof in sig
    steps = [(s, meets if v is None else v) for s, v in ACCOUNT_STEPS]
    return Q("Whether the account and its signatories are approved", dict(signatories=sig, required_head_of_finance=hof, missing_signatory=None if hof in sig else hof, meets_signing_policy=meets, steps=[dict(step=s, done=v) for s, v in steps], outstanding=[s for s, v in steps if not v], approved=all(v for s, v in steps)),
             "signatories on the opening form against the signing policy (two or more, one the Head of Finance); the checklist steps")


@uc("uc-095-sopreview", ["*/sops/sop_*.md"])
def k095(w):
    rows = [dict(sop=s["name"], owner=s["owner"], last_reviewed=s["reviewed"], age_days=(END - s["reviewed"]).days, due=(END - s["reviewed"]).days > 365) for s in w.X.sops]
    return Q("Which procedures to review", dict(sops=rows, to_review=[r["sop"] for r in sorted(rows, key=lambda r: -r["age_days"]) if r["due"]]), "13 Oct 2026 less the last review date in each SOP, flagged above 365 days")


def sop_failures(w):
    cl = sum(1 for c in close_items(w) if c["late"]); rec = [r for r in RECV if r[1] in ("bank_statement", "manager_statement") and r[5] != "received"]
    return {"month-end-report": cl, "capital-call-payment": sum(1 for a in w.approvals if not a["approved"]) + sum(1 for c in w.calls if c["changed"]), "bank-statement-chase": len(rec),
            "vendor-payment-run": sum(1 for i in w.invoices if i["dup"]) + sum(1 for i in w.invoices if i["changed"]) + sum(1 for f in w.fee_invoices if f["amount"] != f["expected"])}


@uc("uc-096-automation", ["*/sops/sop_*.md", "*/exception_log/exception_log_2026-10-13.csv", "received_log_all.csv"])
def k096(w):
    fl = sop_failures(w); rows = []
    for s in w.X.sops:
        man = sum(x["minutes"] for x in s["steps"] if x["manual"]); allm = sum(x["minutes"] for x in s["steps"]); f = fl.get(s["id"], 0)
        rows.append(dict(sop=s["name"], runs_per_month=s["runs"], manual_minutes_per_month=man * s["runs"], total_minutes_per_month=allm * s["runs"], failures_6_months=f, score=man * s["runs"] * 6 + f * SOP_FAIL_MIN,
                         slowest_manual_step=max((x for x in s["steps"] if x["manual"]), key=lambda x: x["minutes"])["step"]))
    rows.sort(key=lambda r: (-r["score"], r["sop"]))
    return Q("Which process to automate", dict(ranking=rows, automate_next=rows[0]["sop"]), "score = manual minutes per run x runs per month x 6 months + 45 minutes of rework per failure; failures counted from the late close steps, late or missing statements, unapproved or changed-account calls and the planted invoice problems")


@uc("uc-097-kycrefresh", ["*/kyc_register/kyc_register_2026-10-13.csv", "*/kyc_register/kyc_pack_Evergreen_Holdings_2026.pdf"])
def k097(w):
    from .more import KYC_DOCS
    rows = [dict(entity=ENT[e], counterparty=cp, document=doc, expires=d(x), days_left=(d(x) - END).days) for e, cp, doc, i, x in KYC_DOCS]; rows.sort(key=lambda r: r["days_left"])
    return Q("Which documents to refresh before the bank or manager freezes the account", dict(expiring_in_90_days=[r for r in rows if 0 <= r["days_left"] <= 90], expired=[r for r in rows if r["days_left"] < 0], documents=len(rows)), "expiry date less 13 Oct 2026; within 90 days, or already past")


@uc("uc-098-wordlist", ["*/glossary/*"])
def k098(w):
    have = set()
    for t, al, df in GLOSSARY: have.add(t.lower()); have |= {a.strip().lower() for a in al.split(";") if a.strip()}
    terms = sorted({t for src, t in GLOSSARY_PROPOSED}); known = [t for t in terms if t in have]; new = [t for t in terms if t not in have]
    return Q("Whether to add a word to the language list", dict(proposed=terms, proposals_made=len(GLOSSARY_PROPOSED), distinct_terms=len(terms), already_in_list=known, to_add=new, list_size=len(GLOSSARY)), "distinct terms proposed in the email and the meeting note against the terms and aliases of the office word list")


@uc("uc-099-newfeed", ["*/new_feed/*"])
def k099(w):
    cols = FEED["columns"]; amb = [c[0] for c in cols if not c[2]]
    return Q("Whether the new feed is designed, mapped and safe to go live", dict(columns=len(cols), mapped_with_confidence=sum(1 for c in cols if c[2]), share_mapped_pct=pct(sum(1 for c in cols if c[2]), len(cols), 1), in_doubt=amb, rows_in_sample=3, safe_to_go_live=not amb),
             "each column of the file against the model fields by name and content; Value could be market or book value, Dt a valuation, trade or settle date")


@uc("uc-100-famaccess", ["*/family_access/*"])
def k100(w):
    rank = {"none": 0, "summary": 1, "full": 2}; rows = {}
    for m, pol in FAMILY_POLICY.items():
        over = {ENT[e]: dict(granted=lv, allowed=pol[e]) for e, lv in FAMILY_GRANTED[m].items() if rank[lv] > rank[pol[e]]}
        rows[m] = dict(allowed={ENT[e]: v for e, v in pol.items() if v != "none"}, granted={ENT[e]: v for e, v in FAMILY_GRANTED[m].items()}, over_granted=over)
    r = FAMILY_REQUEST; ok = rank[r["level"]] <= rank[FAMILY_POLICY[r["member"]][r["entity"]]]
    return Q("What each family member may see", dict(by_member=rows, over_grants=[m for m, v in rows.items() if v["over_granted"]], request=dict(member=r["member"], entity=ENT[r["entity"]], level=r["level"], allowed=ok)), "views granted against the family access policy, per member and entity (none < summary < full)")
