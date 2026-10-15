---
id: data.profile-file
name: "Profile file"
goal: "Columns, types, examples, row count"
when: "Use when: columns, types, examples, row count"
centre: build
source: core
tier: tools
version: 1
status: in_use
from: "catalogue_scan, e0b_tools"
---

# Profile file

## Inputs
What the milestone "Files in" hands over.

## Output
file profile

## Steps
1. Read what Harbor passes in for this step.
2. Columns, types, examples, row count.
3. Produce: file profile.
4. Check: row count equals file. If the check fails, stop and ask a person.

## Tools
- catalogue_scan
- e0b_tools

## Checks
- row count equals file

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
