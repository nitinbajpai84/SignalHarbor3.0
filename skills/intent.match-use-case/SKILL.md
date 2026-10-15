---
id: intent.match-use-case
name: "Match use case"
goal: "Match the ask to a known use case of the pack or the office"
when: "Use when: match the ask to a known use case of the pack or the office"
centre: intent
source: core
tier: fast
version: 1
status: in_use
from: "c2_offers, intent_examples"
---

# Match use case

## Inputs
What the milestone "Understand the ask" hands over.

## Output
use-case id or "new"

## Steps
1. Read what Harbor passes in for this step.
2. Match the ask to a known use case of the pack or the office.
3. Produce: use-case id or "new".
4. Check: id exists. If the check fails, stop and ask a person.

## Tools
- c2_offers
- intent_examples

## Checks
- id exists

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
