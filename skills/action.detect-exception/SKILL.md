---
id: action.detect-exception
name: "Detect exception"
goal: "A break, shortfall, late file or limit breach"
when: "Use when: a break, shortfall, late file or limit breach"
centre: action
source: core
tier: tools
version: 1
status: in_use
from: "e3_recon, e3_rules"
---

# Detect exception

## Inputs
What the milestone "Notice" hands over.

## Output
exception record

## Steps
1. Read what Harbor passes in for this step.
2. A break, shortfall, late file or limit breach.
3. Produce: exception record.
4. Check: rule-based. If the check fails, stop and ask a person.

## Tools
- e3_recon
- e3_rules

## Checks
- rule-based

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
