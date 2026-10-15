---
id: model.propose-clean-table
name: "Propose clean table"
goal: "A new shared clean table when none fits"
when: "Use when: a new shared clean table when none fits"
centre: build
source: core
tier: strong
version: 1
status: in_use
from: "e0b_tools, b10_pack"
---

# Propose clean table

## Inputs
What the milestone "Model" hands over.

## Output
proposal for a person

## Steps
1. Read what Harbor passes in for this step.
2. A new shared clean table when none fits.
3. Produce: proposal for a person.
4. Check: does not break a shared table. If the check fails, stop and ask a person.

## Tools
- e0b_tools
- b10_pack

## Checks
- does not break a shared table

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
