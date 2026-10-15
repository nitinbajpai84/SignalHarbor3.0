# Low-input journey: build plan (5 Oct 2026)

Source: Nitin approved "Bring what you have" (deck https://claude.ai/artifact/VGTjoGJjPVxSTzX7sUhpS4) and asked to build it, test package by package, and demo it on the local prospect workspace (company id in the gitignored `local/companies.yaml`; never name it in tracked files). Standard inputs and the interview: `docs/specs/CUSTOMER-STANDARD-INPUTS.md`.

Principle: bring what you have; agents read first and draft everything; one interview per person; people return only to approve, answer at most 3 exceptions, or improve each quarter. Every draft names the input it came from.

## The company profile (shared contract, every package reads it)
One file per company plane: `plane.path("context", "profile", "profile.json")`, owned by `sh_platform/profile/` (kernel, because all three modules read it). Every value is a provenance cell `{value, mark: stated|guessed|unknown, by, at, from: {kind: document|interview|sample|person, ref, page?}}`.
- `inputs`: per standard input group (1-9), `state` read | partly | missing, documents and samples attached, who was asked.
- `people`: name, role, team, email, account id, is_sponsor, is_head_of_data, is_organiser, owns (systems, measures).
- `systems`: id, name, kind (spreadsheet, system, mailbox, feed, document), owner, how data lands, frequency, tables and fields if known, licence.
- `governance`: restricted areas, field rules (personal class, who may see), decided by.
- `reported_figures`: measure name, figure, unit, period end, from (document and page). These are the benchmarks.
- `samples`: system id, file, period, uploaded by, profile summary.
- `interviews`: person, question id (Q1-Q14), answer, follow-ups (trigger, question, answer), shareable, anonymous.
- `constraints`: licences, internet access, deadlines, running programmes.
Modules read the profile through one function `sh_platform.profile.read(plane, viewer)`, filtered for the viewer like the rest (restricted fields and people hidden). Modules write their own outputs as today; they do not write the profile except through `profile.record(...)` with provenance.

## Packages, in order (each: build, independent review, merge, then a live check on the demo workspace)
1. **LI-DATA**: rich demo inputs for the local workspace, under `local/<id>/`: all nine input groups, three months of data, 8-10 sources, 12-15 measures, interview answers per person, deliberate gaps, and an expected-outcomes key per module (charter, baseline, plan).
2. **LI-PROFILE**: the profile store and the "Bring what you have" page: nine input tiles, uploads into context shelves and samples, Lens reads them and fills the profile (people, systems, governance, reported figures), readiness meter, Nira asks the right person for what is missing.
3. **LI-INTERVIEW**: the one interview (Q1-Q14 in a contract), per role, North and Lens prefill from the profile, follow-ups by the seven triggers (at most 2 per question), answers recorded in the profile with provenance.
4. **LI-M1**: module 1 lean: session drafted from the profile; North writes notes from the interview and the room; the vote decides the charter; stages close on time; one signature.
5. **LI-M2**: module 2 lean (built by the module 2 session): Lens drafts the baseline from the profile and interviews; one "Confirm my measures" page per owner with at most 3 questions; ask once (personal data per field, tracked today, owners).
6. **LI-M3**: module 3 lean: samples and reported figures taken from the profile; uploads filed to sources by Lens; matching rules checked automatically; plan teams from owners.
7. **LI-OUTCOMES**: an outcomes page per workspace: time from kickoff to each signed output, human inputs per module, drafts accepted unchanged, measures ready to build in 3 weeks.
8. **LI-E2E**: a full live run of the demo workspace from "Bring what you have" to the signed plan, screenshots and a run report for the client deck.
