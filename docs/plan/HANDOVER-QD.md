# Handover addendum: the demo journey seeder (QD) finished at 01:40, 7 Oct

The builder's files are UNCOMMITTED in the worktree `.claude/worktrees/qd`: `tools/seed_demo_journey.py`, `tests/tools/test_seed_demo_journey.py`, `packs/family_office/1/demo_journey/journey.yaml` and `README.md`. Tests: 3 passed, 1 expected failure (the sponsor's signature line, see below). Bring the worktree in, run its test file, commit.

## Important: the real ardmore plane holds a partial earlier run
An early copy of the script was run on `data/ardmore` and opened only the Performance wall and the drafted messages (manifest at `data/ardmore/context/seed_demo_journey/manifest.json`). Run the worktree version with `--reset` first: `tools/seed_demo_journey.py ardmore --reset`. It undoes the partial run and seeds the full journey (tested on a copy). Then `tools/seed_demo_history.py ardmore`. Then restart the backend.

## What the seed gives ardmore
- Closed wall "Treasury: capital calls (illustrative)": 8 people, 30 cards (12 anonymous, 2 sealed), five groups, votes, one group on Good to have, a signed charter with six "so that" lines, Build roles set (developer left empty: the people list has no data engineer).
- Open wall "Performance: manager benchmarks" in the private rooms, 4 of 8 seats, 9 cards.
- Signed baseline: 12 measures (K01-K06, K09, K10, K12, K15-K17) with definitions, owners, glossary, all six governed fields; K06 and K16 restricted to named lists; signed by Daniel Kerr then Janet Shaw.
- Module 3: files and benchmarks uploaded, trial run, risks accepted, plan signed.
- Build: five environment answers stated, blueprint signed by Marcus Todd, pipeline contracts, two runs (one ok, one late with a failed rule), UAT signed on ten measures, release draft.
- Two map comments (an ambiguity on K09 by Aaron Lyle; an anonymous suggestion on K17 accepted by the steward), one kept what-if for Daniel, one drafted message of each kind, graph rebuilt after every step.

## Blocked by code outside the seeder (fix these before the demo)
1. `sh_platform/build/prove.py`: `_compute` looks up reported figures by measure code but the profile keys them by measure name; `_ours` reads the mart column named in the blueprint while the demo gold tables have only `period, value`. Result: Prove shows 12 measures with no periods. Even fixed, ardmore's reported figures do not equal the demo gold values, so "ten matches" needs the demo gold CSVs aligned with the reported figures (or the seeder writing prove.json directly for the demo).
2. Prove keeps one row per lineage row, so two-source measures (K02, K16) appear twice and lose their UAT.
3. `sh_platform/pulse/lines.py` `_next_slot_mine` never points at the first slot, so the sponsor never gets a signature line; add a `release` reader that gives the sponsor a line while the release is a draft.
4. `sh_platform/build/uat.py` `_role` reads roles from the charter outcome record, but roles are saved in `intents/m1_intent/roles/<sid>.json`; the named tester is never found.
5. The register and map link measures to charter problems only, not pain points or future signals.
6. The measure page's "defined" trail step shows a raw cell instead of text.
7. `--reset` restores earlier copies of shared files, so run it before anything else edits the plane.

## Pulse per person on a copy of the seeded plane
Janet (organiser): interview, a wall invite, a data request, "1 source late or failed". Daniel (sponsor): Performance wall invite, interview, the K09 ambiguity to decide. Aaron: Performance and Treasury invites, interview, the K09 decision. Katie: Performance invite, interview, late source. Grace: interview only. Harvey: interview, a data request.
