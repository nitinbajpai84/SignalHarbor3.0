---
id: check.explain-difference
name: "Explain difference"
goal: "Why a figure differs (timing, late notice, sweep)"
when: "Use when: why a figure differs (timing, late notice, sweep)"
centre: build
source: core
tier: strong
version: 1
status: in_use
from: "b9_verify, n1_tally"
---

# Explain difference

## Inputs
What the milestone "Run and prove" hands over.

## Output
one sentence with the rows

## Steps
1. Read what Harbor passes in for this step.
2. Why a figure differs (timing, late notice, sweep).
3. Produce: one sentence with the rows.
4. Check: cites rows. If the check fails, stop and ask a person.

## Tools
- b9_verify
- n1_tally

## Checks
- cites rows

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
