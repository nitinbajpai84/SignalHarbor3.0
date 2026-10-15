# V6 walk: one new project end to end (11 Oct)

Server: own test environment (`tools/make_test_env.py v6 --seed`, `tools/serve_test.py --port 8697`), simple mode, Testing models (free tier), no Real use, no real connectors. Project `prj-9af62f90` ("Report of how our private funds", intent `ini-4ff5c128507f59f2bf146a4194e986b6`). Screenshots 1440 wide in `walk/`; designs rendered from `docs/plan/v5-designs/H*.dc.html`. Server stopped at the end.

## The walk

| Step | Who | Result | Shots |
|---|---|---|---|
| Build landing (A1) | Mei | Serif title, poster, chapters, four step cards, running projects: as the design | 01 |
| New project, North | Mei | Opens. First turn failed: the North system prompt was 20,033 characters, over the gateway's 20,000 limit (see Fixed 1) | 02, 03 |
| North records how each system arrives | Mei | Works: custodian files `sftp`/daily, PDFs `mailbox`/monthly, index `upload`/monthly; closing summary names the sections that block signing; short project title | 03n, 04n, 04-closing-summary |
| Sign page (B3) and signature | Daniel | Action lists "Intent to sign"; sign page with the 8 sections, read box, Sign | 05, 06, 07 |
| Hand over to Leo (B4), Leo's Action card (B5) | Mei, Leo | Works; due date and builder card | 08, 08b, 09, 10 |
| Architecture H1 (what I already know) | Leo | Systems "from the intent" with how they arrive; Confirm / This is different | 11, 11b |
| H2 the few questions | Leo | 5 questions, each with a default, Accept all | 12, 12b |
| H3 samples | Leo | CSV profiled, PDF lines marked (net asset value, statement date) | 13, 13b |
| H4 design pack, H5 mapping sheet | Leo | Pack drafted; 6 rows needing a person stopped the send until settled | 14, 14b-14e, 15 |
| H6 approval | Anita | Her Action had no card for the pack (Fixed 3); approved; plan drawn from the pack; plan approved with a note (C2) | 16, 17, 18, 19, 20, 20b, 21 |
| H7 builder connects, runs by itself | Leo | Source channels `sftp`/`mailbox` have no connector on this box: corrected to upload (system correction forks pack v2, approved, plan v2). Builder then connected 4 of 4 and ran by itself | 22 |
| H8 benchmark upload and variance | Leo | Upload read (3 figures); the run holds no figure for them: 3 unexplained (Fixed 5) | 23 |
| H9 send back, pack v3, rerun, go live | Leo, Anita | Sent back with a note; architect issued pack v3 from the variance, Anita approved plan v3, the builder reran by itself; Go live anyway (variance accepted) | 24, 25, 26, 27 |
| H10 Lumen starter | Mei | Starter dashboard with 4 tiles opened (Fixed 6, 7); Send for approval | 28, 29 |
| Approval (D3) | Daniel | "What Lumen checked" with honest "not checked" lines; Approve | 30, 31 |
| Delivery (D4), complete (D5) | Mei, Daniel | Consume and Email digest approved and live; complete page records the live pipeline (Fixed 8) | 32, 33, 34 |
| Consume (E1), Map (F1) | Daniel, Anita | Consume opens with the right column; Map opens on the whole company, 19 items wait for the head of data | 35, 36 |

## Fixed during the integration and walk (root cause, with tests)
1. **North could not answer at all** for a new project: its system prompt was 20,033 characters and the gateway refuses a string over 20,000 (`payload_too_large`, "I could not finish working that out"). Trimmed duplicated lines from `skills/north/traps.md` (the same rules are in the chat prompt) and tightened three sentences in `i6_chat.CHAT_PROMPT`: about 650 characters saved. Margin is still under 700; see Open 1.
2. **The builder never saw how a source arrives or which fields were marked** (the two cards stored them differently): `b10_pack.apply_to_plan` now puts `arrives {how, connector}` and `fields` on each plan source. Test in `test_v6_b10_pack`.
3. **A design pack waiting for the head of data was not in her Action.** `p2_assign._waiting` adds kind `pack`; UI label "Design pack". Test in `test_v6_b10_pack`.
4. **Studio failed ("Something went wrong") once the pipeline was live**: the pack's freshness text "8th working day of each month" went into the plan schedule and `b6_schedule._dom` did `int()` on it. `_dom` now reads the leading number. Test in `test_v6_b10_pack`.
5. **A report none of whose figures the run holds showed "Variance cleared / Looks good"** (nothing was compared). Those lines are now unexplained with "This run has no figure for this line"; go live needs "anyway" and send back works. Test in `test_b11_builder`.
6. **A round that ran at approval was never checked against the benchmark when the page opened** (`can.start` was false once the round existed). Now true while a benchmark is waiting.
7. **Starter dashboard said "made by someone no longer in the company"** (Lumen is not a user): reads "Lumen".
8. **Complete page, Pipelines card "Not recorded"** after a builder go-live: now "Live, started by Leo Park with a variance accepted / after a clean check".
Tests changed: `look.test.tsx` lists `v1/b11/b11.css`; `test_role_matrix_intents` reads only company roles (head_of_data is a seat beside analyst); `test_x3` seat table includes `head_of_data` for the company admin.

