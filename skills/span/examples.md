# Worked examples

Mappings (from the data skill): positions sheet to position_snapshots ("Value (000s)" to source_market_value times 1000, cast decimal; day-first dates); valuations sheet to valuation_observations ("Fund" resolved by approved alias only; month-first dates; Status to estimated or official); cash sheet to cash_movements (Activity to movement_type; reject the batch when the TOTAL row disagrees).

Manager scorecard, one row per manager and month: valuation_observations v join instruments i on v.instrument_id = i.id where i.manager_name is not null; the manager is instruments.manager_name (never the company's own organizations.name); the liquid book has no manager and stays out. Business days late: due = the 10th weekday after the month-end; late = (select count(*) from generate_series(due + 1, received_at::date, interval 1 day) g(d) where isodow(d) < 6). Lateness is judged on the first statement of a fund and month; a revision (supersedes set) is never late. Expected: each fund with a manager, each month-end from its first record; received = distinct funds with a statement; a statement stored twice (pending, then confirmed) counts once.

Explanation: "The manager sent an amended statement for {instrument}: {new_value} against {old_value} in the issued report. Unverified until Operations confirms; official NAV is untouched."
