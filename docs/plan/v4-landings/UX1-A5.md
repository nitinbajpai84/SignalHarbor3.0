# UX1 A5 (build)

Done (ui/src/v1/b6/Steps.tsx, b6.test.tsx updated):
- UX-17: button "Approve the plan" plus muted line "This also approves the new tables and columns in document 2."; send-back textarea placeholder "What should Span change?".
- UX-18: "Run in the sandbox" is now "Try it on a copy"; "Download the Airflow file" moved under a details "For engineers".

Skipped: none (UX-05 was missed by the developer and applied in review, see below).

Tests: npx vitest run src/v1/b6 -> 2 files, 8 tests pass. npx tsc --noEmit -> 2 errors, both in other agents' files (v1/e5/k8.test.tsx:18, v1/k5/ManagersInbox.tsx:16), none in b6.
Backups: .sh-tmp/Steps.tsx.bak-ux1, .sh-tmp/b6.test.tsx.bak-ux1.

See it: Build centre, a project's Approval step (head of data) and Pipeline step.

## Review

Verdict: pass after one fix. UX-17 and UX-18 match the designer's wording exactly (checked against docs/test/UX-REVIEW-1.md rows 33-34). UX-05 had not been applied; applied in review.

UX-05 (applied in review, backup .sh-tmp/BuildPage.tsx.bak-ux1):
- ui/src/v1/b6/BuildPage.tsx: subline by role from the session: analyst/admin "Check Span's plan, then approve it."; everyone else "The data team is building this. You will be told when it is live." Both page branches (no plan yet, plan) use it.
- BuildPage.tsx: when the person may not propose, a muted line under the disabled button: "Only the data team can ask for a plan."
- BuildPage.tsx: document 3 is now "3 Tables".
- ui/src/v1/b6/Steps.tsx: each table's SQL sits inside a collapsed details "How it is calculated"; the aria-label "SQL of <table>" is kept for the test.
- b6.test.tsx: the build page test now checks the analyst subline, "3 Tables" and the "How it is calculated" blocks.

Checks: npx vitest run src/v1/b6 -> 2 files, 8 tests pass. npx tsc --noEmit -> 0 errors in b6 (one remaining error in src/v1/k5/ManagersInbox.tsx:16, another agent's file). Nothing outside ui/src/v1/b6 touched. 390px: the Approval block is a single-column grid (max 420px) and the Pipeline buttons flex-wrap, the new details and muted lines are plain flow text; no servers were started (not allowed), so this is a read of the layout, not a screenshot.

Open items:
- "head of data" still appears in copy the designer did not flag (Steps.tsx 71, 79, 99; api.ts state name; ProjectsPage subline) while the new UX-05 lines say "the data team". Fine for now; one wording pass when the designer reviews round 2.
- docs/guides/FOUR-CENTRES-DEMO.md and docs/test/JOURNEY-NOTES-1.md still say "Tables and SQL" / "Run in the sandbox"; docs, not in this area.
