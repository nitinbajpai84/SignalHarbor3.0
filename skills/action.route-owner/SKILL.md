---
id: action.route-owner
name: "Route owner"
goal: "Who should act, by when"
when: "Use when: who should act, by when"
centre: action
source: core
tier: tools
version: 1
status: in_use
from: "p2_assign, e4_cases"
---

# Route owner

## Inputs
What the milestone "Route" hands over.

## Output
owner and due

## Steps
1. Read what Harbor passes in for this step.
2. Who should act, by when.
3. Produce: owner and due.
4. Check: owner has the role. If the check fails, stop and ask a person.

## Tools
- p2_assign
- e4_cases

## Checks
- owner has the role

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
