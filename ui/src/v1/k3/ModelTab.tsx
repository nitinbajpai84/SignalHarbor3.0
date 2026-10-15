import { useMemo, useState, type ReactNode } from "react";

import ScreenState from "../../components/ScreenState";
import { useLoad } from "../../components/useLoad";
import Lineage from "./Lineage";
import { getModel, type DataModel, type ModelLayer, type ModelTable } from "./api";

// The Map's third view: the data model in three layers. Bronze as it arrived, silver the office's clean model, gold the ready-made figures.
// Pick a table to see its columns and what changes if it changes. Everything comes from the company's records; row counts only.
const ACCENT: Record<ModelLayer, string> = { bronze: "#B87333", silver: "var(--ds-ink-soft)", gold: "var(--ds-amber)" };
const MONO = "var(--ds-mono, 'IBM Plex Mono', monospace)";
const count = (n: number | null) => (n === null ? "" : `${n.toLocaleString("en-GB")} row${n === 1 ? "" : "s"}`);
const plural = (n: number, one: string) => `${n} ${one}${n === 1 ? "" : "s"}`;

export default function ModelTab({ focus }: { focus: string | null }) {
  const { state, data, message, retry } = useLoad(getModel, "k3-model", (d) => d.tables.length === 0);
  return (
    <ScreenState state={state} message={state === "empty" ? "No table is recorded for you yet. Tables appear here as data is loaded and projects are built." : message} onRetry={retry}>
      {data ? <Model m={data} focus={focus} /> : null}
    </ScreenState>
  );
}

