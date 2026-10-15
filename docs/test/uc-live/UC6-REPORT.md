# UC6 report: Can we meet the capital calls? (run 3, 13 Oct 2026)

Run 2 (blocked at July intake) is in git history (commit d0b56a5). This is run 3, after the overnight fixes FIXA to FIXE2. Steps: `UC6-RUNBOOK.md`. Evidence: `uc6-run3-shots/`, `uc6-scripts/run3-calls.jsonl`.

## 1. Verdict

**Both months completed, with four workarounds.** July and August 2026 went from North, signature, hand-over, Span's pack, approval, intake, run on a copy, go live, Lumen, Action and Consume. The intake blockers of run 2 are gone: the money columns load, ISO dates work, fund approval is a step, the counts are honest, and August loaded with the July mappings and no edits. Cash by entity matches the answer key to the cent in both months.

It is **not yet a product a family office could run unattended**, for three reasons. Span's drafted gold does not run (the generated SQL is refused by the product's own guard, and is wrong even where it parses), so a data engineer has to rewrite it. Confirming the one late notice moves "still to be called" for Entity B from 8.9m to 13.1m (key: 8.9m). And Action raises a "Fund the capital call" case for a call that was paid on 23 Jul.

- Clean environment: `D:/Temp/uc6-sit` (company, seven people, master data, core model; no commitments, no cases, no cash). Own server on 8811, Testing mode. Server stopped and `D:/Temp/uc6-sit` deleted at the end. Ports 8530, 8812, 8400, 8504, 8200 and the repo `data/` were not touched. No product code was edited. Scripts were edited (`uc6.py` paths from env vars, `make_clean_env.py --no-commitments`, ids in `m1_04` to `m1_06`).
- Model spend: **USD 0.012** (33 calls: gpt-oss-120b 21, qwen3.7-flash 12; North, Span, Lumen) from the company's `model_costs.jsonl`.
- Time: about 35 minutes of wall time, clock 05:51 to 06:26.

## 2. Month table

| Step | July (cycle 31 Jul) | August (cycle 31 Aug) |
|---|---|---|
| North, Mei | 13 typed messages; intent `ini-097ec18a7f77bc6be9cdf63cf23c8aeb`; result and success filled by North (FIXD works); process map only on the second ask; 7 KPIs | none |
| Sign, Daniel | signed v1, 200 | none |
| Hand-over | Mei herself handed project `prj-a4d01dff` to Leo, due 7 Aug accepted (FIXE1, FIXE2) | none |
| Span pack | v1 drafted, 13 open rows, approved by Anita (plan v1 approved with it); gold rewritten by Leo as v2 (failed, my SQL used the DuckDB keyword `asof`) and v3 (ok) | none |
| Intake | 6 files: 4 loaded, commitments loaded after the 5 fund approvals, receipt log "no data rows" | 6 files: 5 loaded with the remembered mapping, receipt log quarantined (see M5) |
| Run on a copy | `run-20261012-221605-9eda` failed (pack 1), `run-20261012-221711-c668` failed (pack 2), `run-20261012-221809-3b50` ok (pack 3, 11 of 11 checks) | `run-20261012-222308-449c` ok |
| Go live | `run-20261012-221910-38a8` PRODUCTION ok (variance accepted) | `run-20261012-222316-8a22` PRODUCTION ok |
| Lumen | starter `dash-ba87e21f`, 6 tiles, submitted by Leo, approved by Anita | tiles re-read on the August gold |
| Action | not opened in July | 1 case: Fund the capital call, Cedarpoint Opportunities II, 23 Jul, 300,000 (already paid). Raj took it, Mei dismissed it as paid, list empty after |
| Consume | not captured in July (cycle moved before) | Office as Raj and Daniel |

Intake load runs (`intake_load`, listed PRODUCTION in Operations > Runs): July `run-20261012-221416-9f94`, `-221417-11fa`, `-221417-c5f5`, `-221418-ed78`, `-221430-01bb` ok; failed attempts `-221233-8fd5`, `-221244-d2b8`, `-221310-ac7b`, `-221320-4fa3`, `-221336-3d31`, `-221340-6989`, `-221418-6d46`, `-221418-9bd8` (before mappings were approved or funds were approved). August `-222158-7097`, `-222158-7905`, `-222159-5b3f`, `-222159-5bbe`, `-222200-6c3d` ok; `-222200-0472`, `-222213-b210`, `-222220-9f7e` failed (the receipt log). Run times show the real day (12 Oct, UTC), not the cycle date.

## 3. Gold against the answer key

