# Demo warehouse (illustrative synthetic data)

Every figure here is invented for demonstration. It is not real client data and does not come from any real load.
One file per measure, named `gold.<measure_code_lowercase>.csv`, periods 2026-01 to 2026-09, SGD where the measure is money.
K05 has a `vehicle` column; K15 and K16 have a `manager` column. K02 (evidence coverage) drops sharply in 2026-09 on purpose, to show a range break.
Load with `python tools/seed_demo_warehouse.py <company_id>`.

Aligned with the company's reported figures (tools in `.sh-tmp` are not needed to read this): for 2026-07 to 2026-09 each table equals the reported figure, so the Prover matches, except K12 in 2026-09 (the custodian file ends on 22 September, so the table holds 24.00 against 28.57 reported: a gap) and K06 in 2026-09 (left blank: the stress file has not landed, so "not yet"). Percentage measures (K09, K10, K12, K17) are held in percent. K02 and K06 are given reported figures by the journey seed (`prove.reported_extra` in `../demo_journey/journey.yaml`).
