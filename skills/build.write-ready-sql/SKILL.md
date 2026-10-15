---
id: build.write-ready-sql
name: "Write ready sql"
goal: "SQL for ONE ready table"
when: "Use when: sQL for ONE ready table"
centre: build
source: core
tier: strong
version: 1
status: in_use
from: "b6_span, b4_formula"
---

# Write ready sql

## Inputs
What the milestone "Code" hands over.

## Output
SQL

## Steps
1. Read what Harbor passes in for this step.
2. SQL for ONE ready table.
3. Produce: SQL.
4. Check: runs on a copy; passes sqlglot guard. If the check fails, stop and ask a person.

## Tools
- b6_span
- b4_formula

## Checks
- runs on a copy; passes sqlglot guard

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
