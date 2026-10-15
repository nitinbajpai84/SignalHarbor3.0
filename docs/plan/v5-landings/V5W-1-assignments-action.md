# V5W-1 Assignments and the Action landing

The builder's landing note is `V5W-1.md`. It covers what was built, how to see it, the tests and the mount lines (none needed).

## Review (11 Oct 2026, reasoning reviewer)

Verdict: **pass after fixes**. Two defects were fixed in review.

**What was checked**
- Designs (Main, A5, B4, B5): the owner stays the owner. Steps and a person are chosen with a due date and a note, and hand over sends the chosen steps. Action greets the person, then shows Assigned to me, Waiting for my approval, Waiting on others, Needs me and Worth a look. The plain copy matches.
- Access: every route is declared in `p2.permissions.yaml`, and `test_routes_are_declared` keeps the routes and the file equal. Assigning and handing over need full access plus `can_manage`, meaning the owner or a company admin. Only the assignee can mark a step done. Only the assigner or an admin can withdraw one. Reading needs read access to the project.
- Maker and checker: Waiting for my approval reuses `cx_dash.can_approve`, which never offers the maker or submitter. It leaves out the plan's proposer. The intent rule follows the sign flow in i4, where the sponsor or raiser signs.
- Egress: nothing leaves the machine and no model is called. Cards are built from event rows only.
- Nothing dropped: compared with `.sh-tmp/ActionCentre.tsx.bak-v5`, Action still has Shared with you, Today (Needs me / Worth a look, Take case, Not for me, Where is this from?) and every tab. Routes are unchanged apart from the new `action/assign/:pid`.

**Defects fixed**
1. *Today cards never closed.* Pulse rows are stored, so a card stayed pending after its assignment was done, withdrawn or given to someone else. It also used up one of the person's 7 card places. Fix: `p2_assign._close_cards` runs after every assign, hand over, done and withdraw. It dismisses pending `assign:` and `assigned:` cards whose assignment is no longer open (outcome `closed`). It also clears the five-minute pulse refresh so the new assignee sees their card on the next load. Tests added: `test_withdraw_by_assigner_only` now checks the cards are gone, and `test_reassign_closes_the_earlier_card` is new.
2. *The same assignment showed twice on Action.* It appeared in Assigned to me and again as a Today card. B5 shows it once. Fix: `TodayPage` takes an optional `skipKinds` prop, and the Action landing passes `["assignment"]`. `PulseItem` now carries `kind`. The plain Today page is unchanged and still shows assignment cards.

**Tests after review** (exact commands)
- `pytest tests/v1/test_p2_assign.py -q`: 9 passed.
- `npx vitest run src/v1/a5 src/v1/e5`: 36 passed (8 files).
- `npx tsc --noEmit`: no errors in `a5`, `e5` or `p2`. The only errors are elsewhere, from the b9 `Steps.ts`/`steps.ts` casing clash in package 2.

**Backups:** `.sh-tmp/p2_assign.py.bak-v5`, `TodayPage.tsx.bak-v5`, `e5-api.ts.bak-v5`, `ActionCentre.tsx.bak-v5-review`.

**Open items (not fixed)**
- Waiting for my approval has no deliveries or review items yet (`_waiting` needs a clause once they have a pending state).
- Withdrawing a step does not take the person off the team. The project's single `builder` field shows whoever was assigned last.
- If a head of data is assigned Architecture, they could both draft and approve the plan, unless `b6_plan` refuses the proposer. Check this when C2 lands.
- Due dates have no reminders. The past-date check uses the UTC date.
- Not checked in a browser. Screenshot it against B5 and A5 in the integration step.
