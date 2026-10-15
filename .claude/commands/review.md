---
description: Send a built package to an independent reviewer
argument-hint: <PACKAGE_ID> [security|ui]
---

Review package $ARGUMENTS.

Start the `sh-reviewer` agent; also start `sh-security-reviewer` if the package touches sign-in, permissions, isolation, entitlements, egress, uploads or outside tools, and `sh-ui-reviewer` if it changes screens. Give each the package's brief, the list of changed files, and the spec section. Give them the code, not the builder's conclusions.

Write each verdict to `docs/ledger/<PACKAGE_ID>/review-<agent>.md`. Report the verdicts and every BLOCKING finding to Nitin in plain words.
