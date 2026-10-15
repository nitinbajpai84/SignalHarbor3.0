---
id: map.explain-doubt
name: "Explain doubt"
goal: "Say in plain words why a mapping is unsure"
when: "Use when: say in plain words why a mapping is unsure"
centre: build
source: core
tier: fast
version: 1
status: in_use
from: "v3_harbor d2"
---

# Explain doubt

## Inputs
What the milestone "Mapping" hands over.

## Output
one question

## Steps
1. Read what Harbor passes in for this step.
2. Say in plain words why a mapping is unsure.
3. Produce: one question.
4. Check: answerable by a person in one click. If the check fails, stop and ask a person.

## Tools
- v3_harbor
- d2

## Checks
- answerable by a person in one click

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
