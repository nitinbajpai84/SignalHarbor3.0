---
id: intent.name-sources
name: "Name sources"
goal: "Which systems and files hold the inputs"
when: "Use when: which systems and files hold the inputs"
centre: intent
source: core
tier: fast
version: 1
status: in_use
from: "catalogue_scan"
---

# Name sources

## Inputs
What the milestone "Draft the brief" hands over.

## Output
sources with owner and what they hold

## Steps
1. Read what Harbor passes in for this step.
2. Which systems and files hold the inputs.
3. Produce: sources with owner and what they hold.
4. Check: every figure input has a source. If the check fails, stop and ask a person.

## Tools
- catalogue_scan

## Checks
- every figure input has a source

## Never
- Never invent a figure, name or rule that is not in the inputs.
- Never act outside its own output.
