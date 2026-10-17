"""Answer keys, computed from the same World that wrote the files. Nothing here is typed by hand: every expected value is a calculation on w.
Keyed by use case id (packs/family_office/1/use_cases_100.yaml, priority 1..50, plus the role-build uc8), then question, then expected values and how."""
import datetime as dt
import functools
from decimal import Decimal as D
from pathlib import Path

import yaml

from .files import RECV, month_end, months, pname, report_lines, status_word
from .files2 import CONTRACTS, cash_breaks, close_items
from .world import (ACCT, BANK, DAYS, END, ENT, FUND, MGR, OFFICE_RULES, PRIVATE, ROOT, TERMS, U, ADMIN_RATE, CUST_RATE, add_bd, bdays, d, is_bd, lastbd, q2, ym)

PACK = ROOT / "packs/family_office/1/use_cases_100.yaml"
KEYS = {}
FILES = {}  # use case id -> globs (relative to the output folder)


def num(x):
    if x is None or isinstance(x, (bool, str, list, dict)): return x
    x = D(x)
    return int(x) if x == x.to_integral_value() else float(round(x, 4))


def deep(v):
    if isinstance(v, dict): return {k: deep(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)): return [deep(x) for x in v]
    if isinstance(v, (D, float, int)) and not isinstance(v, bool): return num(v)
    if isinstance(v, dt.date): return v.isoformat()
    return v


def uc(id_, files):
    def deco(fn):
        FILES[id_] = files
        KEYS[id_] = fn
        return fn
    return deco


def Q(q, expected, how): return {q: dict(expected=expected, how=how)}


def pct(a, b, dp=4): return float(round(D(a) / D(b) * 100, dp))


def bdays_after(a, b):  # business days after a up to and including b
    return len([x for x in bdays(a + dt.timedelta(days=1), b)]) if b > a else 0


C7 = lambda w: next(c for c in w.calls if c["id"] == "CALL-C-7")
NAV_CUT = lambda pe: f"{add_bd(d(pe), 2)}T06:00:00Z"


def admin_rows(w, pe):
    """Administrator pack rows at pe: {fund or sec: (portfolio, value, status)}."""
    out = {}
    for k in w.sec: out[k] = ("EG-LIQUID", w.value(k, d(pe)), "Priced")
    for f in FUND:
        k = w.known(f, pe, NAV_CUT(pe)); out[f] = (FUND[f]["portfolio"], k["value"] if k else D(0), status_word(k, pe))
    return out


def latest(w, f, asof=None):
    return w.known(f, "2026-12-31", f"{asof or END}T23:59:59Z")


def cash(w, e, c, src="bank", x=END): return w.cash(e, c, x, src)


# ---------------------------------------------------------------------------------------------------- the capital-call story (priority 1 to 7)
@uc("uc-001-noticelog", ["*/notices/2026-10-13_C_call7.pdf", "*/emails/2026-10-13_call_C_7.eml"])
def k001(w):
    c = C7(w)
    return {**Q("Which fund, how much and by when?", dict(fund=pname("C"), investor=ENT[c["ent"]], amount_usd=c["amount"], due=c["due"], new_investments=c["invest"], management_fee=c["fee"], account_ending=c["acct"]),
                "Read from the generated notice CALL-C-7 (world.calls)"),
            **Q("Notices logged and not yet recorded", dict(count=1, notices=["CALL-C-7"]), "Notices dated on or before 13 Oct minus notices recorded in the commitments register as at 13 Oct (the register shows call 7 as 'noticed, not yet recorded')")}


@uc("uc-002-callrecord", ["*/notices/2026-10-13_C_call7.pdf", "*/commitments/commitments_register_2026-10-13.xlsx", "reference/fund_terms.csv"])
def k002(w):
    c = C7(w); com = D(TERMS["C"][0]); before = D(TERMS["C"][1]) + sum((x["amount"] for x in w.calls if x["fund"] == "C" and x["id"] != c["id"]), D(0))
    pctv = D(TERMS["C"][2]); fee_terms = q2(com * pctv / 100)
    return {**Q("Does call 7 fit what we committed to Cedarpoint Ventures III, and what is left after it?", dict(commitment=com, called_before_call_7=before, called_after_call_7=before + c["amount"], unfunded_after_call_7=com - before - c["amount"], within_commitment=c["amount"] <= com - before),
                "commitment 10,000,000 minus called (3,500,000 before April + call 5 + call 6 = 6,000,000; plus call 7)"),
            **Q("Fee part against fund terms", dict(fee_on_notice=c["fee"], fee_per_terms=fee_terms, matches=c["fee"] == fee_terms), "fee % of commitment per billing (reference/fund_terms.csv) times commitment")}


@uc("uc6-liquidity", ["*/administrator_cash/administrator_cash_2026-10_mtd.csv", "*/commitments/commitments_register_2026-10-13.xlsx", "*/notices/2026-10-13_C_call7.pdf"])
def k003(w):
    ent = {e: dict(usd=cash(w, e, "USD", "admin"), sgd=cash(w, e, "SGD", "admin")) for e in ENT}
    due = {e: {"30": D(0), "60": D(0)} for e in ENT}
    for c in w.calls:
        if END < d(c["due"]) <= END + dt.timedelta(days=60):
            for k, n in (("30", 30), ("60", 60)):
                if d(c["due"]) <= END + dt.timedelta(days=n): due[c["ent"]][k] += c["amount"]
    return {**Q("What is our cash by entity today?", {ENT[e]: v for e, v in ent.items()}, "administrator cash on 13 Oct 2026 per entity and currency (equals the bank balances on that day)"),
            **Q("Calls due in 30 and 60 days", {ENT[e]: v for e, v in due.items()}, "sum of recorded and noticed calls with due date inside the window, per entity")}


@uc("uc-004-callcheck", ["*/notices/2026-10-13_C_call7.pdf", "*/administrator_cash/administrator_cash_2026-10_mtd.csv", "*/commitments/commitments_register_2026-10-13.xlsx", "reference/office_rules.csv"])
def k004(w):
    c = C7(w); usd, sgd, fx = cash(w, "EG-HOLD", "USD"), cash(w, "EG-HOLD", "SGD"), w.fx[END]; short = c["amount"] + OFFICE_RULES["buffer_usd"] - usd
    return {**Q("Can Holdings pay the Cedarpoint call on the 23rd?", dict(holdings_usd=usd, holdings_sgd=sgd, sgd_in_usd=q2(sgd / fx), call=c["amount"], buffer=OFFICE_RULES["buffer_usd"], shortfall_usd=short, sgd_to_convert=q2(short * fx),
                                                                      pays_from_usd_alone=short <= 0, needs_approval_over_500000=c["amount"] > OFFICE_RULES["approval_over_usd"]),
                "shortfall = 1,250,000 + 250,000 buffer - 1,230,000 USD cash; SGD to convert = shortfall x WMR 4pm 1.3400 (13 Oct)"),
            **Q("Notice against commitment", dict(fits=True, unfunded_before=D(TERMS["C"][0]) - D(TERMS["C"][1]) - sum((x["amount"] for x in w.calls if x["fund"] == "C" and x["id"] != c["id"]), D(0))), "notice amount <= unfunded before the call")}


