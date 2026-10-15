---
id: harbor.test-skill
name: "Test skill"
goal: "Run a skill on its known answers"
when: "Use when: run a skill on its known answers"
centre: knowledge
source: core
tier: tools
version: 1
status: in_use
from: "new"
---

# Test skill

## Inputs
What the milestone "Reports" hands over.

## Output
pass / fail per case

## Steps
1. Read what Harbor passes in for this step.
2. Run a skill on its known answers.
3. Produce: pass / fail per case.
4. Check: all cases run. If the check fails, stop and ask a person.

## Tools
- none (new code)

## Checks
- all cases run

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
