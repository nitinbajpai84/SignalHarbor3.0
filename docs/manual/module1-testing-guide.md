# Module 1 (Intent Centre): manual testing guide

For Nitin. Plain words, one step at a time, with a picture after each step.
Everything you see is made-up ("Illustrative") practice data. Nothing here is a real client.

## Before you start

1. Start Signal Harbor the usual way (`python tools/dev.py` from the repo folder). Two addresses matter:
   - **http://127.0.0.1:8201** is the screen you use (the UI).
   - **http://127.0.0.1:8200** is the engine behind it (the backend). You do not open this one yourself.
2. Your sign-in details are in `data/_control/seed_credentials.txt` in your repo. Each line is one person: email, password, role, company. Never share that file.
3. The people used in this guide (by email only):
   - `analyst.harbor-mutual@example.test` : the analyst at Illustrative Harbor Mutual (insurance). Main walk-through.
   - `analyst.tidewater-capital@example.test` : the analyst at Illustrative Tidewater Capital (asset management). Short second walk-through, to show different industry content.
   - `analyst.lakeside-family-office@example.test` : the analyst at Illustrative Lakeside Family Office (family office). Part 3: North's industry practice for a family-office question.
4. If you have not set a model key in `.env`, North and Nira will say they are "not available". That is expected and is described where it happens. With a model key in `.env`, they answer.

Pictures in this guide were taken with the model switched off.

---

## Part 1. Harbor Mutual analyst (insurance)

### Step 1. Sign in
Open http://127.0.0.1:8201. Type the analyst's email and the password from your seed file, then press **Sign in**.

![Sign-in page](img/01-sign-in.png)

### Step 2. See your modules
You land on "Your modules". Harbor Mutual sees three tiles: Intent, Baseline, and Connect, scan and gap. Only module 1 is testable today. Click **Intent**.

![Your modules](img/02-modules.png)

### Step 3. Open the Intent Centre
The Intent Centre shows "You have not prepared a session yet." Click **Prepare a session**.

![Intent Centre](img/03-intent-centre.png)

### Step 4. Prepare a session: Purpose
The wizard has seven steps along the top: Purpose, Charter, People and time, North, Briefing video, Approver, Review. Finished steps turn green.

![Purpose step, empty](img/04-wizard-purpose-empty.png)

Fill in "What is this session for?" and "What outcome do you want?". Use your own words, for example "Agree what Harbor Mutual wants to know about claims handling delays." Click **Next**.

![Purpose step, filled in](img/05-wizard-purpose-filled.png)

### Step 5. Charter
Choose the charter template: **Standard charter** (problem, purpose, priority, how many notes back it) or **Short charter** (problem and priority only). Leave Standard. Click **Next**.

![Charter step](img/06-wizard-charter.png)

### Step 6. People and time, and the split check
Choose how many people will join (1 to 10; "1 person" is a solo session) and how long it lasts (5, 10, 20, 30 minutes or another length). Pick **3 people** and **20 minutes**.

![People and time](img/07-wizard-people-time.png)

The time is shared in three parts: Briefing, Individual rooms, Together. The "split check" is the line under them. Try it: change Briefing from 4 to 6. A red message says the three parts add up to 22 minutes but the session is 20, and **Next** is greyed out until you fix it.

![Split check, parts do not add up](img/08-wizard-split-check-wrong.png)

Put Briefing back to 4 (4 + 8 + 8 = 20). The message becomes "The three parts add up to 20 minutes." and **Next** works again.

![Split check, parts add up](img/09-wizard-split-check-ok.png)

Click **Next**.

### Step 7. North options
North is the industry expert. Two tick boxes decide what North may offer: **industry practice** and **the problem library** (17 problems on offer for insurance). Everything North offers is a suggestion, never your company's own definition. Tick both and click **Next**.

![North options](img/10-wizard-north.png)

### Step 8. Briefing video setting
Choose **The standard briefing video** or **No video**. The video itself is added later; today this only records your choice. Click **Next**.