Path K = Consume > Office liquidity as the screen calls it (`/api/v1/office/liquidity`). Path P = the project's gold table, read through Lumen's tiles on the live run.

| Figure | Key July | Run July | Key August | Run August |
|---|---|---|---|---|
| Cash EG-HOLD (K) | 2,305,906.48 | 2,305,906.48 match | 2,287,630.12 | 2,287,630.12 match |
| Cash EG-TRUST (K) | 1,252,492.34 | 1,252,492.34 match | 1,199,690.58 | 1,199,690.58 match |
| Cash EG-B (K) | 905,000.00 | 905,000.00 match | 654,014.07 | 654,014.07 match |
| Cash, three entities total (P) | 4,463,398.82 | 4,463,398.82 match | 4,141,334.77 | 4,141,334.77 match |
| Calls due in 30 days (K and P) | none | 0 match | none | 0 match |
| Calls 31 to 60 days (K and P) | none | 0 match | none | 0 match |
| Shortfall | none | none match | none | none match |
| Uncalled, total (K) | 13,450,000 | 13,450,000 match (EG-B 8,900,000, EG-HOLD 4,550,000) | 13,450,000 | **EG-B 13,100,000, total 17,650,000: wrong** after the late notice is confirmed; 13,450,000 before |
| Notices not confirmed | 0 | 0 match | 0 | 0 match |

