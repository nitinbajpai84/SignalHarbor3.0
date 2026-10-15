---
id: build.order-and-schedule
name: "Order and schedule"
goal: "Order the tables and set the refresh"
when: "Use when: order the tables and set the refresh"
centre: build
source: core
tier: tools
version: 1
status: in_use
from: "b6_plan, b6_schedule"
---

# Order and schedule

## Inputs
What the milestone "Code" hands over.

## Output
build plan

## Steps
1. Read what Harbor passes in for this step.
2. Order the tables and set the refresh.
3. Produce: build plan.
4. Check: no cycles; schedule valid. If the check fails, stop and ask a person.

## Tools
- b6_plan
- b6_schedule

## Checks
- no cycles; schedule valid

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
