---
id: model.design-ready-table
name: "Design ready table"
goal: "ONE ready table for ONE figure"
when: "Use when: oNE ready table for ONE figure"
centre: build
source: core
tier: strong
version: 1
status: in_use
from: "b10_design; once per figure"
---

# Design ready table

## Inputs
What the milestone "Model" hands over.

## Output
table spec (grain, columns, source tables)

## Steps
1. Read what Harbor passes in for this step.
2. ONE ready table for ONE figure.
3. Produce: table spec (grain, columns, source tables).
4. Check: every figure input traced. If the check fails, stop and ask a person.

## Tools
- b10_design

## Checks
- every figure input traced

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
