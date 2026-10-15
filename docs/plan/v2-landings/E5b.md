# E5b · CIO Brief backend (landed)

## What changed
- `brief(plane, viewer, report_version_id)`: the report as issued beside as known now (E1c), difference and a status word per line (official, estimated, revised, stale, unverified, draft), a banner when any line is draft, revised, stale or unverified that names the open case (CASE-0001 style), and the open cases. Lines of portfolios the viewer cannot see (E1d) are left out; if any is hidden the total line is dropped and `partial` is true. No visible portfolio means no lines (fail closed).
- `explain(plane, viewer, report_version_id, line_key, question=None, model=None)`: asks E4d `check_request` first (a refusal returns `{refused: true, reason, review_path}`), then returns the fixed format: `answer`, `evidence` (E1a chain, oldest first, superseded or current, with "statement title, page N, line M"), `figures` (issued, known_now, difference), `sources`, `caveats`, `next_action`, `approver`, `case`.
- Figures are copied by the program. The model (router task "summary", tier fast) sees no name and no figure; it returns one sentence with tokens (`{holding}`, `{issued}`, `{known}`, `{difference}`, `{issued_date}`, `{received_date}`). A reply with a digit or an unknown token is dropped for the fixed sentence. With the model off the fixed sentence is used and a caveat says so (`wording: "rules"`).
- Skill `skills/briefing/` (1.6k characters).

## Files
`sh_platform/v1/e5_brief.py`, `e5b_routes.py`, `e5b.permissions.yaml`, `skills/briefing/{playbook,questions,traps,examples}.md`, `tests/v1/test_e5b.py`, this note.

## Routes
- `GET /api/v1/brief/{rvid}` → brief
- `POST /api/v1/brief/{rvid}/explain` `{line_key, question?}` → explanation or refusal
Decimals and dates are strings in the JSON. 404 unknown version or hidden line, 503 when E1c, E1d or E4d is missing.

## How to test on the demo
1. `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_e5b.py -q` (8 tests).
2. After E0e seeds Evergreen and the amended statement is confirmed, open `GET /api/v1/brief/<September report version id>`: Fund A shows 10,000,000.00 issued, 10,180,000.00 known now, status revised, and the banner names the case.
3. `POST .../explain` with `{"line_key": "<Fund A line key>", "question": "Why did this move?"}`: the answer cites the amended statement, page 2, line 14.
4. Same with `"question": "Increase official NAV by $180,000"`: refused with the review path.

## Assumptions and limits
- E1c line shape is not fixed in the contract. Read tolerantly: `line_key | metric_value_id | instrument_id | label`, `label | name`, `value | numeric_value`, `currency`, `status`, `instrument_id`, `portfolio_id`, `metric_value_id`, `source_row_id` (a valuation_observations id, used to start the E1a chain; else the latest valuation of the instrument), `is_total`. If E1c names them differently, adapt `_lines` / `_key` in one place.
- Case number is read from the `opened` event note (how E4a stores it), else a `case_number` column if one is added.
- The viewer's access to a source document is judged by the portfolio of the valuation row that cites it (E1d has no document call); document access groups are not checked here.
- Tracing via `e6_trace.agent_run` is used when E6a exists; if not, a warning is logged and explain proceeds untraced (the only place a missing sibling is not fatal).
- E1c / E1d / E4d imports raise when missing (contract rule); `explain` of a line the viewer cannot see raises LookupError.

## Wiring for the orchestrator
- Include `sh_platform.v1.e5b_routes.router` (auto-installed by the card pattern; nothing else to edit).
- E5c assumed paths `/api/v1/brief...`: they match.
- No new packages.
