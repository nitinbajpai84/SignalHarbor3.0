# Quality pass: from a working MVP to a product (7 Oct 2026, overnight)

Nitin's bar: production grade. Screens match the design canvas, verified by screenshot against the artboard. Each person sees only what they must act on, what the company shares with everyone, and what makes the agents' context stronger. Agents decide; people act at a few named moments.

## 1. Product principles (the AI product manager's view)

**Three kinds of information, and only these, on any screen**
1. **Act:** something this person must decide, sign, give or fix. It appears on their pulse and nowhere else until done. Agents draft it; the person approves, signs or edits.
2. **Shared (data democratisation):** what the company has aligned on and who owns it: the map, the signed register, the released measures, the market context. Open to everyone in the company, names and links only, figures behind the access list.
3. **Context (the agents' layer):** what the agents learned and remember: the company profile with provenance, the memory per person and per company, the versions on the map. Visible to the person it concerns and the steward; it is never a task.

**When agents decide and when people act**
| Moment | Agent decides | Person acts |
|---|---|---|
| Bring what you have | Nira reads everything, fills the profile, marks guesses | Organiser drops files; confirms or corrects |
| The wall | North drafts cards, groups, suggests | Each person confirms or adds in five minutes; organiser moves the stages |
| Define | Lens proposes shelves, definitions, owners | Committee decides shelves; owners confirm; sponsor signs |
| Moment of truth | Lens profiles, recomputes, drafts the plan | Owners upload a file; sponsor and head of data sign |
| Build | Architect, Builder, Prover draft, build, reconcile | Head of data signs the design; tester signs UAT; sponsor releases |
| Run | Watcher checks, names who must act, drafts the ask | Owner acts on the alert |
| Consume | Feeds, market, what-if are computed | Read; ask; keep a scenario |

**Roles and what they see (A-073)**
| Role | Top bar | Lands on | Never sees |
|---|---|---|---|
| Participant | Pulse, Map | Pulse | Build, Control, other people's walls |
| Owner, approver | Pulse, Consume, Map | Pulse | Build, Control, Intent (except by invite link) |
| Sponsor | Pulse, Intent, Consume, Map | Pulse | Build, Control |
| Analyst (data team) | Pulse, Build, Consume, Map | Pulse | Control |
| Company admin (organiser) | Pulse, Intent, Build, Consume, Map, Control | Pulse | nothing |
| Super admin | Control | Control | company data |
One table (`ui/src/shell/roles.ts` mirrored in `sh_platform/route_permissions.yaml`) drives the bar, the routes and the permissions. An invite link opens the one wall for anyone with a seat, whatever their bar shows.

## 2. The design system in code (package Q0, first)
From the canvas (https://claude.ai/artifact/1yS7Aw8bXxqydH7ZzAcckd): tokens `--ground #0F1B2D`, `--surface #16263D`, `--line #22344D`, `--teal #1F8A8A`, `--teal-bright #5FC2C2`, `--amber #D98E2B`, `--ink #F6F4EE`, `--ink-soft #BFD8D5`, `--ink-muted #8FA3B0`, DM Sans; the light theme maps the same roles. Components in `ui/src/design/`: `TopBar`, `PageFrame` (greeting, date, summary line), `Strip` (label and cards), `ActionCard` (icon, title, detail, due, action word; whole card a link), `SideCard`, `StatPill`, `Chip`, `Pill` (ok, late, failed, draft, signed), `Sparkline`, `LineChart`, `DataTable`, `EmptyState` ("Nothing needs you today"), `PhoneTabBar`, `MapColumns` (the five-column map with hover and click), `Trail` (the five-step provenance), `VersionList`, `CommentThread`, `Signature`, `RoomTile`. Every screen is built only from these.

## 3. Screens, one by one, each along its user journey (packages Q1 to Q14)
For each: build to the artboard, land, screenshot at 1280 and 390 in the real app with the demo company signed in as the right role, UI reviewer compares with the artboard image and lists differences, fix, repeat until it passes. Then the next screen.
| # | Screen | Artboard | Role to sign in as | Journey it serves |
|---|---|---|---|---|
| Q1 | Pulse | Main, Phone-Participant, Desk-Organiser, Desk-Data, Desk-Sponsor | each of five | the front door |
| Q2 | How my organisation connects | Desk-Graph, Phone-Graph | participant | shared: the ontology |
| Q3 | One thing on the map | Desk-Node | owner | shared + context: trail, versions, comments |
| Q4 | Intent home and the three rooms as doors | Intent canvas artboard 1 | organiser | act: the organiser's work |
| Q5 | The wall with stage bar and invite panel | Intent canvas artboards 2, 5 | organiser and participant | act: contribute in five minutes |
| Q6 | Define and the charter | artboard 3 | organiser and sponsor | act: decide and sign |
| Q7 | Baseline and sign-off | derived from artboard 3's panel style | owner and sponsor | act: confirm definitions |
| Q8 | Moment of truth and the data request | artboard 4 | admin, owner by link | act: upload and sign |
| Q9 | Build home, environment, blueprint | Build preview artboard | analyst, admin | act: sign the design |
| Q10 | Pipelines, Prove and release, Ops | Build preview artboard | analyst, tester, sponsor | act: run, test, release, fix |
| Q11 | Consume home, Feeds, measure page | Consume preview artboard | sponsor, owner | shared: the numbers |
| Q12 | Market forces, What-if | Consume preview | sponsor | shared: context and scenarios |
| Q13 | Register, Memory | derived | everyone, each person | shared + context |
| Q14 | Control panel, sign-in | control artboard 8 | super admin, admin | setup |

## 4. Speed and honesty
Pages paint under one second on the demo company. Slow work (graph rebuild, warehouse open) moves off the request path or is cached. Every number traces to a record; "Not available yet" otherwise. No link in the new shell reaches a legacy screen.

## 5. Order of work
Q0 first (one senior builder). Then Q1 to Q14 in parallel across as many builders as the environment allows (20 at once), each with its artboard files, the design system, the role table and the journey. I land, screenshot, review, and return findings to the builder until the screen passes. Full suites run once at the end; the fix round follows.

## 6. Deadline: the Ardmore demo at 08:00 on 7 Oct
Deliverables by 07:30: every screen landed and reviewed; the demo company seeded with six months of history (April to September 2026: walls, a signed charter and baseline, blueprint, monthly pipeline runs with one late month and one failed rule, proofs, UAT, a release, alerts acknowledged, comments, messages, memory); the warehouse carrying nine months of figures (already seeded); a one-page demo script `docs/guides/DEMO-SCRIPT-ARDMORE.md` with the five sign-ins and the clicks in order; servers restarted and signed in once as each account to confirm.
