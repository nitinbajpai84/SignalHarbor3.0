# Talk to all agents (9 Oct)

Decision: every signed-in role (company_admin, sponsor, analyst, owner, approver, participant) can talk to North, Span and Lumen. Talking is asking; acting stays with the role that owns the action.

## What changed
- Permission lines opened to all six roles: `POST /api/v1/build/p/{pid}/chat`, `POST .../consume/p/{pid}/dashboards` (own dashboard), `POST .../dashboards/{did}/ask`, `POST /api/v1/consume/brief/{iid}/chat`, `POST /api/v1/build/{iid}/blueprint/chat` (and its GET). New project-free lines: `POST /api/v1/build/chat` (Span) and `POST /api/v1/consume/chat` (Lumen). Approve/propose/run/accept/reject/share/schedule lines untouched.
- Span (`b6_span.chat`, `b6_routes.post_chat`): no data-team refusal; read access to the project is enough. Questions are answered from the plan and catalogue in plain words (`explain`: sources, bronze/silver/gold, core model, columns, what feeds what). A change request from someone outside the data team is stored as a pending suggestion (`suggestion: true`); the "yes/no" shortcut only accepts or rejects for the data team, others are told the head of data will see it. Accept/reject routes unchanged.
- Lumen (`cx_lumen.ask`, `cx_dash.own_dashboard`): a question ("what is the data model", "how many reports") is answered in words from the project's gold tables (names, purpose, column names, dashboards visible; no rows or figures) with a pointer to Build > Span. A tile asked for on a dashboard the person did not make is created on their own dashboard ("My dashboard", private until shared); the reply carries `dashboard_id`. A request that matches no figure now gets the same description plus the available figures, not "Name one of them" alone.
- North brief chat (c3) and blueprint chat (a1): the routes refused by role; now open. For people who are not designers (c3: analyst, company_admin, sponsor) or the architect seat (a1) the agent answers and keeps the turn, but does not run steps, merge the brief/design, propose patches, or take a "yes/no" as acceptance.
- Project-free talk (`sh_platform/v1/talk.py`): answers about the company model, the projects the person may read, and their tables and dashboards. A project the person cannot open is described by what the lock row allows (title, stage, owner when Internal; only that it exists when Restricted) and who to ask. Project chat in Build and the Lumen ask route do the same instead of a 403. Answers are not stored (no thread).
- UI: composers were already visible to everyone in Build and Consume; Span's blueprint `can_talk` is true for all. New `TalkBox` ("Talk to Span" on the Build landing, "Talk to Lumen" on the Consume landing). Consume project page opens the returned `dashboard_id` after an ask.

## How to see it
Log in as Sofia Reyes (participant). Consume > a project > ask Lumen "Can you please tell me the current data model of performance reporting?" (answer in words). Ask for "net worth by entity per month": the tile appears on her own dashboard. Build > a project > ask Span the same question; type "add a weekly gold table by currency" and see it stay a suggestion. Log in as the data team to see the suggestion and accept it. Try the TalkBox on /centre/build and /centre/consume.

## Not done / known limits
- The intent-based chats (c3 brief chat, a1 blueprint chat) still get the project access gate for a Restricted project (403 from `intent_gate`/`check_agent`); use the project-free Span/Lumen box for those. 
- Project-free answers are stateless and rule-worded (model off path); no model call yet.

## Tests run
- `pytest tests/v1/test_b6*.py tests/v1/test_cx*.py tests/v1/test_c3*.py tests/v1/test_a1*.py tests/v1/test_talk_to_all.py`: 62 passed (new: `tests/v1/test_talk_to_all.py`, 7 tests: participant talks to Span and Lumen, cannot approve/accept, change request pending until the data team accepts, own-dashboard tile, locked project in words, talk lines open and action lines closed, route-vs-permission audit of every /api/v1 route). `test_c3` participant case changed from 403 to 200 (talk is open).
- `npx vitest run src/v1/talk src/v1/b6 src/v1/cxui src/v1/c3 src/v1/a1`: 19 passed. `npx tsc --noEmit` clean.
- Route audit: every /api/v1 route has a permission line (test above passes).
- Backups: `.sh-tmp/*.bak-talk`.
