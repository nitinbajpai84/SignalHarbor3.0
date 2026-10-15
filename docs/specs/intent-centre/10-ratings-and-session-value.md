# 10. Ratings and session value

Part of: Intent Centre v2. Depends on: the intent record and closure (brief section 3), the closure screen spec (the `close` view), the Pulse spec, the visibility rule (brief section 4). Feeds: the centre measures page (outcomes), the Pulse spec (two new line kinds), the North agent spec (two nudges).

## Purpose (three sentences)

Everyone who took part in an intent says, when it closes, how worth their time it was, from 1 to 5 with one optional line, so the company learns which kinds of intent earn their time. A month later North asks the organiser whether the outcome was used, because a good session that changes nothing is not a good session. The numbers feed the centre's own measures, and they are never used to rank, grade or review a person.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Participant, affected person who took part, sponsor, organiser, and the named decider, owner or reporter slots (anyone in `people` except observers) | Intent moves to `closed` | A rating prompt on the `close` view; if skipped, a Pulse line after the reminder day (Open question 1) |
| Organiser (Janet) | Any time after three ratings are in | Ratings panel on the intent screen |
| Organiser (Janet) | One month after `closure.closed_at` | North's "was the outcome used" line on her Pulse |
| Company admin | Weekly review of the centre | Section "Was it worth the time" on the outcomes page |
| Super admin | Never | Sees that intents exist, never ratings (brief section 4) |
| Agents | Never rate | North asks and reminds; a named person rates (brief section 5) |

Weekly check-ins are never rated: neither the series nor any week (ruling 3).

Ardmore example: the Treasury brainstorm closes with six people asked. Aaron (participant) rates it 4 and leaves his name off. Katie (analyst, participant) rates it 5 and signs it. Janet sees "2 of 6 have rated" and no average. When Harvey rates it 4, Janet sees "4.3 out of 5 from 3 ratings".

## Entry points (every route, link, Pulse line, button that leads here)

- `close` view of any closed intent (`/centre/intent/<id>/close`, state `closed`): panel "How worth your time was this?" (the view belongs to the closure spec; this feature adds the one panel).
- Pulse line kind `rate`: "Rate 'Treasury cash-sweep ideas'. 1 minute." Button "Rate it", opens `/centre/intent/<id>/close` scrolled to the panel.
- Pulse line kind `used`: "Was the outcome of 'Treasury cash-sweep ideas' used?" Button "Answer", opens `/centre/intent/<id>` scrolled to the panel "Was the outcome used".
- Intent screen `/centre/intent/<id>`, organiser and sponsor: panel "Ratings" and panel "Was the outcome used".
- Past list `/centre/intent/past`: row link "Rate this" on a closed intent the person has not rated while the window is open.
- Outcomes page `/centre/intent/outcomes` (existing route, `ui/src/pages/OutcomesPage.tsx`): new section "Was it worth the time", company admin and sponsor.

## Screens, element by element

### Screen A. Rating prompt (panel on the `close` view)

Route: `/centre/intent/<id>/close`. The Pulse line opens the same panel; there is no separate rating page (Open question 6).
Layout at 1280: one centred card 560 wide under the intent's title and one-line purpose. Inside the card, top to bottom: five score buttons in a row; the note field; the sign-it switch; the buttons. A right-hand column (320) shows "Your earlier ratings" (own ratings only).
Layout at 390: card is full width; the five score buttons stay in one row (each 56 wide); the right-hand column drops below the card and collapses to a "Your earlier ratings (n)" row that opens on tap.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Intent title and purpose | panel | `title`, `purpose` (intent record), type chip, `closure.closed_at` | None | Anyone in `people` except observers | n/a |
| Question | panel | "How worth your time was this?" and the helper "1 is not worth it. 5 is well worth it." | None | Same | n/a |
| Score buttons 1 to 5 | button (five, single choice) | Numerals with a word under 1 ("Not worth it"), 3 ("About right"), 5 ("Well worth it") | Selects the score; enables "Send rating" | Same | None selected, "Send rating" disabled |
| Note | field (one line, character limit with counter, Open question 1) | Placeholder "One line on why (optional)" | Stores text; counts as one free-text box (A-057: number only) | Same | Empty is valid |
| "Put my name on it" | switch | Off by default (ruling 15). Helper when off: "Anonymous. Nobody else can see who gave this score." Helper when on: "Janet and the company admin will see your name." | Sets `anonymous` true or false for this rating | Same | Off |
| Send rating | button | "Send rating" | Writes the rating (journey step 4), shows "Thank you" with the stored score and note, switches the card to read-only | Same | Disabled until a score is chosen |
| Skip for now | button (text) | "Skip for now" | Closes the panel; writes nothing; the Pulse line follows (Rules) | Same | n/a |
| I was not part of this | button (text, second line) | "I was not part of this" | Calls `POST /api/intents/{id}/rating/waive`: no reminder for this person, no rating written | Same | n/a |
| Your earlier ratings | list | Rows: intent title, your score, your note, "signed" or "anonymous", read from your own receipt | Row opens that intent | The person, own rows only | "You have not rated anything yet." |
| Window closed notice | agent line (North) | "The rating window for this intent closed on <rating.dropped_at date>. Ratings are not taken after that." | None; the form is replaced by the notice | Same | n/a |

