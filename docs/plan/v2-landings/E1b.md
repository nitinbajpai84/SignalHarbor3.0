# E1b Append-only writer

**Changed:** `sh_platform/v1/e1_write.py` (`record`, `record_many`, `org_id`, `WriteRefused`), `tests/v1/test_e1b.py` (5 tests).
There is no update or delete function. A correction is a new row with the table's `supersedes_*_id` set.

**Checks:** unknown table or column refused; `organization_id` forced to this company; `id` and `recorded_at` filled if absent (a caller may pass `recorded_at` to backdate in tests);
`supersedes_id` must be a row of the same table, about the same subject (subject keys per the E1a card), and not already superseded (no forks); `record_many` is one transaction, all or none.
`record_many(plane, table, rows, supersedes_ids=None)` takes an optional list lined up with the rows.

**Test on the demo:** `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_e1b.py -q`.

**Known limits:** columns come from `e0a_catalogue.describe` (falls back to the warehouse column list). Tables without a subject key (cash_movements, documents) are only checked for same table.

**Wiring for the orchestrator:** none. Important: warehouse id columns are real UUIDs, but `plane.company_id` is a slug ("acme"), so `organization_id` cannot hold it as the facts say.
E1b stores `e1_write.org_id(plane)` (the company id if it is a UUID, else a fixed uuid5 of it). Other cards that filter or insert `organization_id` directly must use `org_id(plane)`; ids passed to the writer must be UUID strings (`wh.new_id()`).
