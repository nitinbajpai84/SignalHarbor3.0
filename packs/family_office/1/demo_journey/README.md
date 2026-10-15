ILLUSTRATIVE: invented for demonstration

# Demo journey content (synthetic)

`journey.yaml` is the content `tools/seed_demo_journey.py` writes, through the real stores and routes, into one demo company so every
screen has something to show: two walls, a signed charter with build roles, a signed baseline of twelve measures, a module 3
assessment and plan, the build centre's records, two map comments, a kept what-if and one drafted message of each kind.

Everything here is invented. The people are the demo company's own illustrative people list (`local/companies.yaml` and its
`01-people/people.csv`); the facts follow the family-office demo story in `../demo_story/` (late call notices, the September
Harborview IV call, the USD purchase at T+2, the reserve, the bonus rule's funding-discipline share, benchmarks nobody owns).
No figure here is a real client's. Measure names and business definitions are read from `../kpi_tree.yaml`, not copied.

Run: `python tools/seed_demo_journey.py <company id> [--reset]`.
