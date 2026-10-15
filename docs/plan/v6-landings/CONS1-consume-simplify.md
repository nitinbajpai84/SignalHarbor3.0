# CONS1: Consume, simple and fast

## What changed
Consume has five tabs and one currency switch (top right, kept between pages; Markets also has its Month / Year to date / Since inception switch).
- **Today** (`/centre/consume`): the Morning Note. One sentence, four key numbers (NAV today, P&L yesterday, P&L for the month, against the benchmark), What moved (with unconfirmed funds), the markets in one line with its source. P&L yesterday says "Waits for the daily price file." (no price file, no number). Comments on the note and Ask Lumen sit at the foot.
- **Financial health** (`/centre/consume/health`): Daily P&L and NAV plus Fund performance in one table with a By portfolio / By entity / By fund switch (By fund is the fund league, with the head-of-data index mapping panel), the "Trust in the value" column, total and Unexplained, and the three count tiles.
- **Markets** (`/centre/consume/markets`): the market table, Ours against it, To watch (manager letters and live headlines). Every outside line shows source, date and a FILE or LIVE API tag read from the warehouse (market_observations, source record, batch, source system: `connection_method = live_api` is LIVE API, else FILE). Seeded data reads "Market data file (demo data)".
- **Reports**: library, plus Shared with you and Published dashboards as sections.
- **What if**: the old Attribution page (`/centre/consume/what-if`).
- Delivery (email and Slack previews) is `DeliveriesSection`, mounted in `/centre/operations` (id `deliveries`). Old routes redirect: pnl, league to health; signals to markets; shared, dashboards to reports; analytics to what-if (query kept); email, slack to operations#deliveries.
- Backend: `GET /consume/today`, `GET /consume/health`; `signals` gains `provenance` per series, yield and macro series from the live-API connector, and `headlines`. `note`, `pnl`, `daily`, email and Slack are unchanged.

## How to test
`cd ui && npx tsc --noEmit && npx vitest run src/v1`; `python -m pytest tests/v1/test_k10_note.py` (plus k9, k4, e3, e5). Open the three pages as Daniel Foo on a seeded env; open `/centre/operations` as an analyst for Deliveries. Screenshots: `cons1-today.png`, `cons1-health.png`, `cons1-markets.png` (this folder).

## Performance (seeded env, same machine, quiet moment, median of 4)
Cause: nothing was kept or shared. One Morning Note made 493 warehouse queries and 103 connections: the issued report was read 4 times, cases twice, and `holdings` ran 4-6 queries per holding line (N+1, run twice per line) for "where is this from". P&L and NAV then called `pnl` and `daily` which repeated all of it. Every visit recomputed everything.
Fixes at the root: (1) `scope_memo`: per-request memo of the pure reads (portfolio value, fx, issued report, cases, holdings, ...), (2) `prefetch_sources` in k4_office: five batched queries instead of one set per line, (3) `read_cache`: answers kept per viewer and question until any write request ends, the warehouse file is written, or 60 s pass, (4) Today and Health read only what they show (no liquidity, cases, reports).

| | before | after |
|---|---|---|
| Morning Note API (`note`; `today`) | 900 ms | 584-913 ms cold, 11 ms kept |
| Today page, time to content | 860 ms every visit | 870 ms first load, 140 ms after |
| Daily P&L and NAV page (`pnl` 1330 + `daily` 750 ms) | 1380 ms | Financial health: 630-1030 ms cold, 13 ms kept |
| `signals` | 950 ms | 900-1250 ms cold, 25 ms kept |
| warehouse queries per Today | 493 | 173 |
Cold numbers are the first visit after a write; the machine was shared, so cold figures vary by about 30 percent. Cold Today is under 1 s; a repeat visit is about 0.15 s.

## Old vs new audit
Kept, moved: Morning Note headline, tiles with status and Where is this from (Today); What moved (Today); approved delivery sections (Today); Comments on note and Ask Lumen (Today; Lumen also at the foot of the other tabs, as the old side panel); Daily P&L and NAV: issued against known now, liquid book P&L, administrator against our view, by entity (Financial health values and trust; see departures); Fund league (By fund); index mapping sign-off (By fund); Market signals index table, portfolios against benchmarks, short read, manager news, outside links (Markets); Reports library, company reports links, delivered-each-morning (Reports); Shared with you and Dashboards list (Reports); Delivery email and Slack (Operations); Attribution (What if); USD/SGD (switch).
Removed as Nitin decided: Needs you today on Consume, the Dashboards tab, separate Shared and Delivery tabs.

## Departures
1. P&L is shown per portfolio, month only. The "issued against known now" table and the administrator-against-our-view table are not on Financial health (their numbers repeat Today and the report); they remain on the CIO Brief and the `pnl` endpoint is unchanged. Say if you want them back as a fold-out.
2. Markets keeps a third period, Since inception, and the currency switch next to the period switch (the artboard shows the period switch only; the brief asks for currency on Markets).
3. The per-period "each fund against its index" table is replaced by By fund (month league). Fund returns were "Not available yet" in it anyway.
4. Rows for the Direction column, and the "Values" status column in Ours against it (status shown under the portfolio name) were folded in.
5. Tile status pills (for example "Stale" on NAV, from the Cedarpoint value dated 31 Mar) are kept; the artboard has none. NAV 103.41M matches the artboard.
6. vs bench on Financial health shows each portfolio's first benchmark (private markets proxy for the funds portfolios, where the artboard shows a dash).
7. Headline wording is built from the figures: "The liquid book rose ..." (the artboard says the office rose, which the data cannot support).
8. Delivery component: the Operations page already existed, so Deliveries is mounted there; Operations is data-team only (analyst), as before.
9. Fixture `k10.fixture.json` gained `today` and `health` and refreshed `signals`/`library`; the old `note`, `pnl`, `league`, `email` keys are untouched.
