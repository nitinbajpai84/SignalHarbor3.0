# Full v1 suite after all v2 cards landed (9 Oct, no builder editing)

396 passed, 8 failed (1 deselected: the known OCR timing test). tsc clean.

Failing in the full run:
- test_e0c1::test_states, test_e0c1::test_routes_upload_scan_and_seats: pass alone, fail in the full run (order dependence / shared state with other cards' modules now present).
- test_e2a (3 tests): the test stubs e2_match, but the real e2_match is now installed and wins, so instrument_id is None and supersession_of returns None. Fix the stub to patch the attribute the code actually calls, or seed an approved identifier and use the real matcher.
- test_e2b::test_confirm_supersedes..., test_e2b::test_correct_and_reject: fail in the full run only (assert 0 == 1); likely the same stub-versus-real issue (e3_impact or e6_trace now real).
- test_e3d::test_sgd_and_missing_fx: fx returns None in the full run; the stubbed e3_rules is bypassed by the real module or the rule parameter key differs from the Settled keys (fx_fixing {"fixing": ...}).
