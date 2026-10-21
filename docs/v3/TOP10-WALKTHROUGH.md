# Top 10 use cases, walked through live

Audience: Nitin, to present. Every number, sentence and figure below is copied from the saved office data (the thread files, the figure records, the skill-run log, the model-cost log and the live Consume screens), not written from memory. Synthetic data only: the office is "Evergreen Office" in the test environment at `http://127.0.0.1:8780`.

Source files: thread files in `D:/Temp/sh3-fresh2/evergreen/v3/threads/`, figure records in `.../v3/figures/`, skill log `.../v3/skill_runs.jsonl`, model cost log `.../context/model_costs.jsonl`, second-model log `.../v3/judge/log.json`; run reports in `D:/Temp/sh3-top10/`; use case definitions in `packs/family_office/1/builds/*.yaml` and `role_builds.yaml`; recipes in `packs/family_office/1/recipes/*.yaml`. Structured version: `docs/v3/top10/facts.json`. Machine view of the machinery: `docs/v3/HOW-HARBOR-WORKS.md`.

## Overview

| # | Use case | Person | Minutes | Figures built (with rows) | Files used (new to this case) | Reused from earlier |
|---|---|---|---|---|---|---|
| 1 | `uc-001-noticelog`: A Cedarpoint call notice just came in by email | Sam Lee (ops_clerk) | 10.5 | 5 (4 built) | 19 | 0 figure(s) |
| 2 | `uc-002-callrecord`: Daniel's team just handed me | Helen Foo (fund_accountant) | 4.9 | 6 (6 built) | 1 | 2 figure(s) |
| 3 | `uc-004-callcheck`: Call payment feasibility | Daniel Foo (cfo) | 2.2 | 3 (3 built) | 0 | 0 figure(s) |
| 4 | `uc-005-benefcheck`: The Cedarpoint call 7 notice says | Grace Ong (ops_lead) | 11.8 | 6 (5 built) | 0 | 3 figure(s) |
| 5 | `uc-008-payrun`: Payment run KPIs | Grace Ong (ops_lead) | 7.8 | 6 (6 built) | 0 | 0 figure(s) |
| 6 | `uc-016-schemadrift`: Monthly pack | Anita Rao (head_of_data) | 6.7 | 7 (7 built) | 0 | 3 figure(s) |
| 7 | `uc2-recon-break-desk`: Every morning I check cash | Grace Ong (ops_lead) | 10.9 | 3 (2 built) | 0 | 1 figure(s) |
| 8 | `uc4-vs-benchmark`: Monthly performance line for Evergreen Liquid portfolio | Raj Patel (cio) | 1.7 | 1 (1 built) | 3 | 0 figure(s) |
| 9 | `uc5-limits`: To test the liquid book | Tom Hale (risk_officer) | 6.9 | 6 (4 built) | 0 | 2 figure(s) |
| 10 | `morning-networth-note`: Each morning I would like | Mei Chen (principal) | 7.1 | 3 (3 built) | 5 | 0 figure(s) |

"Files used" counts the files this case dropped and Harbor read. Cases 3, 4, 5, 6, 7, 9 dropped none: they worked from the office folder that earlier cases had already loaded ("already in the office" below). Case 1 recognised 708 files in the office folder; later cases' thread files list no pack of their own, and their workbench reports how many sources were already in the office.

## Read this first (what to check before presenting)

- Consume answers: 7 of the 10 captured answers say 'Answered in 12 to 34 ms (from memory)'. The office keeps answers in memory per data version and answers the golden questions ahead after each live run (HOW doc, step 6), so these are the cached answers for the current data, not fresh calculations. The wording and numbers match each run report; say so if asked.
- Case 1 (uc-001-noticelog) went live with `Funding headroom (six‑month)` not built: The design was refused: The plan check refused gold_a_cedarpoint_call_notice_just_funding_headroom_six_month. Span dropped gold_a_cedarpoint_call_notice_just_funding_headroom_six_month: The SQL for gold_a_cedarpoint_call_not
- Case 4 (uc-005-benefcheck) went live with `Minimum six‑month funding headroom` not built: no table of the company model holds its records, so it is not in a gold table yet. Ask Span for a model change if a new fact must be kept.
- Case 4 (uc-005-benefcheck): step 'Ran on a copy' failed once (The run on the copy stopped at the step that builds This project is already running. Please wait for it to finish.: This project is already running. Please wait for it to finish.. Send the design back...); the person typed 'retry' and it passed.
- Case 5 (uc-008-payrun): 5 figures (Ready payments count; Pending approvals count; Held payments count; Total amount by currency; Payments over their approval limit) point at the same gold table `gold_every_thursday_i_prepare_the_p_approval_exceptions` (151 rows). Unless the table holds a column for each, the count figures are not derived from their own rows; check before presenting them as separate numbers. (The count and total figures are listed with the approval-limit figure that the table was built for.)
- Case 7 (uc2-recon-break-desk) went live with `Number of breaks over threshold` not built: it is a share or a count under a condition, which a plain total of the exceptions cannot give, so it is not in a gold table yet.
- Case 8 (uc4-vs-benchmark): went live without a starter board (Lumen: no figure has a ready table yet, so the board appears after a later live run).
- Case 9 (uc5-limits) went live with `Listed equity allocation` not built: The run did not build allocation by asset class entity.
- Case 9 (uc5-limits) went live with `Stale‑valuation share` not built: The run did not build value age days.
- Case 9 (uc5-limits): step 'Applied your answers' failed once (1 mapping row still need a person: settle them first.); the person typed 'retry' and it passed.

In the run window (07:39 to 08:53 UTC) the cost log has 166 model-call rows: 76 carry one of the ten threads intent id and are counted per case; the other 90 (Span plan, summary and extraction calls, and the connector calls) have no intent id, so the per-case model counts are a floor. Window cost: about USD 0.067. Models: openai/gpt-oss-120b (specialist and manager tiers) and qwen/qwen3.7-flash (fast tier: the worker side of the second-model checks, and extraction). Mode: testing (the default cheap models).

Minutes are the sum of the stage times in the run report (drafting, decision 1, working, decision 2, decision 3, plus any question). "Figures built" are the figure records at decision 3; a figure that could not be built is counted but not built (see its section).

## 1. A Cedarpoint call notice just came in by email  (`uc-001-noticelog`)

**Person:** Sam Lee (ops_clerk). **Thread:** `t-789db690f5`, created 07:39 UTC, live 07:49 UTC (10.3 min from first message to live). **Run:** `run-20261021-074907-5ae2`, next run daily at 06:00. **Stage reached:** live.

**Time per stage (run report, seconds):** drafting 206, decision1 3, working 413, decision2 3, decision3 3. **Total:** 628 s = 10.5 min.

### Intent

- **What the person said:** "A Cedarpoint call notice just came in by email. Tell me which fund it is for, how much, by when, what the money is for and which account it is to be paid into, so I can log it and hand it to Helen."
- **Harbor's one-line restatement (brief):** A Cedarpoint call notice just came in by email.
- **What it is built to show (use case definition):** Action: the notice read with page and quoted line, ready to log; notices logged and not yet recorded.
- **Check question:** "A Cedarpoint call notice just came in by email. Which fund, how much and by when?"; numbers that must appear: 1,250,000, 900,000, 350,000, 4471.

### Decision 1: what Harbor drafted

North asked: "I have drafted suggested usual practice for each area and marked them as changeable. Could you confirm the list of KPIs you need included, or add any others? I have drafted KPI Net worth, KPI Time‑weighted return net of fees, KPI Funding headroom (six‑month), source Custodian statement and 11 more; say yes to accept, or tell me what is wrong."

Signed by Sam Lee at 2026-10-21T07:43:07+00:00.

| Figure (as drafted) | What it means | How it is worked out | Built from | Owner | How often |
|---|---|---|---|---|---|
| Net worth | Total value of all assets including private‑market positions, less liabilities. | Sum of market values of holdings plus cash minus liabilities. | Net worth recipe (suggested) | Operations | monthly |
| Time‑weighted return net of fees | Monthly chained return, net of all fees, compared to the blended benchmark. | Standard TWR calculation using NAVs and cash flows, net of fees. | Time weighted return and active return recipe (suggested) | Performance team | monthly |
| Funding headroom (six‑month) | Minimum cash available over the next six months after accounting for known obligations and proposed funding. | Opening cash + approved inflows – known obligations – scenario‑only calls – proposed funding – reserve (threshold). | No recipe yet: Span designs it (suggested) | Treasury | monthly |
| Capital call payment status | For each call (not cancelled, not superseded) with a due date, paid when a confirmed payment movement of the same fund, currency and amount (compared as positive numbers, A5) has the call's due date as its value date. A call past its due date with no such payment is not paid; a due date after the latest movement date on file is not due. | For each call (not cancelled, not superseded) with a due date, paid when a confirmed payment movement of the same fund, currency and amount (compared as positive numbers, A5) has the call's due date as its value date. A call past its due date with no such payment is not paid; a due date after the latest movement date on file is not due. | Capital call payment status recipe (suggested) | Operations | monthly |
| Capital call notice, as read | For each capital call notice (documents of type capital_call_notice that no later document replaces; the same fund and call number received twice is listed once, with copies counting the documents), the fund, the investor, the call number, the amount and currency, the due date, the purpose split (new investments and management fee) and the last four characters of the wire account, from the notice's extracted fields (a reviewer's correction wins over the reading, text or number; a correction that is not a number leaves the figure empty). The page of the amount is kept for the receipt. | For each capital call notice (documents of type capital_call_notice that no later document replaces; the same fund and call number received twice is listed once, with copies counting the documents), the fund, the investor, the call number, the amount and currency, the due date, the purpose split (new investments and management fee) and the last four characters of the wire account, from the notice's extracted fields (a reviewer's correction wins over the reading, text or number; a correction that is not a number leaves the figure empty). The page of the amount is kept for the receipt. | Capital call notice, as read recipe (suggested) | Operations | monthly |

