
## Review (reasoning reviewer, 11 Oct)
- Contract with package 1: V5W-1 now landed; `b9/api.ts` matches `p2_routes.py` (`GET .../assignments`, `GET .../assign/candidates` -> `{people}`, `POST .../assign` accepts `note` and `handover: true`; step ids architecture/pipelines/dashboards). No change needed.
- Defect fixed: `shell/redirects.ts` sent `/centre/intent/new` (the i3 New intent page, with `?type=` and `&draft=` links from IntentNew, IntentAdmin, IntentBacklog, MemoryOpening, OpportunitiesPanel, SeriesHome) to `/centre/build/intent/new`, which opened a conversation for an intent called "new". Added "new" to INTENT_PAGES; added the case to `shell/shell.test.tsx`. Backups: `.sh-tmp/*.review.bak-v5`.
- Access: default deny holds. b9 routes gate on Build or Intent centre; b6 `/centre/build` opens to Intent roles too; b8 rooms stay Build-only; ROLE_TABLE untouched. Assignment rights are enforced on the server (`can_manage`: owner or company admin).
- Open (minor): the overview shows Assign / Hand over to analyst and company_admin, while the server allows the project owner or company admin. A project owner who is not an analyst does not see the button; an analyst who is not the owner sees it and gets the refusal. Fix when the project record carries a `can.assign` flag.
- Open (minor): Intent-only roles see "Go to step" on cards for steps 2-4 and are bounced by the room gate; hide the link for them or leave as is.
- Egress: the explainer does a same-origin HEAD on `/static/explainer.mp4`; nothing leaves. No model calls. Maker-never-checker not touched (assigning is not approving).
- Tests: `vitest src/shell src/v1/b9` 59 passed; `src/v1/b6 b8 i6 p3 i3` 44 passed.
- Verdict: pass after one fix.