@uc("uc-005-benefcheck", ["*/notices/2026-10-13_C_call7.pdf", "*/emails/2026-10-13_internal_sam.eml", "reference/standing_instructions.csv"])
def k005(w):
    c = C7(w); paid = [x["desc"] for x in w.tx if x["ev"] in ("CALL-C-5", "CALL-C-6") and x["typ"] == "capital_call"]
    return {**Q("Cedarpoint now says to wire to an account ending 4471. Is that really them?", dict(changed=c["acct"] != c["std_acct"], old_ending=c["std_acct"], new_ending=c["acct"], earlier_calls_paid_to=[x[-4:] for x in paid], callback_required=True),
                "notice account vs standing instruction on file (reference/standing_instructions.csv); calls 5 and 6 were paid to the standing account"),
            **Q("Payments on hold awaiting call-back", dict(count=1, payment="CALL-C-7"), "payments to a changed account with no call-back recorded")}


@uc("uc-006-fxneed", ["*/fx_confirmations/FXS-*_confirmation.pdf", "*/fx_rates/fx_usdsgd_2026101*.csv", "*/administrator_cash/administrator_cash_2026-10_mtd.csv"])
def k006(w):
    rows = [dict(ref=c["id"], usd=c["usd"], rate=c["rate"], fixing=c["fix"], diff_pct=pct(c["rate"] - c["fix"], c["fix"], 4), within_0_1_pct=abs(c["rate"] - c["fix"]) / c["fix"] <= D("0.001"), confirmation=c["confirm"]) for c in w.convs]
    paid = [dict(call=c["id"], due=c["due"], amount=c["amount"], paid=any(t["ev"] == c["id"] and t["typ"] == "capital_call" and t["amt"] == -c["amount"] for t in w.tx)) for c in w.calls if d(c["due"]) <= END]
    return {**Q("We hold SGD and need USD for the call. How much do we convert, and did the bank trade at the right rate?", dict(sgd_to_convert_for_call_7=q2(D(270000) * w.fx[END]), planning_rate=w.fx[END], conversions=rows),
                "conversions in the generated bank/OMS data against the WMR 4pm fixing of the day (rate = fixing + 0.0005, inside 0.1 percent)"),
            **Q("Call status after the bank statement", dict(calls_due_to_date=paid), "a call is Paid when a debit of the exact amount appears on the due date (call 7 is not due yet)"),
            **Q("Conversions without a bank confirmation", dict(refs=[c["id"] for c in w.convs if not c["confirm"]]), "conversions in the OMS/bank data with no FX confirmation PDF")}


def committed(w, f, upto=None):
    cs = [c for c in w.calls if c["fund"] == f and (upto is None or c["notice"] <= upto)]
    called = D(TERMS[f][1]) + sum((c["amount"] for c in cs), D(0)); return D(TERMS[f][0]), called, D(TERMS[f][0]) - called


@uc("uc-007-pacing", ["*/commitments/commitments_register_2026-10-13.xlsx", "*/notices/2026-10-13_C_call7.pdf", "reference/Evergreen_Investment_Allocation_Policy_v2026.1.pdf"])
def k007(w):
    by = {pname(f): dict(committed=committed(w, f)[0], called=committed(w, f)[1], unfunded=committed(w, f)[2]) for f in PRIVATE}
    return {**Q("What's our unfunded commitment across all funds?", dict(by_fund=by, total_unfunded=sum((committed(w, f)[2] for f in PRIVATE), D(0)), cedarpoint_iii_unfunded=committed(w, "C")[2]),
                "commitment minus called, with call 7 counted (notice dates up to 13 Oct)"),
            **Q("Room to commit", dict(private_markets_budget=None, note="Policy v2026.1 sets no private-markets budget; there is nothing to compute"), "read from the policy PDF (reference/): section 2 says targets are not set")}


@uc("uc-008-payrun", ["*/invoices/*FEE-*.pdf", "*/invoices/2026-09-14_summit_STA-2609.pdf", "*/notices/2026-10-13_C_call7.pdf"])
def k008(w):
    items = [dict(ref=i["no"], payee=i["vendor"], amount=i["amt"], ccy=i["ccy"], due=i["due"]) for i in w.invoices if END <= i["due"] <= END + dt.timedelta(days=10) and not i["dup"]]
    items += [dict(ref=f["id"], payee=f["vendor"], amount=f["amount"], ccy="USD", due=f["due"], variance=f["amount"] - f["expected"]) for f in w.fee_invoices if END <= f["due"] <= END + dt.timedelta(days=10)]
    c = C7(w); items.append(dict(ref=c["id"], payee=pname("C"), amount=c["amount"], ccy="USD", due=d(c["due"])))
    for i in items:
        usd = i["amount"] if i["ccy"] == "USD" else i["amount"] / w.fx[END]
        i["state"] = "hold: invoice above fee schedule" if i.get("variance") else ("waiting for approval" if usd > OFFICE_RULES["approval_over_usd"] else "ready")
    return Q("Which payments to release", dict(items=items, states={s: sum(1 for i in items if i["state"] == s) for s in sorted({i["state"] for i in items})}),
             "payments due between 13 and 23 Oct; over 500,000 USD waits for the Head of Finance; an invoice above its fee schedule is held")


# ---------------------------------------------------------------------------------------------------- the ten existing builds
@uc("uc9-sop", ["reference/month_end_process_narrative.md", "reference/handover_email_mei_to_raj.txt"])
def k009(w):
    st = U["process"]["steps"]
    return Q("What are the steps of the month-end report process and who does each one?", dict(steps=len(st), owners={s["name"]: s["who"] for s in st}, manual_steps_flagged_for_automation=U["process"]["manual_steps_flagged_for_automation"]), "steps of the process narrative reference file (10-use-case universe)")


@uc("uc-010-bankexp", ["*/bank_statements/*_2026-10_mtd.xlsx"])
def k010(w):
    fx = w.fx[END]; tot = {}
    for a, v in ACCT.items():
        usd = w.bal[a][END] / (fx if v["ccy"] == "SGD" else 1); tot[v["bank"]] = tot.get(v["bank"], D(0)) + usd
    grand = sum(tot.values(), D(0))
    return Q("Whether too much cash sits at one bank", dict(usd_equivalent_by_bank={BANK[b]: q2(v) for b, v in tot.items()}, share_pct={BANK[b]: pct(v, grand, 2) for b, v in tot.items()}, total_usd_eq=q2(grand)),
             "closing balances of the 12 accounts on 13 Oct; SGD converted at the 13 Oct fixing 1.3400. The policy sets no bank limit")


