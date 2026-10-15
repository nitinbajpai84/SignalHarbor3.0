# W09-css-literals: Replace colour literals with design tokens

Card completed: all colour literals in ui/src/v1/workbench/workbench.css and ui/src/v1/t1/templates.css replaced with tokens from ui/src/styles/design.css.

## Changes made

### ui/src/v1/workbench/workbench.css
- `.wb-line--add`: border-color #2e7d32 → var(--ds-teal); background rgba(46,125,50,.14) → color-mix(in srgb, var(--ds-teal) 14%, var(--ds-ground))
- `.wb-line--change`: border-color #b26a00 → var(--ds-amber); background rgba(255,160,0,.18) → color-mix(in srgb, var(--ds-amber) 18%, var(--ds-ground))
- `.wb-line--remove`: border-color #b3261e → var(--ds-red); background rgba(179,38,30,.12) → color-mix(in srgb, var(--ds-red) 12%, var(--ds-ground))
- `.wb-hl-changed`: background rgba(255,160,0,.28) → color-mix(in srgb, var(--ds-amber) 28%, var(--ds-ground))
- `.wb-hl-removed`: background rgba(179,38,30,.16) → color-mix(in srgb, var(--ds-red) 16%, var(--ds-ground))
- `.wb-docs-head`: background var(--ds-bg,var(--ds-surface,#fff)) → var(--ds-surface)
- `.wb-popover`: background var(--ds-surface,#fff) → var(--ds-surface)

### ui/src/v1/t1/templates.css
- `.tpl-sec--grey`: border-left-color var(--ds-line-2,#bbb) → var(--ds-line-2)
- `.tpl-sec--new`: background var(--ds-teal-soft,rgba(0,150,136,.10)) → color-mix(in srgb, var(--ds-teal) 10%, var(--ds-ground))
- `.tpl-sec--new`: border-left-color var(--ds-teal-bright,teal) → var(--ds-teal-bright)
- `.tpl-req`: color var(--ds-amber,#b26a00) → var(--ds-amber)
- `.tpl-grey`, `.tpl-empty`, `.tpl-from`, `.tpl-new`: color var(--ds-muted,#777) → var(--ds-ink-muted)
- `.tpl-table`, `.tpl-card`, `.tpl-pick`, `.tpl-thumb`, `.tpl-preview`: border var(--ds-line-2,#ccc) → var(--ds-line-2)
- `.tpl-thumb b`: background var(--ds-text,#333) → var(--ds-ink)
- `.tpl-pick`: background var(--ds-surface,transparent) → var(--ds-surface)
- `.tpl-thumb i`: background var(--ds-line-2,#bbb) → var(--ds-line-2)
- `.tpl-thumb u span`: border var(--ds-line-2,#bbb) → var(--ds-line-2)
- `.tpl-thumb .req`: background var(--ds-amber,#b26a00) → var(--ds-amber)
- `.tpl-pick[data-chosen]`: border-color and box-shadow var(--ds-teal-bright,teal) → var(--ds-teal-bright)
- `.tpl-thumb`: background var(--ds-surface-2,rgba(128,128,128,.06)) → var(--ds-surface-2)

## Test results

- Colour literal test: **PASS** - 17 of 18 tests pass
- No colour literals found in either file (excluding design.css token declarations)
- File location test reports v1/t1/templates.css and v1/workbench/workbench.css as unexpected (see note below)

## Test note: File location detection

The test "the old scaffold token file is gone and shell.css was really read" (line 72 of src/look.test.tsx) reports these two files as unexpected in the CSS file list. This is expected and correct - the files have been edited per the card but exist outside the styles/legacy directory structure that the original test assumed. Per task instructions: "report rather than editing the test" when the scaffold test lists files as unexpected. No test edits needed.

## Token mapping summary

- Diff line highlights: #2e7d32 (green add) → --ds-teal, #b26a00 (orange change) → --ds-amber, #b3261e (red remove) → --ds-red
- Soft/transparent backgrounds: used color-mix(in srgb, var(--ds-color) NN%, var(--ds-ground)) pattern for opacity effects
- Fallback values cleaned: #bbb → --ds-line-2, #ccc → --ds-line-2, #777 → --ds-ink-muted, #333 → --ds-ink
- Undefined tokens removed: eliminated fallbacks for --ds-teal-soft, --ds-bg, --ds-text, --ds-muted (not in design.css)

Files backed up to .sh-tmp/workbench.css.bak-redo and .sh-tmp/templates.css.bak-redo

## Review
Verdict: pass. Re-ran look.test.tsx: 17 pass, 1 fail. No colour literals remain in either file; all colour vars used exist in design.css. The failing test (look.test.tsx line 72) hard-codes an exact stylesheet list that does not include v1/ files; it was not edited, owner must add the two v1 paths. No defects fixed.
