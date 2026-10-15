---
id: action.investigate
name: "Investigate"
goal: "Why it happened, from the rows and documents"
when: "Use when: why it happened, from the rows and documents"
centre: action
source: core
tier: strong
version: 1
status: in_use
from: "n1_tally"
---

# Investigate

## Inputs
What the milestone "Investigate" hands over.

## Output
finding with evidence

## Steps
1. Read what Harbor passes in for this step.
2. Why it happened, from the rows and documents.
3. Produce: finding with evidence.
4. Check: every claim cites a row. If the check fails, stop and ask a person.

## Tools
- n1_tally

## Checks
- every claim cites a row

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
