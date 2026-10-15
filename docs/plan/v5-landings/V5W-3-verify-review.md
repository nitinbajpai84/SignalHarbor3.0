# V5W-3 review (reasoning reviewer, 11 Oct 2026)

Checked against C4 to C7, b9.permissions.yaml, reuse (e0c batch_control_totals, a5 trail ids, k7_routes.monthly, n2_comments, e4_cases, e3_rules.propose, b6_run), egress and maker-never-checker.

## Defects fixed
1. Maker was checker: a person who verified, sent or fixed the run could accept it if they were also the raiser or a company admin. `accept` now refuses them (403) and `can.accept` is false for them (`_maker` in b9_verify.py).
2. Unverified numbers could be accepted: after the fix reruns the copy, `accept` used the verification of the earlier run. It now refuses with 409 until the data engineer verifies the newest run (`_stale`).
3. A refusal from `n2_comments` or `e4_cases` during flag fell through to a 500. b9_routes `_run` now also catches those Refused classes.
4. Flagging a second time left the old `fix` in place, so the fix button never came back. Flagging now clears `fix`.
5. C7 shows the weights before and after the fix. The Before table now lists each component's weight as well as the benchmark and the difference.

Backups: .sh-tmp/{b9_verify.py,b9_routes.py,test_b9_verify.py,VerifyPanel.tsx}.bak-v5. Test added for both 1 and 2.

## Checked, fine
- Default deny: all 6 routes are declared (a test enforces it). GET requires project read; mark, send and fix need full access plus the data engineer seat. Flag and accept need read and are owner-checked in code.
- Egress: no network or model calls. Notifications go through the existing P1 comment and n2 paths.
- Figures come only from records (batch_control_totals, gold tables, k7). Values are Decimal strings. SQL names are checked against a regex and information_schema.
- No existing files were edited, so no features were dropped.

## Tests
pytest tests/v1/test_b9_verify.py -q: 4 passed. vitest src/v1/b9verify: 4 passed. tsc --noEmit: no b9verify errors.

## Open (not fixed, for integration or follow-up)
- C5: the send form asks for portfolio, benchmark code and month by hand. The design prefills them and adds a subject line and an attached outcome card.
- C6: the "Open the signed benchmark definition" link and the Lumen comparison note are missing. The Lumen note needs an agent, so this card has no model call.
- C7: accepting takes no comment, while the design shows Mei's quote. The weights table reading the signed version is a b6/Span plan change.
- The send for review is a P1 note until package 1's assignment model lands.
