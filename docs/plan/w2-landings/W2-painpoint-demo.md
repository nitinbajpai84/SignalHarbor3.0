# W2-painpoint-demo

## Built
- `sh_platform/v1/k12_painpoints.py`: loads the pain-point list (local/painpoints/<name>.yaml, gitignored, else packs/family_office/1/painpoints_sample.yaml), validates it (coverage strong/partial/not_in_scope, not_in_scope needs a reason and has no link, links are in-app paths only, unique ids), groups by cluster. `GET /api/v1/demo/painpoints[?name=x]`, read only, no model.
- `sh_platform/v1/k12_routes.py` (re-exports the router; auto-discovered by `v1.install`), `sh_platform/v1/k12.permissions.yaml` (all six roles, GET only).
- `packs/family_office/1/painpoints_sample.yaml`: 8 synthetic items (5 covered or partial, 2 not in scope with honest reasons).
- `ui/src/v1/k12/` api.ts, PainPointDemo.tsx, routes.tsx (`demo/painpoints`), k12.test.tsx.
- No existing file edited, so no .bak-w2b.

## See it
`/centre/demo/painpoints` (add `?name=acme` to read `local/painpoints/acme.yaml`). Cluster chips, coverage pills, "Show me" links.

## Tests
- `python -m pytest tests/v1/test_k12_painpoints.py -q`: 13 passed
- `cd ui && npx vitest run src/v1/k12 --no-file-parallelism --maxWorkers=1`: 3 passed (default pool timed out starting workers while the box was busy)

## Mount lines
- Python: none. `sh_platform/v1/__init__.py` install globs `*_routes.py` and `*.permissions.yaml`.
- `ui/src/v1/index.tsx` (or wherever the v1 route lists are merged): `import { routes as k12 } from "./k12/routes";` and add `...k12` beside the other card routes.
- Optional nav link: `/centre/demo/painpoints`.

## Open items
- Show me links point at existing Consume paths (/centre/consume, /pnl, /signals, /reports, /managers); retarget if V5 integration renames them.
- Local file errors return 400 with the reason; no auto-fallback to the sample when a local file is malformed.

## Review
- Access: route listed with all seven-seat roles, viewer_of called; read only; ok.
- Egress/secrets/locality: no network or model; local/ is gitignored; name regex blocks path traversal; ok.
- Fixed: a link such as "/\host" passes the "//" check but browsers treat it as off-site; backslash now rejected.
- Fixed: page now says whether it shows the sample or the local list (a missing ?name= file falls back to sample silently, so a prospect demo could look like theirs).
- Tests: Python 13 and UI 3 re-run after fixes (see verdict).
