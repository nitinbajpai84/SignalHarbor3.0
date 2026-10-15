---
id: intent.restate-ask
name: "Restate ask"
goal: "Say back what the person wants in one line"
when: "Use when: say back what the person wants in one line"
centre: intent
source: core
tier: fast
version: 1
status: in_use
from: "i6_chat"
---

# Restate ask

## Inputs
What the milestone "Understand the ask" hands over.

## Output
question, readers, decisions, frequency

## Steps
1. Read what Harbor passes in for this step.
2. Say back what the person wants in one line.
3. Produce: question, readers, decisions, frequency.
4. Check: every part comes from the person's words or is marked "suggested". If the check fails, stop and ask a person.

## Tools
- i6_chat

## Checks
- every part comes from the person's words or is marked "suggested"

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