Process map Harbor proposed (today's way): 1. Collect statements (Sam Lee): Download custodian statement, bank balance report and fund portal extracts ; 2. Reconcile positions (Sam Lee): Match positions and cash against ledger, resolve breaks ; 3. Value private funds (PERSON_002): Apply latest NAVs, incorporate calls and distributions ; 4. Apply manual adjustments (PERSON_003): Enter approved fee, policy exception or correction entries ; 5. Build pack (PERSON_004): Populate KPI pages, assemble PDF ; 6. Review & approve (PERSON_003): Sign off pack, confirm no open issues ; 7. Distribute (PERSON_005): Upload approved pack to governance portal and email Investment Committee.

Recipe bindings (figure to recipe, from the rules): Net worth -> net_worth (Its name or definition names the net worth recipe.); Time‑weighted return net of fees -> time_weighted_return (Its name or definition names the time weighted return and active return recipe.); Funding headroom (six‑month) -> none, Span designs it (No recipe of the pack computes it; Span designs it.); Capital call payment status -> call_payment_status (Your question asks for the capital call payment status and no figure of the brief is built from it.); Capital call notice, as read -> call_notice_fields (Your question asks for the capital call notice, as read and no figure of the brief is built from it.).

### Decision 2: files, kinds, readers, tables

- **Sources named in the brief:** Custodian statement; Bank balance report; Private‑fund portal data; Call notice email.
- **Systems Span read:** Custodian statement; Bank balance report; Private‑fund portal data; Call notice email.
- **Files this case dropped and Harbor read (19):** `handover_email_mei_to_raj.txt`, `2026-09-01_call_D_5.eml`, `2026-09-02_call_G_4.eml`, `2026-09-08_call_E_5.eml`, `2026-10-13_call_C_7.eml`, `05_saltmarsh_q2_call_2026-07-30.md`, `2026-07-07_call_C_6.eml`, `2026-07-28_chase_cedarpoint_07.eml`, `2026-08-04_call_F_2.eml`, `2026-08-11_call_K_2.eml`, `2026-08-28_lakeside_new_bank_details.eml`, `02_bluewater_quarterly_call_2026-04-22.md`, `03_cedarpoint_update_call_2026-05-19.md`, `2026-05-05_call_E_4.eml`, `2026-06-03_call_A_11.eml`, `2026-06-10_call_G_3.eml`, `2026-04-07_call_C_5.eml`, `IMG_2210.pdf`, `data_export.xlsx`.
- **Kind each file was recognised as:** the thread does not write a kind per file; the office folder has 708 files in its pack map. Emails and Word/markdown notes were read as context (not as a table); PDFs and sheets were read by the reader named below.
- **Readers that loaded them (skills run on this case):** `data.recognise-file`, `data.profile-file`, `data.read-pdf-fields`, `map.map-file`, `data.read-reference-data`, `data.read-commitments-register`, `data.read-administrator-nav`, `data.read-administrator-cash`, `data.read-custodian-positions`, `data.read-bank-statement`, `data.read-custodian-transactions`, `data.read-trading-export`, `data.read-administrator-trades`, `data.read-fx-rates`, `data.read-index-levels`, `data.read-manager-statement`, `data.read-notice`, `data.read-fx-confirmation`, `data.read-invoice`, `data.read-payroll`, `data.read-loan-statement`, `data.read-vendor-contract`, `data.read-family-allowances`, `data.read-insurance-notice`, `data.read-property-bill`, `data.read-property-valuation`, `data.read-title-deed`, `data.read-insurance-schedule`, `data.read-custody-statement`, `data.read-approvals`, `data.read-close-checklist`, `data.read-exception-log`, `data.read-investment-report`, `data.read-audit-request`, `data.read-ddq`, `data.read-fund-teaser`, `data.read-received-log`, `data.read-payment-schedule`, `data.read-income-calendar`, `data.read-corporate-action`, `data.read-settlement-status`, `data.read-tax-lots`, `data.read-manager-outlook`, `data.read-expense-ledger`, `data.read-office-budget`, `data.read-payroll-draft`, `data.read-sop`, `data.read-access-register`, `data.read-kyc-register`, `data.read-onboarding`, `data.read-bank-form`, `data.read-family-access`, `data.read-glossary`, `data.read-break-register`, `data.read-load-log`, `data.read-inbox`, `data.read-new-feed`, `data.read-tax-calendar`, `data.read-tax-notice`, `data.read-grant-ledger`, `data.read-grant-request`, `data.read-trust-deed`, `data.read-estate-memo`, `data.read-fund-holdings`, `data.read-deal-pipeline`, `data.read-redemption-terms`, `data.read-second-source-prices`, `data.read-target-allocation`.
- **Already in the office (reused from earlier cases):** none reported.
- **Answers the person gave to Harbor questions:** Monthly, Use my reading.
- **Loaded:** "708 files loaded, 1 set aside". Left out: bank_balance_report, call_notice_email, custodian_statement. Exceptions: data_export.xlsx did not load: Nothing was loaded. All 4 rows are held back. Row 2: no portfolio in the row..
- **File mapping Harbor proposed and the person answered:** data_export.xlsx -> position_snapshots (confidence 0.25, unmapped Ref, Amt1, Amt2). Answer: Monthly, Use my reading.
- **Learned for next time:** data_export.xlsx: Use my reading.
- **Tables loaded with row counts:** `instruments` 59 rows; `legal_entities` 3 rows; `portfolios` 8 rows; `position_snapshots` 6,329 rows; `market_observations` 614 rows; `transactions` 75 rows; `cash_movements` 557 rows; `documents` 382 rows. These are the row counts in the office now, after all ten cases; the office did not keep a per-case count, so the figures here are not a snapshot at the time of the run.

### Decision 3: figures, recipes, gold tables, checks

| Figure | Version at live | Status | Gold table | Rows | Recipe (what Harbor used) | Formula in words | Tie-out | Reused from earlier |
|---|---|---|---|---|---|---|---|---|
| Net worth (`fig-net-worth`) | v1 | verified | `gold_a_cedarpoint_call_notice_just_net_worth_by_portfolio` | 1008 | `net_worth`: Net worth | Net worth = the sum of the market values of the position snapshots of each date, one value for each portfolio, instrument, date and currency (a snapshot that a later one supersedes is out; a carried-f... | ok: Net worth equals the sum of the position snapshots for the same dates, cash counted once | no |
| Time‑weighted return net of fees (`fig-time-weighted-return-net-of-fees`) | v1 | verified | `gold_a_cedarpoint_call_notice_just_time_weighted_return` | 83 | `time_weighted_return`: Time weighted return and active return | Monthly return in percent (modified Dietz; a month is one whose end is a month end, a month still open is left out) = (end value - start value - net flow) / (start value + 0.5 x net flow) x 100, where... | ok: The month-end values used are the position snapshots of the same dates | no |
| Funding headroom (six‑month) (`fig-funding-headroom-six-month`) | v1 | held | not built: The design was refused: The plan check refused gold_a_cedarpoint_call_notice_just_funding_headroom_six_month. Span dropped gold_a_cedarpoint_call_notice_just_funding_headroom_six_month: The SQL for gold_a_cedarpoint_call_not |  | none: Span designed the table |  | n/a | no |
| Capital call payment status (`fig-capital-call-payment-status`) | v1 | verified | `gold_a_cedarpoint_call_notice_just_call_payment_status` | 11 | `call_payment_status`: Capital call payment status | For each call (not cancelled, not superseded) with a due date, paid when a confirmed payment movement of the same fund, currency and amount (compared as positive numbers, A5) has the call's due date a... | ok: Every call with a due date has one row | no |
| Capital call notice, as read (`fig-capital-call-notice-as-read`) | v1 | verified | `gold_a_cedarpoint_call_notice_just_call_notice_fields` | 11 | `call_notice_fields`: Capital call notice, as read | For each capital call notice (documents of type capital_call_notice that no later document replaces; the same fund and call number received twice is listed once, with copies counting the documents), t... | ok: The purpose split adds up to the amount called | no |

- **Checks at decision 3:** adds-up: "0 ready tables added; no table for Funding headroom (six‑month); 4 of 5 figures have rows". Against the report: "compared with EG-OFFICE-BLEND_Benchmark_Specification_2026-10.xlsx".
- **Notes on figures that were not built:** Funding headroom (six‑month): The design was refused: The plan check refused gold_a_cedarpoint_call_notice_just_funding_headroom_six_month. Span dropped gold_a_cedarpoint_call_notice_just_funding_headroom_six_month: The SQL for gold_a_cedarpoint_call_not.
- **Second-model checks (worker and checker from different families, logged in `judge/log.json`), in this case's window:**
  - 07:42:57 UTC, recipe: did not agree (a person is asked). Question: (text not logged in judge/log.json)

### Skills run

100 of 100 skill calls succeeded, from `skill_runs.jsonl` for this thread. Skills used: 21 skill-folder skills and 65 per-kind file readers (data.read-<kind>). Most used: `model.design-ready-table` x7, `check.adds-up` x3, `intent.define-figure` x2, `model.find-reusable` x2, `data.recognise-file` x2, `data.profile-file` x2, `data.read-pdf-fields` x2, `data.read-tax-lots` x2.
- Workbench steps (the thread's own log): 1. North: Signed the intent (ok; signed and sent to Build) | 2. North: Handed over to build (ok; handed to the data engineer) | 3. Span: Read the systems (ok; 4 systems, 0 questions assumed) | 4. Span: Read the sample files (ok; 727 files given to Span as samples) | 5. Span: Drafted and approved the design pack (ok; design pack approved) | 6. Flow: Read the dropped files (ok; 727 files read, 1 mappings proposed) | 7. Span: Applied your answers (ok; 6 answers applied) | 8. Flow: Accepted the mappings and loaded (ok; 708 files loaded, 1 set aside) | 9. Flow: Ran on a copy (ok; ran on a copy) | 10. Span: Made sure each figure has a filled ready table (ok; 0 ready tables added; no table for Funding headroom (six‑month); 4 of 5 figures have rows) | 11. Flow: Compared with the report (ok; compared with EG-OFFICE-BLEND_Benchmark_Specification_2026-10.xlsx) | 12. Flow: Went live (ok; live on daily at 06:00) | 13. Lumen: Built the starter board (ok; Lumen starter board accepted and published) | 14. Lumen: Wrote the morning note (ok; morning note written) | 15. Flow: Recorded the run on each figure (ok; run recorded on 4 figures).

**Model calls recorded for this case:** 5 (openai/gpt-oss-120b x5; tiers specialist x5); estimated cost USD 0.0025. Source: `model_costs.jsonl`, rows with this thread's intent id.

### Live answer and its receipt

- **Check question (asked in Consume, as Sam Lee):** "A Cedarpoint call notice just came in by email. Which fund, how much and by when?"
- **Answer word for word (Consume screen):** "Cedarpoint Ventures III call 7: USD 1,250,000 (USD 900,000 for investments, USD 350,000 fee) due 23 Oct 2026, to the account ending 4471."
- **Heading on screen:** CAPITAL CALL NOTICE, AS READ · SALTMARSH INFRASTRUCTURE FUND II · ENTITY B · USD · 7741
- **Source line on screen:** Source: a cedarpoint call notice just call notice fields, a cedarpoint call notice just call payment status
- **Same answer in the run report:** "Cedarpoint Ventures III call 7: USD 1,250,000 (USD 900,000 for investments, USD 350,000 fee) due 23 Oct 2026, to the account ending 4471."
- **Screen timing:** not in the captured text.
- **Check (numbers that must appear on screen):** 1,250,000, 900,000, 350,000, 4471; all present: yes.
- **Receipt (Where this number comes from):** the figure page `http://127.0.0.1:8780/v3/knowledge/figures/fig-capital-call-notice-as-read`. The figure is Capital call notice, as read (`fig-capital-call-notice-as-read`): built from Capital call notice, as read; reads documents, extracted_fields, instruments; approved by Grace Ong; versions [1, 2, 3] on record. 

### Left for the next ones

- Figures this case built that later cases used: Net worth (used again by uc-002-callrecord, uc-005-benefcheck, uc-016-schemadrift); Time‑weighted return net of fees (used again by uc-016-schemadrift); Capital call payment status (used again by uc-005-benefcheck); Capital call notice, as read (used again by uc-002-callrecord, uc-005-benefcheck).
- Figures this case reused from earlier cases: none.

### Screens

- Thread page at live: `docs/v3/top10/shots/uc-001-noticelog-thread-live.png`
- Consume answer, with "Show the figures" opened: `docs/v3/top10/shots/uc-001-noticelog-consume-check.png`
- One figure page (Knowledge > Figures): `docs/v3/top10/shots/uc-001-noticelog-figure.png`

## 2. Daniel's team just handed me  (`uc-002-callrecord`)

**Person:** Helen Foo (fund_accountant). **Thread:** `t-b426e8df0b`, created 07:50 UTC, live 07:55 UTC (4.8 min from first message to live). **Run:** `run-20261021-075453-8736`, next run monthly at 06:00. **Stage reached:** live.

**Time per stage (run report, seconds):** drafting 246, decision1 6, working 36, decision2 3, decision3 3. **Total:** 294 s = 4.9 min.

### Intent

- **What the person said:** "Daniel's team just handed me the Cedarpoint call 7 notice. Before I record it, tell me whether it fits what we committed to Cedarpoint Ventures III, what is left after it, and whether the fee part is what the fund terms say. If anything is off, stop it and send it to Daniel with the difference."
- **Read by / decides / when:** Investment Committee; decide portfolio allocations; month‑end
- **What it is built to show (use case definition):** Consume: commitment, called and unfunded for the fund, with the notice added.
- **Check question:** "Does call 7 fit what we committed to Cedarpoint Ventures III, and what is left after it?"; numbers that must appear: 10,000,000, 6,000,000, 7,250,000, 2,750,000.

### Decision 1: what Harbor drafted

North asked: "I don’t have the call notice details nor the commitment terms for Cedarpoint Ventures III; which document or system holds the commitment terms for Cedarpoint Ventures III? I have drafted source Cedarpoint call 7 notice, source Cedarpoint Ventures III commitment terms and 1 open question; say yes to accept, or tell me what is wrong. I am filling the open parts with the usual practice now, marked as suggestions." | "I’ll draft the usual set‑up: the result is a monthly pack with a page per KPI (Net Worth, Time‑Weighted Return, Allocation Drift) and a section for the call notice details; success is the pack published on the agreed month‑end date with no manual re‑work; frequency is monthly at month‑end; the primary reader is the Investment Committee who decides on portfolio allocations. Does the Investment Committee sound right as the main reader and decision‑maker? I have drafted who reads it, what they decide, when it is needed, frequency and success; say yes to accept, or tell me what is wrong." | "I'll draft the usual practice for the remaining sections and suggest extraction fields for the call notice. Does extracting fund, investor, call number, amount, currency, due date, purpose split and wire‑account tail from each call notice sound right? I am filling the open parts with the usual practice now, marked as suggestions." | "The pack would be a monthly PDF with a page for each KPI (Net Worth, Time‑Weighted Return, Allocation Drift) plus a section listing call‑notice details (fund, investor, call number, amount, currency, due date, purpose split and wire‑account tail). I’ve sketched a process map with lanes for Operations, Review and Approval and the steps from receiving files to distribution. Who should own the step that reviews the compiled pack before it is approved? I have drafted result and 7 process steps; say yes to accept, or tell me what is wrong."

Signed by Helen Foo at 2026-10-21T07:54:40+00:00.

| Figure (as drafted) | What it means | How it is worked out | Built from | Owner | How often |
|---|---|---|---|---|---|
| Net Worth | Total value of all assets including private‑fund holdings |  | Net worth recipe (suggested) | Daniel | monthly |
| Time‑Weighted Return | Net‑of‑fees return, chained month‑over‑month |  | Time weighted return and active return recipe (suggested) | Daniel | monthly |
| Allocation Drift | Difference between actual allocation and policy ranges |  | Drift from the policy band and target recipe (suggested) | Daniel | monthly |
| Called to date and unfunded | Called before the notice = the called amount the commitment file states at its as-at date, plus the confirmed call movements after that date in the commitment's currency. A noticed call not yet recorded (received on or after the file's as-at date; an earlier one is in the stated figure) is added for "after the notice". A call posted to a commitment row that a later row replaced counts for the row that replaced it. Unfunded = commitment less called. A noticed call larger than the unfunded amount before it does not fit, and neither does a call in another currency than the commitment (calls_in_other_currency counts them; they are not added). | Called before the notice = the called amount the commitment file states at its as-at date, plus the confirmed call movements after that date in the commitment's currency. A noticed call not yet recorded (received on or after the file's as-at date; an earlier one is in the stated figure) is added for "after the notice". A call posted to a commitment row that a later row replaced counts for the row that replaced it. Unfunded = commitment less called. A noticed call larger than the unfunded amount before it does not fit, and neither does a call in another currency than the commitment (calls_in_other_currency counts them; they are not added). | Called to date and unfunded recipe (suggested) | Daniel | monthly |
| Fee part of a call against the fund terms | Fee on the notice (read from the notice) against the management fee rate in the fund terms (extracted field management_fee_rate, a fraction of the commitment per billing) times the commitment of the investor the notice names (extracted field investor; when the notice names none and the fund has one commitment, that one). Difference = fee on the notice less the fee per terms. It matches when the difference is under one cent. With no rate on record, no commitment, or several investors and none named, the fee cannot be checked and fee_matches is empty; fee_basis says why. | Fee on the notice (read from the notice) against the management fee rate in the fund terms (extracted field management_fee_rate, a fraction of the commitment per billing) times the commitment of the investor the notice names (extracted field investor; when the notice names none and the fund has one commitment, that one). Difference = fee on the notice less the fee per terms. It matches when the difference is under one cent. With no rate on record, no commitment, or several investors and none named, the fee cannot be checked and fee_matches is empty; fee_basis says why. | Fee part of a call against the fund terms recipe (suggested) | Daniel | monthly |
| Capital call notice, as read | For each capital call notice (documents of type capital_call_notice that no later document replaces; the same fund and call number received twice is listed once, with copies counting the documents), the fund, the investor, the call number, the amount and currency, the due date, the purpose split (new investments and management fee) and the last four characters of the wire account, from the notice's extracted fields (a reviewer's correction wins over the reading, text or number; a correction that is not a number leaves the figure empty). The page of the amount is kept for the receipt. | For each capital call notice (documents of type capital_call_notice that no later document replaces; the same fund and call number received twice is listed once, with copies counting the documents), the fund, the investor, the call number, the amount and currency, the due date, the purpose split (new investments and management fee) and the last four characters of the wire account, from the notice's extracted fields (a reviewer's correction wins over the reading, text or number; a correction that is not a number leaves the figure empty). The page of the amount is kept for the receipt. | Capital call notice, as read recipe (suggested) | Daniel | monthly |

