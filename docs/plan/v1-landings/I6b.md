# I6b The one screen: landing

## Reuse check
- `ui/src/v1/i3/api.ts`: `Thread`, `ThreadFile` types, `kindOf`, `readBase64` (the base64 file reader) **imported**, not copied.
- `ui/src/v1/i3/ThreadPage.tsx`: the bubble list (MessageBubble per turn, file tags), the composer (drop, picker, removable file chips), AgentChip status, unclear chips and the plain-error helper **copied and reshaped** into the messenger layout.
- `ui/src/v1/i4/api.ts`: `Sow`, `LineEdit` types and `editLine` (I4's PUT) **imported**. `ui/src/v1/i4/SowPage.tsx` `Line` (edit in place) **copied** (it is not exported and i4/ is another card's folder), trimmed to one input.
- Design: `MessageBubble`, `AgentChip`, `Panel`, `PageFrame`, `Button`, `Chip`, `Pill`, `ds-chip` styles for the tabs. No new design component.
- New: the three-tab side panel, the vertical process flow, the blank-conversation greeting, the open-intent lookup (from `GET /api/v1/home`'s `intents`).

## What landed
- `ui/src/v1/i6/api.ts`: `getChat`, `sendChat` (files inline as `{name, data, kind}`), `sendChatFile`, `createIntent`, `getCompany`, `openIntent`.
- `ui/src/v1/i6/ConversationPage.tsx`: `/centre/intent` and `/centre/intent/:iid`. Left: the conversation (scrolls, "North is thinking…" while waiting, paper-clip, Enter sends, Shift+Enter new line). Right: Context (company in brief, link to the company page, what North has read from `sow.sources`, drop zone: uploads through `…/chat/files` during the talk, or holds the files for the first message before it), Statement of work (goal, KPIs, sources, rules, unclear; each line has "edit", saved through I4's PUT), Process map (`process_steps`, else `sow.process.steps`, as a vertical flow with who and system). "Hand to the architect" appears in the header when `ready` (or thread `sow_ready`) and links to I4's `/centre/intent/:iid/sow`. Phone (< 760px): the tabs stack over the chat.
- `ui/src/v1/i6/routes.tsx`: exports `routes`.
- `ui/src/v1/i6/i6.test.tsx`: blank greeting with the company name, first message starts the intent, SOW/process/hand-over shown, a line edit through PUT, a message with a file inline as base64; the entry opening the open intent and the old `/thread` link redirecting; a 403 in plain words.
- `ui/src/v1/i3/routes.tsx`: `intent/:iid/thread` now redirects to `/centre/intent/:iid` (`intent/new` kept).

Checks: `npx vitest run src/v1/i6` 3 passed. `npx tsc --noEmit` clean (whole ui).

## How to test by hand
1. Sign in as Arjun Mehta (Neera). Open `/centre/intent`. With an open intent it lands on it; otherwise North greets you naming the company.
2. Blank: type "How did our portfolios do against the benchmark each month?", Send. The URL becomes `/centre/intent/<id>`, the Statement of work tab is selected.
3. Click the paper-clip, add `positions.csv`, write a line, Send: "North is thinking…" then North's reply; Context tab lists the file under "What North has read".
4. Statement of work tab: click "edit" on Why, change it, Save; it sticks after a reload.
5. Process map tab: the steps North drew. Describe a step differently and watch it redraw.
6. When North says it is ready, "Hand to the architect" appears top right; it opens the SOW sign page.
7. Open an old link `/centre/intent/<id>/thread`: it lands on the new screen. Narrow the window below 760px: tabs above, chat below.
8. As Leela Raman the conversation reads; sending shows the refusal in one sentence.

## Shared edits needed
- `ui/src/App.tsx` line 123: `<Route path="intent" element={<Navigate to="/centre/home" replace />} />` should go, so `/centre/intent` is I6b's screen without relying on route order.
- `ui/src/v1/i3/i3.test.tsx` now fails (2 tests): it drives `ThreadPage` through the `/thread` route, which redirects. Delete it with `ThreadPage.tsx` (no longer routed), or keep only the `/centre/intent/new` part. `NewIntent` still navigates to `/thread`, which redirects; point it at `/centre/intent/<id>` or drop `/intent/new` once nav and home go to `/centre/intent`.
- X2 home links to `/centre/intent/<id>/thread` (redirects fine); can point straight at `/centre/intent/<id>`.

## Open questions
- Starting from a blank conversation: `POST /api/v1/intents {line}` (I2) already writes the line as the first person turn and North's fixed goal question. I send the first message only there (and any files as a following chat turn with empty text) so the line is not said twice. If I6a wants the first reply to come from the model, `POST /api/v1/intents` should run the chat turn itself, or accept `{line, files}`.
- "The person's open intent" is read from `GET /api/v1/home` (`intents[].open` ending in `/thread`, last one). A dedicated field would be cleaner.
- The chat response's `sow` has no `may` block, so edit is offered while `state` is `draft`; the server refuses others (shown as a sentence).

## Round 2b (after Nitin's mock-up review): changes

- **Right column.** A **Context** box is always on top. It holds, in order: the drop zone; what North has read (the company page summary with a link, a count line "N documents and M sample files" taken from the SOW sources plus the company documents, then the list); and the placeholder line "Family office skill". Below it is one card with two tabs, **Statement of work** (the default) and **Process map**. There is no Context tab any more. On a phone the right column sits above the chat.
- **Backend routes (from I6a.md).** `GET /api/v1/intents/open` gives `{id, greeting}`: it opens the open intent, and the greeting is shown on a blank conversation. A new intent starts with `POST /api/v1/intents/chat {text, files?}`, which returns North's first reply from the model. Turns still go through `GET`/`POST …/chat`. I dropped the Home lookup and I2's `createIntent`. The client types now follow I6a's actual view, `{id, intent_id, turns, needs_done, state, sow, process_map}`; `ready` is `state === "sow_ready"`.
- **Process map in the 2.0 swim-lane style.** `ui/src/v1/i6/Swimlane.tsx` is copied from 2.0 `ui/src/modules/m2_baseline/process_map/Swimlane.tsx`: the same n2- markup, styled by the global `styles/legacy/screens-e2.css`.
  - Lanes are `who` (falling back to the system). Columns are Step 1…N in order.
  - Each card shows the name, what it does, the system, and the hand-overs that start at that step.
  - A step whose name or `does` mentions manual, spreadsheet, Excel or by hand gets a "Manual" pill and the copper tint. The legend reads "Manual step / System-automated step".
  - Columns have a minimum width, so the card scrolls sideways and the page does not.
  - Under the map: "That's right" sends the chat message "The process map is right". "Correct a step" puts "Step N: " in the composer and focuses it; N is the step card last clicked, else step 1.
- **Ready.** North's closing line is the last bubble, exactly as the backend sends it. Under it come "Hand to the architect" (I4's sign page) and "Download a copy" (`/api/v1/intents/{iid}/sow/download`). They no longer appear in the page header.
- **Tests.** `ui/src/v1/i6/i6.test.tsx` has 3 tests, all passing. They cover:
  - the greeting, the start through `/intents/chat`, the context counts, the PUT edit, the swimlane lanes, the manual pill and the hand-over, the two buttons, a file sent inline, and the closing line with hand-over and download;
  - opening the open intent, and the `/thread` redirect;
  - a refusal.
  `npx tsc --noEmit` is clean for the whole ui.

Hand test, in addition to the steps above:
1. Open `/centre/intent` with no open intent. You see the greeting from `/intents/open`, and the Context box above the tabs.
2. Describe the steps. Process map shows lanes per person, and a spreadsheet step is tinted "Manual".
3. Click a step, then "Correct a step": the composer reads "Step N: ".
4. "That's right" sends the confirmation to North.
5. At the close, the last bubble is North's summary, with "Hand to the architect" and "Download a copy" under it.

Open: "Family office skill" is a fixed placeholder line, as asked. When the pack skill exists it should come from the company's pack, because the industry is a parameter.
