# Intent Centre: build plan and model routing (6 Oct 2026)

Spec: `docs/specs/INTENT-CENTRE-SPEC.md`. Working method: one builder per package, an independent reviewer, at most one fix round (a leak gets more), landed through `tools/sh_commit.py`. Graft first for every builder and reviewer (`graft ask`, `graft skeleton`, `graft callers --depth all` before any multi-file change).

## 1. Who does what

| Role | Model | Why |
|---|---|---|
| Orchestrator (this session) | Fable 5.1 or Opus | reads the whole spec, writes briefs, merges, decides what the router may not |
| Reviewer, security reviewer | Opus for gate packages (egress, auth, restricted masking, signatures); Sonnet otherwise | a leak costs more than tokens |
| Builder | Sonnet or Haiku, chosen per subtask by the router | most subtasks are small and well specified |
| Router | Jev (TypeSafe System One) behind `tools/route_task.py` | a typed snap judgment per subtask, under code rules |

Jev never writes code and never talks to a builder. It answers typed questions about a subtask card and the orchestrator launches the agent with the model the answer names.

## 2. How the router works

Input: a subtask card, a small JSON object the orchestrator writes from the brief plus two facts graft gives: how many files the change touches (`graft callers <symbol> --depth all`) and whether any touched path is on the sensitive list.

```json
{"id": "IC-03", "title": "Lane view of the four note kinds over the existing room notes route",
 "kind": "ui", "new_contract": false, "new_route": false, "files_touched": 3, "blast_radius_files": 4,
 "touches_sensitive_path": false, "has_failing_test_first": true, "spec_section": "3",
 "acceptance": ["four lanes with counts", "card edge shows quarters answered", "no names in projector view"]}
```

Code rules first (they decide; Jev may only make them stricter):
- Any path under `sh_platform/auth`, `sh_platform/egress`, `sh_platform/profile/view.py`, `route_permissions.yaml`, signing or masking code → builder Sonnet, reviewer Opus security. Never Haiku.
- A new contract or a new route → at least Sonnet.
- `blast_radius_files > 8` → Sonnet, and the brief must name every file.

Jev questions, one request per card (all in one `system_one` call):
- `tier` (Choice): `haiku_fits` (one file, a copy or rename, a test rewording, a screen with no new state), `sonnet_fits` (new component or route, several files, a contract to read), `needs_reasoning_model` (ambiguous spec, a design choice the brief leaves open), with `other`.
- `spec_is_complete` (Noul): "Does `card.acceptance` state every behaviour the title implies, so a builder needs no further decision?" Below 0.6 the card goes back to the orchestrator, whatever the tier.
- `risk_if_wrong` (Score, 4 levels): a wrong build is noticed in review | breaks a screen for one role | shows one person's data to another | changes a signed record. Level 2 or 3 forces Opus review.
- `review_needed` (Choice): `sonnet_reviewer`, `opus_reviewer`, `security_reviewer`.

Bands: act on `tier.choice` when `tier.confidence >= 0.6`; at 0.35 to 0.6 pick the higher tier; below 0.35 the orchestrator decides. All thresholds in one constants block in `tools/route_task.py`.

Honesty about Jev here: the TypeSafe field notes say a free-form "prompt router" was underwhelming. This is not that. The card has eight explicit features, the code rules carry the safety decisions, and Jev decides only the tier and the review level. If the first twenty routings show Jev agreeing with the orchestrator less than 80% of the time, the router is turned off and the table in section 1 is used by hand.

Logging: every routing is appended to `docs/ledger/routing.jsonl` as `{id, tier, confidence, risk, review, model_used, agreed_with_orchestrator}`; no card text. The agreement rate is the measure of the router.

## 3. Packages and subtasks

Each line is one subtask card. The last columns are the orchestrator's expectation of the router's answer, to be compared with what Jev says.

### IC-0 Fixes the screens assume (first)
| Id | Subtask | Owns | Expect |
|---|---|---|---|
| IC-0a | Group read-state reason per group, not per last file (D1) | `sh_platform/profile/reader.py` readiness | Haiku |
| IC-0b | Lens reads strategy prose: people, systems, pains, future signals from `.md` documents into the profile with provenance (D2) | `sh_platform/profile/reader.py`, a prompt contract | Sonnet |
| IC-0c | Restricted areas derived from the classification policy (D3): "pay", "HR", "compensation" and the policy's own class names become `governance.restricted_areas` | `sh_platform/profile/reader.py`, `view.py` test | Sonnet, Opus security review |
| IC-0d | Data-quality facts from the scan (empty cells, missing periods) recorded on the catalogue entry as rules | `modules/m3_connect/domain/profile.py`, `m2_baseline` catalogue | Sonnet |

