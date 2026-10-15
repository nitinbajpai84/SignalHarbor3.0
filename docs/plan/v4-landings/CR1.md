# CR1: Action is only to-dos, Consume is everything to read

Rule from Nitin (9 Oct): Intent is where a project or intent starts. Action holds only what the person must do or act on. Consume holds company reports, what was shared with the person, and outside data. Nothing was dropped; every item moved and every old path still opens.

## Moved items

| Item | Before | After | How to see it |
|---|---|---|---|
| Projects today (/centre/home) | Action tab | Build projects page header link | /centre/build, first link above the project list |
| Evidence (/centre/action/evidence) | Action tab | Consume > Company reports > "Statements and evidence" | /centre/consume; the route and /centre/action/evidence/:id still open |
| Office view and CIO Brief (/centre/consume/office) | Link under the Action tabs | Consume > Shared with you > "CIO Brief", and Consume > Company reports > "Office view" | /centre/consume |
| Review queue (/centre/extract/review) | Loose link under the Action tabs | Action tab "Review queue" | /centre/action, sixth tab |
| Action tabs | Projects today, Today, Cases, Reconciliations, Managers, Tickets, Evidence | Today, Cases, Reconciliations, Managers, Tickets, Review queue | /centre/action |
| Managers, Benchmark, Signed KPIs and offers | Flat Consume link row | Consume > Company reports | /centre/consume |
| Library (/centre/library) | Account menu only | Also Consume > Company reports | /centre/consume |
| Business views, feeds, market, what-if; Offers | Flat Consume link row | Consume > Outside data and insights | /centre/consume |
| Shape what you see | Flat Consume link row | Beside the project list ("Your projects") | /centre/consume |
| Start a project | Build empty state said "Sign an intent in the Intent Centre" (no link) | "Start a new intent" link to /centre/intent in the Build header and empty state | /centre/build |
| Consume subline | "Pick a project to see its dashboards, or ask Lumen for a new one." | "Everything to read: company reports, what was shared with you, and outside data." | /centre/consume |
| Bar tooltips | Intent "Say what you need", Action "What needs you today", Consume "Reports and dashboards" | "Start new work", "Things to do", "Reports and insights" (names unchanged) | Hover the bar names |

## Gap

There is no list of dashboards shared with the person: the Consume API lists dashboards by project only, and a shared dashboard opens from its own link (/centre/consume/d/:id). "Shared with you" therefore shows the CIO Brief (via the Office view) only. A "shared with me" endpoint would let it list those dashboards.

## Files

ui/src/v1/a5/ActionCentre.tsx, ui/src/v1/a5/routes.tsx (comment only), ui/src/v1/cxui/ProjectList.tsx, ui/src/v1/b6/ProjectsPage.tsx, ui/src/shell/copy.ts; tests in a5.test.tsx, cxui.test.tsx, b6/links.test.tsx, shell/shell.test.tsx. Backups in .sh-tmp/*.bak-cr1.

## Checks

npx vitest run src/v1/a5 src/v1/cxui src/v1/b6 src/shell: 10 files, 63 tests pass. npx tsc --noEmit: clean.

## Review

Verdict: pass. Checked every item in the table against the code. Action has exactly the six to-do tabs; /centre/home, /centre/action/evidence, its detail route, /centre/action/managers, /centre/tickets and /centre/extract/review are all still mounted. Consume shows the three groups, every moved link is present, none dropped. Build has "Projects today" and "Start a new intent"; no project creation is offered outside Intent. Tooltips changed, names kept. Vitest (a5, cxui, b6, shell): 10 files, 63 tests pass; tsc clean. Intent files untouched; backups exist. No defects found. Open gap stays: no "shared with me" dashboards list.
