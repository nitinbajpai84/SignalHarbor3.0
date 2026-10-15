---
id: model.propose-ontology-addition
name: "Propose ontology addition"
goal: "A new object or property this office uses"
when: "Use when: a new object or property this office uses"
centre: build
source: core
tier: fast
version: 1
status: in_use
from: "v3_model"
---

# Propose ontology addition

## Inputs
What the milestone "Model" hands over.

## Output
proposal

## Steps
1. Read what Harbor passes in for this step.
2. A new object or property this office uses.
3. Produce: proposal.
4. Check: not already in the model. If the check fails, stop and ask a person.

## Tools
- v3_model

## Checks
- not already in the model

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
