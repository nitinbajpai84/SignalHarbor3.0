---
id: consume.precompute-golden
name: "Precompute golden"
goal: "After each run, answer the most-asked questions ahead"
when: "Use when: after each run, answer the most-asked questions ahead"
centre: consume
source: core
tier: tools
version: 1
status: in_use
from: "read_cache"
---

# Precompute golden

## Inputs
What the milestone "Answer" hands over.

## Output
cached answers

## Steps
1. Read what Harbor passes in for this step.
2. After each run, answer the most-asked questions ahead.
3. Produce: cached answers.
4. Check: same as answer-question. If the check fails, stop and ask a person.

## Tools
- read_cache

## Checks
- same as answer-question

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
