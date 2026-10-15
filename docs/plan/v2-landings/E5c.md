# E5c Daily Pulse and CIO Brief screens

## What changed
Two screens under `ui/src/v1/e5/`, auto-mounted by `routes.tsx` (no shared file edited).
- `/centre/today` Daily Pulse: role switch (shown only when the user has several roles), "Needs me" / "Worth a look" filters, cards with a written status pill, headline, "Valued / received / affects" line, Open evidence, Take case, Dismiss (needs a typed reason).
- `/centre/brief/:reportVersionId` CIO Brief: title, draft banner (with link to the case), table Holding / Issued / Known now / Status, USD/SGD switch, "Why did this move?" panel calling explain, sources as chips, refusal shown with its review path.
Figures arrive formatted with currency from the server; the UI computes nothing.

## Files
`ui/src/v1/e5/`: `api.ts`, `TodayPage.tsx`, `BriefPage.tsx`, `routes.tsx`, `e5.test.tsx`.

## Assumed routes (confirm against E5a / E5b / E4a)
- `GET  /api/v1/pulse2/items[?role=]` -> `{role, roles[], items[{id, headline, status, valued, received, affected, needs_me, case_id, evidence_href}]}`
- `POST /api/v1/pulse2/items/{id}/dismiss` body `{reason}`
- `POST /api/v1/cases/{caseId}/take` body `{}` (Take case)
- `GET  /api/v1/brief/{reportVersionId}?currency=USD` -> `{title, issued_on, currency, currencies[], banner{text, case_id}|null, lines[{key, holding, issued, known_now, status, changed}]}`
- `POST /api/v1/brief/{reportVersionId}/explain` body `{line_key, question}` -> `{answer, evidence[], sources[{label, href}], caveats[], next_action, approver}` or `{refused, reason, review_path}`
Case link targets assumed: `/centre/desk/:caseId` (E4c), `/centre/evidence/:documentId` (E2d). Server pre-formats status words ("Revised · estimated") and sorts items.

## Test on the demo
1. Seed Evergreen (E0e) and run the revision story; sign in as the CIO.
2. Open `/centre/today`: the Fund A card reads "Revised · estimated"; switch to Worth a look.
3. Dismiss a card: the button stays disabled until a reason is typed.
4. Open `/centre/brief/<report version id>`: banner, Fund A 10,000,000 vs 10,180,000, switch to SGD, click Why did this move?.
Tests: `cd ui && npx tsc --noEmit -p . && npx vitest run src/v1/e5`.

## Known limits
Not run against the real routes (E5a/E5b not landed). No pagination. Dismiss reload refetches the list.

## Wiring for the orchestrator
None; nav entries for "Today" and "Brief" are the shell owner's to add.
