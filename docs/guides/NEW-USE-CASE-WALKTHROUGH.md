# Add a new use case yourself: two worked examples (Evergreen Office)

Evergreen Office is a fictional family office and every figure here is synthetic (`docs/test/10UC-UNIVERSE.md`). This guide shows how a family office adds a new use case without a project team: you describe it to the agents in your own words, one named person approves at each gate, and the result ends up as a tile on a dashboard you share.

We tested it on 10 October 2026 through the real screens (1440 x 900) on a private copy of the demo data (test env `nu1`, port 8693), in **Testing** model mode. **Real use** mode was tried for one step of each use case. The raw record is in `docs/test-evidence/agents/new-uc/`: transcripts, agent traces, final state, the figures check and `tickets.json`.

**Second pass (reviewer).** The same steps were then followed from this guide on a fresh copy (`nu2`, port 8694, transcripts `RA-` and `RB-`, screens in `new-uc-shots/repro/`). Use case A reproduced to a shared tile that Daniel can open, with several differences that are marked **Reproduction** below. Use case B could not be repeated, because every model call failed after the first eight North turns (NU-28). The figures check was run again on the new copy and agrees with the first pass.

| | A. Manager reporting timeliness scorecard | B. Exposure by manager with limit headroom |
|---|---|---|
| Reached a shared tile? | **Yes.** Shared with Daniel Foo and Anita Rao; Daniel sees it under Consume > Shared with you | **No.** The intent was signed and the plan approved, but the trial run failed and Span could not repair the table |
| Figures correct? | **Partly.** Late days match the answer key for the three late statements. Revisions are also counted as late, missing statements do not show, and Fund A's revision is counted twice | Not shown in the product. Our own query of the same data gives the expected 56.50% for Cedarpoint (headroom -1.50 points) |
| Time | 43 minutes: intent 16, build 19, tile and share 6 | 50 minutes and no tile: a first intent thrown away (10), the second intent 11, build stopped after 29 |
| Problems found | 28 tickets across both use cases, 10 of them high (`tickets.json`; NU-24 to NU-28 came from the second pass) | |

---

## The pattern, in four steps

1. **Intent (you and North).** Type what you need in the box on the Intent page. North asks one question at a time and proposes lines for the *intent of work*. Say "yes" to accept them, or press **Not this** and say why. When North says it is ready, the **sponsor signs** and you press **Send to Build**.
2. **Build (Span and the head of data).** Press **Ask Span to propose a plan**, then tell Span which table you want in plain words. The **head of data approves the plan**. Press **Try it on a copy** (a sandbox run), then **Go live**.
3. **Consume (Lumen).** On the project's Consume page, ask Lumen for the tile in words, accept it, ask one follow-up, then tick the people and press **Share with these people**.
4. **Check.** The reader opens Consume > Shared with you. **Where is this from?** on a tile leads back to the gold table and its rows.

---

## A. Manager reporting timeliness scorecard

**Goal:** for each manager and month over the 13 months, statements expected and received, business days late and the number revised; a tile for Daniel Foo (CIO).

### A1. Intent with North (Mei Chen, 16 minutes, 21 turns)

