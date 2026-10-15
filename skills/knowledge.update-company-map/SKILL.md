---
id: knowledge.update-company-map
name: "Update company map"
goal: "Add what was just built to the company's graph"
when: "Use when: add what was just built to the company's graph"
centre: knowledge
source: core
tier: tools
version: 1
status: in_use
from: "m1_map, k3_onto"
---

# Update company map

## Inputs
What the milestone "Reports" hands over.

## Output
nodes and links

## Steps
1. Read what Harbor passes in for this step.
2. Add what was just built to the company's graph.
3. Produce: nodes and links.
4. Check: from records only. If the check fails, stop and ask a person.

## Tools
- m1_map
- k3_onto

## Checks
- from records only

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
