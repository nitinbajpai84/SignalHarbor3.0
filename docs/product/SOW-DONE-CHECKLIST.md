# What an intent of work must hold before North says "done" (8 October 2026)

North talks business, never technology. Each item below is what the architect needs to build without coming back with questions. For every item North has three ways to fill it, in this order: **read** it from the company page, the documents or the files; **ask** the person, one question at a time; **default** it, said out loud ("I'll assume monthly unless you say otherwise") and marked *assumed* in the statement so the head of data sees it. An item North can neither read, nor get answered, nor sensibly default becomes an **unclear** line with who can settle it. North is done when every *required* item is filled or unclear, the person has seen the statement and the process map, and the person agrees.

| # | Item | Required | What the architect needs it for | Read from | Ask (in the person's words) | Default if unknown |
|---|---|---|---|---|---|---|
| 1 | **Intent in one line** and why it matters now | yes | The title of the work and the test of every later decision | the first message | "What do you want to build, and what will it change?" | none |
| 2 | **Who reads the result and what decision they take** | yes | Which views and sign-offs to design; who is a reader, who approves | committee minutes, reporting policy | "Who reads it, and what do they decide from it?" | the person who asked, deciding alone |
| 3 | **When it is needed and how often it runs** | yes | Schedule, service level, late alerts | month-end process note, reporting policy | "By when each month, and how often after that?" | monthly, by the eighth working day |
| 4 | **How it is produced today**: steps, who, which system or file, hand-overs, manual steps, time taken | yes | The process map: what to automate, what to keep, where the risk sits | process notes, procedures, minutes | "Walk me through how it is done today" (then confirms the map) | none; if the person cannot describe it, mark unclear |
| 5 | **The result**: what it looks like (a pack, a page, a feed), sections or figures on it | yes | The report tables and screens to design | a past pack, a cover note | "What should the end result look like? Show me one if you have it" | a monthly page with one card per KPI |
| 6 | **The KPIs**: name and how each is worked out today, in business words | yes | The gold tables, one per KPI | investment policy, glossary, data dictionary | "Which figures must it show, and how do you work each out today?" | the industry's usual KPIs, marked *suggested*, each left unclear until confirmed |
| 7 | **Sources**: every file, system or feed that feeds the result, who owns it, how it arrives | yes | The landing layer, contracts, arrival checks | systems inventory, onboarding checklists, the landing folders themselves | "Where does the data come from? Drop a sample of each" | none; a KPI with no source is marked not buildable |
| 8 | **Strategic sources**: which of them matter most or are hard to replace | no | Priority and risk | systems inventory | "Which of these could you not do without?" | all equal |
| 9 | **Unstructured material** involved: statements, notices, letters, emails, and what must be read from them | yes when documents exist | The document sources in the catalogue, what to extract, confidence rules | the documents folder | "Are there documents or emails this depends on? Drop them in" | none involved |
| 10 | **Transformations and manipulations** done by hand today: adjustments, reclassifications, overrides, corrections | yes | Rules, override workflow, reason codes | reconciliation policy, adjustment sheets | "What do you change by hand before the number is right?" | none; overrides need approval and a reason |
| 11 | **Rules**: who may see what, how long to keep, who approves a change | yes | Access lists, retention, approval gates | access policy, retention note | "Who may see which figures, how long do we keep history, who approves changes?" | readers see only approved results; seven years; the person approves |
| 12 | **Tolerances and definitions that could be disputed**: limits, thresholds, which document wins | no | Checks and tests | policy versus minutes | "The policy says X and the minutes say Y; which stands?" | the signed policy wins; the conflict is noted |
| 13 | **What good looks like**: how the person will know it worked (time saved, errors gone, figures reconciled) | yes | The acceptance test for the release | "What would make you say this worked?" | the pack goes out by the date with no manual step |
| 14 | **What is still unclear and who can settle it** | yes | The open points the architect must not guess | the talk | "Anything you are unsure of, and who could settle it?" | the person, by the signing date |
| 15 | **Extraction**: for each kind of document (statement, notice, invoice, letter), what to take out of it: each value in business words, where it usually sits, whether it must be there, and what it must agree with (a statement total with the positions file, an invoice total with its lines) | yes when documents exist | The extraction spec per document type (fields, checks, worked examples), the review queue and the document tables in landing | the documents themselves: North proposes from what it sees ("this looks like a monthly statement: account, date, closing value, fees") | "For this kind of document, is this what you need from it? Which must always be there?" | only definitions, owners and rules are read from documents; nothing else is taken out |
| 16 | **Benchmarks**: for each KPI, what the person reported for the last period and what it should read after a month's load, within how much ("for September we reported 4.2 %; after the load it should read 4.2 % within 0.1"). Stored on the KPI as `benchmark: {period, reported, expected, tolerance, source: "said by <name>"}`; North copies the figures from the person's words | yes (an answer of "I don't have one" fills it) | The data engineer's definition of done: Flow checks each loaded figure against it, and every miss goes back to the person as a comment on the build pack | past packs, the person's own report | "For the last period, what did you report for each figure, and what should it read once we load the data, within how much?" | `benchmark: null`; the architect's design proposes one, which the person confirms against the first load |

What the person never has to say: table names, data types, pipelines, tools, layers, keys, formats. Those are the architect's, derived from the catalogue and this statement.

## North's closing move

When every required item is filled or unclear, North says what it has, in three short parts, and waits:

1. "Here is what we are building": the intent, the readers, the date, the result.
2. "These are the figures, and where each comes from": the KPIs with their sources and benchmarks (one line each; suggested ones marked).
3. "This is how it runs today": the process map, with the manual steps marked.

When documents are involved, North adds what it will take out of each kind of document (item 15) and how many documents need a look.

Then: "Anything to change? If not, I'll hand this to the architect." On yes: the statement is frozen for signing, a copy (Markdown) is linked in the chat and in the room, and Span is told.

## What the architect takes from it (no further questions expected)

Goal and acceptance test (1, 2, 13) · schedule and service level (3) · the process map (4) · the result's shape (5) · one gold table per KPI with a business definition (6) · the landing sources with owners and samples (7, 8, 9) · the override and approval rules (10, 11) · the checks and disputed definitions (12) · the open points (14) · what to take out of each kind of document, with its checks (15) · the benchmark each figure must meet after the load (16).
