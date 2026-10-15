---
description: Land one reviewed package through the commit gate
argument-hint: <PACKAGE_ID>
---

Land package $ARGUMENTS:

1. Check `docs/ledger/packages.json` has an entry for $ARGUMENTS with `owns`, `builder_id`, `reviewer_id` (different from the builder), `report`, `review` and `verdict: PASS`. If anything is missing, stop and say what.
2. Check the report and review files exist under `docs/ledger/$ARGUMENTS/`.
3. Run `python tools/sh_commit.py $ARGUMENTS` and report its output exactly.
4. Never push. Tell Nitin the commit id and the tag.
