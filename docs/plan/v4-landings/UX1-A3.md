# UX1-A3 (action today and cases)

Done
- UX-14: on each Today card "Dismiss" is now a right-aligned text link "Not for me"; the reason box and "Dismiss with reason" are unchanged. File: ui/src/v1/e5/TodayPage.tsx.
- UX-04 (Today part): TodayPage takes `framed`; ActionCentre passes it, so inside Action there is one title (Action) and Today's own title and sentence are gone. The "Viewing as" selector stays. Standalone /centre/today keeps its title.

Skipped
- UX-04 for Cases, Reconciliations, Managers: their pages live in ui/src/v1/e4/, a5/ReconPage.tsx and k5/ (outside my files or forbidden). Each needs the same `framed` prop, passed from ActionCentre.tsx (one-word change per tab).

Tests
- npx vitest run src/v1/e5 src/v1/a5/a5.test.tsx src/v1/a5/k8.test.tsx: 4 files, 13 tests pass (e5.test.tsx updated to click "Not for me").
- npx tsc --noEmit: no errors in my files. Remaining, not mine: cxui/TileCard.tsx(35), k5/ManagersInbox.tsx(16), e5/k8.test.tsx(18) (test file, null vs string, present before my edit).

See it: open /centre/action; one title, cards with a "Not for me" link at the right.
Backups: .sh-tmp/{TodayPage.tsx,ActionCentre.tsx,e5.test.tsx}.bak-ux1

Review
- Verdict: accepted with two small fixes applied by the reviewer.
- UX-14 matches the designer's wording: "Dismiss" is a right-aligned text link "Not for me" (marginLeft auto, ds-link); the reason box and "Dismiss with reason" are unchanged. Fix: the link is a `<button>`, which does not inherit the page font, so `font: inherit` was added; without it the link rendered in the browser's default 13px button font.
- UX-04 (Today) matches: inside Action there is one title; "Viewing as" stays; /centre/today keeps its own frame. Fix: the framed body rendered outside any `.ds-frame`, so it had no page gutter (40px desktop, 20px at phone width) while the other tabs still have theirs; the cards would touch the screen edge at 390px. The framed branch now wraps the body in `div.ds-frame > section.ds-frame__main` (padding-top 0 so it sits under the tab row). `TodayTrail` still finds its `li.ds-card` hosts.
- UX-04 (Cases, Reconciliations, Managers) stays open: e4/, a5/ReconPage.tsx and k5/ are outside the area or on the forbidden list. Each needs the same `framed` prop and one word in ActionCentre.tsx.
- Also fixed, in the area: ui/src/v1/e5/k8.test.tsx(18) passed `action_type: null` where the type is `string | undefined`; changed to `undefined`. Backup: .sh-tmp/k8.test.tsx.bak-ux1.
- Nothing outside ui/src/v1/e5/ and ui/src/v1/a5/ActionCentre.tsx was touched.
- Tests after review: `npx vitest run src/v1/e5 src/v1/a5/a5.test.tsx src/v1/a5/k8.test.tsx` 4 files, 13 tests pass. `npx tsc --noEmit`: one error left, src/v1/k5/ManagersInbox.tsx(16), on the forbidden list (TileCard.tsx is already clean).
- 390px checked by the stylesheet, not a browser (no servers in this round): under the phone rule `.ds-frame` gives 20px gutters, the card action row wraps, the dismiss form is unchanged from before.
