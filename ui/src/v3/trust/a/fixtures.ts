// Synthetic test data only.
import type { Language, Model } from "../../api";

export const json = (b: unknown, ok = true) =>
  new Response(JSON.stringify(b), { status: ok ? 200 : 500, headers: { "Content-Type": "application/json" } });

export const model: Model = {
  pack: { id: "family_office", label: "Family office", version: 1 },
  objects: [
    { name: "entity", label: "Entity", table: "entities", from: "industry", count: 4, properties: [{ name: "name", label: "Name", column: "entities.name" }], relations: [{ to: "commitment", label: "commits to" }] },
    { name: "commitment", label: "Commitment", table: "commitments", from: "office", count: 12, properties: [{ name: "amount", label: "Amount", column: "commitments.amount_usd" }, { name: "uncalled", label: "Uncalled", derived: "amount_usd - called_to_date" }], relations: [] },
    { name: "index", label: "Index", table: "indices", from: "proposed", count: 3, properties: [], relations: [] },
  ],
  coverage: { pct: 92, unmapped: ["hedge_flag"] },
  proposals: [{ id: "p1", text: "Recallable: a new property of Commitment", object: "commitment", property: "recallable" }],
  versions: [{ v: 1, at: "1 Oct", by: "Leo", change: "first definition" }],
};
export const noPack: Model = { pack: { id: "", label: "", version: "" }, objects: [], proposals: [], versions: [], coverage: { pct: 0, unmapped: [] } };
export const language: Language = {
  words: [{ word: "dry powder", means: "uncalled commitment", by: "Mei", used: 4 }],
  corrections: [{ id: "c1", text: "the book means the listed portfolio" }],
  golden: [{ q: "How much is dry powder?", a: "USD 13.1m uncalled.", by: "Mei" }],
  taught: [{ name: "Span modelling playbook", books: 4, on: true, version: 2 }],
};
export const packs = {
  packs: [{ id: "family_office", label: "Family office", objects: 8, questions: 12 }, { id: "insurance", label: "Insurance", objects: 8, questions: 9 }],
  current: "family_office",
};
