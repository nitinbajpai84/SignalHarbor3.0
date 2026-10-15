# E2b Extraction by the intake agent

## What changed
- `e2_extract.extract(plane, document_id, viewer)` reads the original on this machine (`context_docs.reader`, local OCR for pictures) and finds nav, units, valuation_date, currency and status_label with page and line, using the X5 locator `_locate`. Writes `extracted_fields` (once per document; a second call returns the same ids). Nav, and anything not high confidence, is `pending`; other high-confidence fields are `confirmed` by the reader (reviewed_by empty).
- `confirm(plane, field_id, viewer, corrected_value=None)`: a nav becomes a `valuation_observations` row through `e1_write.record`, superseding the latest valuation of the same fund and valuation date, with `extracted_field_id`, `evidence_document_id`, `received_at` from the document; then `e3_impact.on_new_valuation`. Needs a matched instrument and a confirmed valuation date and currency, else a plain refusal. `reject(...)` also exists.
- The run is recorded with `e6_trace.agent_run` (model id `rules-only`).
- Skill: `skills/intake/`.

## Files
`sh_platform/v1/e2_extract.py`, `e2b_routes.py`, `e2b.permissions.yaml`, `skills/intake/*.md`, `tests/v1/test_e2b.py`.

## Routes
`GET /api/v1/evidence/documents/{doc_id}/fields`, `POST .../extract`, `POST /api/v1/evidence/fields/{id}/confirm`, `/correct` {value}, `/reject` {reason}. Analyst and company admin act; the decision maker may read.

## How to test on the demo
1. `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_e2b.py -q` (4 tests).
2. With E2a, register the Fund A statement, then `POST /api/v1/evidence/documents/{id}/extract`.
3. Confirm the nav with `POST /api/v1/evidence/fields/{id}/confirm`.
4. Register and confirm the amended statement: the valuation supersedes the first and the impact check returns the case id.

## Known limits
- Rules only: no model is called, so the document text never leaves the machine. A statement whose labels are not in the field list is not read (Refused 422, a person reads it). Model-assisted locating can be added through `x5_extract._model_locate`.
- Scale (thousands, millions) is taken from the whole page, not per line.
- Access to the document row is by seat only; the E1d/G1 document filter is applied by E2a routes upstream. Not re-checked here.
- The test stubs `e3_impact` and uses the real `e1_write`.

## Wiring for the orchestrator
None beyond auto-install of `e2b_routes` and the permissions file. The UI (E2d) uses the paths above.
