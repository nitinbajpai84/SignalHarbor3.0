---
id: intent.write-sop
name: "Write sop"
goal: "Standard operating procedure from the signed brief"
when: "Use when: standard operating procedure from the signed brief"
centre: intent
source: core
tier: fast
version: 1
status: in_use
from: "k8_sop"
---

# Write sop

## Inputs
What the milestone "Ready to sign" hands over.

## Output
SOP document

## Steps
1. Read what Harbor passes in for this step.
2. Standard operating procedure from the signed brief.
3. Produce: SOP document.
4. Check: follows the process steps. If the check fails, stop and ask a person.

## Tools
- k8_sop

## Checks
- follows the process steps

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
