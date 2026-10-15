"""Meeting notes and IC note for the Evergreen Office 10UC universe (synthetic, deterministic, markdown).
python-docx is not installed, so md. Every figure is read from docs/test/10uc_universe.json."""
import json, pathlib, datetime as dt

ROOT = pathlib.Path(__file__).resolve().parents[2]
U = json.load(open(ROOT / "docs/test/10uc_universe.json"))
OUT = ROOT / "tests/v1/fixtures/10uc/notes"
OUT.mkdir(parents=True, exist_ok=True)

n = lambda v: f"{float(v):,.0f}"
MGR = {m["id"]: m for m in U["managers"]}
ST = {s["statement_id"]: s for s in U["statements"]}
MV = {m["id"]: m for m in U["cash_movements"]}
DOC = {d["id"]: d for d in U["documents"]}
CM = {c["fund"]: c for c in U["commitments"]}
LIM = {l["rule"]: l for l in U["limits_check_30_sep"]}
people = {p["name"]: p for p in U["people"]}
role = lambda name: f"{name} ({people[name]['business_role']})"
FOOT = "Evergreen Office - internal - synthetic data for testing"
files = {}  # name -> (holds, facts)


def d(s):
    x = dt.date.fromisoformat(s)
    return f"{x.day} {x.strftime('%B %Y')}"


def note(doc_id, ref, attendees, agenda, discussion, questions, actions, fname, facts, extra=""):
    doc = DOC[doc_id]
    m = MGR[doc["manager"]]
    body = f"""# Meeting note: {doc['title']}

| | |
|---|---|
| Reference | {ref} |
| Date | {d(doc['document_date'])} |
| Counterparty | {m['name']} ({m['strategy']}) |
| Prepared by | {role('Mei Chen')} |
| Attendees (Evergreen) | {'; '.join(role(a) for a in attendees)} |
| Attendees ({m['name']}) | {m['contact_name']} (investor relations contact) |

## Agenda
""" + "".join(f"{i}. {a}\n" for i, a in enumerate(agenda, 1)) + "\n## Discussion\n" + "".join(f"- {x}\n" for x in discussion) + extra + "\n## Open questions\n" + "".join(f"- [ ] {q}\n" for q in questions) + "\n## Actions\n\n| Owner | Action | By |\n|---|---|---|\n" + "".join(f"| {o} | {a} | {b} |\n" for o, a, b in actions) + f"\n---\n{FOOT} | {ref} | Page 1 of 1\n"
    (OUT / fname).write_text(body, encoding="utf-8")
    files[fname] = (doc["title"], facts)


a_est, a_am = ST["stmt-A-2026-09-30-estimate"], ST["stmt-A-2026-09-30-amended"]
c_f, c_a = ST["stmt-C-2026-06-30-final"], ST["stmt-C-2026-06-30-amended"]
h1f, h1a = ST["stmt-H1-2026-07-31-final"], ST["stmt-H1-2026-07-31-amended"]
d_miss = ST["stmt-D-2026-06-30-missing"]
d_mar = ST["stmt-D-2026-03-31-final"]

note("doc-note-01", "MN-2026-01", ["Daniel Foo", "Mei Chen"],
     ["Fund A (Evergreen Growth I) performance and pipeline", "Exits and distributions", "Reporting timetable"],
     [DOC["doc-note-01"]["key_facts"][0] + " Northgate would not name the buyers.",
      "Distribution of about 300,000 USD guided for Q4 2026 (Fund A commitment " + n(CM['A']['commitment_amount']) + " USD, " + n(CM['A']['called_to_date']) + " called).",
      "Monthly statements continue; estimate first, final follows."],
     ["Timing of the second exit: before or after the 31 December valuation?"],
     [("Mei Chen", "Diary the Q4 distribution as expected, not confirmed", "28 Feb 2026")],
     "01_northgate_annual_meeting_2026-02-11.md",
     "doc-note-01 (two exits 2026, ~300,000 Q4 distribution); Fund A commitments")

