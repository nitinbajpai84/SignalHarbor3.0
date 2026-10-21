# Closing the gaps: the program

Written 21 Oct 2026 from Nitin's direction on the competitor teardown (docs/v3/COMPETITOR-TEARDOWN.md). Nothing here is built yet; this is the plan for approval.

Nine workstreams, three phases. Each workstream says what it is, how it works, what changes in our code, and what Nitin has to decide or do.

| # | Workstream | Phase | Rough size |
|---|---|---|---|
| W1 | Ten bank and custodian feeds, on a connector framework | 1 | 2 weeks |
| W2 | Reading private-fund documents in any layout | 2 | 3 weeks |
| W3 | Ownership look-through (trusts, holding companies, family shares) | 2 | 2 weeks |
| W4 | Review queue for low-confidence reads | 1 | 1 week |
| W5 | Client portal and mobile app | 3 | 3 weeks |
| W6 | Public API for Consume | 2 | 1.5 weeks |
| W7 | Security certification readiness | runs alongside, 3 to 6 months | mostly not code |
| W8 | Managed onboarding and data ops | 3 | 2 weeks plus a playbook |
| W9 | The assistant: our answer to Addepar's Addison, cheaper | runs through all phases | pricing and positioning |
| W10 | Five accuracy methods, exact code changes | 1 | 2 weeks |

Phase 1 is W1, W4 and W10 (about 2 weeks with parallel builders); Phase 2 is W2, W3 and W6 (about 3 weeks); Phase 3 is W5 and W8 (about 3 weeks). W7 and W9 run alongside.

---

## W1. Ten feeds to show we can connect anything

**The honest picture.** Real live feeds from banks and custodians need a commercial agreement and a signed letter from the client authorising the bank to send data (a "letter of authorisation"). Nobody gets those for a demo. What we *can* show:

- the standard file formats banks and custodians send every day, read by us;
- sandbox APIs that providers open to developers for free, with test data.

Together they prove the point: one connector framework, and a new feed is a small plug-in.

**The ten:**

