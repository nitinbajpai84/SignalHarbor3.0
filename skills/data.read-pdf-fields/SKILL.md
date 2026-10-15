---
id: data.read-pdf-fields
name: "Read pdf fields"
goal: "Read the marked fields of a PDF (notice, statement)"
when: "Use when: read the marked fields of a PDF (notice, statement)"
centre: build
source: core
tier: fast
version: 1
status: in_use
from: "x5_extract, e2_extract"
---

# Read pdf fields

## Inputs
What the milestone "Files in" hands over.

## Output
fields with page and quote

## Steps
1. Read what Harbor passes in for this step.
2. Read the marked fields of a PDF (notice, statement).
3. Produce: fields with page and quote.
4. Check: each value quoted from the page. If the check fails, stop and ask a person.

## Tools
- x5_extract
- e2_extract

## Checks
- each value quoted from the page

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
