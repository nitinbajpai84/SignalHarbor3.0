import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getAccuracy, getRuns, type AccuracyRound, type Run } from "../api";
import { fmtWhen, hasThread, runLabel, useThreadTitles } from "../plain";
import { TrustPage, useLoad } from "./b/Shell";

const HEADS = ["Run", "Use case", "Kind", "Started", "Files in", "Checks passed", "Result", "Signed by"];

function Line({ rows, pick, label, unit }: { rows: AccuracyRound[]; pick: (r: AccuracyRound) => number; label: string; unit: string }) {
  const W = 320, H = 120, max = Math.max(1, ...rows.map(pick));
  const pt = (r: AccuracyRound, i: number) => `${10 + (rows.length > 1 ? (i * (W - 20)) / (rows.length - 1) : (W - 20) / 2)},${H - 20 - (pick(r) / max) * (H - 40)}`;
  return (
    <figure style={{ margin: 0, flex: "1 1 300px" }}>
      <figcaption style={{ fontSize: 14, fontWeight: 500, marginBottom: 4 }}>{label}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${label}: ${rows.map((r) => `${r.round} ${pick(r)}${unit}`).join(", ")}`} style={{ width: "100%", maxWidth: 420 }}>
        <polyline points={rows.map(pt).join(" ")} fill="none" stroke="var(--accent, #2563eb)" strokeWidth="2" />
        {rows.map((r, i) => { const [x, y] = pt(r, i).split(","); return (
          <g key={r.round}><circle cx={x} cy={y} r="3" fill="var(--accent, #2563eb)" /><text x={x} y={H - 4} fontSize="9" textAnchor="middle" fill="var(--mute)">{r.round}</text>
            <text x={x} y={Number(y) - 7} fontSize="9" textAnchor="middle" fill="var(--ink, currentColor)">{pick(r)}{unit}</text></g>); })}
      </svg>
    </figure>
  );
}

function Accuracy() {
  const [rows, setRows] = useState<AccuracyRound[]>([]);
  useEffect(() => { getAccuracy().then((d) => setRows(d.rounds ?? [])).catch(() => setRows([])); }, []);
  if (!rows.length) return null;
  return (
    <section className="v3-card"><h2>Accuracy over time</h2>
      <p className="v3-mute">Each point is one test round, asked of the same kind of questions.</p>
      <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
        <Line rows={rows} pick={(r) => r.right_pct} label="Answers right, by round" unit="%" />
        <Line rows={rows} pick={(r) => r.slipped} label="Wrong answers that slipped through" unit="" />
      </div>
    </section>
  );
}

export default function ProofPage() {
  const s = useLoad(getRuns, "runs");
  const runs: Run[] = s.data?.runs ?? [];
  const title = useThreadTitles();
  return (
    <TrustPage kicker="Trust › Runs and proof · for the auditor" title="Every run, and the checks it passed" sub="Each row is one piece of work Harbor did." state={s}
      empty={s.data && !runs.length ? "No runs yet. The first run appears once a thread has worked on a copy." : false}>
      <Accuracy />
      <section className="v3-card"><h2>Every run</h2>
        <div className="tr-scroll">
          <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 14 }}>
            <thead><tr>{HEADS.map((h) => <th key={h} style={{ textAlign: "left", padding: "0 10px 10px 0", fontSize: 12, color: "var(--mute)", fontWeight: 500 }}>{h}</th>)}</tr></thead>
            <tbody>{runs.map((r) => (
              <tr key={r.run_id} style={{ borderTop: "1px solid var(--line)" }}>
                <td style={{ padding: "10px 10px 10px 0" }} title={r.run_id}>{runLabel(r.started)}</td>
                <td>{hasThread(r.thread) ? <Link to={`/v3/thread/${encodeURIComponent(r.thread)}`} title={r.thread}>{title(r.thread)}</Link> : "No use case"}</td>
                <td>{r.kind === "live" ? "Live" : "Copy"}</td>
                <td>{fmtWhen(r.started)}</td>
                <td className="num">{r.files}</td>
                <td className="num"><span className={`v3-pill ${r.checks_passed < r.checks_total ? "problem" : "done"}`}>{r.checks_passed}/{r.checks_total}</span></td>
                <td>{r.result}</td>
                <td>{r.signed_by}</td>
              </tr>))}</tbody>
          </table>
        </div>
      </section>
      <section className="v3-card"><h2>Linked to the board</h2>
        <p className="v3-mute">Open any figure on the board and it shows the run behind it, the files it came from and the checks it passed.</p>
      </section>
    </TrustPage>
  );
}
