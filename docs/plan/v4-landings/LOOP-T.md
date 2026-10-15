# LOOP-T: Tally is a real tool loop

## What changed
- `sh_platform/v1/tally_tools.py` (new): Tally's own tools, registered under module `m4_action` (the id Tally already ran under) beside the shared `tools_for(plane, viewer, "tally", module_id="m4_action")`.
- `sh_platform/v1/n1_tally.py`: `_model_text` now runs `run_agent` with that registry and `tally_tools.PROMPT_LINE` (it was an empty registry). The cash and limit builders also return a `raw` block (all window items, the ranked candidates, the run, the limit inputs) so the tools show what the program already found; nothing is recomputed. `_wording`/`_answer` pass the viewer and return the drafts; `explain` adds `proposals` to its output. Backup: `.sh-tmp/n1_tally.py.bak-looptally`.
- Kept: every figure filled by the program from placeholders; the number guard (a reply the guard changed, a digit, or an unknown placeholder is dropped for the rules' wording); the rules path when the model is off; routes and output shape (one new key, `proposals`); the wording cache (now keeps the drafts too, so a page view costs no second loop).

## Tools (all arguments required each time; text lines only, so the aggregate rule has nothing to hide)
| Tool | Kind | Arguments | Returns |
|---|---|---|---|
| `get_recon_run` | read | none | check and date, ran at, cutoff, signed rule version, entity, both totals, difference, tolerance, how far past it |
| `get_both_sides` | read | `entity`, `from_date`, `to_date` (YYYY-MM-DD, at most 14 days) | both balances; movements booked on each side with date, type, bank reference, amount, source row; over 40 movements are summarised by side and kind |
| `find_matching_items` | read | `kind` (all, exact, set, timing, duplicate, fx) | the program's ranked candidates with sources |
| `get_valuation_chain` | read | `fund`, `as_of` | statement chain of a fund named in the case: value, status, recorded, statement |
| `get_limit_inputs` | read | none | exposure, limit, each input with age and status, the program's cause |
| `get_case_history` | read, outside material | none | who did what; notes people wrote are marked as data |
| `propose_explanation` | propose | `cause`, `item_ref`, `note` | checked draft `{kind: explanation, cause, item_ref, text, note, sources}` |
| `propose_next_step` | propose | `who`, `action` | checked draft `{kind: next_step, who, text}` |

- Access: registering the tools calls `e4_cases.get` for the viewer (a case they may not see refuses); entity must be the case's entity; fund must be one named in the case; history comes from the same viewer-filtered read.
- Propose checks: `cause` must be allowed for the case kind; for a cash cause `item_ref` must appear in a program candidate of that kind (so WIRE-20261008-B01 is accepted as timing, an invented reference is refused); a limit cause must equal the program's finding; `note` and `action` may hold only `{placeholders}` the case offers and no digit. The sentence of the explanation is written by the program from the candidate; the model's note is filled by the program.
- Filing: nothing is written in a run. `explain(record=True)` adds the drafts as lines in the one `explanation_proposed` event (as before: by Tally, not duplicated); `record=False` (view, ask) returns them in `proposals` only.

## See it
Needs the model on and `python tools/seed_10uc.py` run once. Action, case "Cash differs · Entity B · 2026-10-08", "Ask Tally to write this up": the recorded proposal gains "Cause proposed: a timing difference. 12,400 USD cash movement wire WIRE-20261008-B01 ..." and any "Next step proposed (...)" lines. Settings > Agent runs > the trace (`/api/v1/agent-runs/trace/{id}`) lists each tool call with argument keys and result size. The panel does not yet show `proposals` separately (no UI work in this card).

## Tests
`tests/v1/test_tally_loop.py` (9 passed, 53 s): Entity B loop calls get_recon_run, get_both_sides, find_matching_items and proposes an explanation naming WIRE-20261008-B01 as timing (case unchanged after the run); drafts filed only on record, and a repeat view uses the cache; a planted instruction in a document passage is delivered as outside material and the draft it asked for is refused; the same for a note on the case; an invented figure (in a note, an item reference, or the reply) is dropped; a participant asking gets a model answer and the case row and history are unchanged; strict arguments and scope; limit causes; no access, no tools.
Also run: `test_n1_tally` (16), `test_e4a`, `test_e4b`, `test_e4d`, `test_a5`, with the new file: 137 passed. `test_agent_tools` and `test_north_loop` passed in an earlier combined run (167 passed, 1 failure in `test_e4b::test_model_wording_is_filled_by_the_program`, caused by my first version failing the tool registration for that test's dummy viewer; fixed by falling back to an empty registry with a logged warning; it then passed in two reruns).

## Open
- Stub model only; no live call yet. A live run should confirm the model replies with the JSON object after its tool calls and does not hit the six-step budget.
- `proposals` is returned by the routes but the Tally panel does not render them yet.
- Trade break, revision and capital call have thin tools (the findings text); the cash and limit paths are the full ones.
- Registration failure for a viewer falls back to the single-shot wording with a logged warning rather than an error.

## Review
Verdict: accept. No code changed in review.
- Real tools in the run: `_model_text` calls `run_agent` with `tools_for(...)` plus `tally_tools.register`; the stub-model tests observe each tool result in the next step's messages (recon run, both sides, WIRE-20261008-B01 as `kind: timing`).
- Read vs propose: six read tools, two propose tools (`proposes=True`, not read-only); propose tools only validate and return drafts. A test checks case status, owner and history are unchanged after a run; drafts are filed only on `record=True`.
- Strict schemas: every argument required, dates YYYY-MM-DD, span at most 14 days, enums for kind/cause/who, placeholders-only notes with no digit, item_ref must be a program candidate of that cause.
- Access: registration calls `e4_cases.get` for the viewer; entity and fund scoped to the case; no access gives no tools.
- Injection: document passage and case note arrive marked OUTSIDE MATERIAL; the requested draft is refused. Note that the document test is refused only because the planted text carries a digit; a digit-free planted next step (who from the fixed list, action from placeholders) would be accepted as a draft, but it is still only a proposal a person files, and the action text cannot hold free figures.
- Kept: number guard, rules path, routes, cache. Rerun in review: test_tally_loop, test_n1_tally, test_agent_tools, test_north_loop: 73 passed (367 s). Builder's earlier run covered e4a/e4b/e4d/a5.
- Not verified: live model; test_e4*/test_a5 not rerun in review.
