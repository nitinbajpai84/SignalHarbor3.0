# INT2: chat-turn traces in Settings, hashed trace ids, project-scoped Design talks (9 Oct 2026)

1. **Agent runs lists chat turns.** `GET /api/v1/agent-runs/loops` (company_admin only, in `e6a.permissions.yaml`) returns one row per loop run in
   `context/run_steps.jsonl`: `trace_id, agent, at, steps, tokens, ms, outcome` (newest first, 100). `record_trace` now stamps `at`; older rows show no time.
   Settings > Agent runs has a "Chat turns" list; "Show steps" uses the existing trace route. Code: `e6_trace.loop_traces`, `SettingsPage.tsx`.
2. **Trace ids carry no name.** North and Span Design chat turns run inside `e6_trace.trace(turn_trace_id(...))` = `tr-<agent>-<8-hex salted hash of the person>-<8 hex>`;
   the salt is per company in `context/trace_salt`. Lumen, Span Build and Tally keep `tr-<random>` (no person in it).
3. **North and Span Design talks share with the project.** `mem_wire.intent_focus(plane, iid)` gives `{intent, project}` (project from `p1_project.for_intent`); used for the
   `Wire` focus and `after_turn` in `i6_chat` and `a1_chat`. No project: `{intent}` only, so the talk stays private.

Tests: `tests/v1/test_int2.py` (5); UI test added to `runsteps.test.tsx`. Backups: `.sh-tmp/*.bak-int`.
Open: Lumen and Span Build turns are not wrapped in a person-hashed trace id (files outside this card); they list fine with random ids.

## Review (security, 9 Oct 2026)

Verdict: **pass, no fixes needed.**
- Re-ran: test_int2, test_context_wiring, test_e6a/b/c, test_mem_graph, test_north_loop, test_span_loop, test_a1, test_i6a, test_agent_tools: 77 passed. vitest src/v1/s1: 5 passed. tsc: clean.
- Admin-only: `/loops` goes through the same `_admin` guard as the other agent-runs routes (403 for non-admins, tested) and is in `e6a.permissions.yaml`. "Show steps" reuses the admin trace route.
- Trace privacy: `loop_traces` returns only id, agent, time, counts, tokens, ms and outcome; step rows stay prompt-, answer- and name-free as before. Trace ids carry `sha256(salt|who)[:8]` with a 128-bit per-company salt, so a name cannot be guessed back from the id. A person with no account and a shared display name hashes to "" (one shared tag, still no name).
- Conversation sharing: `intent_focus` adds the project only when `p1_project.for_intent` finds one; the map's `view` already filters by `may_project`, and intent nodes resolve to their project, so project readers see what they could already read. No project: the talk stays owner-only.
- No outer `e6_trace.trace` exists around these chat calls, so the new wrapper does not break an existing correlation id.

Open items (low):
1. The hashed tag is stable per person, so an admin can tell which turns came from the same person (pseudonymous, not anonymous). Accepted for an admin-only view; rotate `context/trace_salt` if that is unwanted.
2. Two first-ever turns at the same moment could each write a salt; the later wins and earlier ids keep the lost salt's tag. Harmless (no name), no fix.
3. Lumen, Span Build and Tally turns still use random `tr-<hex>` ids (no person part) because their files are outside this card.
4. The project-sharing change is tested at the helper level (`intent_focus`); no end-to-end test that a second project reader sees a North talk.
