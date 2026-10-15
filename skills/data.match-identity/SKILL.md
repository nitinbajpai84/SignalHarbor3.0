---
id: data.match-identity
name: "Match identity"
goal: "Which entity, fund or instrument a name means"
when: "Use when: which entity, fund or instrument a name means"
centre: build
source: core
tier: fast
version: 1
status: in_use
from: "e2_match"
---

# Match identity

## Inputs
What the milestone "Files in" hands over.

## Output
id or question

## Steps
1. Read what Harbor passes in for this step.
2. Which entity, fund or instrument a name means.
3. Produce: id or question.
4. Check: one match or ask. If the check fails, stop and ask a person.

## Tools
- e2_match

## Checks
- one match or ask

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
