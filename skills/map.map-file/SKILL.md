---
id: map.map-file
name: "Map file"
goal: "Map ONE file's columns onto the model"
when: "Use when: map ONE file's columns onto the model"
centre: build
source: core
tier: strong
version: 1
status: in_use
from: "e0b_tools propose mapping; once per file"
---

# Map file

## Inputs
What the milestone "Mapping" hands over.

## Output
mapping with confidence

## Steps
1. Read what Harbor passes in for this step.
2. Map ONE file's columns onto the model.
3. Produce: mapping with confidence.
4. Check: every target column exists. If the check fails, stop and ask a person.

## Tools
- e0b_tools

## Checks
- every target column exists

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
