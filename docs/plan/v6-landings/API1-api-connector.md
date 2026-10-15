# API1: Connect an API (Build)

Screenshot: `docs/plan/v6-landings/api1-connect.png` (live Frankfurter test, 2 series, run on a private test server, port 8611, now stopped).
Page: Build › `/centre/build/connect-api` (linked from Settings › Connectors). Built on the existing C5 connectors: same spec file, routes, run records, health, poll and egress Gate. No parallel framework.

## Providers and endpoints (all verified live on 12 Oct 2026)

| Provider | Host (fixed) | Key env name | Endpoint used | Series offered |
|---|---|---|---|---|
| Frankfurter (ECB reference rates) | api.frankfurter.dev | none | `/v1/<start>..?base=&symbols=` | USD/SGD, EUR/USD, EUR/SGD, GBP/USD |
| FRED | api.stlouisfed.org | `FRED_API_KEY` | `/fred/series/observations` | DGS10, DGS2, DEXSIUS (SGD per USD, daily), FPCPITOTLZGSGP (Singapore CPI inflation, annual) |
| Finnhub | finnhub.io | `FINNHUB_API_KEY` (sent as header `X-Finnhub-Token`, never in the address) | `/api/v1/quote`, `/api/v1/news?category=general` | ACWI, AGG, EWS quotes; market news |
| MAS (Singapore Government Securities) | eservices.mas.gov.sg | none | `/statistics/api/v1/bondsandbills/m/listbondsandbills` | SGS 2/5/10/15/20/30-year bond auction cut-off yield |

The old host api.frankfurter.app redirects; only the `.dev` host is on the allowlist. Every call sends User-Agent `SignalHarbor/1.0` (FRED stalls on a UA containing "test").
Straits Times Index: licensed. EWS (iShares MSCI Singapore) is the stand-in and is labelled so in the series list. AGG is the US aggregate bond ETF, labelled as a bonds proxy.

## Singapore findings

- SGS yields: reachable without a licence or key through the MAS statistics API. It returns auction results only (the latest 10 rows, filterable by tenor), so the value is "yield at the last auction of that tenor", not a daily curve. Auctions announced but not held (yield 0) are skipped.
- SORA: not added. MAS publishes it through its API gateway (`eservices.mas.gov.sg/apimg-gw/...`), which refuses calls without a registered key (SOAP fault "MessageBlocked"); the public page is an ASP.NET form, not an API. Needs a free MAS API key registration. Add as a provider when a key exists.
- SGD exchange rates: Frankfurter (ECB) and FRED DEXSIUS. The MAS exchange-rate dataset on data.gov.sg (`d_046ff8d521a218d9178178cfbfc45c2c`) was last updated June 2024, so it is not used.
- data.gov.sg listed no SORA or SGS yield dataset (590 datasets scanned).
- "Any REST API" option: left out on purpose (SSRF). Hosts are fixed per provider and series come from a catalogue.

## What gets written (for Consume; fields to read)

Warehouse table `market_observations`, one row per series and observed day, append-only (a revised value supersedes the old row):
- `series_key`: `FX:USDSGD:ECB`, `FX:USDSGD:FRED_H10`, `YLD:US10Y:FRED`, `YLD:US2Y:FRED`, `MAC:SGCPI:FRED`, `IDX:ACWI:FINNHUB`, `IDX:AGG:FINNHUB`, `IDX:EWS:FINNHUB`, `YLD:SGS10Y:MAS_AUCTION` (and other tenors). The provider is in the key, so an outside rate never matches the company's signed fx_fixing rule unless that rule names it.
- `observation_type`: `fx`, `yield` (percent), `index_level` (ETF price, USD), `macro`.
- `observed_at`: the observed date (UTC midnight). `quality_status` = `outside_live_api` (the outside + live marker).
- Provenance by join: `source_record_id` → `source_records.source_batch_id` → `source_batches.source_system_id` → `source_systems` where `connection_method = 'live_api'`, `source_type = 'api'`, `licence_scope = 'outside public data'`, `source_name` = provider name.
- Ready-made: `sh_platform.v1.c5_connect.api.markers(plane)` returns, per live series, `{series_key, label, kind, value, observed_date, provider, source_code, outside: true, live: true, marker: "LIVE API · <provider> · <date>"}`; also `GET /api/v1/connect-api/latest` (data engineer seat). File-loaded rows keep `quality_status = 'loaded'`, which is the "file" marker.
- News: `market/briefs.json` `added` list (the list Consume › Markets "To watch" already reads), each item `outside: true`, `live_api: true`, `kind: "news"`, `measures: []`, `source: "Finnhub · <publisher>"`, `date`. Newest 50 kept, same headline never twice. News is never a figure.

## How to test

- Backend: `python -m pytest tests/v1/test_c5_api.py tests/v1/test_c5_connect.py` (recorded fixtures, no network, plus live smoke: Frankfurter and MAS always; FRED and Finnhub only when the key variable is in the environment, otherwise skipped with a message).
- UI: `cd ui && npx vitest run src/v1/c5`.
- By hand: Settings › Egress: internet on. Build › Connect an API (or Settings › Connectors › Connect an API): choose Frankfurter, Test the connection (real rows and timing), Save. Settings › Connectors lists it as `api-frankfurter` with Fetch now. Daily 05:30 pull runs on the existing landing poll (`C5.run_due`, uses `b6_schedule.last_slot` for the 05:30 slot, server clock). Check Consume with `api.markers`.

## Security notes

- Fixed hosts, https only, no redirects followed, 10 s timeout with 2 retries, 1 MB reply cap, at most one call per chosen series. Series ids come only from the catalogue; a host or address in the request is ignored.
- Every call goes through `ops.Gate`: company internet switch, host on the company's allowed list, log line written before the call (host, kind, byte count; never the address, key or file name). Save and Test add only the fixed provider hosts to the allowed list; the internet switch itself is never touched.
- Keys read by variable name at call time; never in a spec, response, log, file or error (tested). The UI shows "Stored by the administrator as <NAME>" and whether it is set. FRED takes its key as a query parameter (its only option); the address is never logged and exception text is never kept.
- Outside text: tags, entities and control characters stripped, length-capped, stored as outside material, never read as an instruction. No model call anywhere.
- One change to shared behaviour: `ops.Gate` now also counts as on when every module's internet switch is on (the Settings toggle sets entitled modules, never `c5_connect`, so the earlier connectors could not run from Settings). Off stays the default.
- Not done: on a provider outage the run is recorded as failed with "The provider did not answer. It will be tried again at the next run." and the next daily slot retries; there is no same-day retry.

## Env vars for Railway (names only)

`FRED_API_KEY`, `FINNHUB_API_KEY` (already set per the coordinator). Frankfurter and MAS need none. Optional later: a MAS API key for SORA (name to be chosen when added).

## Files

New: `sh_platform/v1/c5_connect/api.py`, `ui/src/v1/c5/ConnectApiPage.tsx`, `ui/src/v1/c5/connectApi.test.tsx`, `tests/v1/test_c5_api.py`.
Edited (backups `.sh-tmp/*.bak-api1`): `c5_connect/spec.py`, `c5_connect/ops.py`, `c5_routes.py`, `c5.permissions.yaml`, `consume/market_store.py` (`add_news`), `ui/src/v1/c5/api.ts`, `routes.tsx`, `ConnectorsPage.tsx`.
