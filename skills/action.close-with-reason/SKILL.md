---
id: action.close-with-reason
name: "Close with reason"
goal: "Close with the reason recorded"
when: "Use when: close with the reason recorded"
centre: action
source: core
tier: tools
version: 1
status: in_use
from: "e4_cases"
---

# Close with reason

## Inputs
What the milestone "Route" hands over.

## Output
closed case

## Steps
1. Read what Harbor passes in for this step.
2. Close with the reason recorded.
3. Produce: closed case.
4. Check: reason present. If the check fails, stop and ask a person.

## Tools
- e4_cases

## Checks
- reason present

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
