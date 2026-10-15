---
id: run.load-file
name: "Load file"
goal: "Load one file only when it adds up"
when: "Use when: load one file only when it adds up"
centre: build
source: core
tier: tools
version: 1
status: in_use
from: "e0c_load"
---

# Load file

## Inputs
What the milestone "Run and prove" hands over.

## Output
loaded rows

## Steps
1. Read what Harbor passes in for this step.
2. Load one file only when it adds up.
3. Produce: loaded rows.
4. Check: rows in = rows out. If the check fails, stop and ask a person.

## Tools
- e0c_load

## Checks
- rows in = rows out

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
