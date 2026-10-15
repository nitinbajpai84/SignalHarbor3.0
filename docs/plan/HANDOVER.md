# Handover: the Ardmore demo at 07:00 on 7 October 2026 (written 7 Oct 2026, about 05:10)

Read with `docs/guides/DEMO-SCRIPT-ARDMORE.md` (the script, the five sign-ins and the clicks), `docs/guides/DEMO-ARDMORE.pptx (kept in local/branded-decks)` (one slide per step), `docs/guides/TESTING-INTENT-CENTRE.md` (how to test every screen by hand and the automated checks), `docs/plan/QUALITY-PASS.md` (principles, role table, screens) and `docs/plan/SHAPES.md` (API shapes). The shared brief every agent read is `.sh-tmp/AGENT-BRIEF.md`; the queue and the night's timeline are in `.sh-tmp/QUEUE.md`; every agent's walk script, probe and screenshot is under `.sh-tmp/`.

Nitin's standing rules: never push; synthetic data only; no model or vendor attribution anywhere; never edit `.claude/`; production-grade screens verified by screenshot against the artboard; agents decide, people act at named moments; each person sees only act, shared and context information; every number traces to a record; no game words.

## 1. How to run the demo

1. Servers. Backend on 8200, UI on 8201. If they are down: `python tools/doctor.py`, then the backend through the watcher `bash .sh-tmp/backend-watch.sh &` (it restarts uvicorn about 25 s after any Python edit; uvicorn's own `--reload` sticks after one reload on this machine, see `docs/plan` memory), and `cd ui && npx vite --port 8201 --host 127.0.0.1`. For the demo itself stop the watcher (so a stray edit cannot restart the server and sign everyone out) and start the backend plainly: `.venv/Scripts/python -m uvicorn sh_platform.app:create_app --factory --host 127.0.0.1 --port 8200`. The production build in `ui/dist` is served by the backend on 8200 and paints under a second; the vite dev server on 8201 costs 2 to 12 s per page.
2. Data. The plane was reseeded clean after the mutating walkthrough with `bash .sh-tmp/s1-reseed.sh` (journey `--reset`, history, warehouse, then the in-place patches: names and owners, dates, access lists and cells, cluster joins, Aaron's drafted cards, this week's version rows for the closing map). Run it again any time the demo has been rehearsed; it takes about six minutes with the backend up. Proven on disk afterwards: manifest with no refusals, blueprint signed by Marcus Todd on 12 June, 50 runs with June late and August failed, prove with 34 matching periods, one accepted gap (K12) and one not yet (K06), UAT signed on eleven, release draft, one open September alert, memory for seven people, four things new this week on the map.
3. Sign-ins (passwords in `data/_control/seed_credentials.txt`, column two): `participant.ardmore@example.test` is Aaron Lyle; `company_admin.ardmore@example.test` is Janet Shaw, the organiser; `sponsor.ardmore@example.test` is Daniel Kerr; `analyst.ardmore@example.test` is Marcus Todd, head of data and the named tester; `owner.ardmore@example.test` is Harvey Rowley, who owns the files; `approver.ardmore@example.test` is Grace Ward; `platform@example.test` is the super admin. Open five private windows before the meeting, dark theme. The pulse is at `/centre/pulse`.
4. If a page shows an error, reload once. If North or Lens is slow, that is the model call (8 to 25 s); keep talking. If a model call is refused, check for a stale lock file under `data/ardmore/context/` (`*.lock`) and delete it.

## 2. What is ready (verified tonight by screenshot and walkthrough)

- The pulse for all six accounts, with act, shared and context information only; every line traces to a record; the sponsor's release signature and the ambiguity to decide; the organiser's note from the sponsor, running wall, data request and counters.
- The wall: Aaron's two drafted cards to confirm, North drafting a card after two answers and saying so, other people's cards as silhouettes with writers' initials while the rooms are private, North speaking on the wall and in the private room, a plain sentence when speech is unavailable.
- The map: one node per measure, named problems from the charter, no raw ids, "New this week" with one list driving the chip, the filtered columns and the panel; wall names hidden from people without a seat until the charter is signed.
- The node page: trail, definition, plain version sentences, comments with decide for the owner or steward.
- Intent home with doors to the signed baseline and the Treasury charter; Define joined to the baseline's measures with Lens's definitions; the charter with six "so that" lines, who took part, the signature and who does what.
- Baseline and sign-off, the moment of truth and the data request on the real assessment.
- Build home, environment, blueprint (signed by Marcus Todd on 12 June), pipelines with each source's six-month strip (June late, August failed), prove with ten matches, the accepted gap and the not-yet one, a partial release the sponsor can sign (held-back measures named), ops with the one open September alert.
- Consume: feeds with twelve values and K02 amber, the measure page with units and Ask Lens answering with the figures, market forces with three family-office briefs, what-if from Fees Charged with values from the same place Feeds reads.
- The register (twelve rows, five signatures, "came from"), memory per person, the control panel and the sign-in page, context and bring inside the shell.
- Phone width: every page is exactly 390 wide, no unnamed controls.
- Security: no leaks across about 2,300 probe calls as participant, owner and approver; every registered route has a permission line; the egress vault no longer refuses ordinary phrases and breaks stale locks.

## 3. Checks run

- Backend full suite, second run on the final code (`.sh-tmp/f1-pytest-2.log`): 3,686 passed, 1 expected failure, 4 failed, 2 errors. Of the four: three are the "read fast" timing tests in `tests/context_docs` that fail only under load (they pass alone), one was a client name in a pack comment, fixed and rerun (47 pass). The two errors are the repo-tree guard in `modules/m3_connect/tests/test_m3_trial_api.py`, which objects when the live backend writes under `data/` during the run; the file passes alone (6 pass). UI full suite: 934 passed in 80 files. `npx tsc --noEmit` clean; `import sh_platform.app` clean. Run the backend suite on a quiet tree (backend stopped) for a clean sheet.
- Crawler: 46 URLs over seven roles, zero legacy links. Copy rules test passes. Role matrix and shapes tests pass. Leak tests pass (slow, about six minutes).
- Reports: `.sh-tmp/x1-report.md` roles, `x2-report.md` shapes, `x3-report.md` links and copy, `x4-report.md` numbers, `x5-report.md` speed, `x6-report.md` security, `x7b-report.md` phone, `x9-report.md` leaks, `u1-report.md` the customer critic, `m1-report.md` the mutating walkthrough, `p1` to `p5` the persona walkthroughs.

## 4. Known gaps (say "Not available yet" and move on)

- A participant can read a closed wall's board and charter once it is closed (fits "shared" when the charter is signed; wider than the role table's wording).
- "Run now" on the capital calls mailbox adds a run row but no new month, because the demo file carries no date; K04 keeps its nine months.
- Technical definitions on Define show source and field codes, not names.
- Off-path screens (prepare a session) still say "session" where the demo says "wall".
- The organiser's drafts card counts Nira's drafts but has no review screen; the drafts reach each person's pulse when sent from their line.
- Lens's answer takes 15 to 25 s; North's drafting adds about 10 s per answer.
- When the sponsor releases during the demo, eleven measures go and K06 is held back by name until its figure arrives; the register shows the release signature on the released eleven. Reseed before the next run so the release is a draft again.

## 5. Commit

Committed through the private index after the suites (plain message, no attribution, not pushed). Branch `claude/zealous-hawking-w7u39r`, local only. Left uncommitted on purpose: the earlier sessions' edits under `.claude/` (not this session's to commit), `.archify/`, and the stale worktrees under `.claude/worktrees/` (remove with `git worktree remove --force`).
