# Agent evals

Sixty-four golden items for the five agents, a runner that plays them against a running product, and deterministic scorers that mark them. Synthetic data only (the Evergreen Office universe, `docs/test/10uc_universe.json` and `docs/test/10UC-ANSWER-KEY.md`).

| Agent | Items | File | What it is checked on |
|---|---|---|---|
| North (Intent) | 11 | `tests/evals/north.yaml` | Draft intent and swim lane from the process narrative: 6 steps, manual steps 1-4 flagged, asks for missing owners, never invents a figure |
| Span (Build) | 10 | `tests/evals/span.yaml` | Plan holds the gold tables the report and benchmark need, data-model questions answered with the right table names, a participant's change stays a suggestion |
| Lumen (Consume) | 17 | `tests/evals/lumen.yaml` | Tile figures equal the universe (K01 net worth, K02 cash, K03 status), follow-ups edit the last tile, questions answered in words, identity tables refused |
| Tally (Action) | 15 | `tests/evals/tally.yaml` | Right cause and figures for P08, P28-P30, P17-P18, P02, P22; figures filled by the program; who may see which case |
| Memory | 11 | `tests/evals/memory.yaml` | A preference persists across sessions, person A never gets person B's items, forget works, no client figure stored; two context-map items (pending) |

Each item has: `id`, `agent`, `role` (who to log in as: sponsor Daniel Foo, analyst Mei Chen, approver Raj Patel, participant Sofia Reyes, company_admin Grace Ong), `route`, `turns` (what is said), `expected` (exact figures, required and forbidden words, expected status code) and `scorers`.

## What each scorer means

| Scorer | In plain words |
|---|---|
| `figure_match` | Every figure the answer key says must be there is there, to the cent, in the answer, the findings or the tile rows. "12,400" and "12400.00" are the same figure. Ids like T-20261002-003 are not figures. |
| `groundedness` | Every number the model wrote in its own words also appears in what the program filled in (findings, tile rows, sources), in the person's own question, or in the item's short list of allowed numbers. A digit the model made up fails. Small counts, years and days of the month are ignored. For North the "program" is the file the person gave. |
| `citation_present` | The answer comes with something to check it against: source chips, a trail, a trace id. |
| `access` | A person who should not get it gets the 403 or 404, or an answer that holds none of the forbidden words (no e-mails, no hidden cases). |
| `follow_up_edit` | "Make it dots", "line in blue", "monthly not daily", "in SGD" changed the tile from the turn before (same measure, same table, new look) and did the thing asked; a brand-new tile does not count. |
| `egress_clean` | In the egress log lines written during the item, no person, company, entity, manager, fund or security name from the universe. Also counts blocked lines. Not measurable (skipped) when the egress log cannot be read. |
| `latency_ms` | How long the item took. Fails only if the item sets a limit. |
| `cost` | Tokens from the router cost log (and dollars from the agent-runs route when that exists). Fails only if the item sets a limit. |
| `words` | Required words present, forbidden words absent, expected status code. |
| `structure` | North: number of steps, which steps are flagged manual, required intent sections filled. |
| `turn_expect` | Checks written on single turns of a multi-step item (memory: new session, other person, after forget). |

A scorer that does not apply to an item returns "n/a" and is left out of the pass rate. An unknown scorer name fails.

An optional wording judge is described in `tests/evals/judge_rubric.md`. It is a prompt only, off by default, and would run through the product's own router.

## How to run

Start the product yourself (the runner never starts a server and refuses port 8400). Make the data with `python tools/seed_10uc.py --data-root <folder>`; the creds file is `<folder>/_control/seed_credentials.txt`.

```
python tools/run_evals.py --base http://127.0.0.1:8711 --creds <seed_credentials.txt> --mode testing --out docs/test/evals/run-testing
python tools/run_evals.py --base http://127.0.0.1:8711 --creds <seed_credentials.txt> --mode real    --out docs/test/evals/run-real
python tools/run_evals.py --compare docs/test/evals/run-testing docs/test/evals/run-real --out docs/test/evals/compare
```

Options: `--agents north,lumen`, `--items LUM-01,TAL-03`, `--company evergreen`. `--mode` sets the Testing / Real use switch through `POST /api/v1/router/mode` as the company admin and puts it back at the end; without `--mode` the run uses whatever is set and says which. The Testing run costs nothing (stubbed or free models); the Real run spends money on the model, so run it on a small `--agents` set first.

The runner leaves things as it found them: tiles Lumen proposes are rejected after each item, memory the memory items write is forgotten, and the intents North drafts stay as ordinary draft intents (delete them in the test company when done).

