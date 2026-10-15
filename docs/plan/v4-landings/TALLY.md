# TALLY landing: the data analyst of the Action centre

Nitin, 9 Oct: the Action centre had no agent of its own. On the Entity B cash break the "investigation agent" said the facts show no changed manager valuation (wrong for cash), "Sources: none found", "the model is off", every trail step read "Not recorded", and the page said "Something went wrong on our side". Tally is the fourth agent beside North, Span and Lumen and lives in Action.

## What changed
- **`sh_platform/v1/n1_tally.py`** (grown from `e4_investigate`, which is now a thin alias so old callers work). `explain(plane, viewer, case_id, question=None, record=False)` returns `summary`, `findings` (each with a figure and source chips), `next_steps` (who does what), `missing`, `worded_by`, and `answer` when a question is asked. By case kind:
  - **Cash break**: both sides (administrator against trading export) read from the recon run's cutoff, the signed `cash_tolerance`, how far over it, the earlier days (new today, or carried since when), how each side moved, and candidate items the program ranks: one item equal to the difference, a set of two or three, a duplicate, an item on one side only (timing), a foreign-currency line. Each candidate carries its source row and document.
  - **Trade break**: the two rows side by side, the field that differs (quantity, price, settlement date, amount, missing at one side) and the money at stake, with the USD equivalent at the rate the check used.
  - **Limit breach**: exposure, the signed limit, every input with its age and status, and the cause: real breach, stale data, or a missing classification.
  - **Revision, late statement, capital call**: the statement chain or the notice, days and amounts, the commitment called and uncalled.
