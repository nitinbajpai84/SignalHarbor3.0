# Intent Centre: specification (6 Oct 2026)

Status: proposal for Nitin's review. Decisions it depends on: D-002 (six modules), D-003 (agents), D-013 (anonymous is real), D-031 (reuse first), D-036 (module 3 bands). New decisions it asks for are listed at the end as A-052 to A-058.

Design canvas with the screens: https://claude.ai/artifact/RN9Sh8Fxmmxk99rXTvsxK6 (artboards 1 to 9). Concept note: https://claude.ai/artifact/EdjXPtppu4rpdqxN1Z2EPL.

## 1. What changes and what does not

The product is re-staged as three centres. Each centre has three rooms. The agents, the records they write, the signatures and the security model do not change. The modules keep their folders and routes; the centre is a way of presenting them.

| Centre | Room | Runs on | State |
|---|---|---|---|
| Intent | Think unfiltered | `modules/m1_intent` private rooms and notes | re-staged (this spec) |
| Intent | Define strategically | `m1_intent` board, together, charter; `m2_baseline` definitions, owners, glossary, catalogue | re-staged (this spec) |
| Intent | Moment of truth | `modules/m3_connect` sources, intake, trial, plan, accept | re-staged (this spec) |
| Build | Architect your design | module 4 (not built) | later spec |
| Build | Build the data | module 4 (not built) | later spec |
| Build | Ops manager | module 6 ops part (not built) | later spec |
| Consume | Market forces | module 5 (not built) | later spec |
| Consume | What-if | module 5 (not built) | later spec |
| Consume | Feeds | module 6 feed part (not built) | later spec |

Vocabulary rule (A-052): no game words anywhere on screen. Lanes, cards, shelves, seals, the wall. Not hoops, balls, points, levels, badges. Rationale: `docs/decisions.md` A-052 and the market note in the concept artifact.

## 2. The company profile is the spine

Every room reads `sh_platform.profile.read(plane, viewer)` and writes through `profile.record(...)` with provenance. The profile already holds people, systems, reported figures, samples, interviews, constraints, governance (restricted areas, field rules). Two additions:

- `cards` (new section, A-053): one entry per card on the wall. Fields: `lane` (tracking | missing | watch | levers), `q1..q4` provenance cells (business words; where it bites; tracked today and source; technical definition), `sealed` (bool), `anonymous` (bool), `author` (person id or `anon-*`), `from_interview` (qid, when North drafted it), `cluster` (set in Define), `shelf` (set in Define).
- `governed` (new per measure in `reported_figures`/catalogue, A-054): the six-field governed state in section 5.

## 3. Room 1: Think unfiltered (the wall)

Purpose: everyone puts what they know on the wall in five minutes, with no form.

Inputs from the company: a person's answers to four questions, in conversation with North. A seal tap. An anonymous tap.

The four questions (contract `modules/m1_intent/contracts/wall_questions.yaml`, new):
1. What is it, in business words?
2. Where does it bite, and how hard? (who, how often, what it costs)
3. How do you track it today, if at all? (screen, file, person, source)
4. The most technical definition you can give. ("I don't know" is accepted; Lens fills it later from the files and marks it `guessed`.)

Rules:
- North drafts cards from the person's interview (Q1 to Q6 map to lanes as `modules/m1_intent/contracts/interview_notes.yaml` already does). The person confirms, changes or discards. A confirmed draft counts as a card with `from_interview` set.
- A card may be put on the wall with two of four quarters answered (A-055). The empty quarters show as empty; a quarter North fills from a document is marked `guessed` with the document named.
- The seal tap marks the card restricted. A sealed card shows on the wall as a silhouette ("A sealed card about pay") to anyone not on the restricted area's `may_see` list, including the organiser and the company admin. Lens never reads a sealed card into a draft visible to others.
- Anonymous is per card and real (D-013). The wall shows counts per lane, never names, in the projector view; the normal view shows the author's name only where the author chose it.
- North may add at most three suggestion cards per lane from the pack and from the company's own documents (dashed, "Suggested by North, from <document>"). A suggestion becomes a card only when a person picks it up; untouched suggestions are not counted and are dropped when the wall closes (A-056).
- The wall is open for a fixed window (default five working days, set in Prepare). It freezes at close. The frozen wall is page one of the charter.

Outputs: `cards` in the profile; per-lane counts; the frozen wall (a JSON snapshot in the charter outcome, rendered as the first page of the charter HTML and Markdown).

