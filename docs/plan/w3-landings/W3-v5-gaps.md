# W3-v5-gaps: filling the gaps against the approved designs

Backups: `.sh-tmp/*.bak-w3`. Nothing committed. No model calls. app.py and the router untouched.

## What landed
- **D5 Project complete**: four-step row, "What was verified" now leads with the figure line (portfolio, benchmark, points) and the benchmark mix line (approved version and weights), both read from the b9_verify review and the signed benchmark; "Added to the company knowledge map" lists sources, tables, definitions, dashboards and people from the project's own records, marked Verified only where a record says so. Fixed a latent bug: the old summary read a `signed` field that never existed, so the signed lines never showed; it now reads the artefacts.
- **D4 Delivery**: side preview panel (Slack first, any channel via its Preview button), benchmark sentence, email subject, Morning Note line, "Where is this from?" (opens the tile trail panel), link to the Slack thread in Consume. Stopped channels now sort below live ones. Duplicate crumb removed.
- **C5**: the send form opens with portfolio, benchmark code, month and a drafted message (b9_verify.suggest); "Attached to the message" card.
- **C6**: link to the signed benchmark definition (Consume, Benchmark) and Lumen's note on the mix (`lumen_note`).
- **E5**: PowerPoint export, `GET /api/v1/consume/reports/{version_id}/pptx` (python-pptx 1.0.2 is installed; the button shows only when the server reports `pptx_available`). Declared in k10.permissions.yaml.
- **E7**: `/centre/consume/slack`: Lumen's post built from the Morning Note, replies shown from the comments on that note. Linked from the email preview, the reports library and the delivery panel.
- **F1**: graph drawn to fit its width (narrower nodes, viewBox, stops shrinking at 62% and scrolls); nothing reaches past the right edge.
- **Run log paging**: five runs a page, Newer/Older.
- **Duplicate crumb** "All projects · Plan and Span" under the stepper removed in the three rooms and Delivery.
- **Route**: `GET /api/v1/morning-note/delivery-lines` is now `GET /api/v1/consume/delivery-lines` (d1_routes.py, d1.permissions.yaml, k10 api.ts, k10 test mock, d1 test).

## Difference for Nitin's approval
1. E7: the design shows a Lumen answer card with a table and a named channel (#investment-office). We have no stored Lumen thread answers or channel names (they are secrets by name), so the thread shows only real comments on the note; Lumen's reply appears only if one was written. No "Raise as a case" button.
2. D4: the "BEFORE THIS" context block and per-card sentences ("Posted to #family-council-performance...") are not added; the cards keep the existing wording.
3. D5: the knowledge list is derived from the plan, dashboards and people records; the count and groups can differ from the design's 16 items, and "Verified" is shown only where a record backs it.
4. C6: Lumen's note is generic wording from the weights ("All 3 weights differ from version 1: ..."); it cannot say "the run used version 2" because the run does not record which version it used.
5. E5: the PowerPoint is a plain table deck (title slide, then the lines as issued), not the styled design.
6. F1: nodes are narrower (132 px) with labels cut at 17 characters.

## Tests
- Python: test_d1_delivery 15, test_b9_verify 5 (1 new), test_k10_note 24 (1 new, route table updated), test_k3 + test_k3_onto: all pass (44 across k10/k3/k3_onto, 20 across d1/b9).
- UI (vitest): k3, b6, d1, b9verify, b8, k10: 84 pass (8 new). tsc clean except a pre-existing error in k12/PainPointDemo.tsx (not mine).

## Review
Reviewed: route move (no old path left in py/ts/yaml), pptx route and permission, D5 summary and knowledge list, C5 suggest, C6 note, D4 channel order, run log paging, F1 graph, E7 Slack page. No code defects found, no edits made.
- Access: pptx and delivery-lines are declared (default deny holds); pptx refuses an unsigned version and uses the same viewer-filtered lines as the PDF; C5 suggest is only built for the data engineer and skips portfolios the viewer may not see.
- Failure handling: figure lines and the knowledge list degrade to nothing on a missing review or warehouse; pptx returns a plain 404 message when python-pptx is absent.
- Not exercised: the UI suites and tsc were not rerun; the Python d1/b9/k10 tests were run (see the verdict).
- The six listed differences stand and still need Nitin's approval; no unlisted difference found.
