import { useState } from "react";

import { Button } from "../../design";
import type { Change, Proposal } from "./proposals";

export type { Proposal };

// L1/L2: the bar over the strip that shows what an agent proposed, with Accept and Not this. The changed lines are listed here and
// marked in the documents (see ChangedLines) until the person decides. With no proposals nothing shows.
const WORD = { add: "New", change: "Changed", remove: "Removed" } as const;

// V6 walk gap 3: a path such as sow/goal/needed_by reads "Goal: needed by", never the raw field name.
const human = (w: string) => w.replace(/_/g, " ");
export function lineLabel(path: string): string {
  const parts = path.split("/").filter((x) => x && !/^\d+$/.test(x));
  const [section, field] = parts.slice(-2);
  const named: Record<string, string> = { kpis: "KPI", sources: "Source", steps: "Process step", governance: "Rule", unclear: "Open point", catalogue: "Catalogue" };
  const word = (x: string) => named[x] ?? human(x).replace(/^./, (c) => c.toUpperCase());
  return field ? `${word(section ?? "")}: ${human(field)}` : word(section ?? path);
}

export function ChangedLines({ changes }: { changes: Change[] }) {
  if (!changes.length) return null;
  return (
    <ul className="wb-lines" aria-label="Proposed changes in this document">
      {changes.map((c, i) => (
        <li key={i} className={`wb-line wb-line--${c.op}`}>
          <b>{WORD[c.op]}:</b> {lineLabel(c.path)}
          {c.op === "change" ? <> <s className="wb-before">{c.before}</s> {c.after}</> : c.op === "remove" ? <> <s className="wb-before">{c.before}</s></> : <> {c.after}</>}
        </li>
      ))}
    </ul>
  );
}

export default function ChangeBar({ proposals = [], onAccept, onReject, error = "", busy = false }: {
  proposals?: Proposal[]; onAccept?: (id: string) => void; onReject?: (id: string, reason?: string) => void; error?: string; busy?: boolean;
}) {
  const [asking, setAsking] = useState<string | null>(null);
  const [why, setWhy] = useState("");
  if (!proposals.length) return null;
  return (
    <div className="wb-changes" role="region" aria-label="Proposed changes">
      {proposals.map((p) => (
        <div key={p.id} style={{ marginBottom: 6 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <span>{p.summary}</span>
            <Button variant="primary" disabled={busy} onClick={() => onAccept?.(p.id)}>Accept</Button>
            <Button disabled={busy} onClick={() => { setAsking(asking === p.id ? null : p.id); setWhy(""); }}>Not this</Button>
          </div>
          {asking === p.id ? (
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginTop: 4 }}>
              <label>Why not? (optional) <input type="text" value={why} maxLength={300} onChange={(e) => setWhy(e.target.value)} /></label>
              <Button disabled={busy} onClick={() => { onReject?.(p.id, why); setAsking(null); }}>Turn it down</Button>
            </div>
          ) : null}
        </div>
      ))}
      {error ? <p role="alert" className="ds-error" style={{ margin: 0 }}>{error}</p> : null}
    </div>
  );
}
