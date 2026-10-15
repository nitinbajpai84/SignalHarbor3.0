# Figures diagnosis: why four people reached "live" and got no figure (15 Oct)

Method: a COPY of each team office (D:/Temp/sh3-team-env-<role>-1 copied to D:/Temp/sh3-fig/<role>), the thread's chains re-run in-process, the warehouse
read with duckdb, the design pack and the plan read from the office. Nothing in the originals was touched.

## What the four offices showed

| Person | Expected | Ready tables the pack had | Clean tables the load filled | Why no figure |
|---|---|---|---|---|
| head_of_data | 41,200,000 (Evergreen Liquid, 30 Sep) | holdings and net worth by entity on `valuation_observations`; `portfolio_metrics` on `metric_values` | none: the 12 administrator workbooks never reached the thread | see 1, 2, 3, 4, 5 |
| cio | 10,180,000 and 180,000 | one table of metric exceptions, no figure columns | none: the PDFs are quarantined, the workbook rejected | PDF reading (another round) and 1, 2, 6 |
| principal | 57,600,000 | holdings, net worth by entity, daily summary on `valuation_observations` | none: the report workbook was rejected, the FX file held back | PDF / report reading and 1, 2, 6 |
| ops_lead | 12,400 | an `exceptions` table filtered to "count mismatch", no amount column | `position_snapshots` 24 rows, `cash_movements` 232 rows; the three bank statements quarantined | 1, 2, 6, 7 |

## Where the figure is lost (in the order the build runs)

1. **The design reads the wrong clean tables.** Chain A drafts and approves the design pack before any file is mapped. Span's reporting template
   (`b6_span.reporting_tables`) then reads `valuation_observations`; the intake writes administrator positions to `position_snapshots` and cash to
   `cash_movements`. The ready tables were correct SQL over tables nothing ever fills. (b10_design ranked tables by words only, never by which table holds data.)
2. **A figure with no table was a quiet note.** The pack was approved with "Define the KPI ... Span could not place it" in its notes (ops_lead: three of
   four figures; head_of_data: three of four). Nothing at Decision 3 said so. Where the model did design, it chose empty tables (`metric_values`, `exceptions`).
   It also could not write a threshold: the number guard blanked "5,000" to "not available yet" inside the SQL.
3. **Files were called loaded when they were not.** `b_load` treated every answer except failed/blocked/refused as loaded. `rejected_totals`,
   `nothing_loaded`, `quarantined` and `waiting_for_mapping` all counted. ops_lead: five files "loaded", three bank statements quarantined, one trade file held back.
4. **The intake rejected ordinary workbooks.** The reader counted the footer lines under a table ("Rows: 29 ...", "Closing balance at period end") as
   data rows, so the row count never matched and the whole file was rejected (administrator positions, bank statements, the issued report Summary). A row
   with no date (a value "not received") crashed the write of the whole October 2025 file. A renamed column ("Valuation Amount (USD)") was not recognised as the market value.
   Fund names that were exactly the instrument's own waited for a click nobody made, so all rows were held back.
5. **File recognition tied.** `administrator_export_*.xlsx` shares one word with "Administrator positions file" and one with "Trading export": a tie,
   so 12 files stayed "question", never reached the thread, and "administrator_positions" was left out of the run.
6. **The run on a copy can be stale.** The round Harbor reads at "Ran on a copy" can be the one made when the pack was approved, before the load;
   Decision 3 then shows a copy that has none of the loaded data. A new pack version had no round at all, so "go live" refused.
7. **Reconciliation needs a design the model cannot yet write.** ops_lead's break is the administrator's day change less the day's movements
   (880,400 less 879,200, against movements of -11,200 on 8 Oct, Entity B: 12,400). The model's draft filters a currency that is not in the data and fails the plan check.
8. **The answer path never looked at the ready table.** `/api/v3/ask` tried the cash/calls route, then Lumen's free tool loop, which listed every gold
   table, saw zero rows and said so. Which warehouse: the answer reads the live warehouse (go-live runs the pack there); Decision 3 reads the trial-run copy.

## What changed

New: `sh_platform/v1/v3_figures.py`. Small generic edits: `e0c_load._read` (table ends at its first blank row), `e0c_load` (a row with no date is
held back and named), `e0b_tools` (valuation amount), `b10_design` (`prefer(...)`: a table holding loaded data outranks an equal fit; the intent's own
numbers go in the ask so the guard keeps them), `v3_harbor` hooks (`b_load`, `a_pack`, `recognise`, `c_note`, `install` at the end), `v3_board_routes._ask`.

- Chain A, inside `a_pack`, before submit: `cover(x, "draft")` designs a ready table for each figure that has none (skill `model.design-ready-table`).
- Chain B, new step after the run on a copy: rebuilds the copy with the loaded data, designs again for each figure whose tables are still empty, on the tables
  the load filled (rules first, the model only for what the rules cannot place; a column of NULLs or a table with no column for the figure is refused),
  approves the new pack version as the head of data, gives it a round, and checks every figure (skill `check.adds-up`).
- Decision 3: one line per figure, "N rows" or "Not available yet" with the reason (tables empty, files that did not load, Span's own note). Never a silent pass.
- `b_load`: the real answer of the load; exact fund names approved in one click; a second layout's mapping approved as the head of data; the reason of a held row named.
- Ask path: the figure the question names (words of its name, the rarest word counting most) is read from its ready table for the month and the portfolio or
  entity the question names (names resolved through the model's code/name pairs); an empty table answers "Not available yet" and why; otherwise Lumen.
- The morning note adds the brief's own figures from their ready tables.

## Result (fresh offices D:/Temp/sh3-fig/f-<role>, server on 8721, the persona steps through the API: tools in D:/Temp/sh3-fig/tools/persona_lite.py)

| Person | Reached | /api/v3/ask | Verdict |
|---|---|---|---|
| head_of_data | live, 802 s | "Net Worth for Evergreen Liquid portfolio in September 2026: 41,200,000." from a ready table Span designed on `position_snapshots` (39 rows, 12 months x portfolios) | **PASS** |
| ops_lead | live, 670 s | "Not available yet: the ready table for Cash variance over threshold has no split by entity." (the earlier wrong -33,200 was refused by a new rule) | **FAIL, honest**: the bank statements cannot load (account numbers are not portfolios: "TCB-7730-210958: portfolio not approved yet") and the model's break table has no entity |
| principal | stuck at the load, with the files named | not asked | **FAIL**: the FX file is read as positions ("no portfolio in the row"), the report workbook is a key/value summary, the PDF layout is new. Needs the report reader (PDF round) |
| cio | not re-run | - | **FAIL**: PDFs and amended statements (PDF round) |

Decision 3 now carries a line per figure. head_of_data: Net worth 39 rows; Time-weighted return, Allocation drift, Single-issuer concentration "Not available yet"
with the reason (a model draft that was only an empty column is refused; the others read `metric_values`, which no file fills).
Second proof not reached for lack of a second office whose files the intake can read. The copy-based re-runs of chains B and C are not a proof: the copies carried
quarantined file records from the original run.

## Not done
- ops_lead: the account-to-entity question (a Decision 2 question), a reconciliation design (administrator day change less the day's movements) the model can write, and the break amount column.
- principal and cio: reading the issued report workbook and the PDFs as figures (round B), and an FX file read as market data.
- Allocation drift, concentration and time-weighted return: they need policy targets or chained returns that no loaded file holds.
