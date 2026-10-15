# Prompt: phase 1, the platform kernel

Paste everything below the line into a the build session opened in `<2.0 repo>`.

---

You are the orchestrator for **phase 1 (platform kernel)** of Signal Harbor in this repo. Work autonomously until it is done. Do not ask me questions; decide, record, and continue.

## Read first (in this order, nothing else until you need it)
1. `CLAUDE.md`, then `.claude/rules/` chapters as your task needs them
2. `docs/decisions.md` (D-001 to D-025 are settled; they override the spec where they differ)
3. `docs/reuse-map.md` (what to copy, reshape, rebuild, create)
4. `docs/architecture/` (platform, egress and packages diagrams)
5. `docs/specs/MODULES-1-2-FEATURE-SPEC.md` sections 1 to 8 only (rules, agents, roles, screens, data model, contracts)

The old product is at `<earlier repo>` (commit 3a798cc5). It is read-only source: copy and reshape from it, never write there, never merge it. Use `graft` there to find code.

## Added after the first draft of this prompt
- **Look and feel (D-027).** The earlier product's stylesheets and brand marks are already copied into `ui/src/styles/legacy/` and `ui/public/brand/`. P1-05 must use them: read `docs/design/legacy-css.md` and follow its seven steps. Do not invent a new visual style.
- **Sessions link to outcomes (D-026).** The platform needs a generic "process record": every module session has an id, a state, and a link to its outcome record, created when the session starts as "in progress", and queryable both ways. Build this in P1-02 (company plane) so modules 1 and 2 only fill it in.

## Task
Build the platform kernel that modules 1 and 2 will sit on. Nothing module-specific yet.

| Package | What | Reuse |
|---|---|---|
| P1-01 Scaffold | Python 3.11 backend (FastAPI), venv, pytest config, React + TypeScript UI in `ui/` (Vite), `tools/` entry points, `.claude/launch.json` | new |
| P1-02 Company plane | One isolated data plane per company under `SH_DATA_ROOT`; every path resolved from the signed-in company; cross-company reads fail closed | reshape `sh_platform/workspace.py` |
| P1-03 Sign-in and access | Sessions, CSRF, roles (include `approver`), permission per route with default deny, **redirect to login when a session expires**, separate test accounts per agent | reshape `webapp/backend/authz.py` and the sign-in code in `main.py` |
| P1-04 Entitlements and manifests | `manifest.yaml` loader, per-company module switch, module gate (menu, route, tool registry), package catalogue (Discover 1-3, Build 1-5, Run 1-6) | new |
| P1-05 Shell | React home page of module tiles (only owned modules), wizard frame, login, plain-word copy, five screen states | rebuild |
| P1-06 Egress | Egress gateway: internet off by default, destination allowlist, log; minimiser; pseudonymiser with name vault (D-007); under-five rule on aggregates | new, model path reshaped from `agents/gateway.py` |
| P1-07 Agent runtime | Context-pack builder, read-only tool loop, tool registry, number-to-fact guard, evals harness, run registry | reshape `emitters/agent_brain.py`, `emitters/evals/` |
| P1-08 Packs | One pack loader (industry is always a parameter); insurance and asset_management packs copied in; empty-industry state | reshape three old loaders, copy `templates/` |
| P1-09 Doctor and seeds | `tools/doctor.py` extended (ports, data root, keys); synthetic seed for two companies in two industries plus one empty company | extend |
| P1-10 Smoke | `/smoke` suite: two industries, empty company, solo user, switched-off module refused, cross-company read refused | new |

Order: P1-01 first; then P1-02, P1-03, P1-08 in parallel; then P1-04, P1-06, P1-07; then P1-05, P1-09; P1-10 last. Split a package if it is too big; never merge two.

