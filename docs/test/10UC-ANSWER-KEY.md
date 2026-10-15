# Evergreen Office: ten use case answer key (synthetic)

What the product must show, per use case, for the data made by `tools/seed_10uc.py` on top of `tools/seed_evergreen.py` and `tools/seed_v3_demo.py`.
Source of every entity, fund, identifier and figure: `docs/test/10uc_universe.json` (readable form `docs/test/10UC-UNIVERSE.md`). The figures below are
the ones the product's own functions return on the seeded data; `tests/v1/test_seed_10uc.py` asserts each of them (test names in the last column).
Where the product's arithmetic differs from the universe's, both are given and the difference is explained in "Where the product differs from the universe".

Demo window 9-14 Oct 2026: the inbox, the stale-data limit and the capital-call alerts use today's date, so from 15 Oct the Cedarpoint rows flip from Not due yet to late or missing, and from 4 Nov a second Finance case opens. Run the UI pages with the date set to 9 Oct for the figures below.

As of 9 Oct 2026, cutoff 9 Oct 2026 18:00 UTC. Money in USD unless stated. A person types dates the way the screens write them (14 Oct 2026).

## Make the data and sign in

```
python tools/seed_10uc.py --data-root <empty folder>          # about 25 seconds; run again and nothing changes
python tools/seed_10uc.py --data-root <folder> --hold-amended-a   # leaves Fund A's 7 Oct amended statement out, to drop the PDF in live
python tools/seed_10uc.py --data-root <folder> --reset        # rebuild the Evergreen warehouse (only on a root with no earlier one-month demo)
```

Never point it at the live `data/` root in a test. Passwords go to `<data-root>/_control/seed_credentials.txt` (never printed). Sign in as the company "evergreen".

| Person | Seat | Platform role | Use it to see |
|---|---|---|---|
| Daniel Foo | Chief Investment Officer | sponsor | Office view, CIO Brief, Managers (Consume), signed intent and SOP |
| Mei Chen | Operations analyst | analyst | Action (Today, Cases, Reconciliations, Managers), Evidence |
| Raj Patel | Finance | approver | Finance cases, liquidity, benchmark, rules |
| Sofia Reyes | Risk | participant | Limits and the limit cases |
| Anita Rao, Leo Park | Head of data, data engineer | analyst | Build, Map |
| Grace Ong | Company admin | company_admin | everything, Settings |

## What is in the warehouse

3 entities (Evergreen Holdings, Evergreen Family Trust, Entity B), 4 portfolios (EG-GROWTH, EG-LIQUID, EG-B-OPS, EG-FUNDS), 6 managers, 9 funds (5 private A to E,
2 hedge H1 and H2, 2 liquid L1 and L2), the Evergreen Liquid Book of 20 securities, 2 FX forwards, 10 signed rules, 5 commitments, 24 cash movements,
48 administrator NAVs (12 month ends by 4 portfolios), 329 valuations, 104 documents (87 manager statements, of which 85 back-dated and 2 that arrive live, and 17 notices), 12 library documents,
13 months of index levels and USD/SGD fixings, 13 trades (7 trading export, 6 administrator), 9 cases, the four-centre project with its gold tables and dashboard.

Consistency the seed enforces and the tests check: quantity times price equals value on every security line; the 20 lines of each month add to the book total;
each administrator NAV equals the holdings the product knew when it was struck, and the investment view known now equals the universe's, for all 48 NAVs;
calls never exceed commitments; benchmark returns are computed by `e3_calc` from the seeded index levels.

How the data got in. History to 3 Oct 2026 is back-dated (explicit `recorded_at`), with every statement and notice registered as a document and every value linked to
its document, page and line. What arrives after the 3 Oct report goes through the product's own writers, stamped now: Fund A's amended statement (`e2_extract.confirm`,
which opens the revision case), Fund E's Q3 statement (read, not confirmed), the October notices (`e2_extract.confirm` then `k6_liquidity.record_notice`), commitments
(`k6_liquidity.record_commitment`), trades (`e1_write.record_many`), the checks (`e3_recon.run_detail`) and the benchmark question (`k7_benchmark.certified_return`).

## UC1 P&L and NAV explanation

