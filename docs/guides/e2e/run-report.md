# Lakeside end-to-end run, modules 1 and 2

Run on 4 October 2026 against the live dev app (backend :8200, UI :8201, live Gemini). Company: Illustrative Lakeside Family Office (synthetic). Driven with Playwright (Chrome) for screens and plain HTTP for a few bulk or setup steps. Passwords were read inside the scripts from the seed file and were never printed or saved. No code was edited. Output files are only in this folder.

Session used: "Client walkthrough (illustrative)", 4 seats: Mei Tan (organiser, head of data), Arjun Rao (sponsor), Wei Chen (participant), Daniel Kerr (guest by link, no account). Names rule: "each person chooses".

Note on leftovers: my first attempt at this session (id starts 780f8de5) was abandoned in the "rooms open" stage because the guest lost the seat (see D6). It has the same title and cannot be deleted from the UI. The run documented here is the second session (id starts 19ad7bfc).

## Result: 22 steps. 16 PASS, 4 PASS with a workaround, 2 FAIL

| # | Step | Result | Evidence |
|---|---|---|---|
| 1 | Prepare a new session, names rule, 4 seats, approver | PASS (workaround) | Screens 02, 03. The Prepare screen is dead without a workaround (D1). I answered the failing `/templates` call with an empty list inside the browser only. |
| 2 | Start the room, join: 3 seeded accounts and 1 guest by link | PASS (workaround) | Screens 04, 05. The guest seat is tied to one browser tab (D6), so the first run was redone and the tab's session storage was saved between scripts. |
| 3 | Briefing and video slot | PASS | Screen 06. The video is "added later" per the wizard, so I posted `module-1-demo.mp4` with the existing m1 helper approach (PUT briefing/video, returned 200). It plays in the slot (2:17). |
| 4 | Private rooms: 2 to 3 real North turns each, four kinds of note, prefill once | PASS | Screens 07 to 10. 9 North turns; notes: intent, pain point, future signal, lever, one anonymous, one from the industry-problem prefill. 7 notes in, matching 2+2+2+1. |
| 5 | Close the rooms, board grouping by North | PASS | Screens 11, 12. North grouped 2 of 7 notes and left 5 alone; the organiser made the other groups by hand. |
| 6 | Back in the room: vote, tick, finish | PASS | Screen 13. The button read "Finish and go to the charter", not "We're done, go to the charter" (D9). |
| 7 | Confirm the "So that" lines | PASS | Screen 14. |
| 8 | Sign: organiser then sponsor | PASS | Screen 15. 2 of 2 signed; sponsor signed in a separate browser sign-in. |
| 9 | Open the Summary page | FAIL | Evidence file `defect-m1-summary-error.png`. The API answers 404 (D2). |
| 10 | Charter download | PASS | HTML 1,536 bytes and Markdown 781 bytes downloaded; the Markdown reads correctly. |
| 11 | Start the baseline from the charter | PASS | Screen 16. Note D8: the charter list says 2 problems; M1 said 3. |
| 12 | Suggestions, confirm 4 measures | PASS | Screen 16. |
| 13 | Lens drafts | PASS | Screen 17. Definitions drafted by Lens with the documents it read, marked as guesses (D5 for the two oddities). |
| 14 | Owners | PASS | Screen 18. First measure by clicking; the others through the API for speed. |
| 15 | Governance | FAIL | The per-measure personal-data setting works (screen 18). The Governance tab fails with a 404 (D2). Evidence `defect-m2-governance-error.png`. |
| 16 | Requests to owners | PASS | Screens 19, 21. 6 requests made, links shown once and masked in the screens. |
| 17 | Answer two requests by link (Sara Lim, Lina Ho) | PASS (workaround) | Screen 20. The form cannot submit process steps (D3). I stripped the rejected field in transit in the browser. |
| 18 | Answer one by meeting (Tom Ng, also Mei, Arjun, Wei) | PASS | Screen 22. Marked "given in a meeting". |
| 19 | Process map | PASS | Screen 23. |
| 20 | Catalogue | PASS | Screen 24. 5 sources from the answers; one flagged "personal data: not decided yet". |
| 21 | Review and sign-off: sponsor, then head of data | PASS (workaround) | Screens 25, 26. Two owners could not confirm their part at all (D4); I re-nominated them. |
| 22 | Hand-off | PASS | Screen 26 says "Handed on to module 3" and the checklist reads "Ready for module 3". There is no separate hand-off screen or file. |

## Timings

| What | Time |
|---|---|
| North replies (9 turns) | 4.6, 5.4, 5.4, 5.8, 8.1, 9.6, 10.0, 11.9, 13.1 s. Median 8.1 s. |
| Close the rooms | 4.6 s to the board |
| North grouping | about 6.5 s after closing |
| Lens drafts, 4 pack measures (first click) | the button came back in 4 s with nothing visibly changed |
| Lens drafts, all 5 measures (second click, one custom measure added) | 83 s |
| Process map draw | 31 s |
| Catalogue fill | 1 s |
| Owner questionnaire submit (4 measures, via UI) | about 14 s |
| Meeting answers, 2 measures | 87 s of scripted typing, not a system time |

## Workarounds (all disclosed)

