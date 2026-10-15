---
id: consume.attribution
name: "Attribution"
goal: "Why returns moved (allocation, selection)"
when: "Use when: why returns moved (allocation, selection)"
centre: consume
source: core
tier: tools
version: 1
status: in_use
from: "k11_attrib"
---

# Attribution

## Inputs
What the milestone "Reports" hands over.

## Output
attribution table

## Steps
1. Read what Harbor passes in for this step.
2. Why returns moved (allocation, selection).
3. Produce: attribution table.
4. Check: adds up to the active return. If the check fails, stop and ask a person.

## Tools
- k11_attrib

## Checks
- adds up to the active return

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
