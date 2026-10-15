---
id: model.find-reusable
name: "Find reusable"
goal: "Which of the office's clean tables already hold this"
when: "Use when: which of the office's clean tables already hold this"
centre: build
source: core
tier: tools
version: 1
status: in_use
from: "e0a_catalogue"
---

# Find reusable

## Inputs
What the milestone "Model" hands over.

## Output
reused tables

## Steps
1. Read what Harbor passes in for this step.
2. Which of the office's clean tables already hold this.
3. Produce: reused tables.
4. Check: table exists, columns match. If the check fails, stop and ask a person.

## Tools
- e0a_catalogue

## Checks
- table exists, columns match

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
