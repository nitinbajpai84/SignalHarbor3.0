# FIXB2 recon basics (trade_vs_admin)

Files: `sh_platform/v1/e3_recon.py` (`_trades`, `_trade_start`, `_bdays`, `_carried`, `_fx_ids`), `sh_platform/v1/n1_tally.py` (`timing_cause` now reads trade breaks too), `tests/v1/test_fixb2_recon.py`. Backups in D:/Temp/bak-fixb2/.

- Window: a run on the last business day of a month (no weekday left in that month after it) checks the 1st to as_of; any other day keeps the 30-day window. Rule words name the dates.
- Break `type` on every result line: quantity, price (FX forward: contract rate and amount, USD at the as_of spot from market observations, against the allowance), missing (one side only), timing, other (instrument/currency/date disagree).
- Timing: same instrument, quantity and amount, booked exactly one business day apart (by id or without one). Opens a case at net 0 and the line carries `cause` from `n1_tally.timing_cause`, so Action shows "Close as timing".
- Carried: an open trade break dated before the window whose trade is still unreconciled (one side only, or still over the allowance using each side's latest row by effective_date) is listed with `carried: true` and counted in `carried`, not in `breaks`, and no case is opened. Amended items are not listed; their case stays for a person to close.
- Cancelled rows (status 'cancelled', from the loader) are skipped in the run and in the carry check.
- Tests: Jul 4/4/0, Aug timing + cause, Sep quantity 75,870 / FX 8,100 SGD = 6,039.37 USD / missing 592,000, Oct 3/3/0 with Harborview carried once (two runs), cancelled trade skipped.
- Not done: a trade booked either side of a month boundary; no holiday calendar.
