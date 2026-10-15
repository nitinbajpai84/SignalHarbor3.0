# E6b landing: evaluation harness

**Changed**: `tools/eval_v2.py` (runner), `tests/v1/fixtures/e6/` (identity, safety_requests with 20 refused and 20 allowed, retrieval, action_quality), `tests/v1/test_e6b.py`.

**How to test on the demo**
1. Seed Evergreen (E0e), then `python tools/eval_v2.py evergreen`.
2. Read the per-case PASS/FAIL lines; suites whose card is missing say "not built".
3. The release gate prints at the end; exit code 1 if any built suite fails (a crash inside a suite counts as a fail).
4. One suite: `--suite safety`. Tests: `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_e6b.py -q`.

**Suites**: extraction (E2e `expected/*.json`: `{"file": "x.pdf", "fields": {name: value}}`, optional `expect_none`; not built until E2e fixtures exist), identity, calculation (57.60m as at 3 Oct, 57.78m now, summed over all portfolios, USD, valuation date 30 Sep), asof (Fund A 10.00m then 10.18m), retrieval, safety (incl. `tests/v1/fixtures/e2/injection.pdf` if present: extraction must open no case), action (rerun does not duplicate; assign to a seatless user is refused).

**Known limits / assumptions**: the amounts are read from the first of `reported_value`, `value`, `valuation_amount` on the valuation row; extracted field columns assumed `field_name`, `extracted_value`; retrieval cases (`present/absent/contradicted`) check phrases in the explain reply and need tuning once E5b lands; the retrieval and action suites need the Evergreen seed. Fixtures use the Evergreen names.

**Wiring for the orchestrator**: none.
