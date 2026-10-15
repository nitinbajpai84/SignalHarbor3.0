---
id: intent.draw-process-steps
name: "Draw process steps"
goal: "The steps today, in order, with hand-overs"
when: "Use when: the steps today, in order, with hand-overs"
centre: intent
source: core
tier: strong
version: 1
status: in_use
from: "i6_chat"
---

# Draw process steps

## Inputs
What the milestone "Process and decisions" hands over.

## Output
steps and hand-overs

## Steps
1. Read what Harbor passes in for this step.
2. The steps today, in order, with hand-overs.
3. Produce: steps and hand-overs.
4. Check: every step has a lane and an output. If the check fails, stop and ask a person.

## Tools
- i6_chat

## Checks
- every step has a lane and an output

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
