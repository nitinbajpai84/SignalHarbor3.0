# Shadow mode: replay two past periods

Shadow mode loads last month's and this month's files again, in the order they arrived, as if the product had been running. It shows what the product would have found, and when.

## Run it

1. Write a spec file listing each period, its cutoff date and its files with the date and time each was received (example in the header of `tools/shadow_run.py`).
2. `python tools/shadow_run.py <company> spec.json --out shadow_report.csv`
3. Open `shadow_report.csv`. Each row is a finding: file, when received, case opened, seconds from receipt to finding. A reviewer fills the `false_alert` column (yes or no) for each row.
4. Open `shadow_report_reproducible.csv`. For each period cutoff it compares the figures at the end of that period with the figures asked for again after all later periods loaded. Every row should say `yes`: a figure as known on a past date does not change when later files arrive. Exit code 1 if any says `NO`.

## Safe by default

The replay writes to a separate plane `<company>_shadow` and never to live data. `--live` replays into the company itself and adds rows there; use it only when asked.

During a replay the clock is set to each file's historical receipt (plus the real seconds the work takes), so recorded times match what happened then. It is restored when the run ends, even on an error.

## What it needs

The load engine (E0c), reconciliation (E3b) and revision impact (E3c). If one is missing the run stops with a plain error rather than skipping the step.

Reviewer note: time from receipt to finding is machine time only; it does not include the hours before a person would have opened the file.