| Id | Planted fact | What the product shows | Screen, role | Verify (test) |
|---|---|---|---|---|
| P01 | September report as issued | A 10,000,000 (estimated), B 6,400,000, Evergreen Liquid Book 41,200,000, total 57,600,000; issued 3 Oct 2026 10:30 UTC (shown 18:30 in Singapore time), cutoff 3 Oct 10:00. In SGD at 1.3412: A 13,412,000.00, B 8,583,680.00, Evergreen Liquid Book 55,257,440.00, total 77,253,120.00 | Consume > Office view > Issued versus known now; CIO Brief (`/centre/consume/brief/<id>`); sponsor | `test_uc1_issued_report_and_what_is_known_now` |
| P02 | Fund A amended statement | Known now 10,180,000 (+180,000, +1.80%), received 7 Oct; total known now 57,780,000 (SGD 77,494,536.00); line status Revised; banner names the open case; one `revision` case for 180,000 (over 100,000 and over 0.5%) | same page; Action > Today (Revised) and Cases; sponsor | same |
| P03 | NAV bridge EG-GROWTH at 30 Sep | Investment view 16,580,000 against administrator NAV 16,400,000, difference 180,000: Revisions 180,000 (Evergreen Growth I), timing 0, exchange rates 0, unexplained 0 | Office view > NAV bridge (date 30 Sep 2026); sponsor | `test_uc1_the_nav_bridge_at_30_sep` |
| P04 | NAV bridge EG-B-OPS | 22,875,000 against 22,525,000, difference 350,000 shown as Revisions (Fund E's Q3 value of 9,950,000 was recorded 8 Oct, after the NAV of 2 Oct); timing 0, fx 0, unexplained 0 | same | same |
| P05 | NAV bridge EG-FUNDS | 22,750,000 against 22,550,000, difference 200,000 as Revisions: Kestrel Ridge Macro Fund 110,000 and Kestrel Ridge Equity Long/Short Fund 90,000 (September estimates received 6 and 7 Oct). EG-LIQUID: 41,200,000 against 41,200,000, nothing to explain | same | same |
| P06 | Why the liquid book moved Aug to Sep | 39,552,000 to 41,200,000, +1,648,000, return 4.1667%, no flows. Largest contributors from the monthly valuations: Northwind Logistics +132,000, Silverpine Software +130,400 | `e3_calc.portfolio_value`/`portfolio_return` on EG-LIQUID; the brief's Why did this move | `test_uc1_why_the_liquid_book_moved` |
| P07 | Holdings status words at 9 Oct | Evergreen Growth I Revised (10,180,000); Evergreen Income II Official; Cedarpoint Ventures III Stale (8,275,000, valued 30 Jun, 101 days); Cedarpoint Opportunities II Stale (4,650,000, valued 31 Mar, 192 days); Saltmarsh Infrastructure Fund II Unverified (9,950,000 read, not confirmed); both Kestrel funds Estimated (7,320,000 and 5,180,000); both Meridian index funds Official (6,150,000 and 4,100,000). Pacific Rim Convertible 2029 note (1,122,000) shows "Needs a class" | Office view > Holdings; analyst | `test_uc1_holdings_status_words` |

## UC2 Reconciliation and break desk

| Id | Planted fact | What the product shows | Screen, role | Verify |
|---|---|---|---|---|
| P08 | Entity B cash on 8 Oct | Administrator 880,400 against trading export 868,000, difference 12,400, over the 5,000 tolerance: one case "Cash differs · Entity B · 2026-10-08" for 12,400. Trust 1,150,000 against 1,148,200 (1,800, inside tolerance, no case). Holdings 2,300,000 in both views. The run records 3 checked, 1 break | Action > Reconciliations (Cash), Cases; analyst, approver | `test_uc2_entity_b_cash_break_and_no_case_for_the_trust` |
| P08b | The cause of the Entity B break | Tally ranks WIRE-20261008-B01 first: 12,400 USD, legal fees, Saltmarsh Infrastructure Fund II, paid to Lowmoor & Tasker LLP (synthetic), booked by the trading desk on 8 Oct (the bank paid it that day, 868,000) and by the administrator on 9 Oct: a timing difference that clears when the administrator books it. Behind it, 30 days of ordinary items (fees, coupons, FX settlements, sweeps), booked the same day on both sides, add up from the 8 Sep opening balances to every daily balance. The Trust's 1,800 is one charge booked by the trading desk only (CHG-20261006-T01) | Action > Cases > Cash differs · Entity B · 2026-10-08, the Tally panel; analyst | `test_uc2_p08b_cash_movements_add_up_and_tally_ranks_the_wire` |

Administrator cash is loaded for each of the 30 days to 8 Oct; trading-export cash for 1 to 8 Oct only (see differences, item 7).

## UC3 External manager information inbox (Action > Managers, `K5.inbox`)

| Id | Planted fact | What the product shows | Screen, role | Verify |
|---|---|---|---|---|
| P09 | September statements, due 14 Oct 2026 | 9 funds under 6 managers, one row each. Received: Evergreen Growth I 2 Oct (estimate; an amended one on 7 Oct), Evergreen Income II 1 Oct, Saltmarsh Fund II 8 Oct (value unverified), Kestrel Macro 6 Oct, Kestrel Equity L/S 7 Oct, both Meridian funds 1 Oct. Cedarpoint Ventures III and Opportunities II: Not due yet (quarterly, due 14 Oct) | Action > Managers; analyst | `test_uc3_september_statements_expected_against_received` |
| P10 | Late statements | Judged in the month they fell due (the Managers date set to that month): Kestrel Equity L/S August received 22 Sep, due 14 Sep, 6 business days late (date 23 Sep 2026); Saltmarsh Fund II June received 24 Jul, due 14 Jul, 8 days late (date 25 Jul); Cedarpoint Opportunities II March received 21 Apr, due 14 Apr, 5 days late (date 22 Apr) | Action > Managers > Received late; Consume > Managers > statements timeline | `test_uc3_late_statements_in_the_month_they_were_judged` |
| P11 | Missing statement | Cedarpoint Opportunities II, period 30 Jun 2026, due 14 Jul 2026, never received, 63 business days overdue at 9 Oct. "Draft a follow-up" gives subject "Statement request: 30 Jun 2026 (Cedarpoint Opportunities II)", body "Dear Hana Sato (Cedarpoint Ventures), ... due 14 Jul 2026, 63 business days overdue", `sent` false. The seed stores Hana Sato as an approved `manager_contact` identifier on Cedarpoint Ventures III (source "Manager contacts"), so the draft names her | Action > Managers > missing; Draft a follow-up; analyst | `test_uc3_the_missing_statement_and_the_follow_up_draft` |
| P12 | Three amended statements | Evergreen Growth I 30 Sep: 10,000,000 to 10,180,000 (+180,000, received and recorded 7 Oct; the superseded 2 Oct estimate keeps its page, line and 10,000,000); Cedarpoint Ventures III 30 Jun: 8,420,000 to 8,275,000 (-145,000, 18 Aug); Kestrel Macro 31 Jul: 7,050,000 to 7,012,500 (-37,500, 20 Aug; the amended statement is titled "KR Macro Fund Ltd - Class B USD - July 2026 - Amended NAV", the manager's name). Three documents replace the one before | Action > Managers > revised; Consume > Managers > timeline | `test_uc3_three_amended_statements_one_row_per_fund` |
| P13 | One fund under two names | "KR Macro Fund Ltd - Class B USD" and "Kestrel Ridge Macro Fund" resolve to one instrument (administrator code 4481); "Fund B - Evergreen Liquid Book" and "Evergreen Income II" to another (4472). The inbox never shows a fund twice | Action > Managers; Settings > identifiers | same |

## UC4 Certified reporting and benchmark factory

Benchmark EG-OFFICE-BLEND version 1 (approved, from 1 Jan 2026): equity index 0.42, bond index 0.28, equity index plus 300 bps a year 0.30 (the private-markets sleeve). Version 2 (0.36, 0.24, 0.40) is in progress.

| Id | Planted fact | What the product shows | Screen, role | Verify |
|---|---|---|---|---|
| P14 | September 2026 returns | Equity index 1038.22 to 1074.56 = 3.5002%; bond index 1037.07 to 1041.22 = 0.4002%; private sleeve 3.7502% (the spread is 300 bps a year, 25 bps a month, month-end to month-end). Decision: the seed keeps the universe figure; a reader that accrues the spread over 30 days (300 bps x 30/360, not 25 bps a month) gets 3.7466%, and a difference of 0.004 points on the sleeve is tolerated; blend v1 2.7072%; 60/40 liquid sleeve 2.2602%; EG-LIQUID portfolio 4.1667%; EG-LIQUID minus 60/40 1.9065 points; minus blend 1.4595 points. Certified true (approved definition, official values) | Consume tile "portfolio vs benchmark" (`GET /api/v1/benchmarks/comparison?portfolio=EG-LIQUID&code=EG-OFFICE-BLEND&start=2026-09&end=2026-09`: portfolio 4.1667, benchmark 2.7072, difference 1.4595, liquid sleeve 2.2602, difference 1.9065); Build plan table `gold_investment_report_benchmark_monthly`; approver | `test_uc4_benchmark_computed_from_the_seeded_index_levels`, `test_uc4_the_consume_route_reads_the_same_figures` |
| P15 | Version 2 in progress | `k7_benchmark.certified_return` for a period from 1 Oct refuses with "still being defined", and raises one `policy_question` case "Agree the definition of benchmark EG-OFFICE-BLEND"; version 1 still certifies September | Action > Cases (Policy question); Settings > Rules; approver | `test_uc4_version_two_is_in_progress_and_refused_for_certified_output` |
| P16 | SGD conversion | USD/SGD WMR 4pm: 30 Sep 1.3412, 8 Oct 1.3388 (9 Oct carries 8 Oct). 57,600,000 USD = 77,253,120.00 SGD | Office view USD/SGD switch; approver | `test_uc1_issued_report_and_what_is_known_now` |

## UC5 Allocation and limit monitoring (Action > Reconciliations > Limits, run on 9 Oct 2026)

Signed limits: Harborview Semiconductor 0 to 5% (EG-LIQUID); listed equity 60 to 90% (EG-LIQUID); manager Cedarpoint Ventures 0 to 55% (EG-B-OPS); hedge funds 20 to 60% (EG-FUNDS). The run records 13 checks, 2 breaks.

| Id | Planted fact | What the product shows | Screen, role | Verify |
|---|---|---|---|---|
| P17 | Real breach | Harborview Semiconductor 2,368,000 of 41,200,000 = 5.75% (case text "It is 5.75%, above the signed limit of 5.0%"), over 5% by 308,000; case `limit_breach`, cause "real breach", "All inputs are recent and verified" | Reconciliations > Limits; Cases; participant, analyst | `test_uc5_one_real_breach_one_caused_by_a_stale_valuation` |
| P18 | Breach caused by a stale valuation | Cedarpoint Ventures: Cedarpoint Ventures III 8,275,000 + Cedarpoint Opportunities II 4,650,000 = 12,925,000 of 22,875,000 = 56.50%, over 55% by 343,750; cause "stale data" ("3 input value(s) are older than 90 days or not yet verified": Fund D valued 31 Mar (192 days), Fund C valued 30 Jun (101 days), Fund E's 9,950,000 not confirmed) | same | same |
| P19 | Instrument without an asset class | Pacific Rim Convertible 2029 note: 1,122,000 = 2.72% of EG-LIQUID, asset class empty; the Limits run lists it under questions with the status "Needs a class", it is counted in no asset-class bucket, no breach, no case; Holdings shows the same words | Reconciliations > Limits; Office view > Holdings; Settings > instruments; participant | `test_uc5_limits_inside_range_and_the_instrument_without_a_class` |
| P20 | Within range | The run tests each rule against the portfolio it names: EG-LIQUID listed equity 33,210,500 = 80.61% against a maximum of 90%; EG-FUNDS hedge funds 12,500,000 = 54.95% against a maximum of 60%; one line per rule (4 compared), none for portfolios a rule does not name; no case | Reconciliations > Limits; participant | same |

## UC6 Private-asset liquidity and commitments (Office view > Liquidity, 9 Oct 2026)

| Id | Planted fact | What the product shows | Screen, role | Verify |
|---|---|---|---|---|
| P21 | Calls due within 30 days | Entity B, 30-day bucket: Cedarpoint Ventures III 450,000 due 20 Oct 2026 (notice 2 Oct, confirmed) and Saltmarsh Fund II 600,000 due 30 Oct (notice 6 Oct, noticed, not confirmed, listed under "Not confirmed yet"); calls 1,050,000 | Office view > Liquidity; approver | `test_uc6_calls_due_in_30_60_90_days_and_the_unconfirmed_one` |
| P22 | Entity B after-call cash | Available 880,400 (administrator, 8 Oct, official). After both noticed calls -169,600 (shown); after the confirmed call only 430,400. Finance case "Fund the capital call" opened for the Fund C call, 450,000, due 20 Oct, none for Fund E (not confirmed) | Office view > Liquidity; Action > Cases (Finance); approver | same; `test_uc6_the_finance_case_for_the_confirmed_call` |
| P23 | 60 and 90 days | Cedarpoint Opportunities II call 250,000 due 4 Dec 2026 (confirmed, 60-day bucket, Entity B); Evergreen Growth I distribution 320,000 expected 16 Nov 2026 (noticed, Evergreen Holdings). Trust: nothing due; cash 1,150,000; Holdings cash 2,300,000 | same | same |
| P24 | Commitments register | Committed, called, uncalled: A 15,000,000 / 11,250,000 / 3,750,000; B 8,000,000 / 7,200,000 / 800,000; E 10,000,000 / 4,000,000 / 6,000,000. C 6,000,000 / 4,050,000 / 1,950,000 and D 5,000,000 / 4,750,000 / 250,000: the product counts the October notices (450,000 and 250,000) as called once confirmed (the universe's register stops at 30 Sep: C 3,600,000 and D 4,500,000). Called never exceeds committed | Consume > Managers > profile; Liquidity; approver | `test_calls_never_exceed_commitments_and_match_the_register` |

## UC7 Manager diligence research workspace (Consume > Managers)

| Id | Planted fact | What the product shows | Screen, role | Verify |
|---|---|---|---|---|
| P25 | Newsletter team change | Library item "Kestrel Ridge Advisors Q3 2026 newsletter.pdf", dated 28 Sep 2026, under Kestrel Ridge Advisors; the passage says Thomas Lindqvist left the firm on 30 September 2026 and Priya Nair is sole portfolio manager of the Macro Fund from 1 October 2026; shown as a source chip; no judgement | Consume > Managers > Kestrel Ridge Advisors; sponsor, analyst | `test_uc7_what_changed_since_the_last_kestrel_meeting` |
| P26 | What changed since the last meeting (12 Jun 2026) | 13 dated items, newest first (the two 30 Sep valuation lines are counted): Macro Fund 31 Jul revised statement (20 Aug, 7,050,000 to 7,012,500); Equity L/S fund 31 Aug statement received 22 Sep (due 14 Sep); the newsletter (28 Sep) with its passage; the two September estimates (6 and 7 Oct) | "Show what changed"; sponsor | same |
| P27 | Cedarpoint Ventures profile | Funds Cedarpoint Ventures III and Opportunities II; commitments 6,000,000 and 5,000,000; Opportunities II last valued 31 Mar 2026, June statement missing; documents: the 19 May update call note and the DDQ (5 Mar 2026: quarterly statements within 45 days, 10 business days for Evergreen Office under its side letter, so the office rule and the DDQ agree; auditor change in Q2 2026); open question about the June statement; last meeting 19 May | Consume > Managers > Cedarpoint Ventures; sponsor, analyst | `test_uc7_the_cedarpoint_profile` |

Library: 6 meeting notes (also recorded as meetings on each manager), 2 DDQs, 2 newsletters/letters, 2 investment committee notes (17 Sep and 8 Oct 2026). Manager documents are Open to the office; the two committee notes are Internal, so a person other than Mei Chen must ask for access. Each item carries its own document date.

## UC8 Liquid and OTC trade and valuation control (Action > Reconciliations > Trades against the administrator, 9 Oct 2026)

13 trade records in the 30 days (7 from the trading export, 6 from the administrator, among them the FXF-2026-001 trade of 15 Sep); the run records 3 breaks.

| Id | Planted fact | What the product shows | Screen, role | Verify |
|---|---|---|---|---|
| P28 | Quantity mismatch | T-20261002-003 buy Northwind Logistics: trading export 12,000 at 42.15 = 505,800; administrator 10,200 = 429,930; difference 75,870 (1,800 shares); case "Trade differs · Northwind Logistics · 2026-10-02 · T-20261002-003" | Reconciliations; Cases; analyst | `test_uc8_three_trade_breaks_and_the_matches` |
| P29 | Missing at the administrator | T-20261006-005 sell 5,000 Harborview Semiconductor at 118.40 = 592,000: case "Trade not matched · Harborview Semiconductor · 2026-10-06 · T-20261006-005" | same | same |
| P30 | FX forward confirmation mismatch | FXF-2026-002 (sell USD 3,000,000, buy SGD): trading export SGD 4,027,500.00 (1.3425), administrator booked from the confirmation SGD 4,035,600.00 (1.3452); difference SGD 8,100 = USD 6,050.19 at 1.3388, over the 5,000 tolerance; case "Trade differs · FXF-2026-002 · 2026-10-05 · T-20261005-004". FXF-2026-001 (SGD 2,680,000 at 1.3400) matches | same | same |
| P31 | Matches | T-20261001-001, T-20261002-002, T-20261007-006 match on trade id and amount; no case | Reconciliations | same |

## UC9 Process map and SOP builder (Intent > signed intent "Monthly investment report in USD and SGD")

| Id | Planted fact | What the product shows | Screen, role | Verify |
|---|---|---|---|---|
| P32 | SOP from the signed process map | 6 steps with who, system, input, output, control, exception: 1 Collect the exports (Mei Chen, File drop), 2 Check cash against the administrator (Mei Chen, Excel), 3 Collect manager statements (Mei Chen, Email), 4 Convert to SGD (Raj Patel, Excel), 5 Review and approve the report (Raj Patel, Report pack), 6 Read the report (Daniel Foo, Report pack). Manual steps flagged for automation: 1, 2, 3, 4. Hand-overs 1-2, 2-3, 3-4, 4-5, 5-6. No "Not stated yet", no open points, no rule codes: controls and exceptions in plain words, step 5's exception names the CIO materiality threshold (100,000 USD or 0.5% of a fund). Step 2's exception names Entity B, 12,400 USD on 8 Oct 2026. The signed intent reads as finished: no required section left to fill in, North's conversation ends with the intent ready (no question waiting), and it reads "Sent to Build". Daniel Foo, Mei Chen, Raj Patel and Sofia Reyes can read it (Raj and Sofia are on the project team) | Intent > signed intent > Preview / Download the SOP (.docx if python-docx is installed, else .md); sponsor | `test_uc9_the_sop_from_the_signed_process_map` |

## UC10 Data pipeline and insight builder (Intent > Build > Consume)

| Id | Planted fact | What the product shows | Screen, role | Verify |
|---|---|---|---|---|
| P33 | Pipeline and dashboard | Project "Monthly investment report in USD and SGD", stage live; bronze_administrator_positions and bronze_trading_export_positions; gold_investment_report_holdings_monthly (13 months, each fund carried forward to the month end) gold_investment_report_cash_daily and gold_investment_report_benchmark_monthly (K04 Portfolio against benchmark: benchmark_code, month, portfolio_return, benchmark_return, difference; Span's benchmark rule); the gold tables depend on both bronze tables, so "Where is this from?" names them; dashboard dash-0ad2b1c7 with 3 accepted tiles shared with Daniel Foo and Raj Patel. K01 Net worth by entity (Sep 2026): Entity B 22,875,000; Evergreen Family Trust 63,950,000; Evergreen Holdings 16,580,000; total 103,405,000. K02 Cash by entity (8 Oct): administrator and trading export for each entity, 6 bars. K03 Holdings by status (note "Official, revised, estimated or unverified."): official 62,500,000; revised 18,455,000; estimated 12,500,000; unverified 9,950,000 | Intent > Build > Consume; analyst | `test_uc10_the_project_runs_through_build_and_consume_on_13_months` |

## Where the product differs from the universe (the key follows the product)

1. **Limits.** The limits are signed as the universe writes them, with their floors (listed equity 60 to 90, hedge funds 20 to 60) and their portfolio. The single-name rule is a cap on one named holding, Harborview Semiconductor at most 5% of EG-LIQUID, and Settings shows it in those words; the seed no longer rewrites it. The product also reads bucket "any" (or "*") as every holding, but a 5% cap on every line of this book would breach on eight: Harbour Treasury Note 2029 7.08%, Harborview Semiconductor 5.75%, Coastal Rail Holdings 5.64%, Larkspur Health 5.46%, Juniper Consumer Brands 5.38%, Evermore Banking Group 5.29%, Atlas Harbour Shipping 5.13%, Northwind Logistics 5.08%.
2. **NAV bridge labels.** The bridge calls a value recorded after the NAV was struck "Revisions"; "Timing" means a valuation dated after the NAV date. The universe now says the same (E, H1 and H2 are revisions, timing 0).
3. **Called and uncalled.** A confirmed notice counts as called the day it is confirmed (C 4,050,000, D 4,750,000), not at 30 Sep.
4. **Overdue calls.** The calls funded before 1 Oct 2026 (the opening balances and every notice of the 14 months) are seeded "paid", so the Overdue row is 0. They still count as called.
5. **The liquid book.** The 20 securities carry the value; the roll-up instrument "Evergreen Liquid Book" has the base seed's 41,200,000 position and, from 30 Sep, a 0 valuation so the portfolio is not counted twice. Its line shows 0.
6. **Cash.** `e3_calc.portfolio_value` counts trading-export cash as a holding, so the Office view lists a "Cash ... unverified" line per portfolio from 8 Oct, and trading-export cash is loaded only from 1 Oct (before that it would sit inside every NAV bridge). Run the bridge for 30 Sep.
7. **Fund statuses written by the base seed.** `seed_evergreen.py` wrote Fund B's 30 Sep value as "official"; the product reads "approved". The seed corrects that one value so Fund B reads Official, not Unverified.
7b. **Which side booked the wire first (P08b).** The DATA2 card asked for the administrator on 8 Oct and the trading desk on 9 Oct. The balances say the opposite: on 8 Oct the administrator (880,400) is 12,400 higher than the trading export (868,000) and the bank (868,000), so the outgoing wire is already in the trading export and the bank and not yet at the administrator. The universe books it trading desk and bank 8 Oct, administrator 9 Oct; every balance is unchanged. Cash movements are loaded for all 30 days on both sides (they are not holdings, so they do not touch the NAV bridge).
8. **FX forward marks** (the universe's mtm values) are not loaded: they are not in the 41,200,000.
9. **Source files.** The statement and notice PDFs under `tests/v1/fixtures/10uc/` put each label and its value on separate lines, which the rule-based reader in `e2_extract` cannot pair, and they carry no fund line it can match. The seed registers them as documents and writes the reading from the universe, located on the page and line of the PDF text; everything after the reading is the product's code. Meridian's two index funds have no PDFs in the fixtures, so the seed makes small ones.

## Roles and what they should not see

Everything above is visible to Daniel Foo, Mei Chen, Raj Patel and Sofia Reyes (with the screen limits in the next paragraph) (they are in the Investment office group, every entity, full access); Anita Rao and Leo Park (Data team, read) see the same figures read-only; the statement document type is open to both groups. The two investment committee notes are Internal: only Mei Chen reads them until she grants access.

Screen limits by role today: the approver (Raj Patel) gets 403 on the Library and on Pulse items (their permissions allow company_admin, sponsor and analyst only), and the case listing for Sofia (participant) shows 8 cases, not 9: the policy-question case 'Agree the definition of benchmark EG-OFFICE-BLEND' (P15) has no portfolio, so it is listed for the people who agree policy, the approver, analyst and sponsor roles (`POLICY_ROLES` in `sh_platform/v1/e4_cases.py`, a4.1), plus the company admin and the case owner. Raj Patel (approver), Grace Ong, Mei Chen and Daniel Foo see all 9. Check the Library and Pulse as company_admin or analyst.
