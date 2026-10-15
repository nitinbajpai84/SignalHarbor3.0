# The company graph: a context layer that grows after every room (6 Oct 2026)

Status: proposal for Nitin's review. Companion to `docs/specs/INTENT-CENTRE-SPEC.md`. Design screen: canvas artboard 12 (https://claude.ai/artifact/RN9Sh8Fxmmxk99rXTvsxK6).

## 1. What it is

One connected picture of the company: its problems, measures, definitions, processes, systems, fields, people, rules, risks and decisions, and how they join. Every node and edge carries provenance (stated, guessed, unknown; the document, interview, card or signature behind it). It is read by people as a map and by agents as context.

It is a **projection, not a second source of truth**. Each room writes its own records as today (profile, cards, catalogue, process map, trial, plan). The graph is rebuilt from those records whenever one changes. Nothing is edited on the graph directly; a correction goes to the record that owns it and the graph follows. This keeps the signed-record rule intact and means no new store can drift from the stores we already guard.

Where it lives: `plane.path("graph", "company.json")`, the `graph` area the plane already reserves (`sh_platform/plane.py` AREAS). Inside the company data plane; never leaves it.

## 2. Nodes and edges

Node types (all exist as records today except Decision, which is drawn from signatures and accepted ambiguities):

| Type | Comes from | Owner record |
|---|---|---|
| Problem | a cluster on a shelf; before Define, a card | cards, board |
| Pain, Signal, Lever | cards in the Missing, Watch and Levers lanes | cards |
| Measure | catalogue entry | m2 catalogue, pack |
| Term | glossary entry | m2 glossary |
| Process, Step | process map lanes and steps (from owners' answers and SOPs) | m2 process map |
| System, Source, Field | profile systems, catalogue technical definition, data dictionary | profile, catalogue |
| Person, Team | profile people | profile |
| Rule | governed state (classification, who may see), matching rules from the trial, quality rules from the scan | profile governance, m3 rules |
| Risk | accepted ambiguity, accepted risk | m2 known risks, m3 accept |
| Decision | a signature, a shelf placement, an owner confirmation, a settled ambiguity | charter, plan, together audit |
| Plan item | a source in a band | m3 plan |

Edge types: `raised_by` (Problem → Person, anonymous edges carry no person), `measured_by` (Problem → Measure), `defined_as` (Measure → Term), `fed_by` (Measure → Source), `uses` (Source → Field), `produced_by` (Source → Process), `step_of` (Step → Process), `owned_by` (Measure, Source, Process, System → Person), `governed_by` (Measure, Source → Rule), `at_risk` (Measure → Risk), `decided_by` (Risk, Problem → Decision → Person), `moves` (Lever → Measure), `watches` (Signal → Measure), `planned_in` (Source → Plan item), `member_of` (Person → Team).

Every node: `{id, type, label, provenance[], restricted_to?: [names], room: wall|define|truth|build|consume}`. Every edge: `{from, to, type, provenance}`.

## 3. It grows after every room

| After | New on the graph | What a person can now ask |
|---|---|---|
| Bring what you have | People, Teams, Systems, Sources, Fields, Rules from the policy, reported figures as Measure stubs | Who owns which system? Which measures do we already report? |
| Interviews and the wall | Problems, Pains, Signals, Levers, `raised_by` (named cards only) | What hurts most, and whom? Which levers do people believe in? |
| Define | Measures, Terms, Processes, Steps, owners, governed Rules, Risks from accepted ambiguities, Decisions from the vote and the signature | Which problems does one measure serve? Who decided that "return" is before fees? |
| Moment of truth | matching Rules, quality Rules, Risks accepted, Plan items, `fed_by` with match/gap/not-yet status | What breaks if the custodian file is late? Which measures wait on one missing file? |
| Build | tables and lineage as Fields and Sources with `uses`, access rules as Rules | Where does this number come from, column by column? |
| Consume | Scenarios as Decisions, Signals with their outside source | Which lever moves this measure, and what did we assume? |

## 4. Four views, copied from the earlier product

The earlier repo's context layer (V2-Q: `webapp/backend/routers/context_layer.py`, `js/screens/knowledge-graph.js`) replaced an unreadable force-directed graph with four reads, under the rule "no screen ever draws more than one topic's relationships." We copy that rule and those four views:

1. **Shelf**: cards for the most connected or most recently changed nodes, with a search and type chips. The landing view.
2. **Topic**: one node with its edges grouped by type, each edge showing its provenance; "Ask Lens about this" prefilled.
3. **Trace**: one path through the graph, for example Problem → Measure → Source → Field → Process → Person, drawn as a line of cards. This is the lineage view a CFO understands.
4. **Map**: an aggregated picture per room: how many nodes and edges, what changed since the last signature, and the holes (a Measure with no Source, a Source with no owner, a Problem with no Measure). Counts and holes, not a hairball.

A fifth, new: **Impact**. Pick a Source or Rule and the graph shows every Measure, Problem and Person downstream, with the plan band. It answers "what if this file stops arriving" by traversal, no model needed.

## 5. Agents read it too

- Lens answers "ask the graph" questions by traversal first (which nodes, which edges), and only then phrases the answer. The traversal result is the context sent through the egress gateway, tokenised, as counts and labels. The graph itself never leaves.
- North's suggestion cards on the wall come from holes in the graph (a Measure nobody raised a Problem for; a Pain with no Lever), labelled as suggestions.
- Nira's "what is waiting" list is the Map view's holes, by person.

Rules: a node with `restricted_to` is a silhouette to anyone outside the list, on every view and in every traversal result (same filter as `profile.read`). Anonymous cards produce Problem nodes with no `raised_by` edge. The graph is rebuilt, never patched, so a restriction added later removes earlier edges on the next rebuild.

## 6. What we take from Intelligence Warehouse, and what we do not

Their idea: an "intelligence graph" of context, decisions, ontology and metrics above the warehouse, built by an agent ("MORRIE") in conversation with experts, and then queried by agents to find cross-functional decisions nobody saw.

Taken:
- **Decisions are nodes.** We already record signatures, shelf moves, owner confirmations and settled ambiguities; the graph makes them first-class and traceable to a person and a date. This is their "decision blueprint" without a new workflow.
- **Rules are nodes.** Governed state, matching rules and quality rules sit on the graph and can be traversed to the measures and people they touch. Their claim that most agent failures trace to undocumented rules is the same reason our trial writes the amended-notice rule down.
- **Conversation, not questionnaires.** Our interview and the wall already are this; the graph is where their answers land.
- **Cross-function discovery by traversal.** The Impact view and "ask the graph" are this, in a small form.

Not taken:
- A graph database. One JSON file per company, rebuilt from records, is enough for tens of thousands of nodes; a store we cannot inspect is a store we cannot audit.
- Editing on the graph. It would break the signed-record rule.
- Agents executing decisions from the graph. People decide; agents draft. That is the product's promise.
- Their token and cost claims. Ours will be measured, not quoted.

## 7. Build packages (after IC-3)

- **CG-1 Projection**: `sh_platform/graph/build.py` that reads the records and writes `graph/company.json`; a rebuild hook after each record write; per-viewer filter reused from `profile.view`. Tests: two industries, an empty company, restricted node masked, anonymous card has no person edge, rebuild removes stale edges.
- **CG-2 Reads**: shelf, topic, trace, map, impact as routes (copied shapes from V2-Q), counts only, default-deny permissions.
- **CG-3 Screen**: the company map page with the five views, dark and light, opened from the centre home as "Your company, mapped".
- **CG-4 Agents**: Lens traversal-first answers; North suggestions from holes; Nira's list from holes.

Measures of the layer: nodes per room, holes closed per week, "ask the graph" answers that needed no model call, time from a late file to the people told.

## 8. Decisions requested

- A-060 The company graph is a projection rebuilt from the records; nothing is edited on it directly.
- A-061 Decisions and Rules are node types with provenance to a person and a date.
- A-062 No screen draws more than one topic's relationships (the earlier product's rule); the Map view is counts and holes.
- A-063 The graph never leaves the plane; agents receive traversal results as tokenised counts and labels.

