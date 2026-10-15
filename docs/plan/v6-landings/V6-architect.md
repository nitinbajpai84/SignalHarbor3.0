# V6-architect: the Architecture step (H1-H6) and the North gaps

Spec: `docs/plan/BUILD-FLOW-V6.md` step 2, designs H1-H6, `w3-landings/WALK.md` gaps 1, 2, 3 and 7. Nothing was committed. No model call anywhere (stub or off in tests).

## Built

**North: the intent system map (never ask twice)**
- A source row in the intent now carries `format` and `channel` (upload, mailbox, sftp, sharepoint, database) beside `holds`, `owner` and `arrives` (the frequency). North's "inputs" goal asks how it arrives and how often when a system is named; `i6_chat.merge` normalises the channel and never lets an unknown word replace what was said. The prompt grew by about 100 characters only; the gateway's 20,000 limit is close (test_i6a asserts it).
- The signed intent is never rewritten. A later correction (by the engineer, from the pack, or an answer to "how does it arrive") goes to `intents/<iid>/system_map.json` with who, when and what the intent said; `b10_pack.systems_of` is the one reading (the intent overlaid with corrections). The builder (V6-builder) calls `b10_pack.correct_system` when a connection differs, and the pack changes with it.
- Walk gaps: (1) the closing summary names the template sections that block signing and drops "Nothing is left unclear / press Sign" while they are empty (`_sign_gaps`); (2) the benchmark line counts figures on the benchmark sheet, and the raw API path is gone ("A copy ... under Download a copy"); (3) `ChangeBar.lineLabel` words a changed line as "Goal: needed by"; (7) `short_title` gives a short project name from a long first sentence ("Report of how our private funds"), also used by `e0a_catalogue.slug_of`, so table names are short too (30 characters as before). North is also asked in the prompt for a short title.

