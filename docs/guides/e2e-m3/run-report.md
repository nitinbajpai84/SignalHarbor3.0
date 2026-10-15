# Lakeside module 3 run (Assess and plan)

Run on 4 October 2026 on the live dev app (backend :8200, UI :8201, live Gemini). Company: Illustrative Lakeside Family Office (synthetic). Driven with Playwright (Chrome, 1600x1000) and plain HTTP for a few bulk or inspection steps. Passwords were read inside the scripts from the seed file and never printed or saved. No code was edited. Link tokens are masked in the screens.

## Which assessment, and a mismatch to read first

- A NEW assessment was started: `3fbb7a16...`, from the latest signed baseline (outcome `b4233f15...`, signed in the earlier modules 1-2 walkthrough). The old `7f1d1c1c...` was not used.
- The UI could not start it: the Assess and plan home shows the "start" button only when no assessment exists. I started it with `POST /assessments` as the organiser (workaround). The home screen (01) then lists two rows both reading "Started 10/4/2026", with no way to tell them apart.
- **The live signed baseline does not match the demo answer key.** It holds six measures: K01, K04, K05, K12, K15, K18. The demo measures K09, K10 and K16 were left out of that baseline (listed as "left out" in module 2), and the baseline's sources are named differently (for example K12 is fed by "Bluewater administrator NAV portal", not a custody file). I judged 4 of 7 demo measures present (K04, K12, K15, K18) enough to run, so I did not stop. This is a judgement call, flagged here. K09, K10 and K16 cannot appear in the trial at all.
- File-to-source filing (the asks do not match the demo's source names): performance workbook to Performance workbook (S03); custody positions to Bluewater NAV portal (S02, the only source feeding K12); capital calls JSON to Capital_Call_Tracker.xlsx (S06) through the owner link as Sara Lim's request; exposure workbook to Exposure workbook (S07); index levels to "Manager reports folder" (S09, nearest unused request, there is no index-provider source in this baseline). Benchmark file through the organiser's panel.

## Result: 7 steps. 5 PASS, 2 PASS with a workaround, 0 FAIL

| # | Step | Result | Evidence |
|---|---|---|---|
| 1 | Start a new assessment from the latest signed baseline | PASS (workaround) | 01. Started by API; no start button when one exists (D1). |
| 2 | Source map: scores, zones, one source panel | PASS | 02, 03. 11 sources, all in the two "Ready to scan" zones; none unknown. Dots overlap and labels collide (D6). |
| 3 | Data request: requests, 5 uploads (1 by owner link), benchmark file | PASS | 04 to 07. 11 requests made; 4 files uploaded by the organiser, 1 by owner link (05); benchmark file read: 3 lines matched (K04, K12, K15), 3 unmatched (K09, K10, K16, no measure exists to map them to). |
| 4 | Scan: gaps | PASS (partly as expected) | 08, 09, 10. Custody ends 22 Sep: shown. Index levels end 22 Sep: shown. Asset class empty in 4 rows and fees half empty: shown only as fill percentages (90%, 50%), not in the Gaps list (D8). |
| 5 | Trial: compile, run, analyst checks rules | PASS | 11, 12. Results below. Analyst checked 3 rules (K04, K12, K15). |
| 6 | Findings and risks: sponsor accepts, one sent back and re-checked | PASS (workaround) | 13 to 18. 34 risks. Sponsor sent one back (14, 15); re-running the trial turned it to "re-checked" (17), sponsor accepted it. The 8 risks about the restricted K18 are hidden from the sponsor, so I accepted those as the organiser (API, "accept all remaining"), D9. |
| 7 | Plan: bands, sponsor signs, head of data signs, read-only | PASS | 19 to 25. Signed by Arjun Rao (sponsor) then Mei Tan (head of data). After signing: writes return 409 "signed", the outcome record for module 4 reads 200. |

## Trial results per measure (live app) against the answer key

| Measure | Answer key | Live app shows | Verdict |
|---|---|---|---|
| K04 Known obligations due | matches (2,610,000 SGD) | MATCHES, 2,610,000 SGD vs 2,610,000 SGD; rule from the industry pack ("open and not replaced") | As expected |
| K09 Single-issuer concentration | matches | Not in the baseline, not in the trial. Figure 12.92 % sits unmatched in the benchmark file | Cannot be tested |
| K10 Private-market allocation | matches | Same as K09 (20.86 % unmatched) | Cannot be tested |
| K12 Stale-valuation share | gap, period end | GAP: Lens 21.43 % vs 28.57 %; reason "data ends on 22 Sep, your figure is based on 30 Sep" | As expected |
| K15 Manager performance | gap, fees | GAP: Lens 0.63 % vs 0.67 %; reason mentions empty fees cells, 20 of 40 | As expected (wording says cells were excluded rather than counted as zero) |
| K16 Excess return vs benchmark | cannot be worked out | Not in the baseline, not in the trial | Cannot be tested |
| K18 Compensation inputs | unknown | Organiser sees "cannot be worked out" (no rule could be written); the analyst sees "A restricted measure" | Roughly as expected (unknown); wording differs |
| K01, K05 (not in the key) | n/a | Both "cannot be worked out": no rule could be written (inputs unknown; column not available) | Not in the key |

## Timings

| What | Time |
|---|---|
| Source scoring ("Score again", live model) | 10.1 s |
| Each upload (4 by the organiser) | about 1.6 s |
| Owner-link upload | about 3 s |
| Trial compile (rules written by Lens, live model) | 129.3 s |
| Trial run | 11.5 s (10.5 s on the later re-run) |
| Plan draft ("Draft again") | 12.1 s; the first automatic draft finished inside the 150 s wait, exact time not captured |
| Accept all remaining risks | about 4 s |

## Nira's next-step panel

Captured on every screen. It reads the same on every stage after the map: "Waiting for the owners of Northgate custodian daily file, Managers' statements mailbox, ... to send their files." That includes the plan stage, after sponsor signature, and after both signatures (D3).

## Defects

| ID | Screen | What happened | What I expected |
|---|---|---|---|
| D1 | Assess and plan home | No start button once any assessment exists, so a newer signed baseline cannot be started from the screen. Two rows both read "Started 10/4/2026". | A start button for a newer baseline; rows that can be told apart. |
| D2 | Trial table | Each measure cell carries a long "Lens could not write a rule: ..." sentence, repeated again in the Likely reason column. | One short reason per measure. |
| D3 | Nira panel, all stages from the data request on | Always says it waits for source owners, even after the trial, risks and both signatures. The Data request and Scan steps never reach done because all 11 sources were asked and 6 will never send (and 6 of the 11 feed no measure). The "next" sentence is stuck on the first step not done. | A sentence for the current stage (for example "Waiting for the head of data to sign", then "Signed"). |
| D4 | Trial and findings | The Findings heading sits right under the trial table, which is a fixed-height scrolling box (about 520 px); it looks overlapped, and the last rows of the table are hidden until you scroll inside it. | The table and findings clearly apart. |
| D5 | Findings | "Ready to build: None" although K04 matched. K04 is under Unclear because of module 2 notes. K01 (no rule could be written) is placed in the plan's "Next" band with "is ready because ...". | A matched measure counted as ready; a measure with no rule not called ready. |
| D6 | Source map | All 11 dots land in two tight clusters; labels overlap and a label intercepts the click on another dot. Panel opened only via the list or the keyboard. | Readable, clickable dots. |
| D7 | Findings, risks, plan | Accepted-ambiguity text from module 2 shows raw backticks, asterisks and field ids ("F001 `cash_balance` *is*"), and "(accepted in module 2 by Mei Tan)" repeats on 30+ risks. Plan cards show "Expected date: [date]" as a literal placeholder. | Plain words; a real date field or an empty state. |
| D8 | Scan | The Gaps list does not mention the 4 empty asset classes or the 50 % empty fees; they show only as fill percentages. The profile also says "No match in the catalogue" for nearly every column (the file names do not match the catalogue's field names). The file picker still reads "No file chosen" after an upload. | The scan flags low-fill columns as gaps. |
| D9 | Risks, roles | The sponsor cannot see or decide the 8 risks about the restricted K18, yet they stay "to decide" and block nothing the sponsor can act on; the organiser had to accept them. "Accept all remaining" left 8 undecided with no explanation on screen. Also the analyst does not see K18 in the trial table, the organiser does. | A line saying who decides the restricted ones. |
| D10 | Source map and plan | 14 measures that module 2 explicitly left out, plus sources feeding zero measures, appear in the plan's Later band (16 items) and the map. Now band is empty. | Left-out measures not planned, or marked as out of scope. |
| D11 | Trial and the baseline | The demo measures K09, K10 and K16 are not in the signed baseline, so the demo answer key cannot be reproduced end to end on this data. | The demo company's signed baseline holds the demo measures. |

## Leftovers

Assessment `7f1d1c1c...` was not touched. Assessment `3fbb7a16...` is signed (read-only) and cannot be deleted from the UI. Requests for the 6 other sources are still open with live links; the links were never printed or saved.

## Files

Screens 01 to 25 in this folder, `captions.json`, this report. The `tmp-*.png` working files were deleted. 25 screens (a little over the 18-22 asked) because the risks stage needed five to show send-back and re-check.