| # | Mei typed | North replied (short) |
|---|---|---|
| 1 | *I want a manager reporting timeliness scorecard: for each manager and each month over the last 13 months, how many statements we expected and how many we received, how many business days late they were, and how many were revised. Daniel Foo, our CIO, should see it as a tile.* | "Will everyone in the company see this scorecard, or only a specific group of people?" |
| 2 | *Only the people I name: Daniel Foo, Mei Chen and Anita Rao. Yes to your proposal.* | "What decisions will Daniel Foo, you and Anita Rao make based on it?" |
| 3 | *Daniel decides which managers to chase or raise at the next manager meeting; Mei follows up late and missing statements; Anita checks the data is complete. We need it monthly, by the 12th business day after month end, when every statement should be in.* | Drafted readers, decisions and timing. "Can you walk me through the steps of how this is produced today?" |
| 4 | *Today: 1. Managers email their statements to Operations. 2. Mei logs each one in an Excel tracker ... 3. At month end Mei counts expected versus received and the business days late per manager. 4. Daniel reads the tracker before manager meetings. The statements are already loaded in Signal Harbor, in the manager statements data.* | Drafted 5 process steps. "What should the final scorecard look like?" |
| 5 | *One table, one row per manager and month ... statements expected ..., statements received, business days late (received date minus the due date, 10 business days after the period end, weekdays only, 0 if on time), and revised count ... A missing statement counts as expected but not received.* | Drafted the 4 figures with their definitions. "What are the sources for these figures, and who owns them?" |
| 6 | *One source: the manager statements already in the warehouse ... Mei Chen owns it. The list of funds ... is in the fund register, owned by Anita Rao. The signed rule statement_due says a statement is due 10 business days after the period end.* | Added the two sources and the rule. It also proposed "Excel tracker" and "Signal Harbor" as sources, which were wrong |
| 7 | *Not the Excel tracker and not 'Signal Harbor' as sources, please drop those two.* | "I have removed the Excel tracker and Signal Harbor", but the proposal was still waiting. **Mei pressed Not this, then Turn it down** (NU-02) |
| 8 | *Success: the figures match my tracker for the known cases, for example Kestrel Equity Long/Short August 2026 was 6 business days late, Saltmarsh June 2026 8 days late, Cedarpoint Opportunities II June 2026 missing, and three revised statements ...* | Noted success and that Anita Rao settles data questions |
| 9 | *All four figures come from the manager statements in the warehouse; expected also uses the fund register for each fund's frequency.* | "I've linked all four figures to the manager statements in the warehouse" |
| 10 | *Benchmarks, last period September 2026 across all managers: statements expected 9, received 7 ..., business days late 0, revised 1 (Fund A, Northgate) ...* | Put the figures on the benchmark sheet: "Anything to change? ... If not, press Hand to the architect." |

**Reproduction:** North's questions came in a different order the second time (access, then process, then figures, sources, success, benchmarks, manual changes), and the first turn failed once with "I could not reach the model just now"; typing a short "please go on" worked. The words above still led to the same result. About 16 minutes again.

The other turns were plain "yes" answers. Screens: `new-uc-shots/A-01-intent-box.png`, `A-03-north-audience.png`, `A-04-north-figures.png`, `A-06-north-ready.png`.

**Signature.** Daniel Foo opened **Sign the intent of work**, pressed **Sign**, then **Yes, I sign** (`A-07-daniel-signs.png`, `A-08-signed.png`). Mei pressed **Send to Build** (`A-09-sent-to-build.png`).

> **What went wrong here, and what a presenter should do:** at first the Sign button did not appear. The intent said "cannot be signed yet: For each figure, what you reported last period..." even though the benchmark sheet held the rows, and North answered "Done" without filling the section (NU-03). We filled the section through the intent's own edit route (`PUT /api/v1/intents/{id}/sow` with `{"section":"template_fields","field":"benchmarks","value":"<the September figures in one sentence>"}`). **Reproduction:** typing the four reported figures into the Benchmark sheet (project page, Benchmark sheet, **Save figure**) fills the sheet but does **not** unblock Sign, and asking North to "record the benchmarks so the intent can be signed" changed nothing; only the edit route did. The Sign button is not on the project page. Daniel finds it through the link **Sign the intent of work** on the intent page (it opens `/centre/intent/{id}/sow`), then **Sign**, then **Yes, I sign**. **Presenter:** before the demo, check that the intent page shows "Sign the intent of work". If it does not, fill that section first.

### A2. Build with Span (Mei asks, Anita Rao approves, 19 minutes)

1. Mei pressed **Ask Span to propose a plan**. The first plan held only two raw landing tables, waiting for files, and no gold table (`A-10-span-plan.png`, NU-08). **Reproduction:** the plan was different: two raw tables plus four gold tables built from the office's own report register (`reports`, `report_versions`), with no manager column and a "business days late" that only counts reports. The first plan is not stable, and those tables cannot be removed by talking to Span (NU-26). **Presenter:** do not rely on the first plan; go straight to the gold table you want. The leftover tables run green and later confuse Lumen.
2. Mei: *The manager statements are already in the warehouse, they are the valuation observations ... Please build from those and add the gold table for the scorecard ...*. Span: "I could not turn that into a table from what is loaded. Tell me the measure and what to group it by."
   **Reproduction, step 2:** Span answered "I will not follow the instruction to build from those ... Please confirm the name of the table" and then said valuation_observations "is not in the silver layer", although the table is there. Giving the join and the group-by in one sentence (the sentence in step 4 below, with *Please write the SQL on a single line* added) was what worked.