## Remaining differences from the designs and open defects
Design pack (H4/H5): the design is a dark denser page with a roles line, a "Next: Open the mapping sheet" bar, "Compare versions", a table of grain, key, type 2 and owner per gold table, and a Definitions panel next to the silver tables. Ours is the light theme with tabs, a column list per table, no Compare button and no Definitions panel.
1. **Pack content quality.** The pack's gold table is the one table the rules draw (monthly returns), not the design's three (returns, holdings, net worth). Every column shows type `varchar` and the same definition text (the first KPI's), although the table holds numbers; the three KPIs "net worth", "return net of fees", "return against benchmark" became open rows the person settled by words.
2. **The pack names no benchmark block** (portfolio, code, month) for the builder, so the builder cannot compare the report's returns (4.17%, 2.71%, 1.46) with the run; in this walk the report lines stayed unexplained and the walk went live with the variance accepted. Net worth and returns by month are in the gold table, but not as a figure the builder can read.
3. **Step rail on the Architecture step still says "Needs a builder"** after Mei handed over to Leo.
4. **Pipelines page** shows the old section below the builder: "Next run: Not scheduled until the plan is live" after going live, and "Control totals" of earlier demo files (company-wide) and "Reading 104 statements" (all company statements), not this project's.
5. **North** duplicated a source ("Custodian positions file" and "Custodian positions"), left "Why: Not stated", and never offered the PDF source a channel until asked (free-tier model behaviour).
6. **Hand-over note** field has no label (not found by label), so assistive software does not announce it.
7. **Delivery preview subject** prints an unrounded figure ("portfolio return 0.006024795840697594").
8. **Map** lists "Leo" and "Leo Park" and "lumen" as three people.
9. H3 marks a PDF field by line, not by drawing a box (known). Dark theme of the H designs is not used (the app is light).

## Review (Opus, 11 Oct)

Read: the eight integration diffs against `.sh-tmp/*.bak-v6int`, shots 14, 23, 27, 28 and 36 next to H4, H8, H10 and F1. Suites re-run: the changed backend tests (73 passed), the b6, b9, b11, d1, k3 and V6 backend tests (88 + 21 passed), vitest for b8, b9 and b11 (40 passed), `tsc` clean. No model calls, Testing only, no live server started.

**The eight walk fixes hold.** Each one is a root-cause fix with a test. The nothing-compared variance now reads as unexplained, which is honest. The `on_approved` hook never raises. Money stays Decimal. The new b10 and b11 routes have their permissions files. The three changed access tests only add the head of data seat; none of them loosens a check.

**Fixed in this review (backups `.sh-tmp/*.bak-v6rev`, tests in `tests/v1/test_v6_review.py`)**
1. **Control gap: the old Pipelines "Go live" skipped the builder's variance gate.** It sat under the builder, enabled, and with it an architect could take a pack live while the builder held an unexplained variance, and the builder's record would not show it. In `b6_routes.run_plan`, a live run is now refused while the builder holds a round that is not live. Live runs after the builder's own Go live, and projects with no builder, work as before.
2. **The step rail said "Needs a builder" after the hand-over** (Remaining 3). `StepperShell` passed no assignments to `stepStatuses`. It now loads them, so the rail reads "Assigned to Leo Park".
3. **The delivery subject printed `0.006024795840697594`** (Remaining 7). `d1_delivery._fmt` now rounds a Decimal with more than four places: to 4 places below 1, to 2 places otherwise. A figure that already has 2 places, such as money, is left as it is.
4. **The map showed "Leo", "Leo Park" and "lumen" as three people** (Remaining 8). `k3_onto._merge_people` joins a first name to the one full name that starts with it, and joins an agent's name to the agent node. Their links move with them. Two people with the same first name stay apart.
5. Remaining 6 is not a defect: the hand-over note is a textarea inside the label "Note to Leo", so it has an accessible name. The walk script's lookup missed it.

**Still different from the designs or broken (honest list)**
- H4/H5: the pack has one gold table where the design has three. Every column is `varchar` and they share one copied definition. The page is light where the design is dark, and it has no Compare versions or Definitions panel. The benchmark KPIs became open rows that a person settled in words. This is the largest gap in the content.
- H8: the pack gives the builder no benchmark block (portfolio, code, month) and no key figures. Gold holds 9 rows of portfolio, benchmark and difference, yet the run had a figure for none of the 3 report lines. So the walk's "go live anyway" was forced, not a choice. Fixing it needs `b10_pack.apply_to_plan` to write `benchmark` and `key_figures` from the benchmark rule. That is the next build item.
- Pipelines page: below the builder, the old section (stage cards, the run controls and `VerifyPanel`) is still there, so the page is about 29,000 pixels tall. VerifyPanel shows company-wide control totals (453 checks, other projects' statements), "Reading 104 statements" is company-wide, and "Next run: not scheduled" stays after going live. The old Go live is now refused (Fix 1), but the section should fold under the builder or be scoped to the project.
- H10 (shot 28): the starter's "Portfolio return at the latest date 1%" is rounded so far it tells the reader little. The bar axis repeats "1%, 1%, 0%, 0%". The side panel says "Lumen has not suggested any tiles" beside Lumen's own starter. The trend chart plots the run's return series at about ±0.28 while the report says 4.17%. The units need checking against the pack (they may be fractions).
- North: there is less than 700 characters of headroom on the system prompt. Add a size test for the largest template.
- North on the free tier duplicated a source and left "Why: Not stated". H3 marks PDF fields by line, not by drawing a box. The app is light where the H designs are dark.

**Difference for Nitin's approval:** while the builder holds a round that is not live, the old Pipelines "Go live" is refused, and the builder's Go live is the only way to take that pack live.
