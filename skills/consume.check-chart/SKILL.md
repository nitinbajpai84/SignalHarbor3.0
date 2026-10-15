---
id: consume.check-chart
name: "Check chart"
goal: "Is the chart honest (no double counting, right scale)"
when: "Use when: is the chart honest (no double counting, right scale)"
centre: consume
source: core
tier: tools
version: 1
status: in_use
from: "b7k_checks"
---

# Check chart

## Inputs
What the milestone "Boards" hands over.

## Output
checks

## Steps
1. Read what Harbor passes in for this step.
2. Is the chart honest (no double counting, right scale).
3. Produce: checks.
4. Check: rules only. If the check fails, stop and ask a person.

## Tools
- b7k_checks

## Checks
- rules only

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
