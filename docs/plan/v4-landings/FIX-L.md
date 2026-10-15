# FIX-L Limits (UC5)

## What changed
- `e3_recon.py` (limits only): run record gains `results` (every rule/portfolio/bucket with `exposure_pct` as a 2 dp Decimal string, `breached`, plain `words` such as "Private Equity, X: 5.75% against a maximum of 5%."), `questions`, `stale_as_of`. Case description now shows the share at 2 dp ("It is 5.75%, above the signed limit of 5.0%").
- No asset class: the instrument is listed in `questions` with status "Needs a class", value and share of the portfolio; it sits in no bucket, opens no case, and the "classification" breach cause is gone (causes are now "real breach" or "stale data").
- Stale test uses the run date (`wh.now()` date, recorded as `stale_as_of`), not the checked day.
- `e3b.permissions.yaml`: GET /api/v1/recon/runs now company_admin, analyst, sponsor, approver, participant. POST run unchanged (company_admin, analyst).
- `ReconPage.tsx`: Limits card lists each result line and each "Needs a class" question.

## See it
Action > Reconciliations > Limits, as Sofia (participant): last run shows lines like "...: 56.50% against a maximum of 55%." and the PRC29 line "Needs a class". No Run button for her.

## Tests
- tests/v1/test_e3b.py: 19 passed (updated the classification test, added run-date stale and exposure_pct asserts).
- vitest ReconPage.test.tsx: 1 passed. tsc: no errors in ReconPage; two pre-existing errors elsewhere (k8.test.tsx, ManagersInbox.tsx).

## Wiring for the orchestrator
- The runs route returns all checks' last runs, so participants/approvers/sponsors now also read cash and trade results (not just limits). Say if limits-only filtering is wanted.
- docs/test/CHECKER-NOTES-1.md expects approver and participant 403 on GET runs; that expectation is now stale (uc3/uc5 checkers).
- uc5 checker's "no classification cause" and "Needs a class" now should read `questions` in the run record (the P19 holdings-line status in k4_office is not touched).
- Backups: .sh-tmp/*.bak-fixcp.

## Review
Verdict: pass. All four points hold against the diff and the tests.

- Diff against .sh-tmp/*.bak-fixcp: only the four listed files changed (e3_recon.py limits section only; cash and trade_vs_admin untouched). No file outside the list was edited by this fix.
- Money and shares: all arithmetic is Decimal; `exposure_pct` and case description are `share.quantize(Decimal("0.01"))` strings; the limit edge in the words uses `_n()` (Decimal normalise), no float. `wh.now().date()` is the stale as-of; it is recorded as `stale_as_of`.
- Permissions: e3b.permissions.yaml still lists only the allowed roles per route (default-deny); POST run stays company_admin and analyst; GET runs adds sponsor, approver, participant. Parses cleanly.
- Screen copy: "56.50% against a maximum of 55%.", "Outside the limit.", "Needs a class ... counted in no class and opens no breach." Plain words, no ids or codes shown.
- Tests: tests/v1/test_e3b.py 19 passed; vitest ReconPage.test.tsx 1 passed; `npx tsc --noEmit` has one pre-existing error in `src/v1/k5/ManagersInbox.tsx` (another fix's file), none in ReconPage.
- Changed by the reviewer: restored the line endings the fix had flipped (tests/v1/test_e3b.py back to CRLF, e3b.permissions.yaml back to LF, as in the backups). Nothing else.

Open items for the orchestrator (unchanged from the note above): CHECKER-NOTES-1.md lines 77 and 104 expect 403 for approver and participant on `GET /api/v1/recon/runs`; that is now by design wrong. The runs route also exposes cash and trade results to those roles; say if a limits-only view is wanted.
