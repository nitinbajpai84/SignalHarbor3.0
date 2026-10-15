# UC5 live test report: Are we inside our limits?

Evergreen Office, monthly limit monitoring, run as the seven people would run it: a build month (July 2026), then August, September and October. Synthetic data only. Plan: `UC5-PLAN.md`. Answer key: `docs/demo/uc5/ANSWER-KEY.md`. How to run it again: `UC5-RUNBOOK.md`.

- Run date: 12 Oct 2026. Tester server 127.0.0.1:8812, data root `.sh-tmp/testenv/uc5/data`, Testing models only (never Real use).
- Evidence: every call in `D:/Temp/uc5/calls.jsonl`; saved responses `D:/Temp/uc5/*.json`; screenshots `D:/Temp/uc5/shots/`; working notes `D:/Temp/uc5/notes.md`.
- Nothing committed. Product code was changed during the run on Nitin's instruction (12 Oct, mid-run): fix bugs and generic friction, work around data-quality problems. Every change is listed in section 4 with its test.

## 00. Round 3 (13 Oct 2026): the top five product features built, quick test on the September file

| # | Feature | What a customer now does | Files | Unit test | Live (September file) |
|---|---|---|---|---|---|
| 1 | Smart data block, every sheet in one step | Upload the administrator workbook as it comes: a "Portfolio totals" block under the data is read as each group's control total (checked against its rows); `{"sheet": "*"}` loads every sheet, each with its own mapping | `e0c_load.py` (`_read`, group totals), `e0c_landing.py` (`ALL_SHEETS`) | totals block; every sheet | Original file, not edited: 27 + 7 rows; EG-LIQUID 41,200,000, EG-B-OPS 22,525,000, EG-FUNDS 22,550,000 all matched |
| 2 | Load flow helpers | "Approve all exact name matches" (one click by a person, near matches stay for review); the mapping editor (`PUT /api/v1/model/mappings/{id}`) already existed | `e2_match.approve_exact`, `e2c_routes.py`, Identifiers screen | exact only | No names waiting (reused from July) |
| 3 | Signed limits workbook imported | Upload the signed sheet, press import: changed lines become proposed versions for the CIO, unchanged lines stay, one Action item names the differences; never signed by the import, never proposed twice | `e3_rules.import_signed`, `POST /api/v1/rules/import` | proposed / unchanged / waiting / item | v2: only Harborview 6% to 5% proposed, three unchanged, Action item opened, Daniel signed |
| 4 | Received-on date at upload | Give the day a file arrived (not in the future); a check "Files received by" that day counts it, even if it was loaded later (the limits check reads by arrival time; other reports keep the audit view) | `e0c_landing.receive`, `e1_asof.snapshot(by="received")`, Intake screen | arrival parsing; arrival-time cutoff | Received 2 Oct; check as received by 2 Oct 06:00 UTC |
| 5 | One case per standing breach | While a breach's case is open, a later month's breach of the same limit is written in that case ("Still in breach at 31 Oct: …") instead of a new case; never joins a case of a later day | `e3_recon.py` | standing; later-day guard | 31 Oct check joined the open Cedarpoint case, no new case |

September at the 2 Oct receipt time now equals the key: hedge funds 54.95% ("Uses estimates" on H1 and H2), listed equity 80.61%, Cedarpoint 56.50% over 343,750 stale, Harborview 5.75% against 5% real over 308,000; two new cases (one real, one stale). Run `run-20261012-235352-2869`.

