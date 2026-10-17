# Harbor 3.0 UI audit

Date: 17 Oct 2026. Build audited: `ui/dist` in the main folder (not changed). Data: round-8 office copy at `D:/Temp/sh3-audit` (synthetic Evergreen data), served on port 8733 and signed in as Grace Ong (ops lead). No app code was changed.

Screenshots: `docs/v3/ui-audit/<screen>-<width>-<theme>.png`, widths 1440 and 390, themes light and dark. Also `tabbar-390-<theme>.png`. Captured screens: sign-in, desk, action, build, build thread, live thread (with record card), consume (before and after one asked question), knowledge, knowledge skills, the six trust pages, files, board, welcome, start, setup, note, ask.

Coverage: all 96 captures were checked by script (overflow, clipping, dev text, system words, green usage). Visual judgement was made on the desk, action, build, both thread screens, consume, knowledge, skills, the ontology and proof trust pages, and the dark desk and dark live thread. The remaining screens were checked by script only.

Design canvas (https://claude.ai/artifact/MAWLiABUiUvV5MQNRyDXku): opened and listed. It has artboards for each audited screen (Desk2, Action, Build2, Thread, Consume, ConsumePhone, Knowledge, Skills, Ontology, People, Proof, Workbench, Language, Model, Setup, Welcome, Start). A full artboard-by-artboard visual comparison was not done, so the canvas match is not judged here.

## Issues

| Screen | Issue | Severity | Suggested fix |
|---|---|---|---|
| All screens, dark theme (seen on desk and live thread) | Dark mode is not applied to the cards. Light panels sit on a dark-token body; the thread bubbles and desk cards show grey-on-white text that is nearly unreadable. | high | Check the v3 dark tokens in `ui/src/v3/v3.css` and the Frame/card backgrounds; add dark surfaces for cards, bubbles and tiles. Re-shoot to confirm. |
| Trust > Ontology (and tab label on every trust page) | Office sees system words and raw names: tab "Ontology", "The business object graph", table names `legal_entities`, `cash_movements`, "not mapped yet", and column names `counterparty`, `source_system`, `reference` in code font under "Not defined yet · 9 columns". | high | Rename the tab and heading (e.g. "Business objects"); show plain labels; move table and column names into a collapsed "for the auditor" detail. |
| Desk, "Ready to use" card (desktop and phone; also dark) | The figure "880400.00" overflows its tile, is cut off, and runs into the next tile ("0" is clipped at the card edge). | high | Format the figure to fit (e.g. `880,400`), let the tile wrap or shrink the font, or give it a full-width row. |
| Trust > Runs and proof, Trust > People (live thread row) | Dev ids on screen: run ids such as `run-20261016-225642-9d02` and thread id `t-f15adc6b8f`. | high | Show the run's date and label; keep the raw id in a tooltip or the auditor view only. Remove the thread id from the People list. |
| Trust tab strip (phone, 390) | Tabs People, Runs and proof, Workbench and Connections run off the right edge with no scroll cue, so they cannot be seen or reached by touch on phone. | medium | Make the strip horizontally scrollable with a visible edge, or wrap it, or collapse the trust tabs into one menu on phone. |
| Knowledge > Skills | Skill name "Propose ontology addition" and the word "ontology" in skill text are shown to the office. On phone the table is about 7,900 px tall, and the Consume and Knowledge tabs are off-screen. | medium | Rename to "Propose a new business object" or similar; on phone show skill cards instead of a seven-column table. |
| Sign-in (all widths) | Teal accent for the Sign in button, focus ring and the theme chips. Teal is not in `docs/v3/COLOURS.md`, and the act colour is navy. Visually it does not match the v3 pages. | medium | Use `--act` navy for the Sign in button and focus ring; keep the theme chips neutral. |
| Build, Build thread, Live thread, Knowledge skills, Connections, People, Files | Stray green (`--done`) on things not finished: "Next run daily at 06:00" pill; "Reading" (connections); "On" (people autonomy); "In use" skill pills; "Loaded" on files. Green should mean finished and checked only. | medium | Use `--info` slate or `--act` for the schedule, role and status pills; keep green for live, signed and passed. |
| Trust > Ontology (desktop and phone) | Relationship labels overlap ("reports on" over "made for", "approves" over "evidence for"). On phone the graph is too small to read its box labels. | medium | Offset edge labels or show them on hover; on phone show the object list instead of the graph. |
| Trust > Runs and proof | Link to `/v3/thread/null` exists on the proof page (a dead link when a run has no thread). | medium | Hide the link when there is no thread id. |
| Action, Build, Consume (count pills and numbers) | Count pills and numbers use a monospaced face ("All 0", "Decisions 0", "880,400.00" in the watchlist), so they look like dev output. | low | Use the page's sans face with tabular numerals. |
| Action (desktop, empty) | The right detail panel shows an empty placeholder card ("Pick one from the list…") beside "Nothing needs a person right now." | low | Remove the panel when nothing is selected, or show a plain line instead. |
| Desk, Build, Thread (Start and Send buttons) | Start and Send look disabled grey when empty, which reads as a dead control. | low | Keep the act colour with a muted state only when the field is empty, or label it clearly as disabled. |
| Desk, phone | The "Ask Harbor or start something" placeholder is cut off by the mic and Start buttons. | low | Shorten the placeholder on phone or hide the mic until focus. |
| Consume, phone | Watchlist and the table row "EG-TRUST" sit in a scroll box that cuts the third tile. Intended as a carousel, but there is no visible cue. | low | Add a scroll hint or a fade edge. |

## Counts

- high: 4
- medium: 6
- low: 5
- total: 15

## Top 10 issues

1. Dark theme: light cards with faded text (all screens).
2. Trust > Ontology: system words, table names and raw column names shown to the office.
3. Desk "Ready to use": figure "880400.00" cut off and overlapping the next tile.
4. Trust > Runs and proof and People: run ids and thread id shown on screen.
5. Phone trust tab strip: four tabs cannot be reached.
6. Knowledge > Skills: "ontology" in a skill name; phone table is unusable.
7. Sign-in: teal accent is off-spec.
8. Stray green on schedule, role and status pills.
9. Ontology graph: overlapping relation labels; unreadable on phone.
10. Dead `/v3/thread/null` link on the proof page.

## Not confirmed

- The sign-in script check flagged clipped text "Theme". Not visible on the desktop light capture; not counted.
- No app code was changed. Server on port 8733 stopped after the audit.
