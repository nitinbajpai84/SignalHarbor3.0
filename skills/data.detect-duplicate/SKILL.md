---
id: data.detect-duplicate
name: "Detect duplicate"
goal: "Same file as before?"
when: "Use when: same file as before?"
centre: build
source: core
tier: tools
version: 1
status: in_use
from: "e0c_landing"
---

# Detect duplicate

## Inputs
What the milestone "Files in" hands over.

## Output
yes or no

## Steps
1. Read what Harbor passes in for this step.
2. Same file as before?.
3. Produce: yes or no.
4. Check: hash. If the check fails, stop and ask a person.

## Tools
- e0c_landing

## Checks
- hash

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
