# Where the product stands (7 October 2026, 17:40)

One page for Nitin. What is built, what was tested, what is open, and what happens next. Written by the orchestrating session; the other session (f26b4197) handed over at 16:50 and is no longer working on the repo.

## 1. Servers

| Port | What it is | Use it for |
|---|---|---|
| 8300 | Your test copy. Backend with no watcher, screens built at 17:35 with every finished fix | Your manual testing. Nothing refreshes it unless you say so |
| 8200 | Working copy under one watcher; restarts itself 45 s after a Python edit | Agents and automated checks |
| 8201 | Vite dev screens | Builders only |

Sign-ins: `data/_control/seed_credentials.txt` (never printed anywhere). Company: Ardmore (synthetic family office).

## 2. What is built

Built and checked live by a feature tester means a tester signed in as the named people, walked the screen at 1280 and 390 and wrote a VERIFIED report. Built and unit-tested means the code and its tests exist but nobody walked it live yet.

| Area | Spec | State |
|---|---|---|
| Intent record, states, visibility tiers, areas, people, invitations, time box and clock, North panel, events, search, phone views, empty states, counters, links and chain, backlog | 01 to 21 | Built, checked live |
| Initiative: six start questions, wall with private rooms and sealed cards, North's suggestions, Define with clusters and shelves, process map, data sources, glossary, catalogue, governed state, charter and signature, build-ready check, hand to Build, who does what | 22 to 34 | Built, checked live end to end (journey 50 passes as an automated test) |
| Brainstorm: start, pre-thinking, live session, grouping through the agent runtime, converge, outcome, what next | 35 to 37 | Built, checked live |
| Weekly check-in: set-up, two-minute entry on the phone, review and fates | 38 to 40 | Built, checked live |
| Problem: start from an alert or item, triage, owner, cause, fix, affected confirm, bigger than a fix | 41, 42 | Built, checked live (both branches) |
| Decision: options, adviser notes, decider, decide later, no decision, admin cancel | 43 | Built, checked live; adviser note box and option button fixed today (17:20), unit-tested only |
| Lens in Define, Nira's Pulse lines, agent memory, affected and observer view, admin views, pack suggestions | 44 to 49 | Built, checked live |
| Knowledge map with lineage, scan moments, deleted intents leaving the map | 55 | Built, checked live |
| Data-backed opportunities | 56 | Built, checked live |
| Opportunity radar: four business views, hypothesis record, scheduled scan, set-aside list, pick up and think it through, pre-filled starts, charter success measures from the hypothesis | 57 | Built; graded 8 of 8 against the planted answer key; radar screens checked live; pick-up pre-fill checked live |
| Proving: weekly uplift report, verdicts, review, receipts | 58 | Built; verdicts on the four seeded initiatives come out working, working, partly, too early; panel checked live as Janet and Daniel; confirm and review buttons reported dead by one tester (open) |
| Build chain: architecture record in three views, change notes, five gates, head of department | 59 | Built; walked once from hand-off to live with one stand-in tester; polish items open |
| Consume by business view, context cards, what-if into an opportunity | 60 | Built, checked live as Daniel, Katie, Harvey |
| Input ledger and MOAT page (the moat: who supplies each input) | plan | 1,522 rows: automatic 516, manual 507, derived 276, confirm 223; 91 rows still "missing in build" |
| Demo data: Ardmore, 13 monthly periods, 98 daily days, 8 planted truths, 48 documents, proof document | plan | Loaded on the plane; `docs/product/HYPOTHESIS-PROOF.md` shows the queries and result rows |

Not built: the "I feel this" tap on radar cards; the business-view inform line on Pulse; context card "why" from a change note; draft diagrams before approval in the Build chain; nudges after three working days in the chain.

## 3. What was tested

- Feature testers: every spec file above had a tester card; the hand-over lists 17 VERIFIED cards and the re-tests after fixes.
- Department round: 56 personas launched at 16:45; 50 wrote reports (`.sh-tmp/ic/reports/T-P*-report.md`). Two reached their goal and would use it (the super admin, the CEO as observer). The rest were blocked, nearly all by the same five causes (section 4). The round ran all 56 at once, which took the backend down twice and made pages slow; that is a test set-up fault, not a product one.
- Not tested: the specialist passes (customer critic, security prober, numbers, copy, phone, speed) did not run this afternoon. Full test suites were last run green at 15:00 by the other session (vitest 1202 passed, pytest intents 654 passed); not re-run after the afternoon's changes. One stale test is known (`test_b09` expects the map moment once; closing now records it at closing start and at close).

## 4. What the department round found, and what is done about it

| Cause | People hit | State at 17:40 |
|---|---|---|
| Home and Pulse said nothing waits while an invitation was open | 14 | Fixed, deployed on 8300 |
| Daily page not found at `/pulse` | 20 | Fixed (redirect), deployed |
| Advisers had no note box or option button on a Decision; options read "Added by undefined" | 8 | Fixed, deployed |
| Two or three different deadlines on one record | 12 | Fixed, deployed (the Decision screen's own countdown still computes separately: open) |
| Closed intents still offered join, notes, a rating link with no form; "you declined" shown to people who accepted | 9 | Fixed, deployed (fixer was stopped while writing its last tests; the code compiles and the screen tests pass) |
| Converge 500, review page dead end, wall "could not find that" for an adviser | 6 | Fixed, deployed |
| Radar wording (doubled "Not available yet", placeholder titles, "Rejected" heading, footer count) | 1 | Fixed, deployed |
| Seeded walls never opened, so participants accept and have nothing to do | 11 | NOT fixed: it changes seeded records; waiting for your yes |
| A participant can read colleagues' named check-in items on the week's record view | 1 | NOT fixed: privacy defect, first in the next round |
| Reporter of a Problem cannot add evidence; week shows closed while open; analyst account shows "Marcus Todd"; note to organiser fails with a wrong message; affected people get no impact figures; new-problem page saves a draft on open | several | NOT fixed: next round |

## 5. Decisions waiting for you

1. Open the seeded walls on the month-end close and quarterly report initiatives through the organiser's own route (changes seeded data).
2. Spec 59 rulings taken as defaults: head of department as a seventh charter role; only that person signs the blueprint; diagrams drawn in the product as SVG, no renderer bundled. Overturn any you disagree with (`.sh-tmp/ic/RULINGS-CYCLE.md`).
3. Bring back the earlier architecture and data-engineering agents (Span, Flow) by name, or keep Architect and Builder.
4. R15: only the organiser hands over to Build.

## 6. Next steps and estimated times

| Step | Estimate |
|---|---|
| Neera Family Office: a new company of ten people, the 13 months of data and the 48 documents loaded, no intents, plus a step-by-step manual test guide with the click count per feature | about 2 hours |
| Next fix round (section 4, "NOT fixed" rows), simple checks only, then one refresh of 8300 when you say | about 2 hours, in parallel |
| Architecture diagrams (Archify) updated for the return cycle and the four new modules | 30 minutes, in parallel |
| Full test suites and the security pass | 1 hour, after the fixes |
| Commit through the private index, no push, no attribution | 15 minutes, when you say |