1. Prepare screen: browser-side stub for the failing `/templates` call so the wizard could render (D1). Saved sessions were real.
2. Guest: kept the guest's tab session storage between scripts (D6).
3. Owner questionnaire: stripped the `manual` and empty `step` fields from upstream and downstream steps in transit (D3).
4. Sign-off: moved the process owner of two measures from Tom Ng to Sara Lim and the business owner of one measure from Wei Chen to Mei Tan, because Tom, Wei and an account-holding owner cannot confirm (D4).
5. A browser sign-in was needed again mid-run (session ended after about an hour). Not treated as a defect.
6. Owners by API: measure owners 2 to 5 and their governance were set through the API after doing the first through the UI.

## Defects

| ID | Screen | What happened | What I expected |
|---|---|---|---|
| D1 | Intent Centre, Prepare a session | The page shows "Something went wrong" and cannot be used. `GET /api/modules/m1_intent/templates` returns 500 "records could not be read". Cause found: the saved template "Check 123" (4 Oct 04:51) lacks the newer `names` setting, and the reader rejects the whole list. | An old template should be read or skipped, not take the whole wizard down. |
| D2 | M1 Summary page, M2 Governance tab, Lens and Nira side panels | `GET .../sessions/<id>/summary` and `.../baselines/<id>/governance` return 404 "Not Found", and the side panels get 404 and 405 on `/lens` and `/nira`. The backend process on :8200 started at 07:41 and these routes were added at 07:46 to 09:49. The server needs a restart. I did not restart it. | A working Summary page and Governance tab. |
| D3 | M2 owner answer page by link and in a meeting | Submitting any upstream or downstream step fails with "“manual” is not something a step can say" (once per measure), and "Send my answers" then says to answer at least one question per measure. The form sends `manual: false` on every step; the server accepts it only on the in-between step. | An owner can send their answers without a workaround. This blocks the main path for every owner. |
| D4 | M2 Sign-off | Owners cannot confirm their part if their sign-in role is approver or participant (the sign-off data call returns 403), and an owner with an account does not get the "Confirm my part" buttons on their link. Sign-off needs every owner to confirm, so the baseline cannot be signed. | Every nominated owner has some way to confirm, or the owner picker only offers people who can. |
| D5 | M2 Work list, Lens | (a) Pressing "Ask Lens to draft definitions" the first time returned in 4 s with no visible change; the real draft took 83 s on the next press. (b) At the end of that draft a message said "Lens could not reach the model just now; these are the pack's suggestions" although the drafts were by Lens. (c) The Lens side panel said "I filled a definition for 9 of 9. I am still drafting 9" and "drafting 3 of 9". (d) The suggestion "Compensation inputs reconciled" (pay) is offered under the problem "Numbers we cannot trust". | One clear progress state and one clear result. A pay measure should not show on a funding or reporting problem. |
| D6 | M1 guest join | The guest's seat token lives in the browser tab's session storage only. Closing the tab loses the seat: the link then says "All seats are taken", and the organiser has no control to release a seat. | A guest can return, or the organiser can free the seat. |
| D7 | Seeded accounts | The live accounts do not match `tools/seed.py`: the "owner" account is named Lena Kerr and "Sara Lim" is the analyst account; the seed file says owner is Sara Lim and analyst is Priya Nair. | Live data matches the seed (the seed note says Lena Kerr is gone). |
| D8 | M1 to M2 | M1 says "What goes to module 2: 3 problems". The M2 start list says "Funding and capital calls and 1 more, 2 problems". The pain-point problem was dropped without a word. | The same count, or a line saying why one was left out. |
| D9 | M1 Together, charter | (a) When all problems are decided the button reads "Finish and go to the charter", not "We're done, go to the charter". (b) Ticking "In the charter" shows no change until a reload. (c) The drafted "So that" line for "Late report delivery" is about stale totals ("the total we show the family is not stale"), not late reports. (d) The text "0 of 3 are done" stays next to "3 in the charter". | Consistent labels and immediate feedback. |
| D10 | M2 Sign-off | After a signature the page keeps showing "Not signed yet" and an enabled button for several seconds. It updates on reload. | The page shows the signature straight away. |
| D11 | M2 Requests | The email text uses `http://127.0.0.1:8200/answer/...`, the API host, while the link above it uses the UI address (:8201). The 8200 link opens a page that stays on "Loading...". | Both links work and match. |
| D12 | M1 board | In the grouped view the right-hand group is cut off at the edge (the "Split" button is clipped). | No clipping at 1600 px. |
| D13 | M2 Catalogue | Clicking "Download the spreadsheet" in a headless browser produced no download. The export itself works (the API returned a 93 KB xlsx). Not verified in a normal browser. | A download starts. |
| D14 | Logged-out pages | The browser console shows a 401 on `/api/auth/me` on every logged-out page (join and answer pages included). | No error noise on pages that need no sign-in. |

## Screens

Screens 01 to 26 are in this folder in order. `captions.json` lists title, caption and step for each. Two further files, `defect-m1-summary-error.png` and `defect-m2-governance-error.png`, are evidence of D2 and are not for the client. Screen 04 was taken after the session closed, so it shows the closed state of the room page. Join and answer links are masked in every screen; no password, token or real person's data is shown.