Screens: canvas artboards 2 (dark) and 5 (light). Phone view: one lane at a time, swipe between lanes, the North panel as a sheet. Projector view: lanes only, counts, no names, no panel.

Counters (A-057): actions and free-text boxes per person, recorded as numbers only (the `m1_intent` lean counters already exist; extend with `cards_confirmed`, `cards_new`, `cards_sealed`).

## 4. Room 2: Define strategically

Purpose: the committee turns the wall into a charter, a glossary and a catalogue in one ninety-minute session.

Before the session (agents, unattended):
- North clusters the cards (existing board grouping), names each cluster, gives it a colour. A cluster carries its card count and the lanes its cards came from.
- Lens proposes a shelf per cluster from card count, vote prediction is not used; the proposal is a suggestion labelled as such.
- Lens drafts, for every measure a cluster maps to: business definition, technical definition (source, fields, calculation, period, currency; `m2_baseline` M2-E1 technical definitions), owner proposals from the RACI and interviews, and the governed state (section 5). It raises the ambiguous terms (existing glossary logic: three meanings of return, and so on) as questions to the named person, at most three per person (A-043).

In the session (people):
- Drag a card to another cluster; drag a cluster to a shelf. Every move is kept with the person and time.
- Vote (existing together stage). The vote rule from LI-M1 stands: ticked when Must plus Should votes beat the rest; organiser breaks ties.
- Owners confirm or correct their measures ("mine" / "not mine, it is X").
- The governance lead settles the ambiguous terms; the decision is recorded as a known risk where an ambiguity is accepted.
- The sponsor signs the charter (one signature by default, LI-M1).

Shelves: Must, Should, Good to have (renamed from Could), Future (new). The Future shelf keeps a cluster with its reason and a review date (default one quarter). Nothing is deleted.

Rule: a cluster may sit on Must or Should only when every measure it maps to has a complete governed state (section 5). The screen shows a dashed ring on a cluster that is not yet governed and names what is missing.

Outputs:
- Charter (existing outcome): problems with priority and "so that", measures per problem, the frozen wall as page one, one signature.
- Business glossary (existing `m2_baseline` glossary): terms, owners, accepted ambiguities as known risks.
- Data catalogue (existing `m2_baseline` catalogue with technical definitions): per measure, sources, fields, calculation, period, currency, personal data class, who may see, owners.
- Governed state per measure.

Screen: canvas artboard 3.

## 5. Governed state (A-054)

Six fields per measure, each a provenance cell, drafted by Lens, confirmed by a named person. Complete means all six confirmed.

| Field | Drafted from | Confirmed by |
|---|---|---|
| Owners (business, data, process) | RACI, systems list, interviews | each named owner |
| Classification (open, personal, sensitive, restricted) | classification policy, field rules | governance lead |
| Who may see | access list, policy, restricted areas | governance lead and owner |
| Resolving team and target week | the team behind most cards; deadlines file | sponsor, at shelving |
| Affected downstream | pack dependencies; "who feels this" taps | owner |
| Review date | default one quarter | nobody; a default |

Downstream: module 3 masks restricted measures per viewer (already built); module 4 turns classification and who-may-see into access rules; feeds respect who-may-see. Governance is set once, in Define, and enforced everywhere without asking again.

Governance measures already in the pack: K19 (definitions with a named owner), K08 (policy exceptions). The Define screen shows owned, classified, who-may-see confirmed, sealed, as percentages that rise during the session.

## 6. Room 3: Moment of truth

Purpose: the definitions meet the files. Nothing new is asked of the company unless a gap names a missing file.

Runs on module 3 as built (LI-M3): samples and reported figures from the profile, trial per measure against the reported figure, scan per source, source map (impact against readiness, four zones), phased plan (weeks 0-3, 3-8, 8+), accept risks, two signatures (sponsor, then head of data). Restricted measures are scored only for the people who may see them, and risks about them are decided by those people.

Re-staging: a scoreboard header (match, gap, not yet; the restricted count as a separate line), the source map beside it, the trial table with the reason and the fix per gap, the plan bands, the signing panel. All existing data; no new route.

Output: the signed gap report (plan outcome). Signing it opens the Build centre.

Screen: canvas artboard 4.

## 7. Centre home and the context layer

Centre home (artboard 1): three rooms as doors lit in order; the governed-state panel; Nira's "what is waiting" list; the four counters (files read, interviews, Lens can draft, your time so far).

