import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { Pill, type PillTone } from "../../design";
import { getPainPoints, type Coverage, type PainPoints } from "./api";

// W2: walk the customer's pain points cluster by cluster. Each says what Signal Harbor does, how well it is covered (honestly, including what it leaves to other systems) and where to see it.
const WORD: Record<Coverage, string> = { strong: "Covered", partial: "Partly covered", not_in_scope: "Not in scope" };
const TONE: Record<Coverage, PillTone> = { strong: "ok", partial: "late", not_in_scope: "draft" };

export default function PainPointDemo() {
  const [q] = useSearchParams();
  const [d, setD] = useState<PainPoints | null>(null);
  const [err, setErr] = useState("");
  const [at, setAt] = useState(0);
  useEffect(() => { getPainPoints(q.get("name") ?? "").then(setD, () => setErr("We could not load the pain points. Please try again.")); }, [q]);
  if (err) return <p role="alert" className="state state-error">{err}</p>;
  if (!d) return <p className="ds-soft">Loading the pain points…</p>;
  const g = d.clusters[Math.min(at, d.clusters.length - 1)];
  if (!g) return <p className="ds-soft">No pain points yet.</p>;
  return (
    <section style={{ display: "grid", gap: 12 }} aria-label="Pain points">
      <h1 style={{ margin: 0 }}>Your pain points and what we do about them</h1>
      <p className="ds-soft">{d.total} pain points: {d.counts.strong} covered, {d.counts.partial} partly covered, {d.counts.not_in_scope} not in scope. {d.source === "sample" ? "Showing the generic sample list." : "Showing your own list."}</p>
      <nav aria-label="Clusters" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {d.clusters.map((c, i) => (
          <button key={c.cluster} type="button" className="ds-chip" aria-pressed={i === at} onClick={() => setAt(i)} style={{ minHeight: 44, fontWeight: i === at ? 700 : 400 }}>{c.cluster} ({c.items.length})</button>
        ))}
      </nav>
      <h2 style={{ margin: 0, fontSize: 17 }}>{g.cluster}</h2>
      {g.items.map((p) => (
        <article key={p.id} className="ds-card" style={{ display: "grid", gap: 6, padding: 14 }}>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <strong>{p.title}</strong>
            <span className="ds-chip" style={{ padding: "2px 8px", fontSize: 12 }}>{`Severity: ${p.severity}`}</span>
            <Pill tone={TONE[p.coverage]}>{WORD[p.coverage]}</Pill>
          </div>
          <span>{p.does}</span>
          {p.coverage === "not_in_scope" && <span className="ds-muted">{p.reason}</span>}
          {p.link && <Link className="ds-link" to={p.link} style={{ minHeight: 44, display: "inline-flex", alignItems: "center" }}>{`Show me: ${p.use_case}`}</Link>}
        </article>
      ))}
    </section>
  );
}