Found and fixed during this test: the as-of reader judged "received by" on the warehouse write time, so a file loaded after its arrival never counted for that day (fixed for the limits check, feature 4); the first standing-case version joined a later-dated open case (fixed, earlier days only; the demo's 9 Oct Cedarpoint case keeps three "30 Sep" history lines from before the fix).

Not built in this round: a screen button for "load every sheet" (API only; the file page shows one mapping) and the full guided "Load this month" screen. UI typecheck and the intake and settings UI tests pass; no full suite was run.

## 0. Run 2 (13 Oct 2026): the two open decisions built, Month 1 rerun on a fresh seed

Nitin approved fixing G-1 and G-2 and asked for a rerun from Month 1 (July only). Fresh data root (`seed_demo_boot --reset`), same port, evidence in `D:/Temp/uc5/r2/` (calls, JSON, screenshots `r2-*.png`).

Built for the decisions:
- G-2, the limit basis. The limits check now reads the administrator's month-end positions as well as manager statements: per holding the latest dated value; on the same date a fund keeps its manager's statement and a security keeps the administrator's value; an administrator "estimate" is flagged on the line ("Uses estimates: …", C12); a line with no currency is read in the portfolio's currency; cash is not in the limit base (`e3_recon._positions_as_values`, `_rank`). A load can name its sheet (`POST /api/v1/intake/files/{id}/load {"sheet": "Latest statements"}`), so the latest-known statements load too.
- G-1, limits on the dashboard. A company table `limit_results` is added by the product's own model change (Leo proposed, Anita approved, version 4). Every limits run writes its lines there (a rerun for the same as-at day replaces them). Span's design then read it on its own: gold `…_exposure_limits` selects from `limit_results`.

Run 2, Month 1, against the key (run `run-20261012-222131-ce32`, as known now):

| Line | Product | Key | Result |
|---|---|---|---|
| Harborview | 5.73% of 6% (Sofia's v2, Daniel signed), headroom 0.27, inside | same | pass |
| Listed equity | 80.04%, headroom 9.96 | same | pass |
| Cedarpoint C + D | 57.38%, -2.38, over 536,250, stale | same | pass |
| Hedge funds | 54.49%, headroom 5.51 | same | pass |
| Pacific Rim | question, 1,084,000, 2.72% | same | pass |
| Cases | one new: Cedarpoint 31 Jul, stale | one | pass |
| Consume | bar per limit: 54.49 / 80.04 / 57.38 / 5.73 (and 2.72 for the question) | key figures | pass |

The whole July path now runs as people, with no admin workaround: Grace sets Sofia to Owner on the People and access screen; Mei writes the intent, Daniel signs it, Mei hands the build to Leo; Leo loads the positions and the Latest statements sheet (Anita approves each mapping and the 27 names); Anita approves the pack, the model change and the plan; Sofia proposes the 6% limit and Daniel signs; Leo goes live (test `run-20261012-221937-784f`, live `run-20261012-221938-aa99`, `run-20261012-222151-36dc`); Mei runs the check on the screen; Sofia takes the case and sends it for check as stale data, Daniel approves (closed `stale_data`); Mei notes the Fund D chase; Leo sets up the email channel, Daniel approves it, delivery is live (nothing sent).

Run 2, Month 2 (August), run `run-20261012-233235-57c9`: files loaded in one step each (positions 27 rows, Latest statements 7; the approved mappings and names were reused). Harborview 5.71% of 6%, headroom 0.29; listed equity 80.06%; Cedarpoint 57.38%, over 536,250, stale; hedge funds 54.56%; Pacific Rim question 1,051,000, 2.66%: all equal to the key. One new case (Cedarpoint 31 Aug), taken by Sofia, closed `stale_data` after Daniel's check. Live run `run-20261012-233313-9a4d`; Consume shows the August figures. Run 2 stopped after two months, as asked.

Fixed during run 2 (each with a test):

| # | Kind | Change | Files |
|---|---|---|---|
| FX-22 | bug | The model may not fill a field a named column already fills ("Administrator code" was put on the portfolio code, so every row's portfolio became 4473…) | `e0b_tools.py` |
| FX-23 | bug | Approving a model change failed while the server ran ("the warehouse file could not be copied"): the check copies the warehouse through DuckDB, as the pipeline sandbox does | `e0a_catalogue.py` |
| FX-24 | bug, wrong number | The pack's rules design wrote `FILTER` outside the aggregate (SQL did not run), joined two values of one column with AND, and put share KPIs as plain totals of case amounts under their names | `b10_design.py` |
| FX-25 | wrong number | Lumen's starter added four limits' percentages together (200.36 on every tile). A share column is shown one bar per item, never summed; the checks line counts file-filled steps as done | `cx_lumen.py` |
| FX-26 | message | The approval panel names the latest live run instead of "No reviewed run is on record" | `b7_studio.py` |
| FX-27 | bug | Summary sentence ended "..": the goal's own full stop is not doubled | `i6_chat.py` |
| G-1/G-2 | decision | as above | `e3_recon.py`, `e0c_load.py`, `e0c_landing.py`, `e0c_routes.py` |

Still open after run 2:
- North left "Who runs the limits-check step?" unsettled after Mei answered it (its topic is the process, not a form field); signing was still allowed.
- The Latest statements sheet has no Currency column; the loader should take USD from the header "Latest known value (USD)" (the limits check now assumes the portfolio's currency).
- A published starter cannot be redone: the summed tiles were removed by editing the layout (new version, approved again). Tile labels show rule codes ("limit_hedge_funds") and the question row as "null".
- The "Latest statements" lines load as position lines (purpose guessed as positions); they do the right thing for the limits, but a statements purpose would be cleaner.
- Run-date staleness (Fund D 192 days at the pinned 9 Oct) and the case per month for a standing breach are unchanged (decisions, see run 1).

## 1. The answer in one screen (run 1, 12 Oct)

| | Before the fixes | After the fixes |
|---|---|---|
| Intent, design pack, plan | Signed; pack and plan approved only through workarounds (admin handover, access requests) | Same people, no workaround needed except the access request (now automatic for the head of data) |
| Monthly positions file | Never loaded: crash with the model on, then footer rows, then an empty date | Loads 27 rows every month (footer block still removed by hand: data quality) |
| Test run, go live | Every test run failed; go live refused | Test and live runs pass every month; live with monthly schedule from the pack |
| Signed limit change (6% then 5%) | Nobody could propose it | Sofia proposes, Daniel signs; both versions in force on the right dates |
| Limits check, Jul to Sep | Only the admin could run it; Harborview a false breach in Jul and Aug | Mei runs it on screen, with the files' receipt time; Harborview matches the key every month |
| Risk owner acts on cases | Refused (participant); closing lost the reason | Sofia is made owner on screen; cases close as stale_data, cured or explained |
| Dashboard in Consume | Showed 290,850,433 under every limit tile (a sum of all holdings) | Shows no false number; the limit figures are not on the dashboard yet (open gap G-1) |
| October | Not reached | Runs, but every limit figure is September's: October values never reach the check (open gap G-2) |

Honest summary: the people and the pipeline now work end to end, and the limit arithmetic matches the key for July to September once the cutoff basis is understood (section 3). October is wrong, and the dashboard has no limit tiles. Both need a decision from Nitin (section 5), not a code fix.

## 2. Run record by month

IDs: intent `ini-3b5af61fea343d545a462d67417ae582`; project `prj-b35ce997`; design pack v1 then v2 (approved by Anita Rao); plan v1 (rules route), v2 and v3 (from the pack, monthly, 5th business day 06:00); dashboard `dash-a13e4c16`; delivery channel `ch-fed7d0` (email, monthly, live, nothing sent).

### Month 1, July (build)

| Step | Person | What happened | Result |
|---|---|---|---|
| M1-01 mode | Daniel | Header shows the Testing / Real use switch on Testing. The "Testing models (free tier)" line is on agent pages only (Span, North) | note |
| M1-02/03 start | Grace | Register: single name 5.00% from 1 Jan (v1), listed equity 60 to 90, Cedarpoint 0 to 55, hedge funds 20 to 60. Two seeded cases dated 9 Oct (Cedarpoint, Harborview). valuation_observations 329, position_snapshots 115. Pacific Rim has no class | pass (F1, F2 confirmed) |
| M1-04 roles | Grace | Sofia participant, Mei owner. No role-change screen | missing, fixed (FX-7) |
| M1-05 North | Mei | 14 turns. Summary listed the four limits, both sources, readers, process. Defects: "PERSON 010 owns all the KPIs" (name token shown), goal cut ("the headroom in ."), "Needed by by", the settled access question kept blocking, KPI formulas "× not available yet" (the 100 removed) | fail, fixed (FX-11 to FX-13) |
| M1-06 sign | Daniel | Signed v1, 11:47Z. Headroom in points, no basis points | pass |
| M1-07 handover | Mei, Daniel, Grace | Mei refused by the route, Daniel refused by the code ("only the project owner"); Grace assigned. A past due date is refused (used 15 Oct) | fail, fixed (FX-4) |
| M1-08 architecture | Leo | 403: project Internal, the builder not on it until assigned. Then summary: two sources from the intent, format blank | fixed by FX-4 / note |
| M1-09 samples | Leo | Positions header found at row 9 (27 rows); only the first sheet is read | pass / note |
| M1-10 questions | Leo | Grain proposed "monthly by entity" (answered "monthly by portfolio"; pack still shows "one row"). History proposed none (plan expected type 2) | unclear |
| M1-11 pack | Leo, Anita | First pack: generic holdings and net worth tables, names cut ("..._for_e_..."), column definitions copied from the wrong KPI. Submit needs approved sheet mappings first (order differs from the plan). Anita 403 until Mei granted access | fail; access fixed (FX-5) |
| M1-12 plan | Leo, Anita | /plan/propose gave schedule daily 06:00; the pack route (/architecture/pack/plan, the screen's) gives monthly, 5th business day | plan used the older route; note |
| M1-13/14 upload, profile | Leo | Profiles: Positions header 9, Latest statements 7, Signed limits 10. Footer totals not detected | pass / note |
| M1-15 first load | Leo | 500 `KeyError: 'columns'` (e0b_tools.py:248) whenever the model is on | blocker, fixed (FX-1) |
| M1-16 mappings | Leo, Anita | Positions mapped to position_snapshots only; Valuation date ignored. Approved mapping could not be withdrawn or edited. Model mapped columns onto key fields | fail, fixed (FX-2, FX-14, FX-15) |
| M1-17 second load | Leo | Rejected: "Row count 27 vs 31" (the four footer total rows read as data). No footer value check, so G4 cannot be tested | data quality: workaround W-1 |
| M1-17 retries | Leo, Anita | 27 names held back for approval (new source); file then "already loaded" with 0 rows; ISO text date refused | fixed (FX-9, FX-16) |
| M1-18 counts | Leo | After fixes: position_snapshots 115 to 142; valuation_observations unchanged at 329 | pass (G5: positions only) |
| M1-19 limit v1 6% | Sofia, Daniel | Before: nobody could propose. After: Sofia proposes v2 (6%, from 1 Jan), self-sign refused, Daniel signs | blocker, fixed (FX-3) |
| M1-21 test run | Leo | Failed until FX-17 (silver steps read bronze tables nothing fills); then `run-20261012-124256-2fe7` ok | fixed |
| M1-22 limits | Grace, then Mei | Only the admin could run it; after FX-6 Mei runs it. July with 6%: see section 3. Screen run with "Files received by" = API proof run (`run-20261012-125516-2004`) | pass after fixes |
| M1-23/24 benchmark, go live | Leo | Benchmark text must be "label: number" per line and the name needs an extension. 7 "unexplained variances": the pack holds no limit figures. Anita accepted the variance; live `run-20261012-124323-e49b`, then `run-20261012-124837-8195` on pack v2 | pass with decision |
| M1-26 starter dashboard | Leo, Daniel | Four limit tiles all showed 290,850,433 (SUM of every position). Approval panel said "No reviewed run is on record" after a passing run | wrong number, fixed (FX-18, FX-19); panel text open |
| M1-27 delivery | Leo, Daniel | Channel made, submitted, approved by Daniel, delivery go-live by Leo (data team only). Outbox empty: not sent | pass |
| M1-28 cases | Sofia, Mei, Daniel | Sofia (participant) refused take and resolve. Mei took both July cases; closing needs a check; the checker's approval always set "explained" | fixed (FX-7, FX-8) |
| M1-29 consume | Daniel | Dashboard listed in Consume (walkthrough finding not reproduced) | pass |

### Months 2 to 4

| Month | Load | Pipeline runs (test, live) | Limits run (cutoff = receipt) | Cases opened | Actions |
|---|---|---|---|---|---|
| Aug | positions 27 rows; limits v1 re-upload refused as duplicate | `125558-1317`, `125651-d5c9` | `run-20261012-125602-4373` | Cedarpoint 31 Aug (stale) | Sofia took it, sent for check as stale_data, Daniel approved; Mei noted the Fund D chase |
| Sep | positions 27 rows; limits v2 quarantined (no table for it) | `125744-15bd`, `125801-a8ee` | `run-20261012-125805-66ec` (rule v3, 5%) | Harborview 30 Sep (real), Cedarpoint 30 Sep (stale) | Sofia: Harborview "real, cure by trim", asked Raj (after FX-20), Raj approved by note, case left open; Cedarpoint closed stale_data by Daniel |
| Oct | positions 27 rows; limits v2 duplicate | `130144-64be`, `130149-81d1` | `run-20261012-130153-322c` | Cedarpoint 31 Oct, Harborview 31 Oct | September Harborview closed "cured" (Raj checked); October Harborview closed "explained" (out-of-date figure); October Cedarpoint open with the true figure in a note |

Run IDs above are `run-20261012-…`. Every month the new benchmark sends the build back through Go live before a live run is allowed (note N-4).

## 3. Figures against the answer key

Tolerance: share 0.01 point, over-by USD 500. "Cutoff" is the run with the files' receipt time (the plan's proof run); "now" is the same check without a cutoff.

| Month | Line | Key | Product (cutoff) | Product (now) | Result |
|---|---|---|---|---|---|
| Jul | Harborview | 5.73% of 6.00%, headroom 0.27, inside | 5.73% of 6%, headroom 0.27, inside | same | pass (after FX-3; before it: breach against 5%, F1) |
| Jul | Listed equity | 80.04% | 80.04%, headroom 9.96 | same | pass |
| Jul | Cedarpoint | 57.38%, over 536,250, stale | 57.65%, over 601,500, stale | 57.38%, over 536,250, stale | key basis (D-1) |
| Jul | Hedge funds | 54.49% | 55.00% | 54.49% | key basis (D-1) |
| Jul | Pacific Rim | question, 1,084,000, 2.72% | same | same | pass |
| Aug | Harborview | 5.71%, headroom 0.29 | 5.71%, 0.29 | same | pass |
| Aug | Listed equity | 80.06% | 80.06% | same | pass |
| Aug | Cedarpoint | 57.38%, over 536,250, stale | 57.38%, over 536,250, stale | same | pass |
| Aug | Hedge funds | 54.56% | 54.42% | 54.56% | key basis (D-1) |
| Aug | Pacific Rim | 1,051,000, 2.66% | same | same | pass |
| Sep | Harborview | 5.75% of 5.00%, over 308,000, real | same (rule v3) | same | pass |
| Sep | Listed equity | 80.61% | 80.61% | same | pass |
| Sep | Cedarpoint | 56.50%, over 343,750, stale | 57.38%, over 536,250, stale | 56.50%, over 343,750, stale | key basis (D-1) |
| Sep | Hedge funds | 54.95% | 54.55% | 54.95% | key basis (D-1) |
| Sep | Pacific Rim | 1,122,000, 2.72% | same | same | pass |
| Oct | Harborview | 4.28%, inside | 5.75%, breach | — | wrong number (G-2) |
| Oct | Listed equity | 78.76% | 80.61% | — | wrong number (G-2) |
| Oct | Cedarpoint | 58.71%, over 895,000, real | 56.50%, stale | — | wrong number (G-2) |
| Oct | Hedge funds | 54.80% | 54.95% | — | wrong number (G-2) |
| Oct | Pacific Rim | 1,143,000, 2.70% | 1,122,000, 2.72% | — | wrong number (G-2) |

- D-1 (data, not product): the key uses the latest known statements, some of which reached the seeded warehouse after the key's receipt time (the amended Fund C statement in July, the August and September hedge fund and Cedarpoint statements). With the cutoff the product correctly ignores them. Either the key's receipt times or the seed's statement dates need to agree; the product is right on both readings.
- Stale ages are counted to the day the check runs (a deliberate rule, `tests/v1/test_e3b.py:201`), so a past month checked on 9 Oct (the pinned demo clock) shows Fund D at 192 days, not the key's 122 (Jul) or 183 (Sep). C14's "192" comes from this, not from the seed text.
- Cases by month: Jul 0 new after the 6% version (2 before it), Aug 1, Sep 2, Oct 2 (key: 1; the October Harborview case comes from G-2).

## 4. What was changed in the product (and its check)

All changes are uncommitted. Backend tests for every touched module pass (rules and recon 35, cases 109, mapping and load 46, planner and runs 61, consume, studio and delivery 113); UI typecheck and 117 UI tests pass. The full backend suite was started after the first fixes; its final count is in section 7.

| # | Kind | Change | Files | Check |
|---|---|---|---|---|
| FX-1 | bug | Mapping proposal with the model on crashed (`KeyError 'columns'`): read the fields with `columns_of` | `sh_platform/v1/e0b_tools.py` | live: proposal with model on; tests e0b |
| FX-2 | bug | "Valuation date" on a positions sheet maps to the position date | `e0b_tools.py` | `test_valuation_date_on_a_positions_sheet_is_the_position_date` |
| FX-3 | friction | A rule's owner proposes whatever their role; the data team, sponsor or admin may propose for them; neither the owner nor the proposer signs (proposer kept in `rules/proposers.json`). Who may read the register is unchanged (P15: not participants) | `e3_rules.py`, `e3a.permissions.yaml` | `test_owner_of_any_role_proposes`, updated e3a tests, p6 settings tests; live Sofia/Daniel |
| FX-4 | friction | The project owner (owner role) and the project's sponsor can assign and hand over steps | `p2_assign.py`, `p2.permissions.yaml` | live: Mei assigns |
| FX-5 | friction | The head of data reads every project that is not Restricted (they approve its pack and plan) | `g1_access.py` | tests g1 |
| FX-6 | friction | Business owners may run a check (route); the earlier rule that a read-only data group cannot run one is kept | `e3b.permissions.yaml`, `ui/src/v1/a5/ReconPage.tsx` | live: Mei runs on screen |
| FX-7 | missing | The administrator changes a colleague's role in Settings > People and access (not their own) | `k1_routes.py`, `k1.permissions.yaml`, `ui/src/v1/k1/PeopleRoles.tsx`, `SettingsPage.tsx` | live: Grace sets Sofia to owner on screen |
| FX-8 | friction | Sending a case for check carries its closing reason (stale data, action agreed, cured); the checker's approval keeps it | `e4_cases.py`, `e4a_routes.py`, `ui/src/v1/e4/*` | live: closes as stale_data and cured; UI "Closes as" |
| FX-9 | bug | A file whose rows were all held back can be loaded again once the names are approved | `e0c_load.py` | live |
| FX-10 | bug | A rerun for the same day updates the open case's amount and notes "Checked again: …"; limit results carry `max_pct` and `headroom_pts`; each limits run carries its Operations run id | `e3_recon.py` | updated e3b test; live |
| FX-11 | bug | A name token written as "PERSON 010" or "PERSON-010" is mapped back to the name | `sh_platform/egress/vault.py` | egress tests |
| FX-12 | bug | Intent goal line keeps whole sentences (no "the headroom in ."); "Needed by by" fixed; an open question is settled when its topic is answered | `i6_chat.py` | live goal line; i6 tests |
| FX-13 | bug | The figure guard keeps a formula's constant (× 100) | `sh_platform/agents/guard.py` | agents tests |
| FX-14 | friction | A wrong approved mapping can be withdrawn with a reason; the next load proposes a new one | `e0b_mappings.py` | `test_a_wrong_approved_mapping_can_be_withdrawn` |
| FX-15 | bug | The model may not place a sheet column on a key field (`id`, `*_id`) | `e0b_tools.py` | `test_the_model_never_places_a_column_on_a_key` |
| FX-16 | bug | An ISO text date (2026-07-31) loads without a date format | `e0c_load.py` | `test_an_iso_text_date_needs_no_format` |
| FX-17 | bug | A silver step fed only by bronze is left to the file load at run time (it was failing on a missing table, and would duplicate rows live) | `b6_run.py` | `test_a_silver_step_fed_only_by_bronze_is_left_to_the_file_load` |
| FX-18 | wrong number | The rules never place a share or a conditional count as a plain total (was SUM of all holdings under each limit) | `b6_span.py` | `test_a_share_or_a_conditional_count_is_never_a_plain_total` |
| FX-19 | wrong number | A tile reads only gold tables of the project's live plan, never one an older version built | `cx_dash.py` | consume tests; live |
| FX-20 | friction | Finance may be asked on a limit breach (its cure is a trade) | `e4_cases.py` | extended e4a test; live Sofia asks Raj |
| FX-21 | test tool | Optional received-by time on the Reconciliations screen; `serve_test.py --dist` so one tester can try a UI build without changing other testers' screens | `ReconPage.tsx`, `a5/api.ts`, `tools/serve_test.py` | live |

Not changed, on purpose: stale age on the run date (a tested decision); name aliases are never approved by the program (e2_match's rule; bulk approval recommended); `slug()` cuts table names mid-word (changing it renames live tables); a read-only data group still cannot run checks (uc2-02).

Workarounds kept (data quality, per Nitin): W-1 the positions workbooks carry a "Portfolio totals" block after one blank row; each month a copy without it is loaded (`nofooter.py`). The administrator file should end at the data, or the profile's own last data row (36) should bound the load.

## 5. Open gaps after run 1 (G-1 and G-2 are built in run 2, section 0)

- G-1 Limit figures on the dashboard. The limits check (e3_recon) is the only place the limit figures exist; Span's pack has no limit table, so Lumen's tiles have nothing true to show. Proposal: write each limits run's results to a gold table (portfolio, rule, exposure, maximum, headroom, cause, over-by, run id) and let Lumen read it. This is a new table, so it needs a model change and Nitin's approval.
- G-2 October values never reach the limits check. The check reads only valuation_observations; the positions sheet loads into position_snapshots; the Latest statements sheet cannot be loaded at all (the load reads only a file's first sheet). July to September matched only because the seed already held those valuations. Proposal: (a) load a named sheet, so Latest statements feeds valuations; (b) a signed rule for the limit basis: securities at the administrator's month-end value, funds at the latest known statement (the key's basis). The basis is a business rule, so it needs a signature.
- G-3 Signed limits are still typed by hand (M1-19, M3-01); the signed workbook is quarantined each month. Recommend reading it as a proposed rule version with a diff.
- G-4 No early-warning band (C11), no estimate flag (C12): still missing, as the plan expected.
- G-5 Case per month for a standing breach (C10): confirmed (July, August, September each opened a new Cedarpoint case).
- G-6 Two seeded cases dated 9 Oct remain open with no owner.

## 6. Notes and smaller findings

- N-1 Approval panel "What Lumen checked" says "No reviewed run is on record" after passing runs (walkthrough finding reproduced).
- N-2 Tile titles are mangled from the KPI names ("Eg liquid single name exposure"). Tiles that cannot read their table say "Please try again", which is the wrong advice.
- N-3 The Checks status note says "1 of 6 steps ok" when five steps are filled by file loads.
- N-4 Every new benchmark sends the build back through Go live; a monthly benchmark therefore needs a monthly Go live. A plain monthly run should not need it.
- N-5 Go live already starts a live run; a manual live run straight after it doubles the production runs.
- N-6 The pack's grain shows "one row" though the person answered "monthly by portfolio"; history type 2 not proposed for asset class or manager.
- N-7 The server stopped twice with no error in its log (once between sessions, once mid North call, exit 255). Started detached it stayed up for the rest of the run.
- N-8 The demo clock is pinned to 9 Oct 2026; as-at 31 Oct and a 3 Nov cutoff were accepted with no warning.
- N-9 The UC8 break (Northwind 1,800 shares, 75,870) shows under Trades against the administrator and does not touch a limit figure (planted issue 10: pass).

## 7. Verdict for a risk owner

What Sofia can use each month now: one check per month on the screen, with the files' receipt time; each breach split into real and stale, with the stale inputs named; the case in her name, closed with her reason after a second person checks it; the limit version she proposes and the CIO signs, applied from the right date; Pacific Rim kept out of every bucket as a question.

What she cannot use yet: October-style months where new valuations arrive in the administrator file (G-2), and a dashboard that shows the limits (G-1). Until both are decided, the monthly limit figure is trustworthy only when the statements already sit in the warehouse, and the CIO reads the result on the Reconciliations screen, not in Consume.

Testing done (targeted, per Nitin on 13 Oct; the full suite was stopped on request): every module changed in runs 1 and 2 passed its own tests after its last edit: rules and recon (e3a, e3b incl. the limit-basis and limit_results tests), cases (e4a/b/d), mapping and load (e0b, e0c), pack and plan (b6, b6_run, b10 / fixc / v6 pack tests), studio and consume (b7, cx incl. the share-tile test), access and assignment (g1, p2, k1), egress and agents, p6 settings; UI typecheck and 117 UI tests. The last complete full-suite run (12 Oct, mid-way through run 1's fixes) was 4,188 passed, 2 failed; both failures were fixed and their files pass. No full-suite run covers the final code.
