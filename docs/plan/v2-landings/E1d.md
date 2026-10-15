# E1d Access to structured data

## What changed
`e1_access` answers which legal entities and portfolios a person may read in the warehouse, from access groups, memberships and scopes.
- `level(plane, viewer, entity_id=None, portfolio_id=None) -> "full"|"read"|"none"`; `visible_entities`, `visible_portfolios` -> sets of id strings.
- company_admin role sees all. Expired memberships ignored. Scope level `preview` never opens structured rows. A portfolio is visible when granted directly or through its legal entity; an entity is visible when granted or when one of its portfolios is. Neither id given: `none`. Any error: `none` / empty set, with a warning logged.
- A viewer is matched to `users` by `external_identity_id = viewer.account_id`, else by unique display name (never for a shared name).
- Admin (company_admin only, each change appended to `warehouse/access_admin_log.jsonl`): list groups, add group, add or remove member, add scope.

## Files
`sh_platform/v1/e1_access.py`, `e1d_routes.py`, `e1d.permissions.yaml`, `tests/v1/test_e1d.py` (7 tests).

## Routes
`GET /api/v1/access/mine` (any role: your entities and portfolios) · `GET|POST /api/v1/access/groups` · `POST /api/v1/access/groups/{gid}/members` {user_id, expires_at?} · `DELETE /api/v1/access/groups/{gid}/members/{uid}` · `POST /api/v1/access/groups/{gid}/scopes` {scope_type, scope_value, access_level}. All but `mine` are company_admin only.

## How to test on the demo
1. `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_e1d.py -q`
2. After E0e seeds `evergreen`, sign in as the admin: `GET /api/v1/access/groups` lists groups with members and scopes.
3. Sign in as Mei: `GET /api/v1/access/mine` lists only her entities and portfolios.

## Known limits
- The warehouse is one file per company, so reads do not filter on `organization_id` (a UUID derived by `e1_write.org_id`); inserts set it that way.
- Route tests are not included (they need the seeded demo app); logic is tested on a tmp plane.
- `document_type` scopes are stored but read by the document helpers, not here.

## Wiring for the orchestrator
Auto-installed by the card pattern (`router` in `e1d_routes.py`). Other cards: `from sh_platform.v1 import e1_access` and filter rows by `visible_portfolios` / `visible_entities`.