### Screen B. Ratings panel (on the intent screen)

Route: `/centre/intent/<id>`, panel "Ratings", visible to the organiser and sponsor of the intent. Layout at 1280: a card in the right column under "Closure". At 390: a collapsed row "Ratings: 4.3 (5)" that expands in place.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Rated count | chip | "5 of 6 have rated": `len(rating.rated)` over people asked (`people`, minus observers) | None | Organiser, sponsor | "No one has rated yet." |
| Average | panel | "4.3 out of 5 from 5 ratings": mean of `ratings[].score`, with a five-step bar of counts per score | None | Organiser, sponsor, only when `len(ratings)` is 3 or more (brief ruling 8) | "Not shown until three people have rated (2 so far)." |
| Signed ratings | list | Name, score, note, for entries with `anonymous` false | Row expands to the full note | Organiser, sponsor | "Nobody signed a rating." |
| Anonymous ratings line | panel | One line "2 anonymous ratings are counted in the average. Their notes stay with the person who wrote them." Count from `ratings` where `anonymous` is true | None | Organiser, sponsor | Line hidden when there are none |
| Remind people who have not rated | button (organiser only) | "Remind people who have not rated" | North sends one reminder Pulse line to people who skipped, inside the window; once per intent | Organiser | Hidden when everyone has rated or the window closed |
| Outcome used | panel | "Used", "Partly used" or "Not used", the organiser's line, the answered date (`outcome_used`) | "Change answer" reopens Screen C within the change period (Open question 1) | Organiser, sponsor, company admin | "North will ask you on <outcome_used.ask_at>." before the date; "Waiting for your answer." after |

### Screen C. Was the outcome used (panel on the intent screen, organiser only)

Route: `/centre/intent/<id>`, panel "Was the outcome used". Layout at 1280: a card 560 wide in the centre column under "Closure", with a read-only summary of `closure.what_came_out` and `closure.next` above the question. At 390: same card, summary collapsed behind "What came out".

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Summary of the outcome | panel | `closure.what_came_out` and the list of `closure.next` (each with its `ref` and whether that ref is still open, from the linked intent record) | Row opens the linked intent at `/centre/intent/<ref>` | Organiser | "No outcome was recorded at closure." |
| Question | agent line (North) | "A month ago 'Treasury cash-sweep ideas' closed with one idea chosen. Has the outcome been used?" | None | Organiser | n/a |
| Choice | button (three, single choice) | "Yes", "Partly", "No" | Selects the answer | Organiser | None selected, "Save answer" disabled |
| Line | field (one line, character limit, Open question 1) | Placeholder: Yes "What changed?", Partly "What was used and what was not?", No "What stopped it?" | Stores text | Organiser | Empty valid for "Yes"; North asks once more for a line on "Partly" and "No" but does not block |
| Save answer | button | "Save answer" | Calls `POST /api/intents/{id}/outcome-used` (journey step 9) | Organiser | Disabled until a choice |
| Ask me later | button (text) | "Ask me in a week" | North moves the Pulse line on by the deferral period; allowed a limited number of times (Open question 1) | Organiser | Hidden after the last deferral |
| Suggested next move | agent line (North) | After "No" or "Partly": one drafted next step, for example "Open a Problem for what stopped it" | Button "Open it" goes to `/centre/intent/new?type=problem&from=<id>`; button "Not now" dismisses | Organiser | Hidden on "Yes" |