@uc("uc10-pipeline", ["*/administrator_nav/administrator_export_2026-09.xlsx", "*/custodian_positions/positions_20260930.csv", "*/trading_export/trading_export_2026100*.csv"])
def k011(w):
    rows = admin_rows(w, "2026-09-30"); nav = {}
    for k, (p, v, s) in rows.items(): nav[p] = nav.get(p, D(0)) + v
    return Q("What was the Evergreen Liquid portfolio worth at 30 September 2026?", dict(evergreen_liquid=nav["EG-LIQUID"], net_worth_by_portfolio=nav), "sum of position market values per portfolio in the 30 Sep administrator pack (equals the custodian positions)")


@uc("uc5-limits", ["*/administrator_nav/administrator_export_2026-09.xlsx", "reference/Evergreen_Investment_Allocation_Policy_v2026.1.pdf", "reference/EG_security_master_20261008.xlsx"])
def k012(w):
    x = d("2026-09-30"); tot = w.book(x); name = {k: w.value(k, x) for k in w.sec if w.sec[k]["sector"] != "Government bond"}  # a sovereign note is not a single-name exposure
    top = max(name, key=name.get); eq = sum((v for k, v in name.items() if w.sec[k]["asset_class"] == "listed_equity"), D(0))
    rows = admin_rows(w, "2026-09-30"); funds = {p: sum((v for k, (pp, v, s) in rows.items() if pp == p), D(0)) for p in ("EG-FUNDS", "EG-B-OPS")}
    hedge = rows["H1"][1] + rows["H2"][1]
    return {**Q("Which holding is over its single-name limit?", dict(holding=w.sec[top]["canonical_name"], value=name[top], pct_of_portfolio=pct(name[top], tot, 2), limit_pct=5, breach=pct(name[top], tot, 2) > 5), "largest position other than the sovereign note, over the EG-LIQUID total at 30 Sep"),
            **Q("Other limits", dict(listed_equity_pct=pct(eq, tot, 2), listed_equity_band="60-90", hedge_funds_pct_of_eg_funds=pct(hedge, funds["EG-FUNDS"], 2), hedge_band="20-60",
                                    cedarpoint_pct_of_eg_b_ops=pct(rows["D"][1], funds["EG-B-OPS"], 2), cedarpoint_max=55), "values from the 30 Sep administrator pack (Cedarpoint Ventures in EG-B-OPS is fund D only; fund C sits in Holdings)")}


@uc("uc-013-secgaps", ["reference/EG_security_master_20261008.xlsx", "*/custodian_positions/positions_20260930.csv", "*/administrator_nav/administrator_export_2026-09.xlsx"])
def k013(w):
    x = d("2026-09-30"); gaps = [k for k, s in w.sec.items() if not s["asset_class"]]
    return Q("Which instruments need a class or identifier before limits and allocation can be trusted", dict(count=len(gaps), instruments=[w.sec[k]["canonical_name"] for k in gaps], value=sum((w.value(k, x) for k in gaps), D(0))), "securities with a null asset class in the security master / custodian file")


@uc("morning-networth-note", ["*/investment_reports/Evergreen_Office_Investment_Report_2026-09.pdf", "*/fx_rates/fx_usdsgd_20260930.csv"])
def k014(w):
    issue, lines, tot, sgd = report_lines(w, "2026-09")
    return Q("What are we worth in the latest report?", dict(total_usd=tot, total_sgd=sgd, fixing=w.fx[d("2026-09-30")], issued=issue, lines={a: b for a, b, c in lines}), "issued September report: A (estimate) + B + Liquid Book; SGD at the 30 Sep WMR 4pm fixing")


@uc("uc-015-allowances", ["*/family_allowances/allowance_schedule_2026-09.xlsx", "*/family_allowances/allowance_schedule_2026-10.xlsx", "*/bank_statements/HB_TRUST_USD_2026-09.xlsx"])
def k015(w):
    unpaid = [a for a in w.allow if not a["paid"]]
    return Q("What do we owe each family member this month, and do we have the cash?", dict(due_october={a["member"]: a["amount"] for a in w.allow if a["month"] == "2026-10"}, unpaid_earlier=[dict(member=a["member"], month=a["month"], amount=a["amount"]) for a in unpaid],
                                                                                    total_owed=sum((a["amount"] for a in w.allow if a["month"] == "2026-10"), D(0)) + sum((a["amount"] for a in unpaid), D(0)), trust_usd_cash=cash(w, "EG-TRUST", "USD")),
             "scheduled amounts less allowance payments found in the Trust bank statements; Ethan Chen's September payment is missing (planted)")


@uc("uc-016-schemadrift", ["*/administrator_nav/administrator_export_2026-06.xlsx", "*/administrator_nav/administrator_export_2026-05.xlsx"])
def k016(w):
    return Q("The administrator renamed a column. What breaks, and is the new mapping safe?", dict(file="administrator_export_2026-06.xlsx", old_name="Market Value", new_name="Valuation Amount (USD)", months_with_old_name=5), "the 30 June pack (released in July) renames one column; the other packs keep 'Market Value'")


@uc("uc-017-liab", ["*/loan_statements/loan_statement_TL-B-01_2026-09.xlsx", "reference/loan_agreement_TL-B-01.pdf", "*/bank_statements/HB_B_USD_2026-09.xlsx"])
def k017(w):
    bal = {r["month"]: -r["close"] for r in w.loan}; issue, lines, tot, sgd = report_lines(w, "2026-09"); allnav = w.nav_total("2026-09-30")
    return Q("Whether net worth after debt is what the family expects", dict(loan_balance_as_shown_negative=bal["2026-09"], principal_outstanding=-bal["2026-09"], by_month=bal, report_total=tot, report_less_debt=tot + bal["2026-09"],
                                                                         all_portfolios_nav=allnav, all_portfolios_less_debt=allnav + bal["2026-09"]), "loan statements show principal as negative; net worth after debt adds the negative balance")


@uc("uc-018-fundplan", ["*/notices/2026-10-13_C_call7.pdf", "*/administrator_cash/administrator_cash_2026-10_mtd.csv", "*/commitments/commitments_register_2026-10-13.xlsx"])
def k018(w):
    c = C7(w); cover = {ENT[e]: cash(w, e, "USD") - OFFICE_RULES["buffer_usd"] - (c["amount"] if e == c["ent"] else 0) for e in ENT}
    return Q("Which entity pays and whether a transfer is needed first", dict(paying_entity=ENT[c["ent"]], usd_cover_after_buffer_and_call=cover, transfer_needed=cover[ENT[c["ent"]]] < 0, shortfall=-cover[ENT[c["ent"]]],
                                                                     entities_with_spare_usd=[e for e, v in cover.items() if v > 0 and e != ENT[c["ent"]]]), "USD cash less the 250,000 buffer, less the call for the entity named in the commitment")


