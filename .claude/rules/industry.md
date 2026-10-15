# The industry is a parameter

The last build leaked insurance content into every other industry. This rule exists to stop that.

- No module hardcodes an industry, a KPI id, a column name or demo wording. All of it comes from `packs/<industry>/` through the pack loader.
- A company with no pack for its industry gets an honest empty state, never another industry's content.
- Pack content is always labelled as a suggestion ("what others in the industry usually track"), never as the company's own definition or policy.
- Every module's tests run against at least two industries and an empty company.
- Licensed industry data (for example a market data terminal) arrives through the tool registry and the egress gateway as an inbound connector, entitled per company. It is never copied into a pack.