3. Mei: *Measure: count of statements, from valuation_observations. Group it by manager and by month of the valuation date ...*. Span: "I can add gold_manager_reporting_timeliness_s_statements_by_manager_month ..." **But the SQL took the company name as the manager** (NU-09).
4. Mei: *Why that join?* Span replied with a summary of the plan and did not explain the join (NU-10). Mei: *Not this: the manager is not the organization ...* and then *Add a gold table: count of statements from valuation_observations joined to instruments on instrument_id, grouped by instruments.manager_name and month of valuation_date ...*. The corrected table was proposed and **Mei pressed Accept** (`A-12-span-gold-proposal.png`).
   **Reproduction:** with the join named, the table took the manager from `instruments.manager_name`, correct first time. But Span said "I have drafted ... awaiting approval" when its tool had been refused and nothing was pending (NU-25); typing "Nothing was proposed yet, please propose it again" produced the Accept button. The table name must start with the project short name (`gold_manager_reporting_timeliness_s_...`): a name Span chose without it was accepted by Mei and then made **Approve the plan** fail with a 400 and no explanation (NU-24). Name the table in your sentence.
5. Mei: *Add the business-day count to the scorecard: for each manager and month, the total business days late, where a statement is due 10 business days after its valuation date ...* In Testing mode this failed twice (NU-11). **In Real use mode** Span replied "I can add gold_manager_reporting_timeliness_s_late_days_by_manager_month ... Due date is ten business days after the valuation date; late days are the weekdays after the due date up to and including the received date." (`A-13-span-real-use.png`). Mei accepted it. **Reproduction:** Testing mode refused again ("complex date arithmetic"), as before. Real use did not answer at all, because the model credit had run out (NU-28), so this step could not be repeated and the second-pass tile has no business-days figure. **Presenter:** check that Real use answers before the demo; without it the business-day count cannot be built.
6. A request to count *statements expected* (so that missing statements show) failed in Testing mode, so the scorecard has no "expected" column (NU-11).
7. **Anita Rao (head of data) pressed Approve the plan** (`A-14-anita-approves.png`). Mei pressed **Try it on a copy**: run ok, 57 rows in each gold table (`A-15-sandbox-run.png`). Then **Go live**: live run ok (`A-16-live.png`). **Reproduction:** same buttons, trial run ok and live run ok; the by-manager-and-month table had 57 rows (the four leftover tables hold 0 or 1 row each). About 21 minutes for the build, much of it spent on the points above.

### A3. Tile with Lumen and sharing (Mei, then Daniel, 6 minutes)

| Mei typed | Lumen replied |
|---|---|
| *Show the manager reporting scorecard for Daniel: per manager and month, statements received, business days late and revised statements, as a table.* | "I have proposed one tile, Business days late." Mei pressed **Accept** |
| *As bars of business days late per month, only Cedarpoint and Kestrel.* (the follow-up) | Bars per month, **but for all managers**: the filter was dropped (NU-17). Real use gave the same result |
| *superseded_statement_count per manager and month, as a table.* | "Superseded statement count" tile (Lumen accepts only the column name; NU-19) |
| *business_days_late by manager_name as bars* | "Business days late by manager name". Accepted |

**Reproduction (words that worked and failed):** the first ask picked the wrong table ("Statements received" by period, 1 row) because of the leftover tables, so Mei said *Not that one* and named the columns. *statement_count by manager_name as bars* got "I could not tell which figure you mean", while *statement count by manager name per month as bars* gave the tile "Statement count by manager name, per month" (stacked bars, 13 months, six managers; `repro/R-A-18-tile-accepted.png`). *As bars, only Cedarpoint and Kestrel* got "That is already how the tile looks": the filter is ignored (NU-17, NU-27). Asking for a table of revised counts produced the question "month, quarter, or year?" three times, so that tile was left out. Asking for the full 13 months turned into "the last 12 months" and was turned down.

Mei ticked **Daniel Foo** and **Anita Rao** and pressed **Share with these people** (`A-22-share-before.png`, `A-23-shared.png`). Daniel signed in, opened **Consume**, saw "Show the manager reporting scorecard for Daniel ... shared by Mei Chen ... 3 tiles" under **Shared with you** (`A-24-daniel-shared-with-you.png`), and opened it.

**Reproduction, final tile** (`repro/R-A-26-daniel-final.png`): statement count by month and manager, shared with Daniel and Anita; Daniel sees it under Consume > Shared with you (`repro/R-A-24-daniel-shared-with-you.png`). Time for the second pass: about 46 minutes from the first word to Daniel's screen (intent 17, build 21, tile and share 7), including the retries described above.

