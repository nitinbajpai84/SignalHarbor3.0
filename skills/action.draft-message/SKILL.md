---
id: action.draft-message
name: "Draft message"
goal: "Draft the email to the administrator or manager"
when: "Use when: draft the email to the administrator or manager"
centre: action
source: core
tier: fast
version: 1
status: in_use
from: "n1_tally"
---

# Draft message

## Inputs
What the milestone "Investigate" hands over.

## Output
draft, never sent

## Steps
1. Read what Harbor passes in for this step.
2. Draft the email to the administrator or manager.
3. Produce: draft, never sent.
4. Check: needs a person's OK. If the check fails, stop and ask a person.

## Tools
- n1_tally

## Checks
- needs a person's OK

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