Not verified: per-entity split of cash in the gold table (Path P gives the total only; Lumen's proposed tile "Available cash by entity" could not be accepted, 404), and per-fund uncalled (the Office shows the entity total only).

## 4. What Action showed and what was done

July: not opened. August: after Leo confirmed the extracted amount of the 6 Jul notice, one case appeared for Mei, Raj, Leo and Anita alike: "Fund the capital call, Cedarpoint Opportunities II, Entity B, 2026-07-23, CASE-0001, USD 300,000, nobody has taken it yet", due 23 Jul. The key says this call was paid on 23 Jul and is not open (UC6-02). Raj took it. His dismiss was refused ("a material case is dismissed by another person than its owner and maker"). Mei dismissed it with "Already paid on 23 Jul from Entity B (PAY-20260723-B01). The notice reached us late, on 12 Aug." Mei's Action then read "Nothing needs you today". The 12,400 timing break, the Saltmarsh and Fund-from-Entity-B cases belong to September and October and were not in scope. The 14 Aug sweep (UC6-03) raised nothing, as expected. The 23 Jul payment with no notice (UC6-01) raised no "unmatched outflow" in July: nothing flagged it. Anita's Action shows "13 new items from finished projects stay off the signed map until you approve them" (Map review), not looked at.

## 5. Issues

| ID | Severity | What | Evidence |
|---|---|---|---|
| H1 | High | Span's drafted gold is unusable. The model design failed ("Expected END after CASE. Line 6, Col: 188", pack note), the rules fallback wrote SQL with `movement_type = 'call'`, and the run on a copy fails: "The SQL may only create or add rows; it contains something else." (`b6_run._BAD` matches the word `call`). Even if it ran: "calls due 30 days" and "31 to 60 days" are the same expression, available cash is the sum of bank movements, "noticed AND confirmed" is a contradiction, no as-at window. `commitments` is not reused (the KPI "Uncalled commitment by fund" says no table holds its records), so FIXC's "reuses commitments" does not hold on the rules path. | `run-20261012-221605-9eda`; pack v1 gold SQL in `uc6-scripts/run3-calls.jsonl` (pack/generate); `m1_pack_v1.json` was in `D:/Temp/uc6r3` (deleted). Workaround: Leo rewrote the select (pack v3). |
| H2 | High | Confirming one late notice changes uncalled commitment for Entity B from 8,900,000 to 13,100,000 (+4,200,000). Called-to-date seems to switch from the opening balance to "confirmed notices only", dropping the 4.5m already called on the fund. | `liq.py 2026-08-31` before and after `POST /api/v1/evidence/fields/{id}/confirm`; Office screen "Still to be called USD 13,100,000" (`aug-11-raj-consume-office.png`). Key: 13,450,000 in August. |
| H3 | High (workflow) | North drafts each figure as a "source": four figures plus "Administrator closing cash" become ten systems. The builder then refuses to run ("No sample file has arrived for this source yet") for the five phantom sources and for the notices source in a month with no notice. No screen removes a system. Uploading the same real file answers `duplicate`. | builder thread of 12 Oct 22:14:50; `r3_samples2.py`. Workaround R3-W1. |
| M4 | Medium | North: the process map was not drafted until the second explicit ask, although the turn before said it had "added ... process hand-overs" (the claim guard missed it); a raw JSON block (`{"reply": ...`) was shown as North's text in turn 9; the access/result question was asked in turns 1, 2, 5 and 6 despite being answered later; only K01 and K02 were drafted from the first figure list; hand-overs between steps are empty. FIXD's result/success fill works. | `m1_north_turns`, turns 8 to 11 in `run3-calls.jsonl` (GET intents/{iid}/chat). |
| M5 | Medium | Proposed mappings. (a) "Estimate amount" (the manager estimate, UC6-05) is proposed as `commitments.commitment_amount`; Leo must set it to ignore. (b) HOLD and TRUST bank files have no portfolio mapped (account number ignored). (c) The receipt log has no portfolio and its `notice_date` is ignored, so every row is held ("no portfolio in the row") and with a fixed portfolio the write fails on `cash_movements.effective_date NOT NULL`; the log never loads (two attempts, stopped). | `r3_maps.py` output; August load of `notice_receipt_log.csv`. |
| M6 | Medium | The builder's benchmark compare ignores the entity in a label: three correct entity cash figures read as "3 unexplained variances" (each compared with the total of all entities, 4,463,398.82). The only way on is "go live anyway". | Variance block of the builder, 22:18:49. |
| M7 | Medium | Action raises "Fund the capital call" for a call whose due date (23 Jul) is past and was paid. It lists a past-due call as a thing to fund. The 23 Jul payment with no notice was never flagged in July (UC6-01). | Action shots `aug-09-*`. |
| M8 | Medium | Pack open rows ask for decisions that come later: five "Map this sample to the model" rows are settled before any mapping exists (intake comes after the pack). Leo cleared 13 rows with a free-text note each; the screen accepts any text. | `r3_m1_07_approve.py`; `jul-07-*` shots. |
| L9 | Low | Permissions the plan assumed: Mei cannot confirm extracted PDF fields (403, data team only) nor start the Lumen starter (403). Raj cannot dismiss the case he took. Leo or Anita did. | calls log. |
| L10 | Low | Clock: run times in Operations > Runs and the Evidence "received" date follow the real day or the UTC edge (the 12 Oct runs; an upload on cycle 31 Jul is "received 1 Aug"), while intake, hand-over and Action follow the cycle date. Intake loads show as PRODUCTION while the company is in Testing mode, and the retries show as 11 failed runs. | Operations > Runs list. |
| L11 | Low | Lumen: asked for "available cash by entity", it proposed tile `t-3ff60c`, but `tiles/{id}/accept` and `.../data` answer 404 "There is no such tile". The first ask returned a recap of the chat instead of a tile. | calls log, 06:2x. |
| L12 | Low | The gold table keeps only the latest month in my rewritten select (max date); a month-by-month history needs a different design. Gold rewriting also had to avoid `asof` (a DuckDB join keyword) and the word `call`. | pack v2 failure `run-20261012-221711-c668`. |
| L13 | Info | Mapping edits in this run were made by the API call the file page uses; the editable state of the page was not driven or photographed (`jul-06-leo-intake-commitments-file-page.png` shows the read-only loaded state, which is clear and honest). Hand-over, send-to-build and sign were done by the UI's API, sign page and Action shots were taken. | |

## 6. What the fixes did (checked)

FIXA: B1 500 gone; ISO date format on proposals; closing cash, net movement, commitments mapped; "Loaded 93 of 93 rows", "Rows written" control total, `nothing_loaded` state; fund approval button path; the July mapping reused for August. FIXC: pack approval also approves the plan; gold is drafted on the use case's own tables with "Silver reused" (but see H1). FIXD: result and success are filled; duplicate KPIs avoided. FIXE1: Mei hands over. FIXE2: cycle date on screen and API, hand-over due date accepted, intake `received_at` follows it.

## 7. Honest opinion

The plumbing from intake to a live run now works, and the cash numbers the CFO cares about are right in both months, so run 2's blocker is truly fixed. What a customer would feel next is the gap between "Span drafts the design" and "the design runs". The gold SQL is the product's own highest-value artefact and it is refused by the product's own guard; a person has to write SQL, which the whole flow is meant to avoid. The second customer-visible problem is a wrong number: the moment the office confirms its first notice, uncalled commitment jumps by 4.2 million, and a reader like Raj would not know. Third, the North step still invents "sources" out of figures, and the builder punishes that. I would fix H1 (including the `call` guard word), H2 and H3 before any demo, and treat the receipt log and the benchmark compare as the next tier. The Action, Lumen and cycle-date pieces are good; the Action list is quiet and plain, which is right, but it must not ask someone to fund a call that was paid in July.
