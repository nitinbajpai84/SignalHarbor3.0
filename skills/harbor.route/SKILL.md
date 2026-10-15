---
id: harbor.route
name: "Route"
goal: "Which outcome and milestones a request needs"
when: "Use when: which outcome and milestones a request needs"
centre: knowledge
source: core
tier: fast
version: 1
status: in_use
from: "v3_harbor"
---

# Route

## Inputs
What the milestone "Reports" hands over.

## Output
plan

## Steps
1. Read what Harbor passes in for this step.
2. Which outcome and milestones a request needs.
3. Produce: plan.
4. Check: known milestones only. If the check fails, stop and ask a person.

## Tools
- v3_harbor

## Checks
- known milestones only

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
