# G3 and G4 screens: landing

## Summary
1. Benchmark sheet (`ui/src/v1/g3/BenchmarkSheet.tsx`): on the project page, the "Benchmark sheet" chip shows a table with one column per dimension, reported, expected, tolerance, source (link, "file, line N"), stated by, and an "After the load" cell (Met / Missed with expected and got / Not compared / Not loaded yet).
2. `needs figure` rows are highlighted with "No figure yet for ...", a figure box and Save figure. "Sign the sheet" shows the server's refusal sentence; "Download .xlsx" uses the export route.
3. Deviation card (`DeviationCards.tsx`): before / after / why / rows it would fix; Approve and Not this (reason box) only for the people it is addressed to, read-only ("Waiting for Leela.") for everyone else. Shown on the project page (above the artefact) and on `/centre/build/:iid/deviations` (`DeviationsPage.tsx`, `routes.tsx`).
4. Engineer screen: a pending deviation point shows "Waiting for approval: open the request", linking to that page.
5. Tests: `ui/src/v1/g3/g3.test.tsx` (3, mocked fetch). `npx tsc --noEmit` clean; vitest g3, p1, f1, i1, i6 pass (13).

## Edits outside g3/ (additive, small)
- `p1/api.ts`: `Kind` and `KINDS` gain `benchmarks` (placed before brief).
- `p1/ProjectPage.tsx`: label, the `DeviationCards` line, and `BenchmarkSheet` above the generic `ArtefactView` when the chip is `benchmarks` (the generic view keeps the line comments).
- `f1/EngineerPage.tsx`: one line in `PointCard` (the engineer-screen link).

## How to test by hand
1. Run the backend and UI (G3G4.md steps 1 to 4 make the data). Sign in as Arjun, open `/centre/project/<pid>?artefact=benchmarks`.
2. Rows with no figure are highlighted; press "Sign the sheet" and read the refusal; type a figure, Save figure, sign again. Check "Download .xlsx".
3. As Leela load the data (`POST /api/v1/build/<iid>/load`), reload: each row shows Met / Missed with expected and got.
4. As Leela raise a deviation (G3G4.md step 5). Open `/centre/project/<pid>` as Leela: Approve / Not this (reason). As Arjun: read-only card. The engineer page (`/centre/build/<iid>/engineer`) lists it under Open points with the link.
5. Pulse approval card opens the project page; the deviation card is at the top of it.

## API gaps and notes
- No route reads the document to open from "file and line": the source link goes to `/centre/intent/<iid>/extraction?file=<path>&line=<n>`, which does not use those query values yet.
- "Drop last month's report in" has no screen: the figure box covers typed figures; `POST .../sheet/read {file}` has no upload control (needs a library file picker).
- The check result comes from `GET /api/v1/build/<iid>/benchmarks` (`verify`), matched by `row_id`.
- The Pulse card opens the project page at the comment's artefact, not at the deviation; the card sits at the top of the page either way.
- The engineer point `kind: "deviation"` is not in f1's `PointKind` type (cast in the one line); its pill shows no kind label.
- Full vitest run once timed out in i1 and i6 under load; both pass alone.
