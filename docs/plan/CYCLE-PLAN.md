# The return cycle: implementation plan (7 October 2026)

Nitin accepted the eight design points. This plan says how they are built, in what order, and how we prove them with data.

## 1. The cycle

Notice → Think → Decide → Build → Run → Prove → Notice again.

| Stage | Where it lives | What exists | What is new |
|---|---|---|---|
| Notice | Opportunity radar (spec 57), extends 56 | Watcher patterns, opportunity record | Four lenses (new revenue, process cost, retention, risk), hypothesis with evidence and expected uplift, per-person and per-area radar, signals from walls and check-ins |
| Think | Brainstorm, wall (35 to 37, 23 to 25) | Built | Opens pre-filled from an opportunity's hypothesis |
| Decide | Initiative charter, Decision (22 to 34, 43) | Built | The charter inherits the hypothesis as its success parameters |
| Build | Build centre (spec 59) | Blueprint, pipelines, prove, release (v1) | Agent chain: architect (data, infrastructure, enterprise views) → head of department approval → data engineer → tester → ops manager; company architecture as a living record; context cards on gold tables |
| Run | Ops, feeds | Built (v1) | Watcher feeds the radar instead of only alerts |
| Prove | Initiative outcomes (spec 58) | Nothing | Initiative enters Proving after release; weekly uplift report drafted by North, confirmed by the organiser; verdict working, partly, not, too early; a failed hypothesis returns to the radar with its learning |

## 2. New specs (written now, same brief and rulings method)

- **57 Opportunity radar and the hypothesis record.** One hypothesis shape shared by opportunities, brainstorm outcomes, initiatives and charters: belief, lens, evidence lines (each traced to a record), measure, baseline, target, confidence in words, review date. Radar screens per person, per area, per lens. The red-herring rule: North must reject a pattern the evidence does not support and say why.
- **58 Initiative outcomes and the weekly uplift report.** Proving state after release; the weekly report; verdicts; attribution notes; the receipt to everyone who raised the signal ("your item became X, the measure moved Y").
- **59 Build centre agent chain and architecture ownership.** The five agents and the human gates between them; the architecture record with three views; Archify diagrams regenerated on every signed blueprint; the change note the data engineer builds from.
- **60 Consume by lens, and context cards.** Market, data gaps, upliftment and what-if grouped under the four lenses; every gold table carries a context card (meaning, measures served, lineage, owner, quality rules, last change and why).

## 3. The proof: synthetic data with planted truths

Thirteen data agents build a family-office company (Ardmore, synthetic) with 13 months of monthly data (September 2025 to September 2026) and 98 days of daily data (1 July to 6 October 2026), with eight planted hypotheses (section 4 of `.sh-tmp/ic/data/DATA-BRIEF.md`). Each truth leaves a symptom in a measure, a trail in the sources, and words in the text (minutes, notes, emails, check-ins, walls), exactly like the e-commerce returns and size-chart case. Three initiatives already ran on some of them, so the Prove stage has real before and after. The answer key stays outside the product; testers use it to grade whether the radar found the truth and rejected the red herring.

## 4. The input ledger (the moat)

Every input the product asks for is recorded once in `docs/product/input_ledger.yaml` with its mode: **manual** (a person types or picks it), **confirm** (an agent drafts, a person confirms or edits), **derived** (an agent works it out from documents or data, no person), **automatic** (the system computes it). With the person, the screen, the source, and a planning estimate of minutes without and with the product. `docs/product/MOAT.md` summarises: counts by mode, per journey, per role, the top savings, and the claims we can make in product copy, each traced to ledger rows. It is a living file: every new spec adds its rows.

## 5. Order of work

1. Now, in parallel: the fix loop resumes (fixers and testers cut off by the restart), specs 57 to 60 are written, the 13 data agents build the data, four agents build the ledger.
2. Specs 57 to 60 reviewed against the brief, then build cards through the router, builders plus their unit tests.
3. The data loaded on the live plane; the radar run against it; graded against the answer key.
4. Wave 2: 56 people from seven departments live the whole cycle on the data, as described in `.sh-tmp/ic/wave2/LAUNCH.md`, now including Notice and Prove; fixes; re-tests; until every persona reaches its goal and the critic says it would use it.
