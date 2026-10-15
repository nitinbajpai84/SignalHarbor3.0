import { useEffect, useState } from "react";

import { ApiError, apiGet } from "../../api/client";
import { Link } from "react-router-dom";

import { Button, Pill, day } from "../../design";
import Comments from "../n2/Comments";
import type { CommentKind } from "../n2/api";

// A2: "Where is this from?" Six steps from the source to where the figure is used. The server builds them (GET /api/v1/trail);
// nothing is worked out here. Used by Action, Build and Consume: <TrailPanel kind id onClose />.
export interface TrailStep { key: string; label: string; state: "done" | "waiting" | "missing" | "restricted"; what: string; who: string | null; when: string | null; refs: { kind: string; id: string; label: string }[] }
export interface Trail { kind: string; id: string; title: string; figure: { label: string; value: string | null; currency: string | null; was?: string | null; was_label?: string | null } | null; steps: TrailStep[] }

const WORDS: Record<TrailStep["state"], string> = { done: "Recorded", waiting: "Waiting", missing: "Not recorded", restricted: "Restricted" };
// The map link needs a node id the map knows (source:, files:, table:, dash:, person:) or an intent id; the current trail refs carry neither, so no link shows until they do.
const MAP_ID = /^(source|files|table|dash|person):/;
function mapLink(t: Trail): string | null {
  const refs = t.steps.flatMap((s) => s.refs);
  const node = refs.find((r) => MAP_ID.test(r.id));
  if (node) return `/centre/map?focus=${encodeURIComponent(node.id)}`;
  const intent = refs.find((r) => r.kind === "intent");
  return intent ? `/centre/map?tab=processes&focus=${encodeURIComponent(intent.id)}` : null;
}
// The server sends plain digits (10000000, -12400); the screen shows them as the rest of the app does: "10,000,000 USD".
function amount(value: string, currency: string | null): string {
  const n = Number(value);
  const text = Number.isFinite(n) ? n.toLocaleString("en-US", { maximumFractionDigits: 2 }) : value;
  return currency ? `${text} ${currency}` : text;
}
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "The trail could not be loaded. Please try again.");

export default function TrailPanel({ kind, id, onClose }: { kind: string; id: string; onClose: () => void }) {
  const [trail, setTrail] = useState<Trail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setTrail(null); setError("");
    apiGet<Trail>(`/api/v1/trail?kind=${encodeURIComponent(kind)}&id=${encodeURIComponent(id)}`).then(setTrail).catch((e) => setError(plain(e)));
  }, [kind, id]);

  return (
    <section className="ds-card" aria-label="Where this is from" style={{ padding: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
        <strong>{trail ? `Where is this from: ${trail.title}` : "Where is this from?"}</strong>
        <Button onClick={onClose}>Close</Button>
      </div>
      {error ? <p role="alert">{error}</p> : null}
      {!trail && !error ? <p className="ds-muted" role="status">Loading the trail.</p> : null}
      {trail?.figure?.value ? (
        <p>{trail.figure.label}: {amount(trail.figure.value, trail.figure.currency)}
          {trail.figure.was ? ` (${trail.figure.was_label ?? "earlier"}: ${amount(trail.figure.was, trail.figure.currency)})` : ""}</p>) : null}
      {trail ? (
        <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 10 }}>
          {trail.steps.map((s, i) => (
            <li key={s.key}>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <strong>{i + 1}. {s.label}</strong>
                <Pill tone={s.state === "done" ? "ok" : s.state === "waiting" ? "draft" : s.state === "restricted" ? "restricted" : "late"}>{WORDS[s.state]}</Pill>
              </div>
              <div>{s.what}</div>
              {s.who || s.when ? <div className="ds-muted">{[s.who, day(s.when)].filter(Boolean).join(" · ")}</div> : null}
            </li>))}
        </ol>) : null}
      {trail && mapLink(trail) ? <p><Link className="ds-link" to={mapLink(trail)!}>Open in the map</Link></p> : null}
      {/* CM1 line 6: the thread on the thing this trail is about (every trail kind is a comment kind) */}
      {trail ? <Comments target={{ kind: kind as CommentKind, id }} eager /> : null}
    </section>
  );
}
