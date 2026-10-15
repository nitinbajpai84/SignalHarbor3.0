---
id: harbor.write-skill
name: "Write skill"
goal: "Draft a new skill from repeated human steps"
when: "Use when: draft a new skill from repeated human steps"
centre: knowledge
source: core
tier: strong
version: 1
status: in_use
from: "new"
---

# Write skill

## Inputs
What the milestone "Reports" hands over.

## Output
SKILL.md + tests

## Steps
1. Read what Harbor passes in for this step.
2. Draft a new skill from repeated human steps.
3. Produce: SKILL.md + tests.
4. Check: passes its own tests. If the check fails, stop and ask a person.

## Tools
- none (new code)

## Checks
- passes its own tests

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
