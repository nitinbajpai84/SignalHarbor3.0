---
id: intent.draw-process-lanes
name: "Draw process lanes"
goal: "Who takes part today"
when: "Use when: who takes part today"
centre: intent
source: core
tier: fast
version: 1
status: in_use
from: "i6_chat (process map)"
---

# Draw process lanes

## Inputs
What the milestone "Process and decisions" hands over.

## Output
lanes

## Steps
1. Read what Harbor passes in for this step.
2. Who takes part today.
3. Produce: lanes.
4. Check: each lane is a person or system named. If the check fails, stop and ask a person.

## Tools
- i6_chat

## Checks
- each lane is a person or system named

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
