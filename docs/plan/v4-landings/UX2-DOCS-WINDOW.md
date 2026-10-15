# UX2: Saved documents in their own window

Nitin: "can you open a new window for the already saved documents".

## What changed
- "Add context for a more relevant conversation" › **Saved documents** (was "From the organisation's library", an inline box squeezed under the chat) now opens a large window over the page: about 80% of the screen on a desktop, full screen on a phone (760 px and below).
- Window (`ui/src/v1/workbench/SavedDocuments.tsx`, new): title "Saved documents"; a search box that searches file names across all folders; left column of folders with counts ("All folders" first); right column of the files in the chosen folder (or all files, or the search hits) with name, folder, date added, kind; a tick box per file; an **Open** link per file (new tab) to the existing document page `/centre/build/<iid>/source?file=<path>` (G3, no new backend route); footer "Use N files in the conversation" and "Cancel". Locked files still show K1's lock row with Request access; the owner's move, share and delete controls are kept.
- Ticks are held in the window until "Use N files in the conversation", which sends the same `PUT /api/v1/intents/<iid>/context` the composer already used; the chips ("North is reading 1 file: demo statements ×") and their untick are unchanged. Cancel or Escape leaves the conversation as it was.
- Dialog behaviour: `role="dialog"`, `aria-modal="true"`, labelled by its title; focus moves to the search box and Tab is kept inside; Escape, Cancel or a click on the dim background close it; focus returns to "Saved documents"; the page behind does not scroll. If "Use" fails, the error shows inside the window and it stays open.
- `ui/src/v1/l3/LibraryFolders.tsx` reshaped from the folder-tiles-then-list layout into the two-column window body (same API, same props). Styles added to `ui/src/v1/workbench/workbench.css`.
- Not done: **"Open the library in a new tab"**. There is no library page in the app (the only routes are `/centre/library/access`, "Requests to use files", and `/company/context`, which is a different document store), so no link was added. A page could be added later as a UI route rendering `LibraryFolders`; say if it is wanted.

## How to see it
Intent › talk to North › "Add context for a more relevant conversation" › "Saved documents". Tick "demo statements", press "Use 1 file in the conversation": the window closes and the chip reads "North is reading 1 file: demo statements ×". Try the search, a folder on the left, Escape, and a 390 px window (full screen, folders scroll sideways). Same in Span and Lumen where the composer is shared.

## Tests and results
- `ui/src/v1/workbench/workbench.test.tsx`: the old inline-library test replaced by five UX2 tests: opens as a modal with folders, counts and all files, focus inside, page scroll locked, Open link; search across folders; choose then Use (one PUT, chips, focus back, scroll restored, untick); Escape and Cancel change nothing and return focus; Tab is trapped. No i6 test clicked through the old box (i6 only checks the "Add context" button is there).
- `cd ui; npx vitest run src/v1/workbench src/v1/l3 src/v1/i6`: 4 files, 18 tests passed.
- `npx tsc --noEmit`: clean.
- Backups: `.sh-tmp/*.bak-docswin` (AddContextMenu.tsx, LibraryFolders.tsx, workbench.test.tsx, workbench.css).
