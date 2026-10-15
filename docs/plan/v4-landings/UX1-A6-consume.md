# UX1 A6 Consume

Files: ui/src/v1/cxui/ProjectList.tsx, ProjectPage.tsx, TileCard.tsx, cxui.test.tsx. Backups: .sh-tmp/<name>.bak-ux1.

## Done
- UX-01: links row on the Consume landing (ProjectList): Office view and CIO Brief -> /centre/consume/office, Managers -> /centre/consume/managers, Benchmark -> /centre/consume/benchmark.
- UX-02 (wording only): label "Find a project", placeholder "Monthly report", row = title then muted "id · stage", heading "Dashboards for <title>".
- UX-19: picture controls hidden behind an "Add a picture" link; share line prints "when the data changes / daily / weekly".
- UX-20: document "Figures available", column names only, "gold tables" wording removed.
- UX-22 (TileCard only): "Where is this from? ↗" is a 13px ds-link text button, same trail panel.

## Skipped
- UX-01 separate CIO Brief link: the brief route needs a report version id that only the Office data holds (brief_link). The Office link carries it ("Open the CIO Brief" card), so one link covers both. Benchmark route does not exist yet in any routes file; the link will 404 until another area adds it.
- UX-02 shared s1/ProjectPicker swap: that picker navigates straight to the project and cannot show the dashboards list inline; s1 is outside this area. Wording matched instead.
- UX-20 t.purpose: GoldTable from the API has no purpose field; not invented.
- UX-22 shared ds-link in TrailHost/Office/Recon/Action: other areas.

## Tests
cd ui; npx vitest run src/v1/cxui -> 5 passed. npx tsc --noEmit -> no errors in cxui.

## See it
/centre/consume (links, picker), pick a project, open it: Add a picture link, "Figures available" tab, Share tab.

## Review

Verdict: pass, with two small fixes applied by the reviewer.

- Checked each id against docs/test/UX-REVIEW-1.md wording: UX-01 (three links on the landing, nothing in k4/k5), UX-02 (label, placeholder, row order, heading), UX-19 ("Add a picture" link; refresh printed in words), UX-20 ("Figures available", column names only), UX-22 (TileCard text link, same trail panel). All match.
- Fixed: the two `button.ds-link` elements (TileCard "Where is this from? ↗", ProjectPage "Add a picture") had no button reset, so they rendered as grey browser buttons, not text links. Added the same inline reset the repo already uses for button.ds-link (background none, border 0, padding 0, font inherit, 13px).
- Fixed: the four edited files had been saved with CRLF line endings (backups are LF); normalised back to LF.
- Tests: `cd ui; npx vitest run src/v1/cxui` -> 5 passed. `npx tsc --noEmit` -> no errors in cxui; the two errors reported are in e5/k8.test.tsx and k5/ManagersInbox.tsx (other areas, not touched).
- Nothing outside ui/src/v1/cxui touched by this area.
- 390px: the links row wraps (flex-wrap), the project rows are inline-flex buttons whose text wraps, the composer stacks under the workbench's 760px rule. No sideways scroll introduced.

Open items (for other areas)
- /centre/consume/benchmark has no route anywhere yet; the link 404s until one lands.
- TileCard duplicates the TrailPanel glob and open state from a5/TrailHost.tsx; when A9 does UX-22 across the product, give WhereFrom a link variant and drop the copy here.
- UX-02 shared picker (s1/ProjectPicker) still differs from Consume's inline picker; A5/A1 to decide.
