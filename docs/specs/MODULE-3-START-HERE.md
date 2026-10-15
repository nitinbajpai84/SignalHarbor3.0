# Module 3 (Assess and plan): start here

Module 3 is worked on in its own chat. Nothing of module 3 is built or merged yet; only these notes exist.

- **Design deck (14 slides, private to Nitin):** https://claude.ai/artifact/PRnJuiGXEDZHph7pRttB9y
- **Decisions:** D-036 in `docs/decisions.md` (bands of weeks 0-3, 3-8, 8+; copy the earlier connect and scan; the high/low line at zero on each axis; Lens leads and reads first, Nira guides from the side; benchmarks from source owners).
- **Reuse inventory of the earlier repo:** `docs/ledger/M3-REUSE/inventory.md` (what to copy, what is missing, risks).
- **Inputs it starts from:** the signed charter (module 1 hand-off: problems, pain_points, future_signals, levers) and the signed baseline (module 2: `read_catalogue`, `read_baseline_outcome`).
- **Catalogue entry already present:** `m3_connect` in `sh_platform/catalogue.yaml`.

## The six steps
1. Source priority map: impact across, readiness up, four zones, click a source for its tables, measures and what is missing.
2. Data request for priority 1 and 2 sources: columns for one period, plus the owner's own reported figure as the benchmark; by connector, Excel or CSV, or JSON.
3. Scan and completeness: structure only (tables, columns, fill, date range, counts); a gap list.
4. Trial run against the benchmark: rules applied by Lens, checked and signed by the source owner.
5. Findings: ready to build, unclear, unknown, each with affected measures and pain points.
6. Phased build plan, signed by the sponsor and the head of data.

## Not yet done
- No build plan in packages, no code.
- Whether a Snowflake connector exists anywhere in the earlier repo is unconfirmed.
- The deck's slides were checked as text only, not rendered.
