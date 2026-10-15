# E2d · Evidence Explorer screen

## What changed
Screens `/centre/evidence` (statement list) and `/centre/evidence/:documentId`. The detail page shows the header "Fund · valued date", the match line, the Superseded and Current statements side by side (value highlighted, "Page 2, line 14" link opening the original at that page, received dates), the fields table (field, original, amended, read confidence, state) and, for permitted users, Confirm reads / Not right (with a corrected value). A proposed match shows "Approve this match" when the viewer may.

## Files
`ui/src/v1/e2/`: `routes.tsx`, `api.ts`, `EvidenceList.tsx`, `EvidencePage.tsx`, `e2.test.tsx`.

## How to test on the demo
1. Seed Evergreen (E0e) and register both Fund A statements (E2a, E2e PDFs), run extraction (E2b).
2. Open `/centre/evidence`, then the Fund A statement.
3. Check Superseded (2 Oct) beside Current (9 Oct) and the match line.
4. Press Confirm reads on the value; the state becomes Confirmed.
5. Try Not right with a value; the state becomes Corrected.

Tests: `cd ui && npx vitest run src/v1/e2` (3 pass). `tsc` is clean for this folder (one unrelated error: `src/v1/e5/routes.tsx` imports a `BriefPage` that E5c has not written yet).

## Assumed routes (backend cards had not landed)
- `GET /api/v1/evidence/documents` -> `{documents:[{id,title,instrument_name,valuation_date,received_at,label:"Current"|"Superseded"}]}`
- `GET /api/v1/evidence/documents/{id}` -> `{id,instrument_name,valuation_date,can_review,versions:[{id,label,received_at,status_label,value_text,page,line,excerpt,file_url}] (oldest first),fields:[{id,field,original,amended,confidence 0..1,state:waiting|confirmed|corrected|rejected,page,line}],match:{identifier_id,source_name,instrument_name,status:approved|proposed|unknown,can_approve}|null}`
- `POST /api/v1/evidence/fields/{id}/confirm` body `{}` and `/correct` body `{value}` -> the updated field
- `POST /api/v1/evidence/aliases/{identifier_id}/approve` body `{}` -> the updated match
- `GET` of each version's `file_url` serves the original file (opened with `#page=N`)

## Known limits
No "reject" button (card lists Confirm and Not right only). Rejected state is displayed if the API sends it.

## Wiring for the orchestrator
None for the UI (auto-mounted by the glob). The backend (E2a/E2b/E2c routes) must provide or adapt the paths above; the detail route needs to join documents, extracted_fields and identifiers into the shape shown.

## After review (9 Oct)
The routes now answer in exactly the shapes above (joined by `sh_platform/v1/e2_screen.py`); confirm/correct return the mapped field, approve returns the match. The vitest uses `detail.real.json`, written by `tests/v1/test_e2d.py`.
