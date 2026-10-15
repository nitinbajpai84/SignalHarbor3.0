---
id: intent.find-gaps
name: "Find gaps"
goal: "Which required parts are still empty"
when: "Use when: which required parts are still empty"
centre: intent
source: core
tier: tools
version: 1
status: in_use
from: "t1_templates.sign_block"
---

# Find gaps

## Inputs
What the milestone "Ready to sign" hands over.

## Output
list

## Steps
1. Read what Harbor passes in for this step.
2. Which required parts are still empty.
3. Produce: list.
4. Check: from the template, no judgement. If the check fails, stop and ask a person.

## Tools
- t1_templates.sign_block

## Checks
- from the template, no judgement

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
