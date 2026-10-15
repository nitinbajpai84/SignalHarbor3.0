---
id: action.suggest-next-step
name: "Suggest next step"
goal: "What a person could do (ask, mark timing, correct)"
when: "Use when: what a person could do (ask, mark timing, correct)"
centre: action
source: core
tier: fast
version: 1
status: in_use
from: "n1_tally"
---

# Suggest next step

## Inputs
What the milestone "Investigate" hands over.

## Output
2 or 3 options

## Steps
1. Read what Harbor passes in for this step.
2. What a person could do (ask, mark timing, correct).
3. Produce: 2 or 3 options.
4. Check: none moves money. If the check fails, stop and ask a person.

## Tools
- n1_tally

## Checks
- none moves money

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
