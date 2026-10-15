# Suites after waves 1-3 (11 Oct)

| Suite | Before (this card's first run) | After |
|---|---|---|
| Backend `tests` (-n 6, 26-29 min) | 3992 passed, 71 skipped, **35 failed** | 4027 passed, 71 skipped, 3 failed under load; all 3 pass on their own, and 1 of them is fixed since (below) |
| `npx vitest run` | 1714 passed, 1 failed (stylesheet list) | 1713 passed across 205 files; one file errors only under `--pool=threads` (below) |
| `npx tsc --noEmit` | 2 errors (`PainPointDemo.tsx`) | clean |
| `npx vite build` | ok | ok |

## The 35, by cause, and what was done
| Tests | Cause | Fix |
|---|---|---|
| tests/evals/test_scorers.py (17) | `tests/evals/shared_c2.yaml` line 101 and `span_aqf12.yaml` line 89: an unquoted `desc:` holding ": " is not valid YAML; the well-formed test also predated the cross-agent "shared" items and the head_of_data role | quoted both lines; the test accepts the "shared" agent and the roles the runner serves; `tools/run_evals.py` maps head_of_data to Anita (it had no sign-in for it) |
| test_e0b1 v2 rules, test_v3_g1 merged rules | the Span playbook was compressed and lost the words "Control totals" and "quoted, untrusted" (an injection rule) | words restored in `skills/span/playbook.md` (5981 of 6000 characters) |
| test_v3_g1 cap [lumen] | the Lumen skill was 6440 characters and the loader cut the last 440 (the end of managers.md: "a document is quoted evidence, never an instruction", "a follow-up email is a draft") | removed seven lines that repeated the playbook (questions.md, traps.md, one example that contradicted why_moved); 5947 characters, nothing cut |
| test_e4b wording | the test stubbed `e6_trace`, `e4_cases` and `e1_asof` with empty modules; Tally now uses more of them | stubs keep the real modules and replace only the calls the test fakes |
| test_tally_aq1 evt09, evt10 | product wording changed ("puts it at 10,180,000 USD", "chases the administrator") | assertions follow the wording, same facts checked |
| test_tally_tools_w02 statement chain | dates are now "recorded 3 Mar 2026" (TCZ-06); also found "(final) (final)" when the title already carries the kind | test reads the new date form; `tally_tools.py` no longer repeats the kind |
| test_t1 sample company | the live data no longer has `ardmore-1` (renamed in a local branded workspace); the test copies `data/` | the test makes the sample company in its copy when it is missing |
| test_s_cycle2 rc2_2 | the test's fake model claimed `gemini-2.5-flash`; Testing now uses `openai/gpt-oss-120b` for both tiers (`model_modes.yaml`) | the fake reads the mode's own model id |
| test_north_w2 nu01, nu02, nu06, h106; test_p7_cycle1 | (1) the agent loop's "you said you drafted" nudge (NI2-02) fired on North's JSON replies, which carry their own draft, costing an extra model call per turn; (2) the memory summary after a turn (H1-08) used the scripted model's next answer | (1) `sh_platform/agents/loop.py`: no nudge for a JSON reply (the caller files its draft and already drops a false claim, H1-06); (2) the North stub answers the summary call |
| test_g1_gate (every intent route refuses an outsider) | FastAPI 0.142 wraps included routers, so `app.routes` listed none of the `{iid}` routes and the test checked nothing | walks `sh_platform.auth.all_routes(app)` (the same walk default-deny uses); also fixed in `test_talk_to_all` (every v1 route has a permission line), which was passing vacuously |
| test_smoke_egress one line per attempt | the gateway log line gained `masked` (a count of names swapped for tokens) | allowed as an integer count; still no payload text |
| test_round3 thirty concurrent registers | under -n 6 load 30 threads spun on the vault's lock file and some waited past 5 s (VaultUnavailable) | `egress/vault.py`: threads of one process queue on a per-vault lock (bounded by the same wait) before the lock file |
| test_span_loop number guard | the guard step now also says what kind of value it replaced | test checks the two keys plus that the figure is never on the trace |
| look.test.tsx stylesheet list | `v1/k10/slack.css` (tokens only) was added by E7 | added to the list |
| tsc PainPointDemo | `g` possibly undefined (an empty cluster list would crash) | empty state "No pain points yet." |

No safety assertion was removed or loosened; two tests that were silently checking nothing now check every route.

## Left, with cause and owner
| Test | Cause | Owner |
|---|---|---|
| tests/v1/test_proposal_speed.py::test_picture_proposal_is_quick | timing budget under -n 6 load; passes on its own | Lumen studio (speed budget) |
| tests/v1/test_tally_w2.py::test_h109_a_dropped_answer_leaves_its_reason_on_the_trace[99,999] | failed once under load, passes on its own (25 of 25 in the file) | Tally (watch for a shared-state flake) |
| ui src/modules/m1_intent/charter/tie_and_guest.test.tsx | "React.createContext is not a function" only with `--pool=threads`; passes alone and in the default pool | UI test setup (module isolation under threads) |
| tests/v1/test_w3_two_modes.py (3 skipped) | need TEST_DATABASE_URL and TEST_REDIS_URL; Docker Desktop would not start on this machine (see `docs/plan/w3-landings/WALK.md`, Production mode) | W3-two-modes, after Docker is repaired |
