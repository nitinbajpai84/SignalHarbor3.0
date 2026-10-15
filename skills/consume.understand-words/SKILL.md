---
id: consume.understand-words
name: "Understand words"
goal: "Turn the office's words into model terms (\"dry powder\" = uncalled)"
when: "Use when: turn the office's words into model terms (\"dry powder\" = uncalled)"
centre: consume
source: core
tier: tools
version: 1
status: in_use
from: "v3_model language"
---

# Understand words

## Inputs
What the milestone "Answer" hands over.

## Output
terms

## Steps
1. Read what Harbor passes in for this step.
2. Turn the office's words into model terms ("dry powder" = uncalled).
3. Produce: terms.
4. Check: from the language list. If the check fails, stop and ask a person.

## Tools
- v3_model

## Checks
- from the language list

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