**b10 Architecture pack** (`sh_platform/v1/b10_pack.py`, `b10_routes.py`, `b10.permissions.yaml`, UI `ui/src/v1/b10/`)
- 2a `summary`: the signed intent, process map, catalogue, connectors (c5 specs) and landed files (b2 scan); each system "from the intent" with status connected / landed / sample / never seen and what the scan found; `confirm_systems` is the Confirm button.
- 2b `questions`: only what is missing, each with a default: how a source arrives (only when the intent gave no channel and nothing is connected or landed), grain (only when the KPIs do not name period and "by"), history (candidates are text columns of the model whose words the intent uses; default none), checks (from the process map controls, tolerance read from the text), definitions (only unsigned KPIs), freshness (from "needed by"), narrower access (only when the intent has an access rule with a narrower scope). `accept_all` takes every proposal.
- 2b samples: Excel/CSV through `e0c_landing.receive/profile` plus the rules mapping proposal; a PDF is kept in `documents/`, its lines come back, the person marks a field on a line (name, format); the marked fields are stored with the sample and upserted as a confirmed x5 type for the e2 reader.
- 2c `generate`: versioned `pack-v<n>.json` in the b6 build folder: target model (silver used/extended, gold with columns, types, grain, keys, type-2 columns, owners, definitions), catalogue (every table and column, meaning, source, sensitivity), ETL mapping sheet (source field -> bronze -> silver -> gold with words and a per-column formula), rules (checks with tolerances, history, refresh, late data, benchmark), sources. Rules first via `b6_span.draft_plan` (new, split out of `propose_plan`); no model is asked for the pack itself. Rows a person must settle (no mapping for a system, PDF without marked fields, a KPI no table fits) are marked and stop the send.
- Correctable lines: `edit(section, key, changes, note)` with a list of allowed fields per section; every change keeps who, when, before, after. A draft is edited in place; a proposed pack goes back to draft; an approved pack stays locked and a correction forks the next draft version. A formula (SQL expression, checked) changes the gold table's SQL.
- Approval: `submit` (engineer) then `approve` / `reject` by the head of data seat (`seats.HEAD_OF_DATA`, added by V6-design-fixes), never the person who made that version; an earlier approved version becomes superseded. `diff(a, b)` and `history`.
- `apply_to_plan`: the latest approved pack draws the b6 plan (its gold tables and formulas replace the rules' gold, the schedule comes from the pack, `pack_version` is stamped) and saves it as the next plan version for the existing plan approval. A formula the plan check refuses stops it with the reason.

## How to see it
Route (until integration re-points the step tab): `/centre/build/p/<project id>/architecture/pack`. As the engineer (Leo): What I already know, The few questions (Accept all), Samples, Draft the design pack, correct lines, settle amber rows, Send to the head of data. As Anita (head_of_data): Approve version 1 (or Send back). Then the engineer: Draw the build plan from this pack.

## Tests
- `tests/v1/test_v6_b10_pack.py`: 17 passed (summary, minimal questions, system map, Excel sample, PDF marking, pack content, history, corrections, maker-checker, locking and forking with diff, system correction, plan from the pack, refused formula, unsigned intent, North channel/closing/short title).
- `ui/src/v1/b10/b10.test.tsx`: 6 passed; `ui/src/v1/workbench`: 10 passed; `tsc --noEmit` clean for my files.
- Also run green: test_i6a (4), plus the batch listed in the summary reply. `tests/v1/test_b6.py` has 4 failures that come from V6-design-fixes (b6_plan now needs the head_of_data seat; the test viewer is only `analyst`), not from this card.

## Mount lines (integration)
- None for Python: `sh_platform/v1/__init__.install` finds `b10_routes.py` and `b10.permissions.yaml`; `ui/src/v1/index.tsx` globs `b10/routes.tsx`.
- `ui/src/v1/b8/routes.tsx` (or router): make the step tab `build/p/:projectId/architecture` render `b10/ArchitectureStep` (inside `InStep current="architecture"`, same Gate) and keep `ArchitectureRoom` as a "Model" view; my route `.../architecture/pack` stays so both work. `ui/src/v1/b9/steps.ts` needs no change.
- Action/Overview cards may link "Answer the questions" to `.../architecture/pack`.

## Differences for Nitin's approval
1. The H3 sample page marks a PDF field by choosing a text line of the statement and naming it (no drag box over the rendered page).
2. The head of data approves the pack, and then the existing plan approval still applies to the plan drawn from it (two clicks, not "the builder starts by itself"); folding them is a one-line change in `approve` once Nitin agrees.
3. Type-2 columns that are in no silver table are recorded as a note ("a model change adds it"), not turned into a model change automatically (E0a takes one column per proposal).
4. Gold formulas keep sqlglot's upper-case keywords (`SUM(...)`).
5. The "Assign to Leo Park" button of H5 is not built (assignment is the existing Action flow).

## Open items
- `Compare versions` compares the last two versions only; a picker is not built.
- Hand-typed ChangeBar section words for sections not listed ("Kpis" becomes "KPI"; others show the raw section word capitalised).
- Free-tier model replies were not exercised (no model calls were made).

## Review (11 Oct, reviewer)
Checked against BUILD-FLOW-V6 step 2 and "never ask twice", maker-never-checker, the permission file and the tests.

Fixed in review (backups `.sh-tmp/b10_pack.py.bak-v6-review`, `.sh-tmp/test_b10.py.bak-v6-review`):
1. **Maker-checker gap.** Approval only refused the person who drafted the version. Anita holds the data team seat too (head_of_data is held with analyst), so she could correct lines of Leo's draft and then approve them. Edits now carry `by_id`, submit records `submitted_by_id`, and `makers(pack)` (drafter, every corrector, sender) may not approve; `view.can.approve` uses the same set. Test: `test_head_of_data_who_corrected_a_line_cannot_approve_it`.
2. **Unchecked answers.** `answer` stored any value for grain, history, checks, definitions, freshness and access; a string for freshness, or a check without an id, then broke `generate` and line edits with a server error. An answer must now have its proposal's shape, and each check needs an id and words (400 otherwise). Test: `test_an_answer_must_fit_its_question`.
3. A PDF sample whose name matches a different file already in `documents/` no longer overwrites it (a short content hash is added to the name).
4. Removed a dead clause in `_silver` (`any(... for g in [])`).

Tests after review: `test_v6_b10_pack` 19 passed, `test_b6` and `test_i6a` pass (the builder's "4 failures in test_b6" is stale: it passes now); g1 gate, role matrix and talk-to-all 44 passed with 1 failure that is not this card (`tests/intents/test_role_matrix_intents.py` lists roles without the new `head_of_data` role from V6-design-fixes; that card or integration adds it). UI `b10.test.tsx` 6 passed.

Seen and left: the H5 "Assign to Leo Park" button and the two-click approval are listed as differences; compare versions only shows the last two.