![Briefing video](img/11-wizard-briefing-video.png)

### Step 9. Approver
Optionally name the person who will approve the charter (you can change it later). Type `approver.harbor-mutual@example.test` and click **Next**.

![Approver](img/12-wizard-approver.png)

### Step 10. Review
You see all your choices on one page. Check them.

![Review](img/13-wizard-review.png)

### Step 11. Save draft
Click **Save draft**. You see "Draft saved." and new buttons appear: **Continue to start the room**, **Save as a template** and **Delete this draft**. You can come back and change a draft until the room is started.

![Draft saved](img/14-draft-saved.png)

### Step 12. Continue to start the room
Click **Continue to start the room**. The session page opens. Look at the address bar: it ends in a long 32-character code (for example `.../sessions/362686b31f0e11ff6e470965c4b690c7`). You need this code in Step 21, so note it. Scroll to the bottom to find **Start the room**.

![Start the room panel](img/15-start-the-room.png)

### Step 13. Start the room
Click **Start the room**, then **Yes, start the room** (once started, the prepared details are read-only). You now see:
- **The link to share**: the join link (a `/join/` address with a short 22-character code). Anyone with it can take a free seat.
- **Seats**: "0 of 3 seats taken", Seat 1, Seat 2, Seat 3 all FREE.
- **Start the briefing**.

![Room started: join link and seats](img/16-room-started-join-link.png)

Note: the join link is shown only on the screen where you made it. If you reload the page it is hidden, and you must use **Make a new link** (the old link then stops working; people already seated stay seated).

### Step 14. Join seat 1 with your own account
Click **Join as a participant**. Because you are signed in, it says you will join with your account.

![Join form](img/17-join-form.png)

Pick **Seat 1**, type your role (for example "Claims analyst") and click **Join**.

![Join form filled in](img/18-join-form-filled.png)

### Step 15. The lobby
You arrive in the lobby. Nira, the guide, welcomes you and says the session takes 20 minutes. It shows "Waiting for the organiser to start the briefing." and "1 of 3 seats taken", with you in Seat 1.

![Lobby](img/19-lobby.png)

### Step 16. Back to the organiser's page
Click **Back to the organiser's page**. Seat 1 now shows TAKEN and YOU, with a **Remove** button.

![Organiser page with seat 1 taken](img/20-organiser-seat-taken.png)

### Step 17. Start the briefing
Click **Start the briefing**. You can start with empty seats; people who arrive later see the briefing first. The page says "The briefing has started."

![Briefing started](img/21-briefing-started.png)

### Step 18. How to reach the briefing page today
There is no button yet that takes you from the organiser's page to the briefing, so type the address yourself:

`http://127.0.0.1:8201/modules/m1_intent/sessions/<session id>/briefing`

Replace `<session id>` with the **32-character code** from the address bar of the organiser's session page (the one you noted in Step 12). Do **not** use the short 22-character code from a `/join/` address; that one does not work here.

### Step 19. The briefing: rules and video placeholder
You see the session purpose as the headline, a countdown ("Time left in this stage"), **Add 2 / 5 / 10 minutes**, a grey box "A short video will appear here" (the video comes later), and "The room rules" in written form: what the session is for, what we want to leave with, how the time is shared, how notes are shown.

![Briefing page](img/22-briefing-top.png)

### Step 20. Timer and Add time
Click **Add 2 minutes**. The clock jumps up by two minutes and the page says "Time added."

![Time added](img/23-briefing-add-time.png)

### Step 21. "I'm clear"
Scroll down. Click **Read the rules aloud** if you want to hear them, then **I'm clear**. It says "You told us you are clear." and "1 of 3 people say they are clear."

