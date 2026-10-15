---
id: intent.capture-benchmark
name: "Capture benchmark"
goal: "What was reported last period, or \"none\""
when: "Use when: what was reported last period, or \"none\""
centre: intent
source: core
tier: tools
version: 1
status: in_use
from: "p4_benchmarks, g3_sheet"
---

# Capture benchmark

## Inputs
What the milestone "Draft the brief" hands over.

## Output
per-figure benchmark

## Steps
1. Read what Harbor passes in for this step.
2. What was reported last period, or "none".
3. Produce: per-figure benchmark.
4. Check: copied by code from words or a report. If the check fails, stop and ask a person.

## Tools
- p4_benchmarks
- g3_sheet

## Checks
- copied by code from words or a report

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
- Never call a model.
