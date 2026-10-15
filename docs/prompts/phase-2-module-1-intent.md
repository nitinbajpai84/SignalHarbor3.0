# Prompt: phase 2, module 1 (Intent Centre)

Paste the short pointer from the chat into a the build session opened in `<2.0 repo>`. This file is the whole brief.

---

You are the orchestrator for **module 1, the Intent Centre**, in this repo. The platform kernel (phase 1) is landed. Work autonomously until module 1 is done. Do not ask me questions; decide, record, and continue.

## Read first (in this order)
1. `CLAUDE.md`, `modules/m1_intent/CLAUDE.md`, and the `.claude/rules/` chapters your task needs
2. `docs/decisions.md`: D-001 to D-027 and all autonomous decisions A-001 onward. They override the spec where they differ. Most relevant: D-004 (up to ten people, solo allowed), D-006/D-007 (egress), D-013 to D-022 (anonymous, approver, privacy, voting, graph), D-026 (a started session links to its outcome both ways), D-027 (legacy look)
3. `docs/specs/MODULES-1-2-FEATURE-SPEC.md`: sections 1 to 8, then every feature **M1-01 to M1-31** and the cross-cutting X-xx features that module 1 uses
4. `docs/specs/Module 1 Intent Centre workflow and screens.pptx`: the screens and flow
5. `docs/RUNNING.md`, `docs/reuse-map.md`, `docs/design/legacy-css.md`, `docs/ledger/_common.md` and `docs/ledger/autonomous.md`
6. The kernel interfaces you build on, found with `graft skeleton`: `sh_platform/manifest.py`, `entitlements.py`, `modulegate.py`, `plane.py`, `process_record.py`, `auth/`, `egress/`, `agents/`, `packs.py`

## Reuse first (my priority is to reuse what already exists)
The earlier product at `<earlier repo>` (commit 3a798cc5, read-only; never write or merge) already implements most of module 1's behaviour. **Before writing any new code for a feature, search that repo with `graft ask "<question>" --source` and `graft callers`. Copy or reshape what exists. Write new code only where nothing exists, and say why in the brief.** Port its tests as behaviour tests first, then adapt them.

| Need | Old code to reuse | Treatment |
|---|---|---|
| Session engine: phases, seats, timer, notes in rooms, solo run, join binding to the signed-in account, no facilitator rights for a token-only person | `emitters/intent_sessions.py` (959 lines), `webapp/backend/routers/intent_sessions.py` (472), tests `tests/test_intent_sessions.py` | Reshape: phases change to the new flow (prepare, room, lobby, briefing, private rooms, board only after rooms close, back in the room, sign-off) |
| Live updates (server-sent events) | `webapp/backend/routers/live.py` (83), `tests/test_live_updates.py`, `js/live.js` | Copy |
| Private conversation with North, interview turns saved | `webapp/backend/routers/intent_interview.py` (400), `emitters/agent_sessions.py`, `emitters/agent_memory.py`, North's instructions in `contracts/` and `templates/insurance/1/skills/`, `tests/test_intent_interview.py` | Reshape onto the kernel agent runtime (`sh_platform/agents`); North's wording becomes industry-neutral and takes its industry practice from the pack |
| Clustering notes, the wall, agree and discuss | `run_gather`, wall and agree code in `emitters/intent_sessions.py` | Reshape; add voting (D-020) |
| Problem library | `webapp/backend/routers/problem_library.py`, `templates/*/1/problems.yaml` | Already in the new packs; use the pack loader |
| Speech input | `emitters/voice.py` (123), `js/voice.js`, `tests/test_documents_voice.py` | Copy; spoken replies are new |
| Charter, sign-off, gates | `webapp/backend/routers/gates.py`, charter code, `tests/test_gates.py`, `emitters/intent.py`, `emitters/intent_change.py` | Reshape: two sponsors become the approver flow (D-014) |
| Team and room dispatch | `emitters/team_room.py`, `emitters/room_dispatch.py`, `tests/test_team_room.py` | Reshape only if Nira's coordination needs it |
| Screens: session, alignment room, charter, studio | `js/screens/intent-session.js`, `alignment-room.js`, `charter-doc.js`, `intent-center.js`, `intent-charter.js`, `intent-studio.js` | **Rebuild in React**, using these as the behaviour reference and the legacy stylesheets (`ui/src/styles/legacy/`, including `screens-v3-intent.css`, `screens-team-rooms.css`) |

