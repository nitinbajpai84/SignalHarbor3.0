---
id: consume.answer-from-cache
name: "Answer from cache"
goal: "Same question on the same data: return the cached answer"
when: "Use when: same question on the same data: return the cached answer"
centre: consume
source: core
tier: tools
version: 1
status: in_use
from: "read_cache"
---

# Answer from cache

## Inputs
What the milestone "Answer" hands over.

## Output
answer or miss

## Steps
1. Read what Harbor passes in for this step.
2. Same question on the same data: return the cached answer.
3. Produce: answer or miss.
4. Check: data version unchanged. If the check fails, stop and ask a person.

## Tools
- read_cache

## Checks
- data version unchanged

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
