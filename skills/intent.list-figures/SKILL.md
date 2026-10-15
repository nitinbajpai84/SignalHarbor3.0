---
id: intent.list-figures
name: "List figures"
goal: "Name the figures the answer needs"
when: "Use when: name the figures the answer needs"
centre: intent
source: core
tier: fast
version: 1
status: in_use
from: "i6_chat (KPIs)"
---

# List figures

## Inputs
What the milestone "Draft the brief" hands over.

## Output
list of figure names

## Steps
1. Read what Harbor passes in for this step.
2. Name the figures the answer needs.
3. Produce: list of figure names.
4. Check: at least one; no duplicates. If the check fails, stop and ask a person.

## Tools
- i6_chat

## Checks
- at least one; no duplicates

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
