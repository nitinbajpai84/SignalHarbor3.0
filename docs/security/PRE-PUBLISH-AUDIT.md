# Pre-publish audit: prospect name, other projects, personal data, secrets

Date: 10 October 2026. Scope: every file that would be committed to the new private GitHub repo and built into the public Railway image. Nothing under `data/`, `local/` or `.sh-tmp/` was edited; no server was touched; no model was called. This file deliberately names none of the strings it searched for. The search list lives in the audit scripts, which are kept locally.

## Result

**Clean of the prospect's name, other-project paths and names, personal paths and email addresses, and real secrets.** Four low-risk items remain for a decision (listed at the end). None of them names the prospect.

## The commit set

- Built by walking the tree and applying `.gitignore` (fnmatch; `pathspec` is not installed). Manifest: `.sh-tmp/commit-manifest.txt`.
- Before this audit: 4,572 files, 89.1 MB. After (with `docs/ledger/` now ignored): **4,147 files, 86,283,576 bytes (82.3 MiB)**.
- Text was read from every file. For `.xlsx`, `.docx` and `.pptx` the XML parts inside the zip were read, for `.pdf` the page text and metadata (pypdf), and for images the embedded strings. All **240 images** were also read with OCR (rapidocr).

## What was searched

| # | Looked for | How |
|---|---|---|
| 1 | The prospect: any spelling of its name (with a space, `-`, `_`, `.` or nothing between the words, in any case) in content and in file names. Also its people and counterparties, taken from the pre-rename backups of the demo cycle and from `local/`. Also its logo, addresses and account numbers. | regex, office/PDF text, OCR |
| 2 | Other projects: the folder and repo names of the owner's earlier platform repos, the name of an unrelated project whose venv the tools use, and real company names (a list of about 40 banks, insurers, index providers and consultancies). Insurance-client wording. | regex |
| 3 | Personal data: absolute paths under the user's home folder and the projects drive (also JSON-escaped), the owner's first and last name, any email address (by domain), and phone numbers. | regex |
| 4 | Secrets: `sk-`, `sk-or-`, `AIza`, `ghp_`, `github_pat_`, `xox?-`, `AKIA`, private-key headers, `Bearer` values, and `password`/`secret`/`token`/`api_key` assignments. Also the seed credentials file and `.env` content. | regex, manual read |
| 5 | Branded assets: logos or images of the prospect. | OCR of every image, list of `ui/public/brand` |

## Findings and actions

