# W05: North drafting the intent of work runs through the tool loop

## What changed
- `sh_platform/v1/i2_north.py` `_ask_model` now takes `viewer` and `iid`. With a person it builds the registry from `tools_for(plane, viewer, "north", module_id="m1_intent", iid=iid)` plus `north_tools.register` and adds `north_tools.PROMPT_LINE` to the prompt, then calls `run_agent` as before (still one model JSON answer: section, met, unclear, follow_up, next_question).
- Drafts from `propose_intent_section` / `propose_process_step` come back as `got["proposed"]` (`_proposed`) and `turn` applies them with the existing `apply()` after the section for the current need. A step already on the map (same name) is skipped. Sections for other needs land too.
- Rules fallback, thread, SOW shape and replies unchanged. No viewer: loop runs with no tools, as before.
- Backup: `.sh-tmp/i2_north.py.bak-W05`.

## See it
Intent Centre thread with the model on: say "Arjun reconciles the file by hand" while North asks about the process; the step appears in the SOW. Settings > Agent runs shows the tool steps of the run.

## Tests
`tests/v1/test_north_loop.py` (+2, 11 total): loop run through `turn` applies model section plus proposals without duplicates, tools offered; model-off fallback unchanged. With `test_i2.py` and `test_k2_north.py`: 15 passed.

## Review
Verdict: pass. Reran `test_north_loop.py`, `test_i2.py`, `test_k2_north.py`: 15 passed. Diff against the backup touches only `i2_north.py` (plus the test file and this note); no stray files. Rules fallback and no-viewer path unchanged; proposals are applied through the existing `apply()` with duplicate steps skipped. No wording defects (no UI copy added). Nothing fixed.
Open items: `tsc` not run (no TypeScript change, fine); the "Settings > Agent runs" line in "See it" was not checked in the browser.
