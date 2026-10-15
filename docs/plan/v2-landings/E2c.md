# E2c Identity matching (landed)

**What changed.** `resolve(plane, name_or_code, source_system_id, model=None)` returns `{instrument_id, status approved|proposed|unknown, identifier_id, candidates, note}`.
Order: approved identifier (case and spacing ignored) -> cleaned-name rule (case, punctuation, Fund/LP/LLC, "Class I", roman numerals) against instrument names and
known identifiers -> near match (model picks among lettered, digit-free, tokenised candidates; with no model only a single clear spelling winner, 0.8 and 0.1 ahead).
A proposal is an `instrument_identifiers` row with `mapping_status = proposed` (never auto-approved; model picks carry `proposed_by_agent_run_id` from `e6_trace.agent_run`,
which raises ImportError if E6a is missing, only on the model path). Several equally good instruments, or nothing close, gives `unknown` with candidates and no row.
`approve_alias(plane, identifier_id, viewer)` / `reject_alias(..., reason)`: Operations or data engineer seat; one approved mapping per (source, type, value) at overlapping dates
(409 otherwise); a rejected name is not proposed again. Decisions are logged in `data/<company>/model/alias_decisions.jsonl`.

**Files.** `sh_platform/v1/e2_match.py`, `e2c_routes.py`, `e2c.permissions.yaml`, `tests/v1/test_e2c.py` (9 pass).

**Routes.** `GET /api/v1/evidence/aliases` (proposed matches with instrument and source names), `POST /api/v1/evidence/aliases/{identifier_id}/approve`, `.../reject {reason?}`.

**Test on the demo.** 1) Seed evergreen (E0e). 2) Call `resolve(plane, "EG Growth Fund I", <manager source id>)`: approved. 3) Resolve "Evergreen Growth Fund I LP": proposed. 4) Open `GET /api/v1/evidence/aliases`. 5) Approve as Mei; resolve again: approved.

**Known limits.** The "never the proposer" rule is only meaningful for agent proposals (no person proposes here); a person-proposed alias (E2d "correct the match") would need a proposer column or the E0b-style record.
`approved_by` is a UUID: an account id that is not one is mapped with uuid5 (as `e1_write.org_id` does for the company); when E0e seeds `users`, swap in the real users.id. The rejection is recorded only in the jsonl log and the status.
Unique index on identifiers is not in the DuckDB DDL, so uniqueness is enforced in code. `resolve` takes an optional `model` (callers pass `get_model(...)`); the contract's three arguments still work.

**Wiring for the orchestrator.** Register `e2c_routes.router` and `e2c.permissions.yaml` (auto-installed by the version 1 card pattern). Callers with a model (E0c2 load, E2a intake) should pass `model=`.
