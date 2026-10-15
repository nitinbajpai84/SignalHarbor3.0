# Team of ten: shared brief for the two build agents (15 Oct)

Nitin: the app is four things - Action (what to do today), Build (what to build from those actions), Consume (how it shows in the
whole picture), Knowledge (how the mind works). For each person in a company, from CIO to clerk: their actions, the builds Harbor can
suggest from them, the skills those builds use, and proof that the person can build it, do their work, and see it land on their dashboard.

## The ten people (synthetic Evergreen Office; use exactly these ids, names and titles)

| id | name | title | primary build (use case in docs/test/10UC-*.md) |
|---|---|---|---|
| cio | Raj Patel | Chief Investment Officer | UC1 why NAV / P&L moved; second: UC4 portfolio vs benchmark |
| cfo | Daniel Foo | Head of Finance | UC6 can each entity meet its capital calls |
| head_of_data | Anita Rao | Head of Data | UC10 a data pipeline and insight |
| principal | Mei Chen | Principal | a morning net-worth note she reads (consume side of UC1/UC6) |
| investment_analyst | Sofia Reyes | Investment Analyst | UC7 manager diligence: what changed since the last meeting |
| ops_lead | Grace Ong | Operations Lead | UC2 reconciliation and break desk |
| fund_accountant | Helen Foo | Fund Accountant | UC3 manager statements expected vs received, late |
| risk_officer | Tom Hale | Risk and Compliance Officer | UC5 allocation and limit monitoring |
| hr_admin | Priya Nair | Office and HR Manager | UC9 process map and SOP (e.g. new-joiner onboarding, expense approval) |
| ops_clerk | Sam Lee | Operations Clerk | UC8 trades vs the administrator |

Tom Hale, Priya Nair and Sam Lee are new synthetic people (add them as accounts where an office is made for a test).

## Pack file schema: `packs/family_office/1/role_builds.yaml` (industry suggestions, never enforced; the person decides)
```yaml
template: family_office@1
roles:
  - id: cfo
    title: Head of Finance
    person: Daniel Foo            # the synthetic person in the demo office
    actions:                      # what this person acts on, in plain words (3-5)
      - "Approve funding for a capital call"
    builds:                       # suggested use cases (1-2), each startable in one click
      - id: uc6-liquidity
        title: "Can each entity meet its capital calls?"
        say: "I want to know every morning whether each entity can meet its capital calls from cash..."   # first message, the person's own words
        files: ["bank_cash", "commitments", "notices"]     # folders under tests/v1/fixtures/10uc (or docs/demo/uc6/sources/<month>)
        skills: ["intent.restate-ask", "data.recognise-file", "check.against-source", "consume.answer-question"]   # ids from docs/v3/SKILLS-CATALOGUE.md
        dashboard: "Consume: cash by entity and calls due"
        check: {ask: "What is our cash by entity today?", expect: ["2,287,630.12"]}      # from the answer key; [] when no number applies
```
Every number in `check.expect` must be copied from docs/test/10UC-ANSWER-KEY.md or docs/demo/uc6/ANSWER-KEY.md; never invent one.
