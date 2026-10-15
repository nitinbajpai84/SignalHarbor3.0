# UX1 A1 (shell and settings)

Done: UX-06, UX-08, UX-11, UX-23, UX-24. Skipped: none.

- UX-06: Settings grid stacks under 720px (`SettingsPage.tsx`); People intro now "Who can open which centre. The administrator sees everything."
- UX-08: centre labels in sentence case, 14px, each with a `title` (shell/copy.ts, barStyle.ts, CentreShell.tsx). Names unchanged. Role chip kept (plain role words), not hidden, per the task.
- UX-11: cost two decimals, "USD 0.00 (under a cent)" below one cent; failed run reads "North could not finish a run on 9 Oct at 03:12. Open the case."
- UX-23: Escape and click-outside close both menus; menus have role="menu"; company initials chip now stays on phones (only the company name is hidden).
- UX-24: refused line is "That page is not open to you. This is your start page."

Tests: `npx vitest run src/shell src/App.test.tsx src/v1/s1 src/pages/control.test.tsx` all pass (updated shell.test.tsx, App.test.tsx, k8.test.tsx in v1/s1, pages/control.test.tsx for the new wording and the "Map" link). `tsc --noEmit`: only errors in files outside my area (v1/e5/k8.test.tsx:18, v1/k5/ManagersInbox.tsx:16).

See it: open any centre page and narrow to 390px; open Settings > People and access, Agent runs and cost; visit a page your role cannot open.

Backups: .sh-tmp/*.bak-ux1 (copy.ts, barStyle.ts, CentreShell.tsx, SettingsPage.tsx, shell.test.tsx, k8.test.tsx). App.test.tsx and pages/control.test.tsx were edited by sed with no backup (one-word assertion changes).

## Review

Verdict: pass with two small fixes applied.

- UX-06, UX-08, UX-11, UX-24: wording and behaviour match the designer's text; names Intent, Action, Build, Consume, Map kept; role chip kept with plain words (task override of the "hide" suggestion).
- UX-23 defect fixed: the edit un-hid `.cs-company-name` on phones instead of keeping the initials chip (which was never hidden). At 390px the brand, company name and avatar would overflow the bar. `barStyle.ts` now hides the company name under 720px again; the chip stays. Escape, click-outside and `role="menu"` are correct.
- Line endings: `copy.ts`, `barStyle.ts`, `SettingsPage.tsx` had been rewritten CRLF (backups are LF); normalised back to LF.
- Nothing outside the area touched by A1 beyond the two test files already declared.
- Tests: `npx vitest run src/shell src/App.test.tsx src/v1/s1 src/pages/control.test.tsx` — 4 files, 89 passed. `npx tsc --noEmit` — one error left, `src/v1/k5/ManagersInbox.tsx:16`, outside A1 (the earlier e5 error is gone).
- Open: UX-25 (shared `day()`/`when()` helper in `ui/src/design`) was not in this task; `SettingsPage.tsx` has its own local `when()` that should move there when UX-25 is done.