@uc("uc3-statements-inbox", ["*/manager_statements/*_final.pdf", "*/emails/*_stmt_*.eml", "received_log_all.csv"])
def k019(w):
    miss = [s for s in w.stmts if s["status"] == "missing"]; late = []
    for s in w.stmts:
        if s["received"] and s["kind"] != "amended" and d(s["received"]) > d(s["due"]): late.append(dict(fund=pname(s["fund"]), period=s["period"], due=s["due"], received=s["received"], business_days_late=bdays_after(d(s["due"]), d(s["received"]))))
    return {**Q("Which statement is missing and how overdue is it?", dict(missing=[dict(fund=pname(s["fund"]), period=s["period"], due=s["due"], business_days_overdue_13_oct=bdays_after(d(s["due"]), END), business_days_overdue_9_oct=bdays_after(d(s["due"]), d("2026-10-09"))) for s in miss]),
                "business days after the due date (10 business days after period end) up to the as-of date"),
            **Q("Late statements", dict(late=late), "received date after due date, excluding amended re-issues"),
            **Q("Bank statements late or missing", dict(rows=[r for r in RECV if r[1] == "bank_statement" and r[5] != "received"]), "received_log_all.csv")}


@uc("uc1-why-nav-moved", ["*/investment_reports/Evergreen_Office_Investment_Report_2026-09.pdf", "*/manager_statements/northgate_A_2026-09-30_*.pdf", "*/emails/*_stmt_A_2026-09-30_amended.eml", "*/administrator_nav/administrator_export_2026-09.xlsx"])
def k020(w):
    est = next(s for s in w.stmts if s["fund"] == "A" and s["period"] == "2026-09-30" and s["kind"] == "estimate"); am = next(s for s in w.stmts if s["fund"] == "A" and s["period"] == "2026-09-30" and s["kind"] == "amended")
    return Q("Why did Fund A move since the issued September report?", dict(issued=est["value"], amended=am["value"], change=am["value"] - est["value"], change_pct=pct(am["value"] - est["value"], est["value"], 2), received=am["received"], over_materiality=True),
             "amended statement (received 7 Oct) less the estimate used in the issued report; materiality is 100,000 USD or 0.5% of the fund")


@uc("uc-021-stale", ["*/manager_statements/*_final.pdf", "*/administrator_nav/administrator_export_2026-09.xlsx"])
def k021(w):
    rows = {}
    for f in PRIVATE + ["H1", "H2"]:
        k = latest(w, f); rows[pname(f)] = dict(valuation_date=k["period"], age_days=(END - d(k["period"])).days, stale=(END - d(k["period"])).days > 90)
    return Q("Which fund values are older than 90 days and so not safe to use in limits and reports", dict(by_fund=rows, stale=[n for n, r in rows.items() if r["stale"]]), "13 Oct 2026 less the period end of the latest statement received, flagged above 90 days")


@uc("uc-022-amendlog", ["*/manager_statements/*_amended.pdf", "*/emails/*_amended.eml", "*/investment_reports/Evergreen_Office_Investment_Report_2026-09.pdf"])
def k022(w):
    last_issue = max(report_lines(w, m)[0] for m in months("2026-04", "2026-09")); rows = []
    for s in w.stmts:
        if s["kind"] != "amended": continue
        prev = [t for t in w.stmts if t["fund"] == s["fund"] and t["period"] == s["period"] and t["kind"] != "amended" and t["value"] is not None]
        rep = prev[-1]; rows.append(dict(fund=pname(s["fund"]), period=s["period"], replaces=rep["value"], amended=s["value"], change=s["value"] - rep["value"], received=s["received"], after_last_issued_report=d(s["received"]) > last_issue))
    return Q("Which earlier value is replaced and whether reports already issued need a note", dict(last_issued_report=last_issue, amendments=rows, open_count=sum(1 for r in rows if r["after_last_issued_report"])), "amended statements against the latest issued report date")


@uc("uc-023-tieout", ["*/investment_reports/Evergreen_Office_Investment_Report_*.xlsx", "*/administrator_nav/administrator_export_*.xlsx"])
def k023(w):
    out = []
    for m in months("2026-04", "2026-09"):
        issue, lines, tot, sgd = report_lines(w, m); me = month_end(m).isoformat(); ar = admin_rows(w, me)
        adm = {pname("A"): ar["A"][1], pname("B"): ar["B"][1], "Evergreen Liquid Book": sum((v for k, (p, v, s) in ar.items() if p == "EG-LIQUID"), D(0))}
        for a, b, c in lines:
            if b != adm[a]: out.append(dict(month=m, line=a, report=b, administrator=adm[a], difference=b - adm[a]))
    return Q("Does each number on the report agree with the administrator?", dict(differences=out, months_checked=6), "each report line against the administrator pack of the same month end; the report cutoff (3rd, 10:00) is later than the pack (2nd business day, 06:00)")


@uc("uc-024-audit", ["*/audit/audit_request_2026-09-22.xlsx", "*/investment_reports/Evergreen_Office_Investment_Report_*.pdf"])
def k024(w):
    ok = 0; bad = []
    items = __import__("tools.gen_office6m.files2", fromlist=["AUDIT_ITEMS"]).AUDIT_ITEMS
    for i, (m, line) in enumerate(items, 1):
        issue, lines, tot, sgd = report_lines(w, m); v = next((b for a, b, c in lines if a == line), None)
        if v is None: bad.append(dict(item=i, month=m, line=line, figure=9500000))
        else: ok += 1
    return Q("Whether every sampled figure traces to a source", dict(sampled=len(items), traced=ok, share_traced_pct=pct(ok, len(items), 1), untraceable=bad), "sample items matched to the issued report lines of the same month")


@uc("uc7-manager-diligence", ["reference/kestrel_ridge_q3_2026_newsletter.pdf", "*/meeting_notes/04_kestrel_ridge_onsite_2026-06-12.md", "*/manager_statements/kestrel_H1_*.pdf", "reference/kestrel_ridge_ddq_2026.pdf"])
def k025(w):
    items = [dict(date=s["received"], fund=pname(s["fund"]), period=s["period"], kind=s["kind"], value=s["value"]) for s in w.stmts if s["fund"] in ("H1", "H2") and s["received"] and s["received"] > "2026-06-12"]
    items.sort(key=lambda r: r["date"], reverse=True); h1 = latest(w, "H1")
    return Q("What changed at Kestrel Ridge since the last meeting?", dict(items_since_12_june=len(items), newest_first=items, h1_july_restated_from=D(7050000), h1_july_restated_to=D(7012500), h1_latest_value=h1["value"]),
             "Kestrel statements received after the 12 June meeting; the July restatement is in the meeting-note addendum and the amended statement")


@uc("uc-026-stmtadmin", ["*/manager_statements/*_2026-09-30_*.pdf", "*/administrator_nav/administrator_export_2026-09.xlsx"])
def k026(w):
    ar = admin_rows(w, "2026-09-30"); out = {}
    for f in FUND:
        k = latest(w, f)
        if k and k["value"] != ar[f][1]: out[pname(f)] = dict(statement=k["value"], administrator=ar[f][1], difference=k["value"] - ar[f][1], administrator_status=ar[f][2], statement_kind=k["kind"])
    return Q("Whether to accept the administrator value or ask the administrator to correct it", dict(differences=out), "latest statement known on 13 Oct less the 30 Sep administrator pack value, per fund")


