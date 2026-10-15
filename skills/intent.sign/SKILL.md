---
id: intent.sign
name: "Sign"
goal: "Sign in the confirming person's name, keep the record"
when: "Use when: sign in the confirming person's name, keep the record"
centre: intent
source: core
tier: tools
version: 1
status: in_use
from: "i4_sow.sign"
---

# Sign

## Inputs
What the milestone "Ready to sign" hands over.

## Output
signature, version

## Steps
1. Read what Harbor passes in for this step.
2. Sign in the confirming person's name, keep the record.
3. Produce: signature, version.
4. Check: signer = person who clicked. If the check fails, stop and ask a person.

## Tools
- i4_sow.sign

## Checks
- signer = person who clicked

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
