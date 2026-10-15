---
id: run.on-copy
name: "On copy"
goal: "Run the plan on a copy"
when: "Use when: run the plan on a copy"
centre: build
source: core
tier: tools
version: 1
status: in_use
from: "b6_run sandbox"
---

# On copy

## Inputs
What the milestone "Run and prove" hands over.

## Output
run id

## Steps
1. Read what Harbor passes in for this step.
2. Run the plan on a copy.
3. Produce: run id.
4. Check: every step ok. If the check fails, stop and ask a person.

## Tools
- b6_run

## Checks
- every step ok

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
