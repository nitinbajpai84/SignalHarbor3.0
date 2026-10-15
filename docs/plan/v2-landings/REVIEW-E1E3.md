# Review: E1 Versioned evidence and E3 Rules, calculation and reconciliation (9 Oct 2026)

Scope: E1a `e1_asof`, E1b `e1_write`, E1c `e1_reports`, E1d `e1_access`, E3a `e3_rules`, E3b `e3_recon`, E3c `e3_impact`, E3d `e3_calc`, their routes and tests, checked against `docs/plan/V2-CARDS.md` (Facts, Settled, Recommendations 1 to 8) and the callers (E2b, E5b, E0e seed).

Tests: `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_e1a.py ... test_e3d.py -q` → **38 passed, 1 failed** (`test_e3d.py::test_sgd_and_missing_fx`; passes alone, fails after `test_e3c.py` in the same run, see should-fix 1).

Every blocker below was reproduced on a tmp plane (script in the reviewer's scratchpad, not in the repo).

## Verdict

**Not ready.** The as-known-then core (E1a query, E1b no-fork check, E1c as-issued never changing, E3d Decimal/FX by signed fixing) is sound and the code is small and readable. Five contract and recommendation gaps break the Fund A demo flow end to end and must be fixed before the orchestrator wires E2b → E3c → E5b.

## Blockers

1. **E1b lets a superseding row drop the subject, so the revision vanishes from every as-known-now view.** `sh_platform/v1/e1_write.py:73` compares subject keys only `if k in row`. E2b `e2_extract.py:203-208` records the 10.18m row without `portfolio_id`. Reproduced: after that confirm, `e1_asof.latest(valuation_observations, {instrument, portfolio, 30 Sep}, now)` → None; `e1_reports.as_known_now` shows Fund A **10.00m unverified** instead of 10.18m revised; `e3_calc.portfolio_value(now)` total → **0** (Fund A gone, no line). Fix (E1b): after loading `olds`, `for k in SUBJECT.get(table, ()): row.setdefault(k, olds.get(k))` before the diff, so a correction inherits the subject it corrects. (E2b should also pass `portfolio_id`, but E1b is where all callers route through.)

2. **E3c writes `plane.company_id` into a UUID column.** `sh_platform/v1/e3_impact.py:93` inserts `exception_impacts.organization_id = plane.company_id`. On the demo company (`evergreen`, a slug) DuckDB raises `Conversion Error: Could not convert string 'evergreen'`, after the revision case has already been opened by `e4_cases.open` (line 83): the case exists, the impacts are lost, the E2b confirm route returns 500, and E5b's banner (`e5_brief._open_cases` joins `exception_impacts`) never finds the case. The test passes only because `test_e3c.py:22` uses a UUID as the company id. Fix: `from sh_platform.v1.e1_write import org_id` and use `org_id(plane)` (Settled, item 1); write the impacts before or in the same transaction as the case.

3. **E1c `issue` has no cut-off discipline and accepts unverified lines (Recommendation 1).** `sh_platform/v1/e1_reports.py:115-123` stores whatever value, status and source rows the caller passes; nothing checks `source.recorded_at <= cutoff` and `status` defaults to `"unverified"` (line 119). Reproduced: a report issued with `cutoff = 3 Oct` accepted a source recorded 9 Oct and a line with status `unverified`. Fix: in the loop, read each source row's `recorded_at` (the `_pointers` query already touches the row) and raise `ValueError("... recorded after the cutoff")` when later; refuse `status in ("unverified", "draft")` for an issued line.

4. **E1b does not check referenced ids exist (Recommendation 6).** `e1_write.py:49-81` validates column names and the supersedes link only. Reproduced: a valuation with random `instrument_id`, `portfolio_id` and `source_record_id` was accepted. Fix: a small map of FK columns per table (or read `e0a_catalogue.describe(...)["refs"]`) and `select 1 from <ref table> where id = ?` for each non-null one, raising `WriteRefused("<column> <id> is not in this warehouse")`.

5. **`metric_evidence` can carry two pointers and the real pointer is a note (Recommendation 7).** `e1_reports.py:121-123` fills `source_record_id` *and* `extracted_field_id` from the observation row when it has both (an E2b-confirmed valuation has `extracted_field_id`, a loaded one has `source_record_id`, a corrected load could have both), and the observation row itself lives in `note = "table:id"`. Not enforced, not tested. Fix: pick one (`extracted_field_id` if present, else `source_record_id`, else leave both null), keep `note` as the documented single observation pointer, and add an assert in `test_e1c.py` that `sum(x is not None for x in (src, passage, field)) <= 1` on every evidence row.

6. **E3b reads the materiality percent under the wrong key (Settled rule parameter keys).** `sh_platform/v1/e3_recon.py:75` reads `parameters.get("pct")`; E3a stores, E0e seeds and E3c reads `pct_of_fund` (`e3_impact.py:37`). The 0.5 % test silently never fires in reconciliations. Fix: `pct = p.get("pct_of_fund", p.get("pct"))` and change `test_e3b.py:19` to `pct_of_fund`.

## Should-fixes

1. **E3d test isolation.** `test_e3d.py:22-25` replaces `sys.modules["sh_platform.v1.e3_rules"]` but `e3_calc.fx_explained` does `from sh_platform.v1 import e3_rules`, which resolves the package attribute set by an earlier real import (test_e3c stubs and restores it). Add `monkeypatch.setattr(sys.modules["sh_platform.v1"], "e3_rules", rules, raising=False)` as test_e3c does.
2. **DuckDB read-only and read-write connections cannot coexist in one process** (reproduced: `Can't open a connection to same database file with a different configuration`). Every module here mixes `wh.connect(plane, read_only=True)` (E1a, E1c reads, E1d `_grants`, E3b, E3c, E3d) with read-write connections (E1b, E3a `current`, E4a). Sequential calls are fine; two concurrent requests on the 8400 server (FastAPI sync routes run in a thread pool) will fail at random. Shared file, so for the orchestrator: make `wh.connect` ignore `read_only` (or serialise with the existing `_LOCK`), and leave the card code alone.
3. **Valuation `approval_status` vocabulary is not settled.** E2b writes `"confirmed"`, the seed writes `"approved"`, E3d `_val_status` (`e3_calc.py:92-94`) treats anything but `approved`/`approved_official` as `unverified`, so a confirmed revision shows **unverified** in `portfolio_value` while E1c `as_known_now` shows the same row as **revised** without looking at its status at all (`e1_reports.py:184-185`). Settle the words (suggest: `pending`, `confirmed`, `approved`) in V2-CARDS, have E3d accept `confirmed`, and have E1c take the line status from the new row the way E3d does.
4. **E1c `rule_versions_used` is always null** (`e1_reports.py:113`). A run must keep the rule versions it used (E3a card: "past runs keep their version"). Accept `rule_versions: list[str] | None` in `issue` and store it as JSON; E0e passes the signed ids.
5. **Positional `insert ... values (?,?,...)`** in `e1_reports.py:71,83,112,117,122,127` and `e3_rules.py:68,128,131`. E0a allows a company extension to add columns to core tables; the first one on `metric_values` or `users` breaks `issue`/`propose` with a column-count error. Name the columns.
6. **E1b backdating is open to every caller.** `e1_write.py:65` accepts a caller-supplied `recorded_at`, which is exactly what as-known-then must not allow in production (a late file can be made to look known before the cutoff). Only E6c replay needs it: add `replay: bool = False` to `record`/`record_many` and ignore (or refuse) `recorded_at` otherwise.
7. **E1d user matching falls back to display name even when the account has an id.** `e1_access.py:27-35`: an `account_id` that matches no `users.external_identity_id` falls through to the name match. Fall back to the name only when `account_id` is empty, and never when `viewer.shared_name` (already honoured).
8. **E3c opens a new revision case on every superseding row** (`e3_impact.py:83`); confirm then correct the same statement gives two cases for one difference. De-duplicate like E3b: skip when an open `revision` case exists for the same instrument and report version (or add an `exception_impacts` row to it).
9. **E3c case title has no amount and does not use the settled words** (Recommendation 2): `e3_impact.py:84` says "Revised valuation affects an issued report". Make it `f"Investigate the {total:,.0f} {ccy} manager-reported valuation difference"` and say "manager-reported valuation" in the description too. (Nothing in E1/E3 calls the 180,000 P&L. The only "rose by USD 180,000" wording in the repo is the E5c test mock `ui/src/v1/e5/e5.test.tsx:29`, outside this review; tell E5c.)
10. **Rows with no portfolio leak past E1d.** `e1a_routes.py:245` and `e1c_routes.py:237` show a row or line with `portfolio_id` null to anyone who can see *any* portfolio. After E2b, every confirmed valuation has a null portfolio (blocker 1 fixes the cause; keep this as the second line of defence: resolve the instrument's portfolio through `position_snapshots`/the superseded row, else hide).
11. **E0e seeds the FX fixing in a shape E3d cannot read** (`tools/seed_evergreen.py:226-238`: `{"series_key": "FX:USDSGD", "fixing": "month_end"}` with series_key `FX:USDSGD`). E3d looks for a series key containing the fixing name (`e3_calc.py:65`), per Settled: `{"fixing": "WMR_4PM"}` and `FX:USDSGD:WMR_4PM`. On the demo the SGD switch returns no rate. Owner: E0e, but E3d is where it surfaces.
12. **E3a and E1c approvals leave no `approvals` row** (Recommendation 8 exists to be used). `e3_rules.approve` (`e3_rules.py:152`) and `e1_reports.issue` (`approved_by`) could each write one `approvals` row with exactly one target (`rule_version_id` / `report_version_id`); that gives the event trail both landing notes say is missing.

## Nits

- `e1_reports.py:119` stores the line's status word in `metric_values.value_status`; the DBML says `draft, indicative, certified`. Pick one vocabulary and say so in the note.
- `e3_calc.py:117,124` sorts by `(valuation_date, received_at)`; a null `received_at` raises `TypeError` when two dates tie. Use `received_at or datetime.min`.
- `e3_impact.py:81` `new["valuation_type"].replace(...)` fails on a null type.
- `e3_impact.py:60-62` takes the first `metric_values` row for the instrument in the run; a report with the same holding in two currencies would miss one line.
- `e1_write.py:51-53`: when both the `supersedes_id` argument and `row["supersedes_*_id"]` are given and differ, the argument wins silently; refuse the mismatch.
- `e1_write.py:76-77` is check-then-insert with no unique constraint on `supersedes_*_id`; two concurrent corrections can still fork. Acceptable for phase 1, note it in the landing note.
- `e3_recon.py` keeps runs in `recon_runs.jsonl`; fine for phase 1, but the run's cutoff is stored with `str(cutoff)` rather than ISO.
- `e1_asof.latest` orders by `recorded_at`, not by the subject's own date; callers wanting "the latest valuation date" (E3b does this itself) should not use `latest` with a partial subject. Say so in the docstring.
- E3a: ownership and the proposer/approver split are by display name (`_same`); the user id is already available, compare ids.
- E5b `_key` (`e5_brief.py:107`) ignores E1c's `key` field and falls back to `instrument_id` then `label`; works today, but E1c should either rename `key` to `line_key` or E5b should read `key`. E5b also looks for `is_total`, which E1c never sets, so a hidden-portfolio viewer still sees the company total.

## Fixes after review (E1/E3 fixer, 9 Oct)

Tests: 8 files together, **51 passed** (was 38 passed, 1 failed). Backups in `.sh-tmp/*.bak-e1e3fix`.

Blockers
1. E1b `_insert`: a superseding row inherits any missing/null subject key from the row it corrects, then the subject-diff check runs. Test `test_correction_without_subject_inherits_it`.
2. E3c writes `exception_impacts.organization_id = org_id(plane)` (slug company in the test now). Case opened first, impacts after (separate connections; a failed impact insert would leave the case, noted).
3. E1c `issue` refuses lines with status unverified/draft and any source row recorded after the cutoff (date cutoff = end of that day UTC).
4. E1b checks every foreign key the catalogue declares for the table (except organization_id): "<column> <id> is not in this warehouse". Test `test_referenced_ids_must_exist`.
5. E1c evidence: one real pointer (extracted_field_id if the row has one, else source_record_id); `note` stays the observation pointer; test asserts at most one pointer per row.
6. E3b reads `pct_of_fund` (falls back to `pct`); test with a percent-only materiality hit.

Should-fixes: 1 e3d test patches the package attribute; 2 not mine (wh.py); 3 vocabulary below, E3d accepts `confirmed`, E1c takes the line status from the new row; 4 `issue(..., rule_versions=[...])` stored as JSON in `rule_versions_used`; 5 named-column inserts in E1c and E3a; 6 E1b ignores caller `recorded_at` unless `replay=True` (record/record_many); 7 E1d falls back to the name only when the viewer has no account id; 8 E3c: one revision case per instrument and valuation date (a later row returns the open case; only impacts whose draft value changed are added); 9 E3c title "Investigate the <amount> <ccy> manager-reported valuation difference for <fund>", description says manager-reported and that official NAV is unchanged; 10 E1a/E1c routes: a row/line with no portfolio takes the portfolio from its chain/source row, else is hidden; a company total (`is_total`, now set by E1c) needs every portfolio; 11 not mine (E0e seed); 12 E3a approve and E1c issue each write one `approvals` row (one target).

Nits done: null `received_at` in E3d sort, null valuation_type in E3c, supersedes_id mismatch refused, recon cutoff stored as ISO, `latest` docstring, `is_total` set (E5b `_key`/`key` left to E5b). Not done: ids instead of names in E3a `_same`; multi-currency lines of one holding in E3c. Known limit: E1b check-then-insert can still fork under two concurrent corrections (no unique constraint).

Coordinator additions: E3c opens the case for a pending (`proposed`) row too and returns the same case when the confirmed row supersedes it (walks back the chain to the row the report used); case portfolio falls back to the report line's portfolio; E1c `as_known_now` shows a non-confirmed superseding row as unverified, confirmed/approved as revised; `issue(..., issued_at=)` back-dates version and run times.

Settled vocabulary: valuation `approval_status` = proposed, confirmed, rejected (seed's `approved` is read as confirmed). E1c/E3d line status: confirmed or approved manager_final = revised (official if no supersedes); confirmed/approved estimate = estimated; proposed = unverified; rejected is ignored by E3c and shown unverified. `metric_values.value_status` holds official, estimated, revised. Issued lines can never be unverified/draft. `approvals.approval_type`: `report_issue`, `rule_version`.

Needs another card
- E2b: write the pending row with approval_status `proposed` and pass `portfolio_id`; call `on_new_valuation` for it.
- Anyone calling `e1_write.record` with `recorded_at` (back-dating) must pass `replay=True` or patch `wh.now` (E6c patches the clock, fine). Seed uses SQL, fine.
- Any other test or seed writing through E1b with invented instrument/portfolio/source ids now fails; seed the parents first (helper `tests/v1/e1_seed.py`).
- E0e: seed FX shape (series_key `FX:USDSGD:WMR_4PM`, params `{"fixing": "WMR_4PM"}`); pass `rule_versions=` and `issued_at=` to `issue`.
- wh.py: read-only and read-write connections still clash (orchestrator).
- E5b: read `key` and `is_total` from E1c lines. E5c: remove the "rose by USD 180,000" mock wording.