![Rules and I'm clear](img/24-briefing-rules-clear.png)

### Step 22. Ask Nira
In "Your question for Nira" type a question, for example "How long do we have in the room?", and click **Ask Nira** (or **What do I do now?**).

**What do I do now?** is answered at once with a fixed message for this stage, with or without a key. A typed question needs the model: with model calls off, Nira answers "Nira is not available yet. The rules on this screen are all you need to begin." **This is expected.** With a model key in `.env`, Nira answers the question from the rules only.

![Ask Nira](img/25-briefing-clear-and-ask-nira.png)

### Step 23. Send everyone to their rooms
Click **Send everyone to their rooms**. You do not have to wait for everyone to be clear. The page says "The rooms are open." and the clock restarts for the individual-rooms stage.

![Rooms are open](img/26-briefing-rooms-open.png)

### Step 24. Open your private room
Type the same session address, ending in `/room` instead of `/briefing`:

`http://127.0.0.1:8201/modules/m1_intent/sessions/<session id>/room`

You see "Your private room". Only you and North can see it. Left: **Talk with North**. Right: **Your note drafts** and **Common problems (suggestion)**.

![Private room](img/27-room-empty.png)

### Step 25. Talk to North (Enter sends)
Click in the box "Write a note in your own words", type something such as "Claims take too long to settle and customers keep calling us to chase.", and press **Enter** (or click **Send to North**).

With model calls off North says "North is not available right now, but your note is saved." **Expected.** With a model key, North replies with a question or reflection.

![Talking with North](img/28-room-talk-to-north.png)

### Step 26. Save as a note, and the read-back
Type another thought ("Claims over 30 days old are rising and nobody owns the follow-up.") and click **Save as a note**. North reads it back in your words ("Here is what I took down... Is that right?") and the note appears under **Your note drafts** with a **Priority** choice (Not set, Must, Should, Could, Not this time). Drafts stay private to you.

![Note saved and read back](img/29-room-saved-note-readback.png)

### Step 27. Correct a note
Click **Correct** on the note. A box opens with the note text and **Send the correction** / **Stop correcting**. Change the words and send.

![Correct a note](img/30-room-correct-open.png)

The note shows the corrected words. The earlier words stay in the conversation on the left as a record.

![After the correction](img/31-room-after-correction.png)

### Step 28. Industry practice card: Add
Save a note that is close to a known industry problem, for example "We cannot tell which customers are likely to lapse next, so we cannot keep them." Under the note a card appears: **Industry practice (suggestion)**, tagged ILLUSTRATIVE, with typical actions and "Your company decides."

![Industry practice card](img/32-room-practice-card.png)

Click **Add to my note**. The card turns into "You added this suggestion to your note:" with the actions listed.

![Practice added](img/33-room-practice-added.png)

### Step 29. Industry practice card: Dismiss
Save another matching note, for example "Leads are not followed up fast enough by the branches."

![Second note with a card](img/34-room-second-note.png)

Click **Dismiss**. The card goes away and the note says "You dismissed the industry practice suggestion for this note."

![Practice dismissed](img/35-room-practice-dismissed.png)

(If you write a note that matches nothing in the pack, no card appears. That is normal.)

### Step 30. Problem library: Use this
In **Common problems (suggestion)** pick a problem and click **Use this**. A box "Reword it in your own words" opens, with a priority choice, **Add as a note** and **Cancel**. Nothing is added until you choose.

![Reword before adding](img/36-room-problem-library-used.png)

Click **Add as a note**. It joins your drafts, marked as coming from the library.

![Library problem added](img/37-room-problem-library-added.png)

### Step 31. A guest joins by the link (second, signed-out window)
Make a new link on the organiser's page (Step 13 note) and copy it.

![Organiser page: a new link](img/49-organiser-reload-link-hidden-then-new.png)

Open a **private/incognito window** (so you are signed out) and paste the link. No account is needed.

![Guest join form](img/50-guest-join-form.png)

Pick Seat 2, type a name and a role, and click **Join**.

![Guest join form filled in](img/51-guest-join-filled.png)

The guest lands in the lobby. Because the briefing already started, it says "You arrived after the lobby, so you will see the briefing first."

![Guest in the lobby](img/52-guest-lobby.png)

Today a guest reaches the lobby only. If the guest types the briefing address, they are sent to the sign-in page.

![Guest cannot open the briefing yet](img/53-guest-briefing-refused.png)

Back in your window, reload the organiser's page: "2 of 3 seats taken".

![Organiser page, two seats](img/54-organiser-two-seats.png)

---

## Part 2. Tidewater Capital analyst (asset management), short version

Sign out, then sign in as `analyst.tidewater-capital@example.test` (password in your seed file). Tidewater has five modules in its package.

![Tidewater modules](img/60-tidewater-modules.png)

Open Intent and **Prepare a session** as before (this time choose "1 person", a solo session). In the North step, the problem library offers asset-management problems instead of insurance ones.

![Tidewater North options](img/61-tidewater-north-options.png)

Save the draft, continue, start the room, join Seat 1, start the briefing, and open `.../briefing` with the new 32-character session id. Same briefing, with Tidewater wording.

![Tidewater briefing](img/62-tidewater-briefing.png)

Click **I'm clear**, **Send everyone to their rooms**, then open `.../room`. The suggested problems are about net flows, AUM, redemptions, distributors and fees. Insurance wording (leads, agents, policies) must not appear.

![Tidewater private room](img/63-tidewater-room.png)

---

## Part 3. Lakeside Family Office analyst (family office)

Sign in as `analyst.lakeside-family-office@example.test` (password in your seed file). Lakeside is an illustrative family office with the same package as Harbor Mutual (Discover: three modules). Its industry knowledge comes from the family-office pack, copied from the earlier product's family-office work (synthetic test pack, not reviewed by a family-office practitioner).

Prepare a session, switch on **Let North offer industry practice**, save, continue, start the room, join Seat 1, start the briefing, click **I'm clear**, **Send everyone to their rooms**, then open `.../room`.

In the room type: "Can we fund the capital calls over six months?" and press Enter.

- **With a model key in `.env`:** North leads with a short recommended draft, for example the funding-headroom and stress-funding measures, how often family offices usually check them and how they are usually split, every line starting "Industry practice (suggestion):" and ending "Your company decides." Then at most one question. It never gives a target, a reserve amount or a figure you did not say.
- **Without a key:** North says it is not available, as in Step 25. The note is saved, and the **Industry practice (suggestion)** card on the note still appears from the pack.

Also try: "We spend days preparing the investment meeting pack", "I do not trust our valuations, some are stale", "Our concentration in one issuer worries me". Each should offer the matching family-office measure. Insurance or asset-management wording must not appear.

Nira now answers "what do I do now", the welcome and the time warning with fixed messages, with or without a key. Only a typed question to Nira needs the key.

---

## Look and feel: the new screens next to the earlier product (M1-UI1)

The module 1 screens now use the earlier Signal Harbor's own markup and stylesheets: the light top bar with the lighthouse mark and tagline, the navy left rail, page titles in Fraunces with a teal label above, panels with a teal eyebrow, agent chips for North and Nira with the status ring, yellow sticky notes for your notes and for the room rules, copper stickies for North's suggestions, the journey bar in the Prepare wizard, seat tiles in the lobby like a game lobby, and the charter laid out as a document with a signature block. In each pair below the **earlier prototype** is on the left in the file name (`-old`) and the **new screen** is `-new`. The earlier screens show the same made-up family-office example (capital calls, exposure) as the rest of this guide.

Notes on what you see:
- **Prepare** has no earlier screen to put beside it (the earlier product had no Prepare step), so only the new screen is shown, in light and dark. The Charter step shows the charter as a document with "Not signed yet".
- **The problem library panel is shown in the private room only if the organiser switched "Let North offer the problem library" on in Prepare.** The default is off: North listens and checks.
- **Private room:** the timer, "Ask Nira how this works" and "Ask North how others do it". The North button only fills the box with a question; nothing is sent until you press Send.
- **Briefing:** "Read the rules aloud" now uses the same speech as the private room. Without speech set up it says so in one line.

Prepare (new): ![Prepare, light](img/compare/prepare-light-new.png) ![Prepare, dark](img/compare/prepare-dark-new.png)

Lobby, light: ![earlier](img/compare/lobby-light-old.png) ![new](img/compare/lobby-light-new.png)
Lobby, dark: ![earlier](img/compare/lobby-dark-old.png) ![new](img/compare/lobby-dark-new.png)

Briefing, light: ![earlier](img/compare/briefing-light-old.png) ![new](img/compare/briefing-light-new.png)
Briefing, dark: ![earlier](img/compare/briefing-dark-old.png) ![new](img/compare/briefing-dark-new.png)

Private room, light: ![earlier](img/compare/room-light-old.png) ![new](img/compare/room-light-new.png)
Private room, dark: ![earlier](img/compare/room-dark-old.png) ![new](img/compare/room-dark-new.png)

Module home (new): ![Intent Centre home](img/compare/home-light-new.png)

On a phone (375 px, new): ![Prepare](img/compare/phone-prepare-purpose-new.png) ![Lobby](img/compare/phone-lobby-new.png) ![Briefing](img/compare/phone-briefing-new.png) ![Private room](img/compare/phone-room-new.png)

## Nira docked on every screen, and North's interview transcript (M1-UI2)

**Nira** is now a panel docked on the right of every module 1 screen (Prepare, the session page and lobby, briefing, private room, board, back in the room, charter), as in the earlier product. On a wide screen it opens by itself and the page keeps clear of it. On a phone (under 768 px) it is a round button at the bottom right: press it to open the panel as a sheet, and the cross to close it. Ctrl or Cmd and J opens and closes it; Escape steps back.

What to check on each screen:
1. The head shows Nira, "Your single point of contact", **Voice mode** (greyed out when speech is not set up), an expand button (docked full height or a smaller floating panel) and a close button.
2. A teal box says what this step is; an italic line says what Nira is doing ("Nira is here with you at this step", "Nira is thinking about your question" while she answers).
3. Four sections, each opening and closing, and remembered in your browser: **About Nira & this step** (her welcome for this session), **What's needed at this step** (Prepare: the six answers; lobby: who is here; briefing: "I'm clear"; private room: your notes; board, together and charter: their actions), **What am I looking at?** (one paragraph per screen) and **Suggested actions** (the next step you may take, and "What do I do now?").
4. **See the guided flow** leads to the Intent Centre (not shown to a person who joined by link).
5. Type under **Ask Nira...** and press Enter (Shift+Enter is a new line), or use the microphone. The answer appears in the conversation. Under the box: "Audio is transcribed and not stored."
6. On Prepare before the first save, Nira explains the screen but says to save the draft first before she can answer questions.

**North's interview transcript** (private room): the panel is headed "North · the industry expert" with the title "Interview transcript", and every turn is kept as a card with the speaker, the time and the words. Nothing that was there before has gone: the read-back, Correct, Save as a note, "Ask North how others do it", the notes list, voice and the timer.

**Ending the private room early** (new in this package): under "Your turn" there is **I'm done**. It asks once: "Submit your notes and leave your room? You can't add notes after this." On yes it submits your remaining drafts (and only yours), then shows "Your notes are in. The board opens when the rooms close." and moves on to the board by itself when the organiser closes the rooms. The organiser also has **Close the rooms now**, with its own question; it moves everyone to the board. A participant does not see that button.

Nira, old and new (the earlier panel is on the left; its wording was replaced with family-office examples): light ![Nira, light](img/compare/nira-panel-old-vs-new-light.png) dark ![Nira, dark](img/compare/nira-panel-old-vs-new-dark.png)

North's transcript, old and new: light ![North, light](img/compare/north-studio-old-vs-new-light.png) dark ![North, dark](img/compare/north-studio-old-vs-new-dark.png)

New screens, light and dark: Prepare ![](img/nira-prepare-light.png) ![](img/nira-prepare-dark.png) Lobby ![](img/nira-lobby-light.png) ![](img/nira-lobby-dark.png) Briefing ![](img/nira-briefing-light.png) ![](img/nira-briefing-dark.png) Private room ![](img/north-studio-light.png) ![](img/north-studio-dark.png) Board ![](img/nira-board-light.png) ![](img/nira-board-dark.png) Back in the room ![](img/nira-together-light.png) ![](img/nira-together-dark.png) Charter ![](img/nira-charter-light.png) ![](img/nira-charter-dark.png)

All sections open: ![](img/nira-briefing-sections-open.png) Phone, closed and open: ![](img/nira-briefing-phone-collapsed.png) ![](img/nira-briefing-phone-open.png) "I'm done" question: ![](img/north-studio-done-confirm.png)

## Company context: documents for North (M1-CTX)

The company administrator can give North background to read: an investment policy, a capital call schedule, a manager list.

1. Sign in as `company_admin.lakeside-family-office@example.test` (password in your seed file). In the left rail, under **Your company**, click **Company context**.
2. Under **Upload a document**, choose a Word (.docx), text or Markdown file, give it a title such as "Investment policy", and press **Upload**. Within a moment it appears under **Documents for this agent** with the status **Ready**.
3. Try a picture (.png or .jpg). It is refused with "Pictures are not supported yet." A PDF is refused too unless a PDF reader is installed on the machine.
4. Type a short summary beside a document and press **Publish summary**. Only that summary is then visible to other agents; the document's own text is not.
5. Press **Remove** beside a document to stop North using it. Its text is deleted.
6. Sign in as `analyst.lakeside-family-office@example.test`. The page shows the list only, with a note that the company administrator adds and removes documents.

### What data the family-office company has (M1-DATA)

Illustrative Lakeside Family Office starts with five synthetic documents already in **Company context**, titled "Illustrative: ...": committee minutes, a diligence checklist, a distribution notice, a manager email and a meeting transcript. Every company, fund and figure in them is invented. Run `python tools/seed.py` again and nothing is added twice. The other three companies have none. Two more kinds of file are readable now: web pages (.html) and emails (.eml, the text only). The six PDFs of the same test pack are not loaded, because no PDF reader is installed; save one as text to try it. The adversarial test file is not a demo document, it is only used in the automated tests. The family-office pack also carries more suggestions (clusters, data feeds, market sources, a Singapore brief); these are what others in the industry usually track, not the company's own policy.

What North does with it: for each question it reads at most three short passages that fit, shown to the model as quoted background with names replaced by tokens. A document is never an instruction and never a source of a figure, so a number in a document is not repeated as a recorded fact. The memory review (**Pending memories**) is empty until North starts proposing memories.

---

## What is not ready yet

- **Links between screens (next package, M1-P05):** there are no buttons yet from the organiser's page to the lobby, the briefing or the room. You type the addresses, as in Steps 18 and 24. Guests can reach the lobby only; guest access to the briefing and the room also comes with M1-P05.
- **Later packages:** the full note form, anonymous notes, voice, the shared board, voting, the charter and sign-off, and the hand-off to module 2.
- Nira and North answer only when a model key is set in `.env`. The briefing video is a placeholder.

## If something looks wrong

- **Restart:** press Ctrl+C in the window running `tools/dev.py`, then run it again.
- **Cannot sign in:** your sign-in details are in `data/_control/seed_credentials.txt`. To issue new passwords run `python tools/seed.py --reset-credentials`.
- **Switch model calls off:** put `SH_MODEL_PROVIDER=off` in `.env` and restart. North and Nira then say they are not available, and everything else still works.
- **Briefing or room page is blank or asks for sign-in:** check you used the 32-character session id (not the short join code) and that you are signed in.

## The two addresses

- **http://127.0.0.1:8201** : the screens (UI). Use this one.
- **http://127.0.0.1:8200** : the engine behind it (backend).
