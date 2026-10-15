# INT4 landing (Wave 3, offline)

Backups: `.sh-tmp/<name>.bak-w3` for cx_lumen, i6_chat, n1_tally, mem_agent, e4a_routes, the Lumen playbook, test_doc_read, ConversationPage, i6 api and i6.test.

1. **Admin line on every reply path.** Span (project chat and talk) and Tally already appended it; North's `_trouble` and Tally no longer read it with `getattr` (S's function exists). Lumen: a rules answer after a failed loop now appends `e6_trace.model_trouble_note` (`cx_lumen._ask`). `SW2-BILL-ADMIN` passes offline (with `SW2-BILL-PART`, `SW2-H102`).
2. **`mem_agent.clear_convo(plane, viewer, agent, convo_id)`**; Lumen's `new_talk` uses it. Long-term memory is untouched.
3. **Lumen skill.** The playbook's one sentence now reads "Never write a figure yourself: state one only when a tool returned it." No rule weakened; skill size unchanged within the cap. `test_v3_g1` 6 pass.
4. **N1-INT-01 UI and route half.** `POST /api/v1/intents/chat` on a landing question returns `landing: true`, `project_id: null` (route test); `/intents/open` skips it; the first goal promotes it. `ConversationPage` shows "That was a question, so nothing is drafted yet..." and no Project line; `Chat.landing` typed. Still true: the record exists on disk and `IntentWelcome.tsx` (P3, not in this card) navigates to the returned id. Answering with `id: null` needs that file.
5. **test_doc_read** expects the current wording ("I have read the policy: ..."); product wording unchanged.
6. **Tally quick flag.** `GET /api/v1/cases/{cid}/tally?quick=1` returns the rules analysis (or the kept model wording) with no model call and `pending_model: true` when a plain call will word it. `n1_tally.explain(..., quick=False)`. The Tally screen (`ui/src/v1/e4`, not in this card) should call quick first, then the plain route.

Tests: new `tests/v1/test_int4.py` (5). Ran with lumen_w2, north_w2, tally_w2, span_w2, s_wave2, i6a, e4a, mem_*, cx*, doc_read, v3_g1: all pass (after one fix: the route passes `quick` only when set, so older stubs of `explain` still work). `vitest src/v1/i6` 14 pass (1 new); `tsc --noEmit` clean. Offline evals shared_w2 and north_w2: all offline items PASS.

## Review (w3)
Verdict: accept with two known gaps. Re-ran test_int4, e4a, v3_g1, doc_read (34 pass) and lumen/north/tally/span/s_wave2/i6a/mem_agent/cx/n1_tally (185 pass) offline. clear_convo and the quick flag are in place; edits stay within the card's files and each has a .bak-w3.
Open: IntentWelcome.tsx still navigates to the returned id (null for a landing question), and the Tally screen does not yet call quick=1 first.
