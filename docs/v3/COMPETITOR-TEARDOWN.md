# Competitor teardown: Addepar and Masttro against Signal Harbor 3.0

Date of research: 21 October 2026. Public sources only. No accounts, trials, logins or non-public endpoints were used.

**How to read this.** Competitor claims come from their own marketing, press releases, job postings and developer docs, unless marked otherwise. Vendor marketing is not independent evidence of accuracy. Anything marked **(inferred)** is my reading, not something a source states. Anything marked **(unverified)** could not be confirmed from a public source in this pass. Source URLs are listed at the end and cited by number in square brackets, for example [S3].

---

## 1. Summary

- **Both competitors have strong public claims on custodian feeds, private-markets documents and reconciliation.** Neither publishes accuracy rates, error rates or SLAs for those claims.
- **Addepar has shipped a native AI assistant (Addison, launched March 2026)**, grounded on its data platform. Its agentic features (proactive insights, a data operations agent) are still roadmap or preview as of May 2026 [S5][S6].
- **Masttro has no conversational AI assistant on its public pages.** Its "AI" is in document extraction, classification and alternatives valuation [S9][S10]. Its homepage names AI features but no chat or natural-language query.
- **Addepar's own job postings show a human review step.** Low-confidence document extractions go to data operations analysts, who correct the data and relabel documents for retraining [S7]. Masttro's page says outliers are "flagged for review" but does not say who reviews them [S10]. This is the most useful accuracy evidence I found, and it is the mechanism Signal Harbor should copy first.
- **Signal Harbor's public-facing strengths** (receipts per figure, a cross-family two-model check, signed rules tied to payments, a bank-detail call-back hold) are not described on either competitor's public pages. That is not proof they lack them.
- **Signal Harbor's biggest honest gaps** are reach (file intake versus hundreds of live feeds), the one-layout capital-call reader, the absence of an ownership look-through, and answer quality. Our own round-7 live review passed 28 of 100 use cases [S-local-R7].

---

## 2. What each one has

### 2.1 Data aggregation and feeds

| Area | Addepar | Masttro | Signal Harbor (from docs) |
|---|---|---|---|
| Custodian and bank feeds | "Hundreds of custodians and alternative assets", "automate multi-custodian data aggregation", daily. No exact count on its own page; its feed counters render as 0 [S1]. Third-party sites say "more than 300" direct custodian feeds [S12]. | "750+ direct custodian feeds", "750+ custodians, banks, and data providers", "7m+ daily transactions" on its family-office page [S9]. Its older press page and an earlier site version say 650+ [S8]. Its single-family-office page says 700+ [S11]. The count changes by page. | File intake: statements, capital call PDFs, bank files, read by pack readers in `sh_platform/v1/v3_pack_readers*.py`. I did not find a live custodian feed connector in the docs I read. **(unverified: check whether any live connectors exist.)** |
| Ownership and entity model | Entities (trusts, accounts, investments, clients, households) and positions as ownership edges in an ownership graph. Public API docs describe positions as "a connection between two entities in our ownership graph" [S13]. I found no recursive look-through endpoint in the public docs. | "Ownership hierarchies" and multi-entity reporting [S9]. No detail. | `legal_entities`, `portfolios`, `bank_accounts`. Look-through exposure is out of scope for now (assumption A24: `lookthrough_exposure` waits for a table) [docs/v3/ASSUMPTIONS.md]. |
| Non-financial data input | Not stated on operations page. | "Tasks, excel, API, bulk uploads" [S9]. | Files and forms; recipes read from `packs/family_office/1/recipes/`. |
| Corporate actions | Not mentioned on its operations page [S1]. | Not mentioned. | `corporate_actions` table was built later (assumption A32 to A44, superseded note in A23) [docs/v3/ASSUMPTIONS.md]. |

### 2.2 Performance and analytics

- **Addepar** names IRR, MOIC and TVPI, and says it "standardizes" performance for alternatives [S1][S14]. I could not find its published TWR or IRR methodology, benchmark rules or GIPS statement in public sources (unverified).
- **Masttro** shows monthly performance and allocation by asset class in its dashboard images, and "real-time portfolio analytics based on cashflows" [S10]. No TWR or IRR method is named (unverified).
- **Signal Harbor** computes figures from written recipes (`packs/family_office/1/recipes/*.yaml`), each with a stated formula, grain, tie-out and the tables it may read (assumption A8). Performance-specific recipes were not in the files I read (unverified).

