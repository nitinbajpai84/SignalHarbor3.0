# E4a Exceptions and cases

## What changed
Cases for the Action Desk over `exceptions`, `exception_events`, `approvals`, `exception_impacts` (workflow tables: state columns update, every change also writes an event row).
States new, assigned, investigating, waiting_check, resolved, rejected (dismissed = rejected). Maker = whoever submits; checker approves or sends back and is never the maker or the owner (and, when one was named at submit, must be that person). A material or unrated case closes only through a check; `resolve` is the direct path for below-threshold cases. `ask_finance` works only when the case was opened with `accounting_view_affected`.
Contract: `open, assign, take, add_event, submit, approve, send_back, resolve, dismiss, ask_finance, get, listing` (all in `e4_cases`). `get` returns `may` (which buttons this person may press), history with names, impacts, approvals. `listing` orders material first, then earliest due, then oldest; filters status (`active`), owner (`me`), exception_type, materiality_status, portfolio_id. Either the id or `CASE-0001` works wherever an id is taken.

## Files
`sh_platform/v1/e4_cases.py`, `e4a_routes.py`, `e4a.permissions.yaml`, `tests/v1/test_e4a.py` (6 tests), this note.

## Test on the demo
1. `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_e4a.py -q`
2. `GET /api/v1/cases?status=active` signed in as Operations: the Entity B break and the Fund A revision, material first.
3. `POST /api/v1/cases/CASE-0001/take`, then `/submit` {explanation, checker}.
4. Sign in as the checker: `GET /api/v1/cases/CASE-0001` shows `may.approve: true`; as the maker it is false. `POST .../approve`.

## Known limits / open points
- **Case number**: the model has no number column. The number is the note of the `opened` event, with a counter file `data/<co>/cases/counter.json` so a number is never reused. Proposal for the head of data: add `exceptions.case_number` through `e0b_tools.propose_model_change`; then switch `_number`/`_next_number` (two small functions).
- Status `waiting_check` and event types (taken, submitted, sent_back, dismissed, accounting_affected, finance_requested, comment) are not in the DBML notes; the columns are free varchar. The DBML status note should list waiting_check.
- People: owner, maker, checker are `users.id` (uuid). A person with no `users` row (matched by account id, then unique display name) cannot take, submit or check: fails closed with a plain message. The seed (E0e) must create users rows.
- A case with no `portfolio_id` is visible only to its owner, its maker and company admin (fail closed). E3b/E3c pass a portfolio when they have one.
- `approve` resolves the case in one step (events explanation_confirmed then resolved). Sending the report re-issue or notifying Finance is not done here.

## Wiring for the orchestrator
Auto-installed by the card pattern (`router` in `e4a_routes.py`). No shared file touched. E4b, E3b, E3c, E5a/E5b already call `e4_cases` by the contract names. Routes for E4c: `/api/v1/cases...` as listed in the `e4a_routes.py` docstring.
