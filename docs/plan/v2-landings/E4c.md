# E4c Action Desk screen

## What changed
`/centre/desk` (case list, ordered by materiality then due) and `/centre/desk/:caseId` (title with amount and currency, "Medium · maker Mei · checker Raj · Due 16 Oct", "Proposed by the investigation agent" box with sources, "Affects:" line, action buttons, history). Send back and Dismiss ask for a reason first. Buttons appear only when the server's `can` map says the viewer may press them, so the maker never sees Approve.

## Files
`ui/src/v1/e4/`: `api.ts`, `CasesPage.tsx`, `CasePage.tsx`, `routes.tsx`, `e4.test.tsx`.

## Assumed routes (E4a/E4b not on disk when built; confirm against `e4a_routes.py`)
- `GET /api/v1/cases` -> `{cases: [{id, number, title, materiality: high|medium|low, due, state, amount, currency}]}`
- `GET /api/v1/cases/{id}` -> the row plus `maker_name, checker_name, state_label?, proposal: {text, sources[]} | null, affects: string[], history: [{at, by, text}], can: {take, explain, submit, approve, send_back, dismiss, ask_finance: bool}`. `can` must be computed by the server (maker never checker).
- `POST /api/v1/cases/{id}/{take|explain|submit|approve|send-back|dismiss|ask-finance}`, body `{note}` for send-back and dismiss (reason), returns the updated case. `explain` calls E4b `propose_explanation`.

## How to test on the demo
1. Sign in as Mei (Operations), open `/centre/desk`: the Fund A revision case is first.
2. Open it: Take case / Submit for check show, Approve does not.
3. Sign in as Raj: Approve and Send back show; Send back asks for a reason.
4. `cd ui && npx tsc --noEmit -p . && npx vitest run src/v1/e4`.

## Known limits
Route paths and the `can` map are assumptions. No filters on the list. Ask Finance sends no note.

## Wiring for the orchestrator
Add `e4` to the version 1 UI routes index if it is not auto-discovered; nav entry "Action Desk" -> `/centre/desk`.

## After review (9 Oct)
Paths are `send_back` and `ask_finance`; bodies `{reason}`, `{explanation}`, `{to}`; `POST .../explain` is served by E4a. The detail carries `can`, `materiality`, `due`, `state`, `amount`, `currency`, `maker_name`, `checker_name`, `proposal`, `affects`, `history[{at,by,text}]`. The vitest uses `case.real.json` and `cases.real.json`, written by `tests/v1/test_e4a.py`.