### 2.3 Private markets and document handling

This is where both competitors invest most. The published claims are:

- **Addepar:** "automatically ingest alternative asset data", "automate... the manual effort typically required to process capital calls and distributions, NAV adjustments" [S1]. The Alts Data Management product collects capital account statements, capital call and distribution notices, and hedge fund statements, runs "automated data and document quality checks", and sends low-confidence documents to human analysts [S7][S15]. The fact sheet PDF could not be read in this pass (binary output), so its details come from search summaries (unverified).
- **Masttro:** documents arrive by email forwarding or bulk upload; an AI model classifies each document type; capital calls, distributions and valuations are extracted from PDFs; "every feed is reconciled and available in any currency"; alternatives arrive via an Arch partnership announced 17 July 2025 that supplies K-1s, capital calls and alternatives reporting [S9][S10][S16].

**Signal Harbor (from docs):** UC01, "a capital call arrives, can we pay it, and should we?", reads a notice's investor, amount, due date, purpose and bank details, each with page and quoted line, and uses two checks that must agree [docs/v3/use-cases/UC01-CAPITAL-CALL.md]. The reader is built for one PDF layout only (assumption A25) [docs/v3/ASSUMPTIONS.md]. That is the single most important gap in this area.

### 2.4 Reporting, client portal and mobile

- **Addepar:** white-label iOS app, Android functionality, secure messaging, client notifications and template libraries, all previewed at AddeConf26 in May 2026 [S6]. Reporting via its Navigator platform, SOC 3 covered (see section 2.7).
- **Masttro:** mobile app for wealth owners; reports can be shared with trustees, next generation or outside advisors "without exporting to Excel"; a "Secure Communications Portal" listed as a product demo, not described as a client portal [S9].
- **Signal Harbor:** Consume answers and a morning note from verified figures (UC01 story; card 14 in `docs/v3/USE-CASES-100.md`). Client portal and mobile were not in the docs I read (unverified).

### 2.5 Workflow, tasks and controls

