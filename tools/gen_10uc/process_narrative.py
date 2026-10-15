"""Deterministic generator: month-end process narrative (UC9). All figures read from the universe."""
import json, pathlib

R = pathlib.Path(__file__).resolve().parents[2]
U = json.load(open(R / "docs/test/10uc_universe.json"))
OUT = R / "tests/v1/fixtures/10uc/process_narrative"
OUT.mkdir(parents=True, exist_ok=True)
P = U["process"]
S = {s["n"]: s for s in P["steps"]}
rules = {r["rule_code"]: r for r in U["rules"]}
rep = U["report_issued"]
m = lambda x: f"{float(x):,.0f}"
tol = rules["cash_tolerance"]["parameters"]["abs_amount"]
mat = rules["cio_materiality"]["parameters"]
due = rules["statement_due"]["parameters"]["business_days_after_month_end"]
B = next(c for c in U["cash_8_oct"] if c["legal_entity"] == "EG-B")
T = next(c for c in U["cash_8_oct"] if c["legal_entity"] == "EG-TRUST")
stm = U["statements"]


def st(f, pe, kind):
    return next(s for s in stm if s["fund"] == f and s["period_end"] == pe and s["kind"] == kind)


A_est, A_am = st("A", "2026-09-30", "estimate"), st("A", "2026-09-30", "amended")
D_miss, H2_late, E_late = st("D", "2026-06-30", "missing"), st("H2", "2026-08-31", "final"), st("E", "2026-06-30", "final")
C_am, H1_am = st("C", "2026-06-30", "amended"), st("H1", "2026-07-31", "amended")
C_fin, H1_fin = st("C", "2026-06-30", "final"), st("H1", "2026-07-31", "final")
lines = rep["lines"]
tot = next(l for l in lines if l["label"] == "Total")
day = lambda s: s["received_at"][:10]

