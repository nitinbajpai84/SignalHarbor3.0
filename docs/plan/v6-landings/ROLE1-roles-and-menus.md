# ROLE1: roles and menus (12 Oct)

Mei Chen is a business owner, not the data team. Each person now sees only the Settings items, centres and tools of their own role. Nothing was deleted: items are hidden from a role, never removed for everyone, and the server stays the real gate.

## Who holds what (Evergreen seed, `tools/seed_evergreen.py`)

| Person | Roles | Seat |
|---|---|---|
| Daniel Foo | sponsor | decision maker |
| Mei Chen | owner (was analyst) | business owner: talks to North, reads Consume and Map, acts on her Action items |
| Raj Patel | approver | approver |
| Anita Rao | analyst + head_of_data | head of data: approves packs, plans, model changes |
| Leo Park | analyst | data engineer + ops manager (architect, data engineer, ops seats) |
| Grace Ong | company_admin | administrator |
| Sofia Reyes | participant | risk owner, as before |

An already-seeded environment is moved too: `seed_evergreen.accounts()` swaps Mei from analyst to owner (new `AccountStore.set_roles`). `seed_10uc.py` still writes the history as the ops analyst she was in the story (a seed-time viewer only; her account is the owner). Role assignment stays in the existing account code, so any seed that calls `seed_evergreen.accounts()` picks it up.

No new roles were added: `analyst` keeps meaning the data team in `route_permissions.yaml` and the `*.permissions.yaml` files (too widely used to narrow safely). The menus tell the engineer from the head of data by the `head_of_data` role.

## Settings by role (`settingsFor` in `ui/src/shell/roles.ts`)

| Item | Everyone | Head of data | Data engineer | Approver | Administrator |
|---|---|---|---|---|---|
| What the agents remember about you | yes | | | | yes |
| Testing or Real use (and the header switch) | yes | | | | yes |
| Activity trail (was Signed register) | own activity | all | all | own | all |
| Rules | | yes | | yes (read, P15) | yes |
| Identifiers and other names | | yes | yes | | yes |
| Instruments and asset classes | | yes | yes | | yes |
| Sources and data model | | yes (decides) | view and propose | | yes |
| Connectors, Jobs and events | | | yes | | yes |
| Delivery channels, People and access, Intent admin, Templates and skills, Outside assistants, Agent runs and cost, Demo | | | | | yes |

Mei, Daniel and Sofia see three items; Raj four; Anita seven; Leo eight; Grace sixteen. A head of data is not also shown the engineer's tools. Everyone with a company role now opens Settings (the account menu lists the person's own sections).

## Centres

- Sponsor, owner, approver, participant: Action, Build (their own intent and steps, projects they may read), Consume, Map (read only). The Build sub-nav shows no Operations; the "Ops" and "Data intake" links on the project list show only for the engineer and admin.
- Head of data adds the approvals (design pack, build plan, verified map, model changes).
- Data engineer and ops add Operations, Pipelines, Connect an API (under Connectors).
- Action no longer asks for reconciliations, figures to confirm or the map review of a role the server refuses, and hides those groups and chips for them (the business owner).

## Pulse removed as a destination

`/centre/home`, `/centre/pulse`, `/centre/today` and `/pulse` all go to `/centre/action`. The "Viewing as" seat switch is gone from the folded "Everything Tally flagged" list (which stays on Action). "Back to Pulse" is "Back to Action"; "Requests to use files" stays reachable from Action. The page files are kept (never-drop), only unreachable as destinations.

## Activity trail

The old Signed register is renamed "Activity trail". It lists signed intents, measures, rules and plans plus the newest 40 runs from the run log (`sh_platform/v1/run_log.py`). The data team (analyst, head of data, admin) sees every row; anyone else sees only rows with their own name. Case actions are not in it yet (pending).

## Server changes (small, and only these)

- Model-change approval and rejection (`e0a_catalogue.approve/reject`) now need the head of data seat (head_of_data or company_admin), not the architect seat. The engineer still proposes. Design pack and build plan approvals were already head-of-data only.
- `t1.permissions.yaml`: the business owner may read templates (list, one, examples, an intent's template), read only. Without it North's start screen lost its template choice for her.
- `register.py`: run rows, and own-activity filtering for non-data roles.
- Nothing else widened. Studio, audience picker, reconciliations and the architect tools stay closed to the owner: she reads and asks for dashboards in Consume (Lumen), and the sponsor or head of data approves them.

## Audit: nothing deleted for everyone

Every Settings section still exists and is reachable by the roles that had it, except as follows (hidden, not removed): Signed register is renamed, not removed; Settings sections "Delivery channels" and the rest of the admin list are now admin-only in the menu (they were already server-gated); Rules stays for the approver; the data model was readable by every analyst and still is. The Pulse page and its components remain in the source. No route, permission row or API was removed.

## Departures to know about

1. Delivery channels: the matrix gave it to the data engineer, but the server refuses everyone except the administrator (it sets egress hosts, pinned by `test_d1_delivery`). Leo's menu does not show it. Say so if you want it opened.
2. Leo's Sources and data model is "view" for approving, but he can still propose a change (the old behaviour; agents propose too). Say so if you want proposing hidden.
3. Approver keeps Rules (existing P15 behaviour and test).
4. The browser e2e scripts in `tests/e2e_10uc/` still sign in Mei as the analyst (`uc10a_1.py` and others); they are not in the pytest run and were not updated.

## How to test

- Seed: `python tools/seed_10uc.py --data-root <dir>`; sign in as each person and open Settings. Screenshots: `docs/plan/v6-landings/role1-settings-{mei,anita,leo,admin}.png`.
- Mei: Action, Build, New project (talk to North), Consume, Map all load; her Settings has three items; `/centre/connectors` style pages send her back to Action.
- `pytest tests/v1/test_role1.py tests/v1/test_e0a.py tests/graph/test_register.py tests/auth -n 4`
- `cd ui && npx tsc --noEmit && npx vitest run src/shell src/v1/s1 src/v1/a5 src/v1/e5 src/v1/b6`
- Backups of every edited file: `.sh-tmp/<name>.bak-role1`. Test env: `.sh-tmp/testenv/role1/` (port 8611, own data root).
