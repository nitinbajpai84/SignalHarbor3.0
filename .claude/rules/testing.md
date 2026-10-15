---
paths:
  - "tests/**"
  - "**/tests/**"
  - "ui/**/*.test.*"
---

# Testing

- Write the failing test first for any behaviour change or defect.
- Every test writes to a temporary folder. A guard fails any test that leaves a file in the repo.
- Every module runs against: industry A, industry B, an empty company, and one person working alone.
- Every screen is checked in five states: loading, empty, error, refused, populated.
- Security tests: another company's data is unreachable; a role without access is refused; a switched-off module is refused.
- Agents' model calls are stubbed in unit tests. Live calls run only in the evals suite.
- Test accounts are separate per agent and per person. Never test on a real person's account; a new login can end their session.
- Report exact commands and real counts. Never mark an unrun check as passing.