def breaks_of(w):
    return [b for b in cash_breaks(w) if b["ccy"] == "USD"]


@uc("uc2-recon-break-desk", ["*/bank_statements/*_2026-10_mtd.xlsx", "*/administrator_cash/administrator_cash_2026-10_mtd.csv", "*/trading_export/cash_movements_2026-10_mtd.csv"])
def k027(w):
    br = breaks_of(w); over = [dict(date=b["date"], entity=ENT[b["ent"]], source=b["src"], bank=b["bank"], other=b["other"], difference=b["diff"]) for b in br if abs(b["diff"]) > OFFICE_RULES["cash_tolerance"]]
    inside = [dict(date=b["date"], entity=ENT[b["ent"]], source=b["src"], difference=b["diff"]) for b in br if abs(b["diff"]) <= OFFICE_RULES["cash_tolerance"]]
    e8 = d("2026-10-08"); eb = cash(w, "EG-B", "USD", "bank", e8), cash(w, "EG-B", "USD", "admin", e8)
    return {**Q("Which entity has a cash break on 8 October and by how much?", dict(entity="Entity B", date="2026-10-08", bank=eb[0], administrator=eb[1], difference=eb[1] - eb[0], cause="12,400 legal-fee wire paid by the bank on 8 Oct, booked by the administrator on 9 Oct"),
                "administrator cash less bank cash for Entity B USD on 8 Oct"),
            **Q("All breaks over the 5,000 tolerance, and those inside it", dict(over_tolerance=over, inside_tolerance=inside), "every entity-day where the administrator or the desk differs from the bank (USD); tolerance 5,000")}


@uc("uc-028-interco", ["*/bank_statements/HB_TRUST_USD_2026-08.xlsx", "*/bank_statements/HB_HOLD_USD_2026-08.xlsx", "*/approvals/approvals_2026-08.csv"])
def k028(w):
    t = [x for x in w.tx if x["typ"] == "intercompany_transfer" and x["ev"] == "IC-2026-08-01"]
    return Q("Which entity lends to which, and how it is recorded", dict(lender="Evergreen Family Trust", borrower="Evergreen Holdings", amount=-next(x["amt"] for x in t if x["acct"] == "HB-TRUST-USD"), date=t[0]["date"], reference="IC-2026-08-01", approval_recorded=any(a["ref"] == "IC-2026-08-01" and a["approved"] for a in w.approvals),
                                                                    balance_outstanding=-sum((x["amt"] for x in t if x["acct"] == "HB-TRUST-USD"), D(0))), "paired transfer debits and credits across the two entities' bank statements")


@uc("uc-029-closeck", ["*/close_checklist/close_checklist_2026-09.csv", "reference/month_end_process_narrative.md"])
def k029(w):
    rows = [c for c in close_items(w) if c["month"] == "2026-09"]
    return Q("Whether the close is complete and the report can start", dict(steps=len(rows), done=sum(1 for c in rows if c["status"] == "done"), open=[c["step"] for c in rows if c["status"] == "open"], late=[c["step"] for c in rows if c["late"]]),
             "checklist steps (the six steps of the month-end process); late = done after the due date or still open past it (as of 13 Oct)")


@uc("uc-030-vendors", ["reference/vendor_contract_*.pdf", "*/invoices/*orchard*.pdf"])
def k030(w):
    rows = [dict(vendor=v, currency=c, annual_cost=a, renewal=r, days_to_renewal=(r - END).days) for v, c, a, r, f in CONTRACTS if 0 <= (r - END).days <= 90]
    return Q("Which contracts to renew, renegotiate or end", dict(renewing_within_90_days=rows, count=len(rows)), "contract renewal dates (reference vendor contracts) inside 90 days of 13 Oct 2026")


def alloc(w, pe):
    ar = admin_rows(w, pe); cls = {}; ent = {}
    for k, (p, v, s) in ar.items():
        c = (w.sec[k]["asset_class"] or "unclassified") if k in w.sec else FUND[k]["asset_class"]
        cls[c] = cls.get(c, D(0)) + v; ent[ENT[{"EG-GROWTH": "EG-HOLD", "EG-PRIVATE": "EG-HOLD", "EG-LIQUID": "EG-TRUST", "EG-FUNDS": "EG-TRUST", "EG-B-OPS": "EG-B"}[p]]] = ent.get(ENT[{"EG-GROWTH": "EG-HOLD", "EG-PRIVATE": "EG-HOLD", "EG-LIQUID": "EG-TRUST", "EG-FUNDS": "EG-TRUST", "EG-B-OPS": "EG-B"}[p]], D(0)) + v
    return cls, ent, sum(cls.values(), D(0))


@uc("uc-031-alloc", ["*/administrator_nav/administrator_export_2026-09.xlsx", "reference/EG_security_master_20261008.xlsx"])
def k031(w):
    cls, ent, tot = alloc(w, "2026-09-30")
    return Q("What share of the family is in each asset class, and in each entity?", dict(total=tot, by_class_pct={k: pct(v, tot, 2) for k, v in sorted(cls.items())}, by_entity_pct={k: pct(v, tot, 2) for k, v in sorted(ent.items())}, by_class={k: v for k, v in sorted(cls.items())}),
             "30 Sep administrator pack: market value by asset class (security master / fund class) and by the entity that owns the portfolio, over the total of all portfolios")


@uc("uc-032-driftrep", ["reference/Evergreen_Investment_Allocation_Policy_v2026.1.pdf", "*/administrator_nav/administrator_export_2026-09.xlsx"])
def k032(w):
    x = d("2026-09-30"); tot = w.book(x); eq = sum((w.value(k, x) for k, s in w.sec.items() if s["asset_class"] == "listed_equity"), D(0)); ar = admin_rows(w, "2026-09-30")
    hedge = ar["H1"][1] + ar["H2"][1]; fnav = sum((v for k, (p, v, s) in ar.items() if p == "EG-FUNDS"), D(0))
    rows = [dict(rule="listed_equity (EG-LIQUID)", pct=pct(eq, tot, 2), band="60-90", outside=not (60 <= pct(eq, tot, 2) <= 90)), dict(rule="hedge_fund (EG-FUNDS)", pct=pct(hedge, fnav, 2), band="20-60", outside=not (20 <= pct(hedge, fnav, 2) <= 60))]
    return Q("Which asset classes are outside their policy band?", dict(targets="not set in policy v2026.1; bands are the min/max limits", rows=rows, outside=[r["rule"] for r in rows if r["outside"]]), "30 Sep allocation against the policy's min/max limits")


