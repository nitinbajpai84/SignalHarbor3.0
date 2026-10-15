---
id: intent.set-access
name: "Set access"
goal: "Who may see the result"
when: "Use when: who may see the result"
centre: intent
source: core
tier: fast
version: 1
status: in_use
from: "i4_sow governance"
---

# Set access

## Inputs
What the milestone "Rules" hands over.

## Output
access rule

## Steps
1. Read what Harbor passes in for this step.
2. Who may see the result.
3. Produce: access rule.
4. Check: names real roles. If the check fails, stop and ask a person.

## Tools
- i4_sow

## Checks
- names real roles

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