function Model({ m, focus }: { m: DataModel; focus: string | null }) {
  const [find, setFind] = useState("");
  const [whole, setWhole] = useState(false);
  const [graph, setGraph] = useState(false);
  const [picked, setPicked] = useState<string | null>(focus && m.tables.some((t) => t.id === focus) ? focus : null);
  const want = find.trim().toLowerCase();
  const shown = useMemo(() => m.tables.filter((t) => (whole || t.loaded)
    && (!want || t.id.includes(want) || t.columns.some((c) => c.name.includes(want) || c.meaning.toLowerCase().includes(want)))), [m, whole, want]);
  const pick = m.tables.find((t) => t.id === picked) ?? null;
  const lit = new Set(pick ? [...pick.reads, ...pick.feeds.filter((f) => f.kind === "table").map((f) => f.label)] : []);
  const of = (layer: ModelLayer) => shown.filter((t) => t.layer === layer);
  const silver = of("silver");
  const groups = [...new Set(silver.map((t) => t.group))].sort((a, b) => Number(a === "added") - Number(b === "added")); // the model's own order, the company's additions last

  const chip = (t: ModelTable, box: boolean) => {
    const on = pick?.id === t.id, near = lit.has(t.id);
    return (
      <button key={t.id} type="button" aria-pressed={on} onClick={() => setPicked(on ? null : t.id)} style={{
        textAlign: "left", font: `${box ? 500 : 400} ${box ? 13 : 12}px ${MONO}`, color: "var(--ds-ink)", cursor: "pointer",
        background: on || near ? "var(--ds-surface-2)" : "var(--ds-surface)", opacity: t.loaded ? 1 : 0.55,
        border: `${on || near ? 2 : 1}px ${t.added ? "dashed" : "solid"} ${on || near ? "var(--ds-teal-bright)" : t.added ? "var(--ds-amber)" : "var(--ds-line-2)"}`,
        borderRadius: box ? 10 : 8, padding: box ? "9px 11px" : "6px 9px",
      }}>
        <div>{t.id}</div>
        {box ? <div className="ds-muted" style={{ font: "12px var(--ds-font)" }}>
          {[t.layer === "bronze" ? t.source : t.project, t.layer === "bronze" ? t.cadence : "", t.rows !== null ? count(t.rows) : ""].filter(Boolean).join(" · ")}</div> : null}
      </button>
    );
  };
  const column = (layer: ModelLayer, body: ReactNode, wide = false) => (
    <section aria-labelledby={`dm-${layer}`} className="ds-card" style={{ padding: 14, display: "flex", flexDirection: "column", gap: 8, flex: wide ? "1.6 1 0" : "1 1 0", minWidth: 240 }}>
      <h2 id={`dm-${layer}`} style={{ margin: 0, fontSize: 16, color: ACCENT[layer] }}>{m.layers[layer].label} · {m.layers[layer].title}</h2>
      <p style={{ margin: 0, fontSize: 13, color: "var(--ds-ink-soft)" }}>{m.layers[layer].meaning}</p>
      {body}
    </section>
  );
  const none = <p className="ds-muted" style={{ margin: 0, fontSize: 13 }}>{whole ? "None recorded yet." : "None loaded yet. Switch to the whole model to see what is planned."}</p>;
  const kept = <p className="ds-muted" style={{ margin: 0, fontSize: 13 }}>Kept by the data team. Ask the head of data or a data engineer to see these tables.</p>;  // a non-data role: the tables exist, hidden for the role

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <p style={{ margin: 0, color: "var(--ds-ink-soft)" }}>{m.intro}</p>
      {!m.team ? <p className="ds-muted" style={{ margin: 0 }}>You see the ready-made figures of the projects you can open. The raw and company-model tables are the data team&apos;s.</p> : null}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center", fontSize: 14 }}>
        <label htmlFor="dm-find" className="ds-muted">Find a table or column</label>
        <input id="dm-find" value={find} onChange={(e) => setFind(e.target.value)} placeholder="market value, portfolio_id…" style={{
          background: "var(--ds-surface)", color: "var(--ds-ink)", border: "1px solid var(--ds-line-2)", borderRadius: 10, padding: "9px 12px", font: "14px var(--ds-font)", width: 240 }} />
        <span role="group" aria-label="Which tables" style={{ display: "flex", background: "var(--ds-surface)", border: "1px solid var(--ds-line)", borderRadius: 999, padding: 3 }}>
          {([[false, `Loaded · ${m.counts.loaded}`], [true, `Whole model · ${m.counts.whole}`]] as const).map(([w, label]) => (
            <button key={label} type="button" aria-pressed={whole === w} onClick={() => setWhole(w)} style={{
              background: whole === w ? "var(--ds-teal)" : "transparent", color: whole === w ? "var(--ds-on-teal)" : "var(--ds-ink-soft)", border: 0, borderRadius: 999,
              padding: "6px 12px", font: `${whole === w ? 600 : 400} 13px var(--ds-font)`, cursor: "pointer" }}>{label}</button>
          ))}
        </span>
        <span role="group" aria-label="How to draw it" style={{ display: "flex", background: "var(--ds-surface)", border: "1px solid var(--ds-line)", borderRadius: 999, padding: 3 }}>
          {([[false, "Tables"], [true, "Lineage"]] as const).map(([g, label]) => (
            <button key={label} type="button" aria-pressed={graph === g} onClick={() => setGraph(g)} style={{
              background: graph === g ? "var(--ds-teal)" : "transparent", color: graph === g ? "var(--ds-on-teal)" : "var(--ds-ink-soft)", border: 0, borderRadius: 999,
              padding: "6px 12px", font: `${graph === g ? 600 : 400} 13px var(--ds-font)`, cursor: "pointer" }}>{label}</button>
          ))}
        </span>
        {pick ? <span className="ds-muted">Picked: <strong style={{ color: "var(--ds-ink)" }}>{pick.id}</strong> · what it feeds is lit</span> : null}
      </div>

      {graph ? <Lineage m={m} shown={new Set(shown.map((t) => t.id))} picked={picked} onPick={setPicked} /> : <div style={{ display: "flex", flexWrap: "wrap", gap: 14, alignItems: "flex-start" }}>
        {column("bronze", of("bronze").length ? of("bronze").map((t) => chip(t, true)) : m.team ? none : kept)}
        {column("silver", silver.length ? groups.map((g) => {
          const ts = silver.filter((t) => t.group === g);
          return (
            <div key={g} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ font: `500 11px ${MONO}`, letterSpacing: "0.05em", textTransform: "uppercase", color: g === "added" ? "var(--ds-amber)" : "var(--ds-ink-muted)" }}>
                {g === "added" ? `${ts[0]?.group_label} · model v${m.version}` : ts[0]?.group_label}
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>{ts.map((t) => chip(t, false))}</div>
            </div>
          );
        }) : m.team ? none : kept, true)}
        {column("gold", of("gold").length ? of("gold").map((t) => chip(t, true)) : none)}
      </div>}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 14 }}>
        {pick ? <Detail t={pick} /> : <p className="ds-muted" style={{ margin: 0 }}>{shown.length ? "Pick a table to see its columns and what changes if it changes." : "No table matches. Try a shorter word, or the whole model."}</p>}
      </div>
    </div>
  );
}

