# Module 1: Intent Centre

Turns a room of up to ten people into a signed charter and the first business graph. Agent: North, the industry expert; Nira coordinates.

- Spec: `docs/specs/MODULES-1-2-FEATURE-SPEC.md`, features M1-01 to M1-31 and X-xx. Screens: `docs/specs/Module 1 Intent Centre workflow and screens.pptx`.
- Flow: prepare, create room and invite by link, lobby, briefing, private rooms, brainstorm board (only after the rooms close), back in the room (tick clusters, priority), sign or send to the C-level approver, hand-off to module 2.
- Each participant's private conversation is visible only to its author. Anonymous is a per-note choice.
- North may suggest only what others in the industry usually track, labelled as a suggestion, from the company's own industry pack.
- Notes are accepted only while the private rooms are open.
- One person can run the whole module alone.
- Lean defaults (LI-M1, all on by default; the old paths remain): Prepare is drafted from the company profile (`domain/profile_draft.py`, in `/lists`); a person's one interview becomes unconfirmed note drafts in their own room (`contracts/interview_notes.yaml`, only for the interview of the profile person explicitly linked to the signed-in account: `people.<pid>.account_id`, A-043; never by display name, slug or a name typed at a seat; an unlinked person's room opens empty; the door refuses a seat name only when it equals the name of an unrestricted person linked to a different enabled account; Prepare reads the profile with the same viewer as the kernel, shared-name flag included); North writes note cards from the conversation (`POST /room/notes {"from_conversation": true}`); every timed stage ends by itself, and the rooms, briefing and together stages close early when everyone seated says "I'm done" (`POST /room/done` for the rooms: any seated person but the organiser, the roles of briefing/confirm); the vote rule in `contracts/board.yaml` `auto_tick` ticks the charter groups and the organiser only breaks ties or removes one; one signature (two stay a choice in Prepare); `inputs` counters (numbers only) sit in the session record.
- Output: the signed charter and the business graph, written to the company plane. Module 2 reads only these.