note("doc-note-02", "MN-2026-02", ["Daniel Foo", "Raj Patel"],
     ["Private credit book review", "Yield and credit quality", "Fund B drawdown schedule"],
     [DOC["doc-note-02"]["key_facts"][0] + " " + DOC["doc-note-02"]["key_facts"][1],
      f"Fund B commitment {n(CM['B']['commitment_amount'])} USD, {n(CM['B']['called_to_date'])} called, {n(CM['B']['uncalled'])} uncalled.",
      "Bluewater statements name the fund 'Fund B - Evergreen Liquid Book' in some months and 'Evergreen Income II' in others; agreed it is one fund (code 4472)."],
     ["Will Bluewater standardise the fund name on statements?"],
     [("Tom Adeyemi (Bluewater)", "Confirm the single fund name in writing", "30 Apr 2026")],
     "02_bluewater_quarterly_call_2026-04-22.md",
     "doc-note-02 (yield 9.1%, no defaults); P13 same fund under two names (Fund B); Fund B commitments")

note("doc-note-03", "MN-2026-03", ["Daniel Foo", "Mei Chen", "Sofia Reyes"],
     ["Fund C portfolio update", "Fund D reporting and auditor change", "Concentration in Entity B"],
     [DOC["doc-note-03"]["key_facts"][0], DOC["doc-note-03"]["key_facts"][1],
      "Cedarpoint's DDQ commits to quarterly statements within 45 days of quarter end (10 business days for us under the side letter); the auditor change was effective Q2 2026.",
      f"Funds C and D are {n(CM['C']['commitment_amount'])} and {n(CM['D']['commitment_amount'])} USD commitments; together they drive the manager limit in EG-B-OPS (max 55%)."],
     ["When will the Fund D 30 June 2026 statement arrive, given the auditor change?", "Size of the lower-valuation round at the Fund C portfolio company."],
     [("Mei Chen", "Chase Fund D June statement if not in by 14 July", "14 Jul 2026"), ("Sofia Reyes", "Watch Cedarpoint share of EG-B-OPS", "30 Jun 2026")],
     "03_cedarpoint_update_call_2026-05-19.md",
     "doc-note-03 (C lower valuation, D auditor change); P11/P18/P27 background (D June statement, 55% manager limit)")

note("doc-note-04", "MN-2026-04", ["Daniel Foo", "Mei Chen", "Raj Patel"],
     ["Macro fund and Equity L/S fund review", "Fee accruals", "Operations and reporting"],
     [DOC["doc-note-04"]["key_facts"][0], "Fee accruals are reviewed monthly by Kestrel's operations team.",
      "Kestrel statements use the names 'Kestrel Ridge Macro Fund' and 'KR Macro Fund Ltd - Class B USD' for the same fund (code 4481)."],
     ["Do both co-portfolio managers sign off every position change?"],
     [("Mei Chen", "Log Kestrel fee accrual changes against the statement", "19 Jun 2026")],
     "04_kestrel_ridge_onsite_2026-06-12.md",
     "doc-note-04 (two co-PMs, monthly fee review, July restated by 37,500); P13 H1 two names; P26 baseline meeting 12 Jun 2026",
     extra=f"\n## Addendum, {d(h1a['received_at'][:10])}\n\nKestrel restated the July 2026 NAV of the Macro Fund from {n(h1f['value'])} to {n(h1a['value'])} USD (fee accrual correction of {n(float(h1f['value'])-float(h1a['value']))} USD), following the fee accrual review discussed on {d('2026-06-12')}. Mei Chen.\n")