function Detail({ t }: { t: ModelTable }) {
  const tables = t.feeds.filter((f) => f.kind === "table"), dashboards = t.feeds.filter((f) => f.kind === "dashboard"), reports = t.feeds.filter((f) => f.kind === "report");
  const projects = [...new Set(t.feeds.map((f) => f.project).filter(Boolean))];
  const reached = [dashboards.length ? plural(dashboards.length, "dashboard") : "", reports.length ? plural(reports.length, "report") : ""].filter(Boolean).join(" and ");
  const bits = [tables.length ? `${plural(tables.length, "gold table")} read${tables.length === 1 ? "s" : ""} it` : "", reached ? `${tables.length ? "which feed" : "it feeds"} ${reached}` : ""].filter(Boolean);
  const where = [t.layer === "silver" ? (t.added ? "Added for this office" : "Core model") : t.layer === "bronze" ? "As it arrived" : "Ready-made", t.layer === "silver" ? t.group_label.toLowerCase() : "",
    t.rows !== null ? count(t.rows) : "not built yet", t.owner ? `owner ${t.owner}` : ""].filter(Boolean).join(" · ");
  return (
    <>
      <section aria-labelledby="dm-t" className="ds-card" style={{ flex: "999 1 560px", minWidth: 0, padding: "16px 18px", overflowX: "auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "baseline", flexWrap: "wrap" }}>
          <h2 id="dm-t" style={{ margin: 0, fontSize: 17, fontFamily: MONO }}>{t.id}</h2>
          <span className="ds-muted" style={{ fontSize: 13 }}>{where}</span>
        </div>
        {t.meaning ? <p style={{ margin: "6px 0 10px", fontSize: 14, color: "var(--ds-ink-soft)" }}>{t.meaning}</p> : null}
        {t.reads.length ? <p className="ds-muted" style={{ margin: "0 0 10px", fontSize: 13 }}>It reads: {t.reads.join(", ")}</p> : null}
        <div style={{ display: "grid", gridTemplateColumns: "minmax(170px, 1fr) 110px minmax(240px, 2fr)", gap: "7px 14px", fontSize: 13, minWidth: 560 }}>
          <div className="ds-muted">Column</div><div className="ds-muted">Type</div><div className="ds-muted">Meaning</div>
          {t.columns.length === 0 ? <div className="ds-muted" style={{ gridColumn: "1 / -1" }}>The columns are learned when the first file is loaded.</div> : null}
          {t.columns.map((c) => (
            <div key={c.name} style={{ display: "contents" }}>
              <div style={{ fontFamily: MONO }}>{c.name}</div><div>{c.type}</div><div style={{ color: "var(--ds-ink-soft)" }}>{c.meaning}</div>
            </div>
          ))}
        </div>
      </section>
      <aside aria-labelledby="dm-i" className="ds-card" style={{ flex: "1 1 320px", minWidth: 0, padding: "16px 18px", display: "flex", flexDirection: "column", gap: 8, borderColor: "var(--ds-teal-bright)", background: "var(--ds-surface-2)" }}>
        <h2 id="dm-i" style={{ margin: 0, fontSize: 16 }}>If this table changes</h2>
        <p style={{ margin: 0, fontSize: 14, color: "var(--ds-ink-soft)", lineHeight: 1.5 }}>
          {t.feeds.length ? `${bits.join(", ")}${projects.length ? `, in ${plural(projects.length, "project")}` : ""}.` : "Nothing reads it yet."}
        </p>
        {t.feeds.length ? (
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 14, lineHeight: 1.7 }}>
            {t.feeds.map((f) => <li key={f.id ?? `${f.kind}${f.label}`}>{f.kind === "table" ? f.label : `${f.kind === "report" ? "Report" : "Dashboard"}: ${f.label}`}</li>)}
          </ul>
        ) : null}
        <p className="ds-muted" style={{ margin: 0, fontSize: 13 }}>A change is proposed as a new model version; Span lists what it touches before the head of data approves it.</p>
      </aside>
    </>
  );
}