### Screen D. "Was it worth the time" (section on the outcomes page)

Route: `/centre/intent/outcomes` (existing), section reads `GET /api/intents/ratings-summary` (New). Layout at 1280: a three-column grid of measure cards (by type, by area, rated share) above a table of the follow-up answers. At 390: cards stack, tables become card lists.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Average by type | panel (four rows: Initiative, Brainstorm, Problem, Decision; a fifth row "Weekly check-in: not rated" with no number) | Type name, mean score, count of ratings, count of intents rated, from `intents/*/intent.json` `type` and `ratings` | Row filters the area card to that type | Company admin, sponsor (sponsor sees own areas) | Row reads "Not enough ratings yet (1 of 3 needed)" |
| Average by area | panel | Area tag, mean score, count of ratings | None | Same | "No area has three ratings yet." |
| Rated share | panel | "62 percent of closed intents were rated (13 of 21)" (example figures): closed intents with at least one rating over closed intents, from `state` and `ratings` | None | Company admin | "Not available yet. No intent has closed." |
| Intents rated by organiser | list | Organiser name and count of intents rated out of closed, from `people.organiser`. No score column | None | Company admin | "None yet." A person with fewer than five closed intents shows "Fewer than five" in place of the counts (brief ruling 8) |
| Outcome used | panel | Counts of Yes, Partly, No and "Not yet answered", by type, from `outcome_used` and `closure.closed_at` | None | Company admin | "Not available yet. No intent closed more than a month ago." |
| Source line | agent line (North) | "From intent records. Groups smaller than three are not shown." | None | Same | n/a |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Janet closes the brainstorm. North writes the closure draft; Janet signs it. The intent state becomes `closed`.
2. North writes `rating` on the intent record (asked date, reminder day, drop day) and opens the panel on each person's `close` view. North does not rate for anyone. A weekly check-in never reaches this step.
3. Aaron opens `/centre/intent/<id>/close` and sees "How worth your time was this?" He picks 4, types "Good people in the room, too few numbers", leaves the name switch off.
4. He presses "Send rating". The route writes one entry to `ratings` with `by` null and `anonymous` true, adds his account id to `rating.rated` (presence only, kept apart from the score), and writes his own receipt (see Records). The panel shows "Thank you. You gave 4."
5. Katie skips. Nothing is written for her. At the reminder day North makes a `rate` Pulse line for her.
6. Katie opens it from Pulse, picks 5, switches the name on, presses "Send rating". The entry has her `by` and `anonymous` false. The Pulse line disappears.
7. A person who ignores the reminder gets no further line. At `drop_at` North drops the line and writes nothing for them. The intent counts as "not rated by them".
8. Janet opens `/centre/intent/<id>`. With two ratings she sees "2 of 6 have rated" and no average. When the third arrives the average and bar appear.
9. One month after closure North puts a `used` line on Janet's Pulse. She opens the panel "Was the outcome used", picks "Partly", writes "Idea 2 went to Harvey; idea 1 is parked", presses "Save answer". North writes `outcome_used`, then drafts one suggested next move if the answer is "No" or "Partly"; Janet decides.
10. The company admin opens `/centre/intent/outcomes`, reads the averages by type and area, the rated share and the organiser counts, and leaves.

## States and transitions (table: state, who moves it, to what, what is written)

Rating window (a sub-state of a closed intent, held in `rating`):

| State | Who moves it | To what | What is written |
|---|---|---|---|
| not_asked | n/a | n/a | `rating` is null on draft, open and cancelled intents and on every weekly check-in |
| asked | North, when the intent becomes `closed` | window open | `rating.asked_at`, `rating.reminder_at`, `rating.drop_at` |
| answered (per person) | The person, "Send rating" | that person has rated | A `ratings` entry; the account id into `rating.rated`; the receipt |
| waived (per person) | The person, "I was not part of this" | no reminder for that person | The account id into `rating.waived` |
| reminded | North, at `reminder_at`, once per person who is neither answered nor waived | Pulse line `rate` shown | Pulse line only; `rating.reminded` gets the account id |
| dropped | North, at `drop_at` | window closed | `rating.dropped_at`; Pulse lines removed; no more ratings accepted |

Outcome used (held in `outcome_used`):

