import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getFigure, rollbackFigure, type FigureRecord } from "../api";
import V3Frame from "../Frame";
import { Failed, Waiting, useRead } from "../board/common";
import { Pill, day } from "./FiguresPage";
import { thingPath } from "./k/kinds";
import "./figures.css";

const Box = ({ name, rows, out }: { name?: string; rows?: number; out?: boolean }) => (
  <div className={out ? "fg-box out" : "fg-box"}>{name}{rows != null ? <span className="v3-mute"> · {rows} rows</span> : null}</div>
);

/** /v3/knowledge/figures/:id: where a figure comes from, what I assumed, its runs and versions. */
export default function FigurePage() {
  const { id = "" } = useParams();
  const [got, again] = useRead(() => getFigure(id));
  const [over, setOver] = useState<FigureRecord | null>(null);
  const [ask, setAsk] = useState<number | null>(null);  // the version waiting for "Yes, roll back"
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  if (got.state === "loading") return <V3Frame><main className="fg-page"><Waiting what="Reading the figure" /></main></V3Frame>;
  if (got.state === "error") return <V3Frame><main className="fg-page"><Failed message={got.message} again={again} /></main></V3Frame>;
  const f = over ?? got.data;
  const cur = f.versions.find((v) => v.v === f.current_v) ?? f.versions[f.versions.length - 1];
  const roll = (v: number) => {
    setBusy(true); setErr("");
    rollbackFigure(id, v).then((r) => { setOver(r); setAsk(null); }, (e: Error) => setErr(e.message || "I could not roll back.")).finally(() => setBusy(false));
  };
  const runs = f.versions.flatMap((v) => v.runs.map((r) => ({ ...r, v: v.v }))).sort((a, b) => b.at.localeCompare(a.at));
  const assumed = cur?.assumptions ?? [];
  return (
    <V3Frame>
      <main className="fg-page">
        <div>
          <Link to="/v3/knowledge/figures">All figures</Link>
          <h1>{f.name} {cur && <Pill s={cur.status} />}</h1>
          <p className="v3-mute">{f.definition}{f.grain.length ? ` Per ${f.grain.join(" and ")}.` : ""}</p>
          <p>
            <Link to={thingPath(`figure:${f.id.replace(/^fig-/, "")}`)}>See it on the knowledge map</Link>
            {cur?.built_from?.kind === "recipe" ? <> · <Link to={thingPath(`recipe:${cur.built_from.id}`)}>The recipe it follows</Link></> : null}
          </p>
        </div>
        <section aria-labelledby="fg-lin">
          <h2 id="fg-lin">Where this number comes from</h2>
          <div className="fg-lineage">
            <div className="fg-col">{f.lineage.files.map((x) => <Box key={x.name} {...x} />)}</div>
            <span className="fg-arrow" aria-hidden="true">→</span>
            <div className="fg-col">{f.lineage.tables.map((x) => <Box key={x.name} {...x} />)}</div>
            <span className="fg-arrow" aria-hidden="true">→</span>
            <div className="fg-col"><Box out name={f.lineage.figure.name ?? f.name} /></div>
          </div>
        </section>
        <section aria-labelledby="fg-ass">
          <h2 id="fg-ass">What I assumed</h2>
          {assumed.length ? <ul>{assumed.map((a, i) => <li key={i}>{a.text} <span className="v3-mute">({a.source})</span></li>)}</ul> : <p className="v3-mute">Nothing was assumed.</p>}
        </section>
        <section aria-labelledby="fg-runs" className="fg-wide">
          <h2 id="fg-runs">Runs</h2>
          {runs.length ? (
            <table><thead><tr><th>Date</th><th>Result</th><th>Rows</th></tr></thead>
              <tbody>{runs.map((r) => <tr key={r.run_id}><td>{day(r.at)}</td><td><span className={`v3-pill ${r.ok ? "done" : "problem"}`}>{r.ok ? "OK" : "Failed"}</span></td><td>{r.rows}</td></tr>)}</tbody></table>
          ) : <p className="v3-mute">No runs yet.</p>}
        </section>
        <section aria-labelledby="fg-ver" className="fg-wide">
          <h2 id="fg-ver">Versions</h2>
          {err && <p className="v3-err" role="alert">{err}</p>}
          <table><thead><tr><th>Version</th><th>Status</th><th>Approved</th><th /></tr></thead>
            <tbody>{[...f.versions].reverse().map((v) => (
              <tr key={v.v}>
                <td>v{v.v}{v.v === cur?.v ? " (current)" : ""}</td><td><Pill s={v.status} /></td>
                <td>{v.approved_by ? `${v.approved_by}, ${day(v.approved_at)}` : "Not yet"}</td>
                <td>{v.status === "verified" && v.v !== cur?.v && <button type="button" className="go" disabled={busy} onClick={() => setAsk(v.v)}>Roll back</button>}</td>
              </tr>))}
            </tbody></table>
          {ask != null && (
            <div className="fg-roll" role="alertdialog" aria-label="Confirm roll back">
              <p>Make v{ask} the current version of {f.name}? Everything that uses this figure will read v{ask} from now on.</p>
              <div className="v3-row">
                <button type="button" className="go" disabled={busy} onClick={() => roll(ask)}>Yes, roll back</button>
                <button type="button" disabled={busy} onClick={() => setAsk(null)}>Cancel</button>
              </div>
            </div>
          )}
        </section>
        <section aria-labelledby="fg-use">
          <h2 id="fg-use">Also used by</h2>
          {f.used_by.length ? <ul>{f.used_by.map((u, i) => <li key={i}><Link to={`/v3/thread/${encodeURIComponent(u.thread)}`}>{u.brief}</Link> <span className="v3-mute">{u.person}</span></li>)}</ul> : <p className="v3-mute">Nothing else uses this figure yet.</p>}
        </section>
      </main>
    </V3Frame>
  );
}
