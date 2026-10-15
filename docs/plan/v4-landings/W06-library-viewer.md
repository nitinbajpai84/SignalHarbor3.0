# W06-library-viewer: read a library file with no project

Backups: `.sh-tmp/routes.tsx.bak-W06`, `LibraryFolders.tsx.bak-W06`, `LibraryPage.test.tsx.bak-W06` (api.ts was appended to only).

## What changed
- `sh_platform/v1/l3b_routes.py` + `l3b.permissions.yaml` (all six roles): `GET /api/v1/library/view?file=<path>` returns `{name, lines:[{n,text}]}` (first 3,000 lines, read on the machine with `doc_index.read_lines`, so numbers match the source viewer). Same check as the library list (C4 `visible`), then K1 `readable`. A file the person cannot see, an unknown path or a missing `file` gives the same 404 sentence (nothing leaks); a visible but locked file gives 403 with a plain sentence; a sample folder gives 400.
- `ui/src/v1/l3/LibraryViewPage.tsx` at `/centre/library/view?file=`; route added in `routes.tsx`; `getFileView` in `api.ts`.
- `LibraryFolders.tsx`: on the Library page, when no project fits (no `?iid=` and the person has no project) and the file is not locked, Open links to the viewer. With a project it still opens the source page.

## How to see it
Sign in as a person with no project, open Library, press Open on any readable file: a new tab shows the file with line numbers.

## Tests
- pytest `tests/v1/test_l3b.py`: 1 passed (owner reads, another person gets 404 for a private file, 404 for a non-library path and no param, shared file readable, deleted file 404, no sign-in refused).
- vitest `src/v1/l3`: 8 passed (4 new: route, lines, refusal, Open link target).

## Not done / notes
- Folder items (landing samples) are not viewable here (400).
- Sensitive-file access requests stay on the Library page; the viewer only refuses.

## Review
Verdict: pass. Re-ran `tests/v1/test_l3b.py` (1 passed) and `vitest src/v1/l3` (8 passed). Scope is within the card (new l3b files, `ui/src/v1/l3/`, one new test file). Refusal wording is plain and the 404 is identical for hidden, unknown and missing files. No defects fixed.
Open items: files over 3,000 lines are cut off with no note on the page; the page has no sign-in-expired state beyond the generic message.