Process map Harbor proposed (today's way): 1. Receive custodian positions (Daniel): Pull daily positions file from custodian system ; 2. Reconcile positions and cash (Daniel): Match positions and cash against internal ledger ; 3. Value private funds (Daniel): Load latest NAV from fund portal and apply calls/distributions ; 4. Calculate KPIs (Daniel): Compute Net Worth, TWR, Allocation Drift using reconciled data ; 5. Compile pack (Daniel): Assemble pages per KPI and call‑notice section into PDF ; 6. Review pack (Helen Foo): Check accuracy and completeness ; 7. Approve and distribute (Helen Foo): Approve and send to Investment Committee.

Recipe bindings (figure to recipe, from the rules): Net Worth -> net_worth (Its name or definition names the net worth recipe.); Time‑Weighted Return -> time_weighted_return (Its name or definition names the time weighted return and active return recipe.); Allocation Drift -> drift_vs_target (Its name or definition names the drift from the policy band and target recipe.); Called to date and unfunded -> called_to_date (Your question asks for the called to date and unfunded and no figure of the brief is built from it.); Fee part of a call against the fund terms -> call_fee_check (Your question asks for the fee part of a call against the fund terms and no figure of the brief is built from it.); Capital call notice, as read -> call_notice_fields (Your question asks for the capital call notice, as read and no figure of the brief is built from it.).

### Decision 2: files, kinds, readers, tables

- **Sources named in the brief:** Cedarpoint call 7 notice; Cedarpoint Ventures III commitment terms.
- **Systems Span read:** Cedarpoint call 7 notice; Cedarpoint Ventures III commitment terms.
- **Files this case dropped and Harbor read (1):** `2026-05-04_internal_daniel.eml`.
- **Kind each file was recognised as:** the thread does not write a kind per file; the office folder has 0 files in its pack map. Emails and Word/markdown notes were read as context (not as a table); PDFs and sheets were read by the reader named below.
- **Readers that loaded them (skills run on this case):** `data.recognise-file`, `data.profile-file`, `map.map-file`, `data.read-pdf-fields`.
- **Already in the office (reused from earlier cases):** 2 sources already in the office (from the workbench step: 1 files read, 0 mappings proposed, 2 sources already in the office).
- **Answers the person gave to Harbor questions:** none.
- **Loaded:** "0 files loaded". Left out: cedarpoint_call_7_notice, cedarpoint_ventures_iii. Exceptions: none.
- **Tables loaded with row counts:** `instruments` 59 rows; `legal_entities` 3 rows; `portfolios` 8 rows; `position_snapshots` 6,329 rows; `market_observations` 614 rows; `transactions` 75 rows; `cash_movements` 557 rows; `commitments` 61 rows; `documents` 382 rows. These are the row counts in the office now, after all ten cases; the office did not keep a per-case count, so the figures here are not a snapshot at the time of the run.

### Decision 3: figures, recipes, gold tables, checks

| Figure | Version at live | Status | Gold table | Rows | Recipe (what Harbor used) | Formula in words | Tie-out | Reused from earlier |
|---|---|---|---|---|---|---|---|---|
| Net Worth (`fig-net-worth`) | v2 | verified | `gold_daniel_s_team_just_handed_me_net_worth_by_portfolio` | 1008 | `net_worth`: Net worth | Net worth = the sum of the market values of the position snapshots of each date, one value for each portfolio, instrument, date and currency (a snapshot that a later one supersedes is out; a carried-f... | ok: Net worth equals the sum of the position snapshots for the same dates, cash counted once | yes |
| Time‑Weighted Return (`fig-time-weighted-return`) | v1 | verified | `gold_daniel_s_team_just_handed_me_time_weighted_return` | 83 | `time_weighted_return`: Time weighted return and active return | Monthly return in percent (modified Dietz; a month is one whose end is a month end, a month still open is left out) = (end value - start value - net flow) / (start value + 0.5 x net flow) x 100, where... | ok: The month-end values used are the position snapshots of the same dates | no |
| Allocation Drift (`fig-allocation-drift`) | v1 | verified | `gold_daniel_s_team_just_handed_me_drift_vs_target` | 3 | `drift_vs_target`: Drift from the policy band and target | For the the latest month-end position date (a month end is the last day of the month or its last business day; a date in a month still open is not one) of each portfolio that has signed policy limits ... | ok: The portfolio totals used equal the position snapshots of the same portfolios and dates, and every share is between 0 and 100 | no |
| Called to date and unfunded (`fig-called-to-date-and-unfunded`) | v1 | verified | `gold_daniel_s_team_just_handed_me_called_to_date` | 8 | `called_to_date`: Called to date and unfunded | Called before the notice = the called amount the commitment file states at its as-at date, plus the confirmed call movements after that date in the commitment's currency. A noticed call not yet record... | ok: Called before the notice equals, commitment by commitment, the called amount the commitment file states plus the confirmed calls recorded after its as-at date | no |
| Fee part of a call against the fund terms (`fig-fee-part-of-a-call-against-the-fund-terms`) | v1 | verified | `gold_daniel_s_team_just_handed_me_call_fee_check` | 9 | `call_fee_check`: Fee part of a call against the fund terms | Fee on the notice (read from the notice) against the management fee rate in the fund terms (extracted field management_fee_rate, a fraction of the commitment per billing) times the commitment of the i... | ok: Every call notice with a fee is checked once | no |
| Capital call notice, as read (`fig-capital-call-notice-as-read`) | v2 | verified | `gold_daniel_s_team_just_handed_me_call_notice_fields` | 11 | `call_notice_fields`: Capital call notice, as read | For each capital call notice (documents of type capital_call_notice that no later document replaces; the same fund and call number received twice is listed once, with copies counting the documents), t... | ok: The purpose split adds up to the amount called | yes |

- **Checks at decision 3:** adds-up: "all 6 figures have a ready table; 6 of 6 figures have rows". Against the report: "no report to compare with".
- **Second-model checks:** none in this case's window (the checks use the figure rules and the tie-outs above).

### Skills run

38 of 38 skill calls succeeded, from `skill_runs.jsonl` for this thread. Skills used: 21 skill-folder skills and 1 per-kind file readers (data.read-<kind>). Most used: `model.design-ready-table` x8, `intent.define-figure` x3, `check.adds-up` x3, `intent.restate-ask` x2, `intent.find-gaps` x2, `intent.fill-with-practice` x2, `model.find-reusable` x2, `data.recognise-file` x2.
- Workbench steps (the thread's own log): 1. North: Signed the intent (ok; signed and sent to Build) | 2. North: Handed over to build (ok; handed to the data engineer) | 3. Span: Read the systems (ok; 2 systems, 0 questions assumed) | 4. Span: Read the sample files (ok; 5 files given to Span as samples) | 5. Span: Drafted and approved the design pack (ok; design pack approved) | 6. Flow: Read the dropped files (ok; 1 files read, 0 mappings proposed, 2 sources already in the office) | 7. Span: Applied your answers (ok; 0 answers applied) | 8. Flow: Accepted the mappings and loaded (ok; 0 files loaded) | 9. Flow: Ran on a copy (ok; ran on a copy) | 10. Span: Made sure each figure has a filled ready table (ok; all 6 figures have a ready table; 6 of 6 figures have rows) | 11. Flow: Compared with the report (ok; no report to compare with) | 12. Flow: Went live (ok; live on monthly at 06:00) | 13. Lumen: Built the starter board (ok; Lumen starter board accepted and published) | 14. Lumen: Wrote the morning note (ok; morning note written) | 15. Flow: Recorded the run on each figure (ok; run recorded on 6 figures).

**Model calls recorded for this case:** 8 (openai/gpt-oss-120b x8; tiers specialist x7, manager x1); estimated cost USD 0.0042. Source: `model_costs.jsonl`, rows with this thread's intent id.

### Live answer and its receipt

- **Check question (asked in Consume, as Helen Foo):** "Does call 7 fit what we committed to Cedarpoint Ventures III, and what is left after it?"
- **Answer word for word (Consume screen):** "Yes. The USD 1,250,000 call fits Cedarpoint Ventures III: USD 6,000,000 called of USD 10,000,000 committed, USD 7,250,000 after it, leaving USD 2,750,000 unfunded."
- **Heading on screen:** CALLED TO DATE AND UNFUNDED · EVERGREEN HOLDINGS · CEDARPOINT VENTURES III · USD
- **Source line on screen:** Source: daniel s team just handed me called to date
- **Same answer in the run report:** "Yes. The USD 1,250,000 call fits Cedarpoint Ventures III: USD 6,000,000 called of USD 10,000,000 committed, USD 7,250,000 after it, leaving USD 2,750,000 unfunded."
- **Screen timing:** Answered in 34 ms (from memory).
- **Check (numbers that must appear on screen):** 10,000,000, 6,000,000, 7,250,000, 2,750,000; all present: yes.
- **Receipt (Where this number comes from):** the figure page `http://127.0.0.1:8780/v3/knowledge/figures/fig-called-to-date-and-unfunded`. The figure is Called to date and unfunded (`fig-called-to-date-and-unfunded`): built from Called to date and unfunded; reads cash_movements, commitments, instruments, legal_entities; approved by Helen Foo; versions [1] on record. 

### Left for the next ones

- Figures this case built that later cases used: Net Worth (used again by uc-005-benefcheck, uc-016-schemadrift); Allocation Drift (used again by uc-016-schemadrift); Capital call notice, as read (used again by uc-005-benefcheck).
- Figures this case reused from earlier cases: fig-net-worth, fig-capital-call-notice-as-read.

### Screens

- Thread page at live: `docs/v3/top10/shots/uc-002-callrecord-thread-live.png`
- Consume answer, with "Show the figures" opened: `docs/v3/top10/shots/uc-002-callrecord-consume-check.png`
- One figure page (Knowledge > Figures): `docs/v3/top10/shots/uc-002-callrecord-figure.png`

## 3. Call payment feasibility  (`uc-004-callcheck`)

**Person:** Daniel Foo (cfo). **Thread:** `t-c493e74f3c`, created 07:55 UTC, live 07:57 UTC (2.1 min from first message to live). **Run:** `run-20261021-075724-4957`, next run monthly at 06:00. **Stage reached:** live.

**Time per stage (run report, seconds):** drafting 106, decision1 3, working 15, decision2 3, decision3 3. **Total:** 130 s = 2.2 min.

### Intent

- **What the person said:** "A Cedarpoint call is due on the 23rd. I want to know in one answer whether Holdings can pay it from its own cash after the 250,000 buffer, what is short if not, and how much SGD to convert. Show where each number comes from. Anything over 500,000 needs my name on it."
- **Harbor's one-line restatement (brief):** A Cedarpoint call is due on the 23rd. I want to know in one answer whether Holdings can pay it from its own cash after the 250,000 buffer, what is short if not, and how much SGD to convert. Anything over 500,000 needs my name on it.
- **Read by / decides / when:** Investments team, Operations team, Finance team; Approve payment of the call, Authorize SGD conversion above 500,000; By end of the business day the call notice is received
- **What it is built to show (use case definition):** Consume: cash after calls due, by entity, with the shortfall and the amount to convert.
- **Check question:** "Can Holdings pay the Cedarpoint call on the 23rd?"; numbers that must appear: 1,230,000, 1,600,000, 1,194,029.85, 1,250,000, 250,000, 270,000, 361,800.

### Decision 1: what Harbor drafted

North asked: "I don't have the call amount; could you tell me the amount of the Cedarpoint call? I have drafted the title, KPI Call payment feasibility, source Holdings cash balance, source Cedarpoint call notice and source FX rate to SGD; say yes to accept, or tell me what is wrong. I am filling the open parts with the usual practice now, marked as suggestions."

Signed by Daniel Foo at 2026-10-21T07:57:12+00:00.

| Figure (as drafted) | What it means | How it is worked out | Built from | Owner | How often |
|---|---|---|---|---|---|
| Call payment feasibility | Can Holdings meet the Cedarpoint call after reserving the 250,000 cash buffer; if not, the shortfall; and the SGD amount to convert to cover the shortfall. | If (Cash - 250,000) >= CallAmount then Yes else Shortfall = CallAmount - (Cash - 250,000); SGDConvert = Shortfall * FXRateSGD | Capital call payment status recipe (suggested) | Helen Foo | single event |
| Cash after calls due | For each entity and currency, the latest cash balance (as cash_by_entity counts it) less the open calls due in that currency less the buffer of the signed office rule cash_buffer (the buffer applies in the currency the rule names; in another currency, or with no signed rule, the buffer and the result are empty). Open = noticed or expected (even when past due), or recorded with a due date on or after the entity's latest cash date. Negative means the entity is short; the shortfall is that amount made positive. | For each entity and currency, the latest cash balance (as cash_by_entity counts it) less the open calls due in that currency less the buffer of the signed office rule cash_buffer (the buffer applies in the currency the rule names; in another currency, or with no signed rule, the buffer and the result are empty). Open = noticed or expected (even when past due), or recorded with a due date on or after the entity's latest cash date. Negative means the entity is short; the shortfall is that amount made positive. | Cash after calls due recipe (suggested) | Helen Foo | single event |
| FX needed to pay a call | For each entity short after calls due (cash_after_calls, with the signed buffer), the shortfall in the call currency times the planning rate of the FX series (the latest observation of the pair on or before the entity's latest cash date, SGD per 1 USD for the pair USD/SGD), rounded up to the next whole unit of the other currency. The rate and its date are shown, with the cash held in the other currency. With no signed buffer there is no row. | For each entity short after calls due (cash_after_calls, with the signed buffer), the shortfall in the call currency times the planning rate of the FX series (the latest observation of the pair on or before the entity's latest cash date, SGD per 1 USD for the pair USD/SGD), rounded up to the next whole unit of the other currency. The rate and its date are shown, with the cash held in the other currency. With no signed buffer there is no row. | FX needed to pay a call recipe (suggested) | Helen Foo | single event |

Process map Harbor proposed (today's way): 1. Receive call notice (Investments): Collect call amount, due date and currency from notice ; 2. Gather cash balance (Operations): Query daily cash balance from database ; 3. Fetch FX rate (Finance): Retrieve latest SGD conversion rate ; 4. Compute feasibility (Analytics): Apply formula to determine payment ability, shortfall and SGD amount ; 5. Produce answer (Analytics): Create one‑page summary with source citations ; 6. Send to requestor (Investments): Email result to Helen Foo and copy relevant teams.

Recipe bindings (figure to recipe, from the rules): Call payment feasibility -> call_payment_status (Its name or definition names the capital call payment status recipe.); Cash after calls due -> cash_after_calls (Your question asks for the cash after calls due and no figure of the brief is built from it.); FX needed to pay a call -> fx_required (Your question asks for the fx needed to pay a call and no figure of the brief is built from it.).

### Decision 2: files, kinds, readers, tables

- **Sources named in the brief:** Holdings cash balance; Cedarpoint call notice; FX rate to SGD.
- **Systems Span read:** Holdings cash balance; Cedarpoint call notice; FX rate to SGD.
- **Files this case dropped:** none.
- **Kind each file was recognised as:** the thread does not write a kind per file; the office folder has 1 files in its pack map. Emails and Word/markdown notes were read as context (not as a table); PDFs and sheets were read by the reader named below.
- **Readers that loaded them (skills run on this case):** `data.recognise-file`, `data.profile-file`, `map.map-file`, `data.read-pdf-fields`, `data.read-sop`.
- **Already in the office (reused from earlier cases):** 3 sources already in the office (from the workbench step: 1 files read, 0 mappings proposed, 3 sources already in the office).
- **Answers the person gave to Harbor questions:** No check this time.
- **Loaded:** "1 files loaded". Left out: cedarpoint_call_notice, fx_rate_to_sgd, holdings_cash_balance. Exceptions: none.
- **Tables loaded with row counts:** `cash_movements` 557 rows; `instruments` 59 rows; `legal_entities` 3 rows; `portfolios` 8 rows; `position_snapshots` 6,329 rows; `market_observations` 614 rows. These are the row counts in the office now, after all ten cases; the office did not keep a per-case count, so the figures here are not a snapshot at the time of the run.

### Decision 3: figures, recipes, gold tables, checks

| Figure | Version at live | Status | Gold table | Rows | Recipe (what Harbor used) | Formula in words | Tie-out | Reused from earlier |
|---|---|---|---|---|---|---|---|---|
| Call payment feasibility (`fig-call-payment-feasibility`) | v1 | verified | `gold_a_cedarpoint_call_is_due_on_th_call_payment_status` | 11 | `call_payment_status`: Capital call payment status | For each call (not cancelled, not superseded) with a due date, paid when a confirmed payment movement of the same fund, currency and amount (compared as positive numbers, A5) has the call's due date a... | ok: Every call with a due date has one row | no |
| Cash after calls due (`fig-cash-after-calls-due`) | v1 | verified | `gold_a_cedarpoint_call_is_due_on_th_cash_after_calls` | 6 | `cash_after_calls`: Cash after calls due | For each entity and currency, the latest cash balance (as cash_by_entity counts it) less the open calls due in that currency less the buffer of the signed office rule cash_buffer (the buffer applies i... | ok: The cash in the table equals the cash positions of the latest date for each entity and currency | no |
| FX needed to pay a call (`fig-fx-needed-to-pay-a-call`) | v1 | verified | `gold_a_cedarpoint_call_is_due_on_th_fx_required` | 1 | `fx_required`: FX needed to pay a call | For each entity short after calls due (cash_after_calls, with the signed buffer), the shortfall in the call currency times the planning rate of the FX series (the latest observation of the pair on or ... | ok: Every row's amount to convert equals its shortfall times its rate, rounded up to the next whole unit | no |

- **Checks at decision 3:** adds-up: "all 3 figures have a ready table; 3 of 3 figures have rows". Against the report: "no check, by the person's choice".
- **Second-model checks:** none in this case's window (the checks use the figure rules and the tie-outs above).

### Skills run

31 of 31 skill calls succeeded, from `skill_runs.jsonl` for this thread. Skills used: 20 skill-folder skills and 2 per-kind file readers (data.read-<kind>). Most used: `model.design-ready-table` x5, `check.adds-up` x3, `intent.define-figure` x2, `model.find-reusable` x2, `data.recognise-file` x2, `intent.restate-ask` x1, `intent.find-gaps` x1, `intent.fill-with-practice` x1.
- Workbench steps (the thread's own log): 1. North: Signed the intent (ok; signed and sent to Build) | 2. North: Handed over to build (ok; handed to the data engineer) | 3. Span: Read the systems (ok; 3 systems, 0 questions assumed) | 4. Span: Read the sample files (ok; 7 files given to Span as samples) | 5. Span: Drafted and approved the design pack (ok; design pack approved) | 6. Flow: Read the dropped files (ok; 1 files read, 0 mappings proposed, 3 sources already in the office) | 7. Span: Applied your answers (ok; 1 answers applied) | 8. Flow: Accepted the mappings and loaded (ok; 1 files loaded) | 9. Flow: Ran on a copy (ok; ran on a copy) | 10. Span: Made sure each figure has a filled ready table (ok; all 3 figures have a ready table; 3 of 3 figures have rows) | 11. Flow: Compared with the report (ok; no check, by the person's choice) | 12. Flow: Went live (ok; live on monthly at 06:00) | 13. Lumen: Built the starter board (ok; Lumen starter board accepted and published) | 14. Lumen: Wrote the morning note (ok; morning note written) | 15. Flow: Recorded the run on each figure (ok; run recorded on 3 figures).

**Model calls recorded for this case:** 4 (openai/gpt-oss-120b x4; tiers specialist x4); estimated cost USD 0.0018. Source: `model_costs.jsonl`, rows with this thread's intent id.

### Live answer and its receipt

- **Check question (asked in Consume, as Daniel Foo):** "Can Holdings pay the Cedarpoint call on the 23rd?"
- **Answer word for word (Consume screen):** "No. Evergreen Holdings is short USD 270,000 for the USD 1,250,000 of calls due 23 Oct 2026, after keeping the USD 250,000 buffer from cash of USD 1,230,000. Converting SGD 361,800 of its SGD 1,600,000 (worth USD 1,194,029.85) at 1.34 covers the USD 270,000 short."
- **Heading on screen:** CASH AFTER CALLS DUE · EVERGREEN HOLDINGS · USD
- **Source line on screen:** Source: a cedarpoint call is due on th call payment status, a cedarpoint call is due on th cash after calls, a cedarpoint call is due on th fx required
- **Same answer in the run report:** "No. Evergreen Holdings is short USD 270,000 for the USD 1,250,000 of calls due 23 Oct 2026, after keeping the USD 250,000 buffer from cash of USD 1,230,000. Converting SGD 361,800 of its SGD 1,600,000 (worth USD 1,194,029.85) at 1.34 covers the USD 270,000 short."
- **Screen timing:** Answered in 19 ms (from memory).
- **Check (numbers that must appear on screen):** 1,230,000, 1,600,000, 1,194,029.85, 1,250,000, 250,000, 270,000, 361,800; all present: yes.
- **Receipt (Where this number comes from):** the figure page `http://127.0.0.1:8780/v3/knowledge/figures/fig-cash-after-calls-due`. The figure is Cash after calls due (`fig-cash-after-calls-due`): built from Cash after calls due; reads bank_accounts, business_rules, cash_movements, instruments, legal_entities, portfolios, position_snapshots, rule_versions; approved by Daniel Foo; versions [1] on record. 

### Left for the next ones

- Figures this case built that later cases used: none.
- Figures this case reused from earlier cases: none.

### Screens

- Thread page at live: `docs/v3/top10/shots/uc-004-callcheck-thread-live.png`
- Consume answer, with "Show the figures" opened: `docs/v3/top10/shots/uc-004-callcheck-consume-check.png`
- One figure page (Knowledge > Figures): `docs/v3/top10/shots/uc-004-callcheck-figure.png`

## 4. The Cedarpoint call 7 notice says  (`uc-005-benefcheck`)

**Person:** Grace Ong (ops_lead). **Thread:** `t-a48cd41eb4`, created 07:57 UTC, live 08:09 UTC (11.6 min from first message to live). **Run:** `run-20261021-080654-c7ae`, next run daily at 06:00. **Stage reached:** live.

**Time per stage (run report, seconds):** drafting 261, decision1 3, working 432, decision2 3, question 3, decision3 3. **Total:** 705 s = 11.8 min.

### Intent

- **What the person said:** "The Cedarpoint call 7 notice says to wire to an account ending 4471 but we have always paid 2209. Check the notice against the standing instructions and the earlier calls, and hold the payment until I have called them back on the number we have on file."
- **Harbor's one-line restatement (brief):** The Cedarpoint call 7 notice says to wire to an account ending 4471 but we have always paid 2209.
- **Read by / decides / when:** Investment Committee, Operations team; Approve payment release, Confirm account number; not stated
- **What it is built to show (use case definition):** Consume: payee bank details on the notice against the account on file, payments on hold.
- **Check question:** "Cedarpoint now says to wire to an account ending 4471. Is that really them?"; numbers that must appear: 2209, 4471.

### Decision 1: what Harbor drafted

North asked: "I’ll note the call‑notice details to extract and compare to your standing instructions, and hold the payment until you confirm the account number. Who should sign off to release the payment once the number is verified? I have drafted source Call notice 7 and 1 open question; say yes to accept, or tell me what is wrong. I am filling the open parts with the usual practice now, marked as suggestions."

Signed by Grace Ong at 2026-10-21T08:02:11+00:00.

| Figure (as drafted) | What it means | How it is worked out | Built from | Owner | How often |
|---|---|---|---|---|---|
| Minimum six‑month funding headroom | Opening cash + approved inflows – known obligations – scenario‑only calls – proposed funding – reserve; take minimum across six months |  | No recipe yet: Span designs it (suggested) | Helen Foo | Monthly |
| Net worth | Total of all assets less liabilities |  | Net worth recipe (suggested) | Helen Foo | Monthly |
| Payee bank details changed | For each capital call notice, the account ending read from the notice against the payee account on file for the fund as it stood on the notice date (the latest payee row verified on or before it). Changed = the endings differ. The payment stays on hold while it is changed and no payee row for the notice's account records a call-back (verified_on on or after the notice date). Earlier payments to the fund show where the money went before. | For each capital call notice, the account ending read from the notice against the payee account on file for the fund as it stood on the notice date (the latest payee row verified on or before it). Changed = the endings differ. The payment stays on hold while it is changed and no payee row for the notice's account records a call-back (verified_on on or after the notice date). Earlier payments to the fund show where the money went before. | Payee bank details changed recipe (suggested) | Helen Foo | Monthly |
| Capital call payment status | For each call (not cancelled, not superseded) with a due date, paid when a confirmed payment movement of the same fund, currency and amount (compared as positive numbers, A5) has the call's due date as its value date. A call past its due date with no such payment is not paid; a due date after the latest movement date on file is not due. | For each call (not cancelled, not superseded) with a due date, paid when a confirmed payment movement of the same fund, currency and amount (compared as positive numbers, A5) has the call's due date as its value date. A call past its due date with no such payment is not paid; a due date after the latest movement date on file is not due. | Capital call payment status recipe (suggested) | Helen Foo | Monthly |
| Account set-up signatories against the signing policy | One row per current pending bank account. signatories = the signatory fields of its opening form, in the form's order. The policy needs at least min_signatories, one of whom holds the required_role (users.business_role, or the title of the latest payroll period). missing_signatory = the holder of the required role when not among the signatories. meets_signing_policy when both hold; approved when it meets the policy and the account is no longer pending. With no signed policy the checks are empty. | One row per current pending bank account. signatories = the signatory fields of its opening form, in the form's order. The policy needs at least min_signatories, one of whom holds the required_role (users.business_role, or the title of the latest payroll period). missing_signatory = the holder of the required role when not among the signatories. meets_signing_policy when both hold; approved when it meets the policy and the account is no longer pending. With no signed policy the checks are empty. | Account set-up signatories against the signing policy recipe (suggested) | Helen Foo | Monthly |
| Capital call notice, as read | For each capital call notice (documents of type capital_call_notice that no later document replaces; the same fund and call number received twice is listed once, with copies counting the documents), the fund, the investor, the call number, the amount and currency, the due date, the purpose split (new investments and management fee) and the last four characters of the wire account, from the notice's extracted fields (a reviewer's correction wins over the reading, text or number; a correction that is not a number leaves the figure empty). The page of the amount is kept for the receipt. | For each capital call notice (documents of type capital_call_notice that no later document replaces; the same fund and call number received twice is listed once, with copies counting the documents), the fund, the investor, the call number, the amount and currency, the due date, the purpose split (new investments and management fee) and the last four characters of the wire account, from the notice's extracted fields (a reviewer's correction wins over the reading, text or number; a correction that is not a number leaves the figure empty). The page of the amount is kept for the receipt. | Capital call notice, as read recipe (suggested) | Helen Foo | Monthly |

Process map Harbor proposed (today's way): 1. Receive call notice (Grace Ong): Collect the call‑notice document from mailbox ; 2. Extract notice fields (Helen Foo): Pull fund name, call number, amount, currency, due date and unfunded commitment from the notice ; 3. Verify account number (Helen Foo): Compare the account ending 4471 from notice with the standing instruction ending 2209 ; 4. Hold payment (Payments team): Place the payment on hold in the payment system ; 5. Approve payment release (APPROVER (to be confirmed)): Sign off that the account number is correct ; 6. Release payment (Payments team): Execute the wire transfer ; 7. Update ledger (Operations): Record the payment in the family ledger ; 8. Prepare pack (Operations): Aggregate positions, cash, private‑fund values, calculate KPIs and build PDF pack ; 9. Distribute pack (Operations): Send PDF pack to Investment Committee.

Recipe bindings (figure to recipe, from the rules): Minimum six‑month funding headroom -> none, Span designs it (No recipe of the pack computes it; Span designs it.); Net worth -> net_worth (Its name or definition names the net worth recipe.); Payee bank details changed -> bank_details_changed (Your question asks for the payee bank details changed and no figure of the brief is built from it.); Capital call payment status -> call_payment_status (Your question asks for the capital call payment status and no figure of the brief is built from it.); Account set-up signatories against the signing policy -> account_setup (Your question asks for the account set-up signatories against the signing policy and no figure of the brief is built from it.); Capital call notice, as read -> call_notice_fields (Your question asks for the capital call notice, as read and no figure of the brief is built from it.).

### Decision 2: files, kinds, readers, tables

- **Sources named in the brief:** Call notice 7.
- **Systems Span read:** Call notice 7.
- **Files this case dropped:** none.
- **Kind each file was recognised as:** the thread does not write a kind per file; the office folder has 0 files in its pack map. Emails and Word/markdown notes were read as context (not as a table); PDFs and sheets were read by the reader named below.
- **Readers that loaded them (skills run on this case):** `data.recognise-file`, `data.profile-file`, `map.map-file`, `data.read-pdf-fields`.
- **Already in the office (reused from earlier cases):** 1 sources already in the office (from the workbench step: 0 files read, 0 mappings proposed, 1 sources already in the office).
- **Answers the person gave to Harbor questions:** none.
- **Loaded:** "0 files loaded". Left out: call_notice_7. Exceptions: none.
- **Tables loaded with row counts:** `instruments` 59 rows; `legal_entities` 3 rows; `portfolios` 8 rows; `position_snapshots` 6,329 rows; `cash_movements` 557 rows; `documents` 382 rows. These are the row counts in the office now, after all ten cases; the office did not keep a per-case count, so the figures here are not a snapshot at the time of the run.

### Decision 3: figures, recipes, gold tables, checks

| Figure | Version at live | Status | Gold table | Rows | Recipe (what Harbor used) | Formula in words | Tie-out | Reused from earlier |
|---|---|---|---|---|---|---|---|---|
| Minimum six‑month funding headroom (`fig-minimum-six-month-funding-headroom`) | v1 | held | not built: no table of the company model holds its records, so it is not in a gold table yet. Ask Span for a model change if a new fact must be kept. |  | none: Span designed the table |  | n/a | no |
| Net worth (`fig-net-worth`) | v3 | verified | `gold_the_cedarpoint_call_7_notice_s_net_worth_by_portfolio` | 1008 | `net_worth`: Net worth | Net worth = the sum of the market values of the position snapshots of each date, one value for each portfolio, instrument, date and currency (a snapshot that a later one supersedes is out; a carried-f... | ok: Net worth equals the sum of the position snapshots for the same dates, cash counted once | yes |
| Payee bank details changed (`fig-payee-bank-details-changed`) | v1 | verified | `gold_the_cedarpoint_call_7_notice_s_bank_details_changed` | 11 | `bank_details_changed`: Payee bank details changed | For each capital call notice, the account ending read from the notice against the payee account on file for the fund as it stood on the notice date (the latest payee row verified on or before it). Cha... | ok: Every capital call notice with an account is compared once | no |
| Capital call payment status (`fig-capital-call-payment-status`) | v2 | verified | `gold_the_cedarpoint_call_7_notice_s_call_payment_status` | 11 | `call_payment_status`: Capital call payment status | For each call (not cancelled, not superseded) with a due date, paid when a confirmed payment movement of the same fund, currency and amount (compared as positive numbers, A5) has the call's due date a... | ok: Every call with a due date has one row | yes |
| Account set-up signatories against the signing policy (`fig-account-set-up-signatories-against-the-signing-policy`) | v1 | verified | `gold_the_cedarpoint_call_7_notice_s_account_setup` | 1 | `account_setup`: Account set-up signatories against the signing policy | One row per current pending bank account. signatories = the signatory fields of its opening form, in the form's order. The policy needs at least min_signatories, one of whom holds the required_role (u... | ok: Accounts equal the pending bank accounts on file | no |
| Capital call notice, as read (`fig-capital-call-notice-as-read`) | v3 | verified | `gold_the_cedarpoint_call_7_notice_s_call_notice_fields` | 11 | `call_notice_fields`: Capital call notice, as read | For each capital call notice (documents of type capital_call_notice that no later document replaces; the same fund and call number received twice is listed once, with copies counting the documents), t... | ok: The purpose split adds up to the amount called | yes |

- **Checks at decision 3:** adds-up: "0 ready tables added; no table for Minimum six‑month funding headroom; 5 of 6 figures have rows". Against the report: "no report to compare with".
- **Notes on figures that were not built:** Minimum six‑month funding headroom: no table of the company model holds its records, so it is not in a gold table yet. Ask Span for a model change if a new fact must be kept..
- **Second-model checks (worker and checker from different families, logged in `judge/log.json`), in this case's window:**
  - 08:02:08 UTC, recipe: did not agree (a person is asked). Question: (text not logged in judge/log.json)

### Skills run

33 of 34 skill calls succeeded, from `skill_runs.jsonl` for this thread. Skills used: 20 skill-folder skills and 1 per-kind file readers (data.read-<kind>). Most used: `model.design-ready-table` x8, `check.adds-up` x3, `intent.define-figure` x2, `model.find-reusable` x2, `data.recognise-file` x2, `run.on-copy` x2, `intent.restate-ask` x1, `intent.find-gaps` x1.
- Failed calls: `run.on-copy`: The run on the copy stopped at the step that builds This project is already running. Please wait for it to finish.: This project is already running. Please wait for it to finish.. Send the design back....
- Workbench steps (the thread's own log): 1. North: Signed the intent (ok; signed and sent to Build) | 2. North: Handed over to build (ok; handed to the data engineer) | 3. Span: Read the systems (ok; 1 systems, 0 questions assumed) | 4. Span: Read the sample files (ok; 2 files given to Span as samples) | 5. Span: Drafted and approved the design pack (ok; design pack approved) | 6. Flow: Read the dropped files (ok; 0 files read, 0 mappings proposed, 1 sources already in the office) | 7. Span: Applied your answers (ok; 0 answers applied) | 8. Flow: Accepted the mappings and loaded (ok; 0 files loaded) | 9. Flow: Ran on a copy (failed; The run on the copy stopped at the step that builds This project is already running. Please wait for it to finish.: This project is already running. Please wait for it to finish.. Send the design back...) | 10. Flow: Ran on a copy (ok; ran on a copy) | 11. Span: Made sure each figure has a filled ready table (ok; 0 ready tables added; no table for Minimum six‑month funding headroom; 5 of 6 figures have rows) | 12. Flow: Compared with the report (ok; no report to compare with) | 13. Flow: Went live (ok; live on daily at 06:00) | 14. Lumen: Built the starter board (ok; Lumen starter board accepted and published) | 15. Lumen: Wrote the morning note (ok; morning note written) | 16. Flow: Recorded the run on each figure (ok; run recorded on 5 figures).

**Model calls recorded for this case:** 5 (openai/gpt-oss-120b x5; tiers specialist x5); estimated cost USD 0.0032. Source: `model_costs.jsonl`, rows with this thread's intent id.

### Live answer and its receipt

- **Check question (asked in Consume, as Grace Ong):** "Cedarpoint now says to wire to an account ending 4471. Is that really them?"
- **Answer word for word (Consume screen):** "Not confirmed: Cedarpoint Ventures III call 7 asks for account 4471, but earlier calls went to 2209; it is held until a call-back on the number on file."
- **Heading on screen:** CAPITAL CALL NOTICE, AS READ · CEDARPOINT VENTURES III · EVERGREEN HOLDINGS · USD · 4471
- **Source line on screen:** Source: the cedarpoint call 7 notice s account setup, the cedarpoint call 7 notice s bank details changed, the cedarpoint call 7 notice s call notice fields, the cedarpoint call 7 notice s net worth by portfolio
- **Same answer in the run report:** "Not confirmed: Cedarpoint Ventures III call 7 asks for account 4471, but earlier calls went to 2209; it is held until a call-back on the number on file."
- **Screen timing:** not in the captured text.
- **Check (numbers that must appear on screen):** 2209, 4471; all present: yes.
- **Receipt (Where this number comes from):** the figure page `http://127.0.0.1:8780/v3/knowledge/figures/fig-capital-call-notice-as-read`. The figure is Capital call notice, as read (`fig-capital-call-notice-as-read`): built from Capital call notice, as read; reads documents, extracted_fields, instruments; approved by Grace Ong; versions [1, 2, 3] on record. 

### Left for the next ones

- Figures this case built that later cases used: Net worth (used again by uc-016-schemadrift); Account set-up signatories against the signing policy (used again by uc2-recon-break-desk).
- Figures this case reused from earlier cases: fig-net-worth, fig-capital-call-payment-status, fig-capital-call-notice-as-read.

### Screens

- Thread page at live: `docs/v3/top10/shots/uc-005-benefcheck-thread-live.png`
- Consume answer, with "Show the figures" opened: `docs/v3/top10/shots/uc-005-benefcheck-consume-check.png`
- One figure page (Knowledge > Figures): `docs/v3/top10/shots/uc-005-benefcheck-figure.png`

## 5. Payment run KPIs  (`uc-008-payrun`)

**Person:** Grace Ong (ops_lead). **Thread:** `t-f884a3071c`, created 08:09 UTC, live 08:17 UTC (7.7 min from first message to live). **Run:** `run-20261021-081725-9e29`, next run daily at 06:00. **Stage reached:** live.

**Time per stage (run report, seconds):** drafting 437, decision1 6, working 20, decision2 3, decision3 3. **Total:** 469 s = 7.8 min.

### Intent

- **What the person said:** "Every Thursday I prepare the payment run. List what is due in the next ten days: which payments are ready, which wait for Daniel's approval, and which I must hold because the invoice is above the fee schedule. Give me the total by currency."
- **Harbor's one-line restatement (brief):** Every Thursday I prepare the payment run.
- **Read by / decides / when:** Investment Committee; Approve payments listed in the pack; not stated
- **What it is built to show (use case definition):** Consume: payment batch by approval state, with the total by currency.
- **Check question:** "Which payments to release"; numbers that must appear: 5,400, 16,234.5, 6,180, 1,030, 1,250,000.

### Decision 1: what Harbor drafted

North asked: "I don't have the payment details; the finance operations team or the treasury system owner can provide them. Which system or file contains the upcoming payment data you need? I am filling the open parts with the usual practice now, marked as suggestions."

Signed by Grace Ong at 2026-10-21T08:17:12+00:00.

| Figure (as drafted) | What it means | How it is worked out | Built from | Owner | How often |
|---|---|---|---|---|---|
| Ready payments count | Number of payments that meet all criteria and can be processed immediately. | Count of payment rows where status = 'ready' | No recipe yet: Span designs it (suggested) | Finance Operations manager | weekly |
| Pending approvals count | Number of payments awaiting approval from the Investment Committee (Daniel's). | Count of payment rows where status = 'pending approval' | No recipe yet: Span designs it (suggested) | Finance Operations manager | weekly |
| Held payments count | Number of payments held because the invoice exceeds the fee‑schedule limits. | Count of payment rows where status = 'held' | No recipe yet: Span designs it (suggested) | Finance Operations manager | weekly |
| Total amount by currency | Sum of payment amounts for each currency, broken down by status. | Sum(amount) grouped by currency and status | No recipe yet: Span designs it (suggested) | Finance Operations manager | weekly |
| Payment batch by approval state | The payments still to be released (cash movements of type payment, status expected), each in one state. Hold when an open approval of type payment_hold names it (its rationale is the reason), or when the office has signed the rule invoice_above_fee_schedule (parameters action hold, tolerance_amount) and the payment's invoice (the invoice document read from the same source record as the payment) bills more than its fee schedule allows by more than the tolerance, the fee variance worked out as in invoice_variance (billed less fee base times the schedule rate over the billing periods, from the schedule in force on the invoice date; an invoice that cannot be checked is not held by it); with no such rule signed no payment is held for its fee; waiting for approval when an approval requested for it is not yet approved; hold on an unverified changed account when the payment goes to an account that replaced an earlier payee account and has no call-back (verified_on); otherwise ready. release_blocked is true while any of these stands, and blocked_by lists them all. The run window (days from the latest movement date) is the signed rule payment_run_window_days; with no signed rule in_window is empty and every expected payment is listed. Totals are by currency, never across currencies. | The payments still to be released (cash movements of type payment, status expected), each in one state. Hold when an open approval of type payment_hold names it (its rationale is the reason), or when the office has signed the rule invoice_above_fee_schedule (parameters action hold, tolerance_amount) and the payment's invoice (the invoice document read from the same source record as the payment) bills more than its fee schedule allows by more than the tolerance, the fee variance worked out as in invoice_variance (billed less fee base times the schedule rate over the billing periods, from the schedule in force on the invoice date; an invoice that cannot be checked is not held by it); with no such rule signed no payment is held for its fee; waiting for approval when an approval requested for it is not yet approved; hold on an unverified changed account when the payment goes to an account that replaced an earlier payee account and has no call-back (verified_on); otherwise ready. release_blocked is true while any of these stands, and blocked_by lists them all. The run window (days from the latest movement date) is the signed rule payment_run_window_days; with no signed rule in_window is empty and every expected payment is listed. Totals are by currency, never across currencies. | Payment batch by approval state recipe (suggested) | Finance Operations manager | weekly |
| Payments over their approval limit | One row per current expense of the ledger, in USD at the fixing of its day (or the latest before it), rounded to the cent. The limit is the signed approver_limit_ rule named after the approver (the name in lower case, words joined by _), in its currency. over_limit when the USD amount is above it. An approver with no signed limit has an empty limit and is not judged. | One row per current expense of the ledger, in USD at the fixing of its day (or the latest before it), rounded to the cent. The limit is the signed approver_limit_ rule named after the approver (the name in lower case, words joined by _), in its currency. over_limit when the USD amount is above it. An approver with no signed limit has an empty limit and is not judged. | Payments over their approval limit recipe (suggested) | Finance Operations manager | weekly |

Recipe bindings (figure to recipe, from the rules): Ready payments count -> none, Span designs it (No recipe of the pack computes it; Span designs it.); Pending approvals count -> none, Span designs it (No recipe of the pack computes it; Span designs it.); Held payments count -> none, Span designs it (No recipe of the pack computes it; Span designs it.); Total amount by currency -> none, Span designs it (No recipe of the pack computes it; Span designs it.); Payment batch by approval state -> payment_batch (Your question asks for the payment batch by approval state and no figure of the brief is built from it.); Payments over their approval limit -> approval_exceptions (Your question asks for the payments over their approval limit and no figure of the brief is built from it.).

### Decision 2: files, kinds, readers, tables

- **Sources named in the brief:** .
- **Systems Span read:** .
- **Files this case dropped:** none.
- **Kind each file was recognised as:** the thread does not write a kind per file; the office folder has 0 files in its pack map. Emails and Word/markdown notes were read as context (not as a table); PDFs and sheets were read by the reader named below.
- **Readers that loaded them (skills run on this case):** `data.recognise-file`, `data.profile-file`, `map.map-file`, `data.read-pdf-fields`.
- **Already in the office (reused from earlier cases):** 4 sources already in the office (from the workbench step: 0 files read, 0 mappings proposed, 4 sources already in the office).
- **Answers the person gave to Harbor questions:** No check this time.
- **Loaded:** "0 files loaded". Left out: none. Exceptions: none.
- **Tables loaded with row counts:** `market_observations` 614 rows; `cash_movements` 557 rows; `documents` 382 rows. These are the row counts in the office now, after all ten cases; the office did not keep a per-case count, so the figures here are not a snapshot at the time of the run.

### Decision 3: figures, recipes, gold tables, checks

| Figure | Version at live | Status | Gold table | Rows | Recipe (what Harbor used) | Formula in words | Tie-out | Reused from earlier |
|---|---|---|---|---|---|---|---|---|
| Ready payments count (`fig-ready-payments-count`) | v1 | verified | `gold_every_thursday_i_prepare_the_p_approval_exceptions` | 151 | none: Span designed the table |  | n/a | no |
| Pending approvals count (`fig-pending-approvals-count`) | v1 | verified | `gold_every_thursday_i_prepare_the_p_approval_exceptions` | 151 | none: Span designed the table |  | n/a | no |
| Held payments count (`fig-held-payments-count`) | v1 | verified | `gold_every_thursday_i_prepare_the_p_approval_exceptions` | 151 | none: Span designed the table |  | n/a | no |
| Total amount by currency (`fig-total-amount-by-currency`) | v1 | verified | `gold_every_thursday_i_prepare_the_p_approval_exceptions` | 151 | none: Span designed the table |  | n/a | no |
| Payment batch by approval state (`fig-payment-batch-by-approval-state`) | v1 | verified | `gold_every_thursday_i_prepare_the_p_payment_batch` | 4 | `payment_batch`: Payment batch by approval state | The payments still to be released (cash movements of type payment, status expected), each in one state. Hold when an open approval of type payment_hold names it (its rationale is the reason), or when ... | ok: Every expected payment is in the batch once | no |
| Payments over their approval limit (`fig-payments-over-their-approval-limit`) | v1 | verified | `gold_every_thursday_i_prepare_the_p_approval_exceptions` | 151 | `approval_exceptions`: Payments over their approval limit | One row per current expense of the ledger, in USD at the fixing of its day (or the latest before it), rounded to the cent. The limit is the signed approver_limit_ rule named after the approver (the na... | ok: Payments equal the current lines of the expense ledger | no |

- **Checks at decision 3:** adds-up: "all 6 figures have a ready table; 6 of 6 figures have rows". Against the report: "no check, by the person's choice".
- **Second-model checks (worker and checker from different families, logged in `judge/log.json`), in this case's window:**
  - 08:15:34 UTC, recipe: did not agree (a person is asked). Question: (text not logged in judge/log.json)
  - 08:15:57 UTC, recipe: agreed; answer: none. Question: Which recipe computes the figure 'Pending approvals count', defined as: Number of payments awaiting approval from the Investment Committee (Daniel's). (formula: Count of payment rows where status = 'pending approval')? Harbor took: none. qwen/qwen3.7-flash: Th...
  - 08:16:32 UTC, recipe: agreed; answer: none. Question: Which recipe computes the figure 'Held payments count', defined as: Number of payments held because the invoice exceeds the fee‑schedule limits. (formula: Count of payment rows where status = 'held')? Harbor took: none. qwen/qwen3.7-flash: The figure is a simp...
  - 08:17:11 UTC, recipe: did not agree (a person is asked). Question: (text not logged in judge/log.json)

### Skills run

31 of 31 skill calls succeeded, from `skill_runs.jsonl` for this thread. Skills used: 20 skill-folder skills and 1 per-kind file readers (data.read-<kind>). Most used: `model.design-ready-table` x3, `check.adds-up` x3, `intent.restate-ask` x2, `intent.find-gaps` x2, `intent.fill-with-practice` x2, `intent.define-figure` x2, `model.find-reusable` x2, `data.recognise-file` x2.
- Workbench steps (the thread's own log): 1. North: Signed the intent (ok; signed and sent to Build) | 2. North: Handed over to build (ok; handed to the data engineer) | 3. Span: Read the systems (ok; 0 systems, 0 questions assumed) | 4. Span: Read the sample files (ok; 6 files given to Span as samples) | 5. Span: Drafted and approved the design pack (ok; design pack approved) | 6. Flow: Read the dropped files (ok; 0 files read, 0 mappings proposed, 4 sources already in the office) | 7. Span: Applied your answers (ok; 1 answers applied) | 8. Flow: Accepted the mappings and loaded (ok; 0 files loaded) | 9. Flow: Ran on a copy (ok; ran on a copy) | 10. Span: Made sure each figure has a filled ready table (ok; all 6 figures have a ready table; 6 of 6 figures have rows) | 11. Flow: Compared with the report (ok; no check, by the person's choice) | 12. Flow: Went live (ok; live on daily at 06:00) | 13. Lumen: Built the starter board (ok; Lumen starter board accepted and published) | 14. Lumen: Wrote the morning note (ok; morning note written) | 15. Flow: Recorded the run on each figure (ok; run recorded on 6 figures).

**Model calls recorded for this case:** 11 (openai/gpt-oss-120b x11; tiers specialist x7, manager x4); estimated cost USD 0.0052. Source: `model_costs.jsonl`, rows with this thread's intent id.

### Live answer and its receipt

- **Check question (asked in Consume, as Grace Ong):** "Which payments to release"
- **Answer word for word (Consume screen):** "Release Summit Tax Advisory SGD 5,400; Harbourline Fund Services USD 16,234.50. Hold Anchorage Custody USD 6,180, USD 1,030 above the fee schedule. Hold Cedarpoint Ventures III USD 1,250,000: approval not yet given; account changed, no call-back."
- **Heading on screen:** PAYMENT BATCH BY APPROVAL STATE · SUMMIT TAX ADVISORY · SGD · READY · NOT NEEDED · 4432
- **Source line on screen:** Source: every thursday i prepare the p payment batch
- **Same answer in the run report:** "Release Summit Tax Advisory SGD 5,400; Harbourline Fund Services USD 16,234.50. Hold Anchorage Custody USD 6,180, USD 1,030 above the fee schedule. Hold Cedarpoint Ventures III USD 1,250,000: approval not yet given; account changed, no call-back."
- **Screen timing:** Answered in 19 ms (from memory).
- **Check (numbers that must appear on screen):** 5,400, 16,234.5, 6,180, 1,030, 1,250,000; all present: yes.
- **Receipt (Where this number comes from):** the figure page `http://127.0.0.1:8780/v3/knowledge/figures/fig-payment-batch-by-approval-state`. The figure is Payment batch by approval state (`fig-payment-batch-by-approval-state`): built from Payment batch by approval state; reads approvals, bank_accounts, business_rules, cash_movements, documents, extracted_fields, rule_versions, source_records, users; approved by Grace Ong; versions [1] on record. 

### Left for the next ones

- Figures this case built that later cases used: Payments over their approval limit (used again by uc5-limits).
- Figures this case reused from earlier cases: none.

### Screens

- Thread page at live: `docs/v3/top10/shots/uc-008-payrun-thread-live.png`
- Consume answer, with "Show the figures" opened: `docs/v3/top10/shots/uc-008-payrun-consume-check.png`
- One figure page (Knowledge > Figures): `docs/v3/top10/shots/uc-008-payrun-figure.png`

## 6. Monthly pack  (`uc-016-schemadrift`)

**Person:** Anita Rao (head_of_data). **Thread:** `t-5a5eba7a9a`, created 08:17 UTC, live 08:24 UTC (6.5 min from first message to live). **Run:** `run-20261021-082416-c89f`, next run daily at 06:00. **Stage reached:** live.

**Time per stage (run report, seconds):** drafting 347, decision1 6, working 40, decision2 3, decision3 3. **Total:** 399 s = 6.7 min.

### Intent

- **What the person said:** "The administrator renamed a column in their June file. Show me which column changed, what it was called before and what it is called now, how many earlier loads used the old name, and whether the new mapping is safe to accept. Hold the load until I decide."
- **Harbor's one-line restatement (brief):** The administrator renamed a column in their June file. Hold the load until I decide.
- **Read by / decides / when:** Investment Committee; Approve asset allocation and risk parameters; not stated
- **What it is built to show (use case definition):** Action: old and new columns lined up, mapping proposed, load held until accepted.
- **Check question:** "The administrator renamed a column. What breaks, and is the new mapping safe?"; numbers that must appear: Market Value, Valuation Amount (USD).

### Decision 1: what Harbor drafted

North asked: "I don’t have the details of the renamed column or its history yet. Could you tell me which column was changed, the old and new names, and which source file it concerns? I have drafted 1 open question; say yes to accept, or tell me what is wrong. I am filling the open parts with the usual practice now, marked as suggestions." | "I’ve drafted a typical three‑lane process for the monthly pack – Operations collect the source files, Data transforms and calculates the KPIs, and the Investment Committee reviews the pack. The steps, owners, systems, manual flags, controls and hand‑overs are outlined below. Do you confirm these lanes and steps, or is there any additional hand‑over or control you need to add? I have drafted 6 process steps and 5 hand-overs; say yes to accept, or tell me what is wrong."

Signed by Anita Rao at 2026-10-21T08:23:50+00:00.

| Figure (as drafted) | What it means | How it is worked out | Built from | Owner | How often |
|---|---|---|---|---|---|
| Net worth | All entities total market value, including private funds. |  | Net worth recipe (suggested) | Head of Data | monthly |
| Time‑weighted return net of fees | Chained monthly return net of fees, compared to blended benchmark. |  | Time weighted return and active return recipe (suggested) | Head of Data | monthly |
| Allocation drift | Difference between actual allocation and policy ranges. |  | Drift from the policy band and target recipe (suggested) | Head of Data | monthly |
| Single‑issuer concentration | Aggregate direct issuer exposure divided by total included asset value. |  | Single-issuer concentration recipe (suggested) | Head of Data | monthly |
| Columns added, renamed or dropped | For each sheet, the columns of the latest proposed mapping (the one Harbor drew up for the file that just arrived) set against the latest approved mapping. A target field with a different source column is renamed; one only in the proposal is added; one only in the approved mapping is dropped. batches_on_old_name counts the batches already loaded under the approved mapping of the same source system and sheet. | For each sheet, the columns of the latest proposed mapping (the one Harbor drew up for the file that just arrived) set against the latest approved mapping. A target field with a different source column is renamed; one only in the proposal is added; one only in the approved mapping is dropped. batches_on_old_name counts the batches already loaded under the approved mapping of the same source system and sheet. | Columns added, renamed or dropped recipe (suggested) | Head of Data | monthly |
| New feed columns mapped and in doubt | For each mapping whose columns carry a confidence mark (a profiled new feed) and each of its columns: the target and the confidence (high, medium or doubt). Per mapping: columns, mapped_with_confidence (high), share_mapped_pct (high over columns, whole percent), rows_in_sample (from the batch that profiled the file) and safe_to_go_live = 1 only when the mapping is approved and no column is in doubt. | For each mapping whose columns carry a confidence mark (a profiled new feed) and each of its columns: the target and the confidence (high, medium or doubt). Per mapping: columns, mapped_with_confidence (high), share_mapped_pct (high over columns, whole percent), rows_in_sample (from the batch that profiled the file) and safe_to_go_live = 1 only when the mapping is approved and no column is in doubt. | New feed columns mapped and in doubt recipe (suggested) | Head of Data | monthly |
| Change since the issued report | For each valuation that supersedes another (the link on the valuation), the original value is the valuation it replaces, the amended value is the replacing one, and the change is amended less original. Only the latest amendment of a chain counts. | For each valuation that supersedes another (the link on the valuation), the original value is the valuation it replaces, the amended value is the replacing one, and the change is amended less original. Only the latest amendment of a chain counts. | Change since the issued report recipe (suggested) | Head of Data | monthly |

Process map Harbor proposed (today's way): 1. Collect source files (Anita Rao): download custodian statements, bank balances and private‑fund portal data, and any manual adjustments ; 2. Reconcile positions and cash (Anita Rao): reconcile positions and cash to the family ledger, clear or explain breaks, fix missing prices ; 3. Value private funds (Head of Data): apply latest NAV from the private‑fund portal, add calls and subtract distributions ; 4. Calculate KPIs (Head of Data): compute Net worth, time‑weighted return net of fees, allocation drift and single‑issuer concentration ; 5. Assemble monthly pack (Head of Data): create one‑page pack with KPI cards and the column‑change table ; 6. Review by Investment Committee (Investment Committee): review the pack and approve asset allocation and risk parameters.

Recipe bindings (figure to recipe, from the rules): Net worth -> net_worth (Its name or definition names the net worth recipe.); Time‑weighted return net of fees -> time_weighted_return (Its name or definition names the time weighted return and active return recipe.); Allocation drift -> drift_vs_target (Its name or definition names the drift from the policy band and target recipe.); Single‑issuer concentration -> concentration (Its name or definition names the single-issuer concentration recipe.); Columns added, renamed or dropped -> columns_changed (Your question asks for the columns added, renamed or dropped and no figure of the brief is built from it.); New feed columns mapped and in doubt -> feed_mapping (Your question asks for the new feed columns mapped and in doubt and no figure of the brief is built from it.); Change since the issued report -> change_since_report (Your question asks for the change since the issued report and no figure of the brief is built from it.).

### Decision 2: files, kinds, readers, tables

- **Sources named in the brief:** Custodian statements; Bank balances; Private fund portal; Manual adjustments.
- **Systems Span read:** Custodian statements; Bank balances; Private fund portal; Manual adjustments.
- **Files this case dropped:** none.
- **Kind each file was recognised as:** the thread does not write a kind per file; the office folder has 0 files in its pack map. Emails and Word/markdown notes were read as context (not as a table); PDFs and sheets were read by the reader named below.
- **Readers that loaded them (skills run on this case):** `data.recognise-file`, `data.profile-file`, `map.map-file`, `data.read-pdf-fields`.
- **Already in the office (reused from earlier cases):** 3 sources already in the office (from the workbench step: 0 files read, 0 mappings proposed, 3 sources already in the office).
- **Answers the person gave to Harbor questions:** No check this time.
- **Loaded:** "0 files loaded". Left out: bank_balances, custodian_statements, manual_adjustments, private_fund_portal. Exceptions: none.
- **Tables loaded with row counts:** `instruments` 59 rows; `legal_entities` 3 rows; `portfolios` 8 rows; `position_snapshots` 6,329 rows; `market_observations` 614 rows; `transactions` 75 rows; `valuation_observations` 59 rows. These are the row counts in the office now, after all ten cases; the office did not keep a per-case count, so the figures here are not a snapshot at the time of the run.

### Decision 3: figures, recipes, gold tables, checks

| Figure | Version at live | Status | Gold table | Rows | Recipe (what Harbor used) | Formula in words | Tie-out | Reused from earlier |
|---|---|---|---|---|---|---|---|---|
| Net worth (`fig-net-worth`) | v4 | verified | `gold_the_administrator_renamed_a_co_net_worth_by_portfolio` | 1008 | `net_worth`: Net worth | Net worth = the sum of the market values of the position snapshots of each date, one value for each portfolio, instrument, date and currency (a snapshot that a later one supersedes is out; a carried-f... | ok: Net worth equals the sum of the position snapshots for the same dates, cash counted once | yes |
| Time‑weighted return net of fees (`fig-time-weighted-return-net-of-fees`) | v2 | verified | `gold_the_administrator_renamed_a_co_time_weighted_return` | 83 | `time_weighted_return`: Time weighted return and active return | Monthly return in percent (modified Dietz; a month is one whose end is a month end, a month still open is left out) = (end value - start value - net flow) / (start value + 0.5 x net flow) x 100, where... | ok: The month-end values used are the position snapshots of the same dates | yes |
| Allocation drift (`fig-allocation-drift`) | v2 | verified | `gold_the_administrator_renamed_a_co_drift_vs_target` | 3 | `drift_vs_target`: Drift from the policy band and target | For the the latest month-end position date (a month end is the last day of the month or its last business day; a date in a month still open is not one) of each portfolio that has signed policy limits ... | ok: The portfolio totals used equal the position snapshots of the same portfolios and dates, and every share is between 0 and 100 | yes |
| Single‑issuer concentration (`fig-single-issuer-concentration`) | v1 | verified | `gold_the_administrator_renamed_a_co_concentration` | 3755 | `concentration`: Single-issuer concentration | Concentration in percent = the market value held in one issuer (the instrument's name) in a portfolio divided by the portfolio's total market value held, for the same date and currency, times 100. Cas... | ok: The exposures add up to the total of the position snapshots for the same dates, cash counted once | no |
| Columns added, renamed or dropped (`fig-columns-added-renamed-or-dropped`) | v1 | verified | `gold_the_administrator_renamed_a_co_columns_changed` | 1 | `columns_changed`: Columns added, renamed or dropped | For each sheet, the columns of the latest proposed mapping (the one Harbor drew up for the file that just arrived) set against the latest approved mapping. A target field with a different source colum... | ok: Changed columns equal the new names not in the approved mapping plus the dropped targets | no |
| New feed columns mapped and in doubt (`fig-new-feed-columns-mapped-and-in-doubt`) | v1 | verified | `gold_the_administrator_renamed_a_co_feed_mapping` | 10 | `feed_mapping`: New feed columns mapped and in doubt | For each mapping whose columns carry a confidence mark (a profiled new feed) and each of its columns: the target and the confidence (high, medium or doubt). Per mapping: columns, mapped_with_confidenc... | ok: Every column of a profiled mapping is in the figure once | no |
| Change since the issued report (`fig-change-since-the-issued-report`) | v1 | verified | `gold_the_administrator_renamed_a_co_change_since_report` | 3 | `change_since_report`: Change since the issued report | For each valuation that supersedes another (the link on the valuation), the original value is the valuation it replaces, the amended value is the replacing one, and the change is amended less original... | ok: Every amended valuation that is not itself replaced appears once | no |

- **Checks at decision 3:** adds-up: "all 7 figures have a ready table; 7 of 7 figures have rows". Against the report: "no check, by the person's choice".
- **Second-model checks:** none in this case's window (the checks use the figure rules and the tie-outs above).

### Skills run

38 of 38 skill calls succeeded, from `skill_runs.jsonl` for this thread. Skills used: 20 skill-folder skills and 1 per-kind file readers (data.read-<kind>). Most used: `model.design-ready-table` x9, `intent.define-figure` x3, `check.adds-up` x3, `intent.restate-ask` x2, `intent.find-gaps` x2, `intent.fill-with-practice` x2, `model.find-reusable` x2, `data.recognise-file` x2.
- Workbench steps (the thread's own log): 1. North: Signed the intent (ok; signed and sent to Build) | 2. North: Handed over to build (ok; handed to the data engineer) | 3. Span: Read the systems (ok; 4 systems, 0 questions assumed) | 4. Span: Read the sample files (ok; 6 files given to Span as samples) | 5. Span: Drafted and approved the design pack (ok; design pack approved) | 6. Flow: Read the dropped files (ok; 0 files read, 0 mappings proposed, 3 sources already in the office) | 7. Span: Applied your answers (ok; 1 answers applied) | 8. Flow: Accepted the mappings and loaded (ok; 0 files loaded) | 9. Flow: Ran on a copy (ok; ran on a copy) | 10. Span: Made sure each figure has a filled ready table (ok; all 7 figures have a ready table; 7 of 7 figures have rows) | 11. Flow: Compared with the report (ok; no check, by the person's choice) | 12. Flow: Went live (ok; live on daily at 06:00) | 13. Lumen: Built the starter board (ok; Lumen starter board accepted and published) | 14. Lumen: Wrote the morning note (ok; morning note written) | 15. Flow: Recorded the run on each figure (ok; run recorded on 7 figures).

**Model calls recorded for this case:** 11 (openai/gpt-oss-120b x11; tiers specialist x8, manager x3); estimated cost USD 0.0066. Source: `model_costs.jsonl`, rows with this thread's intent id.

### Live answer and its receipt

- **Check question (asked in Consume, as Anita Rao):** "The administrator renamed a column. What breaks, and is the new mapping safe?"
- **Answer word for word (Consume screen):** "Columns added, renamed or dropped for Positions · source market value · Market Value · Valuation Amount (USD) · renamed: 1."
- **Heading on screen:** COLUMNS ADDED, RENAMED OR DROPPED · POSITIONS · POSITION_SNAPSHOTS.SOURCE_MARKET_VALUE · MARKET VALUE · VALUATION AMOUNT (USD) · RENAMED
- **Source line on screen:** Source: the administrator renamed a co columns changed
- **Same answer in the run report:** "Columns added, renamed or dropped for Positions · source market value · Market Value · Valuation Amount (USD) · renamed: 1."
- **Screen timing:** Answered in 12 ms (from memory).
- **Check (numbers that must appear on screen):** Market Value, Valuation Amount (USD); all present: yes.
- **Receipt (Where this number comes from):** the figure page `http://127.0.0.1:8780/v3/knowledge/figures/fig-columns-added-renamed-or-dropped`. The figure is Columns added, renamed or dropped (`fig-columns-added-renamed-or-dropped`): built from Columns added, renamed or dropped; reads sheet_mapping_columns, sheet_mappings, source_batches; approved by Anita Rao; versions [1] on record. 

### Left for the next ones

- Figures this case built that later cases used: Single‑issuer concentration (used again by uc5-limits).
- Figures this case reused from earlier cases: fig-net-worth, fig-time-weighted-return-net-of-fees, fig-allocation-drift.

### Screens

- Thread page at live: `docs/v3/top10/shots/uc-016-schemadrift-thread-live.png`
- Consume answer, with "Show the figures" opened: `docs/v3/top10/shots/uc-016-schemadrift-consume-check.png`
- One figure page (Knowledge > Figures): `docs/v3/top10/shots/uc-016-schemadrift-figure.png`

## 7. Every morning I check cash  (`uc2-recon-break-desk`)

**Person:** Grace Ong (ops_lead). **Thread:** `t-29254afc6f`, created 08:24 UTC, live 08:35 UTC (10.9 min from first message to live). **Run:** `run-20261021-083410-a649`, next run daily at 06:00. **Stage reached:** live.

**Time per stage (run report, seconds):** drafting 377, decision1 6, working 266, decision2 3, decision3 3. **Total:** 655 s = 10.9 min.

### Intent

- **What the person said:** "Every morning I check cash for each entity: administrator against the bank and our trading desk. Anything over 5,000 I want as a break with the likely cause, and the ones that are just timing marked as timing. Entity B was off on the 8th, start there."
- **Read by / decides / when:** Operations manager, CFO; Approve cash breaks, Monitor liquidity; each morning (daily)
- **What it is built to show (use case definition):** Consume: cash differences by entity, open breaks.
- **Check question:** "Which entity has a cash break on 8 October and by how much?"; numbers that must appear: 12,400.

### Decision 1: what Harbor drafted

North asked: "Who reads the cash break report each morning and what decision they take from it? I have drafted source Bank cash feed and source Trading desk cash feed; say yes to accept, or tell me what is wrong. I am filling the open parts with the usual practice now, marked as suggestions." | "Here is what we are building: Every morning I check cash for each entity: administrator against the bank and our trading desk. Anything over 5,000 I want as a break with the likely cause, and the ones that are just timing marked as timing. Entity B was off on the 8th, start there. Read by Operations manager, CFO. Needed by each morning (daily). These are the figures, and where each comes from: - Cash break amount: from Bank cash feed, Trading desk cash feed - Number of breaks over threshold: from Bank cash feed, Trading desk cash feed - Account set-up signatories against the signing policy (suggested): no source yet This is how it runs today: - not described Still unclear (1): Who decides the likely cause for a cash break over 5,000? It cannot be signed yet: Process map: Lanes and steps. Tell me and I will fill them in, or type them on the documents panel. A copy of the statement is under Download a copy. I am filling the open parts with the usual practice now, marked as suggestions."

Signed by Grace Ong at 2026-10-21T08:31:16+00:00.

| Figure (as drafted) | What it means | How it is worked out | Built from | Owner | How often |
|---|---|---|---|---|---|
| Cash break amount | Difference between bank and trading‑desk cash balances per entity |  | Cash break recipe (suggested) | Operations manager | daily |
| Number of breaks over threshold | Count of entities where the cash break exceeds 5,000 |  | No recipe yet: Span designs it (suggested) | Operations manager | daily |
| Account set-up signatories against the signing policy | One row per current pending bank account. signatories = the signatory fields of its opening form, in the form's order. The policy needs at least min_signatories, one of whom holds the required_role (users.business_role, or the title of the latest payroll period). missing_signatory = the holder of the required role when not among the signatories. meets_signing_policy when both hold; approved when it meets the policy and the account is no longer pending. With no signed policy the checks are empty. | One row per current pending bank account. signatories = the signatory fields of its opening form, in the form's order. The policy needs at least min_signatories, one of whom holds the required_role (users.business_role, or the title of the latest payroll period). missing_signatory = the holder of the required role when not among the signatories. meets_signing_policy when both hold; approved when it meets the policy and the account is no longer pending. With no signed policy the checks are empty. | Account set-up signatories against the signing policy recipe (suggested) | Operations manager | daily |

Process map Harbor proposed (today's way): 1. Collect cash feeds (Grace Ong): Download the bank cash feed and the trading‑desk cash feed each morning ; 2. Reconcile cash balances (Operations manager): Compare cash balances per entity and calculate differences ; 3. Classify breaks (Operations manager): Flag any difference over 5,000, assign a likely cause or mark as timing‑only ; 4. Generate cash‑break report (Grace Ong): Create a report listing each entity’s balances, differences and cause/timing flag ; 5. Distribute report (CFO): Email the cash‑break report to Operations manager and CFO ; 6. Archive report (Operations manager): Store the report in the shared drive for one‑year retention.

Recipe bindings (figure to recipe, from the rules): Cash break amount -> cash_break (Its name or definition names the cash break recipe.); Number of breaks over threshold -> none, Span designs it (No recipe of the pack computes it; Span designs it.); Account set-up signatories against the signing policy -> account_setup (Your question asks for the account set-up signatories against the signing policy and no figure of the brief is built from it.).

### Decision 2: files, kinds, readers, tables

- **Sources named in the brief:** Bank cash feed; Trading desk cash feed.
- **Systems Span read:** Bank cash feed; Trading desk cash feed.
- **Files this case dropped:** none.
- **Kind each file was recognised as:** the thread does not write a kind per file; the office folder has 0 files in its pack map. Emails and Word/markdown notes were read as context (not as a table); PDFs and sheets were read by the reader named below.
- **Readers that loaded them (skills run on this case):** `data.recognise-file`, `data.profile-file`, `map.map-file`, `data.read-pdf-fields`.
- **Already in the office (reused from earlier cases):** 2 sources already in the office (from the workbench step: 0 files read, 0 mappings proposed, 2 sources already in the office).
- **Answers the person gave to Harbor questions:** No check this time.
- **Loaded:** "0 files loaded". Left out: bank_cash_feed. Exceptions: none.
- **Tables loaded with row counts:** `cash_movements` 557 rows; `instruments` 59 rows; `legal_entities` 3 rows; `portfolios` 8 rows; `position_snapshots` 6,329 rows. These are the row counts in the office now, after all ten cases; the office did not keep a per-case count, so the figures here are not a snapshot at the time of the run.

### Decision 3: figures, recipes, gold tables, checks

| Figure | Version at live | Status | Gold table | Rows | Recipe (what Harbor used) | Formula in words | Tie-out | Reused from earlier |
|---|---|---|---|---|---|---|---|---|
| Cash break amount (`fig-cash-break-amount`) | v1 | verified | `gold_every_morning_i_check_cash_cash_break` | 834 | `cash_break`: Cash break | Break of a day = the administrator's closing cash of the day, less its closing cash on the day before it (its previous snapshot date), less the sum of the cash movements recorded on the same portfolio... | ok: The administrator cash in the break equals the administrator cash positions of the position snapshots for the same entities, currencies and days | no |
| Number of breaks over threshold (`fig-number-of-breaks-over-threshold`) | v1 | held | not built: it is a share or a count under a condition, which a plain total of the exceptions cannot give, so it is not in a gold table yet. |  | none: Span designed the table |  | n/a | no |
| Account set-up signatories against the signing policy (`fig-account-set-up-signatories-against-the-signing-policy`) | v2 | verified | `gold_every_morning_i_check_cash_account_setup` | 1 | `account_setup`: Account set-up signatories against the signing policy | One row per current pending bank account. signatories = the signatory fields of its opening form, in the form's order. The policy needs at least min_signatories, one of whom holds the required_role (u... | ok: Accounts equal the pending bank accounts on file | yes |

- **Checks at decision 3:** adds-up: "0 ready tables added; no table for Number of breaks over threshold; 2 of 3 figures have rows". Against the report: "no check, by the person's choice".
- **Notes on figures that were not built:** Number of breaks over threshold: it is a share or a count under a condition, which a plain total of the exceptions cannot give, so it is not in a gold table yet..
- **Second-model checks (worker and checker from different families, logged in `judge/log.json`), in this case's window:**
  - 08:29:26 UTC, recipe: agreed; answer: none. Question: Which recipe computes the figure 'Number of breaks over threshold', defined as: Count of entities where the cash break exceeds 5,000 (formula: not given)? Harbor took: none. qwen/qwen3.7-flash: The figure is a count of entities meeting a threshold, which is a...

### Skills run

34 of 34 skill calls succeeded, from `skill_runs.jsonl` for this thread. Skills used: 20 skill-folder skills and 1 per-kind file readers (data.read-<kind>). Most used: `model.design-ready-table` x5, `intent.define-figure` x3, `check.adds-up` x3, `intent.restate-ask` x2, `intent.find-gaps` x2, `intent.fill-with-practice` x2, `model.find-reusable` x2, `data.recognise-file` x2.
- Workbench steps (the thread's own log): 1. North: Signed the intent (ok; signed and sent to Build) | 2. North: Handed over to build (ok; handed to the data engineer) | 3. Span: Read the systems (ok; 2 systems, 0 questions assumed) | 4. Span: Read the sample files (ok; 4 files given to Span as samples) | 5. Span: Drafted and approved the design pack (ok; design pack approved) | 6. Flow: Read the dropped files (ok; 0 files read, 0 mappings proposed, 2 sources already in the office) | 7. Span: Applied your answers (ok; 1 answers applied) | 8. Flow: Accepted the mappings and loaded (ok; 0 files loaded) | 9. Flow: Ran on a copy (ok; ran on a copy) | 10. Span: Made sure each figure has a filled ready table (ok; 0 ready tables added; no table for Number of breaks over threshold; 2 of 3 figures have rows) | 11. Flow: Compared with the report (ok; no check, by the person's choice) | 12. Flow: Went live (ok; live on daily at 06:00) | 13. Lumen: Built the starter board (ok; Lumen starter board accepted and published) | 14. Lumen: Wrote the morning note (ok; morning note written) | 15. Flow: Recorded the run on each figure (ok; run recorded on 2 figures).

**Model calls recorded for this case:** 10 (openai/gpt-oss-120b x10; tiers specialist x9, manager x1); estimated cost USD 0.0052. Source: `model_costs.jsonl`, rows with this thread's intent id.

### Live answer and its receipt

- **Check question (asked in Consume, as Grace Ong):** "Which entity has a cash break on 8 October and by how much?"
- **Answer word for word (Consume screen):** "Cash break on 8 October 2026, over the signed cash tolerance of 5,000 USD per entity per day: Entity B 12,400.00 USD. Agree: Entity B, Evergreen Family Trust, Evergreen Family Trust, Evergreen Holdings, Evergreen Holdings."
- **Heading on screen:** CASH BREAK · 8 OCTOBER 2026 · ENTITY B
- **Source line on screen:** Source: every morning i check cash cash break
- **Same answer in the run report:** "Cash break on 8 October 2026, over the signed cash tolerance of 5,000 USD per entity per day: Entity B 12,400.00 USD. Agree: Entity B, Evergreen Family Trust, Evergreen Family Trust, Evergreen Holdings, Evergreen Holdings."
- **Screen timing:** Answered in 30 ms (from memory).
- **Check (numbers that must appear on screen):** 12,400; all present: yes.
- **Receipt (Where this number comes from):** the figure page `http://127.0.0.1:8780/v3/knowledge/figures/fig-cash-break-amount`. The figure is Cash break amount (`fig-cash-break-amount`): built from Cash break; reads bank_accounts, cash_movements, instruments, legal_entities, portfolios, position_snapshots; approved by Grace Ong; versions [1] on record. 

### Left for the next ones

- Figures this case built that later cases used: none.
- Figures this case reused from earlier cases: fig-account-set-up-signatories-against-the-signing-policy.

### Screens

- Thread page at live: `docs/v3/top10/shots/uc2-recon-break-desk-thread-live.png`
- Consume answer, with "Show the figures" opened: `docs/v3/top10/shots/uc2-recon-break-desk-consume-check.png`
- One figure page (Knowledge > Figures): `docs/v3/top10/shots/uc2-recon-break-desk-figure.png`

## 8. Monthly performance line for Evergreen Liquid portfolio  (`uc4-vs-benchmark`)

**Person:** Raj Patel (cio). **Thread:** `t-92890bb272`, created 08:36 UTC, live 08:37 UTC (1.7 min from first message to live). **Run:** `run-20261021-083744-83fd`, next run monthly at 06:00. **Stage reached:** live.

**Time per stage (run report, seconds):** drafting 65, decision1 3, working 30, decision2 3, decision3 3. **Total:** 104 s = 1.7 min.

### Intent

- **What the person said:** "I need to see how the Evergreen Liquid portfolio did last month against our blended benchmark, in one line I can put in front of the committee. The benchmark definition is in the workbook, the index levels are in the market data."
- **Read by / decides / when:** Investment Committee; Approve or comment on the monthly performance line; Before the monthly committee meeting
- **What it is built to show (use case definition):** Consume: portfolio against benchmark, by month.
- **Check question:** "How did the liquid portfolio do against the benchmark in September 2026?"; numbers that must appear: 4.1667, 2.7072.

### Decision 1: what Harbor drafted

North asked: "Got it – you need a single‑line statement of Evergreen Liquid portfolio’s performance last month versus the blended benchmark. Who reads this line and what decision do they take from it? I have drafted KPI Monthly excess return versus blended benchmark; say yes to accept, or tell me what is wrong. I am filling the open parts with the usual practice now, marked as suggestions."

Signed by Raj Patel at 2026-10-21T08:37:35+00:00.

| Figure (as drafted) | What it means | How it is worked out | Built from | Owner | How often |
|---|---|---|---|---|---|
| Monthly excess return versus blended benchmark | Net‑of‑fee return for Evergreen Liquid portfolio in the last month minus the blended benchmark return for the same period. | (Company return – Benchmark return) | Time weighted return and active return recipe (suggested) |  | monthly |

Process map Harbor proposed (today's way): 1. Custodian data arrival (Operations): Upload positions and cash file from custodian ; 2. Bank balance arrival (Finance): Upload daily bank balance extract ; 3. Private‑fund portal data pull (Investments): Download latest NAV, calls and distributions ; 4. Reconciliation (Raj Patel): Match positions, cash and bank balances; resolve breaks ; 5. Valuation (Investments): Apply latest NAV, add calls, subtract distributions, compute excess return ; 6. Pack assembly (Raj Patel): Insert one‑line statement into committee slide deck.

Recipe bindings (figure to recipe, from the rules): Monthly excess return versus blended benchmark -> time_weighted_return (Its name or definition names the time weighted return and active return recipe.).

### Decision 2: files, kinds, readers, tables

- **Sources named in the brief:** Custodian positions and cash file; Bank balance extract; Private‑fund portal data; Market data workbook.
- **Systems Span read:** Custodian positions and cash file; Bank balance extract; Private‑fund portal data; Market data workbook.
- **Files this case dropped and Harbor read (3):** `month_end_process_narrative.md`, `07_investment_committee_note_2026-09-17.md`, `08_investment_committee_note_2026-10-08.md`.
- **Kind each file was recognised as:** the thread does not write a kind per file; the office folder has 1 files in its pack map. Emails and Word/markdown notes were read as context (not as a table); PDFs and sheets were read by the reader named below.
- **Readers that loaded them (skills run on this case):** `data.recognise-file`, `data.profile-file`, `map.map-file`, `data.read-pdf-fields`, `data.read-sop`.
- **Already in the office (reused from earlier cases):** 4 sources already in the office (from the workbench step: 4 files read, 0 mappings proposed, 4 sources already in the office).
- **Answers the person gave to Harbor questions:** No check this time.
- **Loaded:** "1 files loaded". Left out: bank_balance_extract, market_data_workbook. Exceptions: none.
- **Tables loaded with row counts:** `market_observations` 614 rows; `portfolios` 8 rows; `position_snapshots` 6,329 rows; `transactions` 75 rows. These are the row counts in the office now, after all ten cases; the office did not keep a per-case count, so the figures here are not a snapshot at the time of the run.

### Decision 3: figures, recipes, gold tables, checks

| Figure | Version at live | Status | Gold table | Rows | Recipe (what Harbor used) | Formula in words | Tie-out | Reused from earlier |
|---|---|---|---|---|---|---|---|---|
| Monthly excess return versus blended benchmark (`fig-monthly-excess-return-versus-blended-benchmark`) | v1 | verified | `gold_how_the_evergreen_liquid_portf_time_weighted_return` | 83 | `time_weighted_return`: Time weighted return and active return | Monthly return in percent (modified Dietz; a month is one whose end is a month end, a month still open is left out) = (end value - start value - net flow) / (start value + 0.5 x net flow) x 100, where... | ok: The month-end values used are the position snapshots of the same dates | no |

- **Checks at decision 3:** adds-up: "all 1 figures have a ready table; 1 of 1 figures have rows". Against the report: "no check, by the person's choice".
- **Second-model checks:** none in this case's window (the checks use the figure rules and the tie-outs above).

### Skills run

30 of 30 skill calls succeeded, from `skill_runs.jsonl` for this thread. Skills used: 21 skill-folder skills and 2 per-kind file readers (data.read-<kind>). Most used: `model.design-ready-table` x3, `check.adds-up` x3, `intent.define-figure` x2, `model.find-reusable` x2, `data.recognise-file` x2, `intent.restate-ask` x1, `intent.find-gaps` x1, `intent.fill-with-practice` x1.
- Workbench steps (the thread's own log): 1. North: Signed the intent (ok; signed and sent to Build) | 2. North: Handed over to build (ok; handed to the data engineer) | 3. Span: Read the systems (ok; 4 systems, 0 questions assumed) | 4. Span: Read the sample files (ok; 11 files given to Span as samples) | 5. Span: Drafted and approved the design pack (ok; design pack approved) | 6. Flow: Read the dropped files (ok; 4 files read, 0 mappings proposed, 4 sources already in the office) | 7. Span: Applied your answers (ok; 1 answers applied) | 8. Flow: Accepted the mappings and loaded (ok; 1 files loaded) | 9. Flow: Ran on a copy (ok; ran on a copy) | 10. Span: Made sure each figure has a filled ready table (ok; all 1 figures have a ready table; 1 of 1 figures have rows) | 11. Flow: Compared with the report (ok; no check, by the person's choice) | 12. Flow: Went live (ok; live on monthly at 06:00) | 13. Lumen: Built the starter board (ok; no starter board yet: no figure has a ready table; it appears after a live run fills one) | 14. Lumen: Wrote the morning note (ok; morning note written) | 15. Flow: Recorded the run on each figure (ok; run recorded on 1 figures).

**Model calls recorded for this case:** 3 (openai/gpt-oss-120b x3; tiers specialist x3); estimated cost USD 0.0013. Source: `model_costs.jsonl`, rows with this thread's intent id.

### Live answer and its receipt

- **Check question (asked in Consume, as Raj Patel):** "How did the liquid portfolio do against the benchmark in September 2026?"
- **Answer word for word (Consume screen):** "Evergreen Liquid portfolio 4.1667% for 2026-09 against 2.7072% for the benchmark."
- **Heading on screen:** MONTHLY EXCESS RETURN VERSUS BLENDED BENCHMARK · EG-PRIVATE · MONTH · 2026-09 · A VALUE IS CARRIED FORWARD OR ESTIMATED
- **Source line on screen:** Source: how the evergreen liquid portf time weighted return
- **Same answer in the run report:** "Evergreen Liquid portfolio 4.1667% for 2026-09 against 2.7072% for the benchmark."
- **Screen timing:** not in the captured text.
- **Check (numbers that must appear on screen):** 4.1667, 2.7072; all present: yes.
- **Receipt (Where this number comes from):** the figure page `http://127.0.0.1:8780/v3/knowledge/figures/fig-monthly-excess-return-versus-blended-benchmark`. The figure is Monthly excess return versus blended benchmark (`fig-monthly-excess-return-versus-blended-benchmark`): built from Time weighted return and active return; reads benchmark_components, benchmark_definitions, business_rules, market_observations, portfolios, position_snapshots, rule_versions, transactions; approved by Raj Patel; versions [1] on record. 

### Left for the next ones

- Figures this case built that later cases used: none.
- Figures this case reused from earlier cases: none.

### Screens

- Thread page at live: `docs/v3/top10/shots/uc4-vs-benchmark-thread-live.png`
- Consume answer, with "Show the figures" opened: `docs/v3/top10/shots/uc4-vs-benchmark-consume-check.png`
- One figure page (Knowledge > Figures): `docs/v3/top10/shots/uc4-vs-benchmark-figure.png`

## 9. To test the liquid book  (`uc5-limits`)

**Person:** Tom Hale (risk_officer). **Thread:** `t-ea56a1dffb`, created 08:38 UTC, live 08:45 UTC (7.0 min from first message to live). **Run:** `run-20261021-084504-6b3c`, next run monthly at 06:00. **Stage reached:** live.

**Time per stage (run report, seconds):** drafting 246, decision1 3, working 156, decision2 3, question 3, decision3 3. **Total:** 414 s = 6.9 min.

### Intent

- **What the person said:** "I want to test the liquid book against our signed limits every month: no single name over 5 percent, listed equity between 60 and 90. Tell me what is a real breach and what is just a stale or missing value, and anything that has no asset class."
- **Harbor's one-line restatement (brief):** I want to test the liquid book against our signed limits every month: no single name over 5 percent, listed equity between 60 and 90.
- **Read by / decides / when:** Investment Committee, Risk Officer, Portfolio Manager, Data Owner; Investment Committee decides on breach actions and signs off the pack, Risk Officer reviews KPI calculations, Portfolio Manager monitors asset‑class allocations and limits, Data Owner ensures data quality and completeness; every month; the day is not said yet
- **What it is built to show (use case definition):** Consume: holdings against limits, breaches open.
- **Check question:** "Which holding is over its single-name limit?"; numbers that must appear: 5.75.

### Decision 1: what Harbor drafted

North asked: "I don't have the precise definitions for a real breach versus a stale or missing value, or for items with no asset class – those need to be clarified. Who reads the liquid‑book pack and decides what actions to take when a breach is identified? I have drafted when it is needed and 1 open question; Daniel Foo or another person who may approve this work can accept it. I am filling the open parts with the usual practice now, marked as suggestions." | "I've drafted the usual practice for each missing area; could you confirm which day of the month the pack should be ready? I have drafted source Custodian positions file, source Bank balances feed, source Private fund portal data, source Manual adjustments file and 3 more; it waits for approval." | "Using the usual practice I’ve drafted the missing sections. Could you tell me which day of each month the pack should be ready? I have drafted source Custodian statements, source Bank balance files, source Private fund portal extracts and source Manual adjustments ledger; it waits for approval. I am filling the open parts with the usual practice now, marked as suggestions." | "I’ve drafted the usual practice for who reads the pack and what they decide, and a description of what the pack looks like. Is a PDF pack with one card per KPI and breach flags the format you want? I have drafted who reads it, what they decide and result; it waits for approval."

Signed by Daniel Foo at 2026-10-21T08:42:48+00:00.

| Figure (as drafted) | What it means | How it is worked out | Built from | Owner | How often |
|---|---|---|---|---|---|
| Single‑issuer concentration | Aggregate direct issuer exposure divided by total included asset value |  | Single-issuer concentration recipe (suggested) | Risk Officer | monthly |
| Listed equity allocation | Value of listed equity holdings as a percentage of total assets |  | Allocation by asset class and entity recipe (suggested) | Investment Analyst | monthly |
| Stale‑valuation share | Value of assets with valuation age above the approved threshold divided by total included asset value |  | Valuation age recipe (suggested) | Portfolio Manager | monthly |
| Holdings without asset class | Count of holdings that have no assigned asset‑class label |  | Instruments with no class or identifier recipe (suggested) | Data Owner | monthly |
| Payments over their approval limit | One row per current expense of the ledger, in USD at the fixing of its day (or the latest before it), rounded to the cent. The limit is the signed approver_limit_ rule named after the approver (the name in lower case, words joined by _), in its currency. over_limit when the USD amount is above it. An approver with no signed limit has an empty limit and is not judged. | One row per current expense of the ledger, in USD at the fixing of its day (or the latest before it), rounded to the cent. The limit is the signed approver_limit_ rule named after the approver (the name in lower case, words joined by _), in its currency. over_limit when the USD amount is above it. An approver with no signed limit has an empty limit and is not judged. | Payments over their approval limit recipe (suggested) | Risk Officer | monthly |
| Single-name breaches and cost to cure | For the the latest month-end position date (a month end is the last day of the month or its last business day; a date in a month still open is not one) of each portfolio that has a signed single-name limit (a business rule of type policy or limit, the type a signed limits workbook is loaded as, whose parameters name the portfolio and the dimension single_name, with max_pct), each holding's exposure over the portfolio total in percent. A holding is over the limit when its share is above max_pct. A limit whose bucket names one holding (the signed limits workbook names Harborview Semiconductor) is tested on that holding only; a bucket of any single name, or none, on every holding. A holding is exempt only when a signed office rule says so (a business rule of type policy whose parameters name the portfolio, the dimension single_name_exempt and the instrument); with no such rule on record every holding, a sovereign note included, is tested like the others, and the policy text (section 3, any single name 0 to 5 percent) names no exception. A portfolio with holdings in more than one currency has no share worked out (status says so). A breach is real when the oldest value behind it is no older than the office's stale-value days (rule stale_value_days, else 90 days, the use-case card), otherwise it is possibly stale. Cost to cure = (exposure - limit x total) / (1 - limit), the amount to sell so the name is at the limit of what is left. A holding with no asset class is flagged. | For the the latest month-end position date (a month end is the last day of the month or its last business day; a date in a month still open is not one) of each portfolio that has a signed single-name limit (a business rule of type policy or limit, the type a signed limits workbook is loaded as, whose parameters name the portfolio and the dimension single_name, with max_pct), each holding's exposure over the portfolio total in percent. A holding is over the limit when its share is above max_pct. A limit whose bucket names one holding (the signed limits workbook names Harborview Semiconductor) is tested on that holding only; a bucket of any single name, or none, on every holding. A holding is exempt only when a signed office rule says so (a business rule of type policy whose parameters name the portfolio, the dimension single_name_exempt and the instrument); with no such rule on record every holding, a sovereign note included, is tested like the others, and the policy text (section 3, any single name 0 to 5 percent) names no exception. A portfolio with holdings in more than one currency has no share worked out (status says so). A breach is real when the oldest value behind it is no older than the office's stale-value days (rule stale_value_days, else 90 days, the use-case card), otherwise it is possibly stale. Cost to cure = (exposure - limit x total) / (1 - limit), the amount to sell so the name is at the limit of what is left. A holding with no asset class is flagged. | Single-name breaches and cost to cure recipe (suggested) | Risk Officer | monthly |

Process map Harbor proposed (today's way): 1. Operations pull custodian statements (Operations Manager): Download monthly custodian statement files ; 2. Reconcile positions and cash (Operations Analyst): Match positions against cash and resolve breaks ; 3. Risk runs KPI calculations (Risk Officer): Apply KPI formulas to reconciled data ; 4. Data Owner checks asset‑class tags (Data Owner): Identify holdings missing asset‑class, flag them ; 5. Pack compilation (Investment Analyst): Create monthly PDF pack with KPI cards and breach flags ; 6. Investment Committee review (Investment Committee Chair): Review pack, approve breach actions, sign off.

Recipe bindings (figure to recipe, from the rules): Single‑issuer concentration -> concentration (Its name or definition names the single-issuer concentration recipe.); Listed equity allocation -> allocation (Its name or definition names the allocation by asset class and entity recipe.); Stale‑valuation share -> value_age_days (Its name or definition names the valuation age recipe.); Holdings without asset class -> identifier_gaps (The identifier_gaps recipe flags instruments with no asset class and provides a gap_count, which matches the figure's definition of counting holdings lacking an asset‑class label.); Payments over their approval limit -> approval_exceptions (Your question asks for the payments over their approval limit and no figure of the brief is built from it.); Single-name breaches and cost to cure -> single_name_breach (Your question asks for the single-name breaches and cost to cure and no figure of the brief is built from it.).

### Decision 2: files, kinds, readers, tables

- **Sources named in the brief:** Custodian positions file; Bank balances feed; Private fund portal data; Manual adjustments file; Custodian statements; Bank balance files; Private fund portal extracts; Manual adjustments ledger.
- **Systems Span read:** Custodian positions file; Bank balances feed; Private fund portal data; Manual adjustments file; Custodian statements; Bank balance files; Private fund portal extracts; Manual adjustments ledger.
- **Files this case dropped:** none.
- **Kind each file was recognised as:** the thread does not write a kind per file; the office folder has 0 files in its pack map. Emails and Word/markdown notes were read as context (not as a table); PDFs and sheets were read by the reader named below.
- **Readers that loaded them (skills run on this case):** `data.recognise-file`, `data.profile-file`, `map.map-file`, `data.read-pdf-fields`.
- **Already in the office (reused from earlier cases):** 5 sources already in the office (from the workbench step: 0 files read, 0 mappings proposed, 5 sources already in the office).
- **Answers the person gave to Harbor questions:** No check this time, Use these definitions.
- **Loaded:** "0 files loaded". Left out: bank_balance_files, bank_balances_feed, custodian_positions_file, custodian_statements, manual_adjustments_file, private_fund_portal_extr. Exceptions: none.
- **Tables loaded with row counts:** `instruments` 59 rows; `portfolios` 8 rows; `position_snapshots` 6,329 rows; `legal_entities` 3 rows; `valuation_observations` 59 rows; `market_observations` 614 rows. These are the row counts in the office now, after all ten cases; the office did not keep a per-case count, so the figures here are not a snapshot at the time of the run.

### Decision 3: figures, recipes, gold tables, checks

| Figure | Version at live | Status | Gold table | Rows | Recipe (what Harbor used) | Formula in words | Tie-out | Reused from earlier |
|---|---|---|---|---|---|---|---|---|
| Single‑issuer concentration (`fig-single-issuer-concentration`) | v2 | verified | `gold_to_test_the_liquid_book_concentration` | 3755 | `concentration`: Single-issuer concentration | Concentration in percent = the market value held in one issuer (the instrument's name) in a portfolio divided by the portfolio's total market value held, for the same date and currency, times 100. Cas... | ok: The exposures add up to the total of the position snapshots for the same dates, cash counted once | yes |
| Listed equity allocation (`fig-listed-equity-allocation`) | v1 | held | not built: The run did not build allocation by asset class entity. |  | `allocation`: Allocation by asset class and entity | Market value of the position snapshots (counted as net_worth counts them, cash left out) by asset class and entity, and each row's share_pct of the total of the same position date and currency, in per... | n/a | no |
| Stale‑valuation share (`fig-stale-valuation-share`) | v1 | held | not built: The run did not build value age days. |  | `value_age_days`: Valuation age | As-of date less the latest valuation date of each instrument, in days (the as-of date is the latest position date loaded); stale above 90 days (the threshold the card and the stub name; an office that... | n/a | no |
| Holdings without asset class (`fig-holdings-without-asset-class`) | v1 | verified | `gold_to_test_the_liquid_book_identifier_gaps` | 52 | `identifier_gaps`: Instruments with no class or identifier | One row for each instrument held at the latest month end loaded (the date the limits are measured on, policy section 3; a market value other than zero there; an instrument that is only in the master, ... | ok: The values held add up to the position snapshots at the latest month end | no |
| Payments over their approval limit (`fig-payments-over-their-approval-limit`) | v2 | verified | `gold_to_test_the_liquid_book_approval_exceptions` | 151 | `approval_exceptions`: Payments over their approval limit | One row per current expense of the ledger, in USD at the fixing of its day (or the latest before it), rounded to the cent. The limit is the signed approver_limit_ rule named after the approver (the na... | ok: Payments equal the current lines of the expense ledger | yes |
| Single-name breaches and cost to cure (`fig-single-name-breaches-and-cost-to-cure`) | v1 | verified | `gold_to_test_the_liquid_book_single_name_breach` | 1 | `single_name_breach`: Single-name breaches and cost to cure | For the the latest month-end position date (a month end is the last day of the month or its last business day; a date in a month still open is not one) of each portfolio that has a signed single-name ... | ok: The portfolio totals used equal the position snapshots of the same portfolios and dates (a limit on one named holding tests that holding only) | no |

- **Checks at decision 3:** adds-up: "0 ready tables added; no table for Listed equity allocation, Stale‑valuation share; 4 of 6 figures have rows". Against the report: "no check, by the person's choice".
- **Held (not used in the figures until a person says so):** `gold_to_test_the_liquid_book_allocation_by_asset_class_entity`; `gold_to_test_the_liquid_book_value_age_days`.
- **Notes on figures that were not built:** Listed equity allocation: Span's design repeats a table the pack already has, which holds nothing.; Stale‑valuation share: Span's design repeats a table the pack already has, which holds nothing..
- **Second-model checks (worker and checker from different families, logged in `judge/log.json`), in this case's window:**
  - 08:40:59 UTC, recipe: did not agree (a person is asked). Question: (text not logged in judge/log.json)
  - 08:42:59 UTC, mapping_row: did not agree (a person is asked). Question: (text not logged in judge/log.json)
  - 08:42:59 UTC, mapping_row: did not agree (a person is asked). Question: (text not logged in judge/log.json)
  - 08:42:59 UTC, mapping_row: agreed; answer: yes. Question: Does the proposed definition say clearly what the column position_date of the ready table allocation by asset class entity holds? Harbor took: yes. qwen/qwen3.7-flash: The select passes position_date unchanged from position_snapshots, and the definition correc...
  - 08:43:46 UTC, mapping_row: agreed; answer: yes. Question: Does the proposed definition say clearly what the column instrument_type of the ready table value age days holds? Harbor took: yes. qwen/qwen3.7-flash: The select statement directly passes through i.instrument_type from the instruments table without modificati...
  - 08:42:59 UTC, mapping_row: agreed; answer: no. Question: Does the proposed definition say clearly what the column currency of the ready table allocation by asset class entity holds? Harbor took: no. qwen/qwen3.7-flash: The definition incorrectly attributes the column to instruments.currency, while the select actuall...
  - 08:43:47 UTC, mapping_row: agreed; answer: yes. Question: Does the proposed definition say clearly what the column valuation_date of the ready table value age days holds? Harbor took: yes. qwen/qwen3.7-flash: The select passes l.valuation_date from valuation_observations through unchanged, which matches the definitio...
  - 08:43:44 UTC, mapping_row: agreed; answer: no. Question: Does the proposed definition say clearly what the column fund of the ready table value age days holds? Harbor took: no. qwen/qwen3.7-flash: The definition is vague and does not name the source table and column (instruments.canonical_name) that the select uses...
  - 08:44:08 UTC, mapping_row: agreed; answer: no. Question: Does the proposed definition say clearly what the column as_of of the ready table value age days holds? Harbor took: no. qwen/qwen3.7-flash: The definition merely repeats the column name for a computed column instead of describing the calculation performed in...
  - 08:44:08 UTC, mapping_row: agreed; answer: no. Question: Does the proposed definition say clearly what the column stale_after_days of the ready table value age days holds? Harbor took: no. qwen/qwen3.7-flash: The select statement assigns a fixed value of 90 to the column, satisfying the standard's condition for 'No'...
  - 08:44:13 UTC, mapping_row: agreed; answer: no. Question: Does the proposed definition say clearly what the column currency of the ready table value age days holds? Harbor took: no. qwen/qwen3.7-flash: The definition claims the source is instruments.currency, but the select actually retrieves l.currency from valuatio...

### Skills run

47 of 47 skill calls succeeded, from `skill_runs.jsonl` for this thread. Skills used: 20 skill-folder skills and 1 per-kind file readers (data.read-<kind>). Most used: `model.design-ready-table` x17, `intent.define-figure` x3, `check.adds-up` x3, `intent.restate-ask` x2, `intent.find-gaps` x2, `intent.fill-with-practice` x2, `intent.sign` x2, `model.find-reusable` x2.
- Workbench steps (the thread's own log): 1. North: Signed the intent (ok; signed and sent to Build) | 2. North: Handed over to build (ok; handed to the data engineer) | 3. Span: Read the systems (ok; 8 systems, 0 questions assumed) | 4. Span: Read the sample files (ok; 10 files given to Span as samples) | 5. Span: Drafted and approved the design pack (ok; design pack approved) | 6. Flow: Read the dropped files (ok; 0 files read, 0 mappings proposed, 5 sources already in the office) | 7. Span: Applied your answers (failed; 1 mapping row still need a person: settle them first.) | 8. Span: Applied your answers (ok; 2 answers applied) | 9. Flow: Accepted the mappings and loaded (ok; 0 files loaded) | 10. Flow: Ran on a copy (ok; ran on a copy) | 11. Span: Made sure each figure has a filled ready table (ok; 0 ready tables added; no table for Listed equity allocation, Stale‑valuation share; 4 of 6 figures have rows) | 12. Flow: Compared with the report (ok; no check, by the person's choice) | 13. Flow: Went live (ok; live on monthly at 06:00) | 14. Lumen: Built the starter board (ok; Lumen starter board accepted and published) | 15. Lumen: Wrote the morning note (ok; morning note written) | 16. Flow: Recorded the run on each figure (ok; run recorded on 6 figures).

**Model calls recorded for this case:** 8 (openai/gpt-oss-120b x8; tiers specialist x8); estimated cost USD 0.0039. Source: `model_costs.jsonl`, rows with this thread's intent id.

### Live answer and its receipt

- **Check question (asked in Consume, as Tom Hale):** "Which holding is over its single-name limit?"
- **Answer word for word (Consume screen):** "Over the single-name limit on 30 Sep 2026: Harborview Semiconductor 5.75% (USD 2,368,000 of USD 41,200,000) against 5%, USD 324,210.53 to sell to cure."
- **Heading on screen:** SINGLE-NAME BREACHES AND COST TO CURE · EVERGREEN LIQUID PORTFOLIO · HARBORVIEW SEMICONDUCTOR · LISTED_EQUITY · USD · REAL BREACH
- **Source line on screen:** Source: to test the liquid book single name breach
- **Same answer in the run report:** "Over the single-name limit on 30 Sep 2026: Harborview Semiconductor 5.75% (USD 2,368,000 of USD 41,200,000) against 5%, USD 324,210.53 to sell to cure."
- **Screen timing:** Answered in 18 ms (from memory).
- **Check (numbers that must appear on screen):** 5.75; all present: yes.
- **Receipt (Where this number comes from):** the figure page `http://127.0.0.1:8780/v3/knowledge/figures/fig-single-name-breaches-and-cost-to-cure`. The figure is Single-name breaches and cost to cure (`fig-single-name-breaches-and-cost-to-cure`): built from Single-name breaches and cost to cure; reads business_rules, instruments, portfolios, position_snapshots, rule_versions; approved by Daniel Foo; versions [1] on record. 

### Left for the next ones

- Figures this case built that later cases used: none.
- Figures this case reused from earlier cases: fig-single-issuer-concentration, fig-payments-over-their-approval-limit.

### Screens

- Thread page at live: `docs/v3/top10/shots/uc5-limits-thread-live.png`
- Consume answer, with "Show the figures" opened: `docs/v3/top10/shots/uc5-limits-consume-check.png`
- One figure page (Knowledge > Figures): `docs/v3/top10/shots/uc5-limits-figure.png`

## 10. Each morning I would like  (`morning-networth-note`)

**Person:** Mei Chen (principal). **Thread:** `t-ebee9b7893`, created 08:45 UTC, live 08:52 UTC (7.1 min from first message to live). **Run:** `run-20261021-085233-d49c`, next run daily at 06:00. **Stage reached:** live.

**Time per stage (run report, seconds):** drafting 397, decision1 9, working 15, decision2 3, decision3 3. **Total:** 427 s = 7.1 min.

### Intent

- **What the person said:** "Each morning I would like a short note: what we are worth, in dollars and in Singapore dollars, what changed since last time, and anything that needs me. Plain words, no jargon, one page."
- **Read by / decides / when:** Senior partners (decide daily cash allocation and investment actions), Operations team (validate data and sign‑off); Approve cash allocation, Confirm investment actions; not stated
- **What it is built to show (use case definition):** Consume: the morning note, net worth in USD and SGD.
- **Check question:** "What are we worth in the latest report?"; numbers that must appear: 57,600,000.

### Decision 1: what Harbor drafted

North asked: "Who reads the note each morning, and what decision do they take from it? I am filling the open parts with the usual practice now, marked as suggestions." | "I’ve drafted suggestions for the readers, frequency, result format, data inputs, success criteria and a high‑level process map. Could you tell me what time each morning the note should be ready?" | "Got it – I’ll use the usual practice for the KPI definitions and the other suggestions you haven’t set yourself. Who should be able to see this morning note – everyone in the company, only the internal family‑office team, or a restricted group? I have drafted 3 open questions; say yes to accept, or tell me what is wrong. I am filling the open parts with the usual practice now, marked as suggestions." | "We'll limit access to the internal family‑office team, as usual. What time each morning should the note be ready? I am filling the open parts with the usual practice now, marked as suggestions." | "Here is a draft of who reads the note and decides what, the usual timing, and the typical data sources and owners. Does this list of readers and their decisions look correct? I have drafted who reads it, what they decide, source Custodian positions, source Bank balances and 5 more; say yes to accept, or tell me what is wrong."

Signed by Mei Chen at 2026-10-21T08:52:21+00:00.

| Figure (as drafted) | What it means | How it is worked out | Built from | Owner | How often |
|---|---|---|---|---|---|
| Net worth (USD) | Total assets valued in US dollars, including cash, positions and private‑fund NAVs. | Sum of all asset values converted to USD using end‑of‑day FX rates. | Net worth recipe (suggested) | Operations | Monthly |
| Change since last note | Absolute and percentage difference in net worth compared with the previous morning’s note. | Current net worth minus previous net worth; also shown as % of previous net worth. | Change since the issued report recipe (suggested) | Analyst | Daily |
| Cash drag | Cash holding as a proportion of total assets. | Cash balance / total net worth. | No recipe yet: Span designs it (suggested) | Treasury | Monthly |

Process map Harbor proposed (today's way): 1. Pull custodian positions (Operations): Extract daily positions and cash from custodian system ; 2. Pull bank balances (Treasury): Retrieve daily bank account balances ; 3. Pull FX rates (Treasury): Get end‑of‑day FX rates for required currencies ; 4. Pull private‑fund data (Investments): Download NAV, calls and distributions from fund portal ; 5. Consolidate and calculate KPIs (Analyst): Combine all inputs, compute Net worth, change and cash drag ; 6. Review and sign‑off (Operations): Validate figures, ensure controls passed, sign off ; 7. Publish note (Analyst): Compile one‑page note and distribute to readers.

Recipe bindings (figure to recipe, from the rules): Net worth (USD) -> net_worth (Its name or definition names the net worth recipe.); Change since last note -> change_since_report (Its name or definition names the change since the issued report recipe.); Cash drag -> none, Span designs it (No recipe of the pack computes it; Span designs it.).

### Decision 2: files, kinds, readers, tables

- **Sources named in the brief:** Custodian positions; Bank balances; FX rates; Private‑fund data; Manual adjustments.
- **Systems Span read:** Custodian positions; Bank balances; FX rates; Private‑fund data; Manual adjustments.
- **Files this case dropped and Harbor read (5):** `ic_note_2026-07-15.md`, `ic_note_2026-08-19.md`, `ic_note_2026-04-15.md`, `ic_note_2026-05-20.md`, `ic_note_2026-06-17.md`.
- **Kind each file was recognised as:** the thread does not write a kind per file; the office folder has 2 files in its pack map. Emails and Word/markdown notes were read as context (not as a table); PDFs and sheets were read by the reader named below.
- **Readers that loaded them (skills run on this case):** `data.recognise-file`, `data.profile-file`, `map.map-file`, `data.read-pdf-fields`, `data.read-glossary`.
- **Already in the office (reused from earlier cases):** 4 sources already in the office (from the workbench step: 7 files read, 0 mappings proposed, 4 sources already in the office).
- **Answers the person gave to Harbor questions:** No check this time.
- **Loaded:** "2 files loaded". Left out: bank_balances, custodian_positions, fx_rates, manual_adjustments, private_fund_data. Exceptions: none.
- **Tables loaded with row counts:** `instruments` 59 rows; `legal_entities` 3 rows; `portfolios` 8 rows; `position_snapshots` 6,329 rows; `valuation_observations` 59 rows. These are the row counts in the office now, after all ten cases; the office did not keep a per-case count, so the figures here are not a snapshot at the time of the run.

### Decision 3: figures, recipes, gold tables, checks

| Figure | Version at live | Status | Gold table | Rows | Recipe (what Harbor used) | Formula in words | Tie-out | Reused from earlier |
|---|---|---|---|---|---|---|---|---|
| Net worth (USD) (`fig-net-worth-usd`) | v1 | verified | `gold_each_morning_i_would_like_net_worth_by_portfolio` | 1008 | `net_worth`: Net worth | Net worth = the sum of the market values of the position snapshots of each date, one value for each portfolio, instrument, date and currency (a snapshot that a later one supersedes is out; a carried-f... | ok: Net worth equals the sum of the position snapshots for the same dates, cash counted once | no |
| Change since last note (`fig-change-since-last-note`) | v1 | verified | `gold_each_morning_i_would_like_change_since_report` | 3 | `change_since_report`: Change since the issued report | For each valuation that supersedes another (the link on the valuation), the original value is the valuation it replaces, the amended value is the replacing one, and the change is amended less original... | ok: Every amended valuation that is not itself replaced appears once | no |
| Cash drag (`fig-cash-drag`) | v1 | verified | `gold_each_morning_i_would_like_net_worth_entity_monthly` | 21 | none: Span designed the table |  | n/a | no |

- **Checks at decision 3:** adds-up: "all 3 figures have a ready table; 3 of 3 figures have rows". Against the report: "no check, by the person's choice".
- **Second-model checks (worker and checker from different families, logged in `judge/log.json`), in this case's window:**
  - 08:48:55 UTC, recipe: did not agree (a person is asked). Question: (text not logged in judge/log.json)

### Skills run

50 of 50 skill calls succeeded, from `skill_runs.jsonl` for this thread. Skills used: 21 skill-folder skills and 2 per-kind file readers (data.read-<kind>). Most used: `consume.answer-question` x9, `intent.define-figure` x4, `model.design-ready-table` x4, `consume.explain-number` x4, `intent.restate-ask` x3, `intent.find-gaps` x3, `intent.fill-with-practice` x3, `check.adds-up` x3.
- Workbench steps (the thread's own log): 1. North: Signed the intent (ok; signed and sent to Build) | 2. North: Handed over to build (ok; handed to the data engineer) | 3. Span: Read the systems (ok; 5 systems, 0 questions assumed) | 4. Span: Read the sample files (ok; 15 files given to Span as samples) | 5. Span: Drafted and approved the design pack (ok; design pack approved) | 6. Flow: Read the dropped files (ok; 7 files read, 0 mappings proposed, 4 sources already in the office) | 7. Span: Applied your answers (ok; 1 answers applied) | 8. Flow: Accepted the mappings and loaded (ok; 2 files loaded) | 9. Flow: Ran on a copy (ok; ran on a copy) | 10. Span: Made sure each figure has a filled ready table (ok; all 3 figures have a ready table; 3 of 3 figures have rows) | 11. Flow: Compared with the report (ok; no check, by the person's choice) | 12. Flow: Went live (ok; live on daily at 06:00) | 13. Lumen: Built the starter board (ok; Lumen starter board accepted and published) | 14. Lumen: Wrote the morning note (ok; morning note written) | 15. Flow: Recorded the run on each figure (ok; run recorded on 3 figures).

**Model calls recorded for this case:** 11 (openai/gpt-oss-120b x11; tiers specialist x10, manager x1); estimated cost USD 0.0063. Source: `model_costs.jsonl`, rows with this thread's intent id.

### Live answer and its receipt

- **Check question (asked in Consume, as Mei Chen):** "What are we worth in the latest report?"
- **Answer word for word (Consume screen):** "The latest report (Evergreen_Office_Investment_Report_2026-09.xlsx, to 30 September 2026) gives a total of USD 57,600,000; SGD 77,253,120."
- **Heading on screen:** TOTAL IN THE LATEST REPORT · 30 SEPTEMBER 2026
- **Source line on screen:** Source: Evergreen_Office_Investment_Report_2026-09.xlsx · the report's Total, as issued
- **Same answer in the run report:** "The latest report (Evergreen_Office_Investment_Report_2026-09.xlsx, to 30 September 2026) gives a total of USD 57,600,000; SGD 77,253,120."
- **Screen timing:** Answered in 27 ms (from memory).
- **Check (numbers that must appear on screen):** 57,600,000; all present: yes.
- **Receipt (Where this number comes from):** no figure page on this answer; the receipt is the source line on screen ("Source: Evergreen_Office_Investment_Report_2026-09.xlsx · the report's Total, as issued").

### Left for the next ones

- Figures this case built that later cases used: none.
- Figures this case reused from earlier cases: none.

### Screens

- Thread page at live: `docs/v3/top10/shots/morning-networth-note-thread-live.png`
- Consume answer, with "Show the figures" opened: `docs/v3/top10/shots/morning-networth-note-consume-check.png`
- No figure page: this answer has no figure record (see the receipt above).

## Stage captures copied (viewport, 1440 x 900)

In `docs/v3/top10/stages/`: `uc-008-payrun` (decision1, decision2, decision3, live), `uc-016-schemadrift` (decision1, decision2, decision3, live), `morning-networth-note` (decision2, decision3, live). The morning note has no decision1 image: its stage captures start at drafting, then working, so there was nothing to copy for decision 1.

## Knowledge, once as Daniel Foo

- Lineage flow tab: `docs/v3/top10/shots/knowledge-lineage-flow.png`. Current Knowledge counts: 836 nodes and 1383 links; by kind: file 399, source 203, rule 66, figure 35, usecase 34, recipe 22, signal 22, decision 17, document 16, person 11, fund 8, entity 3. The Lineage flow tab shows files, sources, figures, use cases and people in columns, with the path of one chosen figure highlighted.
- Atlas: `docs/v3/top10/shots/knowledge-atlas.png`.

## How the office grew

Counts after each case, taken from the thread data in the order the cases ran: figures are the distinct figure records each case built or used, gold tables are the ready tables those figures were built on, skills are the distinct skill names run, and files is the office folder that case 1 recognised (708 files). The Knowledge page itself was counted once, at the end, see the line above; the office does not keep a count per case.

| After case | Figures in the office (distinct) | Gold tables built (cumulative) | Skill folders run (cumulative) | Per-kind readers run (cumulative) | Files in the office folder |
|---|---|---|---|---|---|
| 1. uc-001-noticelog | 5 | 4 | 21 | 65 | 708 |
| 2. uc-002-callrecord | 9 | 10 | 21 | 65 | 708 |
| 3. uc-004-callcheck | 12 | 13 | 21 | 65 | 708 |
| 4. uc-005-benefcheck | 15 | 18 | 21 | 65 | 708 |
| 5. uc-008-payrun | 21 | 20 | 21 | 65 | 708 |
| 6. uc-016-schemadrift | 25 | 27 | 21 | 65 | 708 |
| 7. uc2-recon-break-desk | 27 | 29 | 21 | 65 | 708 |
| 8. uc4-vs-benchmark | 28 | 30 | 21 | 65 | 708 |
| 9. uc5-limits | 32 | 36 | 21 | 65 | 708 |
| 10. morning-networth-note | 35 | 39 | 21 | 65 | 708 |

At the end: 35 figures in the office (the Knowledge page shows 35), 39 gold tables built by the ten cases, 21 distinct skills run; the skill folder holds 63 skills with a SKILL.md; these runs used 21 of them, and 65 per-kind file readers (data.read-<kind>) logged their own calls. The 12 family-office model objects hold the records below; the rows in them are the figures' inputs.

## What I could not find

- Decision-stage screenshots for the morning note: the stage captures in D:/Temp/sh3-top10/stages have no decision1 image for `morning-networth-note` (the drafting, working, decision2, decision3 and live images exist). Its decision 1 is described from the thread file.
- Stage captures: uc-001, uc-002 and uc-004 have only a live image in D:/Temp/sh3-top10/stages; uc-005 has working, decision3 and live. Those are not copied (only uc-008, uc-016 and the morning note were asked for); the thread files hold the history of all ten.
- Warehouse row counts were taken once, after all ten cases (model objects in /api/v3/model). The office did not keep row counts per case, so "tables loaded with row counts" is the current state, not the state at each run. The per-case file loads (files read, loaded, set aside) are in the workbench steps.
- Knowledge counts were taken once at the end. The per-case growth columns are rebuilt from the thread and figure data, not from a counter the office kept.
- Model calls: the cost log records model, tier, tokens and cost for each call with the thread intent id; it does not record which skill made each call, so model calls are shown per case, not per skill.
- "Cash drag" (morning note) has no recipe in the pack: Span designed its table, gold_..._net_worth_entity_monthly (21 rows). Check that design before relying on the figure.

