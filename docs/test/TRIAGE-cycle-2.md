# Triage, cycle 2 (10 Oct 2026)

113 tickets from 27 testers. About 70 distinct after merging. Rules answers (no model credit) were judged as rules; nothing was ticketed for the missing model.

## Pass or fail per use case

| UC | Figures vs key | Verdict | Blocking items |
|---|---|---|---|
| UC1 NAV explained | Match before 08:00 SGT | FAIL (sev 1) | Demo clock hides seeded rows after 00:00 UTC (UC1-C2-01); SGD errors and slowness; "Why did this move" missing on tiles |
| UC2 Reconciliation | All match | PASS on figures, FAIL on access (sev 2) | Data team (read) can take/dismiss/run (analyst-uc2-02); Tally misses payee (seed) |
| UC3 Managers | All match | FAIL on speed (sev 2) | Concurrent 500s and 18-35 s loads (AUC3-01/02) |
| UC4 Benchmark | All match | FAIL on speed (sev 2) | Statement list 55-85 s for approver/sponsor (analyst-uc4-01) |
| UC5 Limits | All match | PASS with sev 3 polish | Missing cause/amount on breach lines, case access for risk owner |
| UC6 Liquidity | Match before 08:00 SGT | FAIL (sev 1) | Same clock root cause (UC6-01, UC6-02); trail shows wrong source |
| UC7 Manager research | All match | FAIL on speed (sev 2) | 10-35 s manager pages |
| UC8 Trade control | All match | FAIL (sev 2) | Clock hides trades after 08:00 SGT; read-only team can run checks |
| UC9 Process map and SOP | P32 68/68 | PASS with sev 3-4 | Raw codes in intent, SOP panel, phone swim lane |
| UC10 Pipeline builder | Checker 6/6 | FAIL (sev 2) | Studio empty for non-makers, empty grid for published dashboard, Map fed-by empty, schedule not saved |
| Access / shell | Direct addresses refused | PASS | Tab row overflow at 390 px |
| Journeys uc1a/1b, 3a/3b, 4a, 5a, 6a, 7a, 9a | Pass | PASS | Script waits only |
| Journey uc10a | 4 of 11 fail | FAIL | UC10A-001..005 |
| Journey uc10b | Fails at Lumen tile | FAIL | UC10B-001, 002 |
| Journey mapa | 10/15 and 10/12 | FAIL | MAPA-01..04 |

## Root causes (one fix closes many tickets)

1. **Demo clock** `wh.now()` joins demo_today with the real time of day, so rows seeded at real 22:35 UTC count as future after 00:00 UTC; also thread-local `_CLOCK` makes "today" flip per thread. Verified in code (wh.py:152, k4_office.py:43 `_day`). Fix once: demo clock must be a fixed time of day (or end of demo_today), read from plane not thread. Closes UC1-C2-01, 05, UC6-01, 02, UC8-01.
2. **Warehouse connect/attach** conflicts (DuckDB file handle, memory limit, per-row connections) give 500s and 10-90 s loads. Closes AUC3-01/02, UC1-C2-03/04, UC6-04, UC7-01, UC7A-001, UC4-01, JUC1B-001, UC10B-002 (part).
3. **Comments not mounted** on case page and trail (CM1): UC2-05, UC5-05, UC6-05, UC8-08.
4. **Action tab row overflow** at 390 px: JA-001, UC2-04, AUC3-03, UC5-07.
5. **Read-only access** not checked on take/dismiss/run: analyst-uc2-02, UC8-02.
6. **Raw UTC / ISO dates and codes** across trail, comments, case titles.

## Rejected or merged

- UC2-10 and UC6A-001 (approver sees 9 cases): not a product bug. `POLICY_ROLES` in e4_cases.py:30 deliberately includes approver (a4.1). The answer key line 158 is stale; fix the key (checker package).
- analyst-uc2-07, UC8-07 (no-access page also says "not run yet"): merged, one fix in ReconPage.
- analyst-uc2-06 (approve without confirm/rationale): deferred, matches the verified demo click path; revisit with the product owner.
- UC1-C2-07 (two FX rates on one page): deferred as a note-only caption, S3 low value; fold into package 1 if time.
- UC9-11, JUC1B-003, UC6A-002, UC10B-003, JUC4A-01: journey, guide or key text; not product.
- MAPA-01 = UC10-04; MAPA-03 = UC10-01; UC10-02 = UC10A-004 area only partly; kept separate.
- UC10A-003 ("could not reach the model" with no rules answer): kept but S3; expected message is allowed, the missing rules reply is the defect.

## Packages (disjoint files)

### P1 Clock, office, daily numbers (S1)
Files: sh_platform/v1/wh.py, k4_office.py, k6_liquidity.py, k9_daily.py, e3_calc.py, e3_rules.py, e5_brief.py, ui/src/v1/k4/OfficePage.tsx, ui/src/v1/k9/DailyNumbers.tsx.
Tickets: UC1-C2-01..05, 07, 09, 10, 12, UC6-01, 02, 04, 06, 08, UC4-04, UC8-01, AUC3-01 (wh.py part), JUC1B-004 (Office button).

**Result (developer P1, 10 Oct):** fixed. Evidence: docs/test-evidence/cycle-2/dev-p1/result.md.
- Clock (`wh.now`): the clock starts at 23:00 UTC on demo_today and adds the real time since that day began, slowed 1000 times. It never jumps back at real midnight. The demo date is now process-wide instead of per thread. The uc1, uc4, uc6 and uc8 checkers pass at 08:5x Singapore, inside the old failure window.
- Attach conflict and slowness: test servers ran without server mode (the scheduler is off), so each call opened its own connection. A process that has imported uvicorn now uses the shared connection. Six Office routes in SGD at once all return 200 (8.8 s at most); daily SGD loads in under 9 s (it was 276 s). The cleaner switch, `wh.serve()` in app.py startup, is ticket DEVP1-01.
- Levers card: the liquid book's own split (USD price 1,648,000; SGD fx 613,880). Rate names, issue time and cutoff, stacked tables at phone width, "Return for Sep 2026", the Why-did-this-move link to the Office view, the empty notice sentence, two-decimal money, "Sep" and the no-lines sentence are in.
- Tests: pytest 76+2 on the package files; vitest k4 and k9, 21 tests. Outside P1: DEVP1-01..04 (app.py serve, the k4/api.ts formatters, the BriefPage heading, the e3_recon one-day wording).

