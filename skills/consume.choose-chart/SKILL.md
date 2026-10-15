---
id: consume.choose-chart
name: "Choose chart"
goal: "Three ways to show one figure"
when: "Use when: three ways to show one figure"
centre: consume
source: core
tier: tools
version: 1
status: in_use
from: "b7o_options"
---

# Choose chart

## Inputs
What the milestone "Boards" hands over.

## Output
options

## Steps
1. Read what Harbor passes in for this step.
2. Three ways to show one figure.
3. Produce: options.
4. Check: from the table's columns. If the check fails, stop and ask a person.

## Tools
- b7o_options

## Checks
- from the table's columns

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
