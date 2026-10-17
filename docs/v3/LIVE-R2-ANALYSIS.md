# Live run 2: analysis of the 27 failing checks

Read-only analysis. Evidence: reports in `D:/Temp/sh3-live/r2/<uc>.json`, offices `D:/Temp/sh3-uc-env-<uc>` (threads, figure records), and read-only copies of each office warehouse (`evidence.duckdb` plus `.wal`) queried with DuckDB. The originals were not edited; the copies were deleted after analysis.

Totals: 50 reports, 23 pass, 27 fail (every report with `check.pass` false).

## Counts per class

| Class | Meaning | Count |
|---|---|---|
| (a) | Figure not bound to the recipe that answers the key | 14 |
| (b) | Bound, but its ready table is empty or missing | 7 |
| (c) | Table right, answer did not state the key numbers | 4 |
| (d) | Persona check too strict | 0 confirmed as sole cause (risk noted below) |
| (e) | Other | 2 |
| | Total | 27 |

Class is the dominant cause of the missing keys. Secondary causes are named in the case notes.

## Important caveat on the evidence

The report stores only `answer` (the sentence). The check (`v3_persona.py`, `said()`) also scans the answer's `rows` (label and value), which are not saved. So for class (c) the evidence is what the bound table holds, not what the answer rows showed.

## Class (a): figure not bound to the answering recipe (14)

| Case | Evidence | One-line fix |
|---|---|---|
| uc-015-allowances | "Scheduled payment", "Paid amount", "Cash availability" are bound to no recipe. Family Trust USD cash 213,895.52 sits in `net_worth`, which no figure binds. The answer used September, not October. | Bind cash availability to the net-worth or cash recipe; answer the current month. |
| uc-016-schemadrift | No figure for `columns_changed`; no such table in the warehouse. Answer fell back to "Rules-only reply". | Design and bind a figure on `columns_changed`. |
| uc-017-liab | "Loan debt" is bound to `missing_statements` (185 rows, wrong recipe). `facility_headroom` table never built. | Bind loan debt to `facility_headroom`. |
| uc-026-stmtadmin | "Statement variance" and "Amendment justification" are unbound; the office has no gold tables at all. `statement_vs_admin` is not bound. | Bind statement variance to `statement_vs_admin`; check manager-statement mapping. |
| uc-031-alloc | No `allocation` table in the office; the allocation figure is unbound. Net-worth and TWR rows were used instead. | Bind an asset-class and entity share figure to `allocation`. |
| uc-034-prospect | "Ticket vs uncalled" is bound to `called_to_date`. "Minimum ticket vs policy limit" is unbound; `mandate_fit` never built. | Bind minimum ticket and policy limit to `mandate_fit`. |
| uc-038-navroll | "Quarterly private-fund valuation reconciliation" is bound to `change_since_report` (no table in this office). `nav_rollforward` not built. | Bind to `nav_rollforward`. |
| uc-040-icmemo | "Called amount", "Latest value", "Amendment status" are unbound. "Unfunded amount" is bound to `called_to_date`, not `commitments_by_fund`. | Bind each figure to its recipe (called, latest value, amendment, unfunded). |
| uc-043-liquidpnl | "Daily liquid-book P&L" is bound to `change_since_report` (3 rows, wrong recipe). Liquid P&L recipe not built. | Bind to the liquid P&L recipe. |
| uc-044-twr | No figure is bound to `time_weighted_return`; `metric_values_monthly_by_entity` has 0 rows. | Bind quarter, YTD and benchmark figures to `time_weighted_return`. |
| uc-045-reportpack | `report_ready` recipe is not bound and has no table. Key `60` is its `share_ready_pct`. | Bind section readiness to `report_ready`. |
| uc-047-icpack | `pack_items` and single-name limit (`5.75`) are unbound. Also TWR is bound but unbuilt (class b). | Bind pack items and single-name breach figures. |
| uc-049-feedrag | "Fee share of gain" is unbound (`fee_drag` has 4 rows, but the share column is not carried). Net-gain keys are in no bound figure. | Bind fee share to `fee_drag` and carry net gain. |
| uc3-statements-inbox | "Statement receipt status" is bound to `missing_statements` (calendar basis, answer 65). Key is `statement_timeliness`, business days, 63. | Bind overdue figure to `statement_timeliness`. |

## Class (b): bound, but ready table empty or missing (7)

