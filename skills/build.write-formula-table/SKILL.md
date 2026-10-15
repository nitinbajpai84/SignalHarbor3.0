---
id: build.write-formula-table
name: "Write formula table"
goal: "Formula figures (returns, fee ratios)"
when: "Use when: formula figures (returns, fee ratios)"
centre: build
source: core
tier: strong
version: 1
status: in_use
from: "b4_formula, e3_calc"
---

# Write formula table

## Inputs
What the milestone "Code" hands over.

## Output
SQL or Decimal code

## Steps
1. Read what Harbor passes in for this step.
2. Formula figures (returns, fee ratios).
3. Produce: SQL or Decimal code.
4. Check: matches the formula's test cases. If the check fails, stop and ask a person.

## Tools
- b4_formula
- e3_calc

## Checks
- matches the formula's test cases

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
