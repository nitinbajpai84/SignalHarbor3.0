# Fix round 6 (REVIEW-ROUND6.md)

Orchestrator change made during the work: the B2 stage gate on hand-over offer and accept is NOT added (the hand-over is replaced by a Go live button in a later card). P5's hand-over routes and the HandoverCard button are as they were. B1 and the visibility fix (S1) are interim.

## Findings
- B1: `p1_project.resolve` refuses (409, "Answer it before it is resolved.") when the comment is still open and the person is not its author. Test line in `tests/v1/test_p4.py` (the builder's resolve is 409, and signing stays 409).
- B2: not done, as above.
- S1: `p1_project.document` and `export` take `roles`; design and build pack refuse (403) anyone outside company_admin, analyst, sponsor. Routes pass `v.roles`.
- S2: Pulse skips a hand-over comment written by an agent; a person's hand-over card opens `/centre/build/ops`. `p5_handover.offer` addresses the comment to `people.ops` or leaves `to` unset. `test_p2` and `test_p5` updated.
- S3: the b5 hook catches Exception and logs a warning.
- S4: Pulse project line carries `daily` (guarded); PulsePage shows "Today: state".
- S5: `p4_benchmarks.verify` takes a proposed benchmark's period from the newest loaded period.
- S6: "Sign the build pack" button on the engineer screen's Pipeline tab (`signPack` in f1/api.ts); the 409 sentence shows in a `role="alert"`.
- S7: removed the `intent` route in i6, `consume` in c1, the `build` redirect in App.tsx; the home test now uses `/centre/home/old`; the i6 test adds the bare path locally.
- S8: `tools/reset_v1.py` clears projects/, build/verify/, handovers/tickets/daily ledgers; the model cost log is untouched.
- S9: `room.post` returns `{}` and writes nothing. Asserts changed in test_a1, test_b3, test_c2, test_i4, test_i6a (now assert no room file). `test_x1` (tests the room itself) is skipped. Room link removed from Home; wording fixed in RunsPage and OpsPage. The four conversation screens had no Room link.
- ProjectTag added to the four conversation headers.
- "no any" test: no `any` found in ArtefactView or elsewhere; the test passes.

## Results
- `SH_MODEL_PROVIDER=off python -m pytest tests/v1 -q`: all pass, test_x1 skipped.
- `npx tsc --noEmit -p .`: clean. `npx vitest run src/v1 src/App.test.tsx`: 93 passed.