note("doc-note-05", "MN-2026-05", ["Daniel Foo", "Mei Chen", "Raj Patel"],
     ["Fund E portfolio", "Capital call outlook", "Statement timing"],
     [DOC["doc-note-05"]["key_facts"][0],
      f"Fund E commitment {n(CM['E']['commitment_amount'])} USD, {n(CM['E']['called_to_date'])} called, {n(CM['E']['uncalled'])} uncalled.",
      f"The June statement arrived late ({ST['stmt-E-2026-06-30-final']['late_business_days']} business days after 14 July); Saltmarsh will aim for the 10 business day deadline in Q3."],
     ["Will the call be one notice or two?"],
     [("Raj Patel", "Plan cash in Entity B for a 600,000 USD call in Q4", "30 Sep 2026")],
     "05_saltmarsh_q2_call_2026-07-30.md",
     f"doc-note-05 (600,000 USD call Q4 2026; actual notice {n(MV['mv-2026-10-E-call']['amount'])} on {MV['mv-2026-10-E-call']['notice_date']}); P10 Fund E June late 8 bd; Fund E commitments")

note("doc-note-06", "MN-2026-06", ["Mei Chen", "Anita Rao", "Leo Park"],
     ["Service review", "Pricing file format", "Index fund statements"],
     [DOC["doc-note-06"]["key_facts"][0] + " Meridian will give three months' notice.",
      "Funds L1 and L2 statements continue to arrive on the first business day after month end."],
     ["Will the new format keep the same column names?"],
     [("Leo Park", "Review the daily pricing import for a format change", "Q1 2027")],
     "06_meridian_service_review_2026-08-26.md",
     "doc-note-06 (daily pricing file new format 2027)")

# doc-ic-01: the September IC note as the universe holds it (17 Sep 2026); HVS figure from the 31 Aug liquid book
ic, nws = DOC["doc-ic-01"], DOC["doc-news-01"]
sh, hv, hf = LIM["limit_manager_entity_b"], LIM["limit_single_name_liquid"], LIM["limit_hedge_funds"]
aug = U["liquid_book_month_end"]["2026-08-31"]
hvs_aug = next(p for p in aug["positions"] if p["security"] == "HVS")
IC_SEP = "07_investment_committee_note_2026-09-17.md"
(OUT / IC_SEP).write_text(f"""# {ic['title']}

| | |
|---|---|
| Reference | IC-2026-09 |
| Date | {d(ic['document_date'])} |
| Chair | {role('Daniel Foo')} |
| Attendees | {'; '.join(role(x) for x in ['Raj Patel', 'Sofia Reyes', 'Mei Chen'])} |
| Distribution | Investment committee, Evergreen Office |

## 1. Limits
- {ic['key_facts'][0]} At 31 August 2026 the position was {n(hvs_aug['value'])} USD of a liquid book of {n(aug['total'])} USD.

## 2. Benchmark
- {ic['key_facts'][1]}

## Open questions
- [ ] Size and timing of the Harborview Semiconductor trim.

## Decisions
None recorded in this note. Minutes: Mei Chen.

---
{FOOT} | IC-2026-09 | Page 1 of 1
""", encoding="utf-8")
files[IC_SEP] = (ic["title"], "doc-ic-01 (HVS above the 5% single-name limit, desk to trim; benchmark re-weighting to be proposed by Risk)")