**Final tile** (`A-26-daniel-final.png`): business days late by month (bars: March 5, June 33, July 4, August 6) and by manager (Cedarpoint Ventures 30, Kestrel Ridge 10, Saltmarsh 8, others 0).

> **Presenter:** tiles that Lumen proposes as a *table* show as an empty white square (NU-18). Ask for **bars** or a **line**. Name the column ("business_days_late by manager_name as bars") so Lumen splits by manager, since it ignores "only Cedarpoint and Kestrel".

### A4. Figures check

We read a copy of the warehouse after the server stopped (`docs/test-evidence/agents/new-uc/figures_check.py`, results in `figures-check.json`).

| Check | Tile / gold | Source rows and answer key | Result |
|---|---|---|---|
| Gold equals a fresh count from the statements | per manager and month | recomputed from `valuation_observations` | **Equal** |
| P10 Kestrel Equity L/S Aug 2026 | 6 days | due 14 Sep, received 22 Sep: 6 | **Match** |
| P10 Saltmarsh Jun 2026 | 8 days | due 14 Jul, received 24 Jul: 8 | **Match** |
| P10 Cedarpoint Opportunities II Mar 2026 | 5 days | due 14 Apr, received 21 Apr: 5 | **Match** |
| Cedarpoint Jun 2026 | 25 days | the revised Ventures III statement arrived 18 Aug, after the 14 Jul due date; the answer key counts a revision as 0 days late | **Differs**: a revision counts as late |
| Kestrel Jul 2026 | 4 days | the revised Macro Fund statement arrived 20 Aug; answer key 0 | **Differs**, same reason |
| P11 Cedarpoint Opportunities II Jun 2026 missing | not shown | expected but never received | **Missing**: no "expected" column |
| P12 revised statements | Cedarpoint 1, Kestrel 1, Northgate 2 | 3 in all (A, C, H1) | **Northgate counts 2**: the Fund A amended statement is stored twice (pending and confirmed) |

**Second pass on the new copy** (`figures-check-nu2.txt`): the by-manager-and-month gold table equals a fresh count from the statements in all 57 rows (88 statements). Northgate September 2026 shows 3 statements and 2 revised, Cedarpoint June 1 and Kestrel July 1, so 4 revised against the 3 in P12. Cedarpoint Opportunities II has statements for September 2025, December 2025 and March 2026 only, so the missing June 2026 statement still does not show. The source rows give the same late days as above (Kestrel Aug 6, Saltmarsh Jun 8, Cedarpoint Opportunities II Mar 5, plus the two revisions at 25 and 4). The September 2026 count of 9 statements does not equal the benchmark Mei gave (received 7), because the table counts both stored copies of Fund A's amended statement.

**Verdict for A:** a tile was shared and Daniel can read it. The late days are right for first statements. To match the office's tracker, ask Span to (1) count late days only for the first statement of each period, (2) count a revision once per fund and period, and (3) add "expected" from each fund's frequency. Step (3) needs Real use mode (NU-11, NU-20).

---

## B. Exposure by manager across entities, with limit headroom

**Second pass:** only the first eight North turns could be repeated (the opening sentence, the 5th business day, the access rule, the process, the three figures and the source all drafted correctly, and naming Anita Rao in the access sentence put her in the access rule this time, which should avoid NU-16). Then every model call failed (NU-28), so the intent, the Span steps and the tile were not repeated. The first-pass record below stands, with the figures check re-run.

**Goal:** for each manager, the value held in each entity and its share of each portfolio, against the signed 55% single-manager limit, with the headroom; a tile for Daniel Foo and Raj Patel (Finance).

### B1. Intent with North (Mei Chen)

**First attempt, thrown away (10 minutes).** Mei gave the three figures in one long message. In Testing mode North's drafting tool was refused about 24 times. North then said "I could not reach the model just now, so this is a rules-only reply" and wrote sentence fragments into the intent as figures and sources: "The figures", "2.", "in percent.", "entity" and others. A figure Mei had turned down, "Single-issuer concentration", also came back (NU-06). Real use drafted the figures correctly (`B-05-north-real-use.png`), but North could not remove the junk lines, so Mei started again.

**Second attempt (11 minutes, 22 turns).** Short answers, one point each:

