# ACT1: Action is one page

## What changed
`/centre/action` is now one page (`ui/src/v1/a5/ActionToday.tsx`), built to the approved artboard: greeting with the count of things that need the person, count chips that jump to groups, then Cases to handle, Reconciliations to clear, Statements to chase, Figures to confirm, Waiting for my approval, a folded Done today, and a side panel (Ask Tally, My tickets, Since yesterday). Each line: mono label, headline, one sentence, one primary button plus one secondary. An empty group shows "Nothing to clear."
No backend change; every group uses an existing typed client.

| Group | Source | Primary button (existing action) |
|---|---|---|
| Cases | `GET /cases` (open, not recon breaks) | Take the case (`takeCase`) if new, else Open the case |
| Reconciliations | `GET /recon/runs` (all checks but limits; a breached limit is a case) | Close as timing (case `dismiss`) only when the cause says timing and the server lets this person dismiss; else Open the case |
| Statements to chase | `GET /managers/inbox`, late funds only | Draft a follow-up (`draftFollowup`, shown inline, copy; never sent) |
| Figures to confirm | `GET /extract/queue` + extraction | Confirm (`accept` with no changes); Correct it opens the Review queue |
| Waiting for my approval | `GET /action/landing` waiting_approval (studio dashboards, packs, plans, intents, deliveries) | Review and approve (link to the item) |

## How to test
`cd ui && npx tsc --noEmit && npx vitest run src/v1/a5 src/v1/k5`; open `/centre/action` as an analyst on a seeded env.

## Old vs new audit
- Today tab (Pulse Needs me / Worth a look, Not for me, Viewing as, Where is this from?): kept whole in the folded "Everything Tally flagged" (`PulseFull.tsx`); `/centre/today` unchanged.
- Cases tab: `/centre/action/cases[/:id]` still opens (with "Back to today"); "All cases" link in the group.
- Reconciliations tab (Run now, as-at date): `/centre/action/reconciliations` still opens; "All checks" link.
- Managers tab: `/centre/action/managers` still opens; "All managers" link.
- Tickets: `/centre/tickets[/:id]` unchanged; "All tickets" link; Raise form reused inline.
- Review queue: `/centre/extract/review` unchanged; "Review queue" link.
- Assigned to me (cards, Ask, Mark done), Waiting on others, Before-this line: kept (own group, folded list).
- Shared with you dashboards: now listed under Since yesterday (14-day rule kept).
- Evidence routes unchanged.

## Departures from the design
1. Extra group "Assigned to me" (only when there is one) and folded "Waiting on others" and "Everything Tally flagged": needed so no feature is dropped.
2. Approvals come from the landing endpoint (superset of studio waiting_for_you plus packs/plans/intents), not `listStudio` per project.
3. Done today lists cases closed today plus what this person finished on the page; "closed by Tally" lines are not available from any API.
4. Ask Tally is per case: the box asks about the first reconciliation break, else the first case. There is no page-wide Tally endpoint.
5. Since yesterday shows Pulse "worth a look" headlines and fresh shared dashboards, not a written summary; no API supplies one.
6. Close as timing is not offered when the server refuses dismiss or the cause is not timing; the line then opens the case.
7. Colours use the app's design tokens (the shell already provides the header); the artboard's example names are not used.
