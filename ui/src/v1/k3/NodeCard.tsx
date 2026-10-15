import { Button, Pill } from "../../design";
import type { OntoEdge, OntoNode, Ontology } from "./api";
import { day } from "./dates";

// What a thing on the map is, who owns it, where it came from, what depends on it, and whether it is on the verified map.
const VERB: Record<string, [string, string]> = { // [reading from the thing, reading towards the thing]
  owns: ["Owns", "Owned by"], feeds: ["Feeds", "Fed by"], "defined by": ["Defined by", "Defines"], "decided in": ["Decided in", "Where it was decided"],
  "raised from": ["Raised from", "Led to"], "built by": ["Built by", "Built"],
};

export function stateLine(n: OntoNode): { tone: "signed" | "draft" | "open"; text: string } {
  if (n.state === "verified") return { tone: "signed", text: n.verified_by ? `Verified by ${n.verified_by}, ${day(n.verified_at)}` : "Verified" };
  if (n.sent_back) return { tone: "open", text: `Sent back by ${n.sent_back.by}: ${n.sent_back.reason}` };
  return { tone: "draft", text: n.waiting ? "Finished, waiting for the head of data" : "In progress. It joins the verified map when its project completes." };
}

export default function NodeCard({ node, o, edges, onGo, onReview }: { node: OntoNode; o: Ontology; edges: OntoEdge[]; onGo: (id: string) => void; onReview?: () => void }) {
  const by = new Map(o.nodes.map((n) => [n.id, n]));
  const groups = new Map<string, string[]>();
  for (const e of edges) {
    const out = e.from === node.id, inn = e.to === node.id;
    if (!out && !inn) continue;
    const key = VERB[e.rel]?.[out ? 0 : 1] ?? e.rel;
    groups.set(key, [...(groups.get(key) ?? []), out ? e.to : e.from]);
  }
  const s = stateLine(node);
  return (
    <aside aria-label="About this item" className="ds-card" style={{ padding: 16, display: "grid", gap: 12 }}>
      <div>
        <div className="ds-footnote" style={{ textTransform: "uppercase", letterSpacing: 1, fontSize: 12 }}>{node.type_word}</div>
        <h2 style={{ margin: "2px 0 0", fontSize: 20 }}>{node.label}</h2>
      </div>
      <div><Pill tone={s.tone}>{node.state === "verified" ? "Verified" : node.sent_back ? "Sent back" : node.waiting ? "Waiting for review" : "In progress"}</Pill>
        <div className="ds-muted" style={{ marginTop: 6 }}>{s.text}</div></div>
      {node.sub ? <p style={{ margin: 0 }}>{node.sub}</p> : null}
      <dl style={{ margin: 0, display: "grid", gridTemplateColumns: "auto 1fr", gap: "4px 12px" }}>
        <dt className="ds-muted">Owner</dt><dd style={{ margin: 0 }}>{node.owner ?? "Not named yet"}</dd>
        <dt className="ds-muted">{node.type === "definition" ? "Signed" : "Last change"}</dt><dd style={{ margin: 0 }}>{day(node.at)}</dd>
        {node.health ? <><dt className="ds-muted">Health</dt><dd style={{ margin: 0 }}>{node.health === "ok" ? "On time" : node.health_note}</dd></> : null}
      </dl>
      {[...groups.entries()].map(([title, ids]) => (
        <div key={title}><strong>{title}</strong>
          <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{[...new Set(ids)].map((i) => <li key={i}><Button onClick={() => onGo(i)}>{by.get(i)?.label ?? i}</Button></li>)}</ul></div>
      ))}
      {!groups.size ? <p className="ds-muted" style={{ margin: 0 }}>Nothing is connected to this yet.</p> : null}
      {node.waiting && onReview ? <Button variant="primary" onClick={onReview}>Open the review queue</Button> : null}
    </aside>
  );
}
