---
id: intent.read-company-doc
name: "Read company doc"
goal: "Take facts from a document the person dropped"
when: "Use when: take facts from a document the person dropped"
centre: intent
source: core
tier: fast
version: 1
status: in_use
from: "i5_docs"
---

# Read company doc

## Inputs
What the milestone "Understand the ask" hands over.

## Output
definitions, owners, systems, rules with quotes

## Steps
1. Read what Harbor passes in for this step.
2. Take facts from a document the person dropped.
3. Produce: definitions, owners, systems, rules with quotes.
4. Check: every fact has a quote. If the check fails, stop and ask a person.

## Tools
- i5_docs

## Checks
- every fact has a quote

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