New in module 1 (nothing to reuse): briefing and video, anonymous per note, Mentimeter-style voting, charter templates and versions, business graph, retention setting, spoken replies, hand-off record to module 2, and the approver role.

Lessons from the earlier build to carry into the code (all are bugs we fixed before): join must bind the signed-in account so one person can run a session alone; a token-only participant never gets facilitator rights; notes are accepted only while the private rooms are open; session tests write only to temporary folders; a re-draft never overwrites signed content or a human edit; never show another industry's content.

## Packages (vertical slices: API, agent, screens, tests together)
Write each package's brief to `docs/ledger/<ID>/brief.md`, listing the spec feature ids, OWNS paths, acceptance criteria, the old code it reuses, and the tests. Add it to `docs/ledger/active.json`.

| ID | Features | Notes |
|---|---|---|
| M1-P01 Module shell and session record | M1-01 prepare, M1-02 seats and time, M1-29 storage skeleton, M1-31 solo and empty company | `manifest.yaml`, routes, roles from the kernel (A-005), the state machine, process record created in progress (D-026) |
| M1-P02 Room, join link, lobby | M1-03, M1-04, M1-15 rejoin and late join | Link and code, no account for participants; live updates |
| M1-P03 Briefing and timer | M1-05, M1-06, M1-07, M1-14 | Nira coordinates; the video is a replaceable setting with a placeholder, no real asset needed |
| M1-P04 Private room | M1-08, M1-10, M1-13, M1-16 | One North per participant; industry practice from the pack, labelled as a suggestion; notes only while rooms are open |
| M1-P05 Notes and privacy | M1-11 the note form, M1-12 anonymous per note, rest of M1-29 | D-013, D-015, D-016 enforced and tested; retention is a contract setting (D-017) |
| M1-P06 Voice | M1-09 | Speech in, spoken replies, mute, no audio stored (D-018); works typing-only if no provider key |
| M1-P07 Board and clustering | M1-17, M1-18, M1-19 | Board appears only when the rooms close |
| M1-P08 Back in the room | M1-20, M1-21, M1-22, M1-23 | **Voting like Mentimeter, no restrictions (D-020)**; pause and resume |
| M1-P09 Charter and sign-off | M1-24, M1-25, M1-26, M1-27, M1-28 | Templates, versions, approver role, simple business-graph picture at sign-off (D-022) |
| M1-P10 Hand-off | M1-30 | Writes the outcome record that module 2 reads; two-way link to the session (D-026) |
| M1-P11 Smoke and demo | all | End-to-end across two industries, an empty company, a solo run and a ten-person room (simulated participants); privacy, entitlement and isolation tests; seeded demo data marked illustrative |

Order: P01 first; then P02 and P04 can run in parallel with P03 once P01 lands; P05 after P04; P06 after P04; P07 after P05; P08 after P07; P09 after P08; P10 after P09; P11 last. Split a package if it is too big; never merge two.

## How to work
- Builder in its own worktree for each package (Agent tool, `isolation: "worktree"`), failing tests first, then code.
- Independent review for every package: `sh-reviewer`; plus `sh-security-reviewer` for P01, P02, P05, P06, P09, P10 (access, privacy, anonymity, sign-off, isolation); plus `sh-ui-reviewer` for every package with screens. **Author is never the reviewer.** Give reviewers the code and brief, not the builder's conclusions.
- Fix rounds until PASS, then land with `python tools/sh_commit.py <ID>` (`/ship`). Local commits only.
- A reviewer's finding on the same cause rejected twice: follow decision A-003's pattern (reduce to the simplest sound design, record it, move on).
- Use graft for context. Cheapest capable model for mechanical work; strongest for reviewers.
- Servers only on ports 8200-8299; stop what you start. Tests write only to temporary folders.