| State | Who moves it | To what | What is written |
|---|---|---|---|
| scheduled | North, at closure | waiting | `outcome_used.ask_at` (one calendar month after `closure.closed_at`, Open question 1), `answer` null |
| asked | North, at `ask_at` | Pulse line `used` shown to the organiser | `outcome_used.asked_at` |
| deferred | Organiser, "Ask me in a week" | asked again later | `ask_at` moved on; `deferred` count |
| answered | Organiser, "Save answer" | yes, partly or no | `answer`, `note`, `answered_by`, `answered_at` |
| unanswered | North, after the answer period | stays unanswered; line dropped | `outcome_used.dropped_at`; counted as "Not yet answered" |

Dates and "working day" use the company's time zone from the profile, else UTC (brief ruling 8).

## Records read and written (file or route, fields; mark Existing or New)

| Record | Fields | Mark |
|---|---|---|
| `intents/<id>/intent.json`, field `ratings` | list of `{by \| null, anonymous, score, note, at}` | Brief field `ratings` (section 3), content New |
| `intents/<id>/intent.json`, field `rating` | `asked_at`, `reminder_at`, `drop_at`, `dropped_at`, `rated` (account ids, presence only), `waived`, `reminded` | New |
| `intents/<id>/intent.json`, field `outcome_used` | see Fields this feature adds | New |
| `intents/<id>/intent.json`, fields `closure`, `people`, `areas`, `state`, `type` | read only | Existing in brief section 3 |
| `people/<account_id>/ratings.json` (company plane, own-read only) | list of `{intent_id, score, note, anonymous, at}` | New; the person's own file keeps the link so they can see what they gave (ruling 15); the intent's `ratings` list never carries it |
| `POST /api/intents/{id}/ratings` | body `{score, note, anonymous}`; one per person per intent; refused outside the window | New |
| `GET /api/intents/{id}/ratings` | viewer-filtered: organiser and sponsor get counts, mean (3 or more), signed entries; the person gets own; others get nothing | New |
| `POST /api/intents/{id}/rating/waive` | no body | New |
| `POST /api/intents/{id}/outcome-used` | body `{answer: yes\|partly\|no, note}` | New |
| `GET /api/intents/ratings-summary` | numbers only: by type, by area, rated share, organiser counts, outcome-used counts | New; follows the shape of `GET /api/company/outcomes` (Open question 5) |
| `GET /api/company/outcomes` (`sh_platform/outcomes.py`) | headline, modules, funnel | Existing, not changed |
| `modules/m1_intent/store/sessions.py` `inputs` counters | `actions`, `free_text` | Existing, read through `outcomes.py`; the rating note adds one `free_text` |
| `sh_platform/route_permissions.yaml` | one line per new route (default deny) | Existing file, new lines |

Anonymous ratings: the `ratings` entry has no account id and a date without a time, so a score cannot be matched to the moment a person pressed the button. `rating.rated` lists who has rated and never says which entry is theirs.

## Fields this feature adds to the intent record

```
rating: {
  asked_at, reminder_at, drop_at, dropped_at | null,
  rated: [account id], waived: [account id], reminded: [account id]
}
ratings: [{ by: account id | null, anonymous: bool, score: 1-5, note: string, at: date }]   # "at" added; brief fields kept
outcome_used: {
  ask_at, asked_at | null, deferred: count,
  answer: yes|partly|no|null, note: string | null,
  answered_by: account id | null, answered_at | null, dropped_at | null
}
```

`rating` and `outcome_used` are null on weekly check-ins and on intents that are not closed. They are separate from `outcome`, which is never null (ruling 6). Limits on `note` are in Open question 1.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North, at closure:** writes `rating`, shows the prompt. Drafts nothing about the score. Person acts: rates.
- **North, at the reminder day:** makes the `rate` Pulse line for each person who has not rated or waived. One line, once. Person acts: rates, waives or ignores.
- **North, at the end of the window:** drops the lines. Says nothing to anyone.
- **North, at one month:** asks the organiser "was the outcome used". Drafts one suggested next step on "No" or "Partly". Person acts: the organiser answers and decides the next step.
- **North, on the organiser's panel:** writes the plain line "3 of 6 have rated, average 4.3" from the record. It never reads out an anonymous note and never names who has not rated.
- **Lens:** not used.
- **Nira:** carries the two Pulse line kinds (`rate`, `used`) to the person's "what is waiting for you" list, with the expected minutes (1 and 2) in the existing `MINUTES` table.
- Agents never rate and never answer "was it used" for anyone.

