---
id: consume.make-monthly-pack
name: "Make monthly pack"
goal: "The month-end pack, PDF and Excel"
when: "Use when: the month-end pack, PDF and Excel"
centre: consume
source: core
tier: tools
version: 1
status: in_use
from: "e1_reports, exports"
---

# Make monthly pack

## Inputs
What the milestone "Reports" hands over.

## Output
files

## Steps
1. Read what Harbor passes in for this step.
2. The month-end pack, PDF and Excel.
3. Produce: files.
4. Check: matches the issued report. If the check fails, stop and ask a person.

## Tools
- e1_reports

## Checks
- matches the issued report

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
