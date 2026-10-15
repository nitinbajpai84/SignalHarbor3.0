# W3-suite-and-walk: landing note (11 Oct)

## Mount lines applied
- `ui/src/v1/s1/routes.tsx`: `...jobsRoutes` (`settings/jobs`); `SettingsPage.tsx`: section "Jobs and events" linking to it (W3-two-modes line 1).
- `sh_platform/v1/k3_map.health`: a late or failed connector (`c5_connect.ops.map_feed`) marks its source late (W2-connectors line 4).
- `sh_platform/v1/e0c_landing.ensure_poll`: `c5_connect.ops.run_due(plane)` on the same poll (W2-connectors line 5). Both wrapped so the map and the poll never fail on a connector.
- Not wired: accepting MCP drafts (no mount line describes it).

## Suites
Details and the per-cause table: `docs/test/SUITE-W3.md`. Backend 35 failed -> 3 (load-only, pass alone; one since fixed); vitest 1713 passed (one file errors only under `--pool=threads`); tsc clean; vite build ok.

## Live walk
`docs/plan/w3-landings/WALK.md` and `walk/` (78 shots). One project from New project to Complete, Consume tabs, Map, connectors, MCP tokens, pain-point demo. Seven defects found on the way were fixed at the root, with tests (WALK.md, "Fixed during the walk"); 16 gaps and 14 design differences are listed there.

## Production mode
Blocked: Docker Desktop crashes at start on a stale socket file it cannot remove (WALK.md, Production mode). Migration, parity and the five scenarios not run.

## Files changed (backups `.sh-tmp/<name>.bak-w3`)
Product: `sh_platform/agents/loop.py`, `sh_platform/egress/vault.py`, `sh_platform/v1/{b9_verify,cx_dash,k3_map,e0c_landing,tally_tools}.py`, `skills/span/playbook.md`, `skills/lumen/{questions,traps,examples}.md`, `tools/run_evals.py`, `ui/src/v1/{s1/routes.tsx,s1/SettingsPage.tsx,b7/routes.tsx,b8/routes.tsx,b9verify/VerifyPanel.tsx,b9verify/api.ts,k12/PainPointDemo.tsx}`.
Tests and data: `tests/evals/{shared_c2.yaml,span_aqf12.yaml,test_scorers.py}`, `tests/v1/{test_e4b,test_tally_aq1,test_tally_tools_w02,test_t1,test_s_cycle2,test_north_w2,test_g1_gate,test_talk_to_all,test_b9_verify,test_b7_studio,test_span_loop}.py`, `tests/smoke/test_smoke_egress.py`, `ui/src/look.test.tsx`.
Note: some `.bak-w3` names (for example `SettingsPage.tsx.bak-w3`) may have replaced an earlier wave's backup of the same name; git holds the committed versions.

## Differences for Nitin's approval
All in WALK.md ("Differences for Nitin's approval", 14 items). Two behaviour choices made here:
1. b7/b8 room gates now open for anyone who sees Build in the bar (Build or Intent), as b9 and d1 already did, so the sponsor can approve a dashboard (D3). The server's permission lines are unchanged and still decide every action.
2. The person who approved a published dashboard can view it even when not in its audience (needed to approve its delivery, D4).
3. Map review approval stays company admin only; the design shows Anita (head of data, an analyst seat today) approving.

## How to test
- `python -m pytest tests/v1/test_b9_verify.py tests/v1/test_b7_studio.py tests/v1/test_north_w2.py tests/v1/test_g1_gate.py tests/egress tests/evals -q`
- `cd ui; npx vitest run src/v1/b9verify src/v1/b7 src/v1/b8 src/look.test.tsx`
- Walk: `python tools/serve_test.py --port 8697 --data-root .sh-tmp/testenv/w3/data` (do not re-run make_test_env, it replaces the data); project `prj-f74bf9ab` is complete there. Sign-ins: `.sh-tmp/testenv/w3/data/_control/seed_credentials.txt`.
