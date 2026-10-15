# UX3 Library page

Route `/centre/library` (ui/src/v1/l3/routes.tsx, LibraryPage.tsx). Reads `GET /api/v1/library/folders` (existing L3 route); no backend change.

- Reuses LibraryFolders (folders with counts, search across folders, name, folder, date added, kind, Open, locked rows with Request access, move-folder). LibraryFolders now works without ticks when no tick handlers are passed.
- Owner controls (Share with the company, Delete) are passed through `extra`, as in the Saved documents window.
- Open links need a project (`/centre/build/<iid>/source?file=<path>`). The Saved documents window passes `?iid=`; opened from the menu or the Intent landing, Open is not shown (limit; add a default project when the source page no longer needs one).
- Links: "Open the library in a new tab" in Saved documents, "Library" chip on the Intent landing, "Library" in the account menu.
- Tests: LibraryPage.test.tsx, workbench.test.tsx (link), shell.test.tsx (menu).

## Review
Verdict: accept with one known gap. Checked page, three links, backups, scope (only the link lines changed in IntentHome, CentreShell, SavedDocuments, copy files), tsc clean, vitest over l3, workbench, shell and intents: 360 of 361 pass. The one failure (intents/WallView.test.tsx, wall header text) is outside this work and does not touch the library. Gap: Open is hidden when the page is opened without ?iid= (menu and landing). Needs a default project; not decided here. Not viewed in a browser.
