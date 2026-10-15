---
id: build.write-run-book
name: "Write run book"
goal: "How it runs, who is called when it breaks"
when: "Use when: how it runs, who is called when it breaks"
centre: build
source: core
tier: fast
version: 1
status: in_use
from: "g2_runbook"
---

# Write run book

## Inputs
What the milestone "Live" hands over.

## Output
run book

## Steps
1. Read what Harbor passes in for this step.
2. How it runs, who is called when it breaks.
3. Produce: run book.
4. Check: names owners. If the check fails, stop and ask a person.

## Tools
- g2_runbook

## Checks
- names owners

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