| # | Finding | Action |
|---|---|---|
| 1 | Prospect name: **0 hits** in the commit set, in text, file names, office files, PDFs and OCR. The earlier rename to "Ardmore" holds. The branded deck is in `local/branded-decks/` (gitignored). | None needed |
| 2 | The prospect demo's family and principals shared two surnames that were used in the prospect's demo cycle: four family members, two family trusts and three staff. They appeared in the demo cycle, the Neera client list, seeds, tests and docs. | Renamed consistently everywhere in the commit set to **Shaw** and **Kerr**, in every case form (`janet.shaw`, `daniel-kerr`, `DanielKerr`). This touched 1,294 occurrences. 23 feedback-note files were renamed (`*_kerr_mei_xin.md`, `*_shaw_wei_jie.md`, `*_mr_shaw_kian_peng.md`, `*_mrs_shaw_li_hua.md`). The originals are in `.sh-tmp/bak-leak/`. |
| 3 | The rest of the cast: Grace Ward, Aaron Lyle, Harvey Rowley, Katie Kingsley, Marcus Todd, Mei Ling Chong, Ravi Chandran, Rahul Mehta, Mei Chen, Arjun Mehta and others. | Superseded by the independent audit below: the five names that matched the prospect demo's cast were renamed (the names shown here are the new ones). The others are kept. |
| 4 | Counterparties: Northgate Custody, Harbour Bank, Orchard/Marina/Sentosa/Changi Growth Partners, Pacific Lion Bank, Merlion Telecom, Straits 50, and others. | Kept. They are fictional by the data plan's own rule (`docs/plan/V1-ARDMORE-DATA.md`). None is a real firm. |
| 5 | Absolute paths to the owner's earlier platform repos (the main worktree, a family-office fork, a third repo and a design-docs folder), and those repos' names. Found in `.claude/rules/reuse-first.md`, `docs/prompts/`, `docs/reuse-*.md`, `docs/specs/intent-centre/*`, `docs/plan/*`, `packs/family_office/1/pack.yaml` and `modules/m2_baseline/domain/catalogue.py`. | Replaced with neutral placeholders: `<earlier repo>`, `<earlier repo E>`, `<earlier design docs>`, "earlier platform", `earlier-repo`. The fork's worktree id `practical-hawking-bd28e8` stays in the pack provenance because `tests/test_packs.py` asserts it. It is a random worktree name. |
| 6 | Absolute paths to this workspace and to the 2.0 repo folder on the owner's drive, 84 occurrences, including JSON-escaped ones in `docs/architecture/*.json`, `docs/test/*-NOTES-1.md`, `docs/DEPLOY-RAILWAY.md` and `docs/guides/TESTING-INTENT-CENTRE.md`. | Replaced with `<repo>`, `<2.0 repo>` and `<workspace>`. Two pieces of code used the path itself and now resolve it from `__file__`: `tests/v1/test_e0b1.py` and `tools/gen_10uc/check_10uc.py`. |
| 7 | The owner's home folder, including a venv path inside another project's folder, the archify skill path and a Temp path. Found in `docs/architecture/sh-four-centres.finalize.json` and `docs/plan/v4-landings/*`. | Replaced with `<home>`, `<venv python>` and `<temp>`. |
| 8 | `docs/ledger/` (425 files): agent briefs, reports and `routing.jsonl`, full of absolute paths, earlier-repo notes and code copied from the earlier repo (its old UI scripts name the earlier platform). | **Added `docs/ledger/` to `.gitignore`**: it is the agent working record and stays on this machine. Nothing in the app reads it. `tools/route_task.py` and the guard hook still write and read it locally. |
| 9 | The owner's full name, as the seed user of the empty "Fresh" company (`tools/seed_fresh.py`, `tests/v1/test_t1b.py`, docs). | Renamed to "Fresh Owner". The fake login `nitin.fresh@example.test` was kept, because tests read the local `data/_control/seed_credentials.txt`, which already holds it. |
| 10 | The owner's first name in about 130 files, as the product owner in comments, specs and decisions. | Kept. It is the owner's own attribution in his own private repo, and it is not shown in the app. |
| 11 | Email addresses: none at gmail, outlook, hotmail, yahoo, icloud, live or proton. All are at `example.test`, `example.com`, `*.example`, `test.invalid` or similar. | None needed |
| 12 | Phone numbers: only `+65 6123 4567/8`, the synthetic number in the minimiser tests. The other hits are SVG path numbers. | None needed |
| 13 | Secrets: none. The hits are fake test values (`fake-test-secret-not-real`, `FAKE-...-secret-...`, `tok-xyz`) and test ids (`sk-source-s-custody-licence`). `.env` is ignored. `.env.example` has empty values. The seed credentials file exists only under `data/` (ignored), and the commit set only references its path. | None needed |
| 14 | Real company names: MSCI and Bloomberg as data vendors, OpenAI as a model provider, base64 noise in images and an SVG, and a denylist of real firms in `tools/gen_10uc/check_10uc.py` (it checks that the synthetic data avoids them). No client is named. | None needed |
| 15 | Insurance: `packs/insurance/` is a generic industry pack (the synthetic `harbor-mutual` plane, "Illustrative Harbor Mutual"). No real insurer and no client wording. | None needed |
| 16 | Branded assets: `ui/public/brand/` holds only the Signal Harbor mark. OCR of all 240 images found neither the prospect's name nor "Ardmore". | None needed |
| 17 | Demo planes are synthetic: `seed.py` gives harbor-mutual, tidewater-capital, lakeside-family-office and solo-studio, all named "Illustrative ...". Evergreen comes from the 10uc universe, and Neera and Ardmore from their seeds. The Railway image seeds only Evergreen (`tools/seed_demo_boot.py`). | None needed |
| 18 | `docs/test/BACKEND-SUITE-10OCT.md` described "Ardmore" as the prospect's name. | Reworded: the pack carried the prospect name, since renamed to the neutral "Ardmore". |

Backups of every edited or renamed file are in `.sh-tmp/bak-leak/` (same relative paths, plus the original `.gitignore`).

## Tests run

- pytest on the touched test files, the seed tests and `tests/test_packs.py` (73 files or folders): 867 passed and 14 failed on the first run. The fixes:
  - The glued sponsor name in the vault test.
  - The pack provenance id restored.
  - The fake fresh-company login kept.

  Re-run of the failing files: 70 passed and 1 failed. `tests/test_packs.py`: 46 passed, 1 skipped (it needs `local/companies.yaml`).
- The one remaining failure, `tests/v1/test_e0b1.py::test_v2_rules_present_in_skill`, is **pre-existing and unrelated**. It looks for "Control totals" in the data skill text, which this audit did not touch (no file under `skills/` changed).
- vitest on the 28 touched UI test files: 28 files, 218 tests passed. Four files needed a second run with one worker because the machine was loaded.

## Remaining items (low risk; none names the prospect)

1. `tests/test_packs.py` keeps the name guard. The guard stores two SHA-256 hashes of the prospect's name, never the name itself. Anyone who already guesses the name could confirm it from the hash. Keep the guard (recommended), or move the hashes to the gitignored `local/`, accepting that CI then has no guard.
2. Two screenshots, `docs/guides/e2e/04-session-names-rule.png` and `05-guest-lobby.png`, show the old surname of the synthetic sponsor (now Daniel Kerr). This does not identify the prospect. Re-shoot them if exact consistency matters.
3. The local `data/` planes and `data/_control/seed_credentials.txt` still hold the old spellings. They are not committed. Re-seed (`tools/seed_v1.py` or the matching seed) before following the renamed demo scripts on this machine.
4. The owner's first name in comments and specs, and the fake `nitin.fresh@example.test` seed login, stay in the repo (findings 9 and 10).

