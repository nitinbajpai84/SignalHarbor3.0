# INT1: Tally wired to memory, proposals on the panel, next steps from a fixed set (9 Oct)

Edited (backups `.sh-tmp/*.bak-int`): `n1_tally.py`, `tally_tools.py`, `ui/src/v1/e4/{TallyPanel,CasePage}.tsx`, `ui/src/v1/e4/api.ts`, `tally.test.tsx`, `tests/v1/test_tally_loop.py`. `mem_wire.py` not edited.

- **Memory.** `_model_text` builds one `mem_wire.Wire` per turn: focus `{case, project}` (project = the project of the intent the case came from, `p1_project.for_intent`; empty when none, then the talk stays the owner's), conversation id = case id, `cap` = room left under the 20,000 limit. Sections go into the context, the trace gets the context step. `mem_context.after_turn` runs after a question (ask) with the same focus, so the talk is shared with the project team.
- **Panel.** "What Tally proposes": explanation (text, candidate item chip, source chips) and next steps with who. The case owner (server `can.explain` and `can.submit` or `can.take`) gets "File these proposals on the case", which posts the existing `/explain` route; others read only.
- **Next steps.** `propose_next_step(who, action, note)`: who from `WHO`; action one of ask_administrator, ask_trading_desk, wait_for_file, book_adjustment, close_as_timing, raise_policy_question (the program writes the sentence); note only `{placeholders}` plus punctuation, no digit, no words. The same note rule now covers `propose_explanation`. A digit-free planted instruction is refused (test).

Tests: test_tally_loop 11 (2 new, 1 reworked), test_n1_tally, test_context_wiring, test_e4a/b/d; vitest src/v1/e4 11 (2 new); tsc clean.
Limits: "case owner" on the panel follows the server's buttons (an admin or someone who may take the case); `after_turn` only after a question, not a page view.

## Review (9 Oct)
Re-ran: test_tally_loop, test_n1_tally, test_context_wiring (37 passed); test_e4a/b/d (104 passed); vitest src/v1/e4 (11 passed); tsc clean. Read the wiring, note rule and next-step code; no defects needed fixing.
Verdict: pass. Open items: (1) the file button follows the server's can.explain with can.submit or can.take, so it can show to an admin who is not the owner; add an explicit owner flag from the server if that matters. (2) after_turn runs only on questions, not on the summary view (by design). (3) Project is looked up through the case's decision intent only; a case with a portfolio/entity project but no intent falls back to the owner's scope.
