---
id: knowledge.learn-word
name: "Learn word"
goal: "A new word the office uses, proposed for the language list"
when: "Use when: a new word the office uses, proposed for the language list"
centre: knowledge
source: core
tier: fast
version: 1
status: in_use
from: "v3_model"
---

# Learn word

## Inputs
What the milestone "Reports" hands over.

## Output
proposal

## Steps
1. Read what Harbor passes in for this step.
2. A new word the office uses, proposed for the language list.
3. Produce: proposal.
4. Check: not already listed. If the check fails, stop and ask a person.

## Tools
- v3_model

## Checks
- not already listed

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