## 9. The three-layer shape, and what we add from Questt (added the same day)

Questt (questt.ai) presents the same idea as three layers, "Connect, Capture, Decide": an Intelligence Warehouse (the shared knowledge layer), Morrie (captures rules, constraints and relationships from spreadsheets and people), and coordinated agents that all read the same knowledge so sales, supply and planning stop optimising against each other. They quote under six weeks from onboarding to a first production deployment, for FMCG and retail.

Signal Harbor already has the same three layers under other names. Saying so plainly is useful for the website and the deck:

| Questt | Signal Harbor | State |
|---|---|---|
| Morrie: captures knowledge from spreadsheets and people in conversation | Bring what you have (Lens reads the files) + the interview and the wall (North asks the four questions) | built; the wall is the re-staging |
| Intelligence Warehouse: business logic connected to operational data, "not a data warehouse" | The company graph (this spec): problems, measures, terms, processes, sources, fields, people, rules, risks, decisions, with provenance | specified, CG-1 to CG-4 |
| Coordinated agents reading one knowledge layer | North, Lens, Nira today; the builder, forecaster and ops agents in the Build and Consume centres; all read the graph, none keeps state of its own | partly built |
| Under six weeks to first deployment | Ten working days to a signed gap report; first matching numbers in the first session | measured in part |

Features we take, each tied to a package:

1. **Rule check in conversation (edge-case discovery).** When a person states a rule in the interview or on a card ("an amended notice replaces the one it names"), Lens runs it against the sample files there and then and says what it gives ("counted once, September is SGD 3,520,000; that matches your pack"). The demo run already did this once by accident in a follow-up; make it a rule. Package: IC-2a (the four-question flow) plus a small `rule_preview` in m3's engine. Measure: rules confirmed in conversation versus sent back later.
2. **Cascade before it happens.** The Impact view (section 4) runs on a proposed change as well as the current graph: before a cluster moves shelf, a rule changes, or a source is parked, the screen shows the measures, problems and people downstream and the plan band that moves. Package: CG-2 impact with a `proposed` parameter; Define and Moment of truth call it before committing a drag or an accept. Measure: moves reverted after seeing the cascade.
3. **Cross-function root cause.** Trace a gap or a late file backwards along `fed_by`, `produced_by`, `owned_by` to the step and person where it starts, across teams. Already the Trace view; add "start from a gap" and "start from an alert" entry points in Moment of truth and Ops manager. Package: CG-3.
4. **Decision cards.** A Decision node (a signature, a settled ambiguity, a shelf placement) exported as one page: what was decided, by whom, when, which rule and which measures it binds, and the evidence behind it. Their "decision blueprint", made from records we already hold. Package: CG-3; a Markdown and HTML export like the charter's.
5. **One knowledge layer for every agent.** Written into `.claude/rules/modules.md` and the agent contracts: an agent reads the graph for company facts and never a private cache. Package: CG-4.
6. **Time to first number as the headline measure.** Their six weeks is a sales claim; ours is measured per workspace on the outcomes page: files dropped to first matching measure (today: the same session), first card to signed gap report (target ten working days). Package: LI-OUTCOMES.

Not taken: industry-specific agents (beat optimisation, allocation). Our agents stay generic and the industry stays a pack parameter (rule 6). Autonomous execution: people decide, agents draft.