| Mei typed | North replied (short) |
|---|---|
| *Exposure by manager across entities with limit headroom: for each manager, the value we hold in each entity and its share of each portfolio, against the signed single-manager limit of 55%, with the headroom left. For Daniel Foo (CIO) and Raj Patel (Finance), as a tile.* | "When do you need this, and how often should it be updated?" |
| *Monthly, ready by the 5th business day after month end.* | Proposed the 5th business day. It also kept an earlier guess of the "eighth working day"; **Mei turned that down** |
| *Only the people I name: Daniel Foo, Raj Patel, Sofia Reyes and me. Sofia Reyes approves a change.* | Drafted the access rule and the approval rule |
| *Daniel decides whether to trim a manager; Raj checks headroom before funding a capital call.* | "What does the final report look like?" |
| *One table: one row per manager and portfolio, with the entity, the manager's value, its share of the portfolio in percent, the 55% limit and the headroom in percentage points.* | Drafted the result |
| *Three figures: manager value (latest known statement value of each of the manager's funds at month end, summed per portfolio); manager share (manager value divided by the portfolio total, in percent); headroom (55 minus the share, in points; negative is a breach).* | Drafted "Manager exposure headroom" with formula and unit (`B-04-north-figures.png`) |
| *The manager statements already in the warehouse (valuation observations, with funds, managers, portfolios and entities), owned by Mei Chen, arriving as managers report.* | Added the source |
| *Success: the tile matches our sheet. Last month, 30 Sep 2026, we reported Cedarpoint Ventures at 56.50% of the Entity B portfolio EG-B-OPS (12,925,000 of 22,875,000), headroom -1.50 points ...* | "Thank you for the benchmark figures", then "but not the figures yet" (NU-04) |
| *No documents. Today: 1. Mei exports holdings by portfolio into Excel. 2. ... 3. Sofia compares each share with the 55% limit. 4. Daniel and Raj read the sheet.* | Drafted 4 process steps |

North kept asking for the benchmark figures. **Mei opened the Benchmark sheet, typed -1.50 in "Reported figure" and pressed Save figure** (`B-07-benchmark-sheet.png`). The sheet also shows three garbled rows cut from her sentences (NU-05). After that North offered the hand-over (`B-06-north-ready.png`). **Daniel signed** (`B-08-daniel-signs.png`) and Mei pressed **Send to Build** (`B-09-sent-to-build.png`).

### B2. Build with Span (where it stopped, 29 minutes)

1. **Ask Span to propose a plan** gave one raw landing table and no gold table (`B-10-span-plan.png`).
2. Seven plain-word requests for the gold table failed with "I could not turn that into a table from what is loaded" (`B-11-span-talk.png`, `B-12-span-real-use.png`), in Testing and in Real use. The traces show why: Span's SQL trial tool refuses any SQL that has a line break (NU-12). It also cannot read the live project's gold table (NU-13).
3. Adding *Please write the SQL on a single line* worked: *Add a gold table by manager and portfolio: from valuation_observations joined to instruments, portfolios and legal_entities, take the latest valuation per instrument and portfolio with valuation_date up to 2026-09-30, sum value_amount per instruments.manager_name, portfolio_code and entity_name, plus the portfolio total of those latest values and the manager's share of it in percent. Please write the SQL on a single line.* Span: "I can add gold_exposure_by_manager_across_ent_summary." **Mei pressed Accept** (`B-13-span-gold-proposal.png`).
4. **Anita Rao could not open the project.** The intent's access rule named only Daniel, Raj, Sofia and Mei (NU-16). She pressed **Request access** (`B-14a-anita-requests-access.png`). The request reached Mei only as a comment, with no button to grant it, so Mei granted it through the project's access route. Anita then pressed **Approve the plan** (`B-14-anita-approves.png`).
5. **Try it on a copy: failed.** "Parser Error: syntax error at or near GROUP": Span had put the "latest per fund" filter in the wrong place (`B-15-sandbox-run.png`, NU-14). Note that **Go live** stayed enabled after the failed run (NU-23).
6. Mei: *The trial run failed: ... has a syntax error near GROUP. Please fix that table ...*. Span described the tables instead of fixing them. Four more requests to add a replacement table failed, in Testing and Real use (`B-16-span-fix.png`, NU-15).
7. In Consume, Lumen said: "This project has no gold tables yet. Once Build has run the pipeline, they will be listed here." (`B-17-lumen-tile.png`). There was no tile to share with Daniel and Raj.

### B3. What the tile should have shown (figures check)

From the same warehouse, latest known statement per fund at 30 Sep 2026 (`figures-check.json`, "B_reference"):

| Portfolio (entity) | Manager | Value USD | Portfolio total | Share | Headroom to 55% |
|---|---|---|---|---|---|
| EG-B-OPS (Entity B) | Cedarpoint Ventures | 12,925,000 | 22,875,000 | **56.50%** | **-1.50** (breach; P18) |
| EG-B-OPS (Entity B) | Saltmarsh Real Assets | 9,950,000 | 22,875,000 | 43.50% | 11.50 |
| EG-FUNDS (Family Trust) | Kestrel Ridge Advisors | 12,500,000 | 22,750,000 | 54.95% | 0.05 |
| EG-FUNDS (Family Trust) | Meridian Index Managers | 10,250,000 | 22,750,000 | 45.05% | 9.95 |
| EG-GROWTH (Holdings) | Northgate Partners | 10,180,000 | 16,580,000 | 61.40% | -6.40 (the signed limit covers EG-B-OPS only) |
| EG-GROWTH (Holdings) | Bluewater Capital | 6,400,000 | 16,580,000 | 38.60% | 16.40 |

**Second pass:** the same query on the new copy gives identical figures for all six manager rows, with Cedarpoint at 56.50% and headroom -1.50. The query also returns the liquid book (41,200,000, no manager, outside the single-manager limit), a row this table leaves out.

Cedarpoint's 56.50% agrees with the answer key (P18). The data supports the use case; the build step is what fails.

> **Presenter, for B:** do not demo B live yet. If you must: (1) name Anita Rao (head of data) in the team when North asks who may see the work; (2) switch to **Real use** for the figures turn; (3) give the source and the figures one point per message; (4) end each Span request with "write the SQL on a single line"; (5) if the trial run fails, stop and show the Limits page in Action > Reconciliations, which already shows the 56.50% breach with its cause.

---

## What happens under the hood

> **Intent → plan → bronze / silver / gold → tile → trail**
>
> 1. **Intent of work.** North turns the conversation into a signed document: goal, readers, figures and their definitions, sources and owners, rules, benchmarks. Nothing is built from an unsigned intent.
> 2. **Plan.** Span reads the signed intent and the warehouse model and drafts a build plan: which tables, the SQL for each, and what each reads. Any change sends the plan back to the head of data.
> 3. **Layers.** *Bronze* holds files as they land. *Silver* is the shared clean model; here the statements already sit there as `valuation_observations`, with instruments, portfolios and entities. *Gold* holds one table per tile, for example `gold_manager_reporting_timeliness_s_late_days_by_manager_month`. A trial run on a copy goes first, then the live run, then the schedule.
> 4. **Tile.** Lumen reads only gold tables. It proposes a tile (SQL plus a chart), you accept it, and sharing names the people who may open the dashboard.
> 5. **Trail.** Each tile has **Where is this from?** (gold table, then its SQL, then the source rows). Each agent turn is logged with a trace id (`/api/v1/agent-runs/trace/<id>`), and each approval and run is in the plan log with the person's name.

## Who approved what

| Gate | A | B |
|---|---|---|
| Intent signed (sponsor) | Daniel Foo | Daniel Foo |
| Sent to Build | Mei Chen | Mei Chen |
| Span's table changes accepted | Mei Chen (two tables) | Mei Chen (one table) |
| Plan approved (head of data) | Anita Rao, plan v3 | Anita Rao, plan v3, after access was granted by Mei Chen |
| Trial run / live run | Mei Chen: ok / ok | Mei Chen: failed / not run |
| Tiles accepted and shared | Mei Chen, shared with Daniel Foo and Anita Rao | none |

## Evidence

`docs/test-evidence/agents/new-uc/`: `A-transcript.json` and `B-transcript.json` (every POST the screens made, with what was sent and the reply), `traces.json` (100 agent loops with steps), `final-state.json` (intents, plans, runs, dashboards), `figures_check.py` and `figures-check.json`, `tickets.json` (28 tickets), `drivers/` (the Playwright scripts), and for the second pass `RA-transcript.json`, `RB-transcript.json`, `figures-check-nu2.txt` and the three `figures_check_nu2_*.py` scripts. The Playwright helper `pw.py` reads `NU_PORT`, `NU_ENV` and `NU_SHOTSUB` to run against another copy. Screens: `docs/guides/new-uc-shots/`.
