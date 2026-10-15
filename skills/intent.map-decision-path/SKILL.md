---
id: intent.map-decision-path
name: "Map decision path"
goal: "Who decides what, on which threshold, and who is told"
when: "Use when: who decides what, on which threshold, and who is told"
centre: intent
source: core
tier: strong
version: 1
status: in_use
from: "new"
---

# Map decision path

## Inputs
What the milestone "Process and decisions" hands over.

## Output
decision path

## Steps
1. Read what Harbor passes in for this step.
2. Who decides what, on which threshold, and who is told.
3. Produce: decision path.
4. Check: each decision has an owner and a trigger. If the check fails, stop and ask a person.

## Tools
- none (new code)

## Checks
- each decision has an owner and a trigger

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