## Guardrails (non-negotiable)
1. Never push. No remote, no deploy (D-024).
2. Real client data never leaves the machine. Synthetic data only, marked illustrative. Participants' conversations go only through the egress gateway, with names tokenised (D-007).
3. Never write `.env` or print a secret. If the speech or model provider key is missing, build behind the provider interface with a stub and degrade gracefully; list it in the final report.
4. Do not edit `.claude/hooks/`, `.claude/settings.json` or permission settings. Never modify the old repo.
5. Decisions and the spec are the only source of truth. Never invent a business rule, role, field or threshold.
6. No destructive command outside temporary folders. Use WIP commits to set work aside.
7. The industry is a parameter; no insurance or other industry wording in code. Content comes from the company's pack.
8. Signed content is read-only; a draft never overwrites a human edit.
9. Anonymous means anonymous: no screen, API, export, log or admin tool reveals the author of an anonymous note (D-013, D-016). Test it from every direction.
10. Switched-off module: no tile, refused route, no agent, no tools.
11. Do not start module 2 work.

## Autonomous decisions: do not stop to ask
When something is unclear: look in `docs/decisions.md`, then the spec, then the old repo's behaviour. If still open, choose the **safest, simplest option** that keeps data local and does not close a door, and record it in `docs/decisions.md` under "Autonomous decisions" as `A-nnn` (question, choice, why, how to reverse). Carry on. I review them at the end.

**Stop and tell me only if** (a) you need an account or credential only I can create and nothing can be stubbed, (b) an action needs my approval under guardrail 6, (c) two of my decisions contradict, (d) you find real client data in the repo, or (e) the same package fails security review twice for the same cause and A-003's pattern does not resolve it. Otherwise never stop, and never ask "shall I proceed".

## Definition of done
- [ ] M1-P01 to M1-P11 landed through `tools/sh_commit.py`, one local commit and one `sh/<ID>` tag each; reports and PASS reviews in `docs/ledger/<ID>/`; builder and reviewer ids differ in `packages.json`
- [ ] Every spec feature M1-01 to M1-31 is either built and tested or listed in the final report as not built with the reason; the old-code reuse is recorded per package (copied, reshaped or new)
- [ ] All backend and UI tests pass with real counts; the earlier product's ported behaviour tests pass
- [ ] `python tools/doctor.py` prints Ready; `/smoke` passes including module 1 for two industries, an empty company, a solo run and a ten-person simulated room
- [ ] The full journey works in a browser: prepare, invite by link, lobby, briefing, private rooms with North (typed, and spoken if a provider key exists), board, clusters, voting, charter, send to approver, sign, hand-off. Screenshots for each stage in both themes
- [ ] Privacy tests prove: an anonymous note's author is not revealed anywhere; a private transcript is readable only by its author and, for non-anonymous authors, an admin; another company's data is unreachable; a user without the role is refused
- [ ] Every started session links to its outcome and back (D-026): a paused session reopens where it stopped; an outcome opens its session
- [ ] A solo run completes alone; an empty company shows honest empty states
- [ ] Egress: no raw name leaves; internet stays off by default (D-006)
- [ ] The new screens use the legacy look (D-027); copy follows `.claude/rules/ui-copy.md`; no technical words on screen
- [ ] `docs/reuse-map.md` is updated with what module 1 actually copied, reshaped or created; `docs/decisions.md` has the autonomous decisions
- [ ] Nothing pushed; `git log` shows the package commits

## Final report (one message, plain words)
What landed per package with real test counts; a table of M1-01 to M1-31 with built, partly built or not built; how much was reused from the earlier product against new; how to run and try it, with the seeded logins by name only; screenshots; the autonomous decisions with your reasoning; what is stubbed and what I must supply (for example a speech provider key, a briefing video); and what module 2 needs from me. Nothing before this report unless a stop condition occurs.
