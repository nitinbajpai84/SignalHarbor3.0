# W02-tally-owner

`POST /api/v1/cases/{id}/explain` (the record path) now returns 403 with "Only the person who owns this case, or a company administrator, can file Tally's proposal." unless the viewer is the case owner (`is_owner`) or a company_admin. `GET .../tally` and `POST .../ask` are unchanged.

Files: sh_platform/v1/e4a_routes.py (post_explain only), tests/v1/test_tally_tools_w02.py (one new test). Backups in .sh-tmp/*.bak-redo.

Tests: w02 + e4a + n1_tally = 32 pass, 1 fail.
Open: tests/v1/test_e4a.py::test_explain_route_runs_tally_and_returns_the_case_with_its_proposal has analyst MEI (not owner, not admin) filing on an untaken case; it now gets 403. Not my file. Fix: have MEI `C.take` the case first (or use ADMIN) in that test.

## Review

Verdict: PASS with one follow-up.
- Gate is correct and in scope: `post_explain` checks `is_owner or C._admin(v)` via `_run`, so a refusal is a 403 with the plain sentence; GET `/tally` and POST `/ask` untouched (record=False).
- Reviewer tidy: the new test's owner/other pickers used side effects inside `next(...)` generators; replaced with an explicit take for Mei Chen and a plain non-admin filter. Same assertions.
- Other record paths: `n1_tally.propose_explanation` (record=True) has no HTTP caller in sh_platform, so the route gate covers the server surface.
- Tests: w02 + e4a + n1_tally = 32 pass, 1 fail (expected).
- Follow-up (not on this card): `tests/v1/test_e4a.py::test_explain_route_runs_tally_and_returns_the_case_with_its_proposal` needs MEI to `C.take` the case first (or run as ADMIN); it fails only because the new gate is working.
