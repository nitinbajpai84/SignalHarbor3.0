---
id: check.adds-up
name: "Adds up"
goal: "Parts add up; no figure untraced; reload unchanged"
when: "Use when: parts add up; no figure untraced; reload unchanged"
centre: build
source: core
tier: tools
version: 1
status: in_use
from: "e3_recon"
---

# Adds up

## Inputs
What the milestone "Run and prove" hands over.

## Output
checks

## Steps
1. Read what Harbor passes in for this step.
2. Parts add up; no figure untraced; reload unchanged.
3. Produce: checks.
4. Check: rules only. If the check fails, stop and ask a person.

## Tools
- e3_recon

## Checks
- rules only

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
