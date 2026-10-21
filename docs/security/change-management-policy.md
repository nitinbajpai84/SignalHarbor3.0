# Change management policy

Status: draft (W7). Owner: Nitin Bajpai.

## What exists
- All code is in git; work is done on a branch and merged to `main` by Nitin.
- Tests: the pytest suite (`tests/`), UI tests (`ui/`), and route-permission tests that fail when a route is not declared.
- Deploy: Railway builds the `Dockerfile` from `main`; a failing health check (`/api/health`) stops the release.
- `.github/workflows/security-scan.yml` runs dependency audit (pip-audit, npm audit) and secret scanning (gitleaks) on every pull request, on `main`, and weekly.
- A change to a client's published figures goes through the figure version, hold and rollback record (`sh_platform/v1/v3_figstore.py`); signed decisions are in the audit log.

## Rules
1. No edits on the production host; every change comes from a commit.
2. A change that touches sign-in, permissions, the audit log or backups needs a test and a second look (another person, or a written self-review when working alone).
3. Take a backup before any release that migrates data.
4. Roll back code by redeploying the previous commit; roll back data by restore.
5. Emergency fixes follow the same path, with a note added afterwards.

## Open
- Branch protection and required reviews are not switched on in GitHub (needs a second person).
- No staging environment separate from the demo.
