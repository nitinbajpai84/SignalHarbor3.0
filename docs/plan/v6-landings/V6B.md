# V6B: the design pack, the benchmark check, the starter and the Pipelines page (11 Oct)

Card V6B-pack-and-benchmark. No model call anywhere (the tests run with `SH_MODEL_PROVIDER=off`). Backups of every edited file are in `.sh-tmp/<name>.bak-v6b`. Nothing was committed. `data/` and ports 8400 and 8504 were not touched; the seeded company used for the checks lives under `D:\Temp`.

## What changed

1. **The design pack carries the full target model and a benchmark block (H4, H5).**
   - `b6_span.reporting_tables` draws holdings by fund and month and net worth by entity and month from the company's valuation records, when the intent names those KPIs and the sources are not mapped yet. `benchmark_table` now gives two typed tables: returns by portfolio and month, and the weight each leg of the signed benchmark carried each month. Columns are typed: `DATE`, `DECIMAL(18,2)` money, `DECIMAL(9,6)` rates, `VARCHAR` names (`b6_plan._out_type` reads a cast's type; before, a cast was always `varchar`).
   - Each gold table in the pack shows grain, keys, type 2 columns (manager name and asset class on holdings) and owner. The silver list names the company-model tables the gold tables read, and the one that is extended (instruments).
   - `pack["definitions"]`: one definition per figure (portfolio return, benchmark return, net worth) and per other KPI, with its source ("Signed in the intent", "Signed: benchmark version 1", "Proposed by Span"). Each gold column carries its own definition, not a copy of the first KPI's. A definition can be corrected like any line (section `definition`).
   - `pack["benchmark"]`: portfolio, signed benchmark code and version, month, the figures compared (portfolio return, benchmark return, difference) and the plain names of the legs. The code comes from the approved definitions (named in the intent, else the best word match, else the only one); the portfolio from the intent's words (else the first the engineer may see); the month is the last month with recorded values. Correctable (section `benchmark`). The benchmark KPIs no longer become open rows a person settles in words.
   - `pack["key_figures"]` (money figures: total holdings, each fund, net worth, each entity). `apply_to_plan` writes `benchmark`, `key_figures` and `own_batches` onto the plan.
   - UI (`ArchitectureStep`): gold tables as a table (table and columns, grain and key, type 2, owner), a Definitions panel, a Benchmark check section, Compare versions (always shown; waits for a second version; pick which version to compare with), "Next: Open the mapping sheet".
2. **The builder compares the run with the report line by line using that block.** `b11_builder` reads the plan's key figures for the benchmark month, matches the report's "Office blend" to the benchmark return through its code, labels each line matches, explained (a revision with its evidence) or unexplained, and checks each leg of the benchmark. `b9_verify.comparison` reads a weights table that names each leg ("... plus spread") so the sleeve has its own weight.
   - **The walk story on a fresh seed, no figure in product code:** `tools/seed_walk_benchmark.py` (usage in its docstring) plays it through the product's functions on a company seeded by `tools/seed_10uc.py`. Version 1: the architect corrects one formula so the sleeve weight is read as the smallest weight in the benchmark (28%); the head of data approves; the builder runs on a copy. Result: Portfolio 4.1667% matches 4.17; Office blend 2.6322% against 2.71 unexplained; sleeve 28% against 30 unexplained; the difference 1.53 against 1.46 unexplained; the amended Evergreen Growth I line explained. The builder sends it back; the formula is corrected to read the signed weight; pack version 2 is approved; the builder reruns by itself: 2.7072% (2.71) against 4.1667% (4.17), difference 1.46, no unexplained line. The only typed numbers are the report as issued (the walk's input); the holdings line is read from the 3 Oct issued report.
3. **Lumen's starter (H10).** Rates show as percentages with two decimals (`Chart.tsx` `asRate`, axis, legend and tooltip `.2%`, so the bar axis no longer repeats "1%, 1%, 0%, 0%"). The side panel names the starter's tiles instead of "Lumen has not suggested any tiles". The returns table is by portfolio, and the starter reads the pack's portfolio (else the portfolio with the longest history), so "Portfolio return" is 4.17% for EG-LIQUID rather than every portfolio added up (the old ±0.28 trend came from adding portfolios). The trend plots one point and one label per month (`timeUnit yearmonth`, `%b %Y`). Number tiles say "in the latest month".
4. **Dark theme tokens.** `.ds-dark` in `styles/design.css` pins the dark values; it wraps the Architecture step, the builder on Pipelines and the studio when a starter is open.
5. **Pipelines page.** The builder flow is first. The stage cards, run controls and `VerifyPanel` sit in a "For engineers" fold. For a plan drawn from a pack (`own_batches`), the control totals are those of the plan's own sources, not the company's. "Next run" reads the schedule once the plan is live. The builder's PDF line says "Reading N marked fields from each statement (M on file for the company)".
6. **North size test.** `i6_chat.system_prompt` is now the one function that builds the system prompt (the chat uses it); `test_north_largest_system_prompt_leaves_two_thousand_characters_under_the_gateway_limit` measures it plus the loop's rules over the default goals and every template: about 17,930 of 20,000 characters (it was 19,413, 587 of headroom). About 1,400 characters were removed by cutting repeats: sentences the system rules already say, two worked lines, wording in the playbook, traps and tool lines. The extraction and benchmark rules keep their content.

