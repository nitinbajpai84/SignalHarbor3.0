# UC6 through Harbor 3.0: run report (14 Oct, local)

Data: synthetic Evergreen office, fresh each run (`make_clean_env.py --root D:/Temp/sh3-dataN --today 2026-07-31`), July files, then August.
Driver: `docs/test/uc-live/uc6-scripts/v3_e2e.py` (resumable, one step per run) and `v3_month.py 2026-08`.

## What the person did (run 6)
One message, then Confirm (Decision 1), "This is right, carry on" with one answer, the check file (Decision 2), Go live (Decision 3).
Harbor did 14 steps by itself: sign, hand over, systems, samples, design pack, read files, mappings, load, run on a copy, compare, live, board, note.

## Fixed during the runs (in v3_harbor.py unless named)
1. Internal project locked the people Harbor acts for: they join the project team.
2. Brief not signable after one message: Harbor fills open sections with usual practice (marked suggestions), accepts its own drafted lines, and says "no earlier figures" for a first report.
3. Steps ran as the wrong person: the raiser is the person who started the thread; signing is skipped on retry if already signed.
4. Decision 2 was empty: intake now triggers the 2.0 mapping proposals.
5. Recognition: best word overlap wins, a tie asks; with one thread being built, an unnamed data file goes to it.
6. Sources the brief invented (portal, manual file) blocked the run: they arrive by upload, and any with no file is left out and named in Decision 3.
7. Decision 2 asks which file to check the numbers against (one click); the compare reads it (sums portfolios per entity).
8. A file that will not load in a monthly run is named and set aside; the rest still load and run.
9. 2.0 bug: `b9_verify._pct` crashed on a plain 0 (also present in Repo 1.0, not touched there).

## Still open (needs a decision or more build)
1. **The design pack does not follow the brief.** Span built ready tables for holdings and net worth, not cash by entity, calls due 30/60 and uncalled. So Decision 3 honestly shows "this run has no figure" for every check, and the board has no liquidity tiles. In the 2.0 test a person rewrote the select (`r3_gold_fix.py`). Options: (a) Harbor asks Leo when the pack misses a brief figure (fits "when Harbor must ask a person"); (b) improve Span's pack generation to cover every brief KPI; (c) a pack-level liquidity template from the industry pack.
2. Morning note figures come from the 2.0 office liquidity route, not from this thread's ready tables (correct numbers, wrong lineage).
3. North's free text varies between runs; the brief reached Decision 1 cleanly in 3 of 4 runs.
4. Pages time out while Harbor is working (long 2.0 calls: brief chat about 2 minutes, pack generation about 2 minutes).
5. No route yet to answer "What is this file?", expected-vs-arrived dates, or duplicate detection.
6. August: the run loaded and went live with no exceptions raised, because the ready tables do not hold the liquidity figures (see 1).

Screens: D:/Temp/sh3-shots6 (desk, thread at each decision, live pages, August).
