# W14: Agent runs, steps for warehouse runs, cost per step and per run, one date style (9 Oct 2026)

What changed
1. **Show steps on every warehouse run.** Settings > Agent runs > Recent runs now has "Show steps" on each run. A run that recorded a trace id
   opens its loop steps from `GET /api/v1/agent-runs/trace/{trace_id}`; a run with no trace id, or a trace with no step rows, says
   "No steps were recorded for this run." (Code: `RunSteps` in `ui/src/v1/s1/SettingsPage.tsx`.)
2. **Cost per step and a total per run.** A model step shows its W01 price when the step carries `cost_usd` ("..., 400 ms, USD 0.0012.");
   otherwise its tokens, as before. Under the steps: "Total for this run: USD 0.0015, 150 tokens." or "Total for this run: 150 tokens (no price recorded)."
   The trace route now also returns `total: {cost_usd, tokens}` (`e6a_routes.total`, cost None when no step had a price).
   A warehouse run line also shows its recorded run cost when there is one.
3. **One date style.** Both lists use "9 Oct 2026, 09:12" (local time); the Day column of the table shows "9 Oct 2026". Helpers `stamp`, `dayLabel`.

How to see it: log in as company admin, Settings > Agent runs and cost; press "Show steps" on a recent run and on a chat turn.

Tests: `tests/v1/test_w14.py` (3, with test_e6a and test_int2: 12 passed). vitest `src/v1/s1/runsteps.test.tsx` + `k8.test.tsx`: 6 passed. tsc: no errors in s1.
Backups: `.sh-tmp/*.bak-W14`.

Open: the Chat turns list shows tokens per turn but no price; adding a price there needs `e6_trace.loop_traces` to sum step `cost_usd` (outside this card).

## Review
Verdict: pass. Re-ran test_w14 + test_e6a + test_int2 (12 passed) and vitest runsteps + k8 (6 passed). Scope held (e6a_routes.py, s1/, new test). Wording matches card; one date style in both lists; no-trace and no-steps both say "No steps were recorded for this run." No fixes needed.
Open: chat turns show tokens but no price (needs e6_trace.loop_traces, outside card); full-project tsc not run by reviewer.