## Rules (visibility, time box, who may do what)

1. **Who is asked:** organiser, sponsor, participants, the named decider, owner and reporter (ruling 13), and affected people who took part (the test is Open question 3). Observers are not asked (ruling 4). Draft and cancelled intents are not rated (ruling 14). Weekly check-in series and weeks are not rated (ruling 3).
2. **The prompt:** score 1 to 5, whole numbers only, one optional line, anonymous by default, a switch to sign it. One rating per person per intent. A rating cannot be edited or withdrawn after sending (the receipt shows it).
3. **When:** asked at closure; a Pulse line follows once if not answered by the reminder day; dropped at `drop_at`. No third ask.
4. **Organiser sees:** the mean and the count once three or more ratings are in (ruling 8). Before three, only "n of m have rated". Never an individual anonymous score or note. Signed ratings are shown with name, score and note.
5. **Company admin sees:** means per type and per area, only for groups of three or more ratings; counts; never an individual rating, never a note, never an anonymous entry (brief section 4).
6. **Participants see:** their own ratings (through their own file), nothing of others'.
7. **Super admin:** sees nothing of ratings (ruling 5).
8. **A sponsor** sees the same as the organiser for their own intent, and the area means for areas they sponsor.
9. **A rating is a number plus text.** It is never used to rank, grade, score or review a person. No per-person average exists anywhere (ruling 15); the route has no such query and a request for one is refused. No screen, export or agent line orders organisers or participants by score. The organiser list shows counts only, and a per-person count below five shows "Fewer than five" (ruling 8). No rating or mean is written into any person's profile, pulse, review or HR record.
10. **Small groups:** a group of fewer than three ratings shows "Not enough ratings yet". For a single area with fewer than three, the area row is merged into "Other areas" only if that merged group reaches three; otherwise it is hidden.
11. **Outcome used:** only the organiser answers. The sponsor and company admin read the answer. The answer never changes the intent's closure; it is a separate record. If the organiser has left, see Open question 4.
12. **Tied to a record:** every number on screen traces to `intents/<id>/intent.json`. Where the record lacks it the screen says "Not available yet" and names what is missing.
13. **Copy:** no game words, no vendor names in text. The agent is North.

## Counters and measures of this feature (numbers only, each traced to a record)

| Measure | Definition | Traced to | Shown to |
|---|---|---|---|
| Mean score by type | mean of `ratings[].score` for closed intents of that type; shown when 3 or more ratings | `intents/*/intent.json` `type`, `ratings` | Company admin, sponsor |
| Ratings count by type | `len(ratings)` summed by type (exact) | same | Company admin |
| Intents rated by organiser | count of closed intents with at least one rating, by `people.organiser`. A count only, no score; "Fewer than five" below five closed intents | `people.organiser`, `ratings`, `state` | Company admin |
| Mean score by area | mean score over intents tagged to the area; an intent with two areas counts in both; 3 or more ratings | `areas`, `ratings` | Company admin, sponsor |
| Percent of intents rated | closed intents with at least one rating, over closed intents. Cancelled and weekly check-ins excluded | `state`, `type`, `ratings` | Company admin |
| Rated share per intent | `len(rating.rated)` over people asked | `rating`, `people` | Organiser, sponsor |
| Outcome used by type | counts of yes, partly, no, not yet answered, for intents closed more than a month | `outcome_used`, `closure.closed_at` | Company admin |
| Notes typed | one `free_text` per note typed | `m1_intent` session `inputs.free_text` (A-057) | Existing outcomes page, number only |

Each measure returns `null` for "not yet", never zero (the rule in `sh_platform/outcomes.py`).

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: `graft ask "intent counters actions free_text"`, `graft ask "company outcomes numbers only"`, `graft ask "pulse line kinds minutes"`, `grep -rn "A-057" docs`, and a search for "rating", "rate" and "feedback" in `sh_platform/`, `modules/` and `ui/src` (no existing rating store or screen found). Paths below were checked to exist on 7 Oct 2026.