@uc("uc-033-breachesc", ["reference/Evergreen_Investment_Allocation_Policy_v2026.1.pdf", "*/administrator_nav/administrator_export_2026-09.xlsx"])
def k033(w):
    x = d("2026-09-30"); tot = w.book(x); e = w.value("HVS", x); lim = D("0.05")
    return Q("Whether to waive, cure or escalate the breach", dict(holding="Harborview Semiconductor", exposure=e, total=tot, limit_pct=5, cost_to_cure=q2((e - lim * tot) / (1 - lim))), "(exposure - limit x total) / (1 - limit): selling this amount brings the name to 5 percent of what is left")


@uc("uc-034-prospect", ["*/prospects/fund_teaser_Harborlight_Ventures_IV.pdf", "reference/Evergreen_Investment_Allocation_Policy_v2026.1.pdf"])
def k034(w):
    unf = sum((committed(w, f)[2] for f in PRIVATE), D(0))
    return Q("Whether to take the fund to diligence", dict(minimum_ticket=2000000, asset_class="venture", policy_limit_for_private_markets=None, uncalled_before=unf, uncalled_after=unf + 2000000, ticket_pct_of_current_uncalled=pct(2000000, unf, 2)),
             "teaser terms against the policy (no private-markets limit is set) and the current uncalled commitments")


@uc("uc-035-ddq", ["*/ddq/cedarpoint_ddq_2025.pdf", "*/ddq/cedarpoint_ddq_2026.pdf"])
def k035(w):
    return Q("Which answers differ from what the manager told us or from peers", dict(differences=[dict(question="Number of investment professionals", y2025="12", y2026="14"), dict(question="Assets under management (USD)", y2025="820 million", y2026="910 million"),
                                                                                                  dict(question="Key person provision", y2025="Two named partners", y2026="Three named partners"), dict(question="Management fee", y2025="2.0% of commitment", y2026="2.25% of commitment"),
                                                                                                  dict(question="Chief operating officer", y2025="R. Okafor", y2026="T. Lindqvist")], count=5), "the two generated questionnaires have eight questions; five answers were changed by the generator")


@uc("uc6-uncalled", ["*/commitments/commitments_register_2026-10-13.xlsx"])
def k036(w):
    after = sum((committed(w, f)[2] for f in PRIVATE), D(0)); before = after + C7(w)["amount"]
    return Q("How much is uncalled across all commitments?", dict(uncalled_after_call_7=after, uncalled_register_13_oct_before_call_7_recorded=before, by_fund={pname(f): committed(w, f)[2] for f in PRIVATE}), "sum over the 8 private funds of commitment less called to date (calls by notice date)")


@uc("uc-037-distrack", ["*/notices/*_distribution.pdf", "*/bank_statements/HB_HOLD_USD_2026-07.xlsx"])
def k037(w):
    rows = []
    for x in w.dists:
        cr = sum((t["amt"] for t in w.tx if t["ev"] == x["id"]), D(0)); rows.append(dict(fund=pname(x["fund"]), pay=x["pay"], notice=x["amount"], received=cr, gap=x["amount"] - cr))
    return Q("Whether money promised by a fund has arrived", dict(rows=rows, gaps=[r for r in rows if r["gap"] != 0]), "distribution notice amount less the matching bank credit (by fund and pay date)")


@uc("uc-038-navroll", ["*/manager_statements/*_final.pdf", "*/notices/*_call*.pdf"])
def k038(w):
    rows = []
    for f in PRIVATE:
        for a, b in (("2026-03-31", "2026-06-30"), ("2026-06-30", "2026-09-30")):
            ka, kb = w.known(f, a, "2026-12-31T00:00:00Z"), w.known(f, b, "2026-12-31T00:00:00Z")
            if not ka or not kb or ka["period"] != a or kb["period"] != b: continue
            calls = sum((c["amount"] for c in w.calls if c["fund"] == f and a < c["due"] <= b), D(0)); dist = sum((x["paid"] for x in w.dists if x["fund"] == f and a < x["pay"] <= b), D(0))
            rows.append(dict(fund=pname(f), quarter=f"{a} to {b}", prior=ka["value"], calls=calls, distributions=dist, new=kb["value"], implied_gain=kb["value"] - ka["value"] - calls + dist))
    return Q("Whether the new value is explained by calls, distributions and gain", dict(rows=rows), "prior value + calls - distributions + implied gain = new value; implied gain is what the manager's statement does not explain with flows")


def irr(flows):
    f = lambda r: sum(c / (1 + r) ** ((t - flows[0][0]).days / 365) for t, c in flows)
    lo, hi = -0.99, 10.0
    if f(lo) * f(hi) > 0: return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(lo) * f(mid) <= 0: hi = mid
        else: lo = mid
    return mid


@uc("uc-039-irr", ["*/manager_statements/*_final.pdf", "*/notices/*_call*.pdf", "*/notices/*_distribution.pdf"])
def k039(w):
    rows = {}
    for f in PRIVATE:
        k0 = w.known(f, "2026-03-31", "2026-04-30T00:00:00Z"); k1 = latest(w, f); flows = [(d("2026-03-31"), -float(k0["value"]))]
        flows += [(d(c["due"]), -float(c["amount"])) for c in w.calls if f == c["fund"] and d(c["due"]) <= END]; flows += [(d(x["pay"]), float(x["paid"])) for x in w.dists if x["fund"] == f]
        flows.append((END, float(k1["value"])))
        called = committed(w, f, "2026-10-12")[1]; dist = sum((x["paid"] for x in w.dists if x["fund"] == f), D(0))
        r = irr(sorted(flows)); rows[pname(f)] = dict(irr_pct_since_1_apr=None if r is None else round(r * 100, 2), tvpi=round(float((dist + k1["value"]) / called), 4), dpi=round(float(dist / called), 4), latest_value=k1["value"], latest_period=k1["period"])
    return Q("Which funds earned their place and which to stop adding to", dict(by_fund=rows, basis="since 1 April 2026: opening value on 31 Mar, calls and distributions in the data, latest value; TVPI and DPI use cumulative called and window distributions"),
             "IRR solved by bisection on dated flows; TVPI = (window distributions + latest value) / called to 12 Oct")


@uc("uc-040-icmemo", ["*/ddq/cedarpoint_ddq_2026.pdf", "*/manager_statements/cedarpoint_C_*.pdf", "reference/Evergreen_Investment_Allocation_Policy_v2026.1.pdf"])
def k040(w):
    k = latest(w, "C"); com, called, unf = committed(w, "C")
    return Q("Whether to recommend the commitment", dict(fund=pname("C"), commitment=com, called_incl_call_7=called, unfunded=unf, latest_value=k["value"], latest_period=k["period"], statement_kind=k["kind"], fee_in_call_7=C7(w)["fee"],
                                                    ddq_changes_2025_to_2026=5), "figures taken from the generated statements, calls and questionnaires; each has its file")


