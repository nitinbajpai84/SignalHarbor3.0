# UX1 A2 (Intent and SOP)

Done: UX-03, UX-10, UX-12, UX-13. Skipped: none.
- UX-03 ConversationPage: "Sign the intent of work" (link to sign page), "Send to Build" note "The head of data will plan the build.", first-visit title "What do you need?" with the new subline.
- UX-10 Swimlane: under 760px a numbered list (step, Manual pill, lane); above it a muted "Scroll sideways to see all {n} steps." line. Map reuses it, so Map gets the same.
- UX-12 Sources: only known facts shown; none known gives "North will ask who owns this and how often it arrives."
- UX-13 SopPanel: "Download the procedure" / "Read the procedure here" / "Hide the procedure"; step detail as a definition list.
Files: i6/ConversationPage.tsx, Swimlane.tsx, SopPanel.tsx, SopPanel.test.tsx, i6.test.tsx. Backups in .sh-tmp/*.bak-ux1.
Tests: vitest src/v1/i6 passes (6/6). tsc --noEmit: errors only in cxui/TileCard.tsx, e5/k8.test.tsx, k5/ManagersInbox.tsx (other agents' areas); none in i6.
See it: open an Intent conversation, narrow the window below 760px for the list; sign, then Send to Build and the procedure buttons.

## Review

Verdict: pass. All four ids match the designer's wording exactly (UX-03 link, note, title and subline; UX-10 hint line; UX-12 fallback sentence; UX-13 three button labels and the definition list). Only i6 files were edited; backups exist for each.

Fixed in review:
- UX-10 narrow row order was name, pill, lane; the suggestion says lane, name, pill. Reordered (`Swimlane.tsx`).
- The narrow/wide switch had no test. Added `ui/src/v1/i6/Swimlane.test.tsx` (matchMedia stubbed): wide shows the scroll hint and the swim lane group; narrow shows the numbered list with lane, name and the Manual pill and no hint.

Checks run: `cd ui; npx vitest run src/v1/i6 src/v1/k3` → 4 files, 21 tests passed (k3 covers the Map process tab reuse). `npx tsc --noEmit` → two errors, both outside this area (`e5/k8.test.tsx`, `k5/ManagersInbox.tsx`); none in i6.

390px: the list is a plain `<ol>` of wrapping text buttons; the SOP definition list is `max-content 1fr` so the longest term ("If it goes wrong") leaves ~200px for the value; the action rows are `flex-wrap`. Reviewed from the markup only; no server was started (not allowed for this pass).

Open items (outside A2's files, not touched):
- `tests/e2e_10uc/uc10a_1.py:184-190` still looks for "Hand to the architect" and `uc9a_2.py:72-115` for "Download the SOP" / "Preview the SOP". They will fail until the e2e owner renames them to "Sign the intent of work", "Download the procedure", "Read the procedure here".