detail = {
    1: "Each month-end Mei downloads the administrator positions export and the trading system positions export (CSV) from the portals and saves them to the shared file drop under /MonthEnd/<yyyy-mm>/raw. She opens each file, counts the rows and compares the row count and control total in the footer line with the file. If the batch control totals do not match she rejects it and asks the administrator or the desk for a new file the same day.",
    2: f"Mei opens the cash tab of her reconciliation workbook (Cash_Recon_<yyyy-mm>.xlsx) and pastes the administrator cash balances beside the trading export balances, one row per entity (EG-HOLD, EG-TRUST, EG-B) per day. A formula column shows the difference. The signed rule is that cash may differ by up to {m(tol)} USD per entity per day; anything over is highlighted by hand and a break case is opened in the tracker (tab 'Breaks'). Raj is told by email.",
    3: f"The managers send statements to the shared statements inbox. Mei saves the PDF to the manager folder, types the fund, period end, value and received date into the statements tracker (Excel), and checks the tracker against the expected list. A statement is due {due} business days after the period end. For anything late or missing she writes a follow-up email to the manager by hand. Quarterly funds (C, D, E) are carried forward in the months with no statement.",
    4: f"Raj takes the holdings values from the tracker and the cash from the recon workbook and converts them to SGD in a separate Excel file, looking up the WMR 4pm USD/SGD fixing for the period end in the market data file. For September 2026 the fixing used was {rep['fx_rate_used']}. If there is no fixing for the date he holds the report. The conversion is typed in, not linked, so a changed USD figure does not flow through.",
    5: f"Raj assembles the report pack from the converted figures and sends it for review. A manager estimate may be used in the investment report only. The maker of the figures is never the checker: Raj prepares, Daniel Foo approves. If a late statement revises a value by more than {m(mat['abs_amount'])} USD or {mat['pct_of_fund']}% of a fund, the review is reopened.",
    6: "Daniel reads the issued pack. The pack shows the version and the cutoff time. Questions for managers are logged as open questions and picked up by Mei in the next cycle.",
}
steps_md = "".join(
    f"### Step {s['n']}. {s['name']}\n\n- Who: {s['who']}\n- System: {s['system']}\n"
    f"- Manual spreadsheet or hand step: {'yes' if s['manual'] else 'no'}\n- Control: {s['control']}\n"
    f"- Known exception: {s['exception']}\n\n{detail[s['n']]}\n\n"
    for s in P["steps"]
)
hand = "\n".join(
    f"- Hand-over {a}-{a+1}: {S[a]['who']} ({S[a]['system']}) to {S[a+1]['who']} ({S[a+1]['system']})."
    + (" Same person, different tool: the file is re-saved and re-typed." if S[a]["who"] == S[a + 1]["who"]
       else " By email with the workbook attached; there is no log of what was sent.")
    for a in range(1, 6)
)
man = P["manual_steps_flagged_for_automation"]
main = f"""# Evergreen Office: how we produce the monthly investment report today

Document: OPS-PRC-014, version 3.2 (working copy)
Owner: Mei Chen, Operations analyst
Reviewed by: Anita Rao, Head of data
Last updated: 2026-10-05
Project: {P['project_title']}
Status: describes current practice, not a target design

## 1. Purpose

This note describes, step by step, how the Operations and Finance team at Evergreen Office assembles the monthly investment report in USD and SGD. The report is needed by the {P['needed_by']} and goes to {P['sponsor']}, the Chief Investment Officer. {P['builder']} (data engineer) and {P['head_of_data']} (Head of data) have asked for this to be written down so the process can be mapped and automated.

## 2. People and systems

| Person | Role | Part in the process |
|---|---|---|
| Mei Chen | Operations analyst | Steps 1 to 3 |
| Raj Patel | Finance | Steps 4 and 5 (also owns most rules) |
| Daniel Foo | Chief Investment Officer | Step 6, approves the issued report |
| Sofia Reyes | Risk | Receives the pack, owns the limits |
| Leo Park, Anita Rao | Data | Support the exports; builder and head of data of the project |

Systems: File drop (shared folder), Excel (recon workbook, statements tracker, SGD conversion file), Email (shared statements inbox), Report pack (the formatted pack template).

## 3. Steps today

There are {len(P['steps'])} steps. Steps {', '.join(map(str, man[:-1]))} and {man[-1]} are manual spreadsheet, file or email steps and take most of the time.

{steps_md}## 4. Hand-overs

{hand}

There is no single place that shows where a month stands; Mei and Raj ask each other by chat.

## 5. Controls summary

| Step | Control |
|---|---|
""" + "\n".join(f"| {s['n']} | {s['control']} |" for s in P["steps"]) + f"""

## 6. Known exceptions seen recently

- Cash: on 8 Oct 2026 Entity B (EG-B) showed {m(B['administrator'])} at the administrator against {m(B['trading_export'])} in the trading export, a difference of {m(B['difference'])} USD, over the {m(tol)} USD tolerance, so one break case was opened. EG-TRUST differed by {m(T['difference'])} USD and needed no case.
- Statements: Fund D (Cedarpoint Opportunities II) 30 June 2026 statement was due {D_miss['due_date']} and never arrived. Fund H2 August 2026 arrived {day(H2_late)}, {H2_late['late_business_days']} business days late; Fund E June 2026 arrived {day(E_late)}, {E_late['late_business_days']} business days late.
- Revisions: Fund A September 2026 was reported at {m(A_est['value'])} USD (manager estimate) in the report issued {rep['issued_at'][:10]}; the amended statement of {day(A_am)} shows {m(A_am['value'])} USD, +{m(float(A_am['value']) - float(A_est['value']))}, over the {m(mat['abs_amount'])} USD materiality, so the review is reopened. Earlier revisions: Fund C June 2026 {m(C_am['value'])} (was {m(C_fin['value'])}) and Fund H1 July 2026 {m(H1_am['value'])} (was {m(H1_fin['value'])}).
- The same fund can arrive under different names (for example 'KR Macro Fund Ltd - Class B USD' and 'Kestrel Ridge Macro Fund'); Mei matches them by eye using the administrator code.

## 7. The September 2026 cycle in numbers

Issued {rep['issued_at'][:10]} {rep['issued_at'][11:16]} UTC, cutoff {rep['cutoff_at'][11:16]} UTC. Values in USD: """ + "; ".join(f"{l['label']} {m(l['value'])} ({l['status']})" for l in lines) + f""". Total in SGD {float(rep['total_sgd']):,.2f} at {rep['fx_rate_used']}.

## 8. What we would like North to produce

A swim lane across the three people and four systems above, with the four manual steps flagged, and a standard operating procedure (owner, system, input, output, control, exception for each step).
"""
(OUT / "month_end_process_narrative.md").write_text(main, encoding="utf-8")

