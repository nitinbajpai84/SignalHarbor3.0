---
id: intent.define-figure
name: "Define figure"
goal: "Define ONE figure: meaning, formula, unit, period, owner"
when: "Use when: define ONE figure: meaning, formula, unit, period, owner"
centre: intent
source: core
tier: strong
version: 1
status: in_use
from: "i6_chat; runs once per figure"
---

# Define figure

## Inputs
What the milestone "Draft the brief" hands over.

## Output
one figure card

## Steps
1. Read what Harbor passes in for this step.
2. Define ONE figure: meaning, formula, unit, period, owner.
3. Produce: one figure card.
4. Check: formula uses only named inputs. If the check fails, stop and ask a person.

## Tools
- i6_chat

## Checks
- formula uses only named inputs

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
