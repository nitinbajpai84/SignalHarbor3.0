# Data engineer playbook

Build the pipeline from the signed intent of work, never from memory.
1. Read the catalogue first: each table, its layer (landing, cleaned, report), its source and the KPIs it feeds.
2. Read the mapping sheet row by row: target field, source field, transformation, rule, test. A row marked unclear is a question, not a task.
3. Land every file as it arrives; change nothing in landing. Clean in the middle layer: rename, cast dates and amounts, trim text, one row per grain.
4. Report tables have one shape: period (YYYY-MM) and value. A sum or a latest value the runner builds; anything else is SQL you write and the engineer reads.
5. Every table gets checks: not empty on keys, unique on the grain, a range on amounts, and a tie-out to a known total where one exists.
6. A failed check sets rows aside; it never changes them. Say how many and why, then ask.
7. Stop and ask when a meaning is not written down. Never guess a figure, a column's meaning or a business rule.
