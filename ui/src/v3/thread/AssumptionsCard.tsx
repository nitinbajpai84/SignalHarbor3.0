import { useState } from "react";

import type { Assumption } from "../api";
import "./trust.css";

const FOLD = 5;

/** The office never sees "model": the backend's wording is put in the office's own. */
export function sourceWords(s: string): string {
  const rule = /\bA\d+\b/.exec(s);
  if (/^ASSUMPTIONS/i.test(s) || /^A\d+$/.test(s)) return `Office rule ${rule?.[0] ?? ""}`.trim();
  if (s === "loader") return "From your bank files";
  if (s === "person") return "You told me";
  return s.replace(/models?/g, (m) => (m === "models" ? "checks" : "check"));
}

function Group({ figure, items }: { figure: string; items: Assumption[] }) {
  const [all, setAll] = useState(false);
  const shown = all ? items : items.slice(0, FOLD);
  return (
    <section aria-label={`What I assumed for ${figure}`}>
      <h3>{figure}</h3>
      <ul>{shown.map((a, i) => <li key={i}>{a.text}<small className="v3-mute">{sourceWords(a.source)}</small></li>)}</ul>
      {items.length > FOLD && <button type="button" aria-expanded={all} onClick={() => setAll(!all)}>{all ? "Show fewer" : `Show ${items.length - FOLD} more`}</button>}
    </section>
  );
}

/** Decision 2: "What I assumed", one line each with its source, grouped by figure and folded after five. */
export default function AssumptionsCard({ assumptions }: { assumptions?: Assumption[] }) {
  if (!assumptions?.length) return null;
  const by = new Map<string, Assumption[]>();
  for (const a of assumptions) by.set(a.figure, [...(by.get(a.figure) ?? []), a]);
  return (
    <div className="v3-card t3-assume">
      <span className="v3-kicker">What I assumed</span>
      {[...by].map(([f, items]) => <Group key={f} figure={f} items={items} />)}
    </div>
  );
}