@uc("uc-041-commitappr", ["reference/Evergreen_Investment_Allocation_Policy_v2026.1.pdf", "*/commitments/commitments_register_2026-10-13.xlsx", "*/prospects/fund_teaser_Harborlight_Ventures_IV.pdf"])
def k041(w):
    fx = w.fx[END]; cash_usd = sum((w.bal[a][END] / (fx if v["ccy"] == "SGD" else 1) for a, v in ACCT.items()), D(0)); unf = sum((committed(w, f)[2] for f in PRIVATE), D(0))
    return Q("Whether the commitment fits the budget, limits and cash", dict(new_commitment=2000000, uncalled_after=unf + 2000000, cash_usd_equivalent=q2(cash_usd), cash_cover_of_uncalled_after_pct=pct(cash_usd, unf + 2000000, 2), budget="not set in policy v2026.1"),
             "cash of all 12 accounts at the 13 Oct fixing against uncalled commitments after the new ticket (24 month pacing assumed equal to 100 percent of uncalled)")


@uc("uc4-vs-benchmark", ["reference/EG-OFFICE-BLEND_Benchmark_Specification_2026-10.xlsx", "*/index_levels/index_levels_2026-09.csv", "*/index_levels/index_levels_2026-10.csv", "*/administrator_nav/administrator_export_2026-09.xlsx"])
def k042(w):
    v0, v1 = w.book(d("2026-08-31")), w.book(d("2026-09-30")); a, b = w.idx["2026-08-31"], w.idx["2026-09-30"]; re = b[0] / a[0] - 1; rb = b[1] / a[1] - 1
    bench = D("0.42") * re + D("0.28") * rb + D("0.30") * (re + D("0.0025")); p = v1 / v0 - 1
    return Q("How did the liquid portfolio do against the benchmark in September 2026?", dict(portfolio_return_pct=round(float(p * 100), 4), benchmark_return_pct=round(float(bench * 100), 4), active_pct=round(float((p - bench) * 100), 4), liquid_aug=v0, liquid_sep=v1,
                                                                                         equity_index_pct=round(float(re * 100), 4), bond_index_pct=round(float(rb * 100), 4)),
             "portfolio 41,200,000 / 39,552,000 - 1 (no September trades); benchmark v1 = 0.42 x equity index + 0.28 x bond index + 0.30 x (equity index + 25 bps)")


@uc("uc-043-liquidpnl", ["*/custodian_positions/positions_20261013.csv", "*/custodian_positions/positions_20260930.csv", "*/trading_export/trading_export_2026100*.csv"])
def k043(w):
    v0, v1 = w.book(d("2026-09-30")), w.book(END); net = sum((t["amt"] if t["side"] == "buy" else -t["amt"] for t in w.trades if d("2026-09-30") < t["settle"] <= END), D(0))
    return Q("Whether to act on a large move in the liquid book", dict(value_30_sep=v0, value_13_oct=v1, net_trades_settled=net, gain_loss_mtd=v1 - v0 - net, gain_pct=pct(v1 - v0 - net, v0, 4)), "value on 13 Oct less value at 30 Sep less net purchases settled in October")


def sleeve_ret(w, x0, x1, pred):
    ks = [k for k, s in w.sec.items() if pred(s)]; v0 = sum((w.value(k, x0) for k in ks), D(0)); v1 = sum((w.value(k, x1) for k in ks), D(0)); return v0, (v1 / v0 - 1 if v0 else D(0))


@uc("uc-044-twr", ["*/custodian_positions/positions_*.csv", "*/index_levels/index_levels_2026-0[4-9].csv", "reference/EG-OFFICE-BLEND_Benchmark_Specification_2026-10.xlsx"])
def k044(w):
    ends = [d("2026-03-31")] + [month_end(m) for m in months("2026-04", "2026-09")]; rets = []; brets = []
    for x0, x1 in zip(ends, ends[1:]):
        v0, v1 = w.book(x0), w.book(x1); F = sum((t["amt"] if t["side"] == "buy" else -t["amt"] for t in w.trades if x0 < t["settle"] <= x1), D(0))
        rets.append((v1 - v0 - F) / (v0 + F / 2))
        a, b = w.idx[lastbd(x0).isoformat()], w.idx[lastbd(x1).isoformat()]; re, rb = b[0] / a[0] - 1, b[1] / a[1] - 1; brets.append(D("0.42") * re + D("0.28") * rb + D("0.30") * (re + D("0.0025")))
    def chain(rs):
        t = D(1)
        for r in rs: t *= 1 + r
        return t - 1
    return Q("What to report on performance for the quarter and the year", dict(monthly_pct=[round(float(r * 100), 4) for r in rets], q2_apr_jun_pct=round(float(chain(rets[:3]) * 100), 4), q3_jul_sep_pct=round(float(chain(rets[3:]) * 100), 4), since_1_apr_pct=round(float(chain(rets) * 100), 4),
                                                                                 benchmark_since_1_apr_pct=round(float(chain(brets) * 100), 4)), "modified Dietz monthly return of the liquid book (flows weighted half), chain-linked; benchmark v1 chain-linked from month-end index levels (last business day)")


@uc("uc-045-reportpack", ["*/investment_reports/Evergreen_Office_Investment_Report_2026-09.xlsx", "*/administrator_nav/administrator_export_2026-09.xlsx"])
def k045(w):
    issue, lines, tot, sgd = report_lines(w, "2026-09"); ar = admin_rows(w, "2026-09-30"); adm = {pname("A"): ar["A"][1], pname("B"): ar["B"][1], "Evergreen Liquid Book": sum((v for k, (p, v, s) in ar.items() if p == "EG-LIQUID"), D(0))}
    secs = {a: (b == adm[a] and c == "official") for a, b, c in lines}; secs["FX translation"] = True; secs["Total"] = all(secs.values()) and all(c == "official" for a, b, c in lines)
    return Q("Whether to sign off and issue the report", dict(sections=len(secs), ready=[k for k, v in secs.items() if v], not_ready=[k for k, v in secs.items() if not v], share_ready_pct=pct(sum(secs.values()), len(secs), 1)), "a section is ready when it ties to the administrator and is not an estimate; the total inherits the estimate of Evergreen Growth I")


@uc("uc-046-attrib", ["reference/EG-OFFICE-BLEND_Benchmark_Specification_2026-10.xlsx", "*/index_levels/index_levels_2026-09.csv", "*/custodian_positions/positions_20260831.csv", "*/custodian_positions/positions_20260930.csv"])
def k046(w):
    x0, x1 = d("2026-08-31"), d("2026-09-30"); a, b = w.idx["2026-08-31"], w.idx["2026-09-30"]; re, rb = b[0] / a[0] - 1, b[1] / a[1] - 1
    sl = {"equity": (lambda s: s["asset_class"] == "listed_equity", D("0.6"), re), "bond": (lambda s: s["asset_class"] == "bond", D("0.4"), rb), "unclassified": (lambda s: not s["asset_class"], D(0), D(0))}
    tot0 = w.book(x0); rp = {}; wp = {}
    for n, (pred, wb, rbi) in sl.items(): v0, r = sleeve_ret(w, x0, x1, pred); wp[n] = v0 / tot0; rp[n] = r
    Rp = sum(wp[n] * rp[n] for n in sl); Rb = sum(sl[n][1] * sl[n][2] for n in sl); eff = {}
    for n, (pred, wb, rbi) in sl.items():
        eff[n] = dict(allocation=(wp[n] - wb) * (rbi - Rb), selection=wb * (rp[n] - rbi), interaction=(wp[n] - wb) * (rp[n] - rbi))
    tot = sum(sum(e.values()) for e in eff.values())
    f = lambda v: round(float(v * 100), 4)
    return Q("Which allocation or selection decision to change", dict(portfolio_pct=f(Rp), liquid_benchmark_pct=f(Rb), active_pct=f(Rp - Rb), effects_pct={n: {k: f(v) for k, v in e.items()} for n, e in eff.items()},
                                                                  sum_of_effects_pct=f(tot), adds_up=abs(tot - (Rp - Rb)) < D("0.0000001")), "Brinson-Fachler on the liquid sleeve of the benchmark (60 percent equity, 40 percent bond); allocation + selection + interaction = active return")