## Independent audit (10 Oct 2026)

A second reviewer rebuilt the commit set and repeated every search instead of relying on the first audit.

**Commit set.** Built with git's own ignore engine (`git ls-files --others --exclude-standard`, run against a scratch git directory outside the repo so no repository was created here). Result: **4,149 files, 86.3 MB (86,319,223 bytes)**. This matches the first audit. The manifest is in `.sh-tmp/commit-manifest.txt`.

**Searches.** Every search was case-insensitive and covered spaces, hyphens, underscores, no-space forms, run-together forms and misspellings. They ran over file names and file text, over the XML inside every docx, pptx and xlsx (including author metadata), over PDF text and metadata, and over the raw bytes of images. OCR ran on all 240 images and on the 17 images inside the two spec decks. The patterns covered:
- the prospect's name;
- every person and counterparty in the prospect's own demo documents in `local/`;
- other-project names and paths;
- absolute paths, personal emails and phone numbers;
- secret shapes (`sk-`, `AIza`, `ghp_`, `github_pat_`, `xox`, `AKIA`, `hf_`, Bearer values, private keys, and `password=`/`token=` assignments);
- real bank, insurer and asset-manager names.

**Findings and actions**

| # | Finding | Action |
|---|---|---|
| I-1 | Prospect name: 0 hits in text, file names, office files or OCR. | None needed |
| I-2 | Five cast names in the committed demo were identical to the people in the prospect's own demo documents (first name and surname). The first audit had changed only two surnames. Together, these names were enough to link the public demo to the prospect's demo. | Renamed consistently in every case form, separator and file name: 3,661 occurrences in 237 files, plus 7 renamed demo-cycle files. The new names are Meredith, Harvey Rowley, Katie Kingsley, Aaron Lyle, Grace Ward and Marcus Todd. Other people with the same surnames (for example Sara Lim, Mei Tan and Jade Wong) were not changed. Originals are in `.sh-tmp/bak-leak2/`. |
| I-3 | `tests/graph/test_versions.py` named a test person with the first syllable of the prospect's name. | Renamed to "Will Wall". |
| I-4 | `tests/test_packs.py` held two SHA-256 hashes of the prospect's name. Anyone who guessed the name could confirm it from them. | The hashes moved to the gitignored `local/banned-names.sha256`, and the guard reads them from there. The tracked file now holds no trace of the name. On a machine without the local file, the real-name guard is empty and its local check skips. |
| I-5 | Two screenshots (`docs/guides/e2e/04-session-names-rule.png`, `05-guest-lobby.png`) showed the sponsor's old surname. | The text was redrawn in the image to show the current surname, and OCR confirms the change. Originals are in `.sh-tmp/bak-leak2/docs/guides/e2e/`. |
| I-6 | The first audit's row 3 listed the old cast names. | Row 3 now shows only the new names. |
| I-7 | Other projects: no hits for <earlier project> paths. "Nira" is this product's own guide agent. | None needed |
| I-8 | Personal data: no `C:\Users` or `D:\Projects` paths, no personal emails, and no real phone numbers (the only `+65` number is the fake one used in the minimiser tests). `conftest.py` names `D:/Temp` only when that folder exists, as a scratch location. The owner's first name appears in comments and specs, and in `.claude/hooks/guard.cjs`. | Accepted. A generic scratch path and the owner's own attribution in a private repo are not leaks. |
| I-9 | Secrets: none. The pattern hits were base64 font data inside an SVG and an HTML guide, the strings `fake-test-secret-not-real` and `fake-key-for-tests`, and `sk-source-*` source ids. `.env.example` has empty values only. `.env` and `data/_control/seed_credentials.txt` are not in the commit set. | None needed |
| I-10 | Real firm names appear only as a denylist in `tools/gen_10uc/check_10uc.py` and as OCR noise in images. The counterparties (Northgate Custody, Harbour Bank, Blue Heron Insurance and the place-named growth funds) are invented. | None needed |
| I-11 | The demo family office is set in Singapore and uses SGD, and some fund names are Singapore place names. This identifies a region, not a client. | Accepted. Changing it would mean rebuilding the demo data. |
| I-12 | No image in the commit set (240 files plus the 17 inside decks) shows a prospect logo, name or person. | None needed |

**Tests after the fixes**
- pytest across all 93 affected test files plus `tests/test_packs.py`, run one directory at a time: all pass except `modules/m1_intent/tests/test_m1_private_room_api.py::test_a_role_without_access_and_a_switched_off_module_are_refused`. That test fails the same way in the baseline run taken before these renames, so it is pre-existing and unrelated.
- `tests/intents/test_b04.py` first failed on a double-spaced variant of a name. It is fixed and passes (37 of 37).
- vitest on the 37 touched UI test files: 344 of 344 pass.

**Local follow-up (not committed).** `data/` still holds the old cast names and logins. Re-seed before running the demo scripts on this machine.

**Verdict: CLEAN.** No prospect name, prospect person, prospect logo, other-project path, personal path or address, or secret remains in the commit set. Re-run the manifest and the scan just before committing, because other agents are still adding files.
