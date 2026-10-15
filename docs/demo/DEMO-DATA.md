# Demo data: what every screen shows

Synthetic Evergreen Office only. Built at boot by `tools/start.sh` -> `tools/seed_demo_boot.py` (seed_10uc, then `tools/seed_demo_ready.py`). Every step skips what is already there (the pipeline is run once; a redeploy never runs it again, so `entity_cash_daily` does not grow), so a redeploy changes nothing; a step that fails is printed in the boot log and never stops the boot.

| Screen | Sign in as | What it shows |
|---|---|---|
| Action, Today | Anita Rao | Waiting for my approval: Lumen's starter dashboard and plan v3 (the pending model extension). Cases include the 12,400 Entity B cash break (timing cause from the wire), the 592,000 unmatched trade, the 180,000 revision, limit breaches |
| Action, Today | Mei Chen / Daniel Foo | Statements to chase: Cedarpoint Opportunities II, June statement missing. Figures to confirm: the draft Cedarpoint Ventures III statement (no statement date, so it waits for a person) |
| Operations, Runs | Leo Park | Test and production pipeline runs of the monthly investment report (with steps) and of the benchmark project; reconciliation runs. Live pipelines (from the run log, `GET /api/v1/ops/pipelines`): each pipeline's last production run, time taken, checks, state and next scheduled run; the tile reads 2 of 2 healthy. Sources still come from connector loads |
| Operations, Deliveries | Leo Park | Morning Note preview; the dashboard's Consume and Morning Note channels are approved, live and have sent records (Build > project > Delivery) |
| Consume, Markets | any | LIVE API rows: Frankfurter and MAS always; FRED (DGS10, DEXSIUS) and Finnhub (EWS, ACWI, AGG) only when `FRED_API_KEY` / `FINNHUB_API_KEY` are set on the server |
| Consume, Reports | Raj Patel | Signed September report, the published monthly dashboard, the benchmark project's approved starter dashboard |
| Map, Ontology | Anita Rao | Bronze -> silver (entity_cash_daily, manager_fee_schedule) -> gold -> dashboards; 22 items waiting in the review queue |
| Map, Data model | Anita Rao | 38 loaded silver tables incl. entity_cash_daily; 1 pending model proposal (manager_fee_schedule) for the head of data to approve |
| Build | Leo / Anita | Project "Monthly performance against the office blend": intent signed by Daniel, pack approved, pipeline live, starter dashboard approved |

Markets: the seed turns the company's Internet and Connectors switches on for the demo company only (Settings > Egress), and only when a provider answers a connection. Offline it skips and writes nothing (no fake "live" rows). Rerunning pulls the latest days.

## Reset

`python tools/seed_demo_boot.py --reset --data-root <root>` empties the data root and seeds it again (new sign-in details in `<root>/_control/seed_credentials.txt`, or the shared `SH_DEMO_PASSWORD`). It refuses the repo's `data/` unless `--allow-repo-data` is added, and needs an explicit root.

On Railway (the volume is `$SH_DATA_ROOT`):

    railway ssh -- sh -c 'python tools/seed_demo_boot.py --reset --data-root "$SH_DATA_ROOT"'
    railway redeploy        # the running app keeps the old warehouse file open: restart it

In production mode (DATABASE_URL set) app records also live in Postgres. Add `--reset-db` to empty them too:

    railway ssh -- sh -c 'python tools/seed_demo_boot.py --reset --reset-db --data-root "$SH_DATA_ROOT"'

`--reset-db` needs `--reset` and DATABASE_URL, and only TRUNCATEs the `sh_state_*` and `sh_outbox*` tables (rows; it never drops a table). Run it before the restart, so the next boot reseeds from nothing.

Boot seeding does not need the job queue: the pipeline runs of the seed happen inline even in production mode (no worker runs yet at that point). A market provider that fails prints its reason in the boot log (never the key), e.g. `fred failed (0 new): key_refused: ...`; a key with stray spaces or quotes is trimmed before use.

Add the data after a reset by the same restart; nothing else is needed. Keys (`FRED_API_KEY`, `FINNHUB_API_KEY`) are service variables, never files.