| # | Connector | Kind | Why it matters | Needs |
|---|---|---|---|---|
| 1 | SWIFT MT940 | Bank statement file | The format most banks worldwide send for daily statements | Nothing; we generate synthetic files |
| 2 | ISO 20022 camt.053 | Bank statement file | The newer standard that replaces MT940 (Singapore and EU banks are moving to it) | Nothing |
| 3 | SWIFT MT535 / MT536 | Custody holdings and transactions | How custodians report positions and settlements | Nothing |
| 4 | BAI2 | Bank statement file | US banks' standard | Nothing |
| 5 | SFTP drop | Daily custodian files | How custodians such as Pershing-style providers deliver positions and transactions in practice | A local SFTP server for the demo |
| 6 | Email inbox (IMAP) | Notices and statements by email | Most private-fund documents arrive this way | A test mailbox |
| 7 | Plaid (sandbox) | Bank and brokerage API | Large US aggregator with a free test environment | Nitin creates a developer account |
| 8 | Saxo OpenAPI (simulation) | Broker and custody API | A real multi-asset broker with a free simulation account; strong in Asia | Nitin creates a developer account |
| 9 | GoCardless Bank Account Data | Open banking API (EU and UK) | Free tier, covers thousands of banks | Nitin creates a developer account |
| 10 | A Singapore bank developer sandbox (DBS developer portal, or OCBC's) | Bank API | Shows a local bank connection | Nitin registers; terms to confirm |

The terms of 7 to 10 must be checked when signing up. If one doesn't fit, Alpaca (paper trading) is a free substitute.

**What we build:**
- **A connector interface:** fetch, then map to our tables (`cash_movements`, positions, `bank_accounts`), then put the source file in the landing zone with its receipt. One file per connector under `sh_platform/v1/connectors/`.
- **A Connections page under Build.** It shows each connector, its status, last run, rows loaded and errors, with a Connect button.
- **Every live call goes through the egress gateway** (rule: egress.md), off by default per company, with each destination allow-listed.
- **Feed data and file data reconcile against each other.** That is the start of the daily reconciliation competitors sell (W10, method 3).

**Nitin does:** creates the developer accounts for 7 to 10 and puts the keys into the environment himself; Claude never handles them.

---

## W2. Reading private-fund documents in any layout

**Is there an industry standard layout?** Partly. ILPA (the private-equity investors' association) publishes standard templates for capital call and distribution notices and a standard quarterly reporting template. Many larger funds follow them; many smaller funds don't. So no reader can rely on a layout. The documents that matter (capital calls, distributions, quarterly statements, NAV statements, tax packs, subscription documents) come in hundreds of layouts, and new ones keep arriving.

**How platforms read anything.** There are three generations of technique:

| Technique | How it works | Strength | Weakness |
|---|---|---|---|
| Templates | Someone marks where each field sits on one fund's layout | Exact on known layouts | Breaks on any new layout; needs people for every fund |
| OCR plus rules | Turn a scan into text, then find fields by keywords ("Amount due") | Handles some variation | Brittle; fails on tables and odd wording |
| AI document understanding | A model reads the whole page (text and image) and fills a fixed form for that document type | Works on layouts it has never seen | Can be confidently wrong, so it needs checks |

Specialist vendors in this space publicly describe the third, with human review behind it. OCR is only the first step for scanned paper. The understanding comes from the model plus checks.

**How we do it (building on what exists).** Today `v3_pdf.py` has layout readers, and when it sees a new layout it asks once, then remembers it. We generalise that:

1. **Get text:** use the PDF's own text layer; if it is a scan, run OCR on the machine (the original file never leaves, per egress.md).
2. **Classify:** decide what the document is (capital call, distribution, statement and so on). This exists in `kind_of`.
3. **A schema per document type:** for a capital call that is fund, investor, call number, amount, parts (investment and fee), due date, and bank account. The schemas go in the pack (`packs/family_office/1/doc_schemas/`).
4. **Model extraction into the schema:** every field carries its page and the quoted line (the receipt we already keep).
5. **Checks:** rule checks (W10, method 2) and the second model agreeing (`v3_judge`). Together they give each field a confidence (W4).
6. **Layout memory:** once a layout has been read and confirmed, its fingerprint is saved. The next document in that layout is read deterministically, which is fast and cheap. This is what makes repeat funds exact.
7. **Low confidence goes to a person** (W4), and their correction becomes a test (W10, method 4).

**How we prove it.** Generate 20 synthetic layouts per document type (different fund administrators' styles, scans, tables, multiple pages). Measure field accuracy on layouts the system has never seen. Target 95% of fields right or sent to review, and 0% wrong and passed through silently.

---

## W3. Ownership look-through, explained

**What it means.** A family office rarely owns things directly. A typical chain:

> Mei Chen is a 50% beneficiary of the **Evergreen Family Trust**.
> The Trust owns **60%** of **Evergreen Holdings**; Daniel's company owns the other 40%.
> Evergreen Holdings owns a **USD 10m** commitment to Cedarpoint Ventures III.

"What does Mei own in Cedarpoint?" is 10m × 60% × 50% = **USD 3m**. Look-through means following that chain of percentages down to the asset, for any person or entity, as at any date.

**How our model differs today.** In our data model (`Data Model/evidence-to-action-mvp.dbml`) every portfolio belongs to exactly one legal entity, and entities don't own each other. There is:
- no "entity A owns X% of entity B" record;
- no beneficiary shares;
- no change of ownership over time.

So we can answer "what does Evergreen Holdings hold", but not "what is Mei's share of everything", and not the trust's indirect exposure. Competitors build their whole model around this ownership graph, which is why family offices value them.

**What we add:**
- **A new source-fact table, `entity_ownership`:** owner (an entity or a family member), owned entity, percent, from date and to date, plus the source document (trust deed, share register). It qualifies as core under rule A11 because it is a fact the office records. It needs the steward's decision, logged in ASSUMPTIONS.md.
- **A recipe, `lookthrough_exposure`,** which already waits in A24. It walks the chain and multiplies the percentages, as at a date.
- **Per-person views:** "my share" answers in Consume, and the family portal (W5) shows each member only their own share (`family_access_*` rules already exist).
- **The Knowledge map** draws the ownership chain as a structure chart.
- **Checks:** ownership of an entity adds to 100%, and no circular ownership.

---

## W4. Review queue for low-confidence reads

**What it is.** Every field Harbor reads gets a confidence. Anything below a signed threshold doesn't flow into figures until a person confirms or corrects it. That person gets one card in Action: the field, Harbor's reading, the page image with the line highlighted, and Confirm or Correct.

**How confidence is scored, simply:**
- **High:** a known layout read deterministically; or both models agree and every rule check passes.
- **Medium:** both models agree but a rule check couldn't run.
- **Low:** the models disagree, a rule check fails, or the page was a poor-quality scan.

**What changes:**
- `v3_pdf.py`, the readers: emit a confidence per field.
- `v3_judge.py`: return agreement per field, not per document.
- `extracted_fields`: already has a review status (A21); add `confidence` and `reviewed_by`.
- The threshold is a signed rule, `review_confidence_min`.
- Action board (`v3_board_routes.py`): a "Check what I read" card type.
- A correction goes to W10 method 4.

**What a buyer sees in a demo:** "Harbor read 47 fields; 45 it was sure of, 2 it asked Grace about." That is more trustworthy than claiming 100%.

---

## W5. Client portal and mobile app

**Portal (for the family, read-only):**
- each member's own share (needs W3);
- a morning note;
- documents they're allowed to see;
- ask-a-question limited to their own data;
- approvals for things that need them, such as a family member approving a distribution.

**Mobile, in two steps:**
1. **First, a Progressive Web App.** The existing React app becomes installable on a phone, works offline for the last view, and gets push notifications for signals and approvals. The phone layout already exists (the tab bar in `Frame.tsx`). This is cheap and fast.
2. **Later, app-store apps,** if buyers insist, by wrapping the same app (Capacitor) for iOS and Android. No second codebase.

**Morning note by email** as well: the principal reads email, not apps. WhatsApp only through an approved business provider, later.

---

## W6. Public API for Consume

**What third parties get:** a read-only REST API, documented (OpenAPI), with:
- `GET /figures`, `/figures/{id}` (with its receipts);
- `POST /ask` (a question in, an answer with figures and receipts out);
- `GET /signals`;
- `GET /documents`;
- webhooks when a signal fires;
- an MCP connector, so a client's own AI tools can query Harbor. Addepar has one.

**Controls:**
- API keys per company, scoped (which figures, which entities);
- rate limits;
- every call logged;
- a key never sees another company's plane (data-locality.md);
- family-member keys see only their own share.

**Where it lives:** the routes are declared with their `*.permissions.yaml` (default deny) under `sh_platform/v1/`, with an "API keys" page under Build.

---

## W7. Security certification: what it actually takes

**The two buyers ask about:**
- **SOC 2 Type II** (an American standard, asked for globally). An independent auditor checks that our controls worked over an observation period of usually 3 to 12 months. A Type I report, which checks the controls are designed right on one date, can come first and faster.
- **ISO/IEC 27001.** Certifies our information security management system: risk assessment, policies and controls. It is audited in two stages by a certification body, then yearly.

In Singapore, clients that are financial institutions will also ask about the MAS Technology Risk Management guidelines and PDPA.

**The work, in order:**
1. **Pick a compliance platform** (Vanta, Drata or Secureframe). These watch our cloud and code settings and collect evidence automatically.
2. **Write the policies:** access control, incident response, backups, vendor management, change management, data retention.
3. **Product controls (code work, about 2 weeks):**
   - single sign-on and enforced MFA;
   - full audit log of sign-ins and data access, exportable;
   - encryption at rest for the data volume;
   - data kept in a Singapore region option;
   - backups with a tested restore;
   - least-privilege roles;
   - automatic dependency and secret scanning.
4. **An independent penetration test.**
5. **SOC 2 Type I audit**, then Type II after the observation period.
6. **ISO 27001** if European or Asian institutional buyers ask.

**Cost and time** are rough market ranges that need quotes: a compliance platform plus a Type I audit is commonly tens of thousands of USD in the first year, and readiness to Type II is typically 6 to 12 months.

**Nitin decides:** whether to start now (Type I as a sales signal) or after the first pilot.

---

## W8. Managed onboarding and data ops

**The typical onboarding steps in this industry** (general practice, not any vendor's internal method):
1. **Discovery:** entities, accounts, funds, ownership chart, reports wanted.
2. **Authorisation letters** to each bank and custodian, so feeds can start (the slowest step; weeks).
3. **Historical load:** past statements and transactions back-filled, often years.
4. **Opening balance reconciliation:** our figures must match the custodian on day one.
5. **Ownership structure build** (W3).
6. **Report and dashboard set-up.**
7. **User testing with the office.**
8. **Training.**
9. **Go-live.**
10. **Hypercare:** daily check-ins for a few weeks.

**After go-live (data ops):**
- daily reconciliation;
- working the exception queue;
- entering assets with no feed (art, property, loans);
- chasing missing statements.

Masttro publicly quotes 12 to 14 weeks.

**Our advantage.** Harbor already does steps 1, 3, 4, 5 and much of the ongoing data ops with agents. Span designs the model, the readers back-fill six months, recon is a recipe, and the chase drafts exist. The target is **2 to 4 weeks**, not 12 to 14.

**What we build:**
- an **Onboarding checklist** in Build, with each step, its owner and status, and Harbor doing what it can;
- an **onboarding health score:** feeds connected, history loaded, opening balances reconciled, review queue empty;
- a written playbook (`docs/v3/ONBOARDING-PLAYBOOK.md`) for the human side.

---

## W9. Our assistant versus Addepar's Addison, and doing it cheaper

**Where they're similar.** Both answer plain-English questions over the office's data.

**Where we differ, and should lead:**
- **Receipts:** every number links to the file, page and line it came from.
- **A second model checks every figure** before it is shown.
- **Recipe first:** a known question runs a written, tested calculation; the model doesn't invent the maths.
- **It acts, not only answers:** signals go to the right person, decisions are recorded, and payments are held when bank details change.
- **It reads the documents itself**, rather than needing a feed for everything.

**Why we can be cheaper:**
- Recipe-first and cached answers mean a repeat question costs almost no model time. We already reuse answers.
- We choose the model per task (Jev-style routing): small models for reading, larger only for design.
- There's no large data ops team to pay for, because agents do the first pass and people only review the low-confidence items.
- **Price per office, not per asset under management**, with a flat tier for offices of USD 100m to 1bn. Those offices are underserved by the big platforms' pricing.

**Proof we need before claiming it:** the accuracy numbers (W10) and one pilot office.

---

## W10. The five accuracy methods: exactly what changes

| # | Method | What changes in our code | How we'll know it works |
|---|---|---|---|
| 1 | **Confidence on every field, low confidence to a person** | `v3_pdf.py` readers emit confidence; `v3_judge.py` agreement per field; `extracted_fields` gets `confidence`, `reviewed_by`; signed rule `review_confidence_min`; review card in `v3_board_routes.py` (W4) | Zero wrong fields passed silently on the 20-layout test set |
| 2 | **Rule checks on every document as it arrives** | `v3_rule_checks.py` gains document checks:<br>• call parts add up to the total;<br>• due date after notice date;<br>• call no more than the unfunded amount;<br>• call currency equals the commitment currency;<br>• bank account equals the account on file (`bank_accounts`);<br>• a statement's opening balance equals last month's closing;<br>• no duplicate document (same fund, number, amount).<br>A failure holds the document and raises a card. | Every planted mess item (M01 to M21 in office6m) is caught at arrival |
| 3 | **Match each capital call to the payment that settled it** | `e3_recon.py`: a matcher from noticed call (`cash_movements`) to bank statement line, by amount, a date window and reference words; the call closes as Paid on its own; unmatched after its due date raises a card | Use case 1, step 6 ("Paid on Monday's statement") passes with no human step |
| 4 | **Every correction and failure becomes a permanent test** | A review-queue correction is saved (made synthetic) as a fixture plus a pinned test; live-round failures are already pinned; a new accuracy-over-time chart on Knowledge → Runs and proof | The number only goes up; a regression blocks the merge |
| 5 | **More layouts** | W2: doc schemas in the pack, model extraction into schema, layout memory in `v3_pdf.py`, OCR for scans | 95% field accuracy on unseen layouts, the rest sent to review |

Also carried over from round 7: the **time-zone root fix**. The warehouse session should be set to UTC in `wh.connect`, so no as-at date comes out a day late. Two recipes are patched today; this fixes all of them.

---

## Decisions for Nitin

1. **Approve the program and its order** (Phase 1: W1, W4, W10).
2. **Create the developer accounts** for Plaid, Saxo, GoCardless and a Singapore bank sandbox, and set the keys yourself.
3. **Approve the new table `entity_ownership`** (W3), which will be logged as an assumption.
4. **Mobile:** PWA first, app stores later? (Recommended: yes.)
5. **Security:** start SOC 2 Type I readiness now, or after the first pilot?
6. **Pricing stance:** flat price per office for USD 100m to 1bn offices?
7. **Pause adding new use cases** while the top 20 are made solid and these gaps are closed? (Recommended: yes.)
