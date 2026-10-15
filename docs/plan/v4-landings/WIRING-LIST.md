# Wiring list (9 Oct, after the K, D, FIX and UX1 landings)

Every open "Wiring for the orchestrator" item from `docs/plan/v4-landings/*.md`, `docs/test/UX-REVIEW-1.md` (deferred ids) and `docs/test/JOURNEY-NOTES-1.md` (label changes), checked against the code on 9 Oct. Items already in the code are listed under "Already done" so nobody redoes them.

Rules for every group: back up each file first to `.sh-tmp/<name>.bak-wire`; Decimal money; default-deny permissions; plain copy (`.claude/rules/ui-copy.md`); centre names Intent/Action/Build/Consume/Map and agents North/Span/Lumen stay; never touch `data/`, never start servers, never run `vite build`. Python: `<venv python>`. The eight groups below have disjoint file sets, so they can run in parallel.

## Already done (verified in code, skip)
- K1 item 1 / (e): `ui/src/shell/shell.test.tsx:81` already expects `["Intent", "Action", "Build", "Consume", "Map"]` in sentence case (UX1-A1 did it).
- (d): `ui/src/v1/cxui/ProjectList.tsx:33-35` links Office view, Managers and Benchmark; `ui/src/v1/k7/routes.tsx` serves `consume/benchmark`. Nothing to add.
- K8 item 1 (CaseView in ActionCentre), K8 e5/api.ts status words, UX-04 Today part, UX-14 "Not for me", UX-21 Map Health tab, UX-01/02/19/20/22 Consume, UX-03/10/12/13 Intent, UX-05/17/18 Build, UX-06/08/11/23/24 shell: landed.
- FIX-M seed: revised valuations already carry `supersedes_valuation_id` and `evidence_document_id` (`tools/seed_10uc.py:308-312`); the October amendments go through `e2_extract.confirm`, so `recorded_at` is after the meeting.
- FIX-O seed: `tools/seed_10uc.py:541-542` already writes the 15 Sep FX forward as a `transactions` row in EG-LIQUID (`transaction_type` `fx_forward`, `trade_date` 2026-09-15). Only the `external_trade_id` differs (see group 3). Securities and funds all carry an asset class; PRC29 (Pacific Rim Convertible) is the only valued instrument without one. The two FX-forward instruments also have `asset_class=None`, but they have no valuation so the holdings view never lists them.
- D item 13 (approver/participant 403 on Library and Pulse items; policy-question case hidden from Raj and Sofia): accepted as is; the answer key (`docs/test/10UC-ANSWER-KEY.md:156`) states it. The checkers must follow it (group 7).
- D item 11, 15 (demo dates): not code; the checkers already pass `as_of`.
- K7 item 2 (`pip install python-docx`): environment change, `import docx` still fails on this box; left to the person running the demo box.

