# INT3: skill cap test, Library Open from the menu, router cost per call

Backups: `.sh-tmp/*.bak-int` (test_v3_g1.py, test_router.py, router.py, model_modes.yaml, CostPanel.tsx, LibraryPage.tsx, LibraryFolders.tsx, LibraryPage.test.tsx, l3-api.ts).

## 1. Skills under the cap (tests/v1/test_v3_g1.py)
- The cap (`skill_loader.LIMIT` = 6,000 characters) is a real budget and still holds: north is about 5,000 characters with `sop.md`, lumen about 5,700 with `managers.md`. Nothing is cut off.
- The test's expected file set was stale. It now checks that the four core files come first in loader order, then any extra skill file. The "whole skill under the cap, nothing cut off" assertions are unchanged. No skill file edited.
- Lumen has about 300 characters left. The next skill line added to lumen will need the cap raised or the text tightened.

## 2. Library Open from the menu (ui/src/v1/l3)
- The only read route for a file is the G3 source page (`GET /api/v1/build/{iid}/benchmarks/sheet/doc`). G1 gates the project and K1 gates the file. No route reads a file without a project, and none was added.
- Without `?iid=`, the Library page reads the viewer's projects (`GET /api/intents`) and each project's ticked files (`GET /api/v1/intents/{iid}/context`, at most 20 projects). Open uses the project the file is ticked in. Any other file opens through the viewer's first project.
- A viewer with no project still sees no Open. That needs a project-free file route, which would be new backend work.
- Changes: `LibraryFolders` takes an optional `openIn(item)` prop (`?iid=` still wins), `api.ts` gains `getOpenPlaces`, and `LibraryPage` wires them together. There is one new test.

## 3. Router cost log (sh_platform/v1/router.py, model_modes.yaml)
- `model_modes.yaml` `prices:` holds USD per million tokens {in, out} by model id. These are **list prices to be checked** (gemini-2.5-flash-lite 0.10/0.40, gemini-2.5-flash 0.30/2.50, anthropic/claude-sonnet-5.5 3.00/15.00). Real-use models from `.env` are not listed, so they log `cost_usd: null` until a line is added.
- Every cost-log row now has `cost_usd` and `latency_ms`. A failed call (no reply) is 0.0. Each `attempts` entry also has `cost_usd` and `ms`.
- `costs()` adds `cost_usd` (sum), `priced_all` and `avg_latency_ms`.
- Views: the agent-runs page already shows `cost_usd`, since e6_trace sums it from these rows and showed "Not available yet" before. The step lines already show ms per model step. The Model use panel (`ui/src/v1/router/CostPanel.tsx`, the router's own view) now shows USD at list prices and the average ms per call.
- Not done: `sh_platform/agents/loop.py` `_model_step` does not yet sum `cost_usd` from `attempts` into the run step. That file is not on this card and it is a one-line change.

## Tests
- pytest `test_v3_g1` + `test_router` + `test_e6a/b/c`: 29 passed.
- vitest `src/v1/l3`: 4 passed. `src/v1/router`, `s1`, `c4`: 10 passed.
- tsc clean.

## Review
Verdict: accepted. Re-ran test_v3_g1 + test_router (12 passed), vitest src/v1/l3 + src/v1/router (6 passed), tsc clean. No defects fixed.
Open items:
- Lumen skill has about 300 characters of cap left.
- Library Open is still hidden for a viewer with no project (needs a project-free file route).
- loop.py `_model_step` does not yet add cost_usd to run steps (one line, other card).
- Prices are list prices to be checked; .env models not in the table log cost null.
- CostPanel.tsx was edited outside the card's list (backup kept).
