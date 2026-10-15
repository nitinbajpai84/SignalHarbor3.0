# V6-lumen-starter (design H10)

## Built
- `cx_lumen.propose_starter(plane, pid)`: deterministic, no model. Key-figure tiles from the signed intent KPIs (each KPI matched to a gold column by its name; a KPI no table holds is not invented), trend against the benchmark KPI (one line, two series, last 12 months), a bar breakdown for each column the intent names (by fund, by entity), and a checks line from the live plan version and its last live run. Every tile has a trail (tables read, KPI, pack version) and reads this project's gold tables only (checked by `D.check_sql`). With no signed KPI matched it uses each table's first figure and says so.
- `b7_studio.start_starter` (once per project; draft, Lumen's own, tiles proposed and already placed on the grid, nothing in Consume) and `accept_starter` (Accept as it is: tiles still on the grid accepted, removed ones dropped).
- Goes live hook: `b6_run._move` calls `start_starter` after a live run (failure logged, never fails the run).
- Routes (in the existing b7 router and b7.permissions.yaml): `POST .../studio/starter`, `POST .../studio/{did}/starter/accept`. `submit` accepts a waiting starter first.
- UI: `ui/src/v1/b7/StarterBanner.tsx` (why Lumen chose these; Accept as it is / Add something specific / Send for approval), wired in StudioPage; starter tiles are kept out of the chat's Accept / Not this list; empty studio shows "Ask Lumen for a starter dashboard".
- Edits outside the card's files (small): `cx_dash.starter_open` (data team may open and edit a starter draft, used by `_editor` and `may_view`), `b6_run._move` hook, `b7.permissions.yaml`, `b7_routes.py`.

## How to see it
Run a live pipeline run on a project with gold tables (or in the studio, "Ask Lumen for a starter dashboard"); open Build > Dashboard studio. Accept, ask Lumen for something more (existing conversation), or Send for approval (existing approval by head of data or sponsor, never the person who accepted).

## Tests
- Python: `tests/v1/test_h10_starter.py` 9 passed; with test_b7_studio, test_cx, test_lumen_loop/w2/aq1/aqf13 (161 passed) and test_b6_run, test_b6_run_lock (all passed).
- UI: `src/v1/b7/b7.test.tsx` 17 passed (2 new), `tsc --noEmit` clean. No vite build.

## Mount lines
None. The new routes sit on the already mounted `b7_routes.router`; no change to app.py or router.tsx.

## Difference for Nitin's approval
- The checks tile is a text widget (program-written from the plan and last run), not a table tile, because checks are not stored in a gold table.
- The design's "Fund A amended / revised value" line and placeholder points are not produced: figures come from the gold rows only.
- The starter is made under Lumen's name and opened to the data team (company_admin, analyst) rather than one owner.

## Open items
- Layout is fixed (figures row, trend plus checks row, breakdowns row); at most four key figures and two breakdowns.
- Starter is proposed once per project; a later pipeline change does not regenerate it.

## Review
- Maker-never-checker holds: Lumen is creator, the accepting person is added to editors (begin_edit) and is the submitter, and decide_version/can_approve refuse creator, submitter and editors; submit-with-waiting-starter accepts first as the same person.
- Never ask twice holds: Send for approval accepts the waiting starter itself, so no separate Accept is needed; the Accept button disappears once accepted.
- Access: starter_open limits the open draft to company_admin and analyst; Consume sees nothing until approval. No defect found, no code changed.
- Tests re-run: test_h10_starter, test_b7_studio, test_b6_run, test_b6_run_lock 61 passed (UI tests not re-run; builder reported 17 passed, tsc clean).