- **The model never writes a digit.** Router key `tally` (added to `model_modes.yaml` agents). The model gets placeholder names and one-line meanings only, and replies `{"summary": ...}` or `{"answer": ...}` with `{placeholders}`; the program fills them. A reply with a digit or an unknown placeholder is dropped for the rules' wording. Model off: a correct rules wording per kind. The model's wording is kept per case and facts (`context/tally_wording.json`), so a page view does not call it twice.
- **Routes** (`e4a_routes.py`, all six roles in `e4a.permissions.yaml`): `POST /api/v1/cases/{cid}/explain` (Tally's proposal added to the history, by Tally, not the viewer; the same words are not added twice), `GET /api/v1/cases/{cid}/tally` (read-only analysis for the panel), `POST /api/v1/cases/{cid}/ask {question}` (read-only; anyone who can see the case). Tally only proposes; the case owner acts. A request to change a figure is refused with the e4_guard wording.
- **The "Something went wrong" error**: the failing call was `POST /api/v1/cases/{cid}/explain`. The server log shows it took 20 to 22 seconds (the model call) and then died on a DuckDB "file is being used by another process" error when the agent run was recorded afterwards, which the screen shows as a server error. Fix: the save is retried three times, and if the file is still busy Tally returns its analysis with `saved: false`; any other failure inside Tally becomes a plain 409 sentence ("Tally could not look at this case just now. Please try again in a moment."), never a 500.
- **Recon cases get a real trail** (`a5_trail._case` calls `n1_tally.recon_trail`; two small edits to `a5_trail.py`, with `Decided` and `Shown` added to the step labels): Source (administrator export, trading export), File, Read (sheet and row), Checked (recon run, rule version, tolerance), Decided (case opened, materiality rule version), Shown (the case on the Action desk). Limit breaches show the valuation sources, the limits check and the recorded cause. Cases that did not come from a check keep the old trail.
- **Case page** (`ui/src/v1/e4/TallyPanel.tsx`, `CasePage.tsx`, `api.ts`): "Tally, the data analyst" panel with the summary, findings with source chips (a statement links to the evidence page; a stored fact opens "Where is this from?" in place), next steps, what is missing and an "Ask Tally" box. "Investigation agent" is gone from the screen: the button reads "Ask Tally to write this up", the recorded proposal reads "Proposed by Tally", and the history names Tally. Settings lists Tally.
- **`skills/tally/`** (copied from `skills/investigation/`): playbook (what Tally does and never does), questions, traps, examples. `skill_loader` has a label for it; `SL.agents()` is now four.

## Reuse check
`e4_investigate.py` (the only investigation or analyst agent in this repo) was copied and grown; the earlier repo (earlier-repo) has no investigation agent (searched `*.py` outside `.venv` for "investigat": only `emitters/signals/actions.py`, unrelated). Candidate, trail and recon logic reuse `e3_recon` (`_convert`, `_bucket_of`, `last_runs`), `e1_asof.snapshot`, `e3_rules.current`, `k6_liquidity.commitments` and `e4_guard.check_request`; nothing was rebuilt.

## How to see it
1. Log in as Mei Chen (Operations analyst). Action, Cases, open "Cash differs · Entity B · 2026-10-08" (CASE-0003 in the seeded data; the number varies by database).
2. The "Tally, the data analyst" panel shows 880,400 USD against 868,000 USD, 12,400 USD, 7,400 USD over the 5,000 USD tolerance, new today (both sides agreed on 7 Oct), with source chips on each side. Click a chip: "Where is this from?" opens under the findings.
3. Type "is this timing?" in "Ask Tally" and press Ask Tally. The seeded files carry balances only, so Tally says no individual item is recorded and shows how each side moved since 7 Oct, and the missing list says what to ask for.
4. Click "Where is this from?" on the case: Source, File, Read, Checked, Decided, Shown all read from the recon run.
5. "Ask Tally to write this up" adds one proposal to the history, authored by Tally. Try the Northwind trade (quantity differs by 1,800), the Cedarpoint limit (stale data) and the Harborview limit (real breach).

## Tests and results
- `tests/v1/test_n1_tally.py`: 16 passed (seeded Evergreen warehouse): Entity B 880,400 against 868,000, 12,400 over 5,000, new today; candidate items (exact match first, duplicate, foreign currency, one side only) with sources; "is this timing?"; trade breaks name quantity / price and the money, unmatched trade; limit stale vs real; model-off wording for all kinds; a participant (Sofia Reyes, Risk) may ask and the case row and history are unchanged, a refused request, empty question 400, no access 403, all six roles in the permissions yaml; one proposal by Tally, not duplicated; a busy warehouse is told not raised; model wording filled by the program; digits and unknown placeholders from the model dropped; model answers; the recon trail for cash, limit and trade cases.
- `ui/src/v1/e4/tally.test.tsx`: 4 passed (panel content and chips, trail chip opens the trail, Ask posts the question, failure shows a sentence). `ui/src/v1/e4/e4.test.tsx` updated for the new wording (all pass).
- Existing: `test_e4a`, `test_e4b` (all legacy revision behaviour kept), `test_e4d`, `test_a5`, `test_e0b1`, `test_t1`, `test_x5`, `test_e3b`, `test_e3d`: 152 passed. `test_v3_g1.py` updated to four agents; its two failures (`test_skills_load_under_cap_whole[north]` extra `sop.md`, `[lumen]` extra `managers.md`) are older and not caused by Tally.
- `tsc --noEmit`: clean. Full `vitest run`: 1492 passed, 3 failed, none in this work (`look.test.tsx` stylesheet checks x2 and `WallView.test.tsx`, files of the shell restore).
- Also updated: `tests/e2e_10uc/uc2a_2.py` (the old button and heading names; not run, it needs a browser).

## Open points
- The seeded cash files carry balances only, so the candidate-items list for Entity B is empty until transactions or cash movements for that entity are loaded; the panel then says what to ask for. The test adds items to prove the ranking.
- Tally wording for a "late statement" case is basic (the latest statements and days after the period); no case of that type exists in the seed.
- The model path was tested with a stubbed model only; no live call was made.
- Backups: `.sh-tmp/*.bak-tally`.

## Review (9 Oct, reasoning review)
**Verdict: pass, with the open items below.**

I checked each definition-of-done line against the code and the tests:
1. **`n1_tally.py`:** all six case kinds are built by the program, and `e4_investigate` is a 3-line alias. Every sum, difference, tolerance test, earlier-day comparison and candidate ranking is done with Decimal from recorded rows. The model gets only placeholder names with one-line meanings, the case kind, and the question (digits stripped, wrapped as untrusted). Its reply is dropped if it has any digit or an unknown placeholder. Router key `tally` is in `model_modes.yaml`. `route()` and `run_agent` follow the same egress path as before, and the names are registered for tokenising.
2. **Routes:** `/explain` now runs Tally. `/tally` and `/ask` are read-only. The permissions yaml gains exactly two lines, both for the same six roles, so default deny still holds. A request to change something is refused through `e4_guard`. The participant test proves the case row and history do not change.
3. **Recon trail:** Source, File, Read, Checked, Decided and Shown come from the run record. `a5_trail.py` has two small edits, and they are still there after the other workflow's restore.
4. **Panel:** the summary, findings with chips, next steps, what is missing and "Ask Tally" are on the page. "Investigation agent" no longer appears anywhere on screen. `/explain` failures become a plain 409 sentence, and a busy warehouse is retried.
5. **`skills/tally/`:** it states what Tally never does (no verdict on a manager or person, no arithmetic, no digit, no action on the case).
6. **Tests and 7. this write-up:** both present.

**Fixed in review** (`n1_tally.py`, backup in `.sh-tmp/n1_tally.py.bak-tally-review`):
- **Rules-wording note:** the proposal's note said "Worded by rules only (the model is off)." That is also wrong when the model is on but its reply was dropped, which is Nitin's complaint. It now reads "Worded by rules only, from the recorded facts."
- **Wording when neither side reported:** this case read "Only the neither side reported cash…" and now reads "Neither side reported cash…".
- **Dead code:** removed an `if …: pass` block in the cash path.
- **Trade date fallback:** it now uses `wh.now()` rather than `date.today()`, like the rest of the module.

**Re-run after the fixes:**
- `pytest tests/v1/test_n1_tally.py test_e4b.py test_e4a.py test_a5.py`: 44 passed.
- Earlier full set (n1, a5, e4a, e4b, e4d, v3_g1, e0b1, t1, x5, e3b, e3d): 168 passed, 2 failed. The 2 failures are `test_v3_g1` `[north]` and `[lumen]`, caused by the extra `sop.md` / `managers.md` files. They are not Tally's.
- `vitest run src/v1/e4`: 9 passed.
- `tsc --noEmit`: clean.

**Open items:**
- **No live model call yet:** the model path was tested only with a stubbed model. The first live `/tally` view of a case waits for one model call (about 20 s on this box). After that, the wording is reused from `context/tally_wording.json`.
- **Busy-file cause not found:** the underlying "file used by another process" DuckDB error is only retried. Which second process holds the warehouse open (a script, or a second server) is not found yet.
- **Entity B has no candidate items:** the seeded data has only balances for Entity B. Load the cash movements to see them live.
- **Late-statement wording** is basic.
- **e2e test not run:** `tests/e2e_10uc/uc2a_2.py` needs a browser.