## How to work
- Write each package's brief (JOB, OWNS paths, acceptance criteria, tests to run) to `docs/ledger/<ID>/brief.md` and list it in `docs/ledger/active.json` so the guard enforces its scope.
- Each package: `sh-builder` in its own worktree (Agent tool, `isolation: "worktree"`), failing tests first, then code. Then `sh-reviewer`, and also `sh-security-reviewer` for P1-02, P1-03, P1-04, P1-06, and `sh-ui-reviewer` for P1-05. **Author is never the reviewer.** Give reviewers the code and brief, not the builder's conclusions.
- Fix rounds until every reviewer returns PASS. Then land with `python tools/sh_commit.py <ID>` (use `/ship`). Local commits only.
- Parallel where packages do not touch the same files. Use the cheapest capable model for mechanical work; keep the strongest for reviewers and security.
- Use `graft` for code context. Do not read whole files you will not edit.
- Servers only on ports 8200-8299; stop what you start. Tests write only to temporary folders.

## Guardrails (non-negotiable)
1. **Never push.** No `git push`, no remote, no deploy. The repo stays local (D-024).
2. **Real client data never leaves the machine.** Synthetic data only, always marked illustrative.
3. Never write `.env` or print a secret or key value. Use variable names; if something is missing, `doctor` reports it.
4. Do not edit `.claude/hooks/`, `.claude/settings.json` or permission settings. Never modify the old repo.
5. Contracts and decisions are the only source of truth. Never invent a business rule, role, table or threshold; the answer is in `docs/decisions.md`, the spec, or you choose the safest option and record it (below).
6. No destructive command (`DROP`, `TRUNCATE`, `DELETE`, `rm -rf`, `git reset --hard`, `git clean`, `git stash`) outside temporary folders. Use WIP commits to set work aside.
7. The industry is always a parameter; never hardcode insurance or any industry.
8. Signed content is read-only; a draft never overwrites a human edit.
9. Every package is reviewed by a different agent than its author.
10. Do not start any module 1 or module 2 feature work.

## Autonomous decisions: do not stop to ask
When something is unclear:
1. Look in `docs/decisions.md`, then the spec, then the old repo's behaviour.
2. If still open, pick the **safest, simplest option** that keeps data local and does not close a door, and record it as `A-nnn` in a new section "Autonomous decisions" at the end of `docs/decisions.md`: the question, your choice, why, and how to reverse it.
3. Carry on. Batch every such decision for my review at the end.

**Stop and tell me only if** (a) you need a secret or an account I must create, (b) an action needs my approval under guardrail 6, (c) a decision I made contradicts another, (d) you find real client data in the repo, or (e) a security reviewer rejects the same package twice for the same cause. For anything else, do not stop. Do not ask "shall I proceed".

## Definition of done
- [ ] All packages P1-01 to P1-10 landed through `tools/sh_commit.py`; each has a report and PASS reviews in `docs/ledger/<ID>/`; builder and reviewer ids differ in `packages.json`
- [ ] Backend tests all pass; UI type-check and tests pass; real counts recorded
- [ ] `python tools/doctor.py` prints Ready
- [ ] `/smoke` passes: insurance company, asset-management company, empty company, solo user; a switched-off module is refused by menu, route and agent tool; a user of one company cannot read another's plane; an expired session returns to login
- [ ] Egress tests pass: a payload containing a vault name, a raw row, or a figure from a group under five is blocked; internet access is off by default; every outbound call is logged
- [ ] No hardcoded industry anywhere (a test greps for it); no secret in the repo (the commit gate's scan is clean)
- [ ] I can run the app locally from one documented command, sign in as a seeded user, see only the owned module tiles, and see the expired-session redirect work
- [ ] `docs/decisions.md` has the autonomous decisions; `docs/reuse-map.md` is updated with what was actually copied, reshaped, rebuilt or created
- [ ] `git log` shows one commit per package; nothing pushed; tags `sh/<ID>` exist

## Final report (one message, plain words, no jargon)
What landed (one line per package), real test counts, how to run it, three screenshots (login, home tiles, expired-session redirect), the autonomous decisions with your reasoning, anything you could not finish and why, and what phase 2 (module 1) needs from me. Nothing before this report unless a stop condition occurs.
