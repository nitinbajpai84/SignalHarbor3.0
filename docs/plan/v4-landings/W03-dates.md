# W03-dates (UX-25)

Changed: new `ui/src/design/dates.ts` exports `day` ("9 Oct 2026"), `time` ("09:12"), `when` ("9 Oct 2026, 09:12"); fixed format, ignores viewer locale. Bare YYYY-MM-DD is read as written (no timezone shift).
- k5/api.ts `day` and k3/dates.ts `day` now call the shared helper (k3 keeps "Not available yet" fallback).
- a5/ReconPage: last run uses `when()`, as-at uses `day()`; state var `day` renamed `asAt`. a5/CaseView: "valued" date uses `day()`.
See: Action > Reconciliation "Last run"; Evidence case list; Managers inbox; Consume tabs.
Not mine (other cards): s1/SettingsPage.tsx:43 still uses its own style.
Tests: design/dates.test.ts (3 new); vitest a5, k5, k3, design/dates: 8 files, 39 passed.

## Review

- Verdict: pass with one small fix.
- Tests re-run: `npx vitest run src/design/dates src/v1/a5 src/v1/k5 src/v1/k3`: 8 files, 39 tests pass. `tsc --noEmit` shows no errors in the card's files.
- Scope: edits stay in design/, a5, k5 and k3. s1 is untouched. No toLocaleString, Intl or raw ISO display is left in those folders.
- Fixed: `today()` in `a5/ReconPage.tsx` used the UTC date, so before 08:00 in Hong Kong the default "as at" date was yesterday. It now uses the local calendar day. Backup: `.sh-tmp/ReconPage.tsx.bak-W03-review`.
- Open: `s1/SettingsPage.tsx:43` still has its own date style. The s1 card owns it, and it should use `day`/`when` from design.