| Case | Evidence | One-line fix |
|---|---|---|
| uc-024-audit | `trace_coverage` bound; no table. The audit request xlsx is in the pack as kind `audit`, but "Auditor list of numbers" is left out. | Load kind `audit` into the auditor-list source. |
| uc-032-driftrep | `drift_vs_target` bound, 0 rows. Policy limits are loaded as rule_type `limit` (4 approved, e.g. listed_equity 60 to 90). The recipe reads rule_type `policy`. The signed policy PDF is kind `reference` in all 27 offices. "No file yet for bank_balances, manual_adjustments_log" comes from Span's source list; those files are not in the fixture. | Accept `limit` rules in the recipe, or classify the policy PDF as `policy_document`; drop sources the fixture lacks. |
| uc-033-breachesc | `single_name_breach` bound, 0 rows. Same limit-typing and policy-kind cause; `breach_alert` not in fixture. | As uc-032. |
| uc-035-ddq | `ddq_compare` bound to "Controls" only, no table ("design had no column"). The DDQ PDFs are kind `ddq`, but the sources "DQ 2025 file" and "DQ 2026 file" are left out. | Map kind `ddq` to the DQ 2025 and 2026 sources; let Span design the compare. |
| uc-048-policyupd | `limit_changes` bound, 0 rows. Limits are rule_type `limit`; `manual_adjustments` not in fixture. | As uc-032. |
| uc4-vs-benchmark | TWR bound; no table ("design had no column"). Figure name does not map to `time_weighted_return` columns. | Map "Time-weighted return net of fees" to `portfolio_return_pct` and `benchmark_return_pct`. |
| uc5-limits | `single_name_breach` bound; no table ("design had no column"). | Map the single-name breach columns in the design step. |

## Class (c): table right, answer did not state the key numbers (4)

| Case | Evidence | One-line fix |
|---|---|---|
| uc-007-pacing | `commitments_by_fund` (9 rows) holds every per-fund key (3,750,000, 800,000, 2,750,000, 250,000, 6,000,000, 600,000, 300,000, 150,000). Answer gave the total only. Secondary: budget figure has 0 rows (policy kind, class b). | Answer "for every fund" with one line per row. |
| uc-013-secgaps | `identifier_gaps` (52 rows) holds "Pacific Rim Convertible 2029 note" and 1,122,000. Answer quoted "Missing asset class count" rows, all 0.00. | Pick the figure that matches the question ("which instruments" and "value") among the three bound to the same table. |
| uc-023-tieout | `report_tie_out` (18 rows) holds 4,581, 110,866, 289,043 for Apr to Jun. Answer scoped to September only (0.00). | When no month is given, cover every month in the table. |
| uc-050-feeinv | `invoice_variance` (4 rows) holds 15,595.58, 4,940.14, 16,234.50, 6,180, 5,150, 1,030. Answer listed only variance. "Invoices checked" was refused by the plan check and dropped. | Show billed, expected and variance per invoice; fix the plan-check refusal. |

## Class (d): persona check too strict (0 sole causes)

No case fails only because of string format. Risk: four cases expect 4-decimal strings that a 2-decimal reply can never match: uc4 and uc-047 (`4.1667`, `2.7072`), uc-039 (`0.9282`, `0.9222`, `1.3792`, `1.0168`, `2.4875`, `1.2833`, `1.125`, `0.9042`), uc-044 (`0.2958`, `3.5148`, `3.821`, `5.7563`). uc-035 needs verbatim topic phrases. Fix: compare numerically at the table's precision.

## Class (e): other (2)

| Case | Evidence | One-line fix |
|---|---|---|
| uc-039-irr | The table holds the 9 correct fund rows (23.24, 32.74, -40.54, and so on). It also holds 4 extra rows for the same funds in another entity or with no TVPI. Those carry history gaps of 0.5M to 1.2M and `irr_status` incomplete, because `capital_call_and_distrib` and `custodian_statements` are left out. The answer guard saw conflicting rows and replied "Rules-only". | Exclude incomplete rows from answers and dedupe by fund; load the capital-call and distribution inputs. |
| uc-041-commitappr | `commit_check` (1 row) shows uncalled_before 58,600,000 and uncalled_after 60,600,000, cash cover 10.16%. The same office's `commitments_by_fund` gives unfunded 14,600,000, and the key needs 16,600,000 and 37.08%. Cash 6,156,041.41 and new commitment 2,000,000 are right. The score50 fixture passes this case, so this is a live-only divergence. | Trace the uncalled base in `commit_check` against `commitments_by_fund`. |

## Fixes ranked by cases affected

1. Figure-to-recipe binding (class a): 14 cases (uc-015, uc-016, uc-017, uc-026, uc-031, uc-034, uc-038, uc-040, uc-043, uc-044, uc-045, uc-047, uc-049, uc3). Bind by the recipe's output columns and definition, not by name; refuse to create a figure with no bound recipe; add a per-key binding test.
2. Input kinds not mapped (class b, input side): 5 cases (uc-024, uc-032, uc-033, uc-035, uc-048), plus the uc-007 budget. Classify the policy PDF as `policy_document`; accept `limit` rules; map `audit` and `ddq` kinds to their sources; drop sources the fixture lacks from Span's design.
3. Answer path (class c, and the fallback): 4 cases (uc-007, uc-013, uc-023, uc-050), plus 3 "Rules-only reply" fallbacks (uc-016, uc-039, uc-047). List every row of the bound table when the question says "each" or gives no scope; pick the figure by question semantics; keep verified figures when others fail.
4. Design-to-column mapping (class b, design side): 2 cases (uc4, uc5). Map figure names to recipe columns with synonyms.
5. Row integrity (class e): 2 cases (uc-039, uc-041). Exclude incomplete rows; reconcile `commit_check` uncalled with `commitments_by_fund`.
6. Persona check precision (class d): 0 sole causes; apply to 4 cases at risk.

## Harness note

The report keeps only the answer sentence. Save `said()` (sentence plus rows) so that class (c) can be judged from the answer as shown.