email = f"""From: Mei Chen
To: Raj Patel
Cc: Leo Park
Date: Mon, 05 Oct 2026 09:12 +0800
Subject: Month-end hand-over checklist, September close

Raj,

Here is my side of the hand-over for the September close, in the order I do it. Leo asked for it so he can map the process.

1. Collect the exports ({S[1]['system']}). I pull the administrator and trading positions files and check row counts and file totals. If they do not match I reject the file and ask for a new one the same day.
2. Cash check ({S[2]['system']}). I compare administrator and trading cash per entity per day. Tolerance is {m(tol)} USD. Over tolerance I open a break case. I do this by hand every month.
3. Statements ({S[3]['system']}). I log each manager statement in the tracker. Due is {due} business days after period end. Late or missing, I write the manager a follow-up by hand.

I then email you the recon workbook and the tracker. You do the SGD conversion (step 4, {S[4]['system']}) with the WMR 4pm fixing and then the pack (step 5). There is no log of what I sent you; it is whatever is in my sent items.

Things that bite every month: files arriving late, the same fund under two names, and estimates that get revised after we have issued.

Mei
Operations analyst, Evergreen Office
"""
(OUT / "handover_email_mei_to_raj.txt").write_text(email, encoding="utf-8")

# verify by re-reading
t = (OUT / "month_end_process_narrative.md").read_text(encoding="utf-8")
for s in P["steps"]:
    assert f"### Step {s['n']}. {s['name']}" in t and s["control"] in t and s["exception"] in t
    assert f"- Who: {s['who']}\n- System: {s['system']}" in t
for v in [m(tol), m(mat["abs_amount"]), rep["fx_rate_used"], f"{float(rep['total_sgd']):,.2f}",
          m(tot["value"]), "10,180,000", "10,000,000", "12,400", "880,400", "868,000", "8,275,000", "7,012,500"]:
    assert v in t, v
assert str(due) in email and m(tol) in email

(OUT / "MANIFEST.md").write_text("""# Manifest: process_narrative

Generated by tools/gen_10uc/process_narrative.py from docs/test/10uc_universe.json (deterministic, synthetic).

| File | Holds | Planted facts carried |
|---|---|---|
| month_end_process_narrative.md | Month-end process narrative: purpose, people and systems, 6 steps (who, system, manual flag, control, exception), 5 hand-overs, controls table, recent exceptions, September cycle figures | P32 (6 steps, manual steps 1-4, hand-overs 1-2 to 5-6), P33 (project title), P08 (Entity B 12,400 break), P01 (issued figures, SGD 77,253,120.00 at 1.3412), P02 (A amended 10,180,000), P10, P11, P12, P13 |
| handover_email_mei_to_raj.txt | Informal hand-over email, Mei Chen to Raj Patel, steps 1-3 and hand-over to step 4 | P32 (owners and systems of steps 1-4, cash tolerance 5,000, statement due 10 business days) |
""", encoding="utf-8")
print("ok", sorted(p.name for p in OUT.iterdir()))