### P2 Managers
Files: sh_platform/v1/k5_managers.py, k5_routes.py, ui/src/v1/k5/*.
Tickets: AUC3-02, 04, 05, 08, C2-UC7-01, 02, 08, UC7A-001, AUC3-01 (route part).

**Result (P2 developer, 10 Oct).** Backups: .sh-tmp/<file>.bak-c2fix. Confirmed on c2f2, port 8852: checkers UC3 P09-P13 PASS and UC7 P25-P27 PASS (docs/test-evidence/cycle-2/p2-managers/). pytest tests/v1/test_k5.py: 26 passed (4 new). vitest src/v1/k5: 15 passed (3 new). tsc is clean for k5. The UI needs the orchestrator's rebuild.
- AUC3-02, C2-UC7-01, UC7A-001 (speed), fixed at the root. A manager page used to work out every manager's inbox, with a warehouse read per fund (26 opens). Now `_find` works out only that manager, statements and values are read once per request, and 'what changed' skips commitments and the passage search. On 8852: inbox 0.09 s, Cedarpoint profile 0.27 s, Kestrel profile 0.33 s, changes 0.15-0.20 s (they were 5-35 s).
- AUC3-01 (route part), fixed. `k5_routes._run` tries a warehouse error (duckdb.Error, wh.Busy) once more, then answers a plain 503 "busy" instead of a bare 500. Each route reads before it writes its note, so a retry never writes twice. Probe: 6 people drafted and 6 opened Cedarpoint at once. All got 200 or a plain 403, and server.log has no errors. The wh.py race itself stays with P1.
- AUC3-04, fixed. Action > Managers has a "Judge as of" date and a "Back to today" button, and the follow-up draft uses the same day. At 20 Sep, Kestrel L/S shows Received 6 business days late.
- AUC3-05, fixed. Statement rows carry `value` and `revision {from,to,change}`. The inbox prints "Revised: <title>, revised from USD 10,000,000 to USD 10,180,000 (+180,000)". The timeline shows the manager's own title, for example "KR Macro Fund Ltd - Class B USD - July 2026 - Amended NAV", with old and new figures: Cedarpoint -145,000, Kestrel Macro -37,500.
- AUC3-08, partly fixed. The counts line now reads "0 late this month · 1 missing from earlier months". A draft for one statement says "the statement below" and "send it", and plural is used only for several statements. Not mine: the who_can_act 3-name cap (sh_platform/auth) and the "Fund D/Fund C" seed text (P6).
- C2-UC7-02, fixed. The Commitments table sits in its own horizontally scrolling box.
- C2-UC7-08, fixed. A 'Document added' chip links to /centre/library/view?file=<path>. A diligence document's kind is read from its name: meeting note, due diligence questionnaire, newsletter, letter, or else the library's word.
- For P6: tests/v1/test_seed_10uc.py::test_uc7_the_cedarpoint_profile fails because it still expects the old seed text "Fund D's 30 June..." while the seed now says "Cedarpoint Opportunities II's ...". This comes from the seed or test text, not from k5.

### P3 Evidence, benchmark, library
Files: sh_platform/v1/e2_screen.py, e2a_routes.py, ui/src/v1/e2/*, ui/src/v1/k7/*, sh_platform/v1/k7.permissions.yaml, ui/src/v1/l3/LibraryFolders.tsx.
Tickets: analyst-uc4-01, 02, 06, JUC4A-02, JUC1B-001, C2-UC7-05.

**P3 result (developer, 10 Oct).** Backups: .sh-tmp/*.bak-c2fix. Server 8853 on fresh c2f3 data, stopped after.
- analyst-uc4-01, JUC1B-001 (evidence part): fixed at the root in `e2_screen.can_see`. It opened the warehouse and recomputed E1d visible portfolios once per statement (104 statements); it now takes the `cache` it always declared, read once per list (holdings of every fund in one query, grants once). `detail` no longer lists documents twice. Raj list 6.7 s -> 0.6 s, Daniel 0.5 s, detail 1.0-1.6 s -> 0.3 s under five parallel calls; fail closed unchanged (sponsor with no grant sees none). Test: tests/v1/test_e2d.py::test_a_list_reads_the_viewers_portfolios_once_and_keeps_fail_closed (4/4 pass). Left over, not P3 files: GET /api/v1/cases/{id}/tally still 7.3 s for Daniel (a5_routes / n1_tally, P4).
- JUC4A-02: the screenshot shows a uuid in the typed box, so the holdings call had failed (server busy with the slow evidence lists). BenchmarkPage now shows a disabled picker "Loading the portfolios" until the list arrives, retries once, and falls back to the typed box only if both fail. Holdings answers Raj, Daniel, Sofia with the four portfolios (0.4 s).
- analyst-uc4-02: the month table sits in `.ds-table-wrap`, so it scrolls inside its box at 390 px, not the page.
- analyst-uc4-06: no product change. PF2 decided Consume for every role; roles.ts and tonight's ui/dist give the participant Consume in the bar, and k7.permissions.yaml (participant allowed) matches. The ticket ran on an older bundle; the guide line "Intent, Action, Map (no Consume)" and DEMO-GUIDE-10UC lines 67, 434, 459 are stale (cause checker-or-journey, for the guide owner).
- C2-UC7-05: LibraryFolders says on a 403 "The library is open to the sponsor, the analysts and the company administrator. Ask your company administrator if you need a document from it." (roles from c4.permissions.yaml); other errors keep the try-again words.
- Confirmed: checkers uc4 (P14-P16), uc1 (P05-P07), uc7 (P25-P27) all pass on 8853 (docs/test-evidence/cycle-2/fix-p3/checkers/). Vitest k7, l3, e2: 4 files, 20 tests pass; tsc clean for these files. UI needs the orchestrator rebuild. No browser screenshots: the session-cookie sign-in was refused by the permission classifier.

### P4 Cases, checks, Tally backend
Files: sh_platform/v1/e4_cases.py, e3_recon.py, e3b_routes.py, e3b.permissions.yaml, e4a.permissions.yaml, tally_tools.py, n1_tally.py.
Tickets: analyst-uc2-02, 03, 08, 01 (n1_tally reads description), 09 (proposal cites wire), UC5-C2-01 (backend), 03, 04, 08, 10, 11, analyst-uc8-02, 03, 04, UC1-C2-12 none.

**Result (P4 developer, 10 Oct).** Backups: .sh-tmp/<file>.bak-c2fix. Confirmed on c2f4, port 8854, freshly seeded with `make_test_env.py c2f4 --seed`. Checkers uc2 (9 pass, run again after CASE-0003 was resolved), uc5 (P17-P20 PASS) and uc8 (P28-P31 pass) are in docs/test-evidence/cycle-2/P4-fix/. The API probes are probe-*.json in the same folder. pytest: test_e3b 30 passed (2 new), test_e4a 16 passed (2 new). A wider run of 19 files (cases, recon, Tally, trail, comments, seed, checker tests): 290 passed and 1 error. The error is test_context_egress_shape::test_span_design, whose fixture copies the live data/ folder, which is locked; test_int4 errors the same way. Neither is affected by this change. vitest p5c2 and ReconPage: 7 passed.
- analyst-uc2-02, analyst-uc8-02: fixed at the root. Acting on a case now needs *full* access (E1d) to the case's portfolio as well as an acting role, so a read-only group sees the case and asks Tally but cannot act. `e4_cases._read_only` is used by every action and by `may`. Running a check needs full access to at least one portfolio (`e3b_routes._may_run`). On 8854, Anita and Leo get 403 "Your access to this portfolio is read-only..." on take and 403 on run, and every `may` flag is false. Mei can still take. **P5:** ReconPage `mayRun` still decides by role, so Run now still shows for Anita and Leo, and the server refuses the run with that message.
- analyst-uc2-03: fixed. When a resolved or dismissed case has the same title and the same size, the run reuses it and opens no new case. A break of a different size still opens a new case and names the earlier one (a8.5 kept). On 8854: take, submit, Raj approves, run again gives `opened: []`, and there is one Cash differs case (resolved).
- analyst-uc2-01 (read side): fixed. `n1_tally._about` reads the landed CSV row behind the source record (description, counterparty). The rules answer on 8854 is "Cash movement wire WIRE-20261008-B01: for Legal fees, Saltmarsh Infrastructure Fund II, paid to Lowmoor & Tasker LLP (synthetic)."
- analyst-uc2-09 (proposal part): fixed. The cash write-up sources now include the wire's chips after the balance rows. The chip labels ('Sheet1', 'trading_export') come from the seed and stay with **P6**.
- analyst-uc2-08: not in P4's files. The wording ("the data team", and the list of names) is built by the route guard in sh_platform/auth/__init__.py (ROLE_WORDS) → **P1/shell owner**. Read-only people no longer act, so they should not be named as people who can. That needs the guard to take E1d levels into account.
- UC5-C2-01 (backend): fixed. Each breached limit result now carries `cause` and `over_by` (for example "real breach", "308000.00" and "stale data", "343750.00"), and ReconPage already prints "Outside the limit; real breach, over by 308,000."
- UC5-C2-03: fixed. Tally passes the portfolio to the limit words, so it now reads "The Cedarpoint Ventures share of the Entity B operating portfolio must be at most 55%."
- UC5-C2-08: fixed for limit case titles, the limit description and the Where-is-this-from trail (owned by n1_tally.recon_trail). Titles read "... · 9 Oct 2026", and the trail reads "Limits check of 9 Oct 2026" and "known at 9 Oct 2026". Cash and trade titles keep ISO dates because uc2.py and tests/e2e_10uc match them → journey package, if wanted.
- UC5-C2-10: fixed. The description now says "3 input values are older..." and "above the signed maximum of 55%". The Tally input lines say "not yet verified" or "older than 90 days" instead of "stale".
- UC5-C2-11: not P4. FX forwards have no valuation, so they never reach the limits run. Either give them a class or a "not counted in limits" flag in the seed or Settings (**P6/P7**), or reword the Settings sentence.
- UC5-C2-04: no change; this is a decision. Sofia is a participant, and TD-01 (sev-1, A11) says a participant never acts on a case. Raj and Daniel have full access and acting roles, and the maker-checker rule needs someone other than the owner to dismiss. If Sofia should own limit cases, give her the `owner` role in the seed (**P6**), and the code then lets her act.
- analyst-uc8-03: fixed. Within a band, the case list now ranks cases by size in the materiality rule's currency, at the signed rate. On 8854 the High band reads CASE-0006 592,000, CASE-0001 180,000, CASE-0003 12,400, and the Low band puts Northwind 75,870 USD above FXF 8,100 SGD.
- analyst-uc8-04: fixed in P4's files. Trade lines say "FX forward" and the trail says "The trade check against the administrator for 9 Oct 2026, under the signed cash tolerance rule, version 1" and "the signed CIO materiality rule, version 1". Tally says "The FX forward FXF-2026-002 (trade T-20261005-004) on 5 Oct 2026". Cases already open in the golden root keep the old description until it is reseeded.
- Noticed outside P4: sh_platform/v1/b3_mapping.py and e2_extract.py contain literal backspace (\x08) characters, probably regexes that lost a `\b`. Worth a look.

### P5 Action Centre UI
Files: ui/src/v1/a5/ActionCentre.tsx, CaseView.tsx, ReconPage.tsx, ui/src/v1/e4/CasePage.tsx, ui/src/v1/a5trail/TrailPanel.tsx, TrailHost.tsx, ui/src/v1/n2/Comments.tsx, ui/src/styles/design.css, shell header (switch), cases table.
Tickets: JA-001, analyst-uc2-04, 05, 07, AUC3-03, UC5-C2-01 (UI), 02, 05, 06, 07, 09, UC6-05, UC6-03 (UI), analyst-uc8-05, 06, 07, 08, UC9-10, UC1-C2-08, MAPA-04, UC4-05.

**P5 result (10 Oct).** Vitest: new `ui/src/v1/a5/p5c2.test.tsx` 5/5; P5 folders plus e5, k5, cxui, router, design 88/88; full suite 1616/1618 (both failures are outside P5: b8 Pipelines, P7 in progress; k9 passes when rerun alone). tsc clean. Live API checked on c2f5 (port 8855, stopped). Backups: `.sh-tmp/p5.bak-c2fix/`. ui/dist not rebuilt.
- Phone width (JA-001, analyst-uc2-04, AUC3-03, UC5-C2-07, analyst-uc8-05): the Action tabs now wrap (ActionCentre.tsx). At 900px or narrower `.ds-frame__main` and `.ds-frame__aside` use `flex: 0 1 auto`, so the 560px basis no longer becomes an empty height. This fix is in design.css and covers every page. The cases table sits in `.ds-table-wrap` and scrolls inside its own box (CasesPage.tsx).
- Testing switch (UC9-10, and the switch part of uc2-04 and AUC3-03): a rule in design.css keeps the 38x22 track at 719px or narrower. An invisible `::after` ring keeps the 44px tap target.
- Comments (analyst-uc2-05, UC5-C2-05, UC6-05, analyst-uc8-08): CasePage.tsx shows `<Comments target={{kind:"case", id}} eager />` above History, on both /centre/desk and Action. TrailPanel.tsx shows the thread for the trail's kind and id under the steps (CM1 lines 5 and 6).
- Comment and trail times (UC1-C2-08, UC5-C2-06): Comments.tsx and TrailPanel.tsx now use `when` and `day` from design/dates, so times show in the company time zone (00:06 UTC now reads 10 Oct 2026, 08:06).
- MAPA-04: CaseView no longer puts the trail into CasePage through a DOM portal (MutationObserver). It no longer reads the case a second time. CasePage takes an `extra(c)` slot drawn above History, so "Where is this from?" and the evidence render whenever the case renders. The live trail for CASE-0001 loads (10,180,000 USD, was 10,000,000). Today stuck on "Loading today." is TodayPage (e5), which is not in P5.
- Policy question (analyst-uc4-05): the cases list has a Kind column and the case subline starts with the kind (Policy question, Limit breach, Difference, Capital call, Valuation difference). No kind filter was added.
- Reconciliations (analyst-uc2-07, analyst-uc8-07): when the runs cannot be read, the page shows only the server's sentence, with no "not run yet" cards. The owner getting 403 is a permissions question for P4/e3b.
- Limits card (UC5-C2-01 UI, UC5-C2-09): a breached line now ends "Outside the limit; real breach, over by 308,000." The separate cause lines are gone. Signed limits read "Signed limit:"; the other checks keep "Allowance:". **For P4:** the UI reads `results[i].cause` and `results[i].over_by` (plain digits) when e3_recon sends them. Until then it pairs `causes` with the breached lines in order, which is live today (2 and 2). "over by" shows only once `over_by` is sent.
- Card trails (UC5-C2-02, analyst-uc8-06): each line with a case has its own "Where is this from?" next to "Open the case". The card-level button shows only when no line names a case.
- UC6-03 (UI): nothing wrong in the UI. CaseView passes kind=case and the server id. On c2f5 the CASE-0002 trail is the 450,000 capital call, so the old valuation fallback is P6 backend and looks fixed there.

### P6 Trail wording and seed
Files: sh_platform/v1/a5_trail.py, a5_routes.py, tools/seed_10uc.py, tools/seed_evergreen.py, docs/test/make_10uc_universe.py, docs/test/10uc_universe.json, ui/src/v1/e3a/AdminRules.tsx.
Tickets: UC1-C2-06, 11, AUC3-06, C2-UC7-06, 07, JUC1B-002, UC6-03 (backend), UC6-07 (titles), UC10-05, analyst-uc2-01 (seed), 09 (labels), analyst-uc4-03, C2-UC7-03, 04, UC9-07, UC5-C2-11, JUC4A-01.

#### P6 result (10 Oct, developer)
Backups: `.sh-tmp/<file>.bak-c2fix`. Checked on a fresh seeded env (`make_test_env.py c2f6 --seed`, port 8856): all ten checkers pass (uc1 to uc10). Trail outputs from the live server are in docs/test-evidence/cycle-2/p6-fix/trail_live.txt. pytest: test_seed_10uc 52/52 (6 new `test_c2_*`), test_a5, test_aq1_shared_runtime, test_k4, test_k6, test_e3b, test_e0e and test_n2_comments pass. vitest src/v1/e3a: 2/2.
- UC1-C2-06, JUC1B-002 (a5_trail, seed): Stored now skips a confirmation that re-recorded the same value, so it reads "it replaced the earlier estimate of 10,000,000 USD recorded on 2 Oct 2026". Every date in step text uses the "7 Oct 2026" form. The Stored step is one sentence joined by semicolons, so "...2026-10-07. The issued..." no longer looks like a step "7." The seed dates the intake agent's run 10 minutes after the document arrived, so Read (7 Oct 17:10) now comes before Checked (7 Oct 18:30). Field names are plain words ("net asset value", not "nav").
- AUC3-06, C2-UC7-06, C2-UC7-07 (a5_trail): Used by now names (a) a manager or class limit case whose Tally inputs include the valuation, (b) "the Office view holdings, as the fund's current value" when it is the fund's latest value. Otherwise it says "Not in an issued report or an open case yet." A capital-call case is no longer shown against the fund's valuations. Cadence comes from the fund's statement periods (Cedarpoint quarterly, Kestrel monthly; a notice reads "when the manager sends a notice"). There are no table names any more ("Stored as a valuation, status approved"). A current value older than 90 days adds "so the screens mark it Stale". Checked reads "against the notice" for notices.
- UC6-03 backend (a5_trail): a capital-call case whose notice cannot be found shows "The call notice behind this case is not on file yet." It never falls back to the fund's last valuation.
- UC6-07 titles, UC1-C2-11 (seed_10uc): notice titles read "2 Oct 2026". A manager's own title that names another holding is not used as a title, so Fund B is "Evergreen Income II statement 30 Sep 2026 (final)". The "Evergreen Liquid Book" alias stays as an identifier for matching.
- UC5-C2-11 (universe, seed): FXF-2026-001/002 carry asset class `fx_forward`, so only the Pacific Rim note says "Needs a class".
- C2-UC7-03, 04 (universe, seed): the Kestrel 12 Jun note no longer mentions the August restatement. The Cedarpoint note and open question name Cedarpoint Ventures III and Cedarpoint Opportunities II.
- analyst-uc2-09 labels (seed): cash-movement batches read "cash movements <day> trading export". The proposal's sources (findings[:1]) are n1_tally, which is P4.
- analyst-uc2-01 (seed): no change needed. The seed already lands the trading-export CSV, and the wire's source record points at row 226, which holds description and counterparty. cash_movements has no such columns, and no column was invented. P4's n1_tally now reads the landed row: on this run Tally answers "for Legal fees, Saltmarsh Infrastructure Fund II, paid to Lowmoor & Tasker LLP (synthetic)". That leaves P4's old assertions stale: test_tally_trail_c1::test_a2_1_a2_5 still expects "cannot tell", and 3 test_n1_tally wording tests fail on P4's in-flight wording. P4 should update them.
- analyst-uc4-03 (AdminRules.tsx): benchmark_definitions has no owner column, so no owner is invented. The Owner cell for a benchmark reads "Each version is signed by a second person, named beside it". The approver is already named in the text ("approved by Daniel Foo"). Needs a UI rebuild.
- Outside the listed files (small, nobody else had claimed them):
  - tools/seed_v3_demo.py: UC10-05 maps the gold cash table's view to "administrator" and "trading export", so the legend reads that way. UC9-07 changes North's closing line to "Daniel Foo signed it and sent it to Build; nothing is waiting here."
  - tools/verify_10uc/uc7.py: P27 now looks for "Cedarpoint Opportunities II" instead of "Fund D".
  - Tests changed to match: test_seed_10uc (tile "administrator", question text), test_n1_tally line 95 ("trading export"), test_tally_trail_c1 ("notice 2 Oct 2026"), e3a.test.tsx.
- JUC4A-01: not changed. The seeded plan must stay Live, because UC10 (P33, checker 6/6) and the dashboard depend on it, and seeding it as "waiting" would break UC10. The guide and journey should describe the seeded state; that belongs to the journey package. Its guide line 308 also still quotes "Fund D's 30 June 2026 statement".
- Golden root: `.sh-tmp/golden/data` was seeded before these changes. Run `python tools/make_test_env.py --golden`, or `make_test_env.py <id> --seed`, before the next tester round, or the seed fixes will not show.

### P7 Map, dashboards, Build
Files: sh_platform/v1/k3_map.py, cx_dash.py, b7_studio.py, ui/src/v1/b7/*, ui/src/v1/b8/*, ui/src/v1/b6/*, ui/src/v1/cxui/*, ui/src/v1/s1/SettingsPage.tsx.
Tickets: UC10-01, 02, 03, 04, 06, 07, 08, 09, MAPA-01, 02, 03, UC10A-004, 005, UC10B-004, AUC3-07.

**Result (P7, 10 Oct).** Backups: `.sh-tmp/k3_map.py.bak-c2fix`, `b7_studio.py.bak-c2fix`, `cx_dash.py.bak-c2fix` (unchanged), `SettingsPage.tsx.bak-c2fix`, `ui-p7.bak-c2fix.tar` (b6, b7, b8, cxui).
- UC10-01, MAPA-03 (fixed, k3_map): the lineage runs bronze -> position_snapshots -> gold, and position_snapshots is not drawn, so no edge reached gold. `flow` now joins each drawn table to the nearest drawn tables upstream through tables it does not draw. Holdings monthly and cash daily now read "Fed by Administrator positions, Trading export positions", which matches the trail. Benchmark monthly is still fed by nothing: its lineage has no bronze table. No Company model column is drawn, because the plan has no silver table of its own.
- MAPA-02 (fixed, k3_map): the seed loads straight into the warehouse and leaves no landing records, so no Files box was drawn. A source with batches but no landing records now gets a Files box: "N files", last load = newest batch load, not-accepted count. The raw table takes its last load from that box. Fund administrator -> Files from Fund administrator, last load 9 Oct 2026.
- MAPA-01, UC10-04 (Map part fixed, k3_map): the data team now sees every published dashboard on the Map (K1, every layer), even when it is not in the audience. A personal draft or a never-published draft still shows only to whoever `may_view` allows. Anyone outside the team still sees only what `may_view` allows. The owner shows as a name, never an account id. Not changed: Consume access for Anita. DS1 audience rule: the head of data reaches the dashboard through Build (studio, approver), not Consume. Widening Consume is an access decision for the product owner.
- UC10-06 (fixed): the Map box note is now the dashboard header's sentence (`b7_studio.schedule_words` of the project plan), for example "Updated daily at 06:00 after the pipeline run". The Share panel in Consume says "Refresh: with each pipeline run" (cxui/ProjectPage).
- UC10-02, UC10-03 (already fixed by OP1, confirmed): the tester's server (c2a10, log ends 07:54) ran before OP1 `adopt` landed (b7_studio 08:29). On a fresh c2f7, Anita, Mei, Grace and Leo all list "Monthly investment report in USD and SGD": published, version 1, 3 widgets. Grace's studio opens with the 3 accepted tiles on the grid.
- UC10-07 (fixed): `listing` returns `made_by` (the maker's name) and `approved_by` (None for a dashboard adopted from before approvals). The Dashboards room reads "made by Leo Park · published before approvals were needed". The per-dashboard `getStudio` calls are gone.
- UC10A-004 (partly fixed): the Build Centre list and the room picker show the title only, and search is by title. Still open, outside P7: the Build page plan diagram prints "prj-30b9332c · plan v1" in its SVG header (`ui/src/v1/b6diagram/PlanDiagram.tsx:47`). One-line fix: drop `{data.project_id} · `.
- UC10A-005 (fixed, root cause): the backend saves the schedule (PUT then GET: monthly 07:00). The fault was in `Pipeline` (b6/Steps.tsx): it reset the unsaved form whenever the plan was fetched again. That happens while a go-live run is polled, so "Save the schedule" sent daily 06:00. The reset now depends on the values (freq, at, day), not the object. The vitest fails on the old code and passes on the new.
- UC10B-004 (fixed): before the first answer, ProjectPage now shows "Opening the figures." and no longer says "This project has no figures yet" or "No dashboard has been published".
- UC10-09 (Shared with you part fixed): ProjectList shows `day()` in company time, so 2026-10-09T22:36Z reads 10 Oct 2026. The company reports title uses the same. The trail dates (a5_trail, P6) and comment dates (n2/Comments, P5) are not P7 files.
- AUC3-07 (UI half): Settings > Identifiers shows a "Follow-ups go to" column once `/api/v1/instruments` sends `contacts`. Still open, outside P7: `e2c_routes.instrument_list` drops `manager_contact` rows on purpose ("a contact is a person"). It should put them in `contacts` instead of skipping them.
- UC10-08 (not fixed, outside P7): the rules reply comes from `talk.span_company` (sh_platform/v1/talk.py), which no package owns. Suggested fix at its top: a change verb (drop, delete, truncate, rename, alter) answers "I can't drop or change tables here. Ask for a change in the project's Build chat; the head of data approves it."
- Confirmed on 8857, fresh c2f7: journey mapa_1 15/15 (was 10/15). mapa_2 11/12; its only fail is step 10, MAPA-04, which is P5. Checker uc10 6/6. Evidence: `docs/test-evidence/cycle-2/P7-fix/`. pytest test_k3, test_b7_studio, test_cx*: 87 passed (new: `test_cycle2_raw_feeds_ready...`, `test_listing_names_the_maker...`). Vitest b6, b7, b8, cxui, s1: 70 passed. tsc clean. The UI needs the orchestrator rebuild before the uc10a and uc10b journeys are re-run.

### P8 Intent, SOP, Lumen
Files: ui/src/v1/i6/*, ui/src/intents/*, sh_platform/v1/i4_sow.py, k8_sop.py, cx_lumen.py, ui/src/v1/g1/ProjectAccess.tsx, ui/src/modules/m2_baseline/copy.ts.
Tickets: UC9-01..06, 08, 09, UC10A-001, 002, 003, UC10B-001, 002.

**P8 result (developer, 10 Oct).** Backups: `.sh-tmp/p8.bak-c2fix/`. Server 8858 on fresh c2f8 data, stopped after. pytest test_cx, test_lumen_aq1, test_lumen_loop, test_b7_studio: 112 passed. test_k8: 7 passed (2 new). i4, int4, p1, p7_cycle1, seed_10uc and t1: 66 passed. 12 errors come from fixtures that copy `data/neera`, which is locked by the live server; they are not from these changes. vitest i6, g1, process_map and workbench: 43 passed (4 new, one new file `i6.access.test.tsx`). tsc is clean for these files. The UI needs the orchestrator's rebuild.
- UC9-01, fixed. SopPanel scrolls the procedure heading into view once it loads.
- UC9-05, fixed. The in-page procedure now shows Scope, Systems, Manual steps flagged (named), Controls, Definitions and Open points ("None" when empty), the same sections as the file.
- UC9-02, fixed. The phone process map shows each step's system, what is done and its hand-overs. The step button is a block, so the number stays beside the name.
- UC9-06, fixed. The legend reads "Manual step" / "Not flagged for automation", in i6 Swimlane and in m2_baseline copy.ts `legendSystem`.
- UC9-03, fixed at the root in `i4_sow._blocks`. The project page, intent download and build pack all read these lines. KPI codes are gone, sources and feeds use their names ("Sources: Fund administrator export, Manager statements by email."; "feeds Net worth by entity, ..."), and every sentence ends with one full stop. A catalogue row reads "**Administrator positions** (landing table administrator_positions)". Confirmed on 8858 through GET /api/v1/projects/prj-30b9332c/artefacts/intent.
- UC9-04, fixed in SOP .md/.docx and project page 6.1. A control reads "Access: Only the investment office sees entity figures." (new `i4_sow.kind_word`, used by k8_sop). The manual steps are named ("1. Collect the exports"). **Not mine, still open:** the intent page's T1 layout prints the raw key at `sh_platform/v1/t1_layout.py` L62 (`f"{r.get('kind')}: ..."`). It needs `from sh_platform.v1.i4_sow import kind_word` and `kind_word(r.get('kind'))`.
- UC9-08, fixed. The Internal and Restricted lines say "Only the team and company administrators can read this project." This matches `g1_access.level`. g1.test.tsx was updated to match.
- UC9-09, fixed. ConversationPage calls the context library only for the roles c4.permissions.yaml allows (company_admin, sponsor, analyst). Raj and Sofia now get no /context call and no 403. Confirmed against the API: Raj and Sofia got 403 and Daniel got 200 before the change. The new vitest checks that no /context call is made.
- UC10B-001, fixed in `cx_lumen`. A request for passwords, sign-in details, the access list, a users table or people's emails or phones is refused before the rules or the model run. The reply never uses the word "password", proposes no tile and names the figures it can chart. `is_question` counts such a request as words, so Consume refuses it rather than pointing to the studio. Confirmed on 8858 through the studio and consume routes. In journey uc10b_2, step 08 (the passwords ask) passes. Step 07 failed only because the persisted talk from earlier runs on the same data holds the passwords ask, and the check strips only the current ask (checker-or-journey, the same family as UC10B-003). Steps 01 and 03 (view link) are not P8.
- UC10B-002, not reproduced in isolation and not fixable in P8 files. On a quiet server, rules asks take 0.3-1.8 s. The first ask after a start or after the 300 s breaker window takes 5-14 s. A cProfile of `cx_lumen.ask` shows where the time goes: router.complete 8.7 s for two no-credit model attempts. Inside that, the egress vault's file lock (`egress/vault.py` `_read_lock`/`_release`) takes 4.2 s in 239 lock reads, `ssl load_verify_locations` takes 1.9 s per transport, and mem_graph.search/doc_embed takes 2 s. The 34-58 s in the ticket is that cost under parallel journeys (lock contention). Suggested owner: egress (cache the SSL context in `egress/providers` transport; take the vault lock once per prepare, not per string) and router (open the breaker for every tier of a provider on its first no_credit).
- UC10A-003, already resolved on the current i6_chat.py, which changed after the test. Mei now gets "North (rules only)", the line "The assistant is offline for now; keep typing, your words are kept." and the next question. No change in P8.
- UC10A-001 and UC10A-002, not fixable in P8 files; they are blocked. The rules answer lives in `sh_platform/v1/i6_chat.py` `fallback()` and `i2_north._fallback()`, and neither file is on this package's list. `fallback` fills only the one goal North asked last. `i2_north._fallback('goal')` drops "needs it by the 3rd business day" (`needed_by: ''`). `_fallback('process')` turns "Step 1: Collect the exports, done by Mei Chen in File drop." into who='Step' and system='' (checked by direct call). Fix for the owner of i6_chat and i2_north:
  1. In `fallback`, also read `needed_by` from any message (`by the <Nth> business|working day ...`).
  2. Read a "Step N: <name>, done by <who> in <system>." list as process steps whatever goal was asked, and mark `process` covered.
  3. Fix the `_fallback('process')` pattern for "done by X in Y".

### Journey and checker scripts (one package)
Files: tests/e2e_10uc/*, docs/guides/DEMO-GUIDE-10UC.md, docs/test/10UC-ANSWER-KEY.md.
Tickets: UC2-10 and UC6A-001 (correct key line 158), UC9-11, UC6A-002, UC10B-003, JUC1B-003, JUC4A-01 (guide).

**Result (10 Oct, journey-fix):** all seven fixed; evidence `docs/test-evidence/cycle-2/journey-fix/` (result.md, tickets.json). Run on fresh c2f9, port 8859 (stopped), serving a scratch build of the current UI source:
- UC2-10, UC6A-001: key line 158 now says Sofia sees 8 and Raj (approver, in `POLICY_ROLES`), Grace, Mei, Daniel see 9.
- UC6A-002: entity-code regex `\bEG-[A-Z]+\b(?!-)` in uc6a_1 and uc6a_2 (same bug in both). Both PASS.
- JUC1B-003: uc1b_2 step 7 checks the Brief button sits on the changed Fund A line, not on the unchanged liquid book. Rows are now matched by their first cell, because the old `has_text` locator could match the wrong row and pass. Guide UC1 step 6 updated. uc1b_2 exit 0.
- UC10B-003: the root cause was OP1, which moved tile building to Build > Dashboard studio, so Consume accepts get a 409. uc10b_1 now does propose, Accept and Submit as Leo, then Approve and publish as Anita, then share, then Daniel and Raj see the tile. It is rerun-safe: 12/12 on the 4th run on the same data. Guide UC4/UC10 and the agent tables updated.
- UC9-11: guide says the SOP downloads as .docx.
- JUC4A-01: guide says the seeded plan is Live and approved by Anita Rao, and to show approval on the dashboard studio. uc4a_1 8/8.
- New: JFIX-02 (sev 2): ui/dist (08:25) predates the OP1 source (08:36 to 08:52). Its studio has no Talk to Lumen, while the server already refuses Consume accepts, so it needs a rebuild. JFIX-01 (seed, sev 3): the seeded dashboard reads "made by f6e3ecb1..." and "approved by the approver" in Build.
- Left open: uc1b_2 step 8 (info only) uses the pre-OP1 "Dashboards of" section. uc4-06 (Sofia's Consume in guide lines 67, 435, 459) was not in this ticket list and was not checked.

Cross-package notes: P4 and P6 both touch the Tally cash wire chain (P6 seed adds description/counterparty, P4 reads it). P5 owns TrailPanel layout and comments; P6 owns trail order in a5_trail.py, so P5 must not reorder.

### P5 Review (10 Oct)
Reran a5, a5trail, n2, e4 vitest 38/38 and tsc clean. Fixes sit in shared spots (design.css, CasePage extra slot, Comments, dates helper), so sibling pages are covered. Two notes: trail steps show the date only in company zone (day()), not the time; "over by" and the pairing of causes by order rely on P4 sending cause/over_by. No code changes made. Verdict: accept.

### P3 Review (10 Oct)
Reran test_e2d (4 passed) and vitest k7, l3, e2 (20 passed). Slow-statement fix is at the shared point: can_see caches grants and holdings once per list (rows); single-doc callers (check, a5_trail, e2a_routes) compute once, so no sibling still loops. Cache is per call and per viewer, fail-closed kept. Notes: uc4-06 is a guide fix (DEMO-GUIDE-10UC.md lines 67, 434, 459 still say Sofia has no Consume), already in the journey/guide package; Tally 7.3 s for Daniel is P4's; no browser screenshots, so BenchmarkPage picker and 390 px scroll are unit-verified only. No code changes made. Verdict: accept.

### P2 Review (10 Oct)
Verdict: ACCEPT. pytest test_k5.py 26 passed; vitest src/v1/k5 15 passed. Not browser-checked (ui/dist rebuild is the orchestrator's).
Root cause: speed fix is in the shared `_find` (one manager, one read per request), not per page; the route retry is safe because every write (note JSON) is the last step after all warehouse reads.
Scope: only the listed files; AUC3-08 stays partly open (who_can_act 3-name cap in sh_platform/auth, seed wording with P6); AUC3-01 race itself stays with P1 wh.py.
No defects fixed by review.

### J1 Review (10 Oct)
Fresh env c2r1 on 8861 (stopped). uc6a_1, uc6a_2, uc1b_2, uc10b_1, uc4a_1 all pass (uc1b_2 step 8 is info only: old "Dashboards of" section, line 239). ui/dist now contains "Talk to Lumen" (rebuilt 08:57), so JFIX-02 is closed. Fixes are in the shared pattern (entity regex in both scripts, rows matched by first cell). Fixed here: uc4-06, guide lines 67, 435, 459 said Sofia has no Consume; she has it (checked in the browser). Backup `.sh-tmp/DEMO-GUIDE-10UC.md.bak-j1rev`. JFIX-01 (seed shows maker id) not rechecked, stays open. Verdict: accept.

### P7 Review (10 Oct)
Reran pytest test_talk_to_all, span_w2, k3, b7_studio, e2c, p6_settings (99 passed), vitest b6, b6diagram, b7, b8, cxui, s1 (70 passed, one flaky run when run beside tsc; reran 2x clean), tsc clean. Root causes are at shared points (Map join in k3_map, listing in cx_dash, form reset in Pipeline).
Fixed in review, three small outside-P7 items: UC10A-004 (`PlanDiagram.tsx` header now "plan vN", no project id); AUC3-07 (`e2c_routes.instrument_list` returns approved manager contacts as `contacts`, so the Identifiers column shows); UC10-08 (`talk.span_company` answers a drop/delete/truncate/rename/alter request with a refusal and points to the Build chat; new test).
Still open: UC10-04 Consume access for the head of data (owner decision); UC10-09 trail and comment dates (P6, P5). Not browser-checked; ui/dist needs a rebuild for the PlanDiagram change.
Verdict: accept.

**P8 Review (reviewer, 10 Oct).** Diffs against `.sh-tmp/p8.bak-c2fix/` read; pytest test_b7_studio, test_cx*, test_k8, test_lumen_aq1, test_lumen_loop, test_talk_to_all: 136 passed. vitest i6 and g1: 22 passed. test_t1/t1b errors are the locked `data/neera` copy (live server), not the change. Scope clean: the edits stay in the listed files. `is_question` now counts identity asks as words; its other callers (talk.py, cx_routes) route them to the question path, no data leaks and no test fails. Small fix made: `t1_layout.py` rules line now uses `kind_word` (UC9-04, the intent page showed "access:"); backup `.sh-tmp/p8.bak-c2fix/t1_layout.py.review`. Still open for the i6_chat / i2_north owner: UC10A-001 and UC10A-002; and egress/router for UC10B-002. The UI needs the orchestrator's rebuild.

### P1 Review (10 Oct)
Reran pytest wh_clock, k4, k6, k9_daily, e3b-d, e5b (all pass) and vitest k4, k9 (21). Fresh c2r2 on 8862 (stopped): uc6a_1 pass, uc1b_2 pass (Office "Why did this move" link present; the info step on the old Consume tile is expected), Office at 390 px has no sideways scroll (screenshot docs/test-evidence/cycle-2/P1-review/office-390.png, too tall to read; Holdings and Liquidity cards not eyeballed).
Root cause is at shared points (wh.now process-wide, wh.connect). Fixed in review: UC1-C2-12 "lines below" was still on the Office banner (only the daily page was reworded); `k4_office.py` line 181 now applies the same replace (backup `.sh-tmp/k4_office.py.bak-p1rev`).
Not P1: test_e3a::test_routes (copies locked live data/neera); test_e5a::test_acknowledge_dismiss_and_ownership fails (TODAY is fixed at 9 Oct in the test, now 10 Oct; an acknowledged card drops out of items; P6/pulse date rot); uc4a_1 step "consume-benchmark-figures" fails with "Malformed value" because the benchmark form's first input is now a date field (P3 picker; journey needs updating). DEVP1-01..04 stay open. 
Verdict: accept.

### P6 Review (10 Oct)
Reran pytest test_a5, test_tally_trail_c1, test_seed_10uc, test_n2_comments, test_n1_tally: 114 passed (15 min). Diffs against .sh-tmp/*.bak-c2fix read; universe.json matches make_10uc_universe.py. Root causes sit at shared points (`_date`, `_chain` walk in the Stored step, `_is_current`, `_cadence`, seed title helper), so sibling trails (case, report, gold) get the same dates. Not browser-checked; AdminRules.tsx (benchmark owner line) needs the UI rebuild. Notes: AdminRules.tsx line endings changed CRLF to LF (harmless); `_cadence` uses the median gap (over 45 days = quarterly), fine for the seeded funds. JUC4A-01 left open on purpose. No code changes made. Verdict: accept.

### P4 Review (10 Oct)
Reran 10 files (test_e3b, e4a, e4b, e4d, n1_tally, tally_aq1, tally_loop, tally_tools_w02, tally_trail_c1, tally_w2): 229 passed. Diffed all 5 changed files against the .bak-c2fix backups; no code changes made. Verdict: ACCEPT.
Root cause and scope: read-only is enforced once in e4_cases (_acting/_may_act, used by every action and by `may`) and once in e3b_routes (_may_run), so no sibling action is left open; closed-case reuse sits in e3_recon._open, which all three check kinds (cash, limit, trade) go through. Send-back keeps the case investigating, so "rejected" there means dismissed only.
Notes, none blocking: (1) the server now returns the 403 but the Run now button still shows for Anita/Leo until P5 reads the level; (2) `_landed_row` assumes CSV row_number = line number (breaks only on quoted multi-line cells), `_sizer` treats a missing FX rate as 1; (3) GET /api/v1/cases/{id}/tally 7.3 s for Daniel (P3 note) was not addressed by P4; (4) handed on correctly: uc2-08 auth guard, UC5-C2-11 and UC5-C2-04 P6/P7, stale tests (test_tally_trail_c1 a2_1_a2_5, 3 test_n1_tally wording) now pass.
