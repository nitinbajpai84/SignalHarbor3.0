# V6-design-fixes landing note

Card: WALK.md "Differences for Nitin's approval" 1, 3-6, 8-13 and gaps 4-6, 11-15. Backups: `.sh-tmp/<name>.bak-v6`.

## Built
- **Head of data seat** (`seats.HEAD_OF_DATA`, role `head_of_data` held beside `analyst`; the company admin keeps the seat). Used for the design pack (`a1_routes`), the build plan approve and send back (`b6_plan`, `b6_routes._can`, Action "waiting for my approval") and the verified map (`k3_onto`). Seed: Anita Rao holds it (`tools/seed_evergreen.EXTRA_ROLES`, `seed_10uc` viewers, `seed_v3_demo`). Role added to `route_permissions.yaml` and `roles.ts` (no centres of its own).
- **A1** Build landing: serif title "Build something new, one step at a time", poster with play button and step icons, chapters with icons, four step cards with arrows, running projects with owner and builder; Span talk box moved below.
- **B3** dedicated sign page `/centre/intent/:iid/sign` (Before this, Next, numbered sections, read box, note to the raiser, Sign or Send back with a note). Daniel's Action lists "Intent to sign" (gap 4: nobody was named sponsor before signing). Sign panel wording fixed (gap 5). Sign note stored in the signature.
- **B4** hand-over page `/centre/build/p/:id/handover` (steps, who, when and note, what the builder receives). **B5** builder card: New, due date, assigned by, steps, note, "Ask Mei a question" (posts a project comment), Before this and Next lines.
- **C2** plan approval: choose one, optional note kept with the approval (`approval_note`).
- **D3** approver panel: built by, sent when, "What Lumen checked" (each line from a record, "not checked" when none), note, Approve, Send back. Studio now sits in the step rail. **D4** the step rail shows each step's status (all step pages). **D5** eyebrow, Back to Build, Before this; architecture card reads the plan approval (gap 12).
- **E1** Consume sub-bar (Fund performance, Delivery added) and a right column with Needs you today, reports, comments, Ask Lumen. **F1** Map opens on the whole company (people and agents across the top, projects, data flow, meaning band); a link naming a tab still opens that tab.
- Serif page titles (`--ds-font-serif`, Fraunces added to the fonts link in `ui/index.html`). MCP token form styled (gap 15).
- **Signed fund-to-index mapping** (k10): `GET/POST /api/v1/consume/index-map`; funds compare only with a signed index; the old name rule is only the proposal the head of data signs. Panel under "Each fund against its index".
- Sponsor set on signing (gap 6); delivery preview uses the reporting month row (gap 11); going live sets the project stage live so the map no longer says "Being defined with North" (gap 13); Jobs page lists pipeline runs from run logs (gap 14); Leo Park everywhere (tests).

## How to see it
Sign in as Daniel (sign page via Action), Mei (Build, hand-over), Leo (Action card), Anita (plan approval, Map, Market signals mapping). In a fresh seed the fund-to-index mapping is unsigned: Anita signs it under Market signals.

## Tests
Python: auth, b6, b7, d1, p1, p2, i4, k3, k10, a1, handoff, b9, w3, seed, g1 and more (see summary; run2). UI: vitest `src/v1`, shell, design: 511 passed; 1 failure not mine (`look.test.tsx` lists CSS files and sees `v1/b11/b11.css` from another card). `tsc` clean.

## Mount lines
None needed: all routes sit in existing `routes.tsx` files (i4 `intent/:iid/sign`, b9 `build/p/:projectId/handover`) and existing routers (k10 index-map in `k10_routes`). Integration: nothing in app.py or router.

## Difference for Nitin's approval
- Hand-over is one page with three numbered sections, not two screens.
- Sign page lists the record's sections (8 kinds) rather than the artboard's ten fixed headings.
- "What Lumen checked" has four lines from records; the artboard's "widget reviewed by the data team" has no record, so it is left out.
- Plan approval is now head of data only (analysts no longer approve); company admin keeps it.
- Consume "Delivery" opens the email preview with a Slack link.
- Fund-to-index mapping starts unsigned in the seed (seed_10uc owns only role and names).

## Open items
- Dashboard step (D4) cards and delivery approvals by Raj not changed.
- Map graph nodes are boxes, not circles and hexagons.
- Items 2, 7 and 14 of the differences list untouched.

## Review (11 Oct)
**Checked:** access for the head of data seat (a1 pack approve, b6 plan approve and send back, Action "waiting", k3 verified map, k10 index-map POST: listed in `k10.permissions.yaml` and checked again in `k10_note`). The maker never checks: the plan proposer is refused in `b6_plan.approve`, an unsigned intent never waits for its raiser, and the sponsor is never set from the raiser's own signature. Design copy is present: A1 title, "What Lumen checked", "Needs you today", Fund performance, "Ask <assigner> a question", Fraunces serif. No "Leo Tan" is left.

**Fixed in review:**
- `tools/seed_evergreen.accounts` only gave roles when it created an account. In an environment seeded before V6, Anita had no `head_of_data`, so only Grace could approve plans, packs and the map. The seed now backfills extra roles on existing accounts through the new `AccountStore.add_roles`, which accepts known roles only and never super_admin. Test: `tests/auth/test_auth.py::test_add_roles_backfills_known_roles_only`.
- `tools/seed_v3_demo.dashboard` skipped whenever any dashboard file existed. Going live now drafts Lumen's starter dashboard (H10, `b6_run`), so the seeded `dash-0ad2b1c7` was never written, and 2 tests in `test_seed_10uc` failed. The seed now checks only for its own id.
- Backups: `.sh-tmp/accounts.py.bak-v6`, `seed_evergreen.py.bak-v6r`, `seed_v3_demo.py.bak-v6r`.

**Tests run by the reviewer:**
- Backend: auth + k10_note + p2_assign gave 106 passed. b7_studio + b6 + k3 gave 63 passed. seed_10uc gave 52 passed.
- UI: `tsc` is clean. vitest over a5, b9, k10, k3, i4, b7, d1, shell and look gave 190 passed and 1 failed: the `look.test.tsx` CSS list needs `v1/b11/b11.css`, which belongs to the b11 card.

**Left open:**
- Dashboard approval (`cx_dash.can_approve`) and delivery approval (`d1_delivery.can_approve`) still use the architect seat, which means any analyst. The UI wording says "head of data or the sponsor". This card did not cover it, so it needs a decision.
- E1, B4 and B5 were not compared with the artboards by screenshot, and F1 was not re-shot after the column fix.
