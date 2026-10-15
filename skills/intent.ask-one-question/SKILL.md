---
id: intent.ask-one-question
name: "Ask one question"
goal: "Pick the ONE most useful question to ask next"
when: "Use when: pick the ONE most useful question to ask next"
centre: intent
source: core
tier: fast
version: 1
status: in_use
from: "new"
---

# Ask one question

## Inputs
What the milestone "Ready to sign" hands over.

## Output
one question

## Steps
1. Read what Harbor passes in for this step.
2. Pick the ONE most useful question to ask next.
3. Produce: one question.
4. Check: answerable in one sentence. If the check fails, stop and ask a person.

## Tools
- none (new code)

## Checks
- answerable in one sentence

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
