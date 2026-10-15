# Module 3: Assess and plan

Takes the signed baseline and the signed charter and ends in a signed phased build plan. Agent: Lens, the business analyst; Nira guides from a small side panel (D-036).

- Contract: `contracts/SHARED.md` (read it first). Decisions: D-036. Reuse check: `docs/ledger/M3-DESIGN/reuse-check.md`.
- The customer gives source data and benchmark figures, accepts the risks and accepts the plan. Lens drafts everything else; a draft never overwrites a human edit.
- Reads module 2's signed outcome and module 1's charter outcome from the company plane by path (`domain/inputs.py`); never imports another module. A restricted measure stays restricted.
- One assessment = one folder in the plane. Each package writes only its own files; `store/assessment.py` owns `assessment.json`.
- Six steps (`domain/steps.py`): each package registers a `state(assessment_dir)` function for its step.
- Files stay on the machine. Only column names, types, counts and definition text may reach the model, through the egress gateway.
- Output: the plan outcome record for module 4 (M3-P04).

## Lean module 3 (LI-M3): fewer human inputs
- Samples and reported figures come from the company profile, read with `sh_platform.profile.read(plane, viewer)` only (`domain/from_profile.py`): a sample becomes a source's intake and is not requested again (`intake/<source>/from_profile.json` marks it); reported figures become `benchmarks.json` entries with `from_profile: true` and their label in `came_from`. An organiser's own upload, a figure from an uploaded file and a hand mapping are never replaced.
- A file dropped without a source goes to `.../intake/sources/_auto/upload`: filed by columns, name and the system it came from (`intake_match` and the pack's spellings); not certain means `needs_confirm` and nothing is kept.
- `domain/trial.py` `auto_check`: a rule that matches the customer's figure is `checked` with `auto_checked: true`, taken back if it stops matching; a person's check is never touched.
- Restricted samples: adoption and plan teams read `profile.read_unrestricted` only (same for everyone; the shared files hold nothing restricted). A person who may see a restricted sample may place it by hand; its mark holds the key only. When serving, a mark counts only while its key is open in `read_unrestricted` or the reader may see that sample (`from_profile.served`); otherwise the source reads "A restricted sample" and its profile, rows and figures (trial, findings) are masked for that reader.
- One rule for a shut source: a measure fed by a source that is shut for a viewer is a restricted measure on every route and record. Per viewer, `Ctx.hidden` (api/plan.py) adds the measures `from_profile.shut_sources` feeds, so the plan bands, risks, decisions and the restricted note mask them. Shared records (plan draft, signed outcome facts) use `from_profile.closed_sources` (any sample mark not open in `read_unrestricted`): those items are restricted, store no reason, blocker, team or wording, and the outcome carries nothing derived from the sample. An upload on a shut source by someone who may not see it is refused; the listed person's upload replaces it and clears the mark (`forget_closed`).
- Plan teams: a source with no owner on file takes the catalogue's data owner and module 2's data and process owners, with teams from the profile's people (`api/plan.py`).
- `inputs_count.json` in the assessment folder: `{"actions": {kind: n}, "actions_total": n, "free_text": n}` (`domain/counters.py`); counts only, no names or text. The outcomes page reads it by path.
- Engine filters added for the demo's rules: `not_contains` and `listed_in` (a row's value is in another source's column).
