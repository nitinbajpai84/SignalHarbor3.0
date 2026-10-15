# NI1: Intent page fixes from Nitin's screenshot (9 Oct)

Files: `sh_platform/v1/i6_chat.py`, `ui/src/v1/i6/ConversationPage.tsx`, `ui/src/v1/p3/IntentWelcome.tsx`; tests `tests/v1/test_ni1.py`, `tests/v1/test_l2.py` (one assertion), `ui/src/v1/i6/i6.test.tsx`, `ui/src/v1/p3/p3.test.tsx`. Backups in `.sh-tmp/*.bak-ni1`.

1. Start box. The landing has "What do you need?" with a three-line box and an example placeholder. The conversation header has "Start a new intent" (goes to `/centre/intent?new=1`, which shows the landing even when a draft is open). A blank conversation's composer says "Describe what you need in your own words...".
2. A reply that starts with yes, yep, yeah, ok, okay, accept or go ahead accepts the pending proposals through the same path as the buttons (`_accept_leading_yes`), then North carries on. In the rules-only path a reply that settled proposals is passed on empty, so it fills nothing and the question is asked again.
3. The goal North asked about is kept per turn (`thread.asked`; the model returns `asked`, the fallback knows its own question) and given to the model as `question_you_just_asked_is_about`. The rules-only path fills that goal, not the first open one; "readers" now fills `goal.readers` and "frequency" fills `goal.needed_by`.
4. Root cause of "North (rules only)" with Real use on: the egress gateway refused the model call with `raw_rows` (egress_log: blocked, bytes 0, module m1_intent). `L2.facts` put `turned_down_by_the_person` into North's context as a list of `{what, reason}` objects; two or more objects in a list read as rows to `egress/rows.py`, so after the second turned-down proposal every North call was blocked and the fallback answered. Not the mode, the .env (serve_test loads it like the main server: `load_model_env` reads `.env` from the working directory), nor the size cap (3.9 KB). Fix: North's context turns each into one string. When a model was on but gave no usable answer the reply starts "I could not reach the model just now, so this is a rules-only reply."
5. The header subline names the project through `useProjectTitle`, never the id.

For the orchestrator
- The same `L2.facts` list of objects is used by every agent that reads proposals (Span, Lumen, Tally, Flow); each will be blocked after two turned-down proposals. Best fixed once in `l2_proposals.facts` (strings, not objects); I changed only North's side and updated the one test that read the object shape.
- `ui/src/v1/p1/ProjectPage.tsx` line 64 still shows "Project {p.id}" in its subline (not in my files).
- The Tally `raw_rows` blocks in the same egress log (module m4_action) are probably the same family: look for a list of objects in its context.

## Review
Re-ran: pytest test_ni1, test_i6a, test_p7_cycle1, test_north_loop, test_l2 (42 passed); vitest src/v1/i6 + src/v1/p3 (17 passed); tsc clean. All five points checked against code and tests; no defects fixed. No live server check was made. Verdict: accept. Root cause of point 4 confirmed: egress `raw_rows` block on a list of objects (`turned_down_by_the_person`), not mode, env or size.
