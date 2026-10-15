# Traps

- Renamed columns: stacking monthly files under one header leaves the old name empty after the change. Map both names to one field; never drop the old months.
- Stale files: a file whose period is older than the last loaded period is a re-send or a mistake. Ask before loading it over newer figures.
- Missing currency: never assume one. Hold the rows and ask.
- Duplicates: check the grain (account, instrument, date) before summing; a doubled row doubles the value.
- Return maths: time-weighted return chains monthly returns, (1 + r1) x (1 + r2) - 1; it never averages them. Flows in the month must be taken out first.
- Drift is weight now minus target weight, per asset class, from the policy's targets; a target not written down is an open point.
- Concentration needs a stated level: issuer, asset class or manager.
- Net of fees needs the fee file for the same period; a fee posted late moves the figure.
- The transport rewrites digits in your words: write no digit in SQL or ids; constants come from columns.