## Group 1 · Office figures: cash is not a holding (D item 5 and 12, must before the demo)
Files: `sh_platform/v1/e3_calc.py`, `sh_platform/v1/k4_office.py`, `tests/v1/test_k4.py`, `tests/v1/test_e3c.py`.
1. `e3_calc.portfolio_value` (line 97): skip position rows whose instrument has `instrument_type = 'cash'` (the base seed's "Cash" instrument, `tools/seed_evergreen.py:211`). Read the type once (`select id from instruments where instrument_type = 'cash'`) and drop those ids from `best_p`. Callers: `k4_office.holdings` and `_bridge_one`, `e3_calc.portfolio_return`, `tools/eval_v2.py`; one guard in `portfolio_value` fixes all of them. Expected after the fix at today's date: NAV bridge Evergreen Growth 16,580,000 against 16,400,000 (not 18,880,000), Entity B 23,743,000 minus the 8 Oct cash, Holdings total equal to the dashboard net worth 103,405,000 with no "Cash ... unverified" line.
2. `k4_office.nav_bridge` default date: keep today, but if after step 1 the timing part still shows 8 Oct cash, default `as_of` to the latest NAV date (`_latest_nav`). Step 1 should make this unnecessary; decide after running `tests/v1/test_k4.py`.
3. `tests/v1/test_k4.py`: add one test that a cash position (instrument_type cash) is left out of holdings and the bridge.
4. K5 note: `tests/v1/test_e3c.py:48` stubs `e4_cases` with `stub(...)` and never restores it, which breaks `tests/v1/test_k7.py`'s policy-question test in a combined run. Use `monkeypatch.setattr` so it is restored.
Test: `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_k4.py tests/v1/test_e3c.py tests/v1/test_k7.py -q`.

## Group 2 · Backend small wiring (K4, K5, K6, K7, D items 1, 3, 14)
Files: `sh_platform/v1/e1_asof.py`, `tests/v1/test_e0a.py`, `tests/v1/test_d1.py`, `sh_platform/v1/e3_rules.py`, `sh_platform/v1/e3_recon.py`, `tests/v1/test_e3b.py`, `sh_platform/v1/k6_liquidity.py`, `tests/v1/test_k6.py`, `sh_platform/v1/e2_screen.py`, `sh_platform/v1/i4_sow.py`, `sh_platform/v1/i6_chat.py`, `sh_platform/v1/i2_north.py`, `docs/v2/evidence-to-action-mvp.dbml`.
1. K4: `e1_asof.SUPERSEDES` (line 13) add `"commitments": "supersedes_commitment_id"`.
2. K4: `tests/v1/test_e0a.py:44,51,96,147` and `tests/v1/test_d1.py:16,49` count 41 core tables (and 42 names incl. office_notes); core is now 42 (43 names). Update the counts.
3. K6: `e3_rules.RULE_TYPES` (line 16) add `"limit"` so a limit can be proposed in Settings (the UI side is group 4).
4. D item 14: `e3_recon.py:262` case title lower-cases the manager ("Limit breached · cedarpoint ventures · ...") because `_bucket_of` lowers the bucket. Keep the lower-cased key for matching but print the instrument's `manager_name` / `asset_class` as stored in the title and `words`. Add an assert in `tests/v1/test_e3b.py`.
5. D item 1: `e3_recon._limits` ignores `portfolio_code` on a limit rule; honour it (a rule naming a portfolio applies to that portfolio only). The seed's `_limit_as_the_product_reads_it` workaround (group 3) can then go.
6. D item 3: `k6_liquidity.forecast` has no "paid" state, so every past confirmed call sits in Overdue. Smallest change: an item whose due date is before `as_of` and that has a later `cash_movements` row of the same commitment with status `paid` (or `notice_kind` settled) leaves Overdue; if no such row exists in the model, limit Overdue to calls due within the last 90 days and say so in a `ponytail:` comment. Test in `tests/v1/test_k6.py`.
7. K4 added: `e2_screen.NAMES` gains `notice_kind: "Kind of notice"`, `due_date: "Due date"`, `fund: "Fund"`, `distribution_amount: "Distribution amount"`; `_shown` formats `distribution_amount` as money with the currency and words the kind (call -> Capital call, distribution -> Distribution, recallable -> Recallable distribution).
8. K7 item 1: add `control` and `exception` to `i4_sow.EDITABLE["process"]` (line 25), `i6_chat.FIELDS["steps"]` (line 84) and the step copy in `i2_north.apply` (lines 313-315). Until then every SOP step reads "Not stated yet".
9. K5: `docs/v2/evidence-to-action-mvp.dbml` `exceptions.exception_type` note: add `policy_question`, `limit_breach`, `capital_call`.
Test: `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_e0a.py tests/v1/test_d1.py tests/v1/test_e3a.py tests/v1/test_e3b.py tests/v1/test_k6.py tests/v1/test_k8.py tests/v1/test_i*.py -q`.

## Group 3 · Seed (FIX-M, FIX-O, D items 6, 7)
Files: `tools/seed_10uc.py`, `tools/seed_evergreen.py`, `tools/seed_v3_demo.py`, `tests/v1/test_seed_10uc.py`, `docs/test/10UC-ANSWER-KEY.md`.
1. FIX-M contact: in `_instruments` (near the `ident()` helper, line 125), write one `instrument_identifiers` row per manager with a `contact_name` in `docs/test/10uc_universe.json` (`managers[].contact_name`: Elena Marsh, Tom Adeyemi, Hana Sato, Marcus Bell, Priya Nair): `identifier_type='manager_contact'`, `identifier_value=<name>`, `mapping_status='approved'`, on the manager's first fund, `source_system_id` = a "Manager contacts" internal source (add it beside `security_master`). Hana Sato goes on Cedarpoint Ventures III or Cedarpoint Opportunities II. Then the P11 follow-up opens "Dear Hana Sato (Cedarpoint Ventures),"; update the P11 row in the answer key (it now says the draft has no contact) and the assertion in `tests/v1/test_seed_10uc.py`.
2. FIX-O: the 15 Sep forward row (`_trades`, line 541) uses `external_trade_id` `T-20260915-F01`; make it `FXF-2026-001` so the evidence line on "Why did this move" reads "Fx forward FXF-2026-001 dated 15 Sep 2026". Check `tests/v1/test_seed_10uc.py` for the old id.
3. D item 6: `tools/seed_evergreen.py` writes Fund B's 30 Sep value with `approval_status='official'`; write `approved`. The correction in `seed_10uc.py:315` then becomes a no-op (leave it).
4. D item 7: move `GOLD_HOLDINGS_SQL` (seed_10uc line 673) into `tools/seed_v3_demo.py` as its `HOLDINGS_SQL` (carried-forward values, the liquid roll-up not counted twice, cash tile narrowed to the latest day) and delete the override at line 753.
5. After group 2 item 5 lands, delete `_limit_as_the_product_reads_it` (line 167) and sign the universe's limits as written (floors: listed equity 60, hedge funds 20; single-name cap on the named holding). Do this only if group 2 has landed; otherwise leave a note.
6. FIX-B spread: the private sleeve reads 3.7466% with 300 bps over 30 days; the universe says 3.7502% (25 bps a month). Decide in the seed (about 304 bps) or in the answer key (tolerate 0.004 points); write the decision in the key's P14 row.
Test: `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_seed_10uc.py -q` (about 70 s).

## Group 4 · UI: Office, Brief, Reconciliations, Cases, Today, Settings rules (UX-07, UX-09, UX-04 remainder, K4, K6, K8)
Files: `ui/src/v1/k4/OfficePage.tsx`, `ui/src/v1/k4/k4.test.tsx`, `ui/src/v1/e5/BriefPage.tsx`, `ui/src/v1/e5/TodayPage.tsx`, `ui/src/v1/a5/ReconPage.tsx`, `ui/src/v1/a5/ReconPage.test.tsx`, `ui/src/v1/a5/CaseView.tsx`, `ui/src/v1/a5/ActionCentre.tsx`, `ui/src/v1/a5/api.ts`, `ui/src/v1/e4/CasesPage.tsx`, `ui/src/v1/e4/api.ts`, `ui/src/v1/e3a/AdminRules.tsx`.
1. UX-07 `OfficePage.tsx` (tables at 62, 103, 135, 214): wrap each table in a `div` with `overflow-x: auto`; make the holding name the trigger that opens the "where" row and drop the button column. Keep the trigger a `<button>` with accessible name "Where is this from?" (`aria-label`) so `tests/e2e_10uc/uc1a_1.py:248` and `uc1a_2.py:207,250` still find it. Label the currency chips "Show in". Same wrap in `e5/BriefPage.tsx:44`.
2. UX-09 `ReconPage.tsx`: intro (line 36) "These checks compare two records of the same money. Every difference beyond the agreed allowance becomes a case."; pill (49) "N differences to look at" / "Everything matches" (limits: keep "limits breached" / "All within limits"); line 52 "Allowance: {rule_words}" else "Allowance: not stated" (never a rule version id). `CaseView.tsx:14` "The two sources compared" -> "The two records compared".
3. UX-04 remainder: `e4/CasesPage.tsx:20` takes `framed` and drops its `PageFrame` ("Action Desk") when framed; `ActionCentre.tsx:79` passes `framed`. ReconPage and ManagersInbox have no PageFrame, nothing to do there. Tell group 6: the heading "Action Desk" disappears inside Action.
4. K4: `CaseView.tsx:13-14` add `capital_call` to `NO_STATEMENTS` and `capital_call: "The notice and the commitment it draws on"` to `KIND_WORDS`.
5. K8 item 2: `e5/TodayPage.tsx:10` `statusTone`: `break`, `limit`, `late` -> "late"; `waiting for you` -> "open".
6. K8 item 3: `e4/api.ts` `Case` type gains `exception_type?: string` and `description?: string`; drop the local cast in CaseView.
7. K6: `a5/api.ts` `CHECKS` add `limits` and `trade_vs_admin` (ReconPage de-duplicates); `e3a/AdminRules.tsx:13` `KINDS` add `"limit"` (pairs with group 2 item 3).
Test: `cd ui; npx vitest run src/v1/k4 src/v1/e5 src/v1/a5 src/v1/e4 src/v1/e3a; npx tsc --noEmit`.

## Group 5 · UI: Managers (UX-15, UX-16, tsc error)
Files: `ui/src/v1/k5/ManagersInbox.tsx`, `ui/src/v1/k5/ManagerPage.tsx`, `ui/src/v1/k5/k5.test.tsx`, `ui/src/v1/k5/api.ts`.
1. UX-15 `ManagersInbox.tsx:60`: drop zero counts from the counts line; line 64-65: hide "Draft a follow-up" when nothing is late and show "Nothing is late." alone. Tell group 6: `tests/e2e_10uc/uc3a_1.py:183` calls `.is_enabled()` on a button that will no longer exist for managers with nothing late.
2. UX-16 `ManagerPage.tsx:58-124`: move the "What changed since the last meeting?" section to the top under the title; replace the three `NoteForm`s (Add a note, Record a meeting, Add a question) by one "Add a note" form with a kind selector (Note / Meeting / Question; the date field shows for Meeting). Keep the button "Show what changed" (e2e uc7a_1/uc7a_2 use it) and the section labels.
3. `npx tsc --noEmit` error at `ManagersInbox.tsx:16` (reported by every UX1 review): fix it.
Test: `cd ui; npx vitest run src/v1/k5; npx tsc --noEmit`.

## Group 6 · e2e journeys follow the labels (JOURNEY-NOTES-1 end section, UX1-A2 open item)
Files: `tests/e2e_10uc/access_1.py`, `access_2.py`, `shell_1.py`, `uc1b_2.py`, `uc10a_1.py`, `uc10a_2.py`, `uc10b_1.py`, `uc4a_1.py`, `uc9a_2.py`, `uc3a_1.py`, `uc2a_2.py`, `docs/test/JOURNEY-NOTES-1.md`.
1. Bar labels are sentence case: `access_1.py:94,111,127,147`, `shell_1.py:15-17` (BARS and PATHS keys; check the `.lower()` comparison at line 79), `access_2.py:154,156` ("CONSUME"), `uc1b_2.py:141` ("CONSUME"). `uc10a_1.py:130` uses `re.I`, fine.
2. Intent: `uc10a_1.py:184-190` "Hand to the architect" -> "Sign the intent of work"; `uc9a_2.py:72-132` "Download the SOP" -> "Download the procedure", "Preview the SOP" -> "Read the procedure here".
3. Today: `access_2.py:135` button "Dismiss" -> the link/button "Not for me".
4. Build: `uc10a_2.py:188` "3 Tables and SQL" -> "3 Tables"; `uc10a_2.py:209` and `uc4a_1.py:161,169` "Run in the sandbox" -> "Try it on a copy"; `uc10a_2.py:239` "Download the Airflow file" now sits inside a `<details>` "For engineers" (open it first).
5. Consume: `uc10b_1.py:124` "Gold tables" -> "Figures available".
6. After group 4 item 3: `access_2.py:196` and `uc2a_2.py:79` wait for heading "Action Desk", which disappears inside Action; wait for the "Cases" tab content instead (the table or the 12,400 row).
7. After group 5 item 1: `uc3a_1.py:180-189` `nothing_late`: the button exists only for Cedarpoint; check `count() == 1` for Cedarpoint and `count() == 0` plus "Nothing is late" for the others.
8. `docs/test/JOURNEY-NOTES-1.md`: "Tables and SQL" / "Run in the sandbox" mentions (UX1-A5 open item) -> the new words.
Check: `python -m py_compile tests/e2e_10uc/*.py` (no servers; the runs are for the demo box).

## Group 7 · Use-case checkers follow the fixed routes and the role limits (FIX-B, FIX-L, FIX-O, D item 13)
Files: `tools/verify_10uc/uc1.py`, `uc2.py`, `uc4.py`, `uc5.py`, `uc8.py`, `docs/test/CHECKER-NOTES-1.md`.
1. FIX-O, `uc1.py` P06 (around line 270-276): read `GET /api/v1/office/why-moved?start=2026-08-31&end=2026-09-30&book=liquid` as the sponsor; assert start 39,552,000, end 41,200,000, change +1,648,000, pct 4.1667, `largest` = Northwind Logistics +132,000, and that the trades list names FXF-2026-001. Drop the "no why route" note.
2. FIX-B, `uc4.py` P14 (line 95-112): call `GET /api/v1/benchmarks/comparison?portfolio=EG-LIQUID&code=EG-OFFICE-BLEND&start=2026-09&end=2026-09` as the approver: portfolio 4.1667, blend 2.7072, components 3.5002 / 0.4002 / 3.7502 (tolerate 3.7466 until group 3 item 6 settles), difference 1.4595, `liquid_sleeve.difference` 1.9065, certified true. P15 (line 113-128): the approver cannot see the policy-question case in `/api/v1/cases` (answer key line 156); read `GET /api/v1/benchmarks` as the approver and assert version 2 carries `notice` "In progress: not used for certified figures." and `policy_question` with the open case; keep the `/api/v1/cases?exception_type=policy_question` check but run it as Mei Chen (analyst).
3. FIX-L, `uc2.py:129-135` and `uc8.py:148-158`: approver and participant now get 200 on `GET /api/v1/recon/runs` (e3b.permissions.yaml) and still 403 on the POST run; change the expectation.
4. FIX-L, `uc5.py:144-166`: P19 "Needs a class" and the no-classification cause must read `questions` in the run record (`GET /api/v1/recon/runs`, check `limits`), not `causes`; line 165-166 expects the participant to get 200 on `POST /api/v1/recon/limits/run`, but POST stays company_admin and analyst: assert Sofia gets 403 on the POST and 200 on `GET /api/v1/recon/runs` with the P19 question and the P20 results lines.
5. D item 13, `uc1.py:197`: Pulse items are read as the sponsor, fine; add nothing for the approver. If any checker reads `/api/v1/library` or `/api/v1/pulse2/items` as Raj Patel, expect 403.
6. `docs/test/CHECKER-NOTES-1.md:77,104` (and the uc5 paragraph at 244): say GET runs is open to every company role; POST run is not.
Check: `python -m py_compile tools/verify_10uc/*.py`.

## Group 8 · Shell and legacy map links (K1 items 2, 3, K2)
Files: `ui/src/shell/copy.ts`, `ui/src/App.tsx`, `ui/src/design/Gallery.tsx`, `ui/src/pages/FeedsPage.tsx`, `ui/src/pages/NodePage.tsx`, `ui/src/pages/centre.test.tsx`, `ui/src/v1/a5trail/TrailPanel.tsx`, `ui/src/v1/a5trail/trail.test.tsx`, `ui/src/v1/p3/ConsumeEntry.tsx`.
1. K1 item 2/3: the Map replaces the old company map. `shell/copy.ts` legacy `bar` entry `COMPANY MAP` -> `/centre/map` (or delete the legacy `bar` list if nothing reads it); `App.tsx:158` `intent/graph` route redirects to `/centre/map`; `design/Gallery.tsx:16,52,56,128`, `pages/FeedsPage.tsx:82`, `pages/NodePage.tsx:109,112` -> `/centre/map`; `pages/centre.test.tsx:85` expectation follows.
2. K1 item 2: `a5trail/TrailPanel.tsx`: an "Open in the map" link to `/centre/map?tab=flow&focus=<id>` for a step that names a source, file, table, dashboard or person (ids `source:<code>`, `files:<code>`, `table:<name>`, `dash:<id>`, `person:<name>`); process lane `?tab=processes&focus=<intent id>`. Only when the step carries such an id; no guessing.
3. K2: `p3/ConsumeEntry.tsx` has no link to `/centre/consume/office`; add "Open the Office view" if that page is still shown anywhere (ProjectList already carries the links; if ConsumeEntry is unused, say so instead of editing).
Test: `cd ui; npx vitest run src/shell src/pages src/v1/a5trail src/v1/p3 src/App.test.tsx; npx tsc --noEmit`.

## Not assigned (decisions, not code)
- D item 13 permissions: accepted as the key states (see Already done).
- FIX-B: whether 1.9065 is read off `liquid_sleeve.difference` (as built, and as group 7 asserts) or a signed 60/40 benchmark goes into the seed. Keep as built.
- FIX-L: the runs route exposes cash and trade results to participants, approvers and sponsors; accepted.
- K7: `skills/north/sop.md` in the G1 skill loader only if the loader is an explicit list (grep found no loader naming it; verify in group 2 if time allows).
- FIX-B: `a5_trail.KINDS` benchmark kind for "Where is this from?" on the benchmark table; not needed for the demo.

## G6 e2e journeys follow the labels
Done: items 1-8. Bar labels now sentence case (access_1, shell_1 BARS/PATHS, access_2, uc1b_2); "Sign the intent of work" (uc10a_1); "Download the procedure" / "Read the procedure here" (uc9a_2; the "SOP preview" label and "Hide the SOP" left as is, not in the item list); "Not for me" (access_2); "3 Tables", "Try it on a copy", Airflow link now opens "For engineers" first (uc10a_2, uc4a_1); "Figures available" (uc10b_1); Cases waits for a table column header instead of "Action Desk" (access_2, uc2a_2); uc3a_1 nothing_late now checks the follow-up button count is 1 for Cedarpoint and 0 for the rest; JOURNEY-NOTES-1 words updated.
Skipped: none. Not run against servers (not allowed).
Tests: py_compile tests/e2e_10uc/*.py passes. Backups in .sh-tmp/*.bak-wire.

## G5 UI Managers (UX-15, UX-16, tsc)
- Done UX-15: ManagersInbox count line drops zero counts ("Nothing expected this month." if all zero); "Draft a follow-up" button is not rendered when nothing is late, "Nothing is late." shows alone (G6: uc3a_1.py must not call is_enabled() on a missing button).
- Done UX-16: ManagerPage "What changed since the last meeting?" moved under the title; one "Add a note" form with a kind selector (Note / Meeting / Question), date field for Meeting; "Show what changed" and section labels kept.
- tsc: `npx tsc --noEmit` reports no error at ManagersInbox.tsx:16 in the current tree; no change needed.
- Tests: k5.test.tsx updated (hidden button, kind selector); `npx vitest run src/v1/k5` 8 passed; tsc clean. Backups: .sh-tmp/*.bak-wire.

## G4 UI Office, Brief, Reconciliations, Cases, Today, Settings rules
Done: UX-07 (overflow-x wrap on the four Office tables and the Brief table; holding name is the "Where is this from?" button, button column dropped; "Show in" label on currency chips in Office and Brief). UX-09 (Recon intro, "N differences to look at" / "Everything matches", "Allowance: ..." / "Allowance: not stated", CaseView "The two records compared"). UX-04 remainder (CasesPage takes framed, ActionCentre passes it; G6 must update the e2e that waits for "Action Desk"). K4 (capital_call in NO_STATEMENTS and KIND_WORDS). K8 (statusTone break/limit/late -> late; Case type gains exception_type, description, local cast dropped). K6 (CHECKS gains limits and trade_vs_admin, ReconPage MORE shim removed; AdminRules KINDS gains "limit").
Skipped: nothing. "waiting for you" already falls to "open".
Also touched: a5/a5.test.tsx (two assertions for the new Recon copy).
Tests: vitest src/v1/k4 e5 a5 e4 e3a 31 passed; tsc --noEmit clean.

## G8 Shell and legacy map links (done)
- Done: shell/copy.ts bar "COMPANY MAP" -> /centre/map (GraphPage still reads the list); App.tsx intent/graph now redirects to /centre/map; Gallery, FeedsPage, NodePage links -> /centre/map; TrailPanel "Open in the map" (flow tab on a source:/files:/table:/dash:/person: ref id, processes tab on an intent ref) with two tests in trail.test.tsx; ConsumeEntry "Open the Office view" -> /centre/consume/office (page is rendered by k4 routes).
- Skipped: centre.test.tsx:85 stays on /centre/intent/graph because that link is rendered by PulsePage.tsx:229/235 (not in G8; the redirect covers it). Same for RegisterPage, WhatIfPage, WhereItLives, GraphPage:232, pulsePage.test.
- Note: current a5_trail refs never carry map ids or an "intent" kind, so the trail link stays hidden until the backend adds them.
- Tests: vitest src/shell src/pages src/v1/a5trail src/v1/p3 src/App.test.tsx all pass after the revert above; tsc clean.

## G2 Backend small wiring (K4, K5, K6, K7, D 1, 3, 14)
Done: 1) SUPERSEDES has commitments. 2) table counts 42 / 43 in test_e0a, test_d1. 3) RULE_TYPES has limit. 4) limit title and words print the bucket as stored (matching key stays lower-cased); asserted in test_e3b. 5) limit rule honours portfolio_code (test added). 6) K6: new status `paid`, a past paid call is not Overdue and still counts as called (uncalled, confirmed); test in test_k6. 7) e2_screen NAMES for the four notice fields, distribution_amount shown as money, notice kind in words. 8) control and exception added to i4_sow.EDITABLE['process'], i6_chat.FIELDS['steps'], i2_north step copy. 9) dbml exception_type note adds policy_question, capital_call (limit_breach was already there).
Skipped: nothing. Note: nothing yet sets a call to `paid`; a UI or loader step must write that status.
Tests: the group pytest run, 73 passed.

## G1 Office figures: cash is not a holding

- Done 1: `e3_calc.portfolio_value` drops position rows whose instrument has `instrument_type = 'cash'` (ids compared as strings). Holdings, NAV bridge, portfolio_return and eval_v2 all read through it. Not checked against the live demo plane (data/ untouched): expected Growth 16,580,000 and Holdings total 103,405,000.
- Done 3: `test_k4.py::test_cash_position_is_not_a_holding` (holdings total, line list and bridge investment total).
- Done 4: `test_e3c.py` stub helper now uses `monkeypatch.setattr` for the package attribute, so e4_cases.open is restored.
- Skipped 2: `nav_bridge` default as_of left as is; cash was the only 8 Oct item in the timing part and cannot be confirmed without reading the demo plane. Revisit if timing still shows 8 Oct after step 1.
- Tests: `SH_MODEL_PROVIDER=off pytest tests/v1/test_k4.py tests/v1/test_e3c.py tests/v1/test_k7.py -q` gives 36 passed.

## G7 Use-case checkers follow the fixed routes and role limits
Done: items 1-7. uc1 P06 reads `/office/why-moved` as the sponsor (39,552,000 to 41,200,000, +1,648,000, 4.1667%, Northwind Logistics +132,000, trades name FXF-2026-001; the per-security holdings check is kept, the "no why route" note is gone). uc4 P14 reads `/benchmarks/comparison` as the approver (4.1667 / 2.7072 / 3.5002, 0.4002, 3.7502 or 3.7466 / 1.4595 / liquid_sleeve 1.9065 / certified). uc4 P15 reads `/api/v1/benchmarks` as the approver (version 2 notice and policy_question with the open case) and the cases list as Mei Chen. uc2 and uc8 expect 403 on POST run and 200 on GET runs for approver, participant (and sponsor in uc8). uc5 P19 reads the "Needs a class" question from the run record, P19 and P20 check Sofia 200 on GET runs and 403 on the Limits POST, P20 checks the two results lines. No checker reads `/api/v1/library` or `/pulse2/items` as Raj Patel, so item 6 needed no edit. CHECKER-NOTES-1.md updated.
Skipped: nothing.
Tests: `python -m py_compile tools/verify_10uc/*.py` passes. Checkers not run (no servers). Backups: .sh-tmp/*.bak-wire.

## G3 Seed (FIX-M, FIX-O, D items 6, 7, 5, FIX-B)
Done: 1) FIX-M: seed_10uc writes an approved `manager_contact` identifier per manager (on the manager's first fund, new internal source "Manager contacts"); P11 in the key and the test now read "Dear Hana Sato (Cedarpoint Ventures),". 2) FIX-O: the 15 Sep forward row is `FXF-2026-001`. 3) D6: seed_evergreen writes Fund B's 30 Sep value as `approved` (seed_10uc's correction is a no-op, left). 4) D7: the gold holdings SQL now lives in seed_v3_demo as `HOLDINGS_SQL`, the cash tile reads the latest day there; the override and `_tiles` are gone from seed_10uc. 5) G2 had landed portfolio_code: `_limit_as_the_product_reads_it` deleted and the limits signed as written (floors 60 and 20). 6) FIX-B: decision in the key's P14 row: seed keeps 3.7502, 3.7466 (30-day accrual) tolerated.
Skipped: the single-name rule still names its holding (Harborview Semiconductor, 0 to 5%) because the product reads bucket "any" as a holding called "any" and the true rule breaches on six names. Needs `e3_recon._limits` to treat "any" like "*" (one word in `want in ("", "*")`), then the three lines in seed_10uc can go.
Tests: `pytest tests/v1/test_seed_10uc.py -q`: see final run. Backups: .sh-tmp/*.bak-wire.
