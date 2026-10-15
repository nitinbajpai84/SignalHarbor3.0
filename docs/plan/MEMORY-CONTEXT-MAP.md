# Agent memory and the context map (Nitin, 9 Oct 2026)

Nitin: long-term memory is conversations summarised and kept; shared across the agents; an internal knowledge map (context map) that tracks what people talk about with the agents, the way graft tracks code; any agent, including a new one, answers from **the context map + RAG + the model**; short-term and long-term memory kept in a recorded format, with a vector store.

## Three layers, one store per company (data plane only)

| Layer | What it holds | Written when | Read by |
|---|---|---|---|
| Short-term | The last turns of one conversation and its focus object (tile, case, plan change, draft) | Every turn | The agent in that conversation |
| Long-term memory | (a) Conversation summaries: after a conversation goes quiet or reaches N turns, a summary (who, agent, about what, decisions, open questions, preferences learned) is written and the raw turns stay as the source. (b) Per-person preferences, facts, corrections. (c) Company agreed words (linked to k2_map definitions). | Summary job; rules for "from now on / always / I prefer"; corrections | Every agent, filtered by who may see it |
| Context map | A graph: person, agent, conversation, summary, topic, project, intent, case, dashboard/tile, table, KPI/definition, document, decision, open question. Edges: talked_with, about, mentions, decided, asked, refers_to, supersedes, same_as. Extends the company map graph (i5_graph / m1 MapPage), it is not a second graph. | From each summary and each turn's recognised entities (program first: ids, table names, project ids, people; model only to propose topic labels, through egress) | `context_for()` and the Map page |

Vectors: summaries and long-term items are embedded locally with the existing `doc_embed` (fastembed, nothing leaves the machine) in the plane's vector store next to `doc_index`; search is hybrid words + meaning as for documents.

## One entry point for every agent

`context_for(agent, viewer, question, focus) -> {recall, graph, passages}`: graph neighbours of the focus and of the entities in the question (2 hops, access-filtered) + vector hits over summaries/memory + document RAG passages (doc_index) + the short-term turns. North, Span, Lumen, Tally and any future agent call this one function; the result goes to the model only through the egress gateway with names tokenised.

## Rules

- Never across companies; a person's private items only for that person; conversation summaries visible to the people who could see the conversation (project and E1d access).
- A person can see, correct and forget anything about them; forgetting removes the item, its vectors and its graph edges.
- No client figures stored as memory text: figures stay in the warehouse and are referenced by id.
- Screen: "What the agents remember about you" (Settings), and a "Conversations" tab on the Map showing the context map.

## Build order

1. MEM1 (running 9 Oct): short-term, per-person long-term, Lumen follow-ups, shared hooks.
2. MEM2 (after MEM1 lands): conversation summaries, the context map on the company map graph, vector store for memory, `context_for()` wired into all four agents, the Map "Conversations" tab.
