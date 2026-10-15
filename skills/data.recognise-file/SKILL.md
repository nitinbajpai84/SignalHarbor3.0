---
id: data.recognise-file
name: "Recognise file"
goal: "Which source a file is"
when: "Use when: which source a file is"
centre: build
source: core
tier: tools
version: 1
status: in_use
from: "v3_harbor.recognise"
---

# Recognise file

## Inputs
What the milestone "Files in" hands over.

## Output
source or question

## Steps
1. Read what Harbor passes in for this step.
2. Which source a file is.
3. Produce: source or question.
4. Check: tie asks, never guesses. If the check fails, stop and ask a person.

## Tools
- v3_harbor.recognise

## Checks
- tie asks, never guesses

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
