---
id: consume.build-board
name: "Build board"
goal: "A board from the brief's figures"
when: "Use when: a board from the brief's figures"
centre: consume
source: core
tier: fast
version: 1
status: in_use
from: "b7_studio, v3_harbor c_lumen"
---

# Build board

## Inputs
What the milestone "Boards" hands over.

## Output
tiles

## Steps
1. Read what Harbor passes in for this step.
2. A board from the brief's figures.
3. Produce: tiles.
4. Check: every tile has data. If the check fails, stop and ask a person.

## Tools
- b7_studio
- v3_harbor
- c_lumen

## Checks
- every tile has data

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
