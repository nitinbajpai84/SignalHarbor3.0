# UC8 live run 2 report: do our trades agree with the administrator?

Run on 12 Oct 2026, port 8813. The clean environment is at `.sh-tmp/testenv/uc8-run2` (Option A: company, people, master data and core model only). Only Testing-mode models were used. Model spend was **USD 0.0082** over 22 calls (North on gpt-oss-120b and qwen3.7-flash, Span on gpt-oss-120b). The server was stopped at the end (PID 30600).

Runbook: `UC8-RUNBOOK.md`. Screenshots: `uc8-run2-shots/`. Scripts: `uc8-scripts/`.

## Verdict

**Blocked in Month 1, at "load the July files", step 13.** I went through intent, sign, design pack and pack approval with three workarounds. July's trades cannot get into the silver `transactions` table through any product path, and the trade check (`trade_vs_admin`) reads only that table. The check therefore reports 0 compared for every month. Months 2 to 4 were not attempted, because without a load path they would only repeat the empty check. Following Nitin's stop rule, I made one diagnosis and one workaround attempt, then stopped.

## Month-by-month

| Month | Intended | Done | Outcome | Who | Screenshot |
|---|---|---|---|---|---|
| Jul: intent | Mei writes it with North | 8 North turns, then accepts | Drafted, but not signable: North never wrote result, success or one benchmark (M1, M2) | Mei Chen | jul-01-mei-intent-drafted.png |
| Jul: fill (W1) | n/a | Mei edits result, success and why; Daniel types the missing benchmark figure | Signable | Mei, Daniel | (api/sow-after-fill.json) |
| Jul: sign | Sponsor signs | Signing page: "I have read all sections", then Sign intent | SIGNED v1 | Daniel Foo | jul-02-daniel-intent-signed.png |
| Jul: to Build | n/a | Send to Build | Project prj-44447baa | Mei Chen | jul-03-mei-sent-to-build.png |
| Jul: design pack | Span drafts pack, model extension | Sources confirmed, 6 questions answered, 3 samples (CSV, XLSX, PDF with 8 fields marked), pack generated | Pack v1: **0 gold, 0 silver tables**, 12 open rows (B2); no model extension proposed | Leo Park + Span | jul-05-leo-design-pack-drafted.png |
| Jul: pack approved (W2) | Head of data approves | Leo settles 20 rows with notes; Anita approves; plan drawn | Approved v1 | Anita Rao | jul-06-anita-pack-approved.png |
| Jul: plan (W3) | n/a | Plan proposed (Leo) and approved (Anita); builder started | Round **blocked**: 2 of 6 sources connected, 4 "need a sample" (North duplicates, FX PDF) | Leo, Anita | jul-09-leo-builder-on-copy.png |
| Jul: load + trade check | 4 compared, 4 matched | Trade check as at 31 Jul | **0 compared, 0 records each side**; silver.transactions 0 rows | Grace Ong (only person allowed) | jul-10-grace-trade-check-empty.png, jul-11-grace-map.png |
| Jul: benchmark, go-live, dashboard | | not reached | | | |
| Aug, Sep, Oct | | not attempted (B1) | | | |

## Did data flow bronze -> silver -> gold?

**No.**

- **Bronze:** the builder connected 2 bronze sources from the architecture samples (`trading_export_csv`, latest file `trading_export_20260706.csv`; `admin_monthly_excel_trad`, latest file `administrator_trade_confirmations_2026-07.xlsx`). It never ran a copy, because the round was blocked.
- **Silver:** `transactions` has 0 rows (Map > Data model API, `rows: 0, loaded: false`).
- **Gold:** none. The pack holds no gold table.
- **Operations > Runs:** only two `recon` runs, `run-20261012-115843-3b56` and `run-20261012-120119-4880`, both mode PRODUCTION, who "system", 0 seconds. No TEST run exists.

## Gold vs ANSWER-KEY

| Month | Answer key | Product |
|---|---|---|
| Jul (31 Jul) | compared 4, matched 4, breaks 0, net 0.00 USD | compared 0, matched 0, "Nothing was reported on either side" |
| Aug (31 Aug) | 4 / 3 / 1 timing, net 0 | not run |
| Sep (30 Sep) | 8 / 5 / 3, net 673,909.37 USD, excess 658,909.37 | not run |
| Oct (30 Oct) | 3 / 3 / 0 new; Harborview 592,000.00 carried | not run |

## Issues

