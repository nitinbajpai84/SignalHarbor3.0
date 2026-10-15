---
id: build.go-live
name: "Go live"
goal: "Switch on the schedule, record who and when"
when: "Use when: switch on the schedule, record who and when"
centre: build
source: core
tier: tools
version: 1
status: in_use
from: "p5_handover"
---

# Go live

## Inputs
What the milestone "Live" hands over.

## Output
live record

## Steps
1. Read what Harbor passes in for this step.
2. Switch on the schedule, record who and when.
3. Produce: live record.
4. Check: schedule set. If the check fails, stop and ask a person.

## Tools
- p5_handover

## Checks
- schedule set

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