Self-check of the scorers and the golden sets, no server: `pytest tests/evals/test_scorers.py`.

## How to read the report

`REPORT.md` in the output folder:

- Pass rate per agent (items that ran; "pending" items are not counted) and per scorer. The per-scorer table shows what kind of mistake an agent makes: low `groundedness` means model-written figures, low `figure_match` means wrong or missing figures, low `follow_up_edit` means Lumen makes a new tile instead of editing.
- Cost and latency per agent: median and 95th percentile milliseconds, calls and tokens from the router cost log, dollars from the agent-runs route (company admin), egress lines written and blocked.
- Worst items: each failed item with the scorer and the reason ("not from the program: 15,000").
- Pending: items whose route does not exist yet (a 404 or 405 "Not Found" on the first turn). They turn into real items by themselves when the route lands.

`items/<id>.json` has everything for one item: each request and response, the scores, the trace id (find the same work in the agent-runs page), cost, latency and the egress lines it wrote. `summary.json` is the same in one file and is what `--compare` reads. `COMPARE.md` puts Testing and Real use side by side: pass rate, median time and tokens per agent, and the items whose result differs.

## Observability while testing

What you can see for a test run, and where:

- Per call: trace id (agent-runs route `/api/v1/agent-runs/trace/{trace_id}`), latency, tokens and tier from the router cost log (`/api/v1/router/costs`), and the egress log lines the call produced (`/api/company/egress-log`).
- Per agent per day: runs, failures, tool calls and dollars from `/api/v1/agent-runs` (company admin).
- Per run: the report above, with both modes side by side from `--compare`.
- Gaps to know about: the cost log has tokens but no dollars, so dollars come from agent-runs only where an agent run row exists; the egress log holds hosts, decisions and sizes but no content by design, so `egress_clean` can only catch a name that leaks into a log field.

## Pending today

- Tally items use the routes in `sh_platform/v1/e4a_routes.py` (`/api/v1/cases/{id}/ask` and `/tally`); the landing note `docs/plan/v4-landings/TALLY.md` was not on disk when the items were written. If the n1_tally route changes, edit `route` in `tests/evals/tally.yaml`.
- Memory: MEM-10 (context map on the Map page, `/api/v1/map/conversations`, a name taken from the plan, not a built route) and MEM-11 (Span recalls what Lumen was told, MEM2 `context_for`) are pending until MEM2 lands.
- Case titles for the limit and revision cases (TAL-06 to TAL-08) are found by title text plus `exception_type`; if the product words them differently the runner reports "no case matching" as an error, and the match text in the item is the thing to change.

## Review

One review pass, no live run. Verdict: ready for a first live run; expect some items to need their match text adjusted.

Checked and fine: 15 expected values against `10uc_universe.json` and `10UC-ANSWER-KEY.md` (K01 to K03, P08, P17, P18, P02, P22, P28 to P30, the 12,400 and 5,000 tolerance); the routes, request fields and response keys the items rely on (intents chat returns `id`, `sow`, `process_map`; Tally returns `summary`, `answer`, `findings`, `sources`; memory `items` and `forgotten`; router mode and costs; egress-log `entries`); the cost-log row keys; the scorers are deterministic and groundedness fails a model-written digit (tested). The runner writes only under its `--out` folder, never reads or writes `data/`, and refuses a base URL on port 8400. TAL-11 holds: a policy-question case has no portfolio and no owner, so only the company admin sees it.

Defects fixed:
- `structure` looked for a `manual` field on each process step. The product has none; the SOP builder derives it from the step text (`k8_sop.MANUAL`). NOR-01 would always have failed. The scorer now asks the product's own `k8_sop.build` (read-only import).
- `egress_clean` read `name` from funds and securities, which the universe calls `canonical_name`, and missed manager contact names. Fixed; a test pins Northwind Logistics, Kestrel Ridge Macro Fund and Daniel Foo.
- Sign-in role match required the roles column to equal the role; it now accepts a comma list.

Open items, for the first live run:
- `egress_clean` is weak by design: the egress log holds host, decision and size only, so it can only catch a name that leaks into a log field. Real proof of "no names leave" is the gateway's own tests.
- Case titles for TAL-06 to TAL-09 are guesses; a mismatch shows as an error, not a failure.
- NOR-10 assumes a participant is refused on a signed intent; if the product allows the turn, decide whether the item or the product is wrong.
- Draft intents from North items stay in the test company (delete by hand).
- MEM-10 (map route) is pending; MEM-11 will fail until MEM2 lands.