| Id | Severity | Area | What | Evidence | Workaround |
|---|---|---|---|---|---|
| B1 | blocker | Load / silver model | No product path writes uploaded trade files to silver `transactions`, so the trade check can never see real trades. | (1) The intake loader `e0c_load._TABLES` (sh_platform/v1/e0c_load.py:37-42) covers positions, valuations, cash, NAV and market data only; `transactions` appears in no loader (grep: only e1_write, e1_asof, e3_recon, k4_office, n1_tally). (2) `GET /api/company/build/pipelines` returns `{"pipelines": []}` in a clean company. (3) The trade check `_trades` (e3_recon.py:374-385) reads `transactions` joined to source_systems with source_type administrator/OMS/trading; result `checked 0, records {trading export 0, administrator 0}`. | none; stopped |
| B2 | blocker | Span design pack | Span drafts no gold or silver tables and no model extension for FX confirmations. Every derived figure says "no table could be chosen". The pack edit cannot add a table (`ALLOWED`, b10_pack.py:961). | api/pack-v1.json: counts gold 0, silver 0, 12 open rows | Leo settled rows with notes (W2) |
| M1 | major | North | North says it "added the result description, success criteria" and "noted the page layout and success test" but writes no change. The intent stays unsignable. | Turns 6 and 8 in north_log.txt; api/sow-mei.json sign_block | Mei edits with the document's edit control (W1) |
| M2 | major | North | North loops: it asks for last month's figures in every turn after they were given (turns 4, 5, 6, 7, 8). It creates duplicate KPIs (Net break (USD) vs Net break in USD; Breaks above allowance vs Breaks above 5,000 USD allowance) and duplicate sources (6 sources for 3 real ones). | north_log.txt; api/arch-summary.json systems | Confirmed only 3 sources in Span |
| M3 | major | Rights | The business owner (Mei) is refused the benchmark sheet for her own intent (403 "company administrator or the data team or the sponsor"). | api/bench-sheet.json (first try) | Daniel typed the figure |
| M4 | major | Builder | The 3 unconfirmed duplicate sources still go into the approved pack and block the builder round ("Needs a sample", raised to administrator and Harbour Bank in Action). | jul-09-leo-builder-on-copy.png; api/builder-start.json | none |
| M5 | major | Rights | Trade check: Mei is told "Anita Rao or Leo Park or Grace Ong can", but Anita and Leo get 403 "Your access to the company's data is read-only". Only the company admin can run it. | api/jul-recon-empty-*.json; m1_rule.py output | Ran as Grace |
| M6 | major | Build flow | After the design pack is approved, the builder and Pipelines still say "The design pack is not approved yet". It needs a second propose and approve of the build plan, which no screen points to. | api/builder-get.json; b11_builder.pack_of (b11_builder.py:94) | plan/propose + plan/approve (W3) |
| M7 | major | Pipelines upload | The pipeline upload names the landed file with today's date (runner.py:303), so 23 daily CSVs uploaded on one day overwrite each other. | sh_platform/build/runner.py:301-303 | not reached |
| m1 | minor | Navigation | `/centre/intent/{iid}/charter` returns "We could not find that" for the sponsor. The real signing page is `/centre/intent/{iid}/sign`. | jul (look.py output) | used /sign |
| m2 | minor | Design pack | The pack can be approved while a figure (K07) shows "Needs a definition". Span's definition answer was not applied. | jul-06-anita-pack-approved.png | none |
| m3 | minor | Operations | Trade check runs are logged as PRODUCTION by "system", not by the person who pressed Run now. | api/ops-runs.json | none |
| m4 | minor | North speed | Each North turn took 57 to 146 s. | server.log "slow route ... chat took 121482 ms" | waited |

## Missing features (candid)

- A trade loader: a mapping from a trading export or an administrator trade file into silver `transactions`, with source_type trading/administrator. This is the core of UC8 and it is absent.
- A monthly multi-file intake: drop 23 daily CSVs plus 1 XLSX for a cycle in one action, with replace-or-append rules per business date.
- PDF confirmations as a monthly source: the OTC PDFs can only be marked once as an architecture sample; there is no monthly read of new confirmations into a table.
- An FX forward comparison on rate and SGD amount (rate vs rate), and conversion at the month-end spot named in the rule.
- A month-end trade check window. The check uses a fixed last-30-days window, not "the calendar month", and it cannot see amendment rows for earlier months (predictions P2 and P3).
- Break types (quantity / price / missing / timing) with "close as timing" for net-0 date differences.
- Span proposing gold tables for a reconciliation (trades_compared, breaks with type, USD difference, excess) and a silver extension for OTC confirmations.

## Recommendations (most valuable first)

1. Add a `transactions` target to the intake loader (e0c_load) with an approved mapping for the trading export and the administrator trade file. Without it UC8 cannot start.
2. Let Span's pack hold gold and silver tables for a reconciliation use case, or let the head of data add one in the pack. Otherwise the builder builds bronze only.
3. Make approving the pack also approve the plan, or point to the second approval on the screen.
4. Stop North from looping and from claiming writes it did not make: check its "I have added X" against the proposals it created.
5. Fix the rights wording for the trade check (who can run it), and let the business owner see her intent's benchmark sheet.
6. Give pipeline uploads a business-date name (or keep the original name), so daily files do not overwrite each other.
7. Add a month-end window to `trade_vs_admin` and FX rate comparison, then rerun UC8 Aug to Oct against the answer key.

## Honest opinion

A real family office could not run this monthly today. The front half works with effort:

- **Intent:** North captured the right sources, people, process steps and definitions in about 20 minutes. It then looped and needed hand edits before Daniel could sign.
- **Design pack:** Span read the samples and the PDF fields well, but produced a design with no tables, and two approvals plus 20 settled rows were needed to start a builder that then blocked.

The back half (landing a month of trades, matching them, raising breaks, people acting on them in Action, Consume) cannot be reached, because trades never reach the table the trade check reads. Month 1 cannot complete, so Months 2 to 4 cannot either. The trade check engine itself responds and enforces the signed 5,000 USD allowance. Once a trade loader exists, it is worth rerunning this runbook from step 13.