## Results

- Python: the whole `tests/v1` run, then the failures fixed and re-run. 6 tests failed on the first run, all for the new shape of the benchmark table (per portfolio, two tables): `test_k7` (2), `test_seed_10uc` (1) and `test_x1` (3). The first three were updated to the new shape; the demo seed (`tools/seed_v3_demo.py`) keeps the returns table only, so `test_x1` passes unchanged. After the fixes: `test_k7`, `test_x1`, `test_seed_10uc` 73 passed; `test_v6b_pack_and_benchmark` 8 passed; the b6, b9, b10, b11, review, North and template tests 95 passed; `test_h10_starter`, `test_lumen_w2`, `test_cx` 59 passed. `tests/egress`, `tests/intents`, `tests/agents` and `test_skill_loader_retired` pass (three `tests/agents` files fail to collect when run in parallel with `tests/v1` for a duplicate-name reason; alone they pass).
- Vitest: `src/v1`, `src/pages`, `src/design`, `look.test.tsx`: 117 files, 659 tests passed. New tests in `b10`, `b8` and `b7`; `cxui`/`b7` expectations changed to two decimals.
- `tsc --noEmit`: clean.

## Still different from the designs or open

- The holdings table is by instrument. The issued report's "Evergreen Liquid Book 41,200,000" is one position of the liquid portfolio, so that line has no matching fund row, and a "Total holdings" compared with the report's total is not meaningful for the seeded data (the design's 57,780,000 is a placeholder). The walk compares the Fund A line, which is explained by its amendment.
- The pack's portfolio return does not remove net flows. The pack says so in its notes when the signed definition mentions flows; it is exact for months with none (September has none).
- Net worth is holdings by entity (cash and loans are not in the company model); the pack says so in the table's purpose.
- The roles line under the page title (H4) is not drawn on the Architecture page. The mapping sheet (H5) is the existing table, now on the dark tokens.
- The weights table is a fourth gold table beside the three in the design; the builder needs it to check the legs.

## Review (Opus, 11 Oct)

**Checked.** No figure of the walk is in product code. A grep for 2.71, 4.17, 2.63, 1.46, EG-LIQUID, EG-OFFICE-BLEND and Office blend over `b10_pack`, `b6_span`, `b11_builder`, `b9_verify`, `cx_lumen`, `ArchitectureStep` and `PipelinesRoom` finds none. The report's "Office blend" matches the benchmark return through the signed code's words. The 28% slip and the 30% fix are formulas that a person types in `tools/seed_walk_benchmark.py`, and the report as issued is that script's input.

Access and maker-checker:
- Pack edits (including the new `definition` and `benchmark` sections) need the data engineer seat.
- Approval needs the head of data, and the person who made or changed a version cannot approve it.
- The benchmark check reads through `k7_routes.monthly` with the viewer, so a portfolio the viewer may not see is refused.
- Lumen's portfolio filter is quoted (`where_of`).

**Fixed in review** (backups: `.sh-tmp/<name>.bak-v6b-review`):
1. **H8, the Difference line.** In version 1 it counted as a third unexplained variance. When the portfolio return matches and the gap is the benchmark's own gap, it now reads "Explained: Follows the benchmark return", as H8 says (`b11_builder.variance`). Version 1 now has 2 unexplained lines, the benchmark return and the sleeve leg. Going live is still blocked while the benchmark line is unexplained. The test is updated.
2. **H4, the roles line.** The roles line under the Architecture page title is now drawn: business owner, sponsor, head of data, data engineer. It comes from the project's people (`b10_pack.summary` → `people`).

**Still open** (not fixed; each needs a decision or a larger change):
- The run's portfolio return is not compared. "Portfolio return" in the builder's comparison is the signed calculation (`k7.monthly`), not the run's gold `portfolio_return` column. Only the benchmark weights come from the run. A broken portfolio-return formula in the pack would not show as a variance.
- Changing the benchmark code in the pack (section `benchmark`) leaves the stale `version` and leg `names` of the first code.
- "Next run" shows the frequency and time ("monthly at 06:00"), not a date.
- H8's headline says 1 unexplained variance and the product says 2. The product also counts the sleeve leg; that is a defensible difference, kept.

**Results after review:**
- `pytest` `test_v6b_pack_and_benchmark`, `test_proposal_speed` and the b10/b11 tests: 27 passed.
- First full `tests/v1` run (with `-x`): 1291 passed, then 1 failure. `test_proposal_speed` is a timing test; it failed while vitest ran alongside and passes alone.
- `tsc` clean. Vitest b10, b11 and b8: 26 passed.
- Full `tests/v1` (no `-x`, 6 workers): 1690 passed, 4 skipped, 1 failed. The failure is `test_proposal_speed`, a timing assertion under parallel load; it passes alone, so it is not a V6B defect.
