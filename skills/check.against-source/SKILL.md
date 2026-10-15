---
id: check.against-source
name: "Against source"
goal: "Compare with an independent source (administrator, custodian)"
when: "Use when: compare with an independent source (administrator, custodian)"
centre: build
source: core
tier: tools
version: 1
status: in_use
from: "b9_verify, b11 variance"
---

# Against source

## Inputs
What the milestone "Run and prove" hands over.

## Output
per-figure checks

## Steps
1. Read what Harbor passes in for this step.
2. Compare with an independent source (administrator, custodian).
3. Produce: per-figure checks.
4. Check: copied numbers only. If the check fails, stop and ask a person.

## Tools
- b9_verify
- b11

## Checks
- copied numbers only

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
