---
id: consume.answer-question
name: "Answer question"
goal: "Answer from the ready tables"
when: "Use when: answer from the ready tables"
centre: consume
source: core
tier: fast
version: 1
status: in_use
from: "talk, cx_lumen"
---

# Answer question

## Inputs
What the milestone "Answer" hands over.

## Output
figure, chart, sentence

## Steps
1. Read what Harbor passes in for this step.
2. Answer from the ready tables.
3. Produce: figure, chart, sentence.
4. Check: number guard; every figure traced. If the check fails, stop and ask a person.

## Tools
- cx_lumen

## Checks
- number guard; every figure traced

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
