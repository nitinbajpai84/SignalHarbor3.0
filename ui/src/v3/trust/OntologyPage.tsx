import { useState } from "react";
import { Link } from "react-router-dom";

import V3Frame from "../Frame";
import TrustTabs from "../TrustTabs";
import { decideProposal, getModel, type Model, type ModelObject } from "../api";
import { plainName } from "../plain";
import { usePhone } from "../knowledge/k/usePhone";
import { Status, useLoad } from "./a/useLoad";

const FROM: Record<ModelObject["from"], string> = { industry: "In the model", office: "Added by this office", proposed: "Proposed, waiting for you" };
const ORDER: ModelObject["from"][] = ["industry", "office", "proposed"];
const W = 180, H = 70, DX = 270, DY = 120, COLS = 3, PAD = 20;

/** Deterministic grid: industry objects first, then office, then proposed, three per row. */
export function layout(objects: ModelObject[]) {
  const sorted = [...objects].sort((a, b) => ORDER.indexOf(a.from) - ORDER.indexOf(b.from));
  const at = new Map(sorted.map((o, i) => [o.name, { x: PAD + (i % COLS) * DX, y: PAD + Math.floor(i / COLS) * DY }]));
  const lines = objects.flatMap((o) =>
    o.relations.flatMap((r) => {
      const a = at.get(o.name), b = at.get(r.to) ?? at.get(objects.find((x) => x.label === r.to)?.name ?? "");
      return a && b ? [{ key: `${o.name}-${r.to}-${r.label}`, x1: a.x + W / 2, y1: a.y + H / 2, x2: b.x + W / 2, y2: b.y + H / 2, label: r.label, lx: 0, ly: 0 }] : [];
    }),
  );
  // Spread the labels: start at the middle of each line, slide along it (then step down) until no earlier label is close.
  const placed: { x: number; y: number }[] = [];
  for (const l of lines) {
    for (let k = 0; k < 24; k++) {
      const t = [0.5, 0.35, 0.65, 0.25, 0.75, 0.42, 0.58, 0.3][k % 8] ?? 0.5;
      l.lx = l.x1 + (l.x2 - l.x1) * t;
      l.ly = l.y1 + (l.y2 - l.y1) * t - 4 + Math.floor(k / 8) * 14;
      if (!placed.some((q) => Math.abs(q.x - l.lx) < 70 && Math.abs(q.y - l.ly) < 14)) break;
    }
    placed.push({ x: l.lx, y: l.ly });
  }
  return { sorted, at, lines, height: PAD * 2 + Math.ceil(sorted.length / COLS) * DY - (DY - H) };
}

/** Industry model is just information, office additions are signed (done), Harbor's proposals wait for a person (needs). */
const TONE: Record<ModelObject["from"], string> = { industry: "var(--info)", office: "var(--done)", proposed: "var(--needs)" };
const TINT: Record<ModelObject["from"], string> = { industry: "var(--card)", office: "var(--done-soft)", proposed: "var(--needs-soft)" };

/** The label of a related object, found by its name or label; never the raw name. */
const nameOf = (objects: ModelObject[], to: string) => objects.find((x) => x.name === to || x.label === to)?.label ?? plainName(to);

/** Phone: the relations as sentences, instead of a picture too small to read. */
function Relations({ objects }: { objects: ModelObject[] }) {
  const rows = objects.flatMap((o) => o.relations.map((r) => `${o.label} ${r.label} ${nameOf(objects, r.to)}`));
  return rows.length ? <ul aria-label="How the records relate" style={{ margin: 0, paddingLeft: 20, lineHeight: 1.7 }}>{rows.map((t, i) => <li key={i}>{t}</li>)}</ul> : null;
}

function Graph({ objects, selected, pick }: { objects: ModelObject[]; selected: string; pick: (n: string) => void }) {
  const { sorted, at, lines, height } = layout(objects);
  return (
    <svg viewBox={`0 0 ${PAD * 2 + (COLS - 1) * DX + W} ${height}`} width="100%" role="group" aria-label="How the things Harbor knows connect">
      {lines.map((l) => (
        <g key={l.key}>
          <line x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} style={{ stroke: "var(--info)" }} strokeOpacity={0.6} strokeWidth={1.5} />
        </g>
      ))}
      {sorted.map((o) => {
        const p = at.get(o.name)!;
        const on = o.name === selected;
        return (
          <g key={o.name} role="button" tabIndex={0} aria-pressed={on} aria-label={`${o.label}, ${FROM[o.from]}`} style={{ cursor: "pointer" }}
            onClick={() => pick(o.name)} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && pick(o.name)}>
            <rect x={p.x} y={p.y} width={W} height={H} rx={10} style={{ fill: on ? "var(--act-soft)" : TINT[o.from], stroke: on ? "var(--act)" : TONE[o.from] }}
              strokeWidth={on ? 3 : 1.5} strokeDasharray={o.from === "proposed" ? "5 4" : undefined} />
            <text x={p.x + 12} y={p.y + 22} fontSize={15} fontWeight={600} style={{ fill: "var(--ink)" }}>{o.label}</text>
            <text x={p.x + 12} y={p.y + 40} fontSize={11} fontWeight={600} style={{ fill: TONE[o.from] }}>{FROM[o.from]}</text>
            <text x={p.x + 12} y={p.y + 58} fontSize={11} style={{ fill: "var(--info)" }}>{o.count} rows · {plainName(o.table)}</text>
          </g>
        );
      })}
      {lines.map((l) => (
        <text key={l.key} x={l.lx} y={l.ly} fontSize={11} style={{ fill: "var(--info)", stroke: "var(--card)", strokeWidth: 4, paintOrder: "stroke" }} textAnchor="middle"><title>{l.label}</title>{l.label}</text>
      ))}
    </svg>
  );
}

