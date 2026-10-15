---
id: action.size-impact
name: "Size impact"
goal: "How much is at stake, which reports it touches"
when: "Use when: how much is at stake, which reports it touches"
centre: action
source: core
tier: tools
version: 1
status: in_use
from: "e3_impact"
---

# Size impact

## Inputs
What the milestone "Notice" hands over.

## Output
amount, reports

## Steps
1. Read what Harbor passes in for this step.
2. How much is at stake, which reports it touches.
3. Produce: amount, reports.
4. Check: numbers from rows. If the check fails, stop and ask a person.

## Tools
- e3_impact

## Checks
- numbers from rows

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