### IC-1 Design tokens and shell
| IC-1a | Tokens: dark default, light; Manrope and mono; `data-theme` toggle persisted per viewer | `ui/src/styles`, shell | Haiku |
| IC-1b | Centre home page: three doors, governed panel, Nira list, four counters, reading existing routes only | `ui/src/pages/CentrePage.tsx` | Sonnet |
| IC-1c | Centres in `catalogue.yaml` as named module groups; tile page shows centres | `sh_platform/catalogue.yaml`, `entitlements.py`, `HomePage.tsx` | Sonnet |

### IC-2 The wall
| IC-2a | `wall_questions.yaml` contract and the four-question flow in North's room (reuse the interview engine's prefill) | `modules/m1_intent/contracts`, `agent/north*` | Sonnet |
| IC-2b | `cards` section in the profile, written by the notes routes; `from_interview`, `sealed`, `anonymous`, `lane` | `sh_platform/profile/store.py`, `m1_intent/api/notes.py` | Sonnet, Opus security review |
| IC-2c | Wall screen: four lanes, counts, card edge quarters, sealed silhouette, dark and light | `ui/src/modules/m1_intent/wall/` | Sonnet |
| IC-2d | Seal tap and anonymous tap in the North panel; sealed cards filtered per viewer through `profile.read` | `m1_intent/api/notes.py`, `view.py` test | Sonnet, Opus security review |
| IC-2e | Suggestion cards from pack and documents, at most three per lane, pick-up turns into a card | `agent/north*`, wall screen | Sonnet |
| IC-2f | Wall window: open and close, freeze, snapshot into the charter outcome as page one | `m1_intent/domain/stages.py`, charter export | Sonnet |
| IC-2g | Projector view (counts only) and phone view (one lane, swipe) | wall screen | Haiku |
| IC-2h | Counters `cards_confirmed`, `cards_new`, `cards_sealed` | `m1_intent` lean counters | Haiku |

### IC-3 Define
| IC-3a | Colour per cluster, cluster name and lanes, from the existing board grouping | `m1_intent/api/board.py`, screen | Haiku |
| IC-3b | Shelves: Must, Should, Good to have, Future; Future keeps reason and review date; drag with audit | `m1_intent/domain/together.py`, screen | Sonnet |
| IC-3c | Governed state: six provenance fields per measure; Lens drafts from policy, RACI, deadlines, pack dependencies | `m2_baseline/domain/governance.py`, `profile` | Sonnet, Opus review |
| IC-3d | The Must/Should rule: a cluster cannot sit on Must or Should until governed; dashed ring names what is missing | `together.py`, screen | Sonnet |
| IC-3e | Lens panel: definition, technical definition, governed state, the one question, confirm or send back; opened from a cluster | `ui/src/modules/m2_baseline` reuse of the owner page | Sonnet |
| IC-3f | Governance percentages on the screen and the centre home | screen | Haiku |

### IC-4 Moment of truth
| IC-4a | Scoreboard header over the existing trial result; restricted count on its own line | `ui/src/modules/m3_connect/trial` | Haiku |
| IC-4b | Re-skin of source map, trial table, plan bands, signing panel to the tokens | m3 screens | Haiku |

### IC-5 Control panel
| IC-5a | Routes: centre switches, model provider per company, egress toggles (internet, connectors, cloud push), egress log read | `sh_platform/control/`, `route_permissions.yaml` | Sonnet, Opus security review |
| IC-5b | Control panel screen (super admin and company admin halves) | `ui/src/pages/ControlPage.tsx` | Sonnet |

### IC-6 Outcomes and run
| IC-6a | Outcomes page per workspace (LI-OUTCOMES) with the centre measures from section 9 of the spec | new page, counters | Sonnet |
| IC-6b | Full live run on the demo workspace, screenshots, run report; client deck | scripts under `local/`, docs | orchestrator |

Order: IC-0, IC-1, IC-2, IC-3, IC-4, IC-5, IC-6. IC-2 and IC-3 may run in parallel worktrees after IC-1 lands.

## 4. Each package brief carries

JOB, OWNS, GUARDRAILS (rules chapters by name), DEFINITION OF DONE (acceptance lines from the card), REUSE CHECK (files and lines from `docs/reuse-inventory.md` and the earlier repo, found with graft), TESTS (two industries, an empty company, one person alone; five screen states), and the sentence "No model or tool name in code, comments, docs or commit messages."

## 5. What the router cannot decide

Whether a spec is right. Whether a design choice should be made. Whether a leak finding is real. Those stay with the orchestrator and the reviewers. The router's only job is to spend Sonnet where Haiku would be wrong and to spend Opus review where a mistake would show one person another's data.