| Found | Where | Decision |
|---|---|---|
| m1_intent counters: `store.count` adds `actions`, `free_text`, `cards_*`, numbers only (A-057) | `modules/m1_intent/store/sessions.py` lines 127 to 142; `modules/m1_intent/api/deps.py` lines 42 to 57 (`typed`, `_count`) | **Reused as is.** The rating note is one free-text box and is counted as `free_text` through the same path. No new counter for ratings: the measure is read from the intent record. |
| `sh_platform/outcomes.py` `build` and route `GET /api/company/outcomes`: numbers only, `null` for not yet, per-viewer read, records read by path | `sh_platform/outcomes.py` lines 1 to 187 (helpers `_files`, `_load`, `_v` at 26 to 62; route at 184) | **Reshaped.** The new `GET /api/intents/ratings-summary` is a sibling in a neighbouring module with the same helpers and null-for-not-yet, reading `intents/*/intent.json` instead of module folders. The existing function is not changed. |
| Pulse lines: `line(...)`, `safe`, `MINUTES`, readers per record kind | `sh_platform/pulse/lines.py` lines 22 to 75 (`MINUTES` at 22, `safe` at 60, `line` at 71) | **Reused.** Two new readers (`rate`, `used`) in the same style; two keys added to `MINUTES`. |
| `sh_platform/jsonfile.py` (`lock_for`, `read_json_strict`, `write_json_atomic`) | lines 19 to 61 | **Reused** for `intents/<id>/intent.json` and the receipt. |
| `sh_platform/profile/view.py` `Viewer`, `sees_area` | lines 27 and 79 | **Reused** for the area filter on Screen D and the "who may read the panel" check. |
| `sh_platform/route_permissions.yaml` (default deny; `/api/company/outcomes` roles at line 296) | line 296 | **Reused.** New routes get one declaration each. |
| Outcomes page UI | `ui/src/pages/OutcomesPage.tsx` (route `intent/outcomes`, `ui/src/App.tsx` line 108); copy in `ui/src/pages/centreCopy.ts` | **Reshaped.** A new section on the same page; copy goes in `centreCopy.ts`. `CentrePage.tsx` is the wall home, not used. |
| Anonymous handling for notes and the seal (D-013); small-group constant `SMALL_GROUP = 5` | `modules/m1_intent/api/summary.py` lines 32 and 63 to 69 | **Same rule, not copied code.** The rating follows the same idea: the anonymous entry never carries a name; per-person figures use five. |

Genuinely new: the `rating` and `outcome_used` fields, the intent routes, the aggregate route, the receipt file, two Pulse line kinds, the two panels on the intent and `close` views, and the outcomes section.

## Not in this feature

- Rating of people, organisers or agents. Only the time spent on the intent is rated.
- Rating of weekly check-in series or weeks (ruling 3).
- Free-text sentiment scoring of notes. A note is read by people only.
- Per-person averages, trends, leaderboards or comparisons of any kind (ruling 15).
- Editing or deleting a rating after it is sent.
- Any email or message outside the Pulse.
- The `close` view itself (closure spec); this file adds one panel to it.

## Open questions

1. **Numbers this spec uses that the brief did not give** (defaults, Nitin to confirm each): note limit 140 characters; outcome line limit 200; reminder two working days after closure; window drop at the end of the fifth working day after closure; follow-up one calendar month after closure; deferral of seven days, at most twice; answer period 28 days after the line is first shown; "Change answer" allowed for seven days; "Your earlier ratings" shows ten rows. The calendar month versus working days choice is part of this.
2. **Group size for company admin area means:** three is used for every aggregate (ruling 8). The egress rule (five) applies only to numbers that leave the plane. Confirm.
3. **Who counts as "took part" for affected people:** default is those who opened or contributed to the intent. Confirm the test.
4. **Organiser has left the company:** default is the sponsor answers "was it used". Confirm.
5. **Route for the aggregate:** `GET /api/intents/ratings-summary` follows the convention; the sibling `GET /api/company/outcomes` lives under `/api/company/`. Also, the existing outcomes page route `/centre/intent/outcomes` is not in the brief's route list. Confirm both.
6. **No rating page or `used` page:** the route list (ruling 1) has no `rate` or `used` view, so both are panels (on `close` and on the intent screen). Add views `rate` and `used` only if Nitin wants full pages.
7. **Receipt path:** `people/<account_id>/ratings.json` is proposed here; ruling 15 fixes the behaviour, not the path.
8. **Cancelled intents:** not rated. Should participants of a cancelled intent be asked "was the time wasted"?
