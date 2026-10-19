# Top-2 use cases: visual tour (office 8780, run 18 Oct 2026)

Office: http://127.0.0.1:8780, data D:/Temp/sh3-check. Run by the persona runner (v3_persona.py --uc) as Sam Lee and Helen Foo, then screenshots as Daniel Foo. Pages taller than 2,500 px are cropped to their top 2,500 px.

## Use case results

**uc-001-noticelog (Sam Lee, log an incoming capital call notice): PASS.** Check: "A Cedarpoint call notice just came in by email. Which fund, how much and by when?" (expected 1,250,000 / 900,000 / 350,000 / 4471). Final answer, verbatim:
> Cedarpoint Ventures III call 7: USD 1,250,000 (900,000 for investments, 350,000 fee) due 23 Oct 2026, to the account ending 4471. Not paid yet: Cedarpoint Ventures III USD 1,250,000. 10 earlier calls are paid, 5,950,000 in all.

**uc-002-callrecord (Helen Foo, record a capital call against the commitment): PASS.** Check: "Does call 7 fit what we committed to Cedarpoint Ventures III, and what is left after it?" (expected 10,000,000 / 6,000,000 / 7,250,000 / 2,750,000). Final answer, verbatim:
> The 1,250,000 call fits Cedarpoint Ventures III: 6,000,000 called of 10,000,000 committed, 7,250,000 after it, leaving 2,750,000 unfunded.

At Decision 2 Helen's brief shows "Already in the office" on the custodian positions, bank balances, private-fund portal and call notice PDF rows (the uc-001 notice).

## Screenshots

Use case 1 (Sam Lee, thread t-a01e32a57c)
- 1-01-drafting.png: thread while Harbor drafts the extraction spec
- 1-02-decision1.png: Decision 1, the brief with its open gaps
- 1-03-working.png: working stage after the usual practice was confirmed (extra, not in the brief)
- 1-04-decision2.png: Decision 2, assumed answers and the custodian/administrator check question
- 1-05-live.png: thread once live (Decision 3 passed in under 10 s and was not caught by the watcher)

Use case 2 (Helen Foo, thread t-65f8cbb2fb)
- 2-01-drafting.png: thread while drafting
- 2-02-decision1.png: Decision 1
- 2-03-working.png: working stage (extra)
- 2-04-decision2.png: Decision 2, showing "Already in the office" reads from the uc-001 notice
- 2-05-live.png: thread once live

Daniel Foo, desktop 1440
- 3-01-home.png: Home (/v3/desk)
- 3-02-action.png: Action
- 3-03-build.png: Build
- 3-04-thread-uc001.png: thread for uc-001 (Sam's thread, viewed as Daniel)
- 3-05-thread-uc002.png: thread for uc-002 (Helen's thread, viewed as Daniel)
- 3-06-consume-start.png: Consume before any question
- 3-07-uc001-answer.png: Consume answer to uc-001's check question (see issues: it shows the uc-002 fit sentence)
- 3-07-uc001-figures.png: the same answer with Show the figures open
- 3-09-uc002-answer.png: Consume answer to uc-002's check question
- 3-09-uc002-figures.png: the same answer with Show the figures open
- 3-11-knowledge-atlas.png: Knowledge, Atlas
- 3-12-knowledge-expanded.png: Atlas after Expand map
- 3-12b-knowledge-list.png: Knowledge, List view (figure dots are not clickable on the Atlas canvas, so the figures were opened from List)
- 3-13b-knowledge-figure-panel-list.png: side panel after clicking the Net worth row ("Tap a dot" panel, with Open full page)
- 3-14-thing-full-page.png: full page via Open full page (/v3/knowledge/thing/recipe:net_worth, a recipe thing)
- 3-15-figures.png: Knowledge > Figures
- 3-16-figure-page.png: one figure page (/v3/knowledge/figures/fig-net-worth)
- 3-17-watches-for.png: Knowledge > What Harbor watches for (cropped)
- 3-18-skills.png: Knowledge > Skills Harbor uses
- 3-19-knowledge-for-trust.png: Knowledge page as the starting point for the trust tabs
- 3-20-runs-and-proof.png: Runs and proof
- 3-21-people.png: People (cropped)

Phone width 390
- 4-01-home-390.png: Home at 390 px (cropped)
- 4-02-consume-390.png: Consume at 390 px before a question
- 4-02-answer-390.png: Consume answer at 390 px (Q2 check question)

Not part of this set: team-*.png files written by the persona runner (team-ops_clerk-*, team-fund_accountant-*).

## Issues seen

1. Consume answer to uc-001's question does not give the uc-001 result. Daniel's Ask for "A Cedarpoint call notice just came in by email. Which fund, how much and by when?" returned the uc-002 fit sentence (1,250,000 / 6,000,000 / 7,250,000 / 2,750,000). The due date, the fee split and the account ending 4471 were missing. The API check for uc-001 passed earlier with the correct answer, so the Consume Ask path and the thread answer disagree.
2. The Consume answer headline reads "commitment 10,000,000", which is not a clear label for the answer.
3. Atlas figure dots are drawn on a canvas and cannot be clicked from the DOM; the figure panel was reached from the List view instead.
4. Decision 3 of uc-001 was not captured by the watcher (the stage passed in under 10 s).
5. Helen's run hit repeated ECONNRESET poll errors during working (about 11 min); it recovered and the check passed. The 8780 server stayed up throughout.