# October IC note, dated after the newsletter (28 Sep) and the Fund A amended statement (7 Oct): 8 Oct 2026
body = f"""# Investment committee note, October 2026

| | |
|---|---|
| Reference | IC-2026-10 |
| Date | 8 October 2026 (follows the September note of {d(ic['document_date'])}) |
| Chair | {role('Daniel Foo')} |
| Attendees | {'; '.join(role(x) for x in ['Raj Patel', 'Sofia Reyes', 'Mei Chen'])} |
| Distribution | Investment committee, Evergreen Office |

## 1. Limits
- EG-LIQUID: Harborview Semiconductor at {hv['exposure_pct']}% against the 5% single-name limit ({n(hv['item_value'])} USD). Desk to trim. Unchanged from the September note.
- EG-B-OPS: manager Cedarpoint Ventures at {sh['exposure_pct']}% against the 55% limit (Fund C {n(c_a['value'])} + Fund D {n(d_mar['value'])} = {n(sh['item_value'])} USD of 22,875,000). The cause is stale data, not a trade.

## 2. Stale valuation
Fund D (Cedarpoint Opportunities II) is carried at its 31 March 2026 statement value of {n(d_mar['value'])} USD, 192 days old at 9 October. The 30 June statement was due {d(d_miss['due_date'])} and has not been received; the manager changed auditors in Q2 2026. Fund C is carried at its amended 30 June value of {n(c_a['value'])} USD (previously {n(c_f['value'])}), 101 days old. The breach figure is therefore indicative until Cedarpoint reports.

## 3. Team change at Kestrel Ridge Advisors
Per the Kestrel Ridge Q3 2026 newsletter of {d(nws['document_date'])}: Thomas Lindqvist left the firm on 30 September 2026; Priya Nair is sole portfolio manager of the Macro Fund from 1 October 2026. Our June meeting recorded two co-portfolio managers. The Macro Fund (H1) and Equity Long/Short Fund (H2) together stand at {n(hf['item_value'])} USD, {hf['exposure_pct']}% of EG-FUNDS (range 20-60%).

## 4. Fund A
Northgate's amended September statement ({d(a_am['received_at'][:10])}) shows {n(a_am['value'])} USD against the {n(a_est['value'])} estimate (+{n(float(a_am['value'])-float(a_est['value']))}).

## Open questions
- [ ] Does Cedarpoint give a date for the Fund D June statement?
- [ ] Does the committee want a review of the Macro Fund allocation following the Kestrel team change, or to wait for the next manager call?
- [ ] Benchmark re-weighting to be proposed by Risk (carried from September).

## Decisions
None recorded in this note. Minutes: Mei Chen.

---
{FOOT} | IC-2026-10 | Page 1 of 1
"""
IC = "08_investment_committee_note_2026-10-08.md"
(OUT / IC).write_text(body, encoding="utf-8")
files[IC] = ("Investment committee note, October 2026", "P18 limit breach from stale valuation (56.50%, D 192 days); P25 Kestrel team change; P12 Fund A and C amendments; HVS 5.75% (follows doc-ic-01)")

man = "# Notes fixtures manifest (synthetic)\n\nGenerated by tools/gen_10uc/notes.py from docs/test/10uc_universe.json. Format: markdown (python-docx not installed). 8 files plus this manifest.\n\n| File | Holds | Planted facts / universe items |\n|---|---|---|\n" + "".join(f"| {f} | {h} | {t} |\n" for f, (h, t) in files.items())
(OUT / "MANIFEST.md").write_text(man, encoding="utf-8")

# verify by re-reading
rd = lambda f: (OUT / f).read_text(encoding="utf-8")
fl = list(files)
assert n(CM['A']['commitment_amount']) in rd(fl[0]) and "300,000" in rd(fl[0])
assert "9.1%" in rd(fl[1]) and n(CM['B']['uncalled']) in rd(fl[1])
assert "auditor" in rd(fl[2]) and "55%" in rd(fl[2])
assert "7,050,000" in rd(fl[3]) and "7,012,500" in rd(fl[3]) and "37,500" in rd(fl[3])
assert "600,000" in rd(fl[4]) and n(CM['E']['uncalled']) in rd(fl[4]) and "8 business" in rd(fl[4])
assert "new format" in rd(fl[5])
t = rd(IC)
for s in ["56.50%", "12,925,000", "192 days", "8,275,000", "8,420,000", "4,650,000", "Thomas Lindqvist", "Priya Nair", "10,180,000", "180,000", "5.75%", "54.95%"]:
    assert s in t, s
assert float(c_a['value']) + float(d_mar['value']) == float(sh['item_value'])
print(len(fl) + 1, "files written to", OUT)
