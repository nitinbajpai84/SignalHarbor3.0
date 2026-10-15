---
id: consume.write-morning-note
name: "Write morning note"
goal: "The note: headline, 3 points, who must decide"
when: "Use when: the note: headline, 3 points, who must decide"
centre: consume
source: core
tier: fast
version: 1
status: in_use
from: "k10_note"
---

# Write morning note

## Inputs
What the milestone "Reports" hands over.

## Output
note

## Steps
1. Read what Harbor passes in for this step.
2. The note: headline, 3 points, who must decide.
3. Produce: note.
4. Check: figures from the run. If the check fails, stop and ask a person.

## Tools
- k10_note

## Checks
- figures from the run

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
