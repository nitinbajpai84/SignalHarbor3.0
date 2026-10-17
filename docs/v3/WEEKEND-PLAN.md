# Weekend plan: top 50 use cases, 6 months of data, the signal engine (17 to 19 Oct)

## The moat, in one sentence
The moat is a library of family-office **signals**. Each signal is declared once (what arrives → what Harbor catches → who acts and how little) and is verified against real answer keys. Each is built from **figures that carry receipts** and is checked by **two different models**. It runs on every file and every day. Every office makes it sharper: which signals fire, which get acted on, which get dismissed. Nobody else ships verified, routed, receipted signals, and the name of the product is the promise.

## How the team is organised (about 80 to 100 agent runs over the weekend)
Two limits shape the plan:
- **Parallel code.** Agents can work in parallel only where they don't edit the same file. Each builder therefore owns one domain file, or works in its own worktree.
- **Parallel live runs.** This machine has 16 GB of memory and 20 cores, so it runs at most about 8 live persona servers at once. Live runs go in waves of 8.

| Wave | Who | What | Depends on |
|---|---|---|---|
| 0 (running) | 1 | 100 use cases, top 50 ranked by pain point (done) | — |
| 0 (running) | 1 | 6 months of synthetic office data with computed answer keys | catalogue |
| 0 (running) | 1 | Signal engine (the moat), its own branch | — |
| 0 (running) | 1 | Model steward: decides all 86 new needs once, splits recipes per domain | catalogue |
| 0 (running) | 1 | UI button click-test (Nitin's Confirm and Change report) | — |
| 0 (running) | 1 | Use case 1 video | — |
| 1 | 7 builders + 7 verifiers | One per domain. Each fills its recipes, writes its signals, and turns its use cases into runnable persona builds. A verifier tries to break each builder's work against the answer keys. | steward, data |
| 2 | 2 | UI for signals: the fired-signal card in Action, Knowledge > Signals | signal engine |
| 3 | servers in waves of 8 | Run the top 50 on the 6-month data. Track correct answers, questions asked, time, cost and reuse. | wave 1 |
| 4 | about 10 fixers | One fixer per failure cluster. A cluster is all failures with the same root cause, so one fix covers it everywhere. | wave 3 |
| 5 | servers | Re-run the 50. Report the scorecard and the reuse curve. | wave 4 |
| 6 | 2 | Merge, push to Railway, refresh the walkthrough and video | Nitin's go |

Each agent gets its model from Jev. Waiting (test runs, servers) happens in shell commands, not in agents.

## Quality rules for every builder
- The answer key comes from the data, never typed by hand.
- Every new behaviour has a test, and the full v3 suite stays green before any merge.
- No new table without the steward's decision, which is logged in ASSUMPTIONS.md.
- Plain words on screen. Every figure can be traced. "Not available yet" instead of a guess.
