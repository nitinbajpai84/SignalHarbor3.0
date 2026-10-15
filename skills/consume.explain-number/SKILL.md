---
id: consume.explain-number
name: "Explain number"
goal: "Where a number is from"
when: "Use when: where a number is from"
centre: consume
source: core
tier: tools
version: 1
status: in_use
from: "a5_trail"
---

# Explain number

## Inputs
What the milestone "Answer" hands over.

## Output
file → run → table → definition

## Steps
1. Read what Harbor passes in for this step.
2. Where a number is from.
3. Produce: file → run → table → definition.
4. Check: from records only. If the check fails, stop and ask a person.

## Tools
- a5_trail

## Checks
- from records only

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
