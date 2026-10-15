# Signal Harbor MVP plan (7 Oct 2026)

Goal: one company (the synthetic family office) can walk the whole journey in the product: say what it wants to know, get its data built, and see the numbers. Build first, then test. Security and full test suites come after the MVP.

## How each feature is built
1. One builder agent per feature, several at once, each in its own copy of the repo.
2. The builder finds existing code first (graft, the earlier repo) and copies it; small code only (Ponytail rules).
3. The builder writes 2 to 4 tests for its own feature only.
4. I land it, open the screen, click through it once as a user would, and tell you it is ready.
5. No full test suite and no security review until the MVP is complete.

## Centre 1: Intent (decide what the business wants to know). Built.
| # | Feature | Who uses it, and how | State |
|---|---|---|---|
| 1.1 | Sign in, home | Everyone signs in and lands on the Intent centre | Done |
| 1.2 | Bring what you have | Company admin uploads documents; the profile fills itself | Done |
| 1.3 | The wall | Organiser starts a wall (topic, purpose, days); people write cards with North in their private room | Done |
| 1.4 | Define | Organiser puts card clusters on Must/Should/Good to have/Future; Lens shows the definitions | Done |
| 1.5 | Moment of truth | Ask for sample data, upload it, compare with reported figures, sign the plan | Done |
| 1.6 | Outcomes and company graph | Sponsor sees progress numbers and who owns what | Outcomes done; graph built, to commit |

Left for Intent: commit the graph (step 0) and one click-through of the whole centre.

## Centre 2: Build (turn the signed plan into working data)
| # | Feature | Who uses it, and how | State | Agents |
|---|---|---|---|---|
| 2.1 | Environment check | Company admin confirms five answers: where data lives, how files arrive | Done | 0 |
| 2.2 | Blueprint | The Architect agent drafts the data model from the signed catalogue; head of data reviews and signs | To build | 1 |
| 2.3 | Load the data | A pipeline per source loads landed files into the warehouse; a "Run now" button and a run log | Warehouse core done; pipelines and screen to build | 1 |
| 2.4 | Prove and release | Each measure is recomputed and compared with the reported figure; the sponsor signs the release | To build | 1 |
| 2.5 | Ops | One screen: what loaded today, what is late or failed, who must act | To build | 1 |

Left out of the MVP: scanning an existing warehouse, Airflow, Slack/Teams messages.

## Centre 3: Consume (use the numbers). Not started; a one-page spec first.
| # | Feature | Who uses it, and how | State | Agents |
|---|---|---|---|---|
| 3.1 | Feeds | Owners and sponsor see each governed measure with its latest value and trend | To build | 1 |
| 3.2 | Market forces | Industry briefs and market signals shown beside the company's own measures | To build (copy from the earlier repo) | 1 |
| 3.3 | What-if | Change one driver and see which measures move | To build | 1 |

## Order of work
| Step | What | Agents in parallel | Estimate |
|---|---|---|---|
| 0 | Commit the company graph; write the one-page Consume spec | 0 (me) | 30 min |
| Wave 1 | 2.2 Blueprint, 2.3 Load the data, 3.1 Feeds, 3.2 Market forces | 4 | about 2 hours with landing |
| Wave 2 | 2.4 Prove and release, 2.5 Ops, 3.3 What-if | 3 | about 2 hours with landing |
| Wave 3 | Full journey on the demo company, start to finish; fix what breaks | 0 to 2 | about 2 hours |
| After MVP | Full test suite, security review, Slack/Teams, Airflow, warehouse scan | later | later |

Total to MVP: about 6 to 7 hours of work. These are estimates; I will report against them after each wave.

## What you get after each wave
One message: the features that landed, the screen address, which account to use, and three or four things to click.
