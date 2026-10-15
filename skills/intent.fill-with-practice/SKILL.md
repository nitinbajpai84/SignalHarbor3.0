---
id: intent.fill-with-practice
name: "Fill with practice"
goal: "Fill an empty part with the usual practice, marked suggested"
when: "Use when: fill an empty part with the usual practice, marked suggested"
centre: intent
source: core
tier: fast
version: 1
status: in_use
from: "v3_harbor FILL"
---

# Fill with practice

## Inputs
What the milestone "Ready to sign" hands over.

## Output
suggested lines

## Steps
1. Read what Harbor passes in for this step.
2. Fill an empty part with the usual practice, marked suggested.
3. Produce: suggested lines.
4. Check: every line tagged suggested. If the check fails, stop and ask a person.

## Tools
- v3_harbor

## Checks
- every line tagged suggested

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
