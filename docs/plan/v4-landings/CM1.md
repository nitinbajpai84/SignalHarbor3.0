# CM1: comments with history

A comment hangs on one thing a person can see. It can be replied to, edited and deleted, and nothing is lost: an edited comment says "edited" and keeps its earlier wording; a deleted one says "deleted by X" and shows no words (the words stay in the file). `@Name` (a name from the company people list) puts a card on that person's Today, only if they can see the thing too. "Raise as a case" opens an Action case, "Raise as a ticket" a ticket for a point that is not about money; the thread shows the case link and the case shows the comment in its history.

## Files (all new)

- `sh_platform/v1/n2_comments.py` (logic, storage `comments/events.jsonl` in the company plane, append-only; Today card source registered on import)
- `sh_platform/v1/n2_routes.py`, `sh_platform/v1/n2.permissions.yaml` (auto-installed by `v1.install`; nothing to mount on the backend)
- `ui/src/v1/n2/Comments.tsx`, `ui/src/v1/n2/api.ts`, `ui/src/v1/n2/n2.test.tsx`
- `tests/v1/test_n2_comments.py`

## Who sees a thread (same rule as the thing, checked on every read and write)

| Target kind | id | Rule |
|---|---|---|
| dashboard | `dash-xxxx` | `cx_dash.may_view`, or company-wide with data access |
| widget | `dash-xxxx/<tile id>` | its dashboard |
| office_line | `<portfolio id>/<instrument id>` | E1d level on the portfolio |
| brief_line | `<portfolio id>/<line key>`, or `company/<line key>` for a total | portfolio level; `company/` needs every portfolio |
| case | case id or CASE-0001 | `e4_cases._can_see` |
| valuation, position, cash, nav, metric, tile | the trail id | `a5_trail.trail` itself (refuses what the person may not see) |

A raised case copies the line's portfolio, so people who see the line see the case. A case from a dashboard or a trail figure has no portfolio, so only its maker and admins see it (fails closed).

## Mount lines for the orchestrator (UI only)

Import once per file: `import Comments from "../n2/Comments";`

1. `ui/src/v1/cxui/DashboardView.tsx`, in the returned `PageFrame` after the tiles block (about line 21):
   `<Comments target={{ kind: "dashboard", id: board.id }} />`
2. Each tile in `ui/src/v1/cxui/TileCard.tsx` (widget on a dashboard) and `ui/src/v1/b7/Canvas.tsx` (studio widget, next to the `TileCard` at line 60):
   `<Comments target={{ kind: "widget", id: `${did}/${tile.id}` }} />`
3. Office view, `ui/src/v1/k4/OfficePage.tsx`, in the holdings row where `k = `${p.portfolio_id}:${l.instrument_id}`` (line 73):
   `<Comments target={{ kind: "office_line", id: `${p.portfolio_id}/${l.instrument_id}` }} />`
   and for the issued-against-known rows (line 113, `l.line_key`): `<Comments target={{ kind: "brief_line", id: `${p.portfolio_id}/${l.line_key}` }} />` if the row has its portfolio.
4. Brief, `ui/src/v1/e5/BriefPage.tsx`, last cell of the row (line 66): `<td>...<Comments target={{ kind: "brief_line", id: `${l.portfolio_id ?? "company"}/${l.key}` }} /></td>`.
   Open point: `BriefLine` in `e5/api.ts` does not carry `portfolio_id` yet. Until `e5_brief` sends it, use `company/<key>`, which only a person who sees every portfolio can open.
5. Case page, `ui/src/v1/a5/CaseView.tsx`: `<Comments target={{ kind: "case", id: caseId }} />`.
6. Trail panel, `ui/src/v1/a5trail/TrailPanel.tsx`, under the steps: `<Comments target={{ kind, id }} />` (kind is the trail kind).

Each `<Comments>` is one small button when closed and asks the server only when opened, so a page of many lines makes no extra calls.

## Check

- Backend: `pytest tests/v1/test_n2_comments.py -q` (18 passed)
- UI: `npx vitest run src/v1/n2` (2 passed); `npx tsc --noEmit` shows no error in `v1/n2`

## Open points

- Ticket link: a ticket has no page to link to yet, so the thread shows "Ticket TCK-0001" without a link.
- Mention card has no link for kinds without a page route (office or brief line, trail figures); it opens Today only.
- A mention is checked for access when written; a later loss of access does not withdraw the card (delete the comment to withdraw it).

## Review (10 Oct, reasoning reviewer)

Verdict: pass after three fixes in `sh_platform/v1/n2_comments.py` (backups in `.sh-tmp/*.bak-ovn`).

- Access: every read and write goes through `check`, which fails closed (403, no words, no count). Edit is author-only; delete is author or admin, and both must see the thing first. Mentions are told only when they may see the thing. Correct.
- History: append-only events; edits keep every earlier wording in order; delete hides words and history in the thread but keeps them in the file. Correct.
- Fixed, leak: "Raise as a ticket" assigned the ticket (which carries the comment words) to the first @named person even when that person could not see the thing. Now it goes to the first named person who may see it, otherwise to the raiser. Test `test_ticket_never_goes_to_a_person_who_cannot_see`.
- Fixed, copy: the Today card read "on a office line"; now "on the office line". Test `test_mention_card_reads_plainly`.
- Fixed, cost: `pulse_cards` re-read the events file once per edit on every Today load; now reads it once.
- Figures: comments state no figures, so there is nothing to check against the answer key.
- Runs: `pytest tests/v1/test_n2_comments.py -q` 20 passed; `npx vitest run src/v1/n2` 2 passed; `tsc --noEmit` no errors in `src/v1/n2`.
