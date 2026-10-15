# V5W-5 Consume reading room: review

Landing note: `V5W-5.md`. Reviewer pass (reasoning tier), 11 Oct 2026. No code changed by the review.

## Checked
- **Tests re-run**: `pytest tests/v1/test_k10_note.py` 22 passed; `npx vitest run src/v1/k10 src/v1/cxui` 33 passed.
- **Access, default deny**: all seven GET routes are declared in `k10.permissions.yaml` (same six roles as the existing `/api/v1/consume/daily` and `/api/v1/reports`), loaded by the existing glob; a route with no line is refused. Figures come through k4/k5/k6/k9/e4/e5 with the viewer passed in, so the E1d entity filter applies (test `test_a_person_sees_only_their_entities`). The PDF goes through `e5_brief.brief(plane, viewer, ...)`, so it prints only lines the viewer may see, says when lines are left out, and refuses unsigned (409) or missing (404) versions. The reports list uses `e1_reports.listing(plane)` without a viewer, the same exposure as the existing `GET /api/v1/reports`.
- **Egress**: there are no network, model or mail calls in `k10_note.py`, `k10_routes.py` or `k10/api.ts`. `render_email` only builds the template; package 4 sends it. Market levels, FX and manager letters are marked `outside: true` with a source and date, and the email footer says market figures are outside material. Locked library files show no text.
- **Maker never checker**: the package is read-only and writes nothing. A PDF exists only for `issued` versions and shows the named signer.
- **Nothing dropped**: every old Consume link is still there. Office view, Managers, Benchmark, Signed KPIs, Statements and Library are on Reports; Business views and Offers are on Market signals; Shape what you see, company dashboards and dashboard comments are on Dashboards; DailyNumbers is on P&L; Shared with you has its own tab; Lumen TalkBox is the side panel. `/centre/consume/p/:projectId` still mounts. The only removal is the project picker ("Your projects"), which the card asked for.
- **Email preview** renders the HTML in `<iframe sandbox="">`, and every value is escaped.
- **Money**: values are Decimal end to end; a missing figure reads "Not available yet." and is never shown as zero.

## Defects and open items
1. **Integration blocker, not in this package's files.** `GET /api/v1/consume/morning-note/delivery-lines` (d1_routes.py, package 4) has two segments, and `install()` includes routers in sorted order, so c1's `GET /api/v1/consume/{iid}/{code}` (c1 sorts before d1) matches it first and answers 422/404. The Morning Note's package 4 sections therefore never appear; `getSections` falls back to `[]` without an error. Fix at integration: move the d1 route to a single segment, for example `GET /api/v1/consume/delivery-lines`, in d1_routes.py, d1.permissions.yaml and `ui/src/v1/k10/api.ts` line 71 (and the k10.test.tsx mock).
2. **Not built from the designs**: the E7 Slack thread preview, the PowerPoint export (E5), and "07:00" in the note kicker.
3. **Invented mapping, shown on screen**: `_index_for` chooses each fund's "compared with" index from its asset class and name (ponytail note in the module docstring). No alpha is computed from it, but the column presents an unsigned rule. A signed fund-to-index mapping should replace it, or the column should say "provisional". Product owner to decide.
4. `reportlab` is not in requirements.txt. Add it at integration; without it the PDF button explains that a PDF cannot be made.
5. "Needs you today" lists all open cases, not only the viewer's, because the seeded cases have no assignee (noted by the builder).
6. Not done: screenshots against the artboards and a live Lumen check (no model calls under the cost rule).

## Verdict
Pass with integration items. The code is sound on access, egress and money; item 1 must be fixed when the packages are mounted.
