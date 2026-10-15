# SW1: Shared with you

Closes the CR1 gap. `GET /api/v1/consume/shared` (all six roles, declared in cx.permissions.yaml) returns `{dashboards, brief}`.

- dashboards: every dashboard in any project where the person is in the audience (by name or group) and cx_dash.may_view / E1d access still allows it now; each with title, project_title, shared_by (display name of the maker), shared_at (last saved), tiles, link (/centre/consume/d/:id). The person's own dashboards are left out. Newest first.
- brief: the latest issued report (e1_reports) as `{report_version_id, title, link: /centre/consume/brief/:rvid}` or null.
- Consume "Shared with you" lists the CIO Brief and the dashboards; with neither: "Nothing has been shared with you yet."

Note: shared_at is the dashboard's last-saved time (a share saves it); no separate share timestamp is stored.

Files: cx_dash.py (`_in_audience` split out of `may_view`, `shared_with`, `latest_brief`), cx_routes.py, cx.permissions.yaml, cxui/api.ts, cxui/ProjectList.tsx, cxui.test.tsx; new tests/v1/test_cx_shared.py. Backups: .sh-tmp/*.bak-sw1.

Checks: pytest tests/v1/test_cx_shared.py tests/v1/test_cx.py pass; vitest src/v1/cxui 9 pass; tsc clean.

## Review (10 Oct)

Verdict: pass after two fixes.

- Access checked: audience by name or by a current (unexpired) group membership, E1d still required (fails closed), own dashboards and admin-only access left out, one rule shared with may_view. Other companies are separate planes, so nothing crosses. Permissions line (all six roles) matches the brief routes.
- Fix 1: the brief came back for anyone, even a person who sees no portfolio (the brief page would then show no lines). `latest_brief(plane, viewer)` now returns it only to an admin or someone with at least one visible portfolio, fail closed. New test `test_brief_hidden_without_portfolio_access`.
- Fix 2: one malformed dashboard file (missing key) would have made the whole list fail with a 500; it is now skipped like an unreadable one.
- Re-run: pytest test_cx_shared.py + test_cx.py 29 pass; vitest src/v1/cxui 9 pass; tsc --noEmit clean.
