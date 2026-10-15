# Agent long-term memory: build plan (Nitin, 5 Oct 2026)

Goal: every agent (North, Lens, Nira) keeps a long-term memory of its conversations with each person, summarised and compacted the way a long chat is compacted, kept locally in the company's own plane. Later, general lessons (no personal data, no customer detail) are shared across companies through the industry packs.

Decisions: A-048 to A-051 in `docs/ledger/autonomous.md`.

## Two layers (per company, per agent)
1. **Person memory**: what one agent learned from one person (facts, preferences, open threads, decisions). Used in full in that person's own conversations with that agent. The person can read it, correct it or delete it ("What North remembers about you").
2. **Company memory**: a compacted, de-personalised digest across all people for that agent: facts about the company, its systems, its pain points, its decisions. No names, no "who said it", no quotes. Used by that agent in anyone's conversation (Nitin: "company-wide to agents"). A company admin can read, correct or delete entries.
The existing admin-reviewed memories (`context_docs` pending memories: fact, decision, preference, correction) feed the company memory once accepted.

## Never remembered (filtered before summarising and again before storing)
Anonymous or private notes (Q14 private/anonymous, notes marked anonymous); anything under a restricted area (pay, HR) or from a restricted document; figures (the number guard: numbers are never memory, only recorded facts are); credentials or contact details (emails, phones, account numbers). People in restricted areas are not named in company memory.

## How it is built and compacted (like a long chat being compacted)
- **Short-term** (unchanged): the last turns of the current conversation (North: 8 of the person, 6 of its own).
- **At the end of each conversation** (room closed, interview done, ask-box idle, or every N turns), the agent writes a short structured summary of that conversation through the egress gateway (names tokenised, the four guards), and merges it into the person memory: new facts added, changed facts replace old ones with the date, contradictions kept as an open question.
- **Compaction**: each memory has a size budget. When a person memory passes it, the older conversation summaries are folded into one shorter digest (keep the newest few summaries in detail, compact the rest), exactly like a context summary. Compaction keeps provenance (which conversation, when) and never invents: if the model fails, the old memory stays as it was.
- **Company memory** is rebuilt from the person memories and accepted memories by the same compaction step with names and attributions removed and anything said by only one person about themselves left out.
- **Use**: at the start of each turn the agent gets (a) the person memory for this person, (b) the company memory, each wrapped as background (never an instruction, never the source of a figure), within a token budget.
- Storage: `plane.path("context", "memory", <agent>, "people", <pid>.json)` and `.../company.json`; JSON with entries {id, kind, text, from: [{conversation, at}], updated_at, by: agent|person}. Person edits are never overwritten by the agent (rule 7). Retention: person memory deleted when the person deletes it or leaves; follows the company's retention otherwise.
- People are identified by the profile link (A-043): no link, no person memory (company memory still applies).

## Cross-company (later package, design only now)
Lessons into the industry pack (Nitin's choice): agents propose general lessons from company memories ("family offices often track capital calls by email"); personal data and customer specifics stripped; a lesson kept only if seen in at least 5 companies; two named people approve; it lands in `packs/<industry>/` as a labelled suggestion. No raw memory or summary ever leaves a company plane; only approved, generalised lesson text moves, through the control plane. Needs its own package, review and the cloud-push rule (two approvers).

## Packages
| ID | What | Depends |
|---|---|---|
| MEM-1 | Kernel `sh_platform/memory/`: stores, filters, summarise-and-merge, compaction with budgets, company digest, read for the prompt; stub-model tests | - |
| MEM-2 | Wire North (private room, interview), Lens (ask box, interview), Nira: summarise at conversation end, inject memories; screens: "What <agent> remembers about you" (read, correct, delete) and the admin's company memory; room notice | MEM-1 |
| MEM-3 | Cross-company lessons into packs | later, after MEM-2 is used |