Bring what you have (artboard 7) is the context layer, unchanged in function (LI-PROFILE, LI-MULTI, LI-LINK), re-skinned. It carries a "where this lives" panel on the screen itself (files stay in this company's space; who can open originals; which agent reads; what may leave; sealed files never read).

## 8. Control panel (artboard 8) and security (artboard 9)

The control plane today is `data/_control/companies.json`, `entitlements.json`, `sh_platform/catalogue.yaml`, `packs/`, and `tools/seed.py`. The control panel screen is a view over those files plus the per-company egress log. New routes are needed for: centre switches (a centre is a named group of modules in `catalogue.yaml`), model provider per company, the egress toggles (internet, connectors, cloud push), and reading the egress log. Super admin cannot open any company's files; the company admin cannot open anonymous notes.

Security is as built: three planes, one exit, four guards (`.claude/rules/egress.md`). Not built, said plainly on the screen: SSO and SCIM, encryption at rest beyond the OS, a retention clock, a packaged install for the customer's environment, independent penetration testing.

## 9. Inputs and outputs per person, with targets

| Who | Does | Time | Target |
|---|---|---|---|
| Super admin | creates the company, switches the Intent centre on, picks the pack | 10 min | once |
| Company admin | logo, accounts, links people to accounts | 10 min | once |
| Organiser | drops the files into nine tiles | 10 min (measured) | |
| Every person | one interview | 5 to 15 min (measured, median 11) | |
| Every person | confirms or adds cards on the wall | 5 min | one card in the first five minutes |
| Committee of 8 | Define session | 90 min | about 20 decisions |
| Sponsor, head of data | review and sign the gap report | 30 min | |

Totals: about 10 working days elapsed; organiser about 2.5 hours; each other person 25 to 60 minutes; about 30 human decisions.

Measures of the centre itself (LI-OUTCOMES): days from first card to signed gap report; human minutes per person; definitions confirmed unchanged; match rate at the moment of truth; cards per person in the first five minutes.

## 10. Reuse: what exists, what is new

Exists and is used as is:
- Profile store, reader, per-viewer filtering, provenance cells, restricted areas, field rules (`sh_platform/profile`).
- Context shelves and visibility (`sh_platform/context_docs`), Bring what you have (`ui/src/pages/BringPage.tsx`), people-to-account links.
- Interview engine Q1 to Q14 with follow-ups and private/anonymous notes (`sh_platform/interview`).
- Module 1: private rooms, North conversation, four note kinds, note cards from the conversation (`from_conversation`), anonymous per note, board grouping by North, manual regrouping, together vote and tick, charter with "so that", one or two signatures, approver by link, counters, stage timers.
- Module 2: Lens drafts, technical definitions (M2-E1), owners, governance per field (personal data, who may see), glossary with ambiguities, catalogue, sign-off gate, hand-off with `reported_figures`.
- Module 3: everything (LI-M3).
- Egress gateway, four guards, logs; default-deny route permissions; module gate.

New (this spec):
- Wall screen (dark, light, phone, projector) over the private-room and notes routes; lane view of the four kinds; quarter-filled card edge; seal tap; suggestion cards from documents with pick-up.
- `wall_questions.yaml` contract; `cards` section in the profile; `cards_*` counters; wall open/close window and the frozen wall in the charter.
- Define screen: colours per cluster, shelves with drag, the Future shelf with review date, the governed-state ring and panel, Lens's definition panel opened from a cluster.
- Governed state: six fields, Lens drafting from policy, RACI and deadlines; the Must/Should rule.
- Moment of truth: scoreboard header over the existing trial; nothing else.
- Centre home; centre switches in `catalogue.yaml`; control panel routes and screen; egress toggles per company.
- Design tokens (dark default, light) in the React shell; Manrope and a mono face.
- Fixes assumed by the screens: strategy prose read by Lens (defect D2 of the live run), restricted areas derived from the classification policy (D3), group read-state reason per group not per last file (D1), data-quality rules from the scan carried into the catalogue.

## 11. Decisions requested

- A-052 No game vocabulary on screen; the mechanics stay.
- A-053 `cards` section in the company profile, written only by the wall routes.
- A-054 Governed state: six fields; Must and Should need all six.
- A-055 A card may be placed with two of four quarters; missing quarters show empty, agent-filled quarters are marked guessed.
- A-056 North's suggestion cards: at most three per lane, from the pack and the company's own documents, labelled, counted only when picked up.
- A-057 Counters record numbers only.
- A-058 Shelves: Must, Should, Good to have, Future; Future keeps the reason and a review date; nothing is deleted.
