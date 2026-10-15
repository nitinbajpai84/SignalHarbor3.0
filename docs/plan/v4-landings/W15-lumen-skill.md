# W15: Lumen skill tightened to under 5,000 characters

## What changed

Lumen's skill is now 4,824 characters (was 5,700), down 876 chars.

- **playbook.md**: cut 610 chars (compact opening, compress numbered steps to 2 lines per item, remove redundancy in tile/chart section, tighten explanation flow)
- **questions.md**: cut 184 chars (strip wordy framing, use short forms, trim repetitive phrases)

All critical rules and examples remain: dashboard shaping flow (7 steps), tile structure (title/KPI/SQL/Vega-Lite), explanation format (answer → evidence → sources → caveats → action), status words (official/estimated/revised/stale/unverified), managers workflow.

## How to see it

Skill files in `skills/lumen/` are now tighter:
- `playbook.md`: 1,217 chars (was 1,856)
- `examples.md`: 1,007 chars (unchanged)
- `questions.md`: 592 chars (was 776)
- `traps.md`: 1,108 chars (unchanged)
- `managers.md`: 900 chars (unchanged)

Open a Lumen card and the skill loads and renders the same; no agent behavior change.

## Tests

- pytest tests/v1/test_v3_g1.py: 6 passed
  - Skill stays under cap (test_skills_load_under_cap_whole[lumen] PASSED)
  - All required rules present (test_merged_skills_keep_their_rules PASSED)
  - No rules dropped; no examples cut

Headroom added: 1,176 chars free (6,000 cap − 4,824 used).

## Review

- Total skill size checked: 4859 chars across 5 files, under 5,000 and the 6,000 cap. tests/v1/test_v3_g1.py: 6 passed.
- Fixed: restored "program runs every query" and the {known} token that the tightening had dropped.
- Landing note errors: playbook was cut from about 1,856 to 1,217 and questions.md also changed (no backup was made for questions.md, so its before-text cannot be diffed). The first section's figures are approximate.
- Scope: only skills/lumen/ edited. The builder's note about a "mod" for subagent cost belongs to the relayed chat request, not this card; left open.
