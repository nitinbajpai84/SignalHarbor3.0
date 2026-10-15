# E5a Role Pulse generator

## What changed
Cards for each person, made from events only (no model). Roles: CIO, Operations, Finance, Risk, Data team, taken from `users.business_role` (words such as "CIO", "Operations", "Finance", "Risk", "Data"). A person may hold several; each card carries its `role` so the screen can switch.

| Role | Cards |
|---|---|
| CIO | open cases marked material; approvals asked |
| Operations | revisions, missing documents, breaks due today or overdue, documents with figures waiting for check, missing statements |
| Finance | breaks (accounting differences) |
| Risk | stale data, limit breaches |
| Data team | failed loads (rejected totals, quarantined), mapping proposals |

Card fields: headline, text, status word ("Revised · estimated", Estimated, Stale, Unverified), as_of, received, effect (currency + amount), owner, action, due, link, urgency (`needs_me` or `worth_a_look`). At most 7 per person per day; approvals are never cut and sort first. Running `generate` twice makes no duplicates; a dismissed card does not come back.

## Files
`sh_platform/v1/e5_pulse.py`, `e5a_routes.py`, `e5a.permissions.yaml`, `tests/v1/test_e5a.py` (5 tests).

## Routes
`GET /api/v1/pulse2/items?on_date=` -> `{items}` · `POST /api/v1/pulse2/items/{id}/acknowledge` (outcome `acted`) · `POST /api/v1/pulse2/items/{id}/dismiss` `{reason}` (reason required, outcome `dismissed_with_reason`).

## How to test on the demo
1. `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_e5a.py -q`
2. After E0e is seeded and the Fund A revision case exists: `python -c "from sh_platform.v1 import e5_pulse; ..."` calling `generate(plane)`.
3. Sign in as the CIO, `GET /api/v1/pulse2/items`: one card "Revised · estimated". Sign in as Mei: one card too.
4. Dismiss with and without a reason.

## Known limits
- `pulse_items` has no columns for status word, owner, due or link, so that detail is JSON in `summary`. If the data team adds columns later, `items()` is the one place to change.
- Missing-statement cards need the signed `statement_due` rule from E3a with `parameters.business_days` (or `days`); without it none are made. Expected statement date = last month end.
- Users are matched to the signed-in person by `users.external_identity_id == account_id`, else `display_name`.
- Cards for a case in a portfolio the person may not see are hidden (E1d `visible_portfolios`; raises if E1d is missing).
- Pulse changes do not write `exception_events` rows (pulse_items is not a case record).
- No model wording yet (optional in the card; the headline is the case title).

## Wiring for the orchestrator
- Call `e5_pulse.generate(plane)` on a schedule (for example hourly) and after E3b/E3c create a case or E2b/E0c writes a pending item. No shared file edited.
- E5c screen: `/api/v1/pulse2/items` as assumed.