@uc("uc-047-icpack", ["*/investment_reports/Evergreen_Office_Investment_Report_2026-09.pdf", "*/meeting_notes/ic_note_2026-08-19.md", "*/meeting_notes/08_investment_committee_note_2026-10-08.md"])
def k047(w):
    return Q("Which matters to put to the committee and what to recommend", dict(sections=[dict(section="Report", owner="Raj Patel", status="issued 3 Oct (A estimated)"), dict(section="Performance", owner="Raj Patel", status="liquid book +4.1667% against 2.7072%"),
                                                                                         dict(section="Attribution", owner="Sofia Reyes", status="computed"), dict(section="Breaches", owner="Tom Hale", status="1 real breach (Harborview Semiconductor 5.75%)"),
                                                                                         dict(section="Proposals", owner="Daniel Foo", status="fund Cedarpoint call 7 (short USD 270,000); Harborlight Ventures IV ticket 2,000,000")], real_breaches=1, amendments_open=1), "sections drawn from the other keys of this file")


@uc("uc-048-policyupd", ["reference/Evergreen_Investment_Allocation_Policy_v2026.1.pdf", "*/custodian_positions/positions_20260630.csv", "*/meeting_notes/ic_note_2026-06-17.md"])
def k048(w):
    rows = {}
    for me in [month_end(m) for m in months("2026-04", "2026-09")]:
        tot = w.book(me); rows[me.isoformat()] = max(pct(w.value(k, me), tot, 2) for k in w.sec if w.sec[k]["sector"] != "Government bond")
    return Q("Which limits to change and by how much", dict(max_single_name_pct_by_month_end=rows, breaches_at_5_pct=sum(1 for v in rows.values() if v > 5), breaches_at_6_pct=sum(1 for v in rows.values() if v > 6), current_limit=5, proposed_limit=6),
             "largest single name over the liquid book at each month end from custodian positions (6 months of data, not 12); count above the limit")


@uc("uc-049-feedrag", ["*/notices/*_call*.pdf", "reference/fee_schedule.pdf", "*/manager_statements/*_final.pdf"])
def k049(w):
    out = {}
    for m in sorted({FUND[f]["manager"] for f in PRIVATE}):
        fs = [f for f in PRIVATE if FUND[f]["manager"] == m]; fees = sum((c["fee"] for c in w.calls if c["fund"] in fs and d(c["due"]) <= END and c["id"] != "CALL-C-7"), D(0))
        gain = D(0)
        for f in fs:
            k0, k1 = w.known(f, "2026-03-31", "2026-04-30T00:00:00Z"), latest(w, f)
            flows = sum((c["amount"] for c in w.calls if c["fund"] == f and d(c["due"]) <= END and c["id"] != "CALL-C-7"), D(0)) - sum((x["paid"] for x in w.dists if x["fund"] == f), D(0)); gain += k1["value"] - k0["value"] - flows
        out[MGR[m]["name"]] = dict(fees_paid_via_calls=fees, net_gain_since_1_apr=gain, gross_gain=gain + fees, fee_drag_pct=None if gain + fees <= 0 else pct(fees, gain + fees, 2))
    return Q("Whether a manager earns its fees", dict(by_manager=out), "management fees billed in capital calls (1 Apr to 13 Oct, call 7 excluded) over gross gain = value change less flows plus fees")


@uc("uc-050-feeinv", ["*/invoices/*FEE-*.pdf", "reference/fee_schedule.pdf"])
def k050(w):
    return Q("Whether to pay the invoice as billed", dict(invoices=[dict(id=f["id"], billed=f["amount"], expected=f["expected"], variance=f["amount"] - f["expected"], rate_billed_pct=float(f["rate"] * 100)) for f in w.fee_invoices], overcharged=[f["id"] for f in w.fee_invoices if f["amount"] != f["expected"]]),
             "fee base times schedule rate / 4; the custodian Q3 invoice is billed at 0.06 percent instead of 0.05 percent (planted)")


@uc("uc8-trades-vs-admin", ["*/trading_export/trading_export_2026100*.csv", "*/administrator_trades/administrator_trades_2026-10.csv", "*/fx_confirmations/FXF-2026-002_confirmation.pdf"])
def k0008(w):
    oct_ = [t for t in w.trades if t["trade"] >= d("2026-10-01")]; brk = []
    for t in oct_:
        if t["admin_qty"] is None: brk.append(dict(trade=t["id"], security=t["sec"], kind="missing at administrator", amount=t["amt"]))
        elif t["admin_qty"] != t["qty"]: brk.append(dict(trade=t["id"], security=t["sec"], kind="quantity differs", ours=t["qty"], administrator=t["admin_qty"], difference_usd=(t["qty"] - t["admin_qty"]) * t["price"]))
    fx = U["fx_forwards"][1]
    dup = [t["id"] for t in w.trades if t["dup"]]
    return Q("How much does the FX forward confirmation differ from our record?", dict(fx_forward="FXF-2026-002", booked_rate=fx["contract_rate"], confirmed_rate=fx["confirmation_rate"], difference_sgd=D(fx["difference_sgd"]), difference_usd_at_8_oct=D(fx["difference_usd_at_8_oct"]),
                                                                                  october_trade_breaks=brk, trade_booked_twice_in_export=dup), "OMS trades against administrator bookings and the bank confirmation; the duplicate row is in the June export")


# ---------------------------------------------------------------------------------------------------- build the file
@functools.lru_cache(maxsize=1)
def top50_ids():
    y = yaml.safe_load(PACK.read_text(encoding="utf-8"))
    return [u["id"] for u in sorted((u for u in y["use_cases"] if u.get("priority")), key=lambda u: u["priority"]) if u["priority"] <= 50], {u["id"]: u for u in y["use_cases"]}


def build_keys(w):
    ids, cat = top50_ids(); out = {}
    for i, fn in KEYS.items():
        k = deep(fn(w)); out[i] = dict(title=cat.get(i, {}).get("title", ""), priority=cat.get(i, {}).get("priority"), input_files=FILES[i], questions=k)
    return out
