# UX1 A9 (Map)

Done: UX-21.
- `ui/src/v1/k3/MapPage.tsx`: Health tab is not shown unless `canSettings(roles)`; a `?tab=health` link from someone else falls back to Data flow.
- `ui/src/v1/k3/FlowTab.tsx:56`: "Click a box" now "Choose a box".
- `ui/src/v1/k3/k3.test.tsx`: mocks `useSession` (analyst by default); new test checks Health is hidden for a sponsor.

Skipped: none.

Tests: `npx vitest run src/v1/k3` 13/13 pass. `npx tsc --noEmit`: no errors in k3; two existing errors elsewhere (`e5/k8.test.tsx:18`, `k5/ManagersInbox.tsx:16`, not my area).

See it: sign in as a sponsor and open /centre/map (no Health tab); as analyst or company admin the Health tab shows.

Backups: `.sh-tmp/*.bak-ux1` (MapPage.tsx, FlowTab.tsx, k3.test.tsx).

## Review

- UX-21 matches the designer's wording: Health tab hidden via `canSettings`, not refused; empty-state hint reads "Choose a box…". Centre and agent names untouched; no explainer text added.
- Diff against `.sh-tmp/*.bak-ux1` shows only the three named files changed; nothing outside k3 touched by this work.
- Fix applied: `k3.test.tsx` now resets `roles` in `afterEach` instead of at the end of the sponsor test, so a failed assertion cannot leak the sponsor role into later tests. 13/13 still pass; `tsc --noEmit` has no k3 errors (the two remaining are `e5/k8.test.tsx:18` and `k5/ManagersInbox.tsx:16`, other areas).
- 390px: tab row is `flexWrap: wrap`, Flow columns scroll horizontally and the aside wraps below; layout code unchanged by UX-21, so nothing new to break.
- Open item (not A9's): `shell/roles.ts:32` already keeps Map out of the bar for non-`canSettings` roles, so a sponsor only reaches `/centre/map` by link; the hide is still right for that path.
