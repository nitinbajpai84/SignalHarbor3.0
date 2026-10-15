# FIXC: Span's design pack designs the use case's own gold tables

Evidence: UC6-REPORT (M4, M5) and UC8-REPORT (B2, M6). Spec: BUILD-FLOW-V6 step 2. Direction from Nitin on the way: silver is the company's data model and stays stable, so Span reuses silver first and proposes a model change only when no existing table or column can hold a fact.

## What changed

1. **The pack designs its own gold** (`sh_platform/v1/b10_design.py`, new; called from `b10_pack.generate`). For every figure the rules and the reporting template could not place, the designer gives a column in a gold table at the grain the intent states.
   - With a model: one call (Span, plan tier), which writes the gold SQL over the company model's tables and, only if nothing fits, a silver change with `looked_for` and `considered` (table, why not). Every table goes through the plan check; a table that fails falls back to the rules' design.
   - Rules only: each figure is ranked against the 42-table core model plus approved extensions (table name, listed values of a column such as `movement_type: call, distribution`, column names). The best table is the fact table; the measure, date, dimensions (found by joins up to three keys away, for example entity via portfolio) and filters (calls → `movement_type = 'call'`) come from the model's own columns and notes. No silver table is ever invented by the rules.
   - A figure with no definition, with a condition the rules cannot write, or that no table fits, is still listed: a "Define the KPI" note and an open mapping row (a person settles it). No silent "not available yet".
   - The investment-report template stays one case; its trigger is now `net worth|holdings|valuations` (a figure that only mentions a fund or a position no longer draws holdings tables).
2. **Silver reused vs proposed** in the pack. `target.silver` entries carry `status` reused / extended / proposed. Reused: which other projects already read the table (`k3_model._edges` lineage). Proposed: what was looked for, tables considered and why they do not fit, which other projects' gold tables are affected, and the linked model change number. Columns on an existing table are preferred to a new table.
3. **Model change through e0a**: one proposal per project (`model-change.json` in the project folder), filed with `E.propose` by DBML, linked to the pack (`pack.model_change`). New Span chat tool `propose_model_change` (`span_tools.py`), filed by `b6_span.chat` for the data team; a change filed in chat joins the pack at the next draft. Column types are normalised (`E.norm_type`: varchar, string, char → text; decimal, numeric, money → numeric(18,2); datetime → timestamp) and `_duck_type` accepts them.
4. **Pack edit** can add a gold table (`gold_add`: name, purpose, select, tables read, definitions), rewrite one (`gold_table` with `sql` / `depends_on`), and remove one (`gold_remove`). The plan check types the columns; new columns without a definition become open rows.
5. **One approval** by the head of data (`b10_pack.approve`) now approves the pack, the linked model change and the build plan drawn from it (proposed in the pack maker's name, approved by the approver, so maker-never-checker still holds). The builder starts (`b11_builder.pack_of` finds an approved plan). If the plan cannot be drawn, the pack stays approved with `plan_error`, and the screen shows "Approve the build plan" (`POST .../pack/plan/approve`, permission row added, head-of-data seat enforced in the handler).
6. **UI** (`ui/src/v1/b10`): "Silver reused" table, "Silver proposed" cards, "Add a gold table" form, plan-approval status and button.

## Files

Edited: `sh_platform/v1/b10_pack.py`, `b6_span.py` (draft_plan takes `model_changes`; holdings trigger), `span_tools.py`, `e0a_catalogue.py` (only `norm_type`, `_duck_type`, the form type in `propose`), `b10_routes.py`, `b10.permissions.yaml`, UI `api.ts`, `ArchitectureStep.tsx`, `b10.test.tsx`; test change in `tests/v1/test_v6b_pack_and_benchmark.py` (plan versions skip because pack approval now also approves a plan). New: `sh_platform/v1/b10_design.py`, `tests/v1/test_fixc_span_pack.py`. Backups: `D:/Temp/bak-fixc/`.

## How to test

`pytest tests/v1/test_fixc_span_pack.py tests/v1/test_v6_b10_pack.py tests/v1/test_b11_builder.py tests/v1/test_e0a.py tests/auth`; `cd ui && npx vitest run src/v1/b10 && npx tsc --noEmit`. In the app: Build > Architecture > the design pack: a UC6 pack shows a gold table on cash_movements, "Silver reused", no new table; Anita approves once and Build shows the builder ready.

## Departures and limits

- The number guard rewrites digits it cannot trace in a model reply (it turned `group by 1, 2` into text). The prompt now says `group by all`; the figures in the intent are in the context so names like `next_30_days` survive.
- Rules-only design is a baseline: counts and totals with enum filters. Windows ("within 30 days"), compound figures (cash after calls), and reconciliation breaks need the model or a person; they are listed as "Define the KPI" rows. UC8's break list (trade id, type, amount, status) comes from the model's design over `transactions`; the rules only count trades.
- A new silver table or column still needs a source mapping before it fills; the pack lists it as proposed, not mapped.
- Re-filing a chat change after the first was proposed creates a new proposal that contains both; approving it supersedes the older one (e0a behaviour).
- FIXE2 (cycle date) may touch `today()` call sites in the same files; I changed none.