- **Addepar:** "letting the system flag exceptions automatically" [S1]. Exception types and rules are not described.
- **Masttro:** "Tasks" as an input method; "full audit-ready logs", compliance alerts and "granular permissions by role, entity, or user" [S9][S10]. Log contents and retention are not described.
- **Signal Harbor:** signed office rules with thresholds (payments over USD 500,000 need Daniel Foo's approval; changed bank details need a call-back before payment; a USD 250,000 cash buffer per entity) [UC01 doc]. Approvals are recorded with name and time. The payment hold is a worked example in UC01 step 5. Cases are opened for breaks and limits (`e3_recon.py`, `v3_rule_checks.py`).

### 2.6 APIs and developer access

- **Addepar** has a public REST API: Entities, Positions, and a Portfolio Query API (`POST /v1/portfolio/query`) that runs queries without a saved view ID [S13]. Auth is HTTP Basic with a firm header or OAuth 2.0 with scopes [S13]. A community Python client (`addepy`) is unofficial [S17]. Addepar also has an MCP connector listed on the Claude marketplace [S18].
- **Masttro** says its API "lets its datasets integrate with other systems" [S9]. No API reference was found.
- **Signal Harbor:** internal APIs for the v3 office, not documented publicly. Harbor's Consume chat is the closest equivalent to a query API (unverified as to external access).

### 2.7 Security and compliance

- **Addepar:** SOC 3 reports for the Analytics & Reporting and Navigator platforms covering July 2024 to August 2025, tested against the AICPA Trust Services Criteria for security, confidentiality and privacy. AWS is a subservice organization [S19]. I could not confirm a SOC 2 Type II report or ISO 27001 certificate from public sources (unverified).
- **Masttro:** "ISO/IEC 27001:2022 certified" (certificate "available upon request") [S9]. No SOC report mentioned. Swiss infrastructure, client-controlled encryption keys, MFA, "military-grade encryption" (marketing wording) [S9][S10].
- **Signal Harbor:** the docs describe a permissions model (E1d access per portfolio, restricted document access in the trail) [`sh_platform/v1/a5_trail.py`]. No certification status was in the docs I read (unverified).

### 2.8 Services, onboarding and data operations

- **Addepar:** data operations analysts work on alternatives documents; postings say they handle "processing exceptions captured by automated validation checks" and reprocess "within SLAs" (no SLA figure given) [S7]. Team size not stated. Customer-reported: report creation time cut "by 40%-50%" (Activest) and "15 to 20 hours a month" from "three to four days" (3 Capital Partners) [S1].
- **Masttro:** most family offices go live in "12–14 weeks" with "dedicated project support, training, and a customized success plan" [S9]. Offices in New York, Zurich and Monterrey [S9]. Reports "over 400 leading family offices in 40+ countries" [S10].
- **Signal Harbor:** the operating model is a family office's own staff plus Harbor's checks; no managed data-ops service is described in the docs.

### 2.9 Pricing signals

- **Masttro:** "Fixed Annual Pricing", "not based on your AUM", and clients keep ownership of their data [S9].
- **Addepar:** no list price. Third-party estimates: entry point about USD 50,000 to 70,000+ a year for a single family office; about 0.8 to 3 basis points on assets (Sacra) or 1.2 to 1.5 bps (Aleta); average contract USD 229,000 in 2024 (Sacra). The Kubera source is a competitor and its framing favours cheaper tools [S20]. Treat all as estimates.
- **Signal Harbor:** pricing not in the docs I read (unverified).
- **Inferred:** Masttro's flat-fee model is an easier sell to a single family office than an AUM-based one. That is a reasoned guess, not a sourced claim.

---

## 3. Accuracy: how each one gets it right

| Mechanism | Addepar | Masttro | Signal Harbor (from docs) |
|---|---|---|---|
| Direct feed versus document reading | Both. Feeds for custodians; AI-read documents for alternatives [S1][S7]. | Both. 750+ feeds; documents read by AI [S9][S10]. | Documents only, for now [`v3_pack_readers*.py`]. |
| Daily reconciliation | "Trusted, reconciled information across all asset classes" (marketing; method not described) [S1]. | "Every feed is reconciled" (marketing; method not described) [S9]. | `e3_recon.py`: four code checks (cash by entity, NAV against investments, limits, trades) with a stated tolerance [`e3_recon.py`]. |
| Data operations team that validates | Yes: analysts correct extractions and relabel documents [S7]. | Not stated. | Not a team. The judge asks a person when two models disagree (`v3_judge.py`). |
| Exception queue | "Processing exceptions captured by automated validation checks" [S7]. | "Flag any outliers for review" [S10]. | Cases from breaks and limit breaches; judge questions to a person [`e3_recon.py`, `v3_judge.py`]. |
| Confidence threshold to a human | Yes: "documents flagged with low confidence scores are reviewed by our data operations analysts" [S15]. | Not stated. | Not implemented as a confidence threshold. Two-model agreement is the trigger instead. |
| Validation rules | "Automated data and document quality checks" [S15]. | Not described. | Rule checks in `v3_rule_checks.py`; declared figure tie-outs in each recipe. |
| Audit trail | Not described on operations page. | "Full audit-ready logs" [S10]. | Six-step trail: source, file, read, checked, stored, used by [`a5_trail.py`]. |
| Corporate actions | Not described. | Not described. | Table built later; not in the recipes I read. |
| Pricing source | Not described. | Not described. | Second-price source table exists (`market_observations`, assumption A22). |
| Published accuracy or SLA | None. | None. | None. Round-7 review: 28 of 100 Pass, 34 Partial, 24 Fail [S-local-R7]. |

**Key observation.** Neither competitor publishes an accuracy rate, an error rate, or a reconciliation break rate. Both describe a process. Addepar at least describes a human step in the job postings [S7]. That is a process a family-office buyer can ask about in a demo. Our advantage is that the process is visible in the product (receipts and the trail), not only described on a website. That advantage only counts if our answers are right, which round 7 does not yet show.

---

## 4. Feature gap table (ranked by impact on a family-office buyer)

Impact rates how much a family-office buyer would weigh the gap in a purchase decision. Ranking is my judgement, based on the evidence above.

| Rank | Feature | Addepar | Masttro | Signal Harbor today | Gap |
|---|---|---|---|---|---|
| 1 | Live custodian and bank feeds at scale | Hundreds (300+ per third parties) [S1][S12] | 650–750+ [S8][S9][S11] | File intake; no live feed connector found in docs **(unverified)** | **Large.** The first question a buyer asks. |
| 2 | Private-markets document automation across layouts | Yes; AI plus analysts [S7][S15] | Yes; AI classification and extraction [S10] | One capital-call layout (A25) | **Large.** UC01 works for one layout only. |
| 3 | Ownership graph and look-through | Entity graph; no look-through endpoint found [S13] | "Ownership hierarchies" [S9] | Entities and portfolios; look-through not built (A24) | **Medium-large.** |
| 4 | Performance (TWR, IRR, MOIC, TVPI) with benchmarks | Named; method not public [S14] | Dashboards; method not named [S10] | Not seen in docs read **(unverified)** | **Medium-large, pending check.** |
| 5 | Human review queue for low-confidence extractions | Yes [S7][S15] | Outliers flagged, reviewer unnamed [S10] | Two-model disagreement only | **Medium.** Easy to copy (section 5). |
| 6 | Conversational AI assistant | Addison, launched March 2026, grounded and permission-aware [S5][S6] | None found [S9] | Consume natural-language Q&A; answer quality mixed (round 7) [S-local-R7] | **Medium.** Parity on the feature, behind on answer quality. |
| 7 | Client portal and white-label mobile app | iOS and Android previewed May 2026 [S6] | Mobile app; secure messaging portal [S9] | Not seen in docs **(unverified)** | **Medium.** Not in the core buyer story. |
| 8 | Public API and developer docs | Public REST API, OAuth, MCP connector [S13][S18] | "API lets datasets integrate" [S9] | Internal only **(unverified)** | **Medium.** |
| 9 | Security certification | SOC 3 (2024–25) [S19]; SOC 2 Type II and ISO 27001 unconfirmed | ISO/IEC 27001:2022 [S9] | Not in docs **(unverified)** | **Medium.** Buyers ask for SOC 2 or ISO in procurement. |
| 10 | Onboarding and managed data operations | Analysts in data ops [S7]; implementation 30 to 90 days, or 6 to 12 months by third-party estimates [S20] | 12–14 weeks with project support [S9] | No managed service in docs | **Medium.** Onboarding speed is a buying criterion. |
| 11 | Published pricing | No list price; estimates only [S20] | Fixed annual, not AUM-based [S9] | Not in docs **(unverified)** | **Small to medium.** |
| 12 | Corporate actions | Not described | Not described | Table built, not wired into recipes **(inferred)** | Possible advantage. |

---

## 5. What Signal Harbor has that they do not show publicly

These are advantages in the sense that the competitors' public materials do not describe them. Each claim is either sourced to our own docs or marked **(inferred)**.

1. **Receipts per figure.** Each figure shows where it comes from ("Built from", "Where this number comes from", "What I assumed", "Also used by") [`v3_figstore.py` header]. Addepar says "traceable outputs" and Masttro says "audit-ready logs" [S6][S10]. Neither describes a per-figure receipt in public (inferred).
2. **Two models from different families checking each judgement.** Agreement is trusted and recorded as an assumption; disagreement becomes one question to a person, quoting both [`v3_judge.py`]. No public evidence that either competitor does this (inferred).
3. **Signals as declared objects, verified against answer keys.** The weekend plan calls this the moat [docs/v3/WEEKEND-PLAN.md]. Neither competitor publicly describes a verifiable signal library (inferred).
4. **Signed rules tied to money.** Payment approvals, a call-back before a changed bank account is paid, and a cash buffer are signed rules, not settings [UC01]. Competitor public pages describe permissions and alerts, not payment holds (inferred).
5. **A knowledge map** of what the office knows and where it came from (`docs/v3/use-cases` Knowledge centre; UC01 step 7). Not described by either competitor.

**Where Addepar is ahead on the same ground:** it has shipped conversational AI in production, and it has a published API and an MCP connector [S5][S13][S18]. It can say "we have 1,400 firms and USD 9 trillion" [S6]. We cannot yet say the equivalent.

---

## 6. Concrete accuracy mechanisms to adopt

Ordered by effort (lowest first), with impact in the same line. Each names the code it would change.

**1. Field-level confidence threshold with a human check queue (low effort, high impact).**
Addepar's pattern: documents with low confidence go to an analyst [S15]. Signal Harbor already has two-model agreement. Add a per-field confidence score from the reader and route low-confidence fields to a review case, not only disagreements.
*Changes:* `sh_platform/v1/v3_pdf.py` (field extraction), `v3_judge.py` (new "single read, low confidence" trigger), `extracted_fields` review status.
*Reason:* it is the mechanism buyers can see in a demo, and Addepar has it already.

**2. Rule checks on each incoming document, before it is used (low effort, high impact).**
Addepar runs "automated data and document quality checks" before ingestion [S15]. Harbor can check the capital call in UC01 before the figure is used: the purpose lines (900,000 new investments plus 350,000 management fee) must sum to the notice amount (1,250,000); the due date must follow the notice date; the call must not exceed the unfunded amount; the bank account must match `bank_accounts`.
*Changes:* `sh_platform/v1/v3_rule_checks.py` (new document checks), `v3_rows.py`.
*Reason:* cheap, deterministic, and catches the exact fraud and error cases UC01 is built around.

**3. Reconcile capital calls to bank statements, not only cash to positions (medium effort, high impact).**
Masttro says "every feed is reconciled" [S9]. Harbor reconciles cash and NAV but not a capital call paid against the bank line that paid it. UC01 step 6 describes this match in words, not in code.
*Changes:* `sh_platform/v1/e3_recon.py` (new `capital_calls` check reading `cash_movements` and the bank statement), and a case type for unmatched calls.
*Reason:* it closes the loop from notice to paid, which is the buyer's real question.

**4. Turn analyst corrections and round-7 failures into a regression set (medium effort, high impact).**
Addepar relabels documents to retrain its models [S7]. Harbor's judge already keeps a person's answer and wins from then on (`v3_judge.py`). Store each correction as a labelled case, and run the 100 use cases against it on every change. Round 7 found 24 wrong or missing answers; those should become the first cases.
*Changes:* `sh_platform/v1/v3_judge.py` (persist corrections as cases), `packs/family_office/1/` answer keys, a regression runner.
*Reason:* accuracy needs a number that can go down; without a regression set, round 7's 28-of-100 cannot be watched.

**5. Generalise the capital-call reader beyond one layout (high effort, high impact).**
Addepar and Masttro both claim the readers "regardless of formatting" (Masttro) or across alternatives types (Addepar) [S9][S7]. Harbor's reader is built for one layout (A25). Start with the three layouts already in the samples (calls 5, 6 and 7 in UC01), then test on new layouts with the regression set from mechanism 4.
*Changes:* `sh_platform/v1/v3_pdf.py`, `v3_pack_readers_invest.py`, a layout registry keyed by issuer.
*Reason:* it is the largest reach gap, and it is the one that decides whether Harbor works on a new fund's notices on day one.

**Not in the top five, but worth tracking:** corporate actions wiring (`corporate_actions`), second-price source for valuations (`market_observations`), and a published accuracy metric once the regression set has numbers.

---

## 7. Open checks before this is used in a sales or board conversation

- Confirm whether Harbor has any live custodian or bank connector. The gap in section 4, row 1, depends on it.
- Confirm Harbor's security status (SOC 2, ISO 27001) and whether its APIs are public.
- Confirm Harbor's TWR and IRR methods, if they exist.
- Obtain Addepar's SOC 2 Type II report and ISO 27001 status directly, under NDA, if a buyer asks.
- Obtain a formal quote from each vendor. Current pricing figures are estimates.
- Re-check Masttro's custodian count. It changes between 650, 700 and 750 across its own pages.

---

## Sources

Competitor sources were fetched or searched on 21 October 2026. Where a fetch failed, the search-result summary is used and marked.

- [S1] Addepar, Operations page. https://addepar.com/operations (fetched)
- [S2] Addepar, Wealth management page. https://www.addepar.com/solutions/ria (search result summary)
- [S3] Addepar, Alts Data Management fact sheet. https://addepar.com/assets/addepar-alts-data-management-overview-fact-sheet.pdf (could not be read; binary PDF)
- [S4] Addepar, Alts Data Management product PDF. https://addepar.com/assets/addepar-alts-data-management.pdf (search result only)
- [S5] Addepar Addison launch coverage, Wealth Management. https://www.wealthmanagement.com/artificial-intelligence/addepar-launches-addison-ai-for-natural-language-portfolio-analysis (search result summary; launch date 3 March 2026 from this summary)
- [S6] Addepar, "Addepar Unveils Addison, a Native AI Experience..." press release, webdisclosure. https://www.webdisclosure.com/press-release/addepar-etr-addepar-unveils-addison-a-native-ai-experience-built-to-deliver-actionable-intelligence-across-investment-workflows-z1OmR6JImIT (fetched)
- [S6b] AddeConf26 coverage, MarTech Series. https://martechseries.com/predictive-ai/ai-platforms-machine-learning/addepar-advances-its-ai-innovation-across-agents-data-and-workflow-capabilities/ (fetched)
- [S7] Addepar, Alts Data Operations Analyst job posting. https://jobs.8vc.com/companies/addepar/jobs/34511404-alts-data-operations-analyst (fetched; posting closed)
- [S8] Masttro, launch press release, Business Wire, 25 November 2024. https://www.businesswire.com/news/home/20241125111634/en/Masttro-Launches-Next-Gen-Platform-for-Wealth-Management (could not be fetched, 403; the 650+ figure is from a search summary)
- [S8b] Masttro launch via StreetInsider. https://www.streetinsider.com/Business+Wire/Masttro+Launches+Next-Gen+Platform+for+Wealth+Management/24051783.html (could not be fetched, 403)
- [S9] Masttro, Family office software page. https://masttro.com/family-office-software (fetched)
- [S10] Masttro, Alternative investment document management page. https://masttro.com/insights/alternative-investment-document-management (fetched)
- [S11] Masttro, single family office page (700+ connections figure). https://masttro.com/family-office-software (search result summary; count differs from the fetched page)
- [S12] Third-party profile of Addepar custodian count, andsimple.co. https://andsimple.co/companies/addepar/?amp=1 (search result summary; "more than 300")
- [S13] Addepar Developers docs: Query, Entities, Positions. https://developers.addepar.com/docs/query ; https://developers.addepar.com/docs/entities ; https://developers.addepar.com/docs/positions (search result summaries; not fetched)
- [S14] Addepar, capital calls and alternatives (IRR, MOIC, TVPI) on the operations FAQ. https://addepar.com/operations (fetched, see S1)
- [S15] Addepar, Alts Data Management, human review and automated checks. Source: Addepar Q1 2025 newsletter https://addepar.com/blog/inside-addepar-q1-2025 (search result summary)
- [S16] Masttro and Arch partnership, 17 July 2025. https://www.businesswire.com/news/home/20250717390003/en (could not be fetched, 403; summary from search results and https://www.wealthsolutionsreport.com/arch-teams-with-masttro-to-give-uhnw-investors-enhanced-alts-data/)
- [S17] Unofficial Python client, addepy. https://pypi.org/project/addepy/ (search result only)
- [S18] Addepar MCP connector listing. https://claude.com/ja/connectors/addepar (search result only)
- [S19] Addepar SOC 3 report, Analytics & Reporting and Navigator platforms, 2024–2025. https://addepar.com/assets/addepar-analytics-reporting-and-navigator-platforms-soc-3-2024-2025.pdf (search result summary; not fetched)
- [S20] Kubera, Addepar pricing estimates (competitor source; treat with caution). https://www.kubera.com/blog/addepar-pricing (search result summary). Other estimates: Sacra and Aleta, as cited in the same search results.
- [S-local-R7] Signal Harbor round-7 live answers review, 18 October 2026. `docs/v3/LIVE-R7-ANSWERS.md` (local)
- [S-local-UC01] Signal Harbor UC01 capital call model card. `docs/v3/use-cases/UC01-CAPITAL-CALL.md` (local)
- [S-local-ASSUMP] Signal Harbor assumptions. `docs/v3/ASSUMPTIONS.md` (local)
- [S-local-100] Signal Harbor use cases. `docs/v3/USE-CASES-100.md` (local)
- [S-local-code] Signal Harbor code: `sh_platform/v1/v3_judge.py`, `e3_recon.py`, `v3_figstore.py`, `v3_rule_checks.py`, `a5_trail.py`, `v3_pdf.py`, `v3_pack_readers*.py` (local)