export default function OntologyPage() {
  const { data: m, setData, failed, load } = useLoad<Model>(getModel);
  const [picked, setPicked] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");

  async function answer(pid: string, a: "admit" | "reject") {
    setBusy(true);
    setProblem("");
    try {
      setData(await decideProposal(pid, a));
    } catch {
      setProblem("That did not go through. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const phone = usePhone();
  const sel = m?.objects.find((o) => o.name === picked) ?? m?.objects[0];
  return (
    <V3Frame>
      <TrustTabs />
      <main className="v3-main">
        {!m ? <Status failed={failed} retry={load} what="what Harbor knows" /> : !m.pack?.id || m.objects.length === 0 ? (
          <div className="v3-card">
            <h1>No industry model yet</h1>
            <p>This office has not picked an industry pack, so there are no objects to show.</p>
            <Link to="/v3/setup">Pick the industry in setup</Link>
          </div>
        ) : (
          <>
            <section className="v3-col" style={{ flex: "999 1 640px" }}>
              <div className="v3-head"><h1>What Harbor knows about your data</h1><span className="v3-mute">{m.pack.label} · v{m.pack.version}</span></div>
              <p className="v3-mute">Each box is a kind of record, with how many rows Harbor holds and where they are kept. Slate: in the industry model. Green: added by this office. Dashed amber: proposed, waiting for you.</p>
              <div className="v3-card">
                {phone && <Relations objects={m.objects} />}
                {phone ? <details><summary>Show the picture</summary><Graph objects={m.objects} selected={sel?.name ?? ""} pick={setPicked} /></details>
                  : <Graph objects={m.objects} selected={sel?.name ?? ""} pick={setPicked} />}
              </div>
              {sel && (
                <div className="v3-card" aria-label="Selected kind of record">
                  <span className="v3-kicker">Selected kind of record · {FROM[sel.from]}</span>
                  <h2>{sel.label}</h2>
                  <div className="tr-scroll"><table style={{ borderCollapse: "collapse", fontSize: 14 }}>
                    <thead><tr><th align="left">Detail</th><th align="left">Where it came from</th></tr></thead>
                    <tbody>
                      {sel.properties.map((p) => (
                        <tr key={p.name}>
                          <td style={{ padding: "6px 16px 6px 0" }}>{p.label}</td>
                          <td style={{ fontSize: 14 }}>{p.column ? plainName(p.column) : p.derived ? "Worked out from other details" : "Not found in your files yet"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table></div>
                  <p className="v3-mute">Kept as {plainName(sel.table)}{sel.relations.length ? ` · ${sel.relations.map((r) => `${r.label} ${nameOf(m.objects, r.to)}`).join(", ")}` : ""}</p>
                </div>
              )}
            </section>
            <aside className="v3-side">
              <h2>Admission queue</h2>
              <p className="v3-mute">Harbor proposes from your files. Nothing joins the model until you admit it.</p>
              {m.proposals.length === 0 && <p className="v3-mute">Nothing waiting.</p>}
              {m.proposals.map((p, i) => (
                <div key={p.id} className="v3-card need">
                  <span className="v3-kicker">Proposal {i + 1} · {p.property ? `property of ${nameOf(m.objects, p.object)}` : "new object"}</span>
                  <p>{p.text}</p>
                  <div className="v3-row">
                    <button type="button" className="go" disabled={busy} onClick={() => answer(p.id, "admit")}>Admit</button>
                    <button type="button" disabled={busy} onClick={() => answer(p.id, "reject")}>Reject</button>
                  </div>
                </div>
              ))}
              {problem && <p className="v3-err" role="alert">{problem}</p>}
              <h2>Version history</h2>
              {m.versions.length === 0 ? <p className="v3-mute">No changes yet.</p> : (
                <ol>{m.versions.map((v) => <li key={String(v.v)}><b>v{v.v}</b> {v.change} <span className="v3-mute">· {v.by}, {v.at}</span></li>)}</ol>
              )}
              <h2>Coverage</h2>
              <div className="v3-fig"><span className="num">{m.coverage.pct}%</span><small>of your numbers are defined here</small></div>
              {m.coverage.unmapped.length > 0 && (
                <>
                  <p className="v3-mute">Not described yet · {m.coverage.unmapped.length} details</p>
                  <ul style={{ margin: 0, fontSize: 14 }}>{m.coverage.unmapped.map((c) => <li key={c}>{plainName(c)}</li>)}</ul>
                  <p className="v3-mute">Harbor will ask before it maps any of them.</p>
                </>
              )}
            </aside>
          </>
        )}
      </main>
    </V3Frame>
  );
}
